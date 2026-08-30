#!/usr/bin/env bash
# Deploy the DuckFleet remote MCP server as a Cloud Run *service*. Run from the repo root:
#   bash runtimes/mcp/deploy.sh
#
# Gives a public HTTPS URL you add to Claude / ChatGPT as a CUSTOM CONNECTOR: <url>/mcp
# MVP posture: NO auth (obscure URL), DETERMINISTIC tools only (no spend, no LLM inference,
# no secrets). Add OAuth before opening to strangers or submitting to a directory — see README.
set -euo pipefail

export CLOUDSDK_CONFIG="${CLOUDSDK_CONFIG:-$HOME/.config/gcloud-duckfleet}"
PROJECT=duckfleet-agents
REGION=us-central1
SERVICE="${DUCKFLEET_MCP_SERVICE:-duckfleet-app-mcp}"
PROFILE_ID="${DUCKFLEET_PROFILE_ID:-default}"

# OAuth (optional, per-user profiles): enabled when the public base URL + Google client id are
# in .env AND the client secret exists in Secret Manager (duckfleet-mcp-google-client-secret).
# Otherwise the server deploys OPEN (single shared 'default' profile).
MCP_BASE_URL=$(grep -E '^DUCKFLEET_MCP_BASE_URL=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)
MCP_CLIENT_ID=$(grep -E '^DUCKFLEET_MCP_GOOGLE_CLIENT_ID=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)

SA=$(gcloud iam service-accounts list --project "$PROJECT" \
      --format='value(email)' --filter='displayName:Compute Engine default')
echo "Runtime service account: $SA"

echo "== IAM: Cloud Build + Firestore (profile read/write) =="
for role in roles/cloudbuild.builds.builder roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" --role="$role" --condition=None -q >/dev/null
done

ENV_VARS="DUCKFLEET_PROJECT_ID=$PROJECT,DUCKFLEET_REGION=$REGION,DUCKFLEET_PROFILE_ID=$PROFILE_ID"

echo "== Deploy Cloud Run service =="
# Same image as the other runtimes (Dockerfile); --command/--args run the MCP server instead.
if [ -n "$MCP_BASE_URL" ] && [ -n "$MCP_CLIENT_ID" ]; then
  echo "   OAuth ON (base=$MCP_BASE_URL) — per-user Google sign-in, per-user profiles"
  gcloud secrets add-iam-policy-binding duckfleet-mcp-google-client-secret --project "$PROJECT" \
    --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor -q >/dev/null 2>&1 || true
  gcloud run deploy "$SERVICE" --source . --region "$REGION" --project "$PROJECT" \
    --command=python --args="-m,runtimes.mcp.server" \
    --allow-unauthenticated --cpu=1 --memory=512Mi \
    --set-env-vars="$ENV_VARS,DUCKFLEET_MCP_BASE_URL=$MCP_BASE_URL,DUCKFLEET_MCP_GOOGLE_CLIENT_ID=$MCP_CLIENT_ID" \
    --set-secrets="DUCKFLEET_MCP_GOOGLE_CLIENT_SECRET=duckfleet-mcp-google-client-secret:latest"
else
  echo "   OAuth OFF (open MVP) — set DUCKFLEET_MCP_BASE_URL + DUCKFLEET_MCP_GOOGLE_CLIENT_ID in .env to enable"
  gcloud run deploy "$SERVICE" --source . --region "$REGION" --project "$PROJECT" \
    --command=python --args="-m,runtimes.mcp.server" \
    --allow-unauthenticated --cpu=1 --memory=512Mi \
    --set-env-vars="$ENV_VARS"
fi

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" \
        --format='value(status.url)')
echo
echo "MCP server live. Add this to Claude / ChatGPT as a custom connector URL:"
echo "  $URL/mcp"
echo
echo "No-auth MVP: fine for your own phone (obscure URL, deterministic tools only). Add OAuth"
echo "before real users or a directory submission — see runtimes/mcp/README.md."
