#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${MLFLOW_ARTIFACT_ROOT:-}" ]]; then
  echo "Set MLFLOW_ARTIFACT_ROOT first."
  echo "Example: export MLFLOW_ARTIFACT_ROOT=s3://<bucket>/mlflow-artifacts"
  exit 1
fi

BACKEND_STORE_URI="${MLFLOW_BACKEND_STORE_URI:-sqlite:///mlflow.db}"
HOST="${MLFLOW_HOST:-0.0.0.0}"
PORT="${MLFLOW_PORT:-5000}"

exec mlflow server \
  --host "${HOST}" \
  --port "${PORT}" \
  --backend-store-uri "${BACKEND_STORE_URI}" \
  --default-artifact-root "${MLFLOW_ARTIFACT_ROOT}" \
  --serve-artifacts
