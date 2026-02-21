#!/usr/bin/env bash
set -euo pipefail

if [[ -f infra/aws_outputs.env ]]; then
  # shellcheck disable=SC1091
  source infra/aws_outputs.env
fi

EC2_HOST="${EC2_HOST:-${EC2_PUBLIC_IP:-}}"
EC2_USER="${EC2_USER:-ubuntu}"
EC2_KEY_PATH="${EC2_KEY_PATH:-}"
MLFLOW_S3_BUCKET="${MLFLOW_S3_BUCKET:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
REMOTE_PROJECT_DIR="${REMOTE_PROJECT_DIR:-/home/${EC2_USER}/workforce-mlops}"
REMOTE_MLFLOW_VENV="${REMOTE_MLFLOW_VENV:-/home/${EC2_USER}/.venvs/mlflow}"
REMOTE_MLFLOW_HOME="${REMOTE_MLFLOW_HOME:-/home/${EC2_USER}/mlflow}"
MLFLOW_VERSION="${MLFLOW_VERSION:-2.17.2}"

if [[ -z "$EC2_HOST" || -z "$EC2_KEY_PATH" || -z "$MLFLOW_S3_BUCKET" ]]; then
  echo "Required: EC2_HOST/EC2_PUBLIC_IP, EC2_KEY_PATH, MLFLOW_S3_BUCKET"
  echo "Tip: source infra/aws_outputs.env first"
  exit 1
fi

if [[ ! -f "$EC2_KEY_PATH" ]]; then
  echo "EC2 key not found: $EC2_KEY_PATH"
  exit 1
fi

SSH_OPTS=(
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30
  -i "$EC2_KEY_PATH"
)

echo "Preparing remote directories"
ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" "mkdir -p ${REMOTE_PROJECT_DIR}/scripts ${REMOTE_PROJECT_DIR}/infra"

echo "Copying MLflow service assets"
scp "${SSH_OPTS[@]}" scripts/start_mlflow_server.sh "${EC2_USER}@${EC2_HOST}:${REMOTE_PROJECT_DIR}/scripts/start_mlflow_server.sh"
scp "${SSH_OPTS[@]}" infra/mlflow.service "${EC2_USER}@${EC2_HOST}:${REMOTE_PROJECT_DIR}/infra/mlflow.service"

echo "Installing and starting MLflow on EC2"
ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" <<EOF_REMOTE
set -euo pipefail

sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
mkdir -p ${REMOTE_MLFLOW_HOME}
rm -rf ${REMOTE_MLFLOW_VENV}
python3 -m venv ${REMOTE_MLFLOW_VENV}
${REMOTE_MLFLOW_VENV}/bin/python -m pip install --upgrade pip
${REMOTE_MLFLOW_VENV}/bin/pip install "mlflow==${MLFLOW_VERSION}" boto3
${REMOTE_MLFLOW_VENV}/bin/mlflow --version

chmod +x ${REMOTE_PROJECT_DIR}/scripts/start_mlflow_server.sh
sed -i "s|^Environment=MLFLOW_ARTIFACT_ROOT=.*|Environment=MLFLOW_ARTIFACT_ROOT=s3://${MLFLOW_S3_BUCKET}/mlflow-artifacts|g" ${REMOTE_PROJECT_DIR}/infra/mlflow.service
sed -i "s|^Environment=MLFLOW_BACKEND_STORE_URI=.*|Environment=MLFLOW_BACKEND_STORE_URI=sqlite:////home/${EC2_USER}/mlflow/mlflow.db|g" ${REMOTE_PROJECT_DIR}/infra/mlflow.service
sed -i "s|^Environment=MLFLOW_BIN=.*|Environment=MLFLOW_BIN=${REMOTE_MLFLOW_VENV}/bin/mlflow|g" ${REMOTE_PROJECT_DIR}/infra/mlflow.service

sudo cp ${REMOTE_PROJECT_DIR}/infra/mlflow.service /etc/systemd/system/mlflow.service
sudo systemctl daemon-reload
sudo systemctl enable mlflow
sudo systemctl restart mlflow
sleep 3
sudo systemctl --no-pager --full status mlflow | sed -n '1,40p'

if ! curl -fsS http://127.0.0.1:5000 >/dev/null; then
  echo "MLflow failed health check. Recent logs:"
  sudo journalctl -u mlflow -n 80 --no-pager
  exit 1
fi
EOF_REMOTE

echo "MLflow is running: http://${EC2_HOST}:5000"
echo "Set locally: export MLFLOW_TRACKING_URI=http://${EC2_HOST}:5000"
