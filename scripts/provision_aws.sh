#!/usr/bin/env bash
set -euo pipefail

# Configurable inputs
PROJECT_NAME="${PROJECT_NAME:-workforce-mlops}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.small}"
EC2_VOLUME_SIZE_GB="${EC2_VOLUME_SIZE_GB:-20}"
ECR_REPOSITORY="${ECR_REPOSITORY:-${PROJECT_NAME}-app}"
EC2_TAG_NAME="${EC2_TAG_NAME:-${PROJECT_NAME}-app}"
SECURITY_GROUP_NAME="${SECURITY_GROUP_NAME:-${PROJECT_NAME}-sg}"
KEY_NAME="${KEY_NAME:-${PROJECT_NAME}-key}"
KEY_DIR="${KEY_DIR:-infra/keys}"
EC2_ROLE_NAME="${EC2_ROLE_NAME:-${PROJECT_NAME}-ec2-role}"
EC2_INSTANCE_PROFILE_NAME="${EC2_INSTANCE_PROFILE_NAME:-${PROJECT_NAME}-ec2-profile}"
GITHUB_ROLE_NAME="${GITHUB_ROLE_NAME:-GitHubActionsWorkforceDeployRole}"
GITHUB_REPO="${GITHUB_REPO:-*/*}"
OUTPUT_FILE="${OUTPUT_FILE:-infra/aws_outputs.env}"

# Inbound CIDRs
ALLOW_SSH_CIDR="${ALLOW_SSH_CIDR:-0.0.0.0/0}"
ALLOW_HTTP_CIDR="${ALLOW_HTTP_CIDR:-0.0.0.0/0}"
ALLOW_MLFLOW_CIDR="${ALLOW_MLFLOW_CIDR:-0.0.0.0/0}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1"
    exit 1
  fi
}

validate_bucket_name() {
  local bucket="$1"
  if [[ "$bucket" == *"<"* || "$bucket" == *">"* ]]; then
    echo "Invalid S3 bucket name '$bucket' (looks like placeholder text)."
    echo "Use a real lowercase name, e.g. workforce-mlops-dvc-123456789012"
    exit 1
  fi

  if [[ ! "$bucket" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]]; then
    echo "Invalid S3 bucket name '$bucket'."
    echo "Allowed pattern: lowercase letters/numbers/dots/hyphens, length 3-63."
    exit 1
  fi

  if [[ "$bucket" == *".."* || "$bucket" == *".-"* || "$bucket" == *"-."* ]]; then
    echo "Invalid S3 bucket name '$bucket' (contains invalid dot/hyphen sequence)."
    exit 1
  fi
}

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

authorize_ingress_if_needed() {
  local sg_id="$1"
  local port="$2"
  local cidr="$3"

  aws ec2 authorize-security-group-ingress \
    --group-id "$sg_id" \
    --protocol tcp \
    --port "$port" \
    --cidr "$cidr" \
    --region "$AWS_REGION" >/dev/null 2>&1 || true
}

require_cmd aws
require_cmd ssh

if ! aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "AWS credentials are missing/invalid or AWS endpoint is unreachable."
  echo "Run: aws configure"
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query 'Account' --output text --region "$AWS_REGION")"
DVC_S3_BUCKET="${DVC_S3_BUCKET:-${PROJECT_NAME}-dvc-${ACCOUNT_ID}}"
MLFLOW_S3_BUCKET="${MLFLOW_S3_BUCKET:-${PROJECT_NAME}-mlflow-${ACCOUNT_ID}}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
KEY_PATH="${KEY_DIR}/${KEY_NAME}.pem"

if [[ "$GITHUB_REPO" == "*/*" || "$GITHUB_REPO" == *"<"* || "$GITHUB_REPO" == *">"* ]]; then
  echo "Set GITHUB_REPO to your real repo slug, e.g. Pratik23-pk/workforce-mlops"
  exit 1
fi

validate_bucket_name "$DVC_S3_BUCKET"
validate_bucket_name "$MLFLOW_S3_BUCKET"

mkdir -p "$KEY_DIR" infra

# 1) S3 buckets
ensure_bucket "$DVC_S3_BUCKET"
ensure_bucket "$MLFLOW_S3_BUCKET"

# 2) ECR repository
if aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ECR repo exists: $ECR_REPOSITORY"
else
  echo "Creating ECR repo: $ECR_REPOSITORY"
  aws ecr create-repository \
    --repository-name "$ECR_REPOSITORY" \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true >/dev/null
fi

