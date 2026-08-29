#!/usr/bin/env python
"""Run the operator new-user digest against live Firestore, for local testing.

    ./.venv/bin/python scripts/dev_digest.py          # last 24h
    ./.venv/bin/python scripts/dev_digest.py 168      # last 7 days (to catch recent signups)

Loads .env (project id + email creds) and needs GCP access (your duckfleet ADC / gcloud
config). Reads the duckfleet_interest lead list, prints who's new, and emails the digest ONLY
if there are new users in the window, to DUCKFLEET_ADMIN_EMAIL (or NOTIFY_EMAIL). Prints the
status dict either way, so a quiet window shows `admin_digest_quiet` and sends nothing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if (ROOT / ".env").exists():
    for _l in (ROOT / ".env").read_text().splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from agents.admin_digest import run_admin_digest, new_signups_since  # noqa: E402


def main() -> None:
    hours = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 24
    rows = new_signups_since(hours)
    print(f"new signups in the last {hours}h: {len(rows)}")
    for r in rows:
        print(f"  - {r.get('email')}   first seen {r.get('first_seen')}")
    print("status:", run_admin_digest(hours))


if __name__ == "__main__":
    main()
