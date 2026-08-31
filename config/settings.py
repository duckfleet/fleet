"""Central config. Everything overridable via env — including models per tier."""
import json
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- GCP ---
    project_id: str = "your-gcp-project"
    region: str = "us-central1"
    # Set (e.g. "duckfleet") to append each run's offers to BigQuery offer_history.
    # Empty = disabled (best-effort sink; never blocks the brief).
    bigquery_dataset: str = ""
    # Set (e.g. "default") to load the household profile from the Firestore doc the hosted
    # onboarding page writes (duckfleet_profiles/<id>). Empty = use profile.json / env only.
    profile_id: str = ""

    # --- Model tiers (THE SWITCH) ---
    # Plain string -> native Gemini via ADK.
    # "vertex_ai/..." or "litellm/..." prefix -> LiteLlm wrapper (e.g. Claude on
    # Vertex AI Model Garden). Still 100% inside GCP.
    model_fast: str = "gemini-3.7-flash"      # scouts, worth-it, presenter
    # Newest GA Gemini 3 available to the project (probed 2026-08-21). No 3.x Pro is
    # available yet (3-pro / 3.5-pro both 404), so both tiers use 3.7-flash — the strongest
    # option; swap STRONG to a 3.x Pro via env once your project gets access.
    model_strong: str = "gemini-3.7-flash"    # coordinator, valuer, caller

    # --- Household profile (hackathon: hardcode, don't build OAuth) ---
    home_lat: float = -27.5236   # Tarragindi-ish; set yours
    home_lng: float = 153.0413
    programs: list[str] = ["qantas_ff", "flybuys", "everyday_rewards"]
    cards: list[str] = ["qantas_amex"]
    time_value_aud_per_hour: float = 60.0
    fuel_aud_per_km: float = 0.16
    # Category preferences: avoid = always skip (shown in brief, with reason);
    # conditional = surface only if net value clears the $ bar; else "want" (default).
    prefs_avoid: list[str] = ["credit_card"]
    prefs_conditional: dict[str, float] = {"insurance": 300.0}
    # Where the morning brief is emailed (hackathon: one recipient in config;
    # later: per-user from the profile UI). Set DUCKFLEET_NOTIFY_EMAIL in .env.
    notify_email: str = ""
    # Operator address for the daily "who signed up" digest (agents/admin_digest). Blank
    # falls back to notify_email. Set DUCKFLEET_ADMIN_EMAIL to send the digest elsewhere.
    admin_email: str = ""

    # Resend (transactional ESP) — the PREFERRED sender: an own-domain, authenticated path
    # that actually reaches the inbox (a consumer @gmail.com sender lands in spam). The API
    # key is read ONLY from env / Secret Manager, never committed. When resend_api_key +
    # resend_from are both set, send_brief() uses Resend; otherwise it falls back to Gmail.
    # NOTE: Resend only accepts arbitrary recipients once you VERIFY duckfleet.dev in the
    # Resend dashboard and send from an address on it (e.g. "DuckFleet <hunt@duckfleet.dev>").
    # Until verified, Resend only allows from "onboarding@resend.dev" to your OWN account email.
    resend_api_key: str = ""
    resend_from: str = ""           # e.g. "DuckFleet <hunt@duckfleet.dev>"
    # List-Unsubscribe header value (bulk-inbox deliverability; replaces "reply STOP"). A
    # mailto or an https one-click URL, WITHOUT angle brackets, e.g.
    # "mailto:stop@duckfleet.dev" or "https://duckfleet.dev/unsubscribe?u=TOKEN". An https
    # value also emits the RFC 8058 one-click POST header. Blank = header omitted.
    list_unsubscribe: str = ""

    # Gmail send credentials — read ONLY from env / Secret Manager, NEVER hardcoded
    # or committed. Get a refresh token once via scripts/gmail_authorize.py. Fallback sender
    # (used only when Resend is not configured).
    gmail_sender: str = ""          # e.g. duckfleet.dev@gmail.com (blank -> "me")
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""

    # Phone verification (Twilio) — creds ONLY from env/Secret Manager, never committed.
    # verify_phone_number = who to call (test: YOUR OWN number; prod: the store's).
    # Blank/unset = fall back to the labelled call simulation.
    verify_phone_number: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    # Trial accounts can't pass inline TwiML — point this at a TwiML Bin URL (or the
    # Twilio demo doc) and we call with `url=` instead. Blank = inline TwiML (paid accounts).
    twilio_twiml_url: str = ""

    # --- Guardrails (hard limits, not suggestions) ---
    spend_cap_aud_per_week: float = 100.0
    max_calls_per_store_per_day: int = 1
    call_window_local: tuple[int, int] = (9, 17)   # only call 9am-5pm
    require_human_approval_for: list[str] = ["phone_call", "purchase"]

    model_config = {"env_prefix": "DUCKFLEET_"}


settings = Settings()

# Apply the onboarding profile on top of env/defaults. Two sources, lowest→highest:
#   1. profile.json  — what the local `adk web` onboarding agent writes.
#   2. Firestore doc — what the hosted Cloud Run onboarding page writes (if DUCKFLEET_PROFILE_ID
#      is set). This lets a user onboard on a web page and have tonight's run pick it up,
#      with no redeploy. Both are best-effort: a failure leaves env/defaults intact.
def _overlay(profile: dict) -> None:
    for _k, _v in profile.items():
        if hasattr(settings, _k) and _v not in (None, [], {}):
            setattr(settings, _k, _v)


from contextlib import contextmanager  # noqa: E402


@contextmanager
def profile_overrides(profile: dict):
    """Temporarily overlay one user's profile onto the global settings, then restore.

    The multi-user nightly fan-out (agents/fleet.run_fleet_for_profiles) values the same
    shared offer pool once per profile: it enters this context so the gates / valuer read
    THAT user's programs, spend cap and preferences, and restores the originals on exit.
    Sequential use only (settings is a process-wide singleton) — the fan-out loops, never
    gathers, so no two profiles are ever active at once.
    """
    keys = [k for k in profile if hasattr(settings, k) and profile[k] not in (None, [], {})]
    snapshot = {k: getattr(settings, k) for k in keys}
    try:
        for k in keys:
            setattr(settings, k, profile[k])
        yield
    finally:
        for k, v in snapshot.items():
            setattr(settings, k, v)


_profile_path = Path(__file__).resolve().parent.parent / "profile.json"
if _profile_path.exists():
    try:
        _overlay(json.loads(_profile_path.read_text()))
    except Exception:
        pass

if settings.profile_id:
    try:
        from agents.profile_store import read_profile
        _remote = read_profile(settings.profile_id)
        if _remote:
            _overlay(_remote)
    except Exception:
        pass
