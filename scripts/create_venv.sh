#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 not found. Install with: brew install python@3.11"
  exit 1
fi

python3.11 -m venv .venv
source .venv/bin/activate

PY_VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$PY_VER" != "3.11" ]]; then
  echo "Expected Python 3.11 in virtualenv, got ${PY_VER}"
  exit 1
fi

echo "Created .venv with Python $(python --version | awk '{print $2}')"
echo "Next: pip install --upgrade pip && pip install -r requirements.txt"
