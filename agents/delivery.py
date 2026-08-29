"""Gmail delivery of the morning brief.

Credentials come ONLY from env / Secret Manager (never hardcoded, never committed):
DUCKFLEET_GMAIL_{SENDER,CLIENT_ID,CLIENT_SECRET,REFRESH_TOKEN} + DUCKFLEET_NOTIFY_EMAIL.
Runtime auth uses google-auth (already a dep) + httpx — no google-auth-oauthlib needed
here (that's only for the one-time scripts/gmail_authorize.py consent).
"""
from __future__ import annotations

import base64
from datetime import date
from email.message import EmailMessage
from html import escape as _esc

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from config.settings import settings

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_RESEND_URL = "https://api.resend.com/emails"


def resend_configured() -> bool:
    """True when a Resend API key + From address are set — the preferred sender."""
    return bool(settings.resend_api_key and settings.resend_from)


def gmail_secrets_present() -> bool:
    """True when the Gmail send credentials exist (recipient not required — the caller may
    pass an explicit `to`, e.g. a user's verified email for an on-demand sample)."""
    return bool(settings.gmail_client_id and settings.gmail_client_secret
                and settings.gmail_refresh_token)


def gmail_configured() -> bool:
    """True only when every Gmail secret + the default recipient is present."""
    return bool(gmail_secrets_present() and settings.notify_email)


def email_secrets_present() -> bool:
    """True when SOME sender is usable (Resend preferred, else Gmail). Recipient not
    required — the caller may pass an explicit `to`."""
    return resend_configured() or gmail_secrets_present()


def email_configured() -> bool:
    """True only when a sender AND the default nightly recipient are present."""
    return email_secrets_present() and bool(settings.notify_email)


def active_email_provider() -> str | None:
    """Which sender send_brief() will use right now: 'resend', 'gmail', or None."""
    if resend_configured():
        return "resend"
    if gmail_secrets_present():
        return "gmail"
    return None


_DIV = "═" * 32   # heavy divider
_SUB = "─" * 32   # light divider


def _verdict_label(v: str) -> str:
    return {"do_it": "DO IT", "needs_approval": "NEEDS YOUR OK", "skip": "SKIP"}.get(v, v.upper())


def render_text(result: dict) -> str:
    """Readable plain-text brief (no HTML). Groups a highlighted top pick, other
    do-items, skips, and ToS exclusions, then a provenance block so — during the
    build/simulation period — it's clear what's real vs simulated."""
    mode = result.get("mode", "live")
    items = sorted(result.get("brief", []), key=lambda a: a.rank)
    by_ref = _by_ref(result)
    excluded = result.get("excluded_tos", 0)
    n_do = sum(1 for a in items if a.verdict in ("do_it", "needs_approval"))
    n_skip = sum(1 for a in items if a.verdict == "skip")

    L: list[str] = [f"DuckFleet Daily Hunt · {date.today():%-d %b %Y}"]
    L.append("SIMULATION MODE: replay fixtures (not live deals)"
             if mode == "replay" else "LIVE run: OzBargain feed")
    L.append(f"Reviewed {result.get('n_candidates', len(items))}  ·  "
             f"{n_do} to do  ·  {n_skip} skipped  ·  {excluded} excluded (ToS)")
    L.append("")

    top = next((a for a in items if a.verdict in ("do_it", "needs_approval")), None)
    if top:
        cpp = f"  ·  {top.cents_per_point}c/pt" if top.cents_per_point is not None else ""
        L += [_DIV, "TOP PICK", top.headline,
              f"   {_big_value_text(top, by_ref)}   →  {_verdict_label(top.verdict)}",
              f"   {top.reasoning}", *_links_text(top, by_ref), _DIV, ""]

    others = [a for a in items if a.verdict in ("do_it", "needs_approval") and a is not top]
    if others:
        L.append("ALSO WORTH DOING")
        for a in others:
            cpp = f"  ·  {a.cents_per_point}c/pt" if a.cents_per_point is not None else ""
            L += [f"  • {a.headline} · ${a.net_value_aud:,.2f}{cpp}", f"    {a.reasoning}",
                  *_links_text(a, by_ref)]
        L.append("")

    skips = [a for a in items if a.verdict == "skip"]
    if skips:
        L.append("SKIPPED (saved you the trip)")
        for a in skips:
            L += [f"  • {a.headline}", f"    {a.reasoning}"]
        L.append("")

    if excluded:
        L += [f"EXCLUDED: {excluded} offer(s) blocked for ToS risk before review", ""]

    calls = result.get("call_candidates", [])
    if calls:
        L.append("STOCK CHECK: reply APPROVE and the fleet will call to verify before you go:")
        for c in calls:
            L.append(f"  • {c['merchant']}: {c['item']} (gated call: it self-identifies as AI)")
        L.append("")

    econ = result.get("economics")
    if econ:
        c, v, roi = econ.get("cost_aud", 0), econ.get("value_aud", 0), econ.get("roi")
        if econ.get("verdict") == "quiet_night":
            L += [f"Run economics: ~${c:.3f} compute · nothing cleared the bar, "
                  f"a quiet, cheap night (the fleet won't burn credit for nothing).", ""]
        else:
            roi_s = f"  (≈{roi:,.0f}× return)" if roi else ""
            worth = "worth running" if econ.get("verdict") == "worth_it" else "NOT worth the compute"
            L += [f"Run economics: ~${c:.3f} compute → ${v:,.2f} of value surfaced"
                  f"{roi_s}. {worth}.", ""]

    hist = result.get("history_rows", 0)
    L += [_SUB, "What's real vs simulated (build period):",
          f"  • Deals: {'replay fixtures (canned)' if mode == 'replay' else 'live OzBargain feed (real)'}",
          "  • Points maths & spend cap: real (deterministic Python)",
          f"  • Drive time/fuel: {'frozen fixture values' if mode == 'replay' else 'estimated from a local store directory'}",
          "  • Phone stock-check: gated; a real call on your approval (Twilio), else labelled-simulated",
          f"  • History → BigQuery: {f'yes ({hist} rows)' if hist else 'off'}",
          "", "You're receiving this because you set up DuckFleet."]
    return "\n".join(L)


