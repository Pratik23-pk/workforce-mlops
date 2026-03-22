#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/prompt_utils.sh" ]]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/prompt_utils.sh"
fi

if [[ -z "${MLFLOW_TRACKING_URI:-}" ]]; then
  if command -v prompt_value >/dev/null 2>&1; then
    prompt_value MLFLOW_TRACKING_URI "Enter MLflow Tracking URI"
  fi
fi

if [[ -z "${MLFLOW_TRACKING_URI:-}" ]]; then
  echo "Set MLFLOW_TRACKING_URI first."
  echo "Example (self-hosted): export MLFLOW_TRACKING_URI=http://<mlflow-host>:5000"
  echo "Example (managed): export MLFLOW_TRACKING_URI=<your-managed-mlflow-tracking-uri>"
  exit 1
fi

export MLFLOW_TRACKING_URI

if [[ "${MLFLOW_TRACKING_URI}" == *"0.0.0.0"* ]]; then
  echo "Warning: MLFLOW_TRACKING_URI uses 0.0.0.0, which is not reachable by clients."
  echo "Use a public IP or DNS name instead (e.g., http://<public-ip>:5000)."
fi

if [[ "${MLFLOW_TRACKING_URI}" == *"localhost"* || "${MLFLOW_TRACKING_URI}" == *"127.0.0.1"* ]]; then
  echo "Note: localhost/127.0.0.1 is only reachable from the same machine."
  echo "For GitHub Actions or remote clients, use the EC2 public IP or DNS."
fi

if [[ -z "${MLFLOW_EXPERIMENT_NAME:-}" ]] && command -v prompt_yes_no >/dev/null 2>&1; then
  if prompt_yes_no "Set a custom MLflow experiment name?" "n"; then
    prompt_value MLFLOW_EXPERIMENT_NAME "Enter experiment name" "workforce-multitask"
  fi
fi

if [[ -n "${MLFLOW_EXPERIMENT_NAME:-}" ]]; then
  export MLFLOW_EXPERIMENT_NAME
fi

echo "MLflow configured"
echo "  MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI}"
if [[ -n "${MLFLOW_EXPERIMENT_NAME:-}" ]]; then
  echo "  MLFLOW_EXPERIMENT_NAME=${MLFLOW_EXPERIMENT_NAME}"
fi
