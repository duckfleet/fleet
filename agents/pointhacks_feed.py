"""Deterministic Point Hacks feed fetch. Thin wrapper over agents/wp_rss.py.

Point Hacks (pointhacks.com.au) is an Australian points/miles blog: card sign-up
bonuses, transfer bonuses, and program promos — the *earning* angle OzBargain's
retail feed mostly misses. The scout tool (agents/scouts.py) wraps this; the LLM
normalises the raw items into the Offer schema.

robots.txt note: under `User-agent: *` the site disallows `/*/feed/`, which matches
the per-program feeds (e.g. /qantas/feed/) but NOT the root `/feed/` (no path
segment before it). So we only ever fetch the root feed. (The site additionally
grants named AI crawlers full access, but we crawl as our own DuckFleetBot and
honour the `*` rules.)
"""
from __future__ import annotations

from agents import wp_rss

POINTHACKS_FEED = "https://www.pointhacks.com.au/feed/"


def fetch_offers(limit: int = 20, timeout: float = 15.0) -> list[dict]:
    """Fetch the live Point Hacks root RSS feed and parse it into raw item dicts."""
    return wp_rss.fetch_feed(POINTHACKS_FEED, "pointhacks", limit=limit, timeout=timeout)
