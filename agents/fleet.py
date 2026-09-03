"""The fleet orchestrator — runtime-agnostic (the coordinator's real logic).

Chains: get offers (live scout OR replay fixtures) -> ToS gate -> deterministic
valuation + spend gate -> worth-it (real Routes, or frozen drive in replay) ->
presenter. Reliable by design: Python owns the maths and the gates; the LLM agents
only normalise (scout) and phrase (presenter). Returns the brief + the audit trail.

A runtime (Cloud Run job, etc.) just calls run_fleet(); it holds no platform code.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.scouts import scout_ozbargain, scout_pointhacks, scout_freepoints
from agents.presenter import presenter
from agents.valuer import compute_stack_value
from agents.worth_it import worth_it_verdict, errand_cost
from guardrails.gates import (gate_tos, gate_spend, gate_preference, record,
                              clear_audit, audit_trail, GateDenied)
from schemas.offer import ActionItem
from config.settings import settings, profile_overrides
from agents import history, seen_store, insights, pointhacks_feed
from agents.economics import RunCost, worth_running

_FIX = Path(__file__).resolve().parent.parent / "fixtures"

# Household's known local stores (live path: merchant -> a representative store).
# In prod this is the stock scout's job; a small directory is honest for the demo.
STORE_DIRECTORY = {
    "coles": (-27.5514, 153.0888),
    "woolworths": (-27.5386, 153.0731),
    "big w": (-27.5514, 153.0888),
    "bigw": (-27.5514, 153.0888),
}


def _store_for(merchant: str):
    m = (merchant or "").lower()
    for name, coords in STORE_DIRECTORY.items():
        if name in m:
            return coords
    return None


_PROGRAM_LABEL = {"qantas_ff": "Qantas", "velocity": "Velocity",
                  "flybuys": "Flybuys", "everyday_rewards": "Everyday Rewards"}


def _skip_reason(o: dict, minutes: float, net: float) -> str:
    """An HONEST reason a value-skip was skipped (not a confabulated 'no points')."""
    program = o.get("program", "none")
    if program not in ("none", None) and program not in settings.programs:
        return f"{_PROGRAM_LABEL.get(program, program)} isn't a program you collect"
    if minutes and net < 0:
        return f"the ~{minutes:.0f}-min round trip costs more than it returns"
    if (o.get("spend_required_aud") or 0) > 0:
        return f"only worth it if you'd already spend ${int(o['spend_required_aud'])} there"
    if not o.get("points_out"):
        return "the deal doesn't state a points amount to value"
    return "no net value after costs"


def _json_array(text: str):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    i, j = text.find("["), text.rfind("]")
    return json.loads(text[i:j + 1]) if i != -1 and j != -1 else json.loads(text)


async def _run_agent(agent, app: str, text: str, cost=None) -> str:
    runner = InMemoryRunner(agent=agent, app_name=app)
    s = await runner.session_service.create_session(app_name=app, user_id="fleet")
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    final = ""
    async for ev in runner.run_async(user_id="fleet", session_id=s.id, new_message=msg):
        um = getattr(ev, "usage_metadata", None)
        if cost is not None and um is not None:
            cost.add_llm(getattr(um, "prompt_token_count", 0) or 0,
                         getattr(um, "candidates_token_count", 0) or 0)
        if ev.is_final_response() and ev.content and ev.content.parts:
            final = "".join(p.text or "" for p in ev.content.parts)
    return final


async def _get_offers(replay: bool, cost=None) -> list[dict]:
    if replay:
        # Default replay set, or override with DUCKFLEET_REPLAY_FIXTURE (path or
        # bare filename under fixtures/) to run/record an alternate deterministic brief.
        fixture = os.environ.get("DUCKFLEET_REPLAY_FIXTURE", "replay_offers.json")
        path = Path(fixture)
        if not path.is_absolute():
            path = _FIX / path
        return json.loads(path.read_text())["offers"]

    # Live path: run every scout in parallel and merge. Each returns a JSON array of
    # Offer-shaped dicts; a scout that errors or emits junk is skipped, never fatal.
    scouts = [
        (scout_ozbargain, "Scout OzBargain for loyalty-points offers now."),
        (scout_pointhacks, "Scout Point Hacks for loyalty-points offers now."),
        (scout_freepoints, "Scout freepoints for loyalty-points offers now."),
    ]
    results = await asyncio.gather(
        *(_run_agent(agent, "fleet-scout", prompt, cost) for agent, prompt in scouts),
        return_exceptions=True,
    )
    scouted: list[dict] = []
    seen: set[str] = set()
    for raw in results:
        if isinstance(raw, Exception):
            continue
        try:
            offers = _json_array(raw)
        except (ValueError, json.JSONDecodeError):
            continue
        for o in offers:
            key = o.get("source_url") or f"{o.get('source')}:{o.get('id')}"
            if key in seen:  # de-dupe the same offer surfaced by two feeds
                continue
            seen.add(key)
            scouted.append(o)
    return scouted


def _value(o: dict, cap: float) -> dict:
    """Deterministic valuation; size a cheap collectible buy to the weekly cap."""
    price = o.get("price_aud") or 0.0
    if o.get("points_out"):
        per = compute_stack_value(price, o["points_out"], o.get("program", "none"), o.get("multipliers"))
        units = max(1, int(cap // price)) if price else 1
        return {"value_aud": round(per["net_value_aud"] * units, 2),
                "cents_per_point": per["cost_cents_per_point"],
                "units": units, "total_points": per["total_points"] * units,
                "spend_aud": round(price * units, 2)}
    return {"value_aud": o.get("est_value_aud", 0.0), "cents_per_point": None,
            "units": 1, "total_points": 0, "spend_aud": price}


def _drive(o: dict, coords=None, cost=None):
    """Drive time to the store, or None (online / store unknown / no home to route from).
    `coords` is the caller-resolved (lat, lng) — the live path passes _store_for() only
    when the active profile has a known home; replay offers carry a frozen `drive` instead
    so no live Routes call is ever needed off the fixture path."""
    if "drive" in o:
        return o["drive"]
    lat, lng = o.get("store_lat"), o.get("store_lng")
    if lat is None and coords is not None:
        lat, lng = coords
    if lat is not None and lng is not None:
        try:
            t = errand_cost(lat, lng)
            if cost is not None:
                cost.add_routes()
            return {"minutes": t["minutes"], "km": t["km"]}
        except Exception:
            return None
    return None


def _signature(a: dict) -> str:
    """Stable content signature for repeat-detection: the SAME recurring promo (e.g. a daily
    Coles gift-card 20x deal) keeps this fixed even as its title/date/id rotate. Deliberately
    coarse — source + program + merchant + category — so 'the same thing every day' collapses
    to one key."""
    return "|".join([str(a.get("source") or ""), str(a.get("program") or ""),
                     (a.get("merchant") or "").strip().lower(), str(a.get("category") or "")])


def _apply_demotions(assessed: list[dict], counts: dict[str, int], threshold: int = 2) -> int:
    """Demote (not hide) offers we've already surfaced `threshold`+ times in the window: they
    drop out of the worth-doing picks into the visible skip list, with an honest reason. Value
    that materially changes still shows next time (the count ages out of the window)."""
    n = 0
    for a in assessed:
        if a["verdict"] in ("do_it", "needs_approval"):
            c = counts.get(_signature(a), 0)
            if c >= threshold:
                a["verdict"] = "skip"
                a["recurring"] = True
                a["reason_note"] = f"recurring offer, already flagged {c}x in the last 7 days"
                n += 1
    return n


def _prefetch_insight_ctx(replay: bool):
    """Fetch the Point Hacks feed + a few allowed article bodies ONCE per run (shared across
    users), for the insights beat. Deterministic + best-effort; ([], {}) in replay or on error."""
    if replay:
        return [], {}
    try:
        items = pointhacks_feed.fetch_offers(limit=15)
        return items, insights.prefetch_texts(items)
    except Exception:  # noqa: BLE001
        return [], {}


async def _assess_and_brief(offers: list[dict], replay: bool, cost: RunCost,
                            home_known: bool = True, seen_key: str | None = None,
                            feed_items: list[dict] | None = None,
                            article_texts: dict[str, str] | None = None) -> dict:
    """Value a scouted offer pool against the ACTIVE profile (global settings) and compose
    the brief. Split out from scouting so the pool can be scouted once and re-valued per
    user (run_fleet_for_profiles enters a profile_overrides() context around this call).

    `home_known` gates the in-store errand costing: only when we actually know the active
    user's home do we resolve a store + call Maps Routes. For onboarded users whose suburb
    isn't geocoded yet it stays False, so we never route a stranger's errand from the
    operator's home (and never spend Routes budget on them) — those offers are assessed on
    value alone. Replay offers carry a frozen drive regardless.
    """
    clear_audit()
    cap = settings.spend_cap_aud_per_week

    assessed: list[dict] = []
    excluded_tos = 0
    for o in offers:
        oid = o.get("id", "?")
        # --- gate 1: ToS (violations never reach the brief) ---
        try:
            gate_tos(o.get("tos_risk", "none"), oid)
        except GateDenied:
            excluded_tos += 1
            continue

        val = _value(o, cap)
        category = o.get("category", "other")

        # --- gate 2: user preferences (a visible skip, not a hidden exclusion) ---
        pref_note = gate_preference(category, val["value_aud"], oid)

        # --- gate 3: spend cap (sizing keeps spend <= cap; over-cap -> approval) ---
        needs_approval = False
        try:
            gate_spend(val["spend_aud"], 0.0)
        except GateDenied:
            needs_approval = True

        if pref_note:  # preference says skip — don't even cost the drive
            verdict, net, trip_cost, tmin, tkm = "skip", val["value_aud"], 0.0, 0.0, 0.0
        else:
            coords = _store_for(o.get("merchant", "")) if home_known else None
            drive = _drive(o, coords, cost)
            if drive:
                wv = worth_it_verdict(val["value_aud"], drive["minutes"], drive["km"])
                verdict, net, trip_cost = wv["verdict"], wv["net_after_trip_aud"], wv["trip_cost_aud"]
                tmin, tkm = drive["minutes"], drive["km"]
            else:  # online / no known store -> no errand cost
                verdict = "do_it" if val["value_aud"] > 0 else "skip"
                net, trip_cost, tmin, tkm = val["value_aud"], 0.0, 0.0, 0.0
            if needs_approval and verdict == "do_it":
                verdict = "needs_approval"

        reason_note = pref_note
        if verdict == "skip" and not reason_note:
            reason_note = _skip_reason(o, tmin, net)

        ref = record("offer_assessed", offer=oid, verdict=verdict, net_value_aud=net)
        assessed.append({
            "id": oid, "merchant": o.get("merchant"), "item": o.get("item"),
            "source": o.get("source"), "source_url": o.get("source_url"),
            "category": category, "reason_note": reason_note,
            "program": o.get("program", "none"), "cents_per_point": val["cents_per_point"],
            "units": val["units"], "spend_aud": val["spend_aud"],
            "total_points": val["total_points"], "offer_value_aud": val["value_aud"],
            "trip_minutes": tmin, "trip_km": tkm, "trip_cost_aud": trip_cost,
            "net_value_aud": net, "verdict": verdict,
            "requires_instore": o.get("requires_instore", False),
            "tos_risk": o.get("tos_risk", "none"), "weekly_cap_aud": cap,
            "stock_state": o.get("stock_state"), "store_phone": o.get("store_phone"),
            "audit_ref": ref,
        })

    # Demote offers we've already sent this user 2+ times in the last week (per-user ledger,
    # best-effort). Then record today's still-worth-doing picks for tomorrow's run.
    if seen_key and not replay:
        _apply_demotions(assessed, seen_store.recent_counts(seen_key))
        seen_store.record_surfaced(
            seen_key, [_signature(a) for a in assessed
                       if a["verdict"] in ("do_it", "needs_approval")])

    # Offers worth doing whose stock is unconfirmed + reachable -> a gated call the human
    # can approve. This is the caller beat surfaced in the brief.
    call_candidates = [
        {"merchant": a["merchant"], "item": a["item"], "phone": a["store_phone"]}
        for a in assessed
        if a["verdict"] in ("do_it", "needs_approval")
        and a.get("stock_state") in ("unknown", "low") and a.get("store_phone")
    ]

    # Insights beat: Point Hacks methods applied to THIS user's programs + today's worth-doing
    # offers (personalised ideas + a "worth a read" footer). Skipped in replay; best-effort.
    ins = {"reading": [], "ideas": []}
    if not replay and feed_items:
        worth_doing = [a for a in assessed if a["verdict"] in ("do_it", "needs_approval")]
        ins = await insights.build(feed_items, settings.programs, worth_doing,
                                   article_texts or {}, cost)

    # append this run's offers to BigQuery history (best-effort; never blocks the brief)
    history_rows = history.record_run(assessed, "replay" if replay else "live")

    brief_raw = await _run_agent(presenter, "fleet-present",
                                 "Compose the morning brief:\n" + json.dumps(assessed), cost)
    items = [ActionItem(**x) for x in _json_array(brief_raw)]
    items.sort(key=lambda a: a.rank)

    # Self-governance: did this run earn its compute? (value surfaced vs cost spent)
    value = sum((a["net_value_aud"] or 0) for a in assessed
                if a["verdict"] in ("do_it", "needs_approval"))
    econ = worth_running(value, cost.total_aud)
    record("run_economics", **econ, **cost.breakdown())

    return {"brief": items, "assessed": assessed, "audit": audit_trail(),
            "excluded_tos": excluded_tos, "n_candidates": len(offers),
            "history_rows": history_rows, "mode": "replay" if replay else "live",
            "call_candidates": call_candidates,
            "reading": ins["reading"], "ideas": ins["ideas"],
            "economics": {**econ, "breakdown": cost.breakdown()}}


async def run_fleet(replay: bool = True) -> dict:
    """Run the whole fleet once for the ACTIVE profile (env/profile.json/Firestore default).
    Scout the offer pool, then value + brief it. Unchanged public contract — every existing
    caller (nightly job, sample-brief page, dev scripts) keeps working."""
    cost = RunCost()
    offers = await _get_offers(replay, cost)
    feed_items, texts = _prefetch_insight_ctx(replay)
    seen_key = settings.profile_id or None
    return await _assess_and_brief(offers, replay, cost, home_known=True, seen_key=seen_key,
                                   feed_items=feed_items, article_texts=texts)


def _recipient(profile: dict) -> str | None:
    """The email a profile's brief goes to: its notify_email, else the doc id when that id is
    the user's verified email (hosted onboarding keys every profile on it)."""
    pid = profile.get("profile_id")
    return profile.get("notify_email") or (pid if pid and "@" in pid else None)


