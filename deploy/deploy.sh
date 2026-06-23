#!/usr/bin/env bash
# Deploy the Aegis Underwriting Platform to Google Cloud Run.
#
# Prerequisites (one-time):
#   1. Install the gcloud CLI:  https://cloud.google.com/sdk/docs/install
#   2. gcloud auth login
#   3. gcloud config set project YOUR_PROJECT_ID
#   4. Enable APIs:  gcloud services enable run.googleapis.com cloudbuild.googleapis.com
#
# Then from the repo root:  ./deploy/deploy.sh
set -euo pipefail

PROJECT="$(gcloud config get-value project 2>/dev/null)"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-aegis-underwriting}"

if [[ -z "$PROJECT" || "$PROJECT" == "(unset)" ]]; then
  echo "No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

echo "Project : $PROJECT"
echo "Region  : $REGION"
echo "Service : $SERVICE"
echo

# Build the container with Cloud Build and push to Artifact Registry / GCR,
# then deploy to Cloud Run in one step. --source builds from the Dockerfile here.
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  ${ANTHROPIC_API_KEY:+--set-env-vars "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"}

echo
echo "Deployed. URL:"
gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)'
