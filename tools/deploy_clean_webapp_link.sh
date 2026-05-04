#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sift-495116}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sift}"
SITE_ID="${1:-${FIREBASE_SITE_ID:-sift-platform}}"
APP_URL="https://${SITE_ID}.web.app"

cd "$(dirname "$0")/.."

if ! command -v firebase >/dev/null 2>&1; then
  echo "Firebase CLI not found."
  echo "Install it first with: npm install -g firebase-tools"
  exit 1
fi

echo "Using Firebase Hosting site: ${SITE_ID}"
echo "Canonical app URL will be: ${APP_URL}"

npm --prefix frontend run build

firebase hosting:sites:create "${SITE_ID}" --project "${PROJECT_ID}" || true
firebase target:apply hosting sift-clean "${SITE_ID}" --project "${PROJECT_ID}"

gcloud run services update "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --update-env-vars="SIFT_FRONTEND_URL=${APP_URL},SIFT_CORS_ORIGINS=${APP_URL},SIFT_COOKIE_SECURE=true,SIFT_COOKIE_SAMESITE=lax"

firebase deploy --only hosting:sift-clean --project "${PROJECT_ID}"

echo "Verifying clean link..."
curl -fsS "${APP_URL}/api/health" >/dev/null
curl -fsS "${APP_URL}/api/session/providers" >/dev/null

echo
echo "Clean Sift link:"
echo "${APP_URL}"
