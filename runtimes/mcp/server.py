"""Remote MCP server (FastMCP, Streamable HTTP) — DuckFleet inside Claude / ChatGPT.

Runtime ADAPTER only (Principle 3): wraps the runtime-agnostic core (agents/, schemas/,
guardrails/) as MCP tools. No fleet/guardrail/schema logic lives here.

Design intent (devlog/2026-08-30-mcp-distribution.md): the *user's assistant* owns the model
and orchestrates; these tools are DETERMINISTIC and do NO LLM inference, so running DuckFleet
for someone costs us nothing. `get_offers` fetches a stable public feed; `worth_it` and the
profile tools are pure Python / a small Firestore read-write. The LLM "finding" (which deals
stack, how to phrase it) is done by the assistant calling these tools.

Run:
  local dev (stdio):   python -m runtimes.mcp.server --stdio
  http (Cloud Run):    python -m runtimes.mcp.server            # streamable-http on $PORT
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# Dev convenience: load .env locally. In Cloud Run config arrives as real env vars.
_envf = _ROOT / ".env"
if _envf.exists():
    for _l in _envf.read_text().splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from fastmcp import FastMCP                      # noqa: E402
from config.settings import settings             # noqa: E402


def _build_auth():
    """Enable Google OAuth (per-user profiles) when all three env vars are set; else run open
    (single shared profile / local stdio). base_url must be the server's PUBLIC https URL
    (e.g. https://mcp.duckfleet.dev), and that + '/auth/callback' is the Google redirect URI."""
    cid = os.environ.get("DUCKFLEET_MCP_GOOGLE_CLIENT_ID", "").strip()
    csec = os.environ.get("DUCKFLEET_MCP_GOOGLE_CLIENT_SECRET", "").strip()
    base = os.environ.get("DUCKFLEET_MCP_BASE_URL", "").strip()
    if cid and csec and base:
        from fastmcp.server.auth.providers.google import GoogleProvider
        return GoogleProvider(client_id=cid, client_secret=csec,
                              base_url=base, redirect_path="/auth/callback")
    return None


_INSTRUCTIONS = (
    "DuckFleet hunts loyalty-points deals and tells the user what is actually worth doing. "
    "The DuckFleet 'profile' means the user's saved loyalty-points PREFERENCES held by this "
    "connector (programs, home suburb, weekly spend cap, categories to avoid). It is NOT an "
    "account, a login, a competition entry, or anything to submit. To set it up, just use "
    "get_profile and update_preferences here; never create accounts, enter passwords, or fill "
    "external forms. "
    "When the user greets you, asks what this is, or seems unsure what to do, introduce DuckFleet "
    "in one line and offer three starting points: set up their preferences, find deals worth "
    "chasing, or show what is saved. "
    "If get_profile is empty or sparse, offer to onboard them: ask for their loyalty programs, "
    "home suburb or postcode, weekly spend cap, and any deal categories to avoid, then save with "
    "update_preferences and confirm. To surface value, call get_offers, reason about which deals "
    "stack into worth-chasing points for THIS user's programs, and call worth_it before suggesting "
    "any in-store trip. All money, points and time maths must come from the tools, never guessed. "
    "Be honest about what you skip and why, and lead with the single best pick."
)

_auth = _build_auth()
_OAUTH = _auth is not None
mcp = FastMCP(name="DuckFleet", instructions=_INSTRUCTIONS, auth=_auth)


def _profile_id() -> str:
    """The signed-in user's Google email keys their OWN profile when OAuth is on; otherwise
    the single shared 'default' (open MVP / local stdio)."""
    if _OAUTH:
        try:
            from fastmcp.server.dependencies import get_access_token
            tok = get_access_token()
            email = (tok.claims or {}).get("email") if tok else None
            if email:
                return email
        except Exception:  # noqa: BLE001
            pass
    return settings.profile_id or "default"


@mcp.tool
def get_offers(tag: str = "", limit: int = 20) -> list[dict]:
    """Fetch current loyalty / points deals from the OzBargain feed (read-only, no login).
    `tag` optionally narrows the feed (e.g. "qantas", "flybuys"); `limit` caps the count.
    Returns structured offers (merchant, price, program hint, url) for you to reason over —
    decide which stack into something worth chasing, then check each with `worth_it`."""
    from agents.ozbargain_feed import fetch_deals
    return fetch_deals(tag=tag, limit=max(1, min(limit, 50)))


@mcp.tool
def get_pointhacks_offers(limit: int = 20) -> list[dict]:
    """Fetch current points/miles offers from the Point Hacks feed (read-only, no login).
    Point Hacks covers the earning side — card sign-up bonuses, transfer bonuses, program
    promos — that retail deal feeds miss. Returns raw items (title, url, categories, summary,
    program hint) for you to reason over. Numbers stated in the text are the source's, not
    computed; check anything actionable with `worth_it`."""
    from agents.pointhacks_feed import fetch_offers
    return fetch_offers(limit=max(1, min(limit, 50)))


@mcp.tool
def get_freepoints_offers(limit: int = 20) -> list[dict]:
    """Fetch current loyalty-points deals from the freepoints feed (read-only, no login).
    freepoints aggregates AU Flybuys / Everyday Rewards / Qantas / Velocity offers at Coles,
    Woolworths, BigW and partners. Returns raw items (title, url, categories, summary, program
    hint) for you to reason over — decide which are worth chasing, then check with `worth_it`."""
    from agents.freepoints_feed import fetch_offers
    return fetch_offers(limit=max(1, min(limit, 50)))


@mcp.tool
def worth_it(net_value_aud: float, drive_minutes: float, drive_km: float) -> dict:
    """Is an in-store errand worth the trip? Deterministic verdict weighing the net dollar
    value against the time + fuel of driving `drive_minutes` / `drive_km`. Call it before
    telling the user to go somewhere. Returns a structured verdict (do it / skip, the
    travel-adjusted value, and the reason)."""
    from agents.worth_it import worth_it_verdict
    return worth_it_verdict(net_value_aud, drive_minutes, drive_km)


@mcp.tool
def get_profile() -> dict:
    """Return the user's saved DuckFleet preferences (loyalty programs, categories to avoid,
    weekly spend cap, home suburb, notify email). Sparse or empty if they haven't onboarded."""
    from agents.profile_store import read_profile
    pid = _profile_id()
    return read_profile(pid) or {"profile_id": pid, "note": "no profile saved yet"}


@mcp.tool
def update_preferences(programs: list[str] | None = None,
                       prefs_avoid: list[str] | None = None,
                       spend_cap_aud_per_week: float | None = None,
                       time_value_aud_per_hour: float | None = None,
                       home_label: str | None = None,
                       notify_email: str | None = None) -> dict:
    """Save / merge the user's DuckFleet preferences (onboarding by chat). Pass ONLY the fields
    the user actually gave; omitted fields are left unchanged. Examples: programs
    ["qantas_ff", "flybuys"]; prefs_avoid ["credit_card"]; home_label a suburb or postcode.
    Returns the saved profile."""
    from agents.profile_store import read_profile, write_profile
    pid = _profile_id()
    prof = read_profile(pid) or {}
    updates = {"programs": programs, "prefs_avoid": prefs_avoid,
               "spend_cap_aud_per_week": spend_cap_aud_per_week,
               "time_value_aud_per_hour": time_value_aud_per_hour,
               "home_label": home_label, "notify_email": notify_email}
    for k, v in updates.items():
        if v is not None:
            prof[k] = v
    write_profile(prof, pid)
    return prof


@mcp.prompt
def onboard() -> str:
    """Set up your DuckFleet loyalty-points preferences."""
    return ("Use the DuckFleet connector to set up my loyalty-points preferences. Ask me for my "
            "loyalty programs, my home suburb or postcode, my weekly spend cap, and any deal "
            "categories I want to avoid, then save them with update_preferences and show me what "
            "you saved. This is just my saved preferences in the connector, not an account.")


@mcp.prompt
def find_deals() -> str:
    """Find current points deals worth chasing."""
    return ("Using DuckFleet, fetch current deals with get_offers, work out which are worth "
            "chasing for my saved programs, and give me a short ranked list of what's worth "
            "doing. Check any in-store errand with worth_it first, and lead with the best pick.")


@mcp.prompt
def my_profile() -> str:
    """Show what DuckFleet has saved for you."""
    return "Show my saved DuckFleet preferences using get_profile."


def main() -> None:
    if "--stdio" in sys.argv:
        mcp.run()  # stdio transport — local dev / testing
    else:
        mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
