#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO_NAME="${GITHUB_REPO_NAME:-workforce-mlops}"
GITHUB_VISIBILITY="${GITHUB_VISIBILITY:-private}" # private|public
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI not found. Install gh first."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login"
  exit 1
fi

if [[ -z "$(git rev-parse --is-inside-work-tree 2>/dev/null)" ]]; then
  echo "Run this from inside a git repository."
  exit 1
fi

git branch -M "$DEFAULT_BRANCH"

if [[ -n "$(git status --porcelain)" ]]; then
  git add .
  git commit -m "Initial end-to-end workforce MLOps pipeline"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin "$DEFAULT_BRANCH"
else
  VISIBILITY_FLAG="--private"
  if [[ "$GITHUB_VISIBILITY" == "public" ]]; then
    VISIBILITY_FLAG="--public"
  fi

  gh repo create "$GITHUB_REPO_NAME" \
    "$VISIBILITY_FLAG" \
    --source=. \
    --remote=origin \
    --push
fi

REPO_SLUG="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
echo "GitHub repo ready: https://github.com/${REPO_SLUG}"