# 3) Key pair
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  if [[ -f "$KEY_PATH" ]]; then
    echo "EC2 key pair exists and local key file found: $KEY_NAME"
  else
    KEY_NAME="${KEY_NAME}-$(date +%s)"
    KEY_PATH="${KEY_DIR}/${KEY_NAME}.pem"
    echo "Existing key pair has no local PEM file; creating new key pair: $KEY_NAME"
    aws ec2 create-key-pair --key-name "$KEY_NAME" --query 'KeyMaterial' --output text --region "$AWS_REGION" > "$KEY_PATH"
    chmod 400 "$KEY_PATH"
  fi
else
  echo "Creating EC2 key pair: $KEY_NAME"
  aws ec2 create-key-pair --key-name "$KEY_NAME" --query 'KeyMaterial' --output text --region "$AWS_REGION" > "$KEY_PATH"
  chmod 400 "$KEY_PATH"
fi

# 4) Security group
VPC_ID="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")"
if [[ -z "$VPC_ID" || "$VPC_ID" == "None" ]]; then
  echo "Could not find default VPC in region $AWS_REGION"
  exit 1
fi

SECURITY_GROUP_ID="$(aws ec2 describe-security-groups \
  --filters Name=group-name,Values="$SECURITY_GROUP_NAME" Name=vpc-id,Values="$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")"

if [[ -z "$SECURITY_GROUP_ID" || "$SECURITY_GROUP_ID" == "None" ]]; then
  echo "Creating security group: $SECURITY_GROUP_NAME"
  SECURITY_GROUP_ID="$(aws ec2 create-security-group \
    --group-name "$SECURITY_GROUP_NAME" \
    --description "Security group for ${PROJECT_NAME}" \
    --vpc-id "$VPC_ID" \
    --query 'GroupId' \
    --output text \
    --region "$AWS_REGION")"
fi

authorize_ingress_if_needed "$SECURITY_GROUP_ID" 22 "$ALLOW_SSH_CIDR"
authorize_ingress_if_needed "$SECURITY_GROUP_ID" 80 "$ALLOW_HTTP_CIDR"
authorize_ingress_if_needed "$SECURITY_GROUP_ID" 5000 "$ALLOW_MLFLOW_CIDR"

# 5) IAM role + instance profile for EC2
EC2_TRUST_DOC="$(mktemp)"
cat > "$EC2_TRUST_DOC" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

if aws iam get-role --role-name "$EC2_ROLE_NAME" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$EC2_ROLE_NAME" --policy-document "file://${EC2_TRUST_DOC}" >/dev/null
else
  echo "Creating IAM role: $EC2_ROLE_NAME"
  aws iam create-role --role-name "$EC2_ROLE_NAME" --assume-role-policy-document "file://${EC2_TRUST_DOC}" >/dev/null
fi

aws iam attach-role-policy --role-name "$EC2_ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly >/dev/null
aws iam attach-role-policy --role-name "$EC2_ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore >/dev/null

EC2_S3_POLICY_DOC="$(mktemp)"
cat > "$EC2_S3_POLICY_DOC" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
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
aws iam put-role-policy --role-name "$EC2_ROLE_NAME" --policy-name "${PROJECT_NAME}-s3-access" --policy-document "file://${EC2_S3_POLICY_DOC}" >/dev/null

if aws iam get-instance-profile --instance-profile-name "$EC2_INSTANCE_PROFILE_NAME" >/dev/null 2>&1; then
  :
else
  echo "Creating instance profile: $EC2_INSTANCE_PROFILE_NAME"
  aws iam create-instance-profile --instance-profile-name "$EC2_INSTANCE_PROFILE_NAME" >/dev/null
fi

if aws iam get-instance-profile --instance-profile-name "$EC2_INSTANCE_PROFILE_NAME" \
  --query "InstanceProfile.Roles[?RoleName=='${EC2_ROLE_NAME}'].RoleName" --output text | grep -q "$EC2_ROLE_NAME"; then
  :
else
  aws iam add-role-to-instance-profile --instance-profile-name "$EC2_INSTANCE_PROFILE_NAME" --role-name "$EC2_ROLE_NAME" >/dev/null 2>&1 || true
fi

# Instance profile propagation delay
sleep 10

# 6) Launch or reuse EC2 instance
INSTANCE_ID="$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values="$EC2_TAG_NAME" Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query 'Reservations[].Instances[].InstanceId | [0]' \
  --output text \
  --region "$AWS_REGION")"

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
  AMI_ID="$(aws ssm get-parameter \
    --name '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id' \
    --query 'Parameter.Value' \
    --output text \
    --region "$AWS_REGION")"

  echo "Launching EC2 instance (${INSTANCE_TYPE})"
  INSTANCE_ID="$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --count 1 \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SECURITY_GROUP_ID" \
    --iam-instance-profile Name="$EC2_INSTANCE_PROFILE_NAME" \
    --user-data "file://infra/user_data.sh" \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":${EC2_VOLUME_SIZE_GB},\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${EC2_TAG_NAME}},{Key=Project,Value=${PROJECT_NAME}}]" \
    --query 'Instances[0].InstanceId' \
    --output text \
    --region "$AWS_REGION")"
