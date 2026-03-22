# AWS Deployment Playbook (CLI + Console)

Use this as a dual-path guide.  
`CLI` path runs scripts. `Console` path gives equivalent click-ops.

## 0) Prerequisites

| CLI path | Console path |
|---|---|
| Install and configure AWS CLI (`aws configure`) | Sign in to AWS Console with IAM user that has S3/ECR/IAM/EKS permissions |
| Authenticate GitHub CLI (`gh auth login`) | Open GitHub repo with admin access (`Settings -> Secrets and variables -> Actions`) |
| Set repo env vars (`AWS_REGION`, `GITHUB_REPO`) | Keep same values ready to fill in forms |

## 1) Provision core AWS resources

| CLI path | Console path |
|---|---|
| `MODE=cli bash scripts/provision_aws_gitops.sh` | `MODE=console bash scripts/provision_aws_gitops.sh` to print checklist, then create in AWS Console: |
| Script creates S3 buckets (DVC + MLflow), ECR repo, IAM OIDC provider, IAM role for GitHub Actions | 1) S3 buckets: `workforce-mlops-dvc-<account-id>` and `workforce-mlops-mlflow-<account-id>` |
| Writes output env file: `infra/aws_gitops_outputs.env` | 2) ECR repo: `workforce-mlops-app` |
| | 3) IAM OIDC provider: `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com` |
| | 4) IAM role (web identity) trusted for `repo:<owner>/<repo>:*` with ECR + S3 policy |

After either path:

```bash
source infra/aws_gitops_outputs.env
```

If you used console path, replace `<aws-account-id>` placeholders before sourcing.

## 1b) Start MLflow Tracking Server (self-hosted)

If you want MLflow logs visible across EC2 + GitHub Actions, run a tracking
server and point `MLFLOW_TRACKING_URI` to it (use a public IP/DNS, not `0.0.0.0`).

Example on an EC2 instance:

```bash
export MLFLOW_S3_BUCKET=<your-mlflow-bucket>
export MLFLOW_PUBLIC_HOST=<public-ip-or-dns>
export MLFLOW_ALLOWED_HOSTS="<public-ip-or-dns>,localhost,127.0.0.1"
bash scripts/run_mlflow_server.sh
```

Security group inbound must allow TCP `5000` from your public IP.

## 2) Configure DVC remote to S3

| CLI path | Console path |
|---|---|
| `MODE=cli bash scripts/setup_dvc_s3.sh` | `MODE=console bash scripts/setup_dvc_s3.sh` (prints exact local DVC commands) |
| `dvc push -v -j 1` | Run same `dvc push -v -j 1` after local config |

## 3) Configure GitHub Actions secrets

| CLI path | Console path |
|---|---|
| `MODE=cli bash scripts/set_github_secrets.sh` | `MODE=console bash scripts/set_github_secrets.sh` |
| Uses `gh secret set` automatically | Add each secret manually in GitHub UI |

Required secrets:

- `AWS_ROLE_TO_ASSUME`
- `AWS_REGION`
- `ECR_REPOSITORY`
- `DVC_S3_BUCKET`
- `MLFLOW_TRACKING_URI`
- `MLFLOW_EXPERIMENT_NAME` (optional override)

## 4) GitOps deploy (EKS + Argo CD)

| CLI path | Console path |
|---|---|
| Install/verify Argo CD with `kubectl` and apply `deploy/argocd/application.yaml` | Create EKS cluster and node group in Console, then connect via `kubectl`; Argo CD install/apply still uses kubectl |
| GitHub CD workflow runs CT (`dvc repro compare_models promote_model evaluate`), pushes refreshed DVC artifacts, then updates `deploy/k8s/overlays/prod/kustomization.yaml` image tag | Same behavior once secrets and role are configured |
| Argo CD syncs manifests to cluster | Same behavior |

Reference: `docs/ARGOCD_GITOPS_SETUP.md`

## 5) Verify

```bash
kubectl -n workforce-mlops get deploy,svc,pods
kubectl -n argocd get applications
```

App URL comes from the `workforce-mlops-api` service external endpoint.

## Common failure patterns

- `Invalid bucket name "<...>"`: you still have placeholder text in env vars.
- `Unable to locate credentials`: `aws sts get-caller-identity` must succeed first.
- GitHub CD fails at DVC pull: missing `DVC_S3_BUCKET` secret or IAM role lacks S3 permission.
- GitHub CD fails before CT: missing `MLFLOW_TRACKING_URI` secret.
- CD fails at ECR push: IAM role missing ECR permissions.
