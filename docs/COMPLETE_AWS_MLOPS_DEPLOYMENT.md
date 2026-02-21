# Complete MLOps Deployment on AWS

This guide maps 1:1 with the target phases for this repository.

## Current assumptions

- Codebase is at `/Users/pratikkanjilal/Documents/workforce-mlops`
- DVC cache already contains locally generated artifacts
- You will authenticate locally for AWS and GitHub CLI before running automation scripts

## Prerequisites (interactive)

```bash
brew install awscli
aws configure

gh auth login
```

## Phase 1: Provision AWS resources

Creates:

- S3 bucket for DVC cache/artifacts
- S3 bucket for MLflow artifacts
- ECR repository
- EC2 key pair (saved under `infra/keys/`)
- Security group (22, 80, 5000)
- EC2 IAM role + instance profile (ECR read + S3 access)
- EC2 instance (Ubuntu 22.04, `t3.small`) with `infra/user_data.sh`
- GitHub OIDC provider
- GitHub Actions deployment role
- Output inventory at `infra/aws_outputs.env`

Run:

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate

export AWS_REGION="us-east-1"
export GITHUB_REPO="<owner>/workforce-mlops"
export INSTANCE_TYPE="t3.small"

bash scripts/provision_aws.sh
source infra/aws_outputs.env
```

## Phase 2: DVC remote + push to S3

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate
source infra/aws_outputs.env

bash scripts/setup_dvc_s3.sh
dvc push -v -j 1
```

## Phase 3: MLflow on EC2

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate
source infra/aws_outputs.env

export EC2_HOST="$EC2_PUBLIC_IP"
bash scripts/setup_mlflow_ec2.sh

export MLFLOW_TRACKING_URI="http://$EC2_PUBLIC_IP:5000"
source scripts/setup_mlflow_aws.sh
```

## Phase 4: Build, push, deploy Streamlit container

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate
source infra/aws_outputs.env

export EC2_HOST="$EC2_PUBLIC_IP"
bash scripts/build_push_and_deploy.sh
```

## Phase 5: GitHub repo + CI/CD

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate
source infra/aws_outputs.env

bash scripts/bootstrap_github_repo.sh

export EC2_HOST="$EC2_PUBLIC_IP"
export EC2_USER="ubuntu"
export EC2_SSH_KEY_PATH="$EC2_KEY_PATH"
export DVC_S3_BUCKET="$DVC_S3_BUCKET"
export MLFLOW_TRACKING_URI="http://$EC2_PUBLIC_IP:5000"

bash scripts/set_github_secrets.sh
```

Push to trigger CD:

```bash
git add .
git commit -m "Finalize AWS MLOps automation"
git push origin main
```

## Phase 6: Verification

```bash
source infra/aws_outputs.env

echo "Streamlit: http://$EC2_PUBLIC_IP/"
echo "MLflow:    http://$EC2_PUBLIC_IP:5000"
```

Validation checks:

- Streamlit UI reachable at `http://<EC2_HOST>/`
- MLflow UI reachable at `http://<EC2_HOST>:5000`
- `dvc push` and `dvc pull` succeed against S3 remote
