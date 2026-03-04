#!/usr/bin/env bash
set -euo pipefail

echo "Bootstrap check: validating local prerequisites for workforce-mlops."

for candidate in python3.12 python3.11 python3 python; do
  if ! command -v "${candidate}" >/dev/null 2>&1; then
    continue
  fi

  if ${candidate} - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if (sys.version_info.major == 3 and 11 <= sys.version_info.minor < 13) else 1)
PY
  then
    PYTHON_CMD="${candidate}"
    break
  fi
done

if [[ -z "${PYTHON_CMD:-}" ]]; then
  echo "Python 3.11 or 3.12 not found. Install a supported version and rerun."
  exit 1
fi

PY_VERSION="$(${PYTHON_CMD} - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

echo "Python OK: ${PYTHON_CMD} (${PY_VERSION})"

for cmd in git pip; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}"
    exit 1
  fi
done

echo "Required tools OK: git, pip"
echo "Optional tools (needed only for specific workflows):"
for cmd in aws gh kubectl dvc; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    echo "  - ${cmd}: found"
  else
    echo "  - ${cmd}: not found"
  fi
done

echo
echo "Next steps:"
echo "  bash scripts/create_venv.sh"
echo "  source .venv/bin/activate   # macOS/Linux"
echo "  # or .\\.venv\\Scripts\\Activate.ps1   # Windows PowerShell"
echo "  python -m pip install --upgrade pip"
echo "  pip install -r requirements.txt"
