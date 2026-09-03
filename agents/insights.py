"""Insights: turn Point Hacks know-how into help for THIS user — not a re-hash of their
articles, but their methods applied to the user's programs + today's live offers.

Two layers (both runtime-agnostic; the IP):
  - select_reading()  — deterministic, no LLM. Picks recent Point Hacks posts relevant to the
    user's programs for a "Worth a read" footer, with a reason WE derive (from the match), and
    a link out to Point Hacks (attribution + traffic back to them).
  - advise()          — STRONG-tier LLM. Reads a few allowed article bodies and proposes short,
    personalised ideas ("Point Hacks found a fuel method; you collect Flybuys and there's a live
    20x gift-card offer, so this combination could earn more"). Honesty is enforced in the
    prompt: it may only quote a number that OUR system already computed for a real offer, never
    one derived from the article; article methods stay qualitative. Best-effort: any failure
    yields no ideas rather than breaking the brief.
"""
from __future__ import annotations

from google.adk.agents import Agent

from agents import model_factory, article_fetch

ALL_PROGRAMS = ["qantas_ff", "velocity", "flybuys", "everyday_rewards"]
_LABEL = {"qantas_ff": "Qantas", "velocity": "Velocity",
          "flybuys": "Flybuys", "everyday_rewards": "Everyday Rewards"}
# General earning-method cues that make a program-agnostic guide worth surfacing.
_GENERIC = ("guide", "earn", "points", "fuel", "petrol", "gift card", "transfer",
            "bonus", "credit card", "supermarket")


def _why(matched: str | None, programs: list[str]) -> str:
    if matched:
        return f"Relevant to your {_LABEL.get(matched, matched)} collecting."
    labels = [_LABEL[p] for p in programs if p in _LABEL]
    who = " / ".join(labels[:2]) if labels else "your programs"
    return f"A general earning method that could apply to {who}."


def select_reading(items: list[dict], programs: list[str], limit: int = 3) -> list[dict]:
    """Pick recent Point Hacks posts worth reading for a user on `programs`. Program-specific
    posts for programs they DON'T collect are dropped; program-agnostic method guides are kept."""
    progs = set(programs or [])
    out: list[dict] = []
    for it in items:
        hint = it.get("program_hint")
        hay = ((it.get("title") or "") + " " + " ".join(it.get("categories") or [])).lower()
        if hint in progs:
            matched = hint
        elif hint is None and any(k in hay for k in _GENERIC):
            matched = None
        else:
            continue  # a program the user doesn't collect
        out.append({"title": it.get("title"), "source_url": it.get("source_url"),
                    "program": matched, "why": _why(matched, programs)})
        if len(out) >= limit:
            break
    return out


def prefetch_texts(items: list[dict], max_articles: int = 3) -> dict[str, str]:
    """Deterministically fetch the readable body of the top program-relevant posts ONCE per run
    (shared across users). Robots-allowlisted + best-effort inside article_fetch."""
    reading = select_reading(items, ALL_PROGRAMS, limit=max_articles)
    texts: dict[str, str] = {}
    for r in reading:
        url = r.get("source_url")
        if url and url not in texts:
            body = article_fetch.fetch_readable(url)
            if body:
                texts[url] = body
    return texts


ADVISOR_INSTRUCTION = """You are DuckFleet's points advisor. You get a JSON payload with:
- programs: the loyalty programs THIS user collects.
- offers: today's worth-doing offers, each with numbers OUR system already computed
  (points, cents_per_point) — these numbers are trustworthy.
- articles: the text of a few Point Hacks posts (earning methods / news).

Produce AT MOST 3 short, personalised ideas that combine an article's insight with this user's
programs and today's offers to help them earn more or earn smarter.

RULES (strict):
- Personalise: only suggest things relevant to the user's programs. Skip articles that aren't.
- Numbers: you may ONLY state a points figure or cents-per-point if it appears verbatim in an
  offer's fields. NEVER calculate or estimate a number from an article. For article-derived
  methods, stay qualitative ("could improve your earn", "worth exploring").
- Do NOT reproduce the article. One or two sentences, your own words, genuinely useful.
- Always include that article's source_url so the user can read the original.
- Plain and honest: no hype, no emoji, no em-dashes.

Output ONLY a JSON array (no prose, no markdown fences) of objects:
  {"headline": "<= 60 chars", "idea": "1-2 sentences", "source_url": "the article url"}
If nothing is genuinely useful for this user, output []."""

advisor = Agent(
    name="advisor",
    model=model_factory.strong(),
    instruction=ADVISOR_INSTRUCTION,
    output_key="ideas",
)


async def advise(articles: list[dict], programs: list[str], worth_doing: list[dict],
                 cost=None) -> list[dict]:
    """Run the advisor over pre-fetched article bodies. `articles` = [{title,url,text}].
    Best-effort: returns [] on empty input or any failure."""
    if not articles:
        return []
    import json
    from agents.fleet import _run_agent, _json_array  # lazy: avoid import cycle
    payload = {
        "programs": programs,
        "offers": [{"id": a.get("id"), "merchant": a.get("merchant"), "item": a.get("item"),
                    "program": a.get("program"), "points": a.get("total_points"),
                    "cents_per_point": a.get("cents_per_point")} for a in worth_doing],
        "articles": articles,
    }
    try:
        raw = await _run_agent(advisor, "fleet-advisor",
                               "Suggest ideas from this payload:\n" + json.dumps(payload), cost)
        ideas = _json_array(raw)
        return [i for i in ideas if isinstance(i, dict) and i.get("source_url")][:3]
    except Exception:  # noqa: BLE001 — an idea is never worth failing the brief
        return []


async def build(feed_items: list[dict], programs: list[str], worth_doing: list[dict],
                article_texts: dict[str, str], cost=None) -> dict:
    """Assemble a user's insights: the reading footer (deterministic) + advisor ideas (LLM over
    the shared pre-fetched article bodies)."""
    reading = select_reading(feed_items, programs)
    articles = [{"title": r["title"], "url": r["source_url"], "text": article_texts[r["source_url"]]}
                for r in reading if r.get("source_url") in article_texts]
    ideas = await advise(articles, programs, worth_doing, cost)
    return {"reading": reading, "ideas": ideas}
