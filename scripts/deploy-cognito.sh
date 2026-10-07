#!/usr/bin/env bash
# Deploy the Cognito User Pool, App Client, and Hosted UI Domain defined in
# infra/cognito.yaml, and write client/domain/pool IDs into .env.
#
# Safe to re-run: idempotent CloudFormation deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/cognito.yaml"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# Helper to normalize paths for native Windows Python when running in Git Bash
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
STACK_NAME="${COGNITO_STACK_NAME:-${PROJECT_NAME}-cognito}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-north-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

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

with open(path, "w") as fh:
    fh.write("\n".join(lines) + "\n")
PY
  log "wrote ${key}=${val} to .env"
}

# --- preflight --------------------------------------------------------------

for tool in aws python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "no usable AWS credentials - set AWS_PROFILE or the AWS_* keys in .env"
CALLER="$(aws sts get-caller-identity --query Arn --output text)"
log "account ${ACCOUNT_ID} in ${AWS_REGION} as ${CALLER}"

# --- parameters -------------------------------------------------------------

CALLBACK_URLS="${COGNITO_CALLBACK_URLS:-http://localhost:3000}"
if [[ -n "${SITE_URL:-}" && "${CALLBACK_URLS}" != *"${SITE_URL}"* ]]; then
  CALLBACK_URLS="${CALLBACK_URLS},${SITE_URL}"
fi

LOGOUT_URLS="${COGNITO_LOGOUT_URLS:-http://localhost:3000}"
if [[ -n "${SITE_URL:-}" && "${LOGOUT_URLS}" != *"${SITE_URL}"* ]]; then
  LOGOUT_URLS="${LOGOUT_URLS},${SITE_URL}"
fi

DOMAIN_PREFIX="${COGNITO_DOMAIN_PREFIX:-${PROJECT_NAME}-${ACCOUNT_ID}}"
DOMAIN_PREFIX="$(echo "${DOMAIN_PREFIX}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')"

PARAMS_FILE="$(mktemp)"
PARAMS_FILE_WIN="$(to_win_path "${PARAMS_FILE}")"
chmod 600 "${PARAMS_FILE}"
trap 'rm -f "${PARAMS_FILE}"' EXIT

PROJECT_NAME="${PROJECT_NAME}" \
CALLBACK_URLS="${CALLBACK_URLS}" \
LOGOUT_URLS="${LOGOUT_URLS}" \
DOMAIN_PREFIX="${DOMAIN_PREFIX}" \
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}" \
python3 - "${PARAMS_FILE_WIN}" <<'PY'
import json, os, sys

params = {
    "ProjectName": os.environ["PROJECT_NAME"],
    "CallbackUrls": os.environ["CALLBACK_URLS"],
    "LogoutUrls": os.environ["LOGOUT_URLS"],
    "DomainPrefix": os.environ["DOMAIN_PREFIX"],
    "GoogleClientId": os.environ["GOOGLE_CLIENT_ID"],
    "GoogleClientSecret": os.environ["GOOGLE_CLIENT_SECRET"],
}

with open(sys.argv[1], "w") as fh:
    json.dump(
        [
            {"ParameterKey": k, "ParameterValue": v}
            for k, v in params.items()
            if v != ""
        ],
        fh,
    )
PY

# --- deploy -----------------------------------------------------------------

if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  log "first deploy - creating ${STACK_NAME}"
else
  log "updating ${STACK_NAME}"
fi

TEMPLATE_WIN="$(to_win_path "${TEMPLATE}")"
if ! aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE_WIN}" \
  --parameter-overrides "file://${PARAMS_FILE_WIN}" \
  --region "${AWS_REGION}" \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"; then
  warn "deploy failed - most recent failure reasons:"
  aws cloudformation describe-stack-events --stack-name "${STACK_NAME}" --region "${AWS_REGION}" \
    --max-items 40 \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`||ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
    --output table >&2 || true
  exit 1
fi

outputs() {
  aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

USER_POOL_ID="$(outputs UserPoolId)"
CLIENT_ID="$(outputs ClientId)"
COGNITO_DOMAIN="$(outputs CognitoDomain)"
GOOGLE_ENABLED="$(outputs GoogleEnabled)"

# --- update .env ------------------------------------------------------------

env_set COGNITO_REGION "${AWS_REGION}"
env_set COGNITO_USER_POOL_ID "${USER_POOL_ID}"
env_set COGNITO_CLIENT_ID "${CLIENT_ID}"
env_set COGNITO_DOMAIN "${COGNITO_DOMAIN}"
env_set COGNITO_GOOGLE_ENABLED "${GOOGLE_ENABLED}"

# --- report -----------------------------------------------------------------

echo
echo "Cognito deployment complete:"
echo "  COGNITO_REGION         ${AWS_REGION}"
echo "  COGNITO_USER_POOL_ID   ${USER_POOL_ID}"
echo "  COGNITO_CLIENT_ID      ${CLIENT_ID}"
echo "  COGNITO_DOMAIN         ${COGNITO_DOMAIN}"
echo "  COGNITO_GOOGLE_ENABLED ${GOOGLE_ENABLED}"
echo
echo "OAuth redirect URI for Google Cloud Console (if using Google IdP):"
echo "  https://${COGNITO_DOMAIN}/oauth2/idpresponse"
echo
