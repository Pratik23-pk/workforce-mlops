# Argo CD GitOps Setup (AWS EKS)

This project uses GitOps CD:

1. GitHub Actions runs CT (`compare_models -> promote_model -> evaluate`) and pushes refreshed DVC artifacts.
2. GitHub Actions builds/pushes image to ECR.
3. GitHub Actions updates image tag in `deploy/k8s/overlays/prod/kustomization.yaml`.
4. Argo CD detects git change and syncs to EKS.

For end-to-end AWS setup in both modes, see:

- `docs/AWS_DEPLOY_PLAYBOOK.md`

## 1) Prerequisites

- EKS cluster running
- `kubectl` configured to the cluster
- Argo CD installed in `argocd` namespace
- Repo access configured in Argo CD (if repo is private)

## 2) Install Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

## 3) Apply the Application

```bash
kubectl apply -f deploy/argocd/application.yaml
```

## 4) Verify Sync

```bash
kubectl -n argocd get applications
kubectl -n workforce-mlops get deploy,svc,pods
```

## 5) Access App

```bash
kubectl -n workforce-mlops get svc workforce-mlops-api
```

Use the EXTERNAL-IP from the LoadBalancer service.

## 6) Required CI Secrets

Set in GitHub repo:

- `AWS_ROLE_TO_ASSUME`
- `AWS_REGION`
- `ECR_REPOSITORY`
- `DVC_S3_BUCKET`
- `MLFLOW_TRACKING_URI`
- `MLFLOW_EXPERIMENT_NAME` (optional override)

Use:

```bash
bash scripts/set_github_secrets.sh
```

## 7) Notes

- CD workflow skips self-trigger loops using actor guard.
- For private repos, Argo CD must be given repo credentials/token.
- If DVC pull is required during image build, ensure the OIDC role can access DVC S3 bucket.
