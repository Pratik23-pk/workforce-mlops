# Cloud Auto Connect (Identity-First)

This project supports automatic cloud connection at container startup without embedding static credentials.

## What it does

At startup, `/app/docker/entrypoint.sh` calls:

- `/app/scripts/auto_cloud_connect.sh`

The script:

1. Detects provider (`aws`, `gcp`, `azure`) from metadata service and runtime hints.
2. Supports AWS IMDSv2 detection and region auto-discovery.
3. Configures DVC remote for that provider.
4. Optionally runs `dvc pull` if enabled.
5. Configures `MLFLOW_TRACKING_URI` from provider-specific env var if not already set.

## Required runtime env vars

### Common

- `AUTO_CLOUD_CONNECT=1` (default in deployment manifest)
- `DVC_AUTO_PULL=0|1` (default `0`)
- `DVC_REMOTE_NAME=origin` (optional)
- `DVC_REMOTE_SUBPATH=dvc` (optional)
- `METADATA_RETRIES=3` (optional)
- `METADATA_RETRY_DELAY_SEC=1` (optional)
- `METADATA_TIMEOUT_SEC=1` (optional)

### AWS

- `DVC_S3_BUCKET=<bucket-name>` or `DVC_BUCKET=<bucket-name>`
- `AWS_REGION=<region>` (optional; auto-detected from IMDS when available)
- Workload identity: IAM role attached to runtime (EKS IRSA / EC2 role / ECS task role)

Optional:

- `MLFLOW_TRACKING_URI_AWS=<tracking-uri>`

### GCP

- `DVC_GS_BUCKET=<gcs-bucket>` or `DVC_BUCKET=<gcs-bucket>`
- Workload identity: GKE Workload Identity / Compute Service Account

Optional:

- `MLFLOW_TRACKING_URI_GCP=<tracking-uri>`

### Azure

- `DVC_AZURE_CONTAINER=<blob-container>` or `DVC_BUCKET=<blob-container>`
- Optional `AZURE_STORAGE_ACCOUNT=<account-name>`
- Workload identity: Azure Managed Identity

Optional:

- `MLFLOW_TRACKING_URI_AZURE=<tracking-uri>`

### MLflow fallback

- `MLFLOW_TRACKING_URI_DEFAULT=<tracking-uri>` can be set as a provider-agnostic fallback.

## Security model

- Static credentials are intentionally not hardcoded.
- Authentication must come from runtime identity (role/service account/managed identity).
- New containers auto-connect only when identity and role bindings are correct.

## Notes

- If provider cannot be detected, the script logs and continues.
- If required DVC env vars are missing, DVC setup is skipped.
- App startup is not blocked by auto-connect failures; errors are logged and app still starts.
