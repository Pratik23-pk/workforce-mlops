# End-to-End Setup Guide (macOS, AWS-only)

## 1) Local setup

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
bash scripts/bootstrap_macos.sh
bash scripts/create_venv.sh
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Local model pipeline

Put dataset at `data/raw/workforce.csv`, then:

```bash
export PYTHONPATH=src
dvc repro
streamlit run app/streamlit_app.py
```

## 3) AWS provisioning

```bash
aws configure
gh auth login

export AWS_REGION="us-east-1"
export GITHUB_REPO="<owner>/workforce-mlops"

bash scripts/provision_aws.sh
source infra/aws_outputs.env
```

## 4) DVC + MLflow + deployment

```bash
bash scripts/setup_dvc_s3.sh
dvc push -v -j 1

export EC2_HOST="$EC2_PUBLIC_IP"
bash scripts/setup_mlflow_ec2.sh

export MLFLOW_TRACKING_URI="http://$EC2_PUBLIC_IP:5000"
source scripts/setup_mlflow_aws.sh

bash scripts/build_push_and_deploy.sh
```

## 5) GitHub and Actions secrets

```bash
bash scripts/bootstrap_github_repo.sh

export EC2_USER="ubuntu"
export EC2_SSH_KEY_PATH="$EC2_KEY_PATH"
export DVC_S3_BUCKET="$DVC_S3_BUCKET"
export MLFLOW_TRACKING_URI="http://$EC2_PUBLIC_IP:5000"

bash scripts/set_github_secrets.sh
```

Full runbook:

- `/Users/pratikkanjilal/Documents/workforce-mlops/docs/COMPLETE_AWS_MLOPS_DEPLOYMENT.md`