else
  INSTANCE_STATE="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text --region "$AWS_REGION")"
  if [[ "$INSTANCE_STATE" == "stopped" || "$INSTANCE_STATE" == "stopping" ]]; then
    aws ec2 start-instances --instance-ids "$INSTANCE_ID" --region "$AWS_REGION" >/dev/null
  fi
fi

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
EC2_PUBLIC_IP="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text --region "$AWS_REGION")"
EC2_PUBLIC_DNS="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicDnsName' --output text --region "$AWS_REGION")"

# 7) GitHub OIDC provider
OIDC_PROVIDER_ARN="$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn | [0]" --output text)"
if [[ -z "$OIDC_PROVIDER_ARN" || "$OIDC_PROVIDER_ARN" == "None" ]]; then
  OIDC_PROVIDER_ARN="$(aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
    --query 'OpenIDConnectProviderArn' \
    --output text)"
fi

# 8) GitHub Actions role for CD
GITHUB_TRUST_DOC="$(mktemp)"
cat > "$GITHUB_TRUST_DOC" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:ref:refs/heads/main"
        }
      }
    }
  ]
}
JSON

if aws iam get-role --role-name "$GITHUB_ROLE_NAME" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$GITHUB_ROLE_NAME" --policy-document "file://${GITHUB_TRUST_DOC}" >/dev/null
else
  echo "Creating GitHub OIDC role: $GITHUB_ROLE_NAME"
  aws iam create-role --role-name "$GITHUB_ROLE_NAME" --assume-role-policy-document "file://${GITHUB_TRUST_DOC}" >/dev/null
fi

aws iam attach-role-policy --role-name "$GITHUB_ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser >/dev/null

AWS_ROLE_TO_ASSUME="arn:aws:iam::${ACCOUNT_ID}:role/${GITHUB_ROLE_NAME}"

GITHUB_DVC_POLICY_DOC="$(mktemp)"
cat > "$GITHUB_DVC_POLICY_DOC" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::${DVC_S3_BUCKET}"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::${DVC_S3_BUCKET}/*"]
    }
  ]
}
JSON
aws iam put-role-policy \
  --role-name "$GITHUB_ROLE_NAME" \
  --policy-name "${PROJECT_NAME}-github-dvc-read" \
  --policy-document "file://${GITHUB_DVC_POLICY_DOC}" >/dev/null

# 9) Write outputs
cat > "$OUTPUT_FILE" <<ENV
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${ACCOUNT_ID}
DVC_S3_BUCKET=${DVC_S3_BUCKET}
MLFLOW_S3_BUCKET=${MLFLOW_S3_BUCKET}
ECR_REPOSITORY=${ECR_REPOSITORY}
ECR_REGISTRY=${ECR_REGISTRY}
EC2_INSTANCE_ID=${INSTANCE_ID}
EC2_PUBLIC_IP=${EC2_PUBLIC_IP}
EC2_PUBLIC_DNS=${EC2_PUBLIC_DNS}
EC2_KEY_NAME=${KEY_NAME}
EC2_KEY_PATH=${KEY_PATH}
EC2_SECURITY_GROUP_ID=${SECURITY_GROUP_ID}
EC2_ROLE_NAME=${EC2_ROLE_NAME}
EC2_INSTANCE_PROFILE_NAME=${EC2_INSTANCE_PROFILE_NAME}
GITHUB_OIDC_PROVIDER_ARN=${OIDC_PROVIDER_ARN}
GITHUB_ROLE_NAME=${GITHUB_ROLE_NAME}
AWS_ROLE_TO_ASSUME=${AWS_ROLE_TO_ASSUME}
MLFLOW_TRACKING_URI=http://${EC2_PUBLIC_IP}:5000
STREAMLIT_URL=http://${EC2_PUBLIC_IP}
ENV

echo "Provisioning complete."
echo "Outputs written to ${OUTPUT_FILE}"

echo "Next steps:"
echo "  1) source ${OUTPUT_FILE}"
echo "  2) bash scripts/setup_dvc_s3.sh"
echo "  3) bash scripts/setup_mlflow_ec2.sh"
echo "  4) bash scripts/build_push_and_deploy.sh"
