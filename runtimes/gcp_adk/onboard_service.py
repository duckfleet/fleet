"""Cloud Run *service*: the hosted DuckFleet onboarding page. 🦆

The product front door — a branded chat page where a user sets their loyalty profile in
~30 seconds, no install, no dev console. Runtime ADAPTER only: it wires the shared
onboarding agent (agents/onboarding.py) to FastAPI + Firestore. The conversation logic and
the Profile contract live in agents/ and schemas/ — nothing agent-specific is invented here.

Flow:  browser  ──POST /api/chat──▶  onboarding agent (Gemini)  ──save_profile──▶  Firestore
        and the nightly fleet reads that same Firestore doc at startup (config/settings.py).

Access & identity:
  - If GOOGLE_OAUTH_CLIENT_ID is set, every /api call requires a valid Google ID token
    (Sign in with Google) — this keeps anonymous bots out of a public URL, and gives a
    verified email to key each person's profile on. Profiles are stored per email, so a
    returning user sees and edits what they saved before.
  - If it's unset (local dev), the service runs open and writes a single profile id
    (DUCKFLEET_PROFILE_ID, default "default").

Run locally:   python -m runtimes.gcp_adk.onboard_service   (serves on $PORT, default 8080)
Deploy:        bash runtimes/gcp_adk/deploy_onboard.sh
"""
from __future__ import annotations

import contextvars
import os
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# Dev convenience: load .env locally (no-op in Cloud Run, where config is real env vars).
_envf = _ROOT / ".env"
if _envf.exists():
    for _l in _envf.read_text().splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

import json                                                    # noqa: E402
from fastapi import FastAPI, Header, HTTPException             # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse  # noqa: E402
from pydantic import BaseModel                                 # noqa: E402
from google.adk.runners import InMemoryRunner                  # noqa: E402
from google.genai import types                                 # noqa: E402

from datetime import date                                           # noqa: E402
from agents.onboarding import build_onboarding_agent, build_profile  # noqa: E402
from agents.profile_store import write_profile, read_profile         # noqa: E402
from agents import interest_store                                    # noqa: E402
from agents.delivery import (email_secrets_present, render_text,      # noqa: E402
                             render_html, send_brief)
from agents.fleet import run_fleet                                   # noqa: E402
from guardrails.gates import record                                  # noqa: E402

_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
_DEFAULT_PID = os.environ.get("DUCKFLEET_PROFILE_ID", "default")
_APP = "duckfleet_onboarding"
_STATIC = Path(__file__).resolve().parent / "onboard_static" / "index.html"

# The profile id (Firestore doc) the save tool should write, set per-request from the
# caller's verified identity. A ContextVar keeps it isolated per request/task.
_current_pid: contextvars.ContextVar[str] = contextvars.ContextVar("pid", default=_DEFAULT_PID)
_primed: set[str] = set()  # sessions already given their existing-profile context


def save_profile(programs: list[str], avoid_categories: list[str],
                 conditional_categories: list[str], conditional_min_net_aud: float = 300.0,
                 spend_cap_aud_per_week: float = 100.0, notify_email: str = "",
                 home_label: str = "") -> dict:
    """Tool: persist the confirmed profile to Firestore (the fleet reads it next run).
    Maps free-form intent to the fleet's contract. Call once details are confirmed."""
    pid = _current_pid.get()
    profile = build_profile(programs, avoid_categories, conditional_categories,
                            conditional_min_net_aud, spend_cap_aud_per_week,
                            notify_email, home_label)
    ok = write_profile(profile.model_dump(), pid)
    record("profile_saved", programs=profile.programs, avoid=profile.prefs_avoid,
           sink="firestore", persisted=ok, profile_id=pid)
    return {"status": "saved" if ok else "save_failed",
            "profile_id": pid, "profile": profile.model_dump()}


_runner = InMemoryRunner(agent=build_onboarding_agent(save_profile), app_name=_APP)

app = FastAPI(title="DuckFleet Onboarding")


class ChatIn(BaseModel):
    session_id: str | None = None
    message: str


def _identify(authorization: str | None) -> tuple[str, str | None]:
    """Return (profile_id, email). Enforces Google sign-in when an OAuth client id is set;
    otherwise runs open (local dev) keyed to the default profile id."""
    if not _OAUTH_CLIENT_ID:
        return _DEFAULT_PID, None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in with Google to continue.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as greq
        claims = id_token.verify_oauth2_token(token, greq.Request(), _OAUTH_CLIENT_ID)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired sign-in. Please sign in again.")
    email = claims.get("email")
    if not email or not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="A verified Google email is required.")
    return email, email  # key the profile on the verified email


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "auth_required": bool(_OAUTH_CLIENT_ID)}


@app.get("/api/config")
def config() -> dict:
    """Front-end bootstrap: sign-in requirement, client id, and whether the sample-email
    button should show (only when send credentials are present on the service)."""
    return {"auth_required": bool(_OAUTH_CLIENT_ID), "client_id": _OAUTH_CLIENT_ID,
            "sample_available": email_secrets_present()}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _STATIC.read_text()


