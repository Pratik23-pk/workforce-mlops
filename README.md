# Workforce MLOps (Multi-Task DNN)

End-to-end MLOps project for predicting workforce outcomes with one shared deep neural network and four output heads:

- Hiring (`new_hires`) - regression
- Layoffs (`layoffs`) - regression
- Layoff risk (`layoff_risk`) - binary classification
- Workforce volatility (`workforce_volatility`) - regression

## Project layout

```text
workforce-mlops/
├── app/                         # Streamlit app
├── artifacts/                   # Trained model + preprocessor bundle
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── docker/
├── infra/
├── reports/
├── scripts/
├── src/workforce_mlops/
│   ├── data/
│   └── models/
├── tests/
├── dvc.yaml
├── params.yaml
└── .github/workflows/
```

## Quickstart (macOS)

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
bash scripts/bootstrap_macos.sh
bash scripts/create_venv.sh
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Place your dataset at:

```text
data/raw/workforce.csv
```

## Local run

```bash
export PYTHONPATH=src
python -m workforce_mlops.data.ingest \
  --input data/raw/workforce.csv \
  --output data/interim/workforce_clean.csv

python -m workforce_mlops.data.validate \
  --input data/interim/workforce_clean.csv \
  --report reports/validation_report.json

python -m workforce_mlops.data.preprocess \
  --input data/interim/workforce_clean.csv \
  --train-output data/processed/train.csv \
  --val-output data/processed/val.csv \
  --test-output data/processed/test.csv \
  --params params.yaml

python -m workforce_mlops.models.train \
  --train-path data/processed/train.csv \
  --val-path data/processed/val.csv \
  --output-dir artifacts/model \
  --params params.yaml

python -m workforce_mlops.models.evaluate \
  --test-path data/processed/test.csv \
  --artifact-dir artifacts/model \
  --report-path reports/test_metrics.json

streamlit run app/streamlit_app.py
```

## AWS MLOps Setup
### Prerequisites (interactive)

```bash
brew install awscli
aws configure
gh auth login
```

### One-time AWS provisioning

```bash
export AWS_REGION="us-east-1"
export GITHUB_REPO="<owner>/workforce-mlops"
bash scripts/provision_aws.sh
source infra/aws_outputs.env
```

### DVC remote on S3

```bash
bash scripts/setup_dvc_s3.sh
dvc repro
dvc push -v -j 1
```

### MLflow on EC2

```bash
export EC2_HOST="$EC2_PUBLIC_IP"
bash scripts/setup_mlflow_ec2.sh

export MLFLOW_TRACKING_URI="http://$EC2_PUBLIC_IP:5000"
source scripts/setup_mlflow_aws.sh
```

### Build, push, and deploy Streamlit app

```bash
bash scripts/build_push_and_deploy.sh
```

### GitHub repository and CI/CD

```bash
bash scripts/bootstrap_github_repo.sh

export AWS_ROLE_TO_ASSUME="$AWS_ROLE_TO_ASSUME"
export AWS_REGION="$AWS_REGION"
export ECR_REPOSITORY="$ECR_REPOSITORY"
export EC2_HOST="$EC2_PUBLIC_IP"
export EC2_USER="ubuntu"
export EC2_SSH_KEY_PATH="$EC2_KEY_PATH"
export DVC_S3_BUCKET="$DVC_S3_BUCKET"
export MLFLOW_TRACKING_URI="http://$EC2_PUBLIC_IP:5000"
bash scripts/set_github_secrets.sh
```

## CI/CD

- `ci.yml`: lint + tests on PR/push.
- `cd.yml`: build/push Docker image and deploy to EC2 on `main`.

Add required GitHub secrets before enabling CD:

- `AWS_ROLE_TO_ASSUME`
- `AWS_REGION`
- `ECR_REPOSITORY`
- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_KEY`

Optional secrets:

- `MLFLOW_TRACKING_URI`
- `DVC_S3_BUCKET`

## Notes for first project

- Keep the first model small (dataset is only 532 rows).
- Prioritize reproducibility and traceability over model complexity.
- Add model/data drift monitoring after baseline deployment is stable.

## Troubleshooting

- See `/Users/pratikkanjilal/Documents/workforce-mlops/docs/TROUBLESHOOTING.md`
- AWS + GitHub CI/CD: `/Users/pratikkanjilal/Documents/workforce-mlops/docs/AWS_GITHUB_SETUP.md`
