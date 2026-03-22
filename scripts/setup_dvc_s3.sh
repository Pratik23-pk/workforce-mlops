#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/prompt_utils.sh" ]]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/prompt_utils.sh"
fi

MODE="${MODE:-cli}" # cli|console

if [[ "${1:-}" == "--console" ]]; then
  MODE="console"
fi
if [[ "${1:-}" == "--cli" ]]; then
  MODE="cli"
fi

if [[ "$MODE" != "cli" && "$MODE" != "console" ]]; then
  echo "Invalid MODE='${MODE}'. Use MODE=cli or MODE=console."
  exit 1
fi

if [[ -z "${DVC_S3_BUCKET:-}" ]] && command -v prompt_value >/dev/null 2>&1; then
  prompt_value DVC_S3_BUCKET "Enter DVC S3 bucket name"
fi
if [[ -z "${AWS_REGION:-}" ]] && command -v prompt_value >/dev/null 2>&1; then
  prompt_value AWS_REGION "Enter AWS region" "us-east-1"
fi

if [[ -z "${DVC_S3_BUCKET:-}" || -z "${AWS_REGION:-}" ]]; then
  echo "Set DVC_S3_BUCKET and AWS_REGION first."
  exit 1
fi

if [[ "${DVC_S3_BUCKET}" == *"<"* || "${DVC_S3_BUCKET}" == *">"* ]]; then
  echo "DVC_S3_BUCKET looks like placeholder text: ${DVC_S3_BUCKET}"
  exit 1
fi

if [[ "$MODE" == "console" ]]; then
  echo "MODE=console selected."
  echo "No AWS Console action is needed for this step if bucket already exists."
  echo "Run these local commands to point DVC to your S3 bucket:"
  echo
  echo "  dvc config core.site_cache_dir .dvc/site-cache"
  echo "  dvc remote add -d origin s3://${DVC_S3_BUCKET}/dvc --force"
  echo "  dvc remote modify origin --unset endpointurl"
  echo "  dvc remote modify origin region ${AWS_REGION}"
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    echo "  dvc remote modify --local origin profile ${AWS_PROFILE}"
  fi
  echo "  dvc push -v -j 1"
  exit 0
fi

if ! command -v dvc >/dev/null 2>&1; then
  echo "dvc is not installed in the active environment."
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found. Install and configure it first."
  exit 1
fi

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials are not configured or invalid. Run 'aws configure' first."
  exit 1
fi

if [[ ! -d .dvc ]]; then
  dvc init
fi

# Ensure site cache stays in project workspace to avoid permission issues.
dvc config core.site_cache_dir .dvc/site-cache

# Reset local DVC credentials/config to avoid stale settings.
rm -f .dvc/config.local

dvc remote add -d origin "s3://${DVC_S3_BUCKET}/dvc" --force
dvc remote modify origin --unset endpointurl || true
dvc remote modify origin region "${AWS_REGION}"

if [[ -n "${AWS_PROFILE:-}" ]]; then
  dvc remote modify --local origin profile "${AWS_PROFILE}"
fi

echo "DVC S3 remote configured."
echo "  remote: s3://${DVC_S3_BUCKET}/dvc"
echo "  region: ${AWS_REGION}"
if [[ -n "${AWS_PROFILE:-}" ]]; then
  echo "  profile: ${AWS_PROFILE}"
fi

echo
echo "Verify AWS credentials: aws sts get-caller-identity"
echo "Then push: dvc push -v -j 1"
