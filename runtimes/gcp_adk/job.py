"""Cloud Run Job entrypoint — the nightly fleet run.

Runtime ADAPTER only: it wires run_fleet() to the platform (env, structured logging,
exit code). No fleet/guardrail/schema logic lives here — that stays in agents/.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# Dev convenience: load .env when running locally. In Cloud Run the config arrives as
# real env vars (--set-env-vars) and there is no .env, so this is a no-op there.
_envf = _ROOT / ".env"
if _envf.exists():
    for _l in _envf.read_text().splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from agents.fleet import run_fleet, run_fleet_for_profiles              # noqa: E402
from agents.profile_store import list_profiles                          # noqa: E402
from agents.delivery import (email_configured, email_secrets_present,   # noqa: E402
                             active_email_provider, send_brief, render_text, render_html)
from config.settings import settings                                    # noqa: E402


async def _main() -> None:
    replay = os.environ.get("DUCKFLEET_REPLAY", "false").lower() in ("1", "true", "yes")
    subject = f"Your DuckFleet brief for {date.today():%-d %b %Y}"

    # Multi-user path: every onboarded user in Firestore gets their own brief, valued off a
    # single shared scout. Falls back to the single-recipient default when no profiles exist
    # (or Firestore is unreachable) — so a brand-new signup tomorrow is picked up with no
    # redeploy, and today's operator-only setup keeps working unchanged.
    profiles = list_profiles() if not replay else []
    if profiles and email_secrets_present():
        await _run_for_profiles(profiles, subject, replay)
        return

    result = await run_fleet(replay=replay)
    brief = [a.model_dump() for a in result["brief"]]

    # Cloud Logging captures stdout — one structured line summarising the run.
    print(json.dumps({
        "event": "fleet_run_complete",
        "mode": "replay" if replay else "live",
        "n_candidates": result["n_candidates"],
        "excluded_tos": result["excluded_tos"],
        "brief": brief,
    }, default=str))

    # Deliver via Resend (preferred) or Gmail if configured; else say exactly what's missing.
    if email_configured():
        send_brief(subject, render_text(result), render_html(result))
        print(json.dumps({"event": "brief_emailed", "to": settings.notify_email,
                          "provider": active_email_provider()}))
    else:
        missing = []
        if not settings.notify_email:
            missing.append("DUCKFLEET_NOTIFY_EMAIL")
        if not email_secrets_present():
            missing.append("a sender: DUCKFLEET_RESEND_API_KEY + DUCKFLEET_RESEND_FROM "
                           "(preferred), or the DUCKFLEET_GMAIL_* fallback")
        print(json.dumps({"event": "brief_not_emailed", "missing_config": missing}))


async def _run_for_profiles(profiles: list, subject: str, replay: bool) -> None:
    """Scout once, fan out a brief per onboarded user, email each their own."""
    multi = await run_fleet_for_profiles(profiles, replay=replay)
    print(json.dumps({"event": "fleet_fanout_complete", "n_offers": multi["n_offers"],
                      "n_profiles": len(multi["runs"]), "scout_cost": multi["scout_cost"]},
                     default=str))
    provider = active_email_provider()
    for run in multi["runs"]:
        pid, to, result = run["profile_id"], run["notify_email"], run["result"]
        if not to:
            print(json.dumps({"event": "brief_skipped_no_email", "profile_id": pid}))
            continue
        try:
            send_brief(subject, render_text(result), render_html(result), to=to)
            print(json.dumps({"event": "brief_emailed", "profile_id": pid, "to": to,
                              "provider": provider, "n_candidates": result["n_candidates"]}))
        except Exception as e:  # one user's send failure must not sink the rest
            print(json.dumps({"event": "brief_send_error", "profile_id": pid, "error": str(e)}))

    # Operator digest: who newly signed up in the last day (product CRM data, read from the
    # duckfleet_interest lead list). Sends ONLY on a non-quiet day, to DUCKFLEET_ADMIN_EMAIL
    # (falls back to NOTIFY_EMAIL). Best-effort: never blocks or fails the fleet run.
    try:
        from agents.admin_digest import run_admin_digest
        print(json.dumps(run_admin_digest(), default=str))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"event": "admin_digest_error", "error": str(e)}))


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
