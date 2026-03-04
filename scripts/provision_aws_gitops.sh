#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-workforce-mlops}"
AWS_REGION="${AWS_REGION:-us-east-1}"
GITHUB_REPO="${GITHUB_REPO:-}"
ECR_REPOSITORY="${ECR_REPOSITORY:-${PROJECT_NAME}-app}"
DVC_S3_BUCKET="${DVC_S3_BUCKET:-}"
MLFLOW_S3_BUCKET="${MLFLOW_S3_BUCKET:-}"
GITHUB_ROLE_NAME="${GITHUB_ROLE_NAME:-GitHubActionsWorkforceGitOpsRole}"
OUTPUT_FILE="${OUTPUT_FILE:-infra/aws_gitops_outputs.env}"
MODE="${MODE:-cli}" # cli|console

if [[ "${1:-}" == "--console" ]]; then
  MODE="console"
fi
if [[ "${1:-}" == "--cli" ]]; then
  MODE="cli"
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1"
    exit 1
  fi
}

bucket_is_placeholder() {
  local value="$1"
  [[ "$value" == *"<"* || "$value" == *">"* ]]
}

bucket_name_valid() {
  local value="$1"
  [[ "$value" =~ ^[a-z0-9.-]{3,63}$ ]]
}

if [[ "$MODE" != "cli" && "$MODE" != "console" ]]; then
  echo "Invalid MODE='${MODE}'. Use MODE=cli or MODE=console."
  exit 1
fi

if [[ -z "$GITHUB_REPO" ]]; then
  echo "Set GITHUB_REPO, e.g. export GITHUB_REPO='Pratik23-pk/workforce-mlops'"
  exit 1
fi

ACCOUNT_ID=""
if command -v aws >/dev/null 2>&1; then
  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION" 2>/dev/null || true)"
fi

if [[ -z "$DVC_S3_BUCKET" ]]; then
  if [[ -n "$ACCOUNT_ID" && "$ACCOUNT_ID" != "None" ]]; then
    DVC_S3_BUCKET="${PROJECT_NAME}-dvc-${ACCOUNT_ID}"
  else
    DVC_S3_BUCKET="${PROJECT_NAME}-dvc-<aws-account-id>"
  fi
fi
if [[ -z "$MLFLOW_S3_BUCKET" ]]; then
  if [[ -n "$ACCOUNT_ID" && "$ACCOUNT_ID" != "None" ]]; then
    MLFLOW_S3_BUCKET="${PROJECT_NAME}-mlflow-${ACCOUNT_ID}"
  else
    MLFLOW_S3_BUCKET="${PROJECT_NAME}-mlflow-<aws-account-id>"
  fi
fi

if [[ "$MODE" == "console" ]]; then
  mkdir -p "$(dirname "$OUTPUT_FILE")"
  cat > "$OUTPUT_FILE" <<EOF
export AWS_REGION='${AWS_REGION}'
export AWS_ROLE_TO_ASSUME='arn:aws:iam::<aws-account-id>:role/${GITHUB_ROLE_NAME}'
export ECR_REPOSITORY='${ECR_REPOSITORY}'
export DVC_S3_BUCKET='${DVC_S3_BUCKET}'
export MLFLOW_S3_BUCKET='${MLFLOW_S3_BUCKET}'
export ECR_REGISTRY='<aws-account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com'
export GITHUB_REPO='${GITHUB_REPO}'
EOF

  echo "MODE=console selected."
  echo
  echo "Manual AWS Console Playbook"
  echo "1) S3 -> Create bucket -> '${DVC_S3_BUCKET}' (Region: ${AWS_REGION})"
  echo "2) S3 -> Create bucket -> '${MLFLOW_S3_BUCKET}' (Region: ${AWS_REGION})"
  echo "3) ECR -> Create repository -> '${ECR_REPOSITORY}' (scan on push: enabled)"
  echo "4) IAM -> Identity providers -> Add provider:"
  echo "   URL: https://token.actions.githubusercontent.com"
  echo "   Audience: sts.amazonaws.com"
  echo "5) IAM -> Roles -> Create role (Web identity) for GitHub Actions with trust:"
  echo "   repo:${GITHUB_REPO}:*"
  echo "6) Attach inline policy granting:"
  echo "   - ECR push/pull permissions"
  echo "   - s3:ListBucket on ${DVC_S3_BUCKET} and ${MLFLOW_S3_BUCKET}"
  echo "   - s3:GetObject/PutObject/DeleteObject on both bucket object ARNs"
  echo "7) Update ${OUTPUT_FILE} placeholders (<aws-account-id>) with real values."
  echo
  echo "Next:"
  echo "  source ${OUTPUT_FILE}"
  echo "  MODE=console bash scripts/set_github_secrets.sh"
  echo
  echo "Tip: For command-based provisioning later, rerun with MODE=cli."
  exit 0
