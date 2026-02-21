#!/usr/bin/env bash
set -euo pipefail

required_vars=(
  AWS_ROLE_TO_ASSUME
  AWS_REGION
  ECR_REPOSITORY
  EC2_HOST
  EC2_USER
  EC2_SSH_KEY_PATH
)

for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: ${name}"
    exit 1
  fi
done

if [[ ! -f "${EC2_SSH_KEY_PATH}" ]]; then
  echo "EC2_SSH_KEY_PATH file not found: ${EC2_SSH_KEY_PATH}"
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI not found. Install gh and run gh auth login"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login"
  exit 1
fi

gh secret set AWS_ROLE_TO_ASSUME --body "${AWS_ROLE_TO_ASSUME}"
gh secret set AWS_REGION --body "${AWS_REGION}"
gh secret set ECR_REPOSITORY --body "${ECR_REPOSITORY}"
gh secret set EC2_HOST --body "${EC2_HOST}"
gh secret set EC2_USER --body "${EC2_USER}"
gh secret set EC2_SSH_KEY < "${EC2_SSH_KEY_PATH}"

if [[ -n "${MLFLOW_TRACKING_URI:-}" ]]; then
  gh secret set MLFLOW_TRACKING_URI --body "${MLFLOW_TRACKING_URI}"
fi

if [[ -n "${DVC_S3_BUCKET:-}" ]]; then
  gh secret set DVC_S3_BUCKET --body "${DVC_S3_BUCKET}"
fi

echo "GitHub Actions secrets configured for current repository."
