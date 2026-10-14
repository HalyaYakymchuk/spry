#!/usr/bin/env bash
# Delete the reports stack: S3 bucket and S3 Gateway VPC Endpoint.
# The bucket is emptied first if it contains any objects.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

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

command -v aws >/dev/null 2>&1 || die "aws cli is required"
aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1 \
  || die "stack ${STACK_NAME} does not exist in ${AWS_REGION}"

if [[ "${FORCE:-0}" != "1" ]]; then
  echo "This deletes stack ${STACK_NAME} in ${AWS_REGION}: the reports S3"
  echo "bucket and the S3 Gateway VPC Endpoint."
  read -r -p "Type the stack name to confirm: " reply
  [[ "${reply}" == "${STACK_NAME}" ]] || die "aborted"
fi

BUCKET="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ReportsBucketName'].OutputValue" \
  --output text 2>/dev/null || true)"

if [[ -n "${BUCKET}" && "${BUCKET}" != "None" ]]; then
  log "emptying s3://${BUCKET}"
  aws s3 rm "s3://${BUCKET}" --recursive --only-show-errors || true
fi

log "deleting ${STACK_NAME}"
aws cloudformation delete-stack --stack-name "${STACK_NAME}" --region "${AWS_REGION}"
aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}" --region "${AWS_REGION}"

log "done - stack deleted"
