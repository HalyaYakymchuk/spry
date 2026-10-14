#!/usr/bin/env bash
# Deploy the reports infrastructure defined in infra/reports.yml:
# private S3 bucket with 90-day lifecycle rule and S3 Gateway VPC Endpoint.
#
# Safe to re-run: idempotent CloudFormation deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/reports.yml"
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
STACK_NAME="${REPORTS_STACK_NAME:-${PROJECT_NAME}-reports}"
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

# --- network discovery ------------------------------------------------------

VPC_ID="${AWS_VPC_ID:-}"
if [[ -z "${VPC_ID}" ]]; then
  # Try backend stack parameter first if stack exists
  VPC_ID="$(aws cloudformation describe-stacks --stack-name "${PROJECT_NAME}-backend" --region "${AWS_REGION}" \
    --query "Stacks[0].Parameters[?ParameterKey=='VpcId'].ParameterValue" --output text 2>/dev/null || true)"
fi
if [[ -z "${VPC_ID}" || "${VPC_ID}" == "None" ]]; then
  VPC_ID="$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
    --region "${AWS_REGION}" --query 'Vpcs[0].VpcId' --output text 2>/dev/null || true)"
fi
[[ -n "${VPC_ID}" && "${VPC_ID}" != "None" ]] || die "could not resolve VPC ID"

ROUTE_TABLE_IDS="${AWS_ROUTE_TABLE_IDS:-}"
if [[ -z "${ROUTE_TABLE_IDS}" ]]; then
  ROUTE_TABLE_IDS="$(aws ec2 describe-route-tables --filters Name=vpc-id,Values="${VPC_ID}" \
    --region "${AWS_REGION}" --query 'RouteTables[*].RouteTableId' --output text 2>/dev/null | tr '\t' ',')"
fi
[[ -n "${ROUTE_TABLE_IDS}" && "${ROUTE_TABLE_IDS}" != "None" ]] || die "could not resolve Route Table IDs"

# --- backend resource discovery --------------------------------------------

IMAGE_URI="${IMAGE_URI:-${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-backend:reports-step4}"

SUBNET_IDS="${AWS_SUBNET_IDS:-}"
if [[ -z "${SUBNET_IDS}" ]]; then
  SUBNET_IDS="$(aws lambda get-function-configuration --function-name "${PROJECT_NAME}-backend" \
    --region "${AWS_REGION}" --query "VpcConfig.SubnetIds" --output text 2>/dev/null | tr '\t' ',' || true)"
fi

SECURITY_GROUP_IDS="${AWS_SECURITY_GROUP_IDS:-}"
if [[ -z "${SECURITY_GROUP_IDS}" ]]; then
  SECURITY_GROUP_IDS="$(aws lambda get-function-configuration --function-name "${PROJECT_NAME}-backend" \
    --region "${AWS_REGION}" --query "VpcConfig.SecurityGroupIds" --output text 2>/dev/null | tr '\t' ',' || true)"
fi

if [[ -z "${DATABASE_URL:-}" || "${DATABASE_URL}" =~ @postgres: || "${DATABASE_URL}" =~ localhost || "${DATABASE_URL}" =~ 127\.0\.0\.1 ]]; then
  DATABASE_URL="$(aws secretsmanager get-secret-value --secret-id "${PROJECT_NAME}/backend/database-url" \
    --region "${AWS_REGION}" --query SecretString --output text 2>/dev/null || true)"
fi

log "using VPC ${VPC_ID} and route table(s) ${ROUTE_TABLE_IDS}"
[[ -n "${IMAGE_URI}" && "${IMAGE_URI}" != "None" ]] && log "using ImageUri ${IMAGE_URI}"

# --- deploy -----------------------------------------------------------------

if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  log "first deploy - creating ${STACK_NAME}"
else
  log "updating ${STACK_NAME}"
fi

DOMAIN_NAME="${DOMAIN_NAME:-${DOMAIN:-spry.org.ua}}"
SENDER_EMAIL="${SENDER_EMAIL:-reports@${DOMAIN_NAME}}"
RECIPIENT_EMAIL="${RECIPIENT_EMAIL:-galyayakymchuk19@gmail.com}"
HOSTED_ZONE_ID="${HOSTED_ZONE_ID:-}"