def _badge(verdict: str) -> str:
    c = {"do_it": ("#e6f4ea", "#1a7f37", "DO IT"),
         "needs_approval": ("#fef7e6", "#b54708", "NEEDS YOUR OK"),
         "skip": ("#fdecec", "#b42318", "SKIP")}.get(verdict, ("#eee", "#333", verdict.upper()))
    return (f'<span style="background:{c[0]};color:{c[1]};padding:2px 8px;border-radius:10px;'
            f'font-size:11px;font-weight:700">{c[2]}</span>')


def _calendar_url(title: str, details: str = "") -> str:
    """A Google Calendar 'add event' link (all-day, tomorrow) so a good one isn't forgotten."""
    from datetime import date, timedelta
    from urllib.parse import quote
    d0 = date.today() + timedelta(days=1)
    d1 = d0 + timedelta(days=1)
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote('DuckFleet: ' + title)}&details={quote(details)}"
            f"&dates={d0:%Y%m%d}/{d1:%Y%m%d}")


def _by_ref(result: dict) -> dict:
    return {a.get("audit_ref"): a for a in result.get("assessed", [])}


_PLABEL = {"qantas_ff": "Qantas", "velocity": "Velocity", "flybuys": "Flybuys",
           "everyday_rewards": "Everyday Rewards", "none": ""}


def _big_value_html(item, by_ref: dict) -> str:
    """Lead with the POINTS; dollar value is a modelled estimate in subtext."""
    rec = by_ref.get(item.audit_ref) or {}
    pts = rec.get("total_points") or 0
    sub = ("font-size:17px;font-weight:600;color:#6a675e;letter-spacing:normal;margin-left:8px")
    if pts > 0:
        prog = _PLABEL.get(rec.get("program", ""), "")
        return (f'{pts:,}<span style="{sub}">{prog} pts · ~${item.net_value_aud:,.2f}</span>')
    return f'${item.net_value_aud:,.2f}<span style="{sub}">net</span>'


def _big_value_text(item, by_ref: dict) -> str:
    rec = by_ref.get(item.audit_ref) or {}
    pts = rec.get("total_points") or 0
    if pts > 0:
        prog = _PLABEL.get(rec.get("program", ""), "")
        return f"{pts:,} {prog} pts  (~${item.net_value_aud:,.2f} est. value)"
    return f"Worth ${item.net_value_aud:,.2f}"


def _links_html(item, by_ref: dict) -> str:
    """Editorial underlined text links (not buttons), to match the brief's typographic look."""
    url = (by_ref.get(item.audit_ref) or {}).get("source_url")
    base = "text-decoration:none;font-weight:600;font-size:15px;padding-bottom:1px;border-bottom:2px solid"
    out = []
    if url:
        out.append(f'<a href="{_esc(url)}" style="{base} #2b6cff55;color:#2b6cff">Activate</a>')
    ml = "margin-left:24px" if out else ""
    out.append(f'<a href="{_esc(_calendar_url(item.headline))}" style="{base} #e6e1d5;color:#6a675e;{ml}">'
               f'Add a reminder</a>')
    return "".join(out)


