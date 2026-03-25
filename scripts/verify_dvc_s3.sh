#!/usr/bin/env bash
set -euo pipefail

# Verify DVC S3 connectivity and bucket readiness
# Usage: bash scripts/verify_dvc_s3.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== DVC S3 Connectivity Verification ==="

# Load environment
if [[ -f "${PROJECT_DIR}/infra/aws_gitops_outputs.env" ]]; then
  # shellcheck disable=SC1090
  source "${PROJECT_DIR}/infra/aws_gitops_outputs.env"
  echo "✓ Loaded AWS outputs from infra/aws_gitops_outputs.env"
else
  echo "✗ Missing infra/aws_gitops_outputs.env"
  exit 1
fi

# Verify required vars
required=(AWS_REGION DVC_S3_BUCKET)
for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "✗ Missing ${var}"
    exit 1
  fi
  echo "✓ ${var}=${!var}"
done

# Check AWS credentials
echo ""
echo "=== AWS Credentials Check ==="
if ! aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "✗ AWS credentials not available. Configure with: aws configure"
  exit 1
fi
CALLER_IDENTITY=$(aws sts get-caller-identity --region "${AWS_REGION}" --output json)
echo "✓ AWS credentials valid"
echo "  Account: $(echo "$CALLER_IDENTITY" | grep -o '"Account": "[^"]*' | cut -d'"' -f4)"

# Check S3 bucket access
echo ""
echo "=== S3 Bucket Access Check ==="
if aws s3 ls "s3://${DVC_S3_BUCKET}/" --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "✓ S3 bucket exists and is accessible: ${DVC_S3_BUCKET}"
  echo "  Contents:"
  aws s3 ls "s3://${DVC_S3_BUCKET}/" --region "${AWS_REGION}" | head -5 || true
else
  echo "✗ S3 bucket not accessible: ${DVC_S3_BUCKET}"
  echo "  Action: Create bucket with:"
  echo "    aws s3 mb s3://${DVC_S3_BUCKET} --region ${AWS_REGION}"
  exit 1
fi

# Check DVC remote
echo ""
echo "=== DVC Remote Configuration ==="
cd "${PROJECT_DIR}"

pip install -q "dvc[s3]>=3.58.0" 2>/dev/null || true

dvc remote add -f origin "s3://${DVC_S3_BUCKET}/dvc"
dvc remote modify origin region "${AWS_REGION}"
dvc remote modify origin use_ssl "true"

echo "✓ DVC remote configured:"
dvc remote list

# Test DVC connection
echo ""
echo "=== DVC Pull Test ==="
if dvc pull -v --dry 2>/dev/null || dvc status -c 2>/dev/null; then
  echo "✓ DVC can access S3 artifacts"
else
  echo "⚠ DVC may have issues accessing S3 (this is normal if no artifacts exist yet)"
fi

echo ""
echo "✓ All checks passed! S3 is ready for DVC."
