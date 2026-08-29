#!/usr/bin/env bash
# Deploy the DuckFleet onboarding page as a Cloud Run *service* (the hosted front door).
# Run from the repo root:
#   bash runtimes/gcp_adk/deploy_onboard.sh
#
# What it does: builds the same image as the nightly job, but runs the FastAPI onboarding
# service instead of job.py. Chat writes the profile to Firestore (duckfleet_profiles/<id>);
# the nightly job reads that same doc when DUCKFLEET_PROFILE_ID is set (see below).
set -euo pipefail

export CLOUDSDK_CONFIG="${CLOUDSDK_CONFIG:-$HOME/.config/gcloud-duckfleet}"
PROJECT=duckfleet-agents
REGION=us-central1
# Product deploy target (new URL). The frozen HACKATHON page stays as `duckfleet-onboard` and
# is never touched by this script. Override with DUCKFLEET_SERVICE=... only if you mean to.
SERVICE="${DUCKFLEET_SERVICE:-duckfleet-app-onboard}"
PROFILE_ID="${DUCKFLEET_PROFILE_ID:-default}"   # fleet-run profile id (see note at end)

# Google sign-in gate (keeps bots off the public URL; gives per-user profiles keyed by
# verified email). Read from env or .env. Blank = OPEN (no login) — fine for a private
# test, not for a public URL. Create a Web OAuth client id: APIs & Services → Credentials
# → Create credentials → OAuth client ID → Web application, then add your Cloud Run URL to
# "Authorised JavaScript origins". Set DUCKFLEET_OAUTH_CLIENT_ID in .env or the environment.
OAUTH_CLIENT_ID="${DUCKFLEET_OAUTH_CLIENT_ID:-}"
if [ -z "$OAUTH_CLIENT_ID" ] && [ -f .env ]; then
  # `|| true` so a missing line doesn't trip `set -e`/`pipefail` and kill the script.
  OAUTH_CLIENT_ID=$(grep -E '^DUCKFLEET_OAUTH_CLIENT_ID=' .env | head -1 | cut -d= -f2- || true)
fi
if [ -z "$OAUTH_CLIENT_ID" ]; then
  echo "!! No OAuth client id set — deploying in OPEN mode (anyone can use the URL)."
  echo "   Set DUCKFLEET_OAUTH_CLIENT_ID to require Google sign-in. Continuing in 3s..."
  sleep 3
fi

# Sender config for the on-demand "sample brief" email (sent only to a user's verified
# address). Preferred: Resend (duckfleet-resend-api-key secret + DUCKFLEET_RESEND_FROM).
# Fallback: Gmail (3 secrets, same as the nightly job). All non-secret bits read from .env;
# no sender configured => the sample button simply hides.
SENDER=""
RESEND_FROM=""
LIST_UNSUB=""
if [ -f .env ]; then
  SENDER=$(grep -E '^DUCKFLEET_GMAIL_SENDER=' .env | head -1 | cut -d= -f2- || true)
  RESEND_FROM=$(grep -E '^DUCKFLEET_RESEND_FROM=' .env | head -1 | cut -d= -f2- || true)
  LIST_UNSUB=$(grep -E '^DUCKFLEET_LIST_UNSUBSCRIBE=' .env | head -1 | cut -d= -f2- || true)
fi

SA=$(gcloud iam service-accounts list --project "$PROJECT" \
      --format='value(email)' --filter='displayName:Compute Engine default')
echo "Runtime service account: $SA"

echo "== Enable APIs (Firestore) =="
gcloud services enable firestore.googleapis.com --project "$PROJECT" -q >/dev/null

echo "== Ensure a Firestore (Native mode) database exists =="
# The profile is stored in the (default) database. Creating it is idempotent here:
# if one already exists, gcloud errors and we carry on.
if ! gcloud firestore databases describe --project "$PROJECT" --database='(default)' >/dev/null 2>&1; then
  gcloud firestore databases create --project "$PROJECT" \
    --location="$REGION" --type=firestore-native -q
fi

echo "== IAM: Vertex + Cloud Build + Firestore access =="
for role in roles/aiplatform.user roles/cloudbuild.builds.builder roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" --role="$role" --condition=None -q >/dev/null
done
echo "== IAM: email secret access (for the sample-brief email) =="
for s in duckfleet-resend-api-key duckfleet-gmail-client-id duckfleet-gmail-client-secret duckfleet-gmail-refresh-token; do
  gcloud secrets add-iam-policy-binding "$s" --project "$PROJECT" \
    --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor -q >/dev/null 2>&1 || true
done

echo "== Deploy Cloud Run service (profile id: $PROFILE_ID) =="
# --command/--args override the Dockerfile CMD (which runs the nightly job) so the same
# image serves the onboarding app. --max-instances=1 keeps chat sessions on one instance
# (sessions are in-memory; state that must survive is the saved profile, which is in Firestore).
gcloud run deploy "$SERVICE" --source . --region "$REGION" --project "$PROJECT" \
  --command=python --args="-m,runtimes.gcp_adk.onboard_service" \
  --allow-unauthenticated --max-instances=1 --cpu=1 --memory=1Gi \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,DUCKFLEET_PROJECT_ID=$PROJECT,DUCKFLEET_REGION=$REGION,DUCKFLEET_MODEL_FAST=gemini-3.7-flash,DUCKFLEET_MODEL_STRONG=gemini-3.7-flash,DUCKFLEET_PROFILE_ID=$PROFILE_ID,GOOGLE_OAUTH_CLIENT_ID=$OAUTH_CLIENT_ID,DUCKFLEET_RESEND_FROM=$RESEND_FROM,DUCKFLEET_LIST_UNSUBSCRIBE=$LIST_UNSUB,DUCKFLEET_GMAIL_SENDER=$SENDER" \
  --set-secrets="DUCKFLEET_RESEND_API_KEY=duckfleet-resend-api-key:latest,DUCKFLEET_GMAIL_CLIENT_ID=duckfleet-gmail-client-id:latest,DUCKFLEET_GMAIL_CLIENT_SECRET=duckfleet-gmail-client-secret:latest,DUCKFLEET_GMAIL_REFRESH_TOKEN=duckfleet-gmail-refresh-token:latest"

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" \
        --format='value(status.url)')
echo
echo "Onboarding page live:  $URL"
if [ -n "$OAUTH_CLIENT_ID" ]; then
  echo "Sign-in: ON. Add this exact URL to the OAuth client's 'Authorised JavaScript origins':"
  echo "  $URL"
fi
echo
echo "NEXT: point the nightly job at the profile it should hunt (the fleet runs ONE profile;"
echo "the page can collect many). Redeploy the job with that doc id:"
if [ -n "$OAUTH_CLIENT_ID" ]; then
  echo "  # profiles are keyed by verified email when sign-in is on — use YOUR Google email:"
  echo "  DUCKFLEET_PROFILE_ID=you@gmail.com bash runtimes/gcp_adk/deploy.sh"
else
  echo "  DUCKFLEET_PROFILE_ID=$PROFILE_ID bash runtimes/gcp_adk/deploy.sh"
fi
echo "(The fleet then reads duckfleet_profiles/<id> from Firestore each run, falling back to"
echo " profile.json. Running a nightly hunt per user is multi-tenant execution — out of scope.)"
