#!/usr/bin/env bash
# Delete the agenda parser CloudFormation stack.
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
STACK_NAME="${PARSER_STACK_NAME:-${PROJECT_NAME}-parser}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-north-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  log "stack ${STACK_NAME} does not exist"
  exit 0
fi

log "deleting ${STACK_NAME}"
aws cloudformation delete-stack --stack-name "${STACK_NAME}" --region "${AWS_REGION}"
aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}" --region "${AWS_REGION}"
log "${STACK_NAME} deleted"
