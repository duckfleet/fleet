"""Deterministic parse checks for the WordPress-RSS scouts (Point Hacks / freepoints).

Pure, offline, no network — feeds a fixed RSS blob to agents/wp_rss.parse_feed and
asserts the raw item contract the LLM scout relies on. Runs in the same local suite
as the red-team evals.
"""
from agents import wp_rss

SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>freepoints</title>
  <item>
    <title>3,000 Velocity points and 15 bottles of wine for $89 at Virgin Wines</title>
    <link>https://freepoints.com.au/virgin-wines-offer-aug-2026/</link>
    <guid>https://freepoints.com.au/virgin-wines-offer-aug-2026/</guid>
    <category>Velocity</category><category>Virgin Wines</category>
    <description><![CDATA[<p>Ends 30 Sep 2026. Grab 3,000 Velocity points.</p>]]></description>
    <pubDate>Sun, 23 Aug 2026 00:00:00 +0000</pubDate>
  </item>
  <item>
    <title>20x Flybuys points on gift cards at Coles</title>
    <link>https://freepoints.com.au/coles-2-sep-2026/</link>
    <guid>https://freepoints.com.au/coles-2-sep-2026/</guid>
    <category>Flybuys</category><category>Coles</category>
    <description>In-store only, 2-8 Sep 2026.</description>
    <pubDate>Wed, 26 Aug 2026 00:00:00 +0000</pubDate>
  </item>
</channel></rss>"""


def test_parse_sets_source_and_id():
    items = wp_rss.parse_feed(SAMPLE, "freepoints")
    assert len(items) == 2
    assert all(i["source"] == "freepoints" for i in items)
    assert items[0]["id"] == "virgin-wines-offer-aug-2026"


def test_program_hint_from_categories():
    items = wp_rss.parse_feed(SAMPLE, "freepoints")
    assert items[0]["program_hint"] == "velocity"
    assert items[1]["program_hint"] == "flybuys"  # Coles/Flybuys category


def test_price_parsed_but_multiplier_is_not_a_price():
    items = wp_rss.parse_feed(SAMPLE, "freepoints")
    assert items[0]["price_aud"] == 89.0            # "$89" -> price
    assert items[1]["price_aud"] is None            # "20x points" is not a dollar price


def test_summary_is_stripped_of_html():
    items = wp_rss.parse_feed(SAMPLE, "freepoints")
    assert "<p>" not in items[0]["summary"]
    assert "3,000 Velocity points" in items[0]["summary"]


def test_empty_channel_is_safe():
    assert wp_rss.parse_feed(b"<rss><channel></channel></rss>", "pointhacks") == []