# llms.txt: a concise, curated description an AI assistant can fetch and act on (a no-connector
# on-ramp). Served here so app.duckfleet.dev/llms.txt is reachable; keep in sync with the MCP URL.
_LLMS_TXT = """# DuckFleet

> An agent fleet that hunts loyalty-points deals overnight and tells you what is actually worth
> doing, and what it skipped, with reasons. Open source, governed by design.

## Use it in your assistant (recommended)
Add the DuckFleet connector, a remote MCP server: https://mcp.duckfleet.dev/mcp
- Claude: Settings > Connectors > Add custom connector > paste the URL (paid plan).
- ChatGPT: Settings > Connectors (Plus and up).
Then say: "Set up my DuckFleet preferences" to onboard, or "find deals worth chasing".

## Use it on the web
Open https://app.duckfleet.dev , sign in with Google, and describe your setup, for example:
"Qantas and Flybuys, no more credit cards, $100 a week, brief me at me@example.com, I'm in Bondi."

## What it does
- Onboards your loyalty programs, home suburb, weekly spend cap, and categories to avoid.
- Fetches current deals, works out cents-per-point, and whether an errand is worth the drive.
- Deterministic maths and honest skips: it refuses, asks, and logs. It never guesses the numbers.

## Notes for an assistant helping a user
- "DuckFleet profile" means the user's saved loyalty-points preferences. It is not an account,
  a login, or anything to submit. Do not create accounts or fill external forms.
- Source: https://github.com/duckfleet/fleet
"""


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt() -> str:
    return _LLMS_TXT


@app.get("/api/profile")
def get_profile(authorization: str | None = Header(default=None)) -> JSONResponse:
    """Return the caller's currently-saved profile (or null) — the 'what you sent before' view.
    Also records the visit in the potential-users list (operational; not a marketing opt-in)."""
    pid, email = _identify(authorization)
    if email:
        interest_store.note_visit(email)
    return JSONResponse({"profile_id": pid, "email": email, "profile": read_profile(pid)})


class InterestIn(BaseModel):
    interested: bool


@app.post("/api/interest")
def set_interest(body: InterestIn, authorization: str | None = Header(default=None)) -> JSONResponse:
    """Explicit opt-in ('keep me posted') — the only thing that marks a user for follow-up."""
    _, email = _identify(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="Sign in to opt in.")
    return JSONResponse({"interested": interest_store.set_interested(email, body.interested)})


@app.post("/api/sample")
async def sample(authorization: str | None = Header(default=None)) -> JSONResponse:
    """Send a sample brief NOW to the caller's VERIFIED email — replay mode (deterministic
    fixtures, near-zero cost), rate-limited to once/24h. Never sends to any other address."""
    _, email = _identify(authorization)
    recipient = email or settings.notify_email  # open dev mode falls back to the configured inbox
    if not recipient:
        raise HTTPException(status_code=400, detail="No verified email to send to.")
    if not email_secrets_present():
        raise HTTPException(status_code=503, detail="Email isn't configured on this instance yet.")
    if email and not interest_store.can_send_sample(email):
        raise HTTPException(status_code=429,
                            detail="You've already had a sample today — check your inbox (and spam).")

    result = await run_fleet(replay=True)
    subject = f"Your sample DuckFleet brief, {date.today():%-d %b %Y}"
    send_brief(subject, render_text(result), render_html(result), to=recipient)
    if email:
        interest_store.note_sample(email)
    record("sample_sent", to=recipient, mode="replay")
    return JSONResponse({"sent": True, "to": recipient})


async def _ensure_session(session_id: str) -> None:
    svc = _runner.session_service
    existing = await svc.get_session(app_name=_APP, user_id=session_id, session_id=session_id)
    if existing is None:
        await svc.create_session(app_name=_APP, user_id=session_id, session_id=session_id)


@app.post("/api/chat")
async def chat(body: ChatIn, authorization: str | None = Header(default=None)) -> JSONResponse:
    pid, email = _identify(authorization)
    _current_pid.set(pid)

    session_id = body.session_id or uuid.uuid4().hex
    await _ensure_session(session_id)

    # First turn of a returning user's session: give the agent their saved profile so
    # partial edits ("change my email") preserve everything else.
    text = body.message
    if session_id not in _primed:
        _primed.add(session_id)
        existing = read_profile(pid)
        if existing:
            text = (f"(Context — this is a returning user. Their current saved profile is "
                    f"{json.dumps(existing)}. Treat their message as edits to it, keeping "
                    f"unchanged fields, then confirm and call save_profile with the FULL "
                    f"updated set.)\n\nUser: {body.message}")

    msg = types.Content(role="user", parts=[types.Part(text=text)])
    reply = ""
    save_status = None
    async for ev in _runner.run_async(user_id=session_id, session_id=session_id,
                                      new_message=msg):
        for fr in ev.get_function_responses():
            if fr.name == "save_profile" and isinstance(fr.response, dict):
                save_status = fr.response.get("status")
        if ev.is_final_response() and ev.content and ev.content.parts:
            reply = "".join(p.text or "" for p in ev.content.parts)

    # Authoritative receipt: read the doc back from Firestore rather than trusting the
    # model's prose. `saved` is true only if the profile really landed.
    saved = False
    stored = None
    if save_status is not None:
        stored = read_profile(pid)
        saved = save_status == "saved" and stored is not None

    return JSONResponse({
        "session_id": session_id,
        "reply": reply,
        "attempted_save": save_status is not None,
        "saved": saved,
        "profile_id": pid,
        "profile": stored,
        "error": None if (save_status is None or saved) else
                 "The profile couldn't be saved to the cloud. Please try again.",
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
