"""Pure, offline checks for the insights beat: the robots allowlist for article fetch and the
deterministic 'worth a read' selection. The LLM advisor itself needs a model, so it's not
exercised here — these cover the parts that must be correct without any inference."""
from agents.article_fetch import is_allowed
from agents.insights import select_reading


def test_article_allowlist_permits_guides_and_news():
    assert is_allowed("https://www.pointhacks.com.au/earning-points-petrol-stations-guide/")
    assert is_allowed("https://www.pointhacks.com.au/news/qantas-reveals-condor-partner/")


def test_article_allowlist_blocks_disallowed_and_offsite():
    assert not is_allowed("https://www.pointhacks.com.au/qantas/feed/")   # /*/feed/
    assert not is_allowed("https://www.pointhacks.com.au/search/x")       # /search/
    assert not is_allowed("https://www.pointhacks.com.au/wp-login.php")
    assert not is_allowed("https://freepoints.com.au/coles/")             # host not allowlisted
    assert not is_allowed("ftp://www.pointhacks.com.au/guide/")           # scheme


def test_reading_drops_programs_user_does_not_collect():
    items = [
        {"title": "Best KrisFlyer redemptions", "source_url": "https://www.pointhacks.com.au/kf/",
         "categories": ["KrisFlyer"], "program_hint": "velocity"},
    ]
    # user collects only flybuys -> a velocity-hinted post is not relevant
    assert select_reading(items, ["flybuys"]) == []


def test_reading_keeps_matched_program_and_generic_guides():
    items = [
        {"title": "Qantas reveals Condor partner", "source_url": "https://www.pointhacks.com.au/news/condor/",
         "categories": ["Qantas"], "program_hint": "qantas_ff"},
        {"title": "Earning points at petrol stations guide",
         "source_url": "https://www.pointhacks.com.au/petrol-guide/",
         "categories": ["Earning Points"], "program_hint": None},
    ]
    picked = select_reading(items, ["qantas_ff", "flybuys"])
    urls = {p["source_url"] for p in picked}
    assert "https://www.pointhacks.com.au/news/condor/" in urls        # matched program
    assert "https://www.pointhacks.com.au/petrol-guide/" in urls       # generic method guide
    assert all(p.get("why") for p in picked)                           # every pick has a reason
