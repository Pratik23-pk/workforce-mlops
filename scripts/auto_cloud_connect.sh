#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[auto-cloud-connect] $*"
}

normalize_provider() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

probe_gcp_metadata() {
  curl -fsS --max-time "${METADATA_TIMEOUT_SEC:-1}" \
    -H "Metadata-Flavor: Google" \
    "http://169.254.169.254/computeMetadata/v1/project/project-id" >/dev/null 2>&1
}

probe_azure_metadata() {
  curl -fsS --max-time "${METADATA_TIMEOUT_SEC:-1}" \
    -H "Metadata: true" \
    "http://169.254.169.254/metadata/instance?api-version=2021-02-01" >/dev/null 2>&1
}

aws_imds_token() {
  curl -fsS --max-time "${METADATA_TIMEOUT_SEC:-1}" \
    -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true
}

probe_aws_metadata() {
  local token
  token="$(aws_imds_token)"
  if [[ -n "${token}" ]]; then
    curl -fsS --max-time "${METADATA_TIMEOUT_SEC:-1}" \
      -H "X-aws-ec2-metadata-token: ${token}" \
      "http://169.254.169.254/latest/meta-data/" >/dev/null 2>&1 && return 0
  fi

  # Fallback for environments that still allow IMDSv1.
  curl -fsS --max-time "${METADATA_TIMEOUT_SEC:-1}" \
    "http://169.254.169.254/latest/meta-data/" >/dev/null 2>&1
}

aws_region_from_imds() {
  local token
  local doc

  token="$(aws_imds_token)"
  if [[ -n "${token}" ]]; then
    doc="$(curl -fsS --max-time "${METADATA_TIMEOUT_SEC:-1}" \
      -H "X-aws-ec2-metadata-token: ${token}" \
      "http://169.254.169.254/latest/dynamic/instance-identity/document" 2>/dev/null || true)"
  else
    doc="$(curl -fsS --max-time "${METADATA_TIMEOUT_SEC:-1}" \
      "http://169.254.169.254/latest/dynamic/instance-identity/document" 2>/dev/null || true)"
  fi

  if [[ -n "${doc}" ]]; then
    echo "${doc}" | sed -n 's/.*"region"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1
  fi
}

detect_cloud_provider() {
  local provider_hint="${CLOUD_PROVIDER:-}"
  local retries="${METADATA_RETRIES:-3}"
  local attempt=1

  if [[ -n "${provider_hint}" ]]; then
    normalize_provider "${provider_hint}"
    return
  fi

  # Fast env-hint detection for managed runtimes.
  if [[ -n "${GOOGLE_CLOUD_PROJECT:-}" || -n "${GKE_CLUSTER_NAME:-}" || -n "${K_SERVICE:-}" ]]; then
    echo "gcp"
    return
  fi

  if [[ -n "${IDENTITY_ENDPOINT:-}" || -n "${MSI_ENDPOINT:-}" || -n "${AZURE_HTTP_USER_AGENT:-}" ]]; then
    echo "azure"
    return
  fi

  if [[ -n "${AWS_EXECUTION_ENV:-}" || -n "${ECS_CONTAINER_METADATA_URI:-}" || -n "${ECS_CONTAINER_METADATA_URI_V4:-}" ]]; then
    echo "aws"
    return
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "unknown"
    return
  fi

  while [[ "${attempt}" -le "${retries}" ]]; do
    if probe_gcp_metadata; then
      echo "gcp"
      return
    fi

    if probe_azure_metadata; then
      echo "azure"
      return
    fi

    if probe_aws_metadata; then
      echo "aws"
      return
    fi

    attempt=$((attempt + 1))
    sleep "${METADATA_RETRY_DELAY_SEC:-1}"
  done

  echo "unknown"
}

dvc_remote_url() {
  local provider="$1"
  local subpath="${DVC_REMOTE_SUBPATH:-dvc}"

  case "${provider}" in
    aws)
      local s3_bucket="${DVC_S3_BUCKET:-${DVC_BUCKET:-}}"
      if [[ -z "${s3_bucket}" ]]; then
        log "AWS detected but DVC_S3_BUCKET (or DVC_BUCKET) is missing"
        return 1
      fi
      echo "s3://${s3_bucket}/${subpath}"
      ;;
    gcp)
      local gs_bucket="${DVC_GS_BUCKET:-${DVC_BUCKET:-}}"
      if [[ -z "${gs_bucket}" ]]; then
        log "GCP detected but DVC_GS_BUCKET (or DVC_BUCKET) is missing"
        return 1
      fi
      echo "gs://${gs_bucket}/${subpath}"
      ;;
    azure)
      local az_container="${DVC_AZURE_CONTAINER:-${DVC_BUCKET:-}}"
      if [[ -z "${az_container}" ]]; then
        log "Azure detected but DVC_AZURE_CONTAINER (or DVC_BUCKET) is missing"
        return 1
      fi
      echo "azure://${az_container}/${subpath}"
      ;;
    *)
      log "Cloud provider not detected; skipping DVC remote setup"
      return 1
      ;;
  esac
}

