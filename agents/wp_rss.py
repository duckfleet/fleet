"""Deterministic WordPress RSS fetch + parse. Shared by the Point Hacks and
freepoints scouts. No LLM, no GCP — pure and unit-testable.

Both sites are standard WordPress RSS 2.0 feeds: each <item> carries title, link,
one or more <category> tags, pubDate and a description (post excerpt). Unlike the
OzBargain feed there is no structured price/points/expiry metadata, so we surface
the raw text fields and let the LLM scout read points/spend it can *see stated*;
we never guess those numbers here (principle: LLM finds, Python computes).

Etiquette (mirrors agents/ozbargain_feed.py): we send an identifying UA, fetch ONE
feed per run, follow no outbound links, and only ever hit a path each site's
robots.txt allows for `*` — the caller passes that URL (see pointhacks_feed.py /
freepoints_feed.py for the per-site robots note).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

USER_AGENT = ("DuckFleetBot/0.1 (+https://duckfleet.dev; loyalty-points research; "
             "contact duckfleet.dev@gmail.com)")

# Program name / earning-merchant -> the loyalty scheme a post is about. Scanned
# over the item's categories + title (categories are the strong signal on these
# sites). A hint only; the valuer LLM confirms.
PROGRAM_KEYWORDS = {
    "qantas": "qantas_ff",
    "frequent flyer": "qantas_ff",
    "velocity": "velocity",
    "virgin australia": "velocity",
    "virgin money": "velocity",
    "flybuys": "flybuys",
    "coles": "flybuys",                 # Coles earns Flybuys
    "everyday rewards": "everyday_rewards",
    "woolworths": "everyday_rewards",   # Woolworths/BigW earn Everyday Rewards
    "big w": "everyday_rewards",
    "bigw": "everyday_rewards",
}

_PRICE_RE = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _program_hint(title: str, categories: list[str]) -> str | None:
    hay = " ".join([title or "", *(categories or [])]).lower()
    for kw, prog in PROGRAM_KEYWORDS.items():
        if kw in hay:
            return prog
    return None


def _parse_price_aud(text: str) -> float | None:
    m = _PRICE_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _clean(html: str, limit: int = 500) -> str:
    """Strip tags/entities-ish noise from a post excerpt so the LLM reads plain text."""
    text = _TAG_RE.sub(" ", html or "")
    text = text.replace("&#8217;", "'").replace("&#8211;", "-").replace("&amp;", "&")
    text = _WS_RE.sub(" ", text).strip()
    return text[:limit]


def parse_feed(xml_bytes: bytes, source: str) -> list[dict]:
    """Parse a WordPress RSS feed into raw item dicts. Pure function — unit-testable.

    `source` labels the origin ("pointhacks" / "freepoints") and becomes each dict's
    source, so the scout can pass it straight through to the Offer schema.
    """
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        return []
    items: list[dict] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        categories = [c.text.strip() for c in item.findall("category") if c.text]
        summary = _clean(item.findtext("description") or "")
        guid = (item.findtext("guid") or link).strip()

        items.append({
            "id": guid.rstrip("/").rsplit("/", 1)[-1] or guid,
            "source": source,
            "title": title,
            "source_url": link,
            "categories": categories,
            "summary": summary,
            "price_aud": _parse_price_aud(title) or _parse_price_aud(summary),
            "pubdate": (item.findtext("pubDate") or "").strip() or None,
            "program_hint": _program_hint(title, categories),
        })
    return items


def fetch_feed(url: str, source: str, limit: int = 20, timeout: float = 15.0) -> list[dict]:
    """Fetch + parse one WordPress RSS feed. Returns at most `limit` items."""
    resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout,
                     follow_redirects=True)
    resp.raise_for_status()
    return parse_feed(resp.content, source)[:limit]
