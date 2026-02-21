#!/usr/bin/env bash
set -euo pipefail

IMAGE_URI="$1"
CONTAINER_NAME="workforce-mlops-app"

aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "$(echo "${IMAGE_URI}" | cut -d'/' -f1)"

docker pull "${IMAGE_URI}"
docker rm -f "${CONTAINER_NAME}" || true
docker run -d --name "${CONTAINER_NAME}" -p 80:8501 "${IMAGE_URI}"
