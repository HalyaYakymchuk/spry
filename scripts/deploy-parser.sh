#!/usr/bin/env bash
# Deploy the AI agenda parser infrastructure defined in infra/parser.yaml:
# Stateless Lambda running outside VPC with public Function URL, Bedrock Claude,
# and Cognito JWT authentication.
#
# Safe to re-run: idempotent CloudFormation deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/parser.yaml"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

to_win_path() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$1"
  else
    echo "$1"
  fi
}

# --- configuration ----------------------------------------------------------

if [[ -f "${ENV_FILE}" ]]; then
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  eval "${preset}"
fi

for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
STACK_NAME="${PARSER_STACK_NAME:-${PROJECT_NAME}-parser}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-north-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

if [[ "${AWS_REGION}" == "us-east-1" ]]; then
  die "us-east-1 is blocked by SCP explicit deny policy. Please use eu-north-1."
fi

LAMBDA_ARCHITECTURE="${LAMBDA_ARCHITECTURE:-arm64}"
case "${LAMBDA_ARCHITECTURE}" in
  arm64) CFN_ARCHITECTURE=arm64 ;;
  amd64|x86_64) CFN_ARCHITECTURE=x86_64 ;;
  *) die "LAMBDA_ARCHITECTURE must be arm64 or amd64, got '${LAMBDA_ARCHITECTURE}'" ;;
esac

# --- helpers ----------------------------------------------------------------

env_set() {
  local key="$1"
  local val="$2"
  local env_win
  env_win="$(to_win_path "${ENV_FILE}")"
  KEY="${key}" VALUE="${val}" ENV_FILE="${env_win}" python3 - <<'PY'
import os, re

key, value, path = os.environ["KEY"], os.environ["VALUE"], os.environ["ENV_FILE"]
lines = open(path).read().splitlines() if os.path.exists(path) else []
pattern = re.compile(rf"^{re.escape(key)}=")

for i, line in enumerate(lines):
    if pattern.match(line):
        lines[i] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")

open(path, "w").write("\n".join(lines) + "\n")
PY
  log "wrote ${1}=${2} to .env"
}

# --- preflight --------------------------------------------------------------

for tool in aws python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "no usable AWS credentials"
log "account ${ACCOUNT_ID} in ${AWS_REGION}"

# --- image discovery / build ------------------------------------------------

IMAGE_URI="${IMAGE_URI:-}"
if [[ -z "${IMAGE_URI}" ]]; then
  # Try finding latest tagged image in ECR
  LATEST_TAG="$(aws ecr describe-images --repository-name "${PROJECT_NAME}-backend" --region "${AWS_REGION}" \
    --query 'sort_by(imageDetails,& imagePushedAt)[-1].imageTags[0]' --output text 2>/dev/null || true)"
  if [[ -n "${LATEST_TAG}" && "${LATEST_TAG}" != "None" ]]; then
    REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    IMAGE_URI="${REGISTRY}/${PROJECT_NAME}-backend:${LATEST_TAG}"
  fi
fi

if [[ -z "${IMAGE_URI}" || "${IMAGE_URI}" == "None" ]]; then
  # Fallback to reports stack
  IMAGE_URI="$(aws cloudformation describe-stacks --stack-name "${PROJECT_NAME}-reports" --region "${AWS_REGION}" \
    --query "Stacks[0].Parameters[?ParameterKey=='ImageUri'].ParameterValue" --output text 2>/dev/null || true)"
fi

if [[ -z "${IMAGE_URI}" || "${IMAGE_URI}" == "None" ]]; then
  REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  IMAGE_URI="${REGISTRY}/${PROJECT_NAME}-backend:reports-step4"
fi

# Build and push new image if requested or if docker daemon is active and build is forced
if [[ "${BUILD_IMAGE:-false}" == "true" ]]; then
  REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  IMAGE_TAG="parser-$(date -u +%Y%m%d%H%M%S)"
  IMAGE_URI="${REGISTRY}/${PROJECT_NAME}-backend:${IMAGE_TAG}"

  log "building and pushing ${IMAGE_URI}"
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${REGISTRY}" >/dev/null

  docker buildx build \
    --platform "linux/${LAMBDA_ARCHITECTURE}" \
    --target lambda \
    --provenance=false \
    --sbom=false \
    --tag "${IMAGE_URI}" \
    --push \
    "${ROOT}/backend"
fi

log "using ImageUri: ${IMAGE_URI}"

# --- cognito discovery ------------------------------------------------------

COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:-}"
if [[ -z "${COGNITO_USER_POOL_ID}" ]]; then
  COGNITO_USER_POOL_ID="$(aws cloudformation describe-stacks --stack-name "${PROJECT_NAME}-cognito" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text 2>/dev/null || true)"
fi
[[ -n "${COGNITO_USER_POOL_ID}" && "${COGNITO_USER_POOL_ID}" != "None" ]] || die "could not resolve COGNITO_USER_POOL_ID"

COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:-}"
if [[ -z "${COGNITO_CLIENT_ID}" ]]; then
  COGNITO_CLIENT_ID="$(aws cloudformation describe-stacks --stack-name "${PROJECT_NAME}-cognito" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='ClientId'].OutputValue" --output text 2>/dev/null || true)"
fi
[[ -n "${COGNITO_CLIENT_ID}" && "${COGNITO_CLIENT_ID}" != "None" ]] || die "could not resolve COGNITO_CLIENT_ID"

PARSER_MODEL="${PARSER_MODEL:-eu.anthropic.claude-haiku-4-5-20251001-v1:0}"

log "using Cognito Pool: ${COGNITO_USER_POOL_ID}, Client: ${COGNITO_CLIENT_ID}"
log "using Parser Model: ${PARSER_MODEL}"

# --- deploy -----------------------------------------------------------------

if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  log "first deploy - creating ${STACK_NAME}"
else
  log "updating ${STACK_NAME}"
fi

PARAMS=(
  "ProjectName=${PROJECT_NAME}"
  "ImageUri=${IMAGE_URI}"
  "Architecture=${CFN_ARCHITECTURE}"
  "ParserModel=${PARSER_MODEL}"
  "CognitoUserPoolId=${COGNITO_USER_POOL_ID}"
  "CognitoClientId=${COGNITO_CLIENT_ID}"
)

TEMPLATE_WIN="$(to_win_path "${TEMPLATE}")"
aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE_WIN}" \
  --parameter-overrides "${PARAMS[@]}" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region "${AWS_REGION}" \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"

PARSER_FUNCTION_URL="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ParserFunctionUrl'].OutputValue" --output text)"

env_set PARSER_FUNCTION_URL "${PARSER_FUNCTION_URL}"
env_set NEXT_PUBLIC_PARSER_URL "${PARSER_FUNCTION_URL}"

log "Agenda Parser Function URL: ${PARSER_FUNCTION_URL}"
log "Deployment complete!"
