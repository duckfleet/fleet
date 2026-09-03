"""Per-user 'already surfaced' ledger — so we don't email the same recurring offer every
day. Best-effort Firestore, exactly like agents/profile_store.py: a failure is logged and
swallowed, so it can never break a run (no ledger simply means nothing gets demoted).

One doc per profile in `duckfleet_seen`, mapping an offer content-signature -> the recent
dates we surfaced it as worth-doing. The fleet reads counts before composing the brief
(to demote things flagged 2+ times in the last week) and records today's picks after.
Dates older than the window are trimmed on write so a demoted offer can resurface later.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from config.settings import settings

log = logging.getLogger("duckfleet.seen_store")

_COLLECTION = "duckfleet_seen"
_WINDOW_DAYS = 7


def _client():
    from google.cloud import firestore
    return firestore.Client(project=settings.project_id)


def _within(dates: list[str], days: int) -> list[str]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return [d for d in dates if d >= cutoff]


def recent_counts(profile_key: str, days: int = _WINDOW_DAYS) -> dict[str, int]:
    """signature -> how many distinct prior days we surfaced it (within the window)."""
    if not profile_key:
        return {}
    try:
        snap = _client().collection(_COLLECTION).document(profile_key).get()
        doc = snap.to_dict() if snap.exists else None
        if not doc:
            return {}
        return {sig: len(_within(dates or [], days)) for sig, dates in doc.items()}
    except Exception as e:  # noqa: BLE001 — never let the ledger break a run
        log.warning("seen_store read failed (%s); nothing demoted this run", e)
        return {}


def record_surfaced(profile_key: str, signatures: list[str], days: int = _WINDOW_DAYS) -> bool:
    """Append today to each surfaced signature (one entry per day), trimmed to the window."""
    if not profile_key or not signatures:
        return False
    today = date.today().isoformat()
    try:
        ref = _client().collection(_COLLECTION).document(profile_key)
        snap = ref.get()
        doc = (snap.to_dict() if snap.exists else None) or {}
        for sig in set(signatures):
            dates = set(_within(doc.get(sig, []) or [], days))
            dates.add(today)
            doc[sig] = sorted(dates)
        ref.set(doc)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("seen_store write failed (%s); recurring offers not tracked this run", e)
        return False
