# AWS + GitHub Actions Setup

Primary runbook:

- `/Users/pratikkanjilal/Documents/workforce-mlops/docs/COMPLETE_AWS_MLOPS_DEPLOYMENT.md`

Quick start:

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate

export AWS_REGION="us-east-1"
export GITHUB_REPO="<owner>/workforce-mlops"
bash scripts/provision_aws.sh
source infra/aws_outputs.env

bash scripts/setup_dvc_s3.sh
dvc push -v -j 1

export EC2_HOST="$EC2_PUBLIC_IP"
bash scripts/setup_mlflow_ec2.sh
bash scripts/build_push_and_deploy.sh
bash scripts/bootstrap_github_repo.sh

export EC2_USER="ubuntu"
export EC2_SSH_KEY_PATH="$EC2_KEY_PATH"
export DVC_S3_BUCKET="$DVC_S3_BUCKET"
export MLFLOW_TRACKING_URI="http://$EC2_PUBLIC_IP:5000"
bash scripts/set_github_secrets.sh
```