PARAMS=(
  "ProjectName=${PROJECT_NAME}"
  "VpcId=${VPC_ID}"
  "RouteTableIds=${ROUTE_TABLE_IDS}"
  "DomainName=${DOMAIN_NAME}"
  "SenderEmail=${SENDER_EMAIL}"
  "RecipientEmail=${RECIPIENT_EMAIL}"
)
[[ -n "${HOSTED_ZONE_ID}" ]] && PARAMS+=("HostedZoneId=${HOSTED_ZONE_ID}")
[[ -n "${IMAGE_URI}" && "${IMAGE_URI}" != "None" ]] && PARAMS+=("ImageUri=${IMAGE_URI}")
[[ -n "${SUBNET_IDS}" && "${SUBNET_IDS}" != "None" ]] && PARAMS+=("SubnetIds=${SUBNET_IDS}")
[[ -n "${SECURITY_GROUP_IDS}" && "${SECURITY_GROUP_IDS}" != "None" ]] && PARAMS+=("SecurityGroupIds=${SECURITY_GROUP_IDS}")
[[ -n "${DATABASE_URL}" ]] && PARAMS+=("DatabaseUrl=${DATABASE_URL}")

TEMPLATE_WIN="$(to_win_path "${TEMPLATE}")"
aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE_WIN}" \
  --parameter-overrides "${PARAMS[@]}" \
  --capabilities CAPABILITY_IAM \
  --region "${AWS_REGION}" \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"

outputs() {
  aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

BUCKET_NAME="$(outputs ReportsBucketName)"
BUCKET_ARN="$(outputs ReportsBucketArn)"
VPCE_ID="$(outputs S3EndpointId)"
BUILDER_ARN="$(outputs ReportBuilderFunctionArn)"
BUILDER_NAME="$(outputs ReportBuilderFunctionName)"
MAILER_ARN="$(outputs ReportMailerFunctionArn)"
MAILER_NAME="$(outputs ReportMailerFunctionName)"
SCHEDULE_ARN="$(outputs WeeklyReportScheduleArn)"
QUEUE_URL="$(outputs ReportRequestsQueueUrl)"
QUEUE_ARN="$(outputs ReportRequestsQueueArn)"
TOKEN1_NAME="$(outputs DkimDNSTokenName1)"
TOKEN1_VAL="$(outputs DkimDNSTokenValue1)"
TOKEN2_NAME="$(outputs DkimDNSTokenName2)"
TOKEN2_VAL="$(outputs DkimDNSTokenValue2)"
TOKEN3_NAME="$(outputs DkimDNSTokenName3)"
TOKEN3_VAL="$(outputs DkimDNSTokenValue3)"

if [[ -f "${ENV_FILE}" ]]; then
  env_set REPORTS_BUCKET_NAME "${BUCKET_NAME}"
  env_set REPORTS_BUCKET_ARN "${BUCKET_ARN}"
  env_set REPORT_REQUESTS_QUEUE_URL "${QUEUE_URL}"
  env_set REPORT_REQUESTS_QUEUE_ARN "${QUEUE_ARN}"
  env_set DOMAIN_NAME "${DOMAIN_NAME}"
  env_set SENDER_EMAIL "${SENDER_EMAIL}"
  env_set RECIPIENT_EMAIL "${RECIPIENT_EMAIL}"
fi

echo
echo "Reports infrastructure deployment complete:"
echo "  Bucket Name:        ${BUCKET_NAME}"
echo "  Bucket ARN:         ${BUCKET_ARN}"
echo "  S3 VPC Endpoint:    ${VPCE_ID}"
echo "  Builder Lambda:     ${BUILDER_NAME} (${BUILDER_ARN})"
echo "  Mailer Lambda:      ${MAILER_NAME} (${MAILER_ARN})"
echo "  Weekly Schedule:    ${SCHEDULE_ARN}"
echo "  Requests Queue:     ${QUEUE_URL}"
echo "  Requests Queue ARN: ${QUEUE_ARN}"
echo "  Domain Name:        ${DOMAIN_NAME}"
echo "  Sender Email:       ${SENDER_EMAIL}"
echo "  Recipient Email:    ${RECIPIENT_EMAIL}"
echo
echo "DKIM DNS Configuration (Add these 3 CNAME records to DNS for ${DOMAIN_NAME}):"
echo "  Record 1:"
echo "    Host/Name:  ${TOKEN1_NAME}"
echo "    Type:       CNAME"
echo "    Value:      ${TOKEN1_VAL}"
echo "  Record 2:"
echo "    Host/Name:  ${TOKEN2_NAME}"
echo "    Type:       CNAME"
echo "    Value:      ${TOKEN2_VAL}"
echo "  Record 3:"
echo "    Host/Name:  ${TOKEN3_NAME}"
echo "    Type:       CNAME"
echo "    Value:      ${TOKEN3_VAL}"
echo
