"""Firestore profile store — the shared state between the hosted onboarding surface
and the headless nightly fleet.

The onboarding web service (runtimes/gcp_adk/onboard_service.py) WRITES a profile here;
the fleet READS it at startup (config/settings.py). This is what makes onboarding feel
like a product instead of a local file edit: chat on a hosted page → Firestore → tonight's
run picks it up. No redeploy, no file drop.

Best-effort and runtime-agnostic in spirit (mirrors agents/history.py): a Firestore
failure is logged and swallowed so it can never break a run — the fleet falls back to
profile.json / env defaults. Collection: `duckfleet_profiles`, one doc per profile id
(the demo uses a single id, e.g. "default").
"""
from __future__ import annotations

import logging

from config.settings import settings

log = logging.getLogger("duckfleet.profile_store")

_COLLECTION = "duckfleet_profiles"


def _client():
    from google.cloud import firestore
    return firestore.Client(project=settings.project_id)


def write_profile(profile: dict, profile_id: str = "default") -> bool:
    """Persist a profile dict (Profile.model_dump()) to Firestore. Returns True on success."""
    try:
        doc = {k: v for k, v in profile.items() if v not in (None, [], {})}
        _client().collection(_COLLECTION).document(profile_id).set(doc)
        log.info("profile written to firestore: %s/%s", _COLLECTION, profile_id)
        return True
    except Exception as e:  # noqa: BLE001 — never let a sink failure surface
        log.warning("firestore write failed (%s); profile not persisted remotely", e)
        return False


def read_profile(profile_id: str = "default") -> dict | None:
    """Load a profile dict from Firestore, or None if absent/unreachable."""
    try:
        snap = _client().collection(_COLLECTION).document(profile_id).get()
        return snap.to_dict() if snap.exists else None
    except Exception as e:  # noqa: BLE001
        log.warning("firestore read failed (%s); falling back to local profile", e)
        return None


def list_profiles() -> list[dict]:
    """Every saved profile (one per onboarded user), each dict carrying its doc id as
    `profile_id`. Powers the multi-user nightly fan-out. Best-effort: returns [] if
    Firestore is unreachable, so an empty/failed list simply falls back to the single
    default run — a new user tomorrow is picked up with no redeploy."""
    try:
        out: list[dict] = []
        for snap in _client().collection(_COLLECTION).stream():
            rec = snap.to_dict() or {}
            rec["profile_id"] = snap.id
            out.append(rec)
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("firestore list failed (%s); no per-user profiles this run", e)
        return []
