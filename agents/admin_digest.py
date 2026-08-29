"""Daily operator digest: 'who newly signed up', emailed to YOU only if there are new users.

Reads the duckfleet_interest lead list (see agents/interest_store) and reports verified users
whose first_seen falls in the last N hours. Sends NOTHING on a quiet day (no new users => no
email). This is OPERATIONAL / CRM data for the operator: it never emails the users themselves
and needs no user opt-in. Best-effort, mirroring the rest of the Firestore code.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from config.settings import settings
from agents.delivery import send_brief, email_secrets_present

log = logging.getLogger("duckfleet.admin_digest")

_COLLECTION = "duckfleet_interest"


def _client():
    from google.cloud import firestore
    return firestore.Client(project=settings.project_id)


def new_signups_since(hours: int = 24) -> list[dict]:
    """Verified users whose first_seen is within the last `hours`, oldest first.
    Best-effort: returns [] on any error (never blocks the run)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        q = _client().collection(_COLLECTION).where(filter=FieldFilter("first_seen", ">=", cutoff))
        rows = [d.to_dict() for d in q.stream()]
        rows.sort(key=lambda r: r.get("first_seen", ""))
        return rows
    except Exception as e:  # noqa: BLE001
        log.warning("admin_digest query failed (%s)", e)
        return []


def _render(rows: list[dict], hours: int) -> tuple[str, str, str]:
    n = len(rows)
    plural = "" if n == 1 else "s"
    subject = f"DuckFleet: {n} new user{plural} in the last {hours}h"

    def _flags(r: dict) -> str:
        f = []
        if r.get("interested"):
            f.append("opted in")
        if r.get("sample_count"):
            f.append(f"sample x{r.get('sample_count')}")
        return ", ".join(f)

    lines = [f"{n} new DuckFleet sign-up{plural} in the last {hours} hours:", ""]
    for r in rows:
        extra = _flags(r)
        tag = f"  ({extra})" if extra else ""
        lines.append(f"  - {r.get('email', '?')}   first seen {str(r.get('first_seen', '?'))[:16]}{tag}")
    text = "\n".join(lines)

    trs = "".join(
        f"<tr><td style='padding:4px 14px 4px 0'>{r.get('email', '?')}</td>"
        f"<td style='padding:4px 14px 4px 0;color:#6a675e'>{str(r.get('first_seen', '?'))[:16]}</td>"
        f"<td style='padding:4px 0;color:#6a675e'>{_flags(r)}</td></tr>"
        for r in rows)
    html = (
        "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
        "font-size:15px;color:#181812\">"
        f"<p><strong>{n}</strong> new DuckFleet sign-up{plural} in the last {hours}h.</p>"
        "<table style='border-collapse:collapse;font-size:14px'>"
        "<tr style='text-align:left;color:#6a675e'><th style='padding:4px 14px 4px 0'>Email</th>"
        "<th style='padding:4px 14px 4px 0'>First seen (UTC)</th><th style='padding:4px 0'>Signals</th></tr>"
        f"{trs}</table></div>")
    return subject, text, html


def run_admin_digest(hours: int = 24) -> dict:
    """Query new sign-ups and email the operator ONLY if there are any. Returns a status dict
    (never raises): quiet days and missing config are reported, not sent."""
    admin = settings.admin_email or settings.notify_email
    if not admin:
        return {"event": "admin_digest_skipped", "reason": "set DUCKFLEET_ADMIN_EMAIL (or NOTIFY_EMAIL)"}
    if not email_secrets_present():
        return {"event": "admin_digest_skipped", "reason": "no email sender configured"}
    rows = new_signups_since(hours)
    if not rows:
        return {"event": "admin_digest_quiet", "new_users": 0}
    subject, text, html = _render(rows, hours)
    try:
        send_brief(subject, text, html, to=admin)
    except Exception as e:  # noqa: BLE001
        log.warning("admin_digest send failed (%s)", e)
        return {"event": "admin_digest_error", "new_users": len(rows), "error": str(e)}
    return {"event": "admin_digest_sent", "new_users": len(rows), "to": admin}
