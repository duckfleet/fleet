"""Deterministic single-article fetch + readable-text extract. No LLM here — this only
pulls the page text so the insights advisor (agents/insights.py) can reason over it.

robots.txt: Point Hacks allows article/guide/news pages for `*` (it disallows only
wp-admin, wp-login, /search/, the cross-auth callback, and /*/feed/). We enforce that
allowlist here so we can never fetch a disallowed path, send an identifying UA, and cap
how much text we return (synthesis needs the gist, not the whole page — and we never
reproduce it, only synthesise transformatively).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from agents.wp_rss import USER_AGENT

_ALLOWED_HOSTS = {"www.pointhacks.com.au", "pointhacks.com.au"}
# Path prefixes disallowed for `*` in Point Hacks robots.txt.
_DISALLOWED_PREFIXES = ("/wp/wp-admin", "/wp-login.php", "/search/", "/callback-cross-auth")

_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def is_allowed(url: str) -> bool:
    """True only for a Point Hacks content page we may crawl under robots.txt for `*`
    (host on the allowlist, path not disallowed and not a feed)."""
    try:
        u = urlparse(url)
    except ValueError:
        return False
    if u.scheme not in ("http", "https") or (u.hostname or "") not in _ALLOWED_HOSTS:
        return False
    path = u.path or "/"
    if path.rstrip("/").endswith("/feed") or "/feed/" in path:  # /*/feed/
        return False
    return not any(path.startswith(p) for p in _DISALLOWED_PREFIXES)


def _readable(html: str, limit: int) -> str:
    """Pull the article body: drop scripts/styles, keep <p> text, collapse whitespace."""
    html = _SCRIPT_RE.sub(" ", html)
    paras = [_TAG_RE.sub(" ", m.group(1)) for m in _P_RE.finditer(html)]
    text = _WS_RE.sub(" ", " ".join(paras)).strip()
    text = (text.replace("&#8217;", "'").replace("&#8211;", "-")
                .replace("&amp;", "&").replace("&nbsp;", " ").replace("&#8230;", "..."))
    return text[:limit]


def fetch_readable(url: str, limit: int = 4000, timeout: float = 15.0) -> str | None:
    """Fetch a permitted Point Hacks page and return its readable body text, or None if the
    URL isn't allowed or the fetch fails (best-effort — an insight is never worth a crash)."""
    if not is_allowed(url):
        return None
    try:
        resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout,
                         follow_redirects=True)
        resp.raise_for_status()
        text = _readable(resp.text, limit)
        return text or None
    except Exception:  # noqa: BLE001
        return None
