#!/usr/bin/env bash
set -euo pipefail

if [[ "${AUTO_CLOUD_CONNECT:-1}" == "1" ]]; then
  /app/scripts/auto_cloud_connect.sh || echo "[entrypoint] auto_cloud_connect failed; continuing"
fi

exec uvicorn workforce_mlops.api.main:app \
  --host "${UVICORN_HOST:-0.0.0.0}" \
  --port "${UVICORN_PORT:-8000}"
