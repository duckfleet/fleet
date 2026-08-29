#!/usr/bin/env bash
# Schedule the nightly fleet run (02:00 Australia/Brisbane -> triggers the Cloud Run Job).
#   bash runtimes/gcp_adk/schedule.sh
set -euo pipefail

export CLOUDSDK_CONFIG="${CLOUDSDK_CONFIG:-$HOME/.config/gcloud-duckfleet}"
PROJECT=duckfleet-agents
REGION=us-central1
# Points the nightly trigger at the PRODUCT job (Resend + cleaned brief). Running this repoints
# the existing `nightly-hunt` schedule to the product job, so the frozen hackathon job stops
# firing nightly (it stays deployed, just untriggered). Override with DUCKFLEET_JOB=... if needed.
JOB="${DUCKFLEET_JOB:-duckfleet-app-nightly}"
SCHED=nightly-hunt

SA=$(gcloud iam service-accounts list --project "$PROJECT" \
      --format='value(email)' --filter='displayName:Compute Engine default')

# The scheduler's SA needs permission to run the job.
gcloud run jobs add-iam-policy-binding "$JOB" --region "$REGION" --project "$PROJECT" \
  --member="serviceAccount:$SA" --role=roles/run.invoker -q >/dev/null

URI="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/$JOB:run"

# create (or update if it already exists)
if gcloud scheduler jobs describe "$SCHED" --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  VERB=update
else
  VERB=create
fi
gcloud scheduler jobs "$VERB" http "$SCHED" --location "$REGION" --project "$PROJECT" \
  --schedule="0 2 * * *" --time-zone="Australia/Brisbane" \
  --uri="$URI" --http-method=POST \
  --oauth-service-account-email="$SA"

echo "Scheduled '$SCHED' at 02:00 Australia/Brisbane. Pause with:"
echo "  gcloud scheduler jobs pause $SCHED --location $REGION --project $PROJECT"
