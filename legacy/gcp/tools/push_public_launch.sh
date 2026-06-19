#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL="${REMOTE_URL:-git@github.com:saimihirj/Sift.git}"
BRANCH="${BRANCH:-codex/sift-public-ready}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Prepare Sift for public launch}"

cd "$(dirname "$0")/.."

echo "Checking GitHub CLI status..."
if command -v gh >/dev/null 2>&1; then
  gh auth status || true
else
  echo "GitHub CLI is not installed. Continuing with git over SSH."
fi

echo "Setting repository remote:"
echo "${REMOTE_URL}"
git remote set-url origin "${REMOTE_URL}"

echo "Staging Sift launch changes..."
git add \
  .firebaserc \
  .gitignore \
  README.md \
  backend/api/auth.py \
  cloudbuild.yaml \
  docs/DEPLOYMENT_CHECKLIST.md \
  docs/GCP_SERVERLESS_DEPLOYMENT.md \
  tests/test_cloud_readiness.py \
  tools/configure_oauth_cloud_run.sh \
  tools/deploy_clean_webapp_link.sh \
  tools/push_public_launch.sh

if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "${COMMIT_MESSAGE}"
fi

echo "Pushing ${BRANCH}..."
git push -u origin "${BRANCH}"

echo
echo "Pushed Sift launch branch:"
echo "${BRANCH}"