def _dedupe_by_recipient(profiles: list[dict]) -> list[dict]:
    """One brief per inbox. When several profiles resolve to the same recipient (e.g. the seed
    `default` doc alongside a user's own email-keyed profile), keep the most specific: a real
    onboarded profile (email id, own notify_email) wins over the `default` seed. Profiles with
    no resolvable recipient are kept as-is (the runtime logs them as unsendable)."""
    def score(p: dict) -> int:
        pid = p.get("profile_id") or ""
        return (2 if p.get("notify_email") else 0) + (1 if pid != "default" and "@" in pid else 0)

    best: dict[str, dict] = {}
    passthrough: list[dict] = []
    for p in profiles:
        to = _recipient(p)
        if not to:
            passthrough.append(p)
            continue
        if to not in best or score(p) > score(best[to]):
            best[to] = p
    return list(best.values()) + passthrough


async def run_fleet_for_profiles(profiles: list[dict], replay: bool = False) -> dict:
    """Multi-user nightly: scout the offer pool ONCE, then value + brief it per profile.

    The expensive, user-independent stage (scouting the feeds) runs a single time; the cheap
    deterministic stage (valuation against each user's programs / spend cap / preferences)
    fans out. Each profile is valued inside a profile_overrides() context so the gates read
    THAT user's settings, then restored. Sequential by design — settings is a process-wide
    singleton, so profiles are never valued concurrently.

    Returns {n_offers, scout_cost, runs:[{profile_id, notify_email, result}, ...]}. Emailing
    is the caller's job (the runtime adapter), so this stays runtime-agnostic and testable.
    """
    scout_cost = RunCost()
    offers = await _get_offers(replay, scout_cost)  # shared, read-only across users
    feed_items, texts = _prefetch_insight_ctx(replay)  # shared insight context across users

    deduped = _dedupe_by_recipient(profiles)
    runs: list[dict] = []
    for profile in deduped:
        # A user whose suburb isn't geocoded yet has no home to route errands from.
        home_known = profile.get("home_lat") is not None and profile.get("home_lng") is not None
        with profile_overrides(profile):
            result = await _assess_and_brief(offers, replay, RunCost(), home_known=home_known,
                                             seen_key=profile.get("profile_id"),
                                             feed_items=feed_items, article_texts=texts)
        runs.append({"profile_id": profile.get("profile_id"),
                     "recipient": _recipient(profile),
                     "notify_email": profile.get("notify_email"), "result": result})
    return {"n_offers": len(offers), "n_profiles_in": len(profiles),
            "n_recipients": len(runs), "scout_cost": scout_cost.breakdown(), "runs": runs}
