#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sift-495116}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sift}"

cd "$(dirname "$0")/.."

echo "Using Google Cloud project: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

echo "Checking local build and tests..."
python3 -m py_compile tools/reset_runtime_data.py backend/services/model_router.py backend/schemas.py tests/test_cloud_readiness.py
python3 -m pytest
npm --prefix frontend run build

echo "Resetting deployed Sift runtime data..."
python3 tools/reset_runtime_data.py --gcp --project="${PROJECT_ID}" --yes

echo "Submitting Cloud Build deployment..."
gcloud builds submit --project="${PROJECT_ID}" --region="${REGION}" --config=cloudbuild.yaml .

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)')"

echo "Verifying live health..."
curl -fsS "${SERVICE_URL}/api/health" >/dev/null

echo "Verifying provider catalog..."
curl -fsS "${SERVICE_URL}/api/session/providers" >/dev/null

echo
echo "Sift is live:"
echo "${SERVICE_URL}"
