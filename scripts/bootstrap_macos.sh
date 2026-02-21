#!/usr/bin/env bash
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install from https://brew.sh and rerun."
  exit 1
fi

brew update
brew install git python@3.11 awscli gh

echo "Installed: git, python@3.11, awscli, gh"
echo "Next: python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
