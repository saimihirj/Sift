#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sift-495116}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sift}"
SITE_ID="${SITE_ID:-sift-vc}"
APP_URL="${APP_URL:-https://${SITE_ID}.web.app}"
RUNTIME_SA="${RUNTIME_SA:-sift-runner@${PROJECT_ID}.iam.gserviceaccount.com}"

REQUIRED_ENV_VARS=(
  GOOGLE_OAUTH_CLIENT_ID
  GOOGLE_OAUTH_CLIENT_SECRET
  APPLE_OAUTH_CLIENT_ID
  APPLE_OAUTH_CLIENT_SECRET
  LINKEDIN_OAUTH_CLIENT_ID
  LINKEDIN_OAUTH_CLIENT_SECRET
  X_OAUTH_CLIENT_ID
  X_OAUTH_CLIENT_SECRET
)

missing=()
for name in "${REQUIRED_ENV_VARS[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("${name}")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "Missing OAuth values:"
  printf '  %s\n' "${missing[@]}"
  echo
  echo "Set those values in your shell first. Do not paste OAuth secrets into chat."
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Google Cloud CLI not found."
  exit 1
fi

upsert_secret() {
  local secret_name="$1"
  local secret_value="$2"

  if gcloud secrets describe "${secret_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    printf '%s' "${secret_value}" | gcloud secrets versions add "${secret_name}" \
      --project="${PROJECT_ID}" \
      --data-file=- >/dev/null
  else
    printf '%s' "${secret_value}" | gcloud secrets create "${secret_name}" \
      --project="${PROJECT_ID}" \
      --data-file=- >/dev/null
  fi
}

echo "Writing OAuth credentials to Secret Manager for ${PROJECT_ID}..."
upsert_secret google-oauth-client-id "${GOOGLE_OAUTH_CLIENT_ID}"
upsert_secret google-oauth-client-secret "${GOOGLE_OAUTH_CLIENT_SECRET}"
upsert_secret apple-oauth-client-id "${APPLE_OAUTH_CLIENT_ID}"
upsert_secret apple-oauth-client-secret "${APPLE_OAUTH_CLIENT_SECRET}"
upsert_secret linkedin-oauth-client-id "${LINKEDIN_OAUTH_CLIENT_ID}"
upsert_secret linkedin-oauth-client-secret "${LINKEDIN_OAUTH_CLIENT_SECRET}"
upsert_secret x-oauth-client-id "${X_OAUTH_CLIENT_ID}"
upsert_secret x-oauth-client-secret "${X_OAUTH_CLIENT_SECRET}"

echo "Granting Cloud Run access to OAuth secrets..."
for secret_name in \
  google-oauth-client-id \
  google-oauth-client-secret \
  apple-oauth-client-id \
  apple-oauth-client-secret \
  linkedin-oauth-client-id \
  linkedin-oauth-client-secret \
  x-oauth-client-id \
  x-oauth-client-secret; do
  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role=roles/secretmanager.secretAccessor >/dev/null
done

echo "Updating Cloud Run OAuth configuration..."
gcloud run services update "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --update-env-vars="SIFT_FRONTEND_URL=${APP_URL},SIFT_CORS_ORIGINS=${APP_URL},SIFT_COOKIE_SECURE=true,SIFT_COOKIE_SAMESITE=none" \
  --update-secrets="GOOGLE_OAUTH_CLIENT_ID=google-oauth-client-id:latest,GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest,APPLE_OAUTH_CLIENT_ID=apple-oauth-client-id:latest,APPLE_OAUTH_CLIENT_SECRET=apple-oauth-client-secret:latest,LINKEDIN_OAUTH_CLIENT_ID=linkedin-oauth-client-id:latest,LINKEDIN_OAUTH_CLIENT_SECRET=linkedin-oauth-client-secret:latest,X_OAUTH_CLIENT_ID=x-oauth-client-id:latest,X_OAUTH_CLIENT_SECRET=x-oauth-client-secret:latest"

echo "Verifying OAuth provider endpoint..."
curl -fsS "${APP_URL}/api/auth/providers"
echo
echo "OAuth callbacks to register:"
echo "${APP_URL}/api/auth/callback/google"
echo "${APP_URL}/api/auth/callback/apple"
echo "${APP_URL}/api/auth/callback/linkedin"
echo "${APP_URL}/api/auth/callback/x"
