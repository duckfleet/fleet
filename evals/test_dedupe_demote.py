"""Pure, offline checks for the multi-user fan-out helpers: recipient de-dup (one brief per
inbox) and recurring-offer demotion (don't re-send the same promo daily). No network."""
from agents.fleet import _dedupe_by_recipient, _recipient, _signature, _apply_demotions


def test_dedupe_prefers_real_profile_over_default_seed():
    profs = [
        {"profile_id": "default", "notify_email": "u@x.com"},
        {"profile_id": "u@x.com", "notify_email": "u@x.com"},
        {"profile_id": "alice@x.com", "notify_email": "alice@x.com"},
    ]
    out = _dedupe_by_recipient(profs)
    kept = {p["profile_id"] for p in out}
    assert kept == {"u@x.com", "alice@x.com"}  # one brief per inbox; seed 'default' dropped


def test_recipient_falls_back_to_email_keyed_id():
    assert _recipient({"profile_id": "bob@x.com"}) == "bob@x.com"
    assert _recipient({"profile_id": "default", "notify_email": "n@x.com"}) == "n@x.com"
    assert _recipient({"profile_id": "default"}) is None


def test_signature_stable_across_rotating_title_and_case():
    a = {"source": "freepoints", "program": "flybuys", "merchant": "Coles", "category": "shopping"}
    b = {"source": "freepoints", "program": "flybuys", "merchant": "coles ", "category": "shopping"}
    assert _signature(a) == _signature(b)


def test_demote_after_two_prior_sends_only():
    picks = [
        {"source": "freepoints", "program": "flybuys", "merchant": "Coles",
         "category": "shopping", "verdict": "do_it"},
        {"source": "pointhacks", "program": "qantas_ff", "merchant": "Amex",
         "category": "credit_card", "verdict": "needs_approval"},
    ]
    counts = {_signature(picks[0]): 2}  # the Coles promo seen twice already; Amex never
    demoted = _apply_demotions(picks, counts, threshold=2)
    assert demoted == 1
    assert picks[0]["verdict"] == "skip" and picks[0]["recurring"] is True
    assert picks[1]["verdict"] == "needs_approval"  # untouched


def test_demote_leaves_once_seen_alone():
    picks = [{"source": "freepoints", "program": "flybuys", "merchant": "Coles",
              "category": "shopping", "verdict": "do_it"}]
    assert _apply_demotions(picks, {_signature(picks[0]): 1}, threshold=2) == 0
    assert picks[0]["verdict"] == "do_it"  # seen once -> still shown