configure_dvc_remote() {
  local provider="$1"
  local remote_name="${DVC_REMOTE_NAME:-origin}"
  local remote_url

  if ! command -v dvc >/dev/null 2>&1; then
    log "dvc not installed; skipping remote configuration"
    return
  fi

  if ! remote_url="$(dvc_remote_url "${provider}")"; then
    return
  fi

  if ! dvc remote add -d "${remote_name}" "${remote_url}" --force; then
    log "Failed to configure DVC remote ${remote_name}=${remote_url}; continuing"
    return
  fi

  case "${provider}" in
    aws)
      if [[ -z "${AWS_REGION:-}" ]]; then
        local imds_region
        imds_region="$(aws_region_from_imds || true)"
        if [[ -n "${imds_region}" ]]; then
          export AWS_REGION="${imds_region}"
          export AWS_DEFAULT_REGION="${imds_region}"
        fi
      fi

      if [[ -n "${AWS_REGION:-}" ]]; then
        dvc remote modify "${remote_name}" region "${AWS_REGION}" || true
      fi

      if [[ -n "${AWS_PROFILE:-}" ]]; then
        dvc remote modify --local "${remote_name}" profile "${AWS_PROFILE}" || true
      fi
      ;;
    azure)
      if [[ -n "${AZURE_STORAGE_ACCOUNT:-}" ]]; then
        dvc remote modify "${remote_name}" account_name "${AZURE_STORAGE_ACCOUNT}" || true
      fi
      ;;
  esac

  log "DVC remote configured: ${remote_name} -> ${remote_url}"
}

configure_mlflow_uri() {
  local provider="$1"
  local selected_uri=""

  if [[ -n "${MLFLOW_TRACKING_URI:-}" ]]; then
    log "Using existing MLFLOW_TRACKING_URI"
    return
  fi

  case "${provider}" in
    aws)
      selected_uri="${MLFLOW_TRACKING_URI_AWS:-}"
      ;;
    gcp)
      selected_uri="${MLFLOW_TRACKING_URI_GCP:-}"
      ;;
    azure)
      selected_uri="${MLFLOW_TRACKING_URI_AZURE:-}"
      ;;
  esac

  if [[ -z "${selected_uri}" ]]; then
    selected_uri="${MLFLOW_TRACKING_URI_DEFAULT:-}"
  fi

  if [[ -n "${selected_uri}" ]]; then
    export MLFLOW_TRACKING_URI="${selected_uri}"
    log "MLflow tracking URI configured"
  else
    log "No MLflow URI configured; app will use local mlruns"
  fi
}

pull_dvc_artifacts_if_requested() {
  if [[ "${DVC_AUTO_PULL:-0}" != "1" ]]; then
    return
  fi

  if ! command -v dvc >/dev/null 2>&1; then
    log "DVC auto-pull requested, but dvc is not installed"
    return
  fi

  if [[ ! -f dvc.yaml && ! -f .dvc/config ]]; then
    log "No DVC project files found; skipping dvc pull"
    return
  fi

  log "DVC_AUTO_PULL=1 -> pulling artifacts"
  if ! dvc pull -j "${DVC_PULL_JOBS:-1}"; then
    log "dvc pull failed; continuing container startup"
  fi
}

main() {
  if [[ "${AUTO_CLOUD_CONNECT:-1}" != "1" ]]; then
    log "AUTO_CLOUD_CONNECT disabled"
    return
  fi

  local provider
  provider="$(detect_cloud_provider)"
  provider="$(normalize_provider "${provider}")"
  export CLOUD_PROVIDER="${provider}"
  log "Detected provider=${provider}"

  configure_dvc_remote "${provider}"
  configure_mlflow_uri "${provider}"
  pull_dvc_artifacts_if_requested
}

main "$@"
