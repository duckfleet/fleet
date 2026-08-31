"""Deterministic freepoints feed fetch. Thin wrapper over agents/wp_rss.py.

freepoints (freepoints.com.au) is an Australian loyalty-points *deals aggregator* —
Flybuys / Everyday Rewards / Qantas / Velocity offers at Coles, Woolworths, BigW and
partners. Very close in shape to the OzBargain feed, but points-scheme-native, so it
complements it well. The scout tool (agents/scouts.py) wraps this; the LLM normalises
the raw items into the Offer schema.

robots.txt note: the site only disallows `/wp-admin/` for `*` (no feed restriction),
so the root `/feed/` is fair game. We fetch one feed per run with an identifying UA.
"""
from __future__ import annotations

from agents import wp_rss

FREEPOINTS_FEED = "https://freepoints.com.au/feed/"


def fetch_offers(limit: int = 20, timeout: float = 15.0) -> list[dict]:
    """Fetch the live freepoints RSS feed and parse it into raw item dicts."""
    return wp_rss.fetch_feed(FREEPOINTS_FEED, "freepoints", limit=limit, timeout=timeout)