def _links_text(item, by_ref: dict) -> list[str]:
    url = (by_ref.get(item.audit_ref) or {}).get("source_url")
    lines = []
    if url:
        lines.append(f"   Activate/view: {url}")
    lines.append(f"   Add reminder: {_calendar_url(item.headline)}")
    return lines


_NUM = {0: "nothing", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
        6: "six", 7: "seven", 8: "eight", 9: "nine"}


def _word(n: int) -> str:
    return _NUM.get(n, str(n))


def render_html(result: dict) -> str:
    """Editorial, email-safe HTML: type + whitespace do the hierarchy (no images, no
    dashboard). Inline styles, solid highlight, and tables for side-by-side rows so it
    survives Gmail/Outlook; a system-font stack stands in where web fonts are stripped.
    Sent as the HTML alternative alongside plain text; clients that block HTML fall back."""
    mode = result.get("mode", "live")
    items = sorted(result.get("brief", []), key=lambda a: a.rank)
    by_ref = _by_ref(result)
    excluded = result.get("excluded_tos", 0)
    do_items = [a for a in items if a.verdict in ("do_it", "needs_approval")]
    top = do_items[0] if do_items else None
    others = do_items[1:]
    skips = [a for a in items if a.verdict == "skip"]
    calls = result.get("call_candidates", [])
    econ = result.get("economics")
    n_reviewed = result.get("n_candidates") or len(items)
    n_do, n_skip = len(do_items), len(skips)
    banner = "SIMULATION · replay fixtures" if mode == "replay" else "LIVE · OzBargain feed"

    INK, SOFT, RULE, PAPER, MARK = "#181812", "#6a675e", "#e6e1d5", "#faf7f0", "#ffe08a"
    FONT = ("'Space Grotesk',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
            "Helvetica,Arial,sans-serif")
    rule = f'<div style="height:1px;background:{RULE};margin:34px 0"></div>'

    def kicker(t: str) -> str:
        return (f'<div style="font-size:12px;font-weight:700;letter-spacing:2px;'
                f'text-transform:uppercase;color:{SOFT}">{t}</div>')

    P = [f'<div style="background:#eceae3;padding:24px 12px;margin:0">'
         f'<div style="font-family:{FONT};max-width:600px;margin:0 auto;background:{PAPER};'
         f'border-radius:18px;padding:44px 40px 32px;color:{INK};line-height:1.5">']

    # masthead (table for reliable left/right in email)
    P.append(
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:38px"><tr>'
        '<td style="font-weight:700;font-size:19px">DuckFleet</td>'
        f'<td align="right" style="color:{SOFT};font-size:12px;font-weight:600;letter-spacing:.4px">'
        f'{date.today():%-d %b} · {banner}</td></tr></table>')

    # headline carries the summary — no pills
    offers = f"{n_reviewed} offer" + ("" if n_reviewed == 1 else "s")
    parts = []
    if n_do:
        parts.append(f"Kept {_word(n_do)}")
    if n_skip:
        parts.append(f"Refused {_word(n_skip)}")
    line2 = (". ".join(parts) + ".") if parts else "Nothing cleared the bar tonight."
    P.append(
        f'<div style="font-size:42px;line-height:1.1;font-weight:700;letter-spacing:-1px">'
        f'Checked <span style="background:{MARK};padding:0 4px;border-radius:2px">{offers}</span> '
        f'overnight.<br>{line2}</div>')
    P.append(f'<div style="margin-top:16px;font-size:16px;line-height:1.55;color:{SOFT};'
             f'font-weight:500">Ran while you slept. Here\'s the short version, and what I passed on.</div>')

    if top:
        P.append(rule + kicker("Worth doing"))
        P.append(f'<div style="font-size:58px;font-weight:700;letter-spacing:-2px;line-height:1;'
                 f'margin-top:12px">{_big_value_html(top, by_ref)}</div>')
        P.append(f'<div style="margin-top:12px;font-size:17px;line-height:1.5;font-weight:500">'
                 f'{_esc(top.reasoning)}</div>')
        P.append(f'<div style="margin-top:20px">{_links_html(top, by_ref)}</div>')
        for a in others:
            # headline already carries the net value (e.g. "… ($5 net)"), so don't repeat it
            P.append(f'<div style="margin-top:22px;font-weight:600;font-size:17px">{_esc(a.headline)}</div>'
                     f'<div style="margin-top:12px">{_links_html(a, by_ref)}</div>')

    if skips:
        P.append(rule + kicker("Refused, on purpose"))
        for a in skips:
            P.append(f'<div style="margin-top:22px"><div style="font-size:18px;font-weight:700">'
                     f'{_esc(a.headline)}</div><div style="margin-top:5px;font-size:15px;line-height:1.5;'
                     f'color:{SOFT};font-weight:500">{_esc(a.reasoning)}</div></div>')

    if excluded:
        P.append(f'<div style="margin-top:22px;color:{SOFT};font-size:15px">Plus {excluded} '
                 f'offer{"" if excluded == 1 else "s"} blocked for ToS risk before I looked closer.</div>')

    if calls:
        names = ", ".join(_esc(c["merchant"]) for c in calls)
        P.append(rule + kicker("Waiting on you"))
        P.append(f'<div style="margin-top:12px;font-size:21px;line-height:1.4;font-weight:600;'
                 f'letter-spacing:-.3px">Reply <span style="background:{INK};color:{PAPER};padding:1px 9px;'
                 f'border-radius:6px;font-weight:700">APPROVE</span> and I\'ll call {names} to check '
                 f'stock. I\'ll tell them I\'m an AI.</div>')

    # footer (table for left/right)
    cost = ""
    if econ:
        c = econ.get("cost_aud", 0)
        cost = (f"A quiet night, cost ${c:.3f} to run."
                if econ.get("verdict") == "quiet_night" else f"Cost ${c:.3f} to run.")
    P.append(
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:40px;'
        f'border-top:1px solid {RULE}"><tr>'
        f'<td style="padding-top:14px;color:{SOFT};font-size:13px;font-weight:500">{cost}</td>'
        f'<td align="right" style="padding-top:14px;color:{SOFT};font-size:13px;font-weight:500">'
        f'You set up DuckFleet, so it sends you this brief.</td></tr></table>')

    P.append('</div></div>')
    return "".join(P)