fi

require_cmd aws

if [[ -z "$ACCOUNT_ID" || "$ACCOUNT_ID" == "None" ]]; then
  echo "Unable to resolve AWS account. Run aws configure first."
  exit 1
fi

if [[ -z "$DVC_S3_BUCKET" ]]; then
  DVC_S3_BUCKET="${PROJECT_NAME}-dvc-${ACCOUNT_ID}"
fi
if [[ -z "$MLFLOW_S3_BUCKET" ]]; then
  MLFLOW_S3_BUCKET="${PROJECT_NAME}-mlflow-${ACCOUNT_ID}"
fi

if bucket_is_placeholder "$DVC_S3_BUCKET" || bucket_is_placeholder "$MLFLOW_S3_BUCKET"; then
  echo "Bucket name contains placeholder text. Set real values for DVC_S3_BUCKET/MLFLOW_S3_BUCKET."
  exit 1
fi

if ! bucket_name_valid "$DVC_S3_BUCKET"; then
  echo "Invalid DVC_S3_BUCKET: ${DVC_S3_BUCKET}"
  exit 1
fi

if ! bucket_name_valid "$MLFLOW_S3_BUCKET"; then
  echo "Invalid MLFLOW_S3_BUCKET: ${MLFLOW_S3_BUCKET}"
  exit 1
fi

ensure_bucket() {
  local bucket="$1"
  if aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
    echo "S3 bucket exists: $bucket"
    return
  fi

  echo "Creating S3 bucket: $bucket"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$bucket" --region "$AWS_REGION" >/dev/null
  else
    aws s3api create-bucket \
      --bucket "$bucket" \
      --region "$AWS_REGION" \
      --create-bucket-configuration "LocationConstraint=${AWS_REGION}" >/dev/null
  fi
}

ensure_bucket "$DVC_S3_BUCKET"
ensure_bucket "$MLFLOW_S3_BUCKET"

if aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ECR repository exists: $ECR_REPOSITORY"
else
  echo "Creating ECR repository: $ECR_REPOSITORY"
  aws ecr create-repository \
    --repository-name "$ECR_REPOSITORY" \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true >/dev/null
fi

OIDC_URL="https://token.actions.githubusercontent.com"
if aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text | grep -q "token.actions.githubusercontent.com"; then
  echo "OIDC provider exists for GitHub Actions"
else
  echo "Creating IAM OIDC provider for GitHub Actions"
  aws iam create-open-id-connect-provider \
    --url "$OIDC_URL" \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
fi

TRUST_DOC="$(mktemp)"
cat > "$TRUST_DOC" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:*"
        }
      }
    }
  ]
}
JSON

if aws iam get-role --role-name "$GITHUB_ROLE_NAME" >/dev/null 2>&1; then
  echo "IAM role exists: $GITHUB_ROLE_NAME"
  aws iam update-assume-role-policy --role-name "$GITHUB_ROLE_NAME" --policy-document "file://${TRUST_DOC}" >/dev/null
else
  echo "Creating IAM role: $GITHUB_ROLE_NAME"
  aws iam create-role --role-name "$GITHUB_ROLE_NAME" --assume-role-policy-document "file://${TRUST_DOC}" >/dev/null
fi

PERM_DOC="$(mktemp)"
cat > "$PERM_DOC" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:DescribeRepositories"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::${DVC_S3_BUCKET}",
        "arn:aws:s3:::${MLFLOW_S3_BUCKET}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": [
        "arn:aws:s3:::${DVC_S3_BUCKET}/*",
        "arn:aws:s3:::${MLFLOW_S3_BUCKET}/*"
      ]
    }
  ]
}
JSON

aws iam put-role-policy \
  --role-name "$GITHUB_ROLE_NAME" \
  --policy-name "${PROJECT_NAME}-github-actions-gitops" \
  --policy-document "file://${PERM_DOC}" >/dev/null

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${GITHUB_ROLE_NAME}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

mkdir -p "$(dirname "$OUTPUT_FILE")"
cat > "$OUTPUT_FILE" <<EOF
export AWS_REGION='${AWS_REGION}'
export AWS_ROLE_TO_ASSUME='${ROLE_ARN}'
export ECR_REPOSITORY='${ECR_REPOSITORY}'
export DVC_S3_BUCKET='${DVC_S3_BUCKET}'
export MLFLOW_S3_BUCKET='${MLFLOW_S3_BUCKET}'
export ECR_REGISTRY='${ECR_REGISTRY}'
export GITHUB_REPO='${GITHUB_REPO}'
EOF

echo "Provisioning complete."
echo "Outputs written to ${OUTPUT_FILE}"
echo "Next steps:"
echo "  source ${OUTPUT_FILE}"
echo "  bash scripts/set_github_secrets.sh"
echo "  kubectl apply -f deploy/argocd/application.yaml"
