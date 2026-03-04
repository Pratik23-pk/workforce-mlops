#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${PYTHON_BIN:-}" ]]; then
  CANDIDATES=("${PYTHON_BIN}")
else
  CANDIDATES=(python3.12 python3.11 python3 python)
fi

PYTHON_CMD=""
for candidate in "${CANDIDATES[@]}"; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    PYTHON_CMD="${candidate}"
    break
  fi
done

if [[ -z "${PYTHON_CMD}" ]]; then
  echo "Python not found. Install Python 3.11 or 3.12 and rerun."
  exit 1
fi

VERSION_CHECK="$(${PYTHON_CMD} - <<'PY'
import sys
ok = (sys.version_info.major == 3 and 11 <= sys.version_info.minor < 13)
print("ok" if ok else f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

if [[ "${VERSION_CHECK}" != "ok" ]]; then
  echo "Expected Python 3.11 or 3.12, got ${VERSION_CHECK}. Set PYTHON_BIN to a supported interpreter."
  exit 1
fi

${PYTHON_CMD} -m venv .venv

echo "Created virtual environment with ${PYTHON_CMD}."
echo "Activate on macOS/Linux: source .venv/bin/activate"
echo "Activate on Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1"
echo "Then install dependencies:"
echo "  python -m pip install --upgrade pip"
echo "  pip install -r requirements.txt"
