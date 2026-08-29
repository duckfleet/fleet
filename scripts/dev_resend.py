#!/usr/bin/env python
"""Smoke-test the Resend sender and check inbox placement BEFORE real users see it.

    ./.venv/bin/python scripts/dev_resend.py you@example.com            # tiny hello test
    ./.venv/bin/python scripts/dev_resend.py test-xxxx@srv1.mail-tester.com   # spam score
    ./.venv/bin/python scripts/dev_resend.py you@example.com --brief    # a real replay brief

Reads DUCKFLEET_RESEND_API_KEY + DUCKFLEET_RESEND_FROM from .env (or the environment).
Locally the key isn't in Secret Manager, so put it in .env to run this:
    DUCKFLEET_RESEND_API_KEY=re_...
    DUCKFLEET_RESEND_FROM=DuckFleet <hunt@duckfleet.dev>   # verified-domain address
Until you've verified duckfleet.dev in Resend, use  onboarding@resend.dev  as the From and
send only to your OWN Resend account email — that's all an unverified account may do.

Tip: send to a fresh https://www.mail-tester.com address and open the score to see SPF/DKIM/
DMARC and content flags. Aim for 10/10 before pointing real users at it.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_env(path: Path) -> None:
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env(ROOT / ".env")

from agents.delivery import resend_configured, send_brief, render_text, render_html  # noqa: E402
from config.settings import settings                                                 # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("Usage: dev_resend.py <recipient> [--brief]")
    to = args[0]

    if not resend_configured():
        sys.exit("Resend not configured — set DUCKFLEET_RESEND_API_KEY and "
                 "DUCKFLEET_RESEND_FROM in .env (see this file's docstring).")

    print(f"Sending via Resend  from={settings.resend_from!r}  to={to!r} ...")
    if "--brief" in sys.argv:
        import asyncio
        from agents.fleet import run_fleet
        result = asyncio.run(run_fleet(replay=True))
        subject = f"Your DuckFleet brief for {date.today():%-d %b %Y}"
        resp = send_brief(subject, render_text(result), render_html(result), to=to)
    else:
        resp = send_brief(
            "A quick note from DuckFleet",
            "Hi from DuckFleet. If you can read this, the plain-text fallback works.\n",
            "<p>Hi from DuckFleet. If you can read this, delivery is working.</p>",
            to=to)
    print("Sent. Resend response:", resp)
    print("Now check the inbox (and spam), or open the mail-tester score.")


if __name__ == "__main__":
    main()