def _list_unsub_headers() -> dict:
    """RFC 2369 / 8058 unsubscribe headers. A real unsubscribe path is required for bulk
    inbox placement (Gmail/Yahoo) and beats 'reply STOP'. An https value also gets the
    one-click POST header; a mailto value gets the plain header only."""
    v = settings.list_unsubscribe.strip()
    if not v:
        return {}
    h = {"List-Unsubscribe": f"<{v}>"}
    if v.lower().startswith("https://"):
        h["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    return h


def _send_via_resend(subject: str, body_text: str, body_html: str | None,
                     recipient: str) -> dict:
    """Send through Resend's REST API (kept on httpx to avoid a new dep — no SDK needed).
    Sends both text and html so HTML-blocking clients fall back."""
    payload: dict = {"from": settings.resend_from, "to": [recipient],
                     "subject": subject, "text": body_text}
    if body_html:
        payload["html"] = body_html
    headers = _list_unsub_headers()
    if headers:
        payload["headers"] = headers
    resp = httpx.post(_RESEND_URL, timeout=20.0, json=payload, headers={
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    })
    resp.raise_for_status()
    return resp.json()


def _access_token() -> str:
    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        token_uri=_TOKEN_URI,
    )
    creds.refresh(Request())
    return creds.token


def _send_via_gmail(subject: str, body_text: str, body_html: str | None,
                    recipient: str) -> dict:
    """Send through the Gmail API as settings.gmail_sender. Fallback path only — a consumer
    @gmail.com sender has poor deliverability; prefer Resend on a verified domain."""
    msg = EmailMessage()
    msg["To"] = recipient
    msg["From"] = settings.gmail_sender or "me"
    msg["Subject"] = subject
    for k, val in _list_unsub_headers().items():
        msg[k] = val
    msg.set_content(body_text)                      # plain-text fallback (always present)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    resp = httpx.post(_SEND_URL, headers={"Authorization": f"Bearer {_access_token()}"},
                      json={"raw": raw}, timeout=20.0)
    resp.raise_for_status()
    return resp.json()


def send_brief(subject: str, body_text: str, body_html: str | None = None,
               to: str | None = None) -> dict:
    """Send the brief. Uses Resend when configured (preferred, own-domain deliverability),
    else falls back to Gmail. Recipient defaults to settings.notify_email (the nightly job);
    pass `to` to send to a specific address (e.g. a user's VERIFIED sign-in email for an
    on-demand sample). Sends plain text + optional HTML so clients that block HTML fall back.
    Raises if no sender is configured or there is no recipient."""
    recipient = to or settings.notify_email
    if not recipient:
        raise RuntimeError("No recipient (pass `to` or set DUCKFLEET_NOTIFY_EMAIL).")
    if resend_configured():
        return _send_via_resend(subject, body_text, body_html, recipient)
    if gmail_secrets_present():
        return _send_via_gmail(subject, body_text, body_html, recipient)
    raise RuntimeError(
        "No email sender configured (set DUCKFLEET_RESEND_API_KEY + DUCKFLEET_RESEND_FROM, "
        "or the DUCKFLEET_GMAIL_* fallback).")
