#!/usr/bin/env bash
set -euo pipefail

if [[ -f infra/aws_outputs.env ]]; then
  # shellcheck disable=SC1091
  source infra/aws_outputs.env
fi

AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPOSITORY="${ECR_REPOSITORY:-workforce-mlops-app}"
EC2_HOST="${EC2_HOST:-${EC2_PUBLIC_IP:-}}"
EC2_USER="${EC2_USER:-ubuntu}"
EC2_KEY_PATH="${EC2_KEY_PATH:-}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%s)}"
CONTAINER_NAME="${CONTAINER_NAME:-workforce-mlops-app}"

if [[ -z "$EC2_HOST" || -z "$EC2_KEY_PATH" ]]; then
  echo "Required: EC2_HOST/EC2_PUBLIC_IP and EC2_KEY_PATH"
  echo "Tip: source infra/aws_outputs.env first"
  exit 1
fi

if [[ ! -f "$EC2_KEY_PATH" ]]; then
  echo "EC2 key not found: $EC2_KEY_PATH"
  exit 1
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1"
    exit 1
  fi
}

require_cmd aws
require_cmd docker
require_cmd ssh

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "Building Docker image: $IMAGE_URI"
docker build -f docker/Dockerfile -t "$IMAGE_URI" .

echo "Pushing Docker image"
docker push "$IMAGE_URI"

SSH_OPTS=(
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30
  -i "$EC2_KEY_PATH"
)

echo "Deploying container on EC2"
ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" <<EOF_REMOTE
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y docker.io
  sudo systemctl enable docker
  sudo systemctl start docker
fi

aws ecr get-login-password --region "$AWS_REGION" | sudo docker login --username AWS --password-stdin "$ECR_REGISTRY"
sudo docker pull "$IMAGE_URI"
sudo docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
sudo docker run -d --name "$CONTAINER_NAME" -p 80:8501 "$IMAGE_URI"
EOF_REMOTE

echo "Deployment complete"
echo "App URL: http://${EC2_HOST}/"
