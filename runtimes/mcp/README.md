# DuckFleet remote MCP server

DuckFleet reachable from inside the assistant you already use (Claude / ChatGPT), added as a
**custom connector by URL** and usable **from your phone**. A hosting adapter over the
runtime-agnostic core — see `devlog/2026-08-30-mcp-distribution.md` for the why.

## What it exposes (deterministic — the assistant orchestrates, we do zero inference)
- `get_offers(tag, limit)` — current OzBargain points deals (read-only public feed).
- `worth_it(net_value_aud, drive_minutes, drive_km)` — is the errand worth the trip.
- `get_profile()` / `update_preferences(...)` — onboarding + preferences, by chat.

The user's assistant does the "finding" (which deals stack, how to phrase it) on *its* model
billing; these tools just fetch data and do the maths. That is what keeps it $0-inference to run
for other people. A full one-shot `run_hunt` (the whole pipeline) is a later, auth-gated add —
it does server-side inference, so it stays off the open MVP.

## 1. Test locally (stdio)
```
pip install fastmcp          # once (also add to your venv)
python -m runtimes.mcp.server --stdio
```
Point any MCP client at it, or use `fastmcp` tooling to list/call the tools.

## 2. Deploy (Cloud Run) — public HTTPS URL
```
bash runtimes/mcp/deploy.sh
```
Prints the connector URL: `https://duckfleet-app-mcp-<hash>-<region>.run.app/mcp`.
Optionally map a domain (like the onboarding page): `app-mcp.duckfleet.dev` via a Cloud Run
domain mapping (see how `app.duckfleet.dev` was set up), Google auto-issues the SSL cert.

## 3. Add it on your phone
In the Claude mobile app (Pro/Max/Team) → Settings → Connectors → Add custom connector → paste
the `/mcp` URL. It syncs to all your devices, so it is usable from the phone. Then just ask:
*"Use DuckFleet to find points deals worth chasing near me,"* or *"save my programs: Qantas and
Flybuys, avoid credit cards, I'm in Bondi."*

(ChatGPT: Settings → Connectors / developer mode → add the same URL.)

## Auth: open MVP vs per-user OAuth (both built in)
The server auto-selects based on env:
- **Open (no env set):** single shared `default` profile. Fine for your own testing / local
  stdio. Connector Authentication = **None**.
- **OAuth (per-user):** set `DUCKFLEET_MCP_BASE_URL`, `DUCKFLEET_MCP_GOOGLE_CLIENT_ID`, and the
  `duckfleet-mcp-google-client-secret` Secret Manager secret. Then each signed-in user keys
  their OWN profile (`duckfleet_profiles/<their-email>`) and the connector requires Google
  sign-in. This is the gate before sharing the URL or submitting to a directory.

### Turn on OAuth
1. **Map a stable domain first** (OAuth needs a fixed public URL). See `mcp.duckfleet.dev` below.
2. **Google OAuth client** (APIs & Services → Credentials → Web application; a dedicated
   "DuckFleet MCP" client is cleanest). Add **Authorized redirect URI**:
   `https://mcp.duckfleet.dev/auth/callback`. Copy its client id + secret.
3. **Secret Manager:** put the client secret in `duckfleet-mcp-google-client-secret`.
4. **.env:** `DUCKFLEET_MCP_BASE_URL=https://mcp.duckfleet.dev` and
   `DUCKFLEET_MCP_GOOGLE_CLIENT_ID=<id>`.
5. **Redeploy:** `bash runtimes/mcp/deploy.sh` (prints "OAuth ON").
6. **Re-add the connector** in Claude — it now auto-detects the auth server; pick
   Authentication = **Always required** and sign in with Google.

### mcp.duckfleet.dev (branded URL)
```
gcloud beta run domain-mappings create --service=duckfleet-app-mcp --domain=mcp.duckfleet.dev \
  --region=us-central1 --project=duckfleet-agents
```
Add the printed CNAME (`mcp` -> `ghs.googlehosted.com`) at GoDaddy, wait for the auto SSL cert,
then the connector URL is `https://mcp.duckfleet.dev/mcp`. Directory submission is the last step
for browse-and-tap install by anyone.

## Notes
- Requires `fastmcp` (in requirements.txt) — the Cloud Run image installs it on deploy.
- Frozen hackathon services are untouched; this is a new sibling service `duckfleet-app-mcp`.
- FastMCP's HTTP transport serves the MCP endpoint at `/mcp` by default; verify the path/flags
  against your installed FastMCP version if a client can't connect.
