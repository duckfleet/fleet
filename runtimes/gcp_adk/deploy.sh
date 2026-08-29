#!/usr/bin/env bash
# Deploy the DuckFleet nightly fleet as a Cloud Run Job. Run from the repo root:
#   bash runtimes/gcp_adk/deploy.sh
#
# Prereqs (one-time, done by you in the console / earlier):
#   - Secret Manager secret exists for the preferred sender: duckfleet-resend-api-key
#     (Gmail fallback also supported: duckfleet-gmail-client-id/-client-secret/-refresh-token)
#   - .env has DUCKFLEET_NOTIFY_EMAIL, DUCKFLEET_RESEND_FROM (non-secret), and optionally
#     DUCKFLEET_LIST_UNSUBSCRIBE and DUCKFLEET_GMAIL_SENDER
set -euo pipefail

export CLOUDSDK_CONFIG="${CLOUDSDK_CONFIG:-$HOME/.config/gcloud-duckfleet}"
PROJECT=duckfleet-agents
REGION=us-central1
# Product deploy target. The frozen HACKATHON job stays as `duckfleet-nightly` and is never
# touched by this script. Override with DUCKFLEET_JOB=... only if you deliberately mean to.
JOB="${DUCKFLEET_JOB:-duckfleet-app-nightly}"
REPLAY="${DUCKFLEET_REPLAY:-false}"   # false = live hunt; set true for the hero-duck demo brief
# Set to the id the onboarding page writes (e.g. "default") to read the household profile from
# Firestore (duckfleet_profiles/<id>). Blank = use profile.json / env defaults only.
PROFILE_ID="${DUCKFLEET_PROFILE_ID:-}"

# Non-secret email config (read from .env; never echoed). RESEND_FROM must be an address on
# a domain you've VERIFIED in Resend (e.g. "DuckFleet <hunt@duckfleet.dev>"); LIST_UNSUBSCRIBE
# is optional (a mailto or https one-click URL for the List-Unsubscribe header).
NOTIFY_EMAIL=$(grep -E '^DUCKFLEET_NOTIFY_EMAIL=' .env | head -1 | cut -d= -f2-)
SENDER=$(grep -E '^DUCKFLEET_GMAIL_SENDER=' .env | head -1 | cut -d= -f2- || true)
RESEND_FROM=$(grep -E '^DUCKFLEET_RESEND_FROM=' .env | head -1 | cut -d= -f2- || true)
LIST_UNSUB=$(grep -E '^DUCKFLEET_LIST_UNSUBSCRIBE=' .env | head -1 | cut -d= -f2- || true)
: "${NOTIFY_EMAIL:?set DUCKFLEET_NOTIFY_EMAIL in .env}"

SA=$(gcloud iam service-accounts list --project "$PROJECT" \
      --format='value(email)' --filter='displayName:Compute Engine default')
echo "Runtime service account: $SA"

echo "== IAM: Vertex + Cloud Build + Secret Manager access =="
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA" --role=roles/aiplatform.user --condition=None -q >/dev/null
# New projects don't grant the default compute SA build rights; --source deploy needs it.
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA" --role=roles/cloudbuild.builds.builder --condition=None -q >/dev/null
for s in duckfleet-resend-api-key duckfleet-gmail-client-id duckfleet-gmail-client-secret duckfleet-gmail-refresh-token; do
  # `|| true`: the Gmail fallback secrets may not exist once you're on Resend — don't fail.
  gcloud secrets add-iam-policy-binding "$s" --project "$PROJECT" \
    --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor -q >/dev/null 2>&1 || true
done
# BigQuery: write offer_history + run query/load jobs. Datastore: read the onboarding
# profile from Firestore (duckfleet_profiles/<id>) when DUCKFLEET_PROFILE_ID is set.
for role in roles/bigquery.dataEditor roles/bigquery.jobUser roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" --role="$role" --condition=None -q >/dev/null
done

echo "== Deploy Cloud Run Job (REPLAY=$REPLAY) =="
gcloud run jobs deploy "$JOB" --source . --region "$REGION" --project "$PROJECT" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,DUCKFLEET_PROJECT_ID=$PROJECT,DUCKFLEET_REGION=$REGION,DUCKFLEET_MODEL_FAST=gemini-3.7-flash,DUCKFLEET_MODEL_STRONG=gemini-3.7-flash,DUCKFLEET_REPLAY=$REPLAY,DUCKFLEET_PROFILE_ID=$PROFILE_ID,DUCKFLEET_BIGQUERY_DATASET=duckfleet,DUCKFLEET_RESEND_FROM=$RESEND_FROM,DUCKFLEET_LIST_UNSUBSCRIBE=$LIST_UNSUB,DUCKFLEET_GMAIL_SENDER=$SENDER,DUCKFLEET_NOTIFY_EMAIL=$NOTIFY_EMAIL" \
  --set-secrets="DUCKFLEET_RESEND_API_KEY=duckfleet-resend-api-key:latest,DUCKFLEET_GMAIL_CLIENT_ID=duckfleet-gmail-client-id:latest,DUCKFLEET_GMAIL_CLIENT_SECRET=duckfleet-gmail-client-secret:latest,DUCKFLEET_GMAIL_REFRESH_TOKEN=duckfleet-gmail-refresh-token:latest"

echo "== Smoke test: run once now =="
gcloud run jobs execute "$JOB" --region "$REGION" --project "$PROJECT" --wait

echo "Done. Schedule it nightly with: bash runtimes/gcp_adk/schedule.sh"
