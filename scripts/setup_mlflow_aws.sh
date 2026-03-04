#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${MLFLOW_TRACKING_URI:-}" ]]; then
  echo "Set MLFLOW_TRACKING_URI first."
  echo "Example (self-hosted): export MLFLOW_TRACKING_URI=http://<mlflow-host>:5000"
  echo "Example (managed): export MLFLOW_TRACKING_URI=<your-managed-mlflow-tracking-uri>"
  exit 1
fi

export MLFLOW_TRACKING_URI

if [[ -n "${MLFLOW_EXPERIMENT_NAME:-}" ]]; then
  export MLFLOW_EXPERIMENT_NAME
fi

echo "MLflow configured"
echo "  MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI}"
if [[ -n "${MLFLOW_EXPERIMENT_NAME:-}" ]]; then
  echo "  MLFLOW_EXPERIMENT_NAME=${MLFLOW_EXPERIMENT_NAME}"
fi
