#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/prompt_utils.sh" ]]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/prompt_utils.sh"
fi

MODE="${MODE:-cli}" # cli|console
GITHUB_REPO="${GITHUB_REPO:-}"

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

required_vars=(
  AWS_ROLE_TO_ASSUME
  AWS_REGION
  ECR_REPOSITORY
  DVC_S3_BUCKET
  MLFLOW_TRACKING_URI
)

for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    if command -v prompt_value >/dev/null 2>&1; then
      prompt_value "${name}" "Enter value for ${name}"
    fi
  fi
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: ${name}"
    exit 1
  fi
done

if [[ -z "${MLFLOW_EXPERIMENT_NAME:-}" ]] && command -v prompt_yes_no >/dev/null 2>&1; then
  if prompt_yes_no "Set optional MLflow experiment name secret?" "n"; then
    prompt_value MLFLOW_EXPERIMENT_NAME "Enter MLflow experiment name" "workforce-multitask"
  fi
fi

if [[ -z "${MLFLOW_TRACKING_USERNAME:-}" ]] && command -v prompt_yes_no >/dev/null 2>&1; then
  if prompt_yes_no "Set optional MLflow tracking username/password secrets?" "n"; then
    prompt_value MLFLOW_TRACKING_USERNAME "Enter MLflow tracking username"
    prompt_value MLFLOW_TRACKING_PASSWORD "Enter MLflow tracking password" "" "1"
  fi
fi

if [[ -z "${MLFLOW_REGISTER_MODEL:-}" ]] && command -v prompt_yes_no >/dev/null 2>&1; then
  if prompt_yes_no "Enable optional MLflow model registry in CD?" "n"; then
    export MLFLOW_REGISTER_MODEL="1"
    prompt_value MLFLOW_REGISTERED_MODEL_NAME "Enter registered model name" "workforce-model"
  fi
fi

if [[ "$MODE" == "console" ]]; then
  echo "MODE=console selected."
  echo "Open GitHub repo -> Settings -> Secrets and variables -> Actions -> New repository secret"
  echo
  echo "Required secrets:"
  echo "  AWS_ROLE_TO_ASSUME=${AWS_ROLE_TO_ASSUME}"
  echo "  AWS_REGION=${AWS_REGION}"
  echo "  ECR_REPOSITORY=${ECR_REPOSITORY}"
  echo "  MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI}"
  if [[ -n "${MLFLOW_EXPERIMENT_NAME:-}" ]]; then
    echo "  MLFLOW_EXPERIMENT_NAME=${MLFLOW_EXPERIMENT_NAME}"
  else
    echo "  MLFLOW_EXPERIMENT_NAME=<optional, defaults from code>"
  fi
  if [[ -n "${MLFLOW_TRACKING_USERNAME:-}" ]]; then
    echo "  MLFLOW_TRACKING_USERNAME=${MLFLOW_TRACKING_USERNAME}"
  fi
  if [[ -n "${MLFLOW_TRACKING_PASSWORD:-}" ]]; then
    echo "  MLFLOW_TRACKING_PASSWORD=<set>"
  fi
  if [[ -n "${MLFLOW_REGISTER_MODEL:-}" ]]; then
    echo "  MLFLOW_REGISTER_MODEL=${MLFLOW_REGISTER_MODEL}"
  fi
  if [[ -n "${MLFLOW_REGISTERED_MODEL_NAME:-}" ]]; then
    echo "  MLFLOW_REGISTERED_MODEL_NAME=${MLFLOW_REGISTERED_MODEL_NAME}"
  fi
  echo "  DVC_S3_BUCKET=${DVC_S3_BUCKET}"
  echo
  if [[ -n "$GITHUB_REPO" ]]; then
    echo "Target repo: ${GITHUB_REPO}"
  else
    echo "Target repo: current repository"
  fi
  exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI not found. Install gh and run gh auth login"
  echo "Or use manual mode: MODE=console bash scripts/set_github_secrets.sh"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login"
  exit 1
fi

repo_args=()
if [[ -n "$GITHUB_REPO" ]]; then
  repo_args=(-R "$GITHUB_REPO")
fi

gh secret set AWS_ROLE_TO_ASSUME "${repo_args[@]}" --body "${AWS_ROLE_TO_ASSUME}"
gh secret set AWS_REGION "${repo_args[@]}" --body "${AWS_REGION}"
gh secret set ECR_REPOSITORY "${repo_args[@]}" --body "${ECR_REPOSITORY}"
gh secret set MLFLOW_TRACKING_URI "${repo_args[@]}" --body "${MLFLOW_TRACKING_URI}"

gh secret set DVC_S3_BUCKET "${repo_args[@]}" --body "${DVC_S3_BUCKET}"
if [[ -n "${MLFLOW_EXPERIMENT_NAME:-}" ]]; then
  gh secret set MLFLOW_EXPERIMENT_NAME "${repo_args[@]}" --body "${MLFLOW_EXPERIMENT_NAME}"
fi
if [[ -n "${MLFLOW_TRACKING_USERNAME:-}" ]]; then
  gh secret set MLFLOW_TRACKING_USERNAME "${repo_args[@]}" --body "${MLFLOW_TRACKING_USERNAME}"
fi
if [[ -n "${MLFLOW_TRACKING_PASSWORD:-}" ]]; then
  gh secret set MLFLOW_TRACKING_PASSWORD "${repo_args[@]}" --body "${MLFLOW_TRACKING_PASSWORD}"
fi
if [[ -n "${MLFLOW_REGISTER_MODEL:-}" ]]; then
  gh secret set MLFLOW_REGISTER_MODEL "${repo_args[@]}" --body "${MLFLOW_REGISTER_MODEL}"
fi
if [[ -n "${MLFLOW_REGISTERED_MODEL_NAME:-}" ]]; then
  gh secret set MLFLOW_REGISTERED_MODEL_NAME "${repo_args[@]}" --body "${MLFLOW_REGISTERED_MODEL_NAME}"
fi

echo "GitHub Actions secrets configured for CI/CD (GitOps + Argo CD)."
if [[ -n "$GITHUB_REPO" ]]; then
  echo "Repo: ${GITHUB_REPO}"
fi
