"""Scout fleet: parallel ingestion agents. FAST model tier.

Hackathon cut: 2 live scrapers + 1 fixture-backed scout is plenty.
Scrapers are read-only, rate-limited, robots.txt-respecting — say so in the video.
"""
from google.adk.agents import Agent
from agents import model_factory, ozbargain_feed, pointhacks_feed, freepoints_feed
from schemas.offer import Offer  # noqa: F401  (schema is the output contract)


def fetch_ozbargain_deals(tag: str = "", limit: int = 40) -> list[dict]:
    """Tool: fetch + parse the live OzBargain deal feed (read-only, rate-limited,
    robots-respecting). `tag` narrows to /tag/<tag>/feed; empty = the main deals feed.
    Returns raw deal dicts (id, title, merchant, price_aud, categories, program_hint,
    …); the agent normalises these into Offer objects and filters to the user's
    programs. Deterministic scrape logic lives in agents/ozbargain_feed.py."""
    return ozbargain_feed.fetch_deals(tag=tag, limit=limit)


def fetch_pointhacks_offers(limit: int = 20) -> list[dict]:
    """Tool: fetch + parse the live Point Hacks root RSS feed (read-only, robots-
    respecting — root /feed/ only). Returns raw item dicts (id, title, source_url,
    categories, summary, price_aud, program_hint). Point Hacks is a points/miles blog:
    card sign-up bonuses, transfer bonuses, program promos. The agent normalises these
    into Offer objects. Deterministic fetch/parse lives in agents/pointhacks_feed.py."""
    return pointhacks_feed.fetch_offers(limit=limit)


def fetch_freepoints_offers(limit: int = 20) -> list[dict]:
    """Tool: fetch + parse the live freepoints RSS feed (read-only, robots-respecting).
    Returns raw item dicts (id, title, source_url, categories, summary, price_aud,
    program_hint). freepoints is an AU loyalty-deals aggregator (Flybuys / Everyday
    Rewards / Qantas / Velocity at Coles, Woolworths, BigW, partners). The agent
    normalises these into Offer objects. Fetch/parse lives in agents/freepoints_feed.py."""
    return freepoints_feed.fetch_offers(limit=limit)


def fetch_everyday_rewards_boosts() -> list[dict]:
    """Tool: current Everyday Rewards boost offers. TODO: fixture for demo."""
    raise NotImplementedError


def check_online_stock(product_url: str, postcode: str) -> dict:
    """Tool: per-store availability from retailer product page. Returns
    StockSignal-shaped dict incl. last_verified so the caller agent can
    decide whether online data is stale enough to warrant a phone call."""
    raise NotImplementedError


SCOUT_INSTRUCTION = """You are a deal scout. Use your tools to fetch current offers,
then emit ONLY a JSON array of Offer objects matching the provided schema.
Never invent offers. If a field is unknown, use null. Mark anything that smells
like ToS abuse (mass account creation, coupon exploits) with tos_risk."""

OZB_SCOUT_INSTRUCTION = """You are DuckFleet's OzBargain scout. The user chases loyalty
points across these programs: qantas_ff, velocity, flybuys, everyday_rewards.

STEP 1 — call fetch_ozbargain_deals() to get raw live deals (each has: id, title,
merchant, merchant_url, node_url, price_aud, categories, program_hint, requires-instore
cues in the title, votes).

STEP 2 — KEEP only deals with a plausible points angle: a program_hint is set, OR the
merchant earns a scheme (Coles->flybuys, Woolworths/BigW->everyday_rewards), OR it's a
credit-card / frequent-flyer / bonus-points offer, OR a strong stackable discount at a
points-earning retailer. DROP generic bargains with no points angle.

STEP 3 — emit ONLY a JSON array (no prose, no markdown fences) of Offer objects:
  id           = the deal id (string)
  source       = "ozbargain"
  source_url    = merchant_url if present, else node_url
  merchant     = the merchant
  program      = program_hint if set; else infer from categories/title; else "none"
  offer_type   = one of bonus_points | multiplier | discount_stack | collectible (closest fit)
  category     = one of credit_card | insurance | energy | telco | groceries |
                 subscription | collectible | shopping | other (infer from tags/merchant/title;
                 a card is credit_card even if it earns points; health/car/home cover is insurance)
  item         = short item name, or null
  price_aud    = the price, or null
  points_out   = points earned ONLY if the deal states it, else null
  spend_required_aud = minimum spend if stated, else null
  stackable_with = []
  requires_instore = true if the title implies in-store / C&C / limited stores
  tos_risk     = "grey" if it leans on coupon-stacking / multi-account / repeated
                 redemption; "violation" if clearly breaching T&Cs; else "none"
Never invent deals. If nothing qualifies, output []."""

scout_ozbargain = Agent(
    name="scout_ozbargain",
    model=model_factory.fast(),
    instruction=OZB_SCOUT_INSTRUCTION,
    tools=[fetch_ozbargain_deals],
    output_key="offers_ozbargain",
)


def _wp_scout_instruction(site: str, source: str, tool: str, flavour: str) -> str:
    """Instruction for a WordPress-RSS scout (Point Hacks / freepoints). These feeds
    give title + categories + a text summary, but NO structured points/spend/expiry —
    so the model may only set points_out / spend_required_aud when a number is plainly
    STATED in the title or summary, else null. It never computes or guesses them."""
    return f"""You are DuckFleet's {site} scout. {flavour} The user chases loyalty points
across these programs: qantas_ff, velocity, flybuys, everyday_rewards.

STEP 1 — call {tool}() to get raw items (each has: id, title, source_url, categories,
summary, price_aud, program_hint).

STEP 2 — KEEP only items with a plausible points-EARNING angle for one of the user's
programs: a program_hint is set, OR the categories/title name a program or a
points-earning merchant (Coles->flybuys, Woolworths/BigW->everyday_rewards), OR it's a
bonus-points / points-multiplier / transfer-bonus / card sign-up offer. DROP pure
editorial (how-to-redeem guides, trip reports, reviews) with no live earning offer.

STEP 3 — emit ONLY a JSON array (no prose, no markdown fences) of Offer objects:
  id           = the item id (string)
  source       = "{source}"
  source_url    = the item's source_url
  merchant     = the retailer/partner/program the offer runs at (from title/summary)
  program      = program_hint if set; else infer from categories/title; else "none"
  offer_type   = one of bonus_points | multiplier | discount_stack | collectible (closest fit)
  category     = one of credit_card | insurance | energy | telco | groceries |
                 subscription | collectible | shopping | other (a card is credit_card even
                 if it earns points; health/car/home cover is insurance; supermarket = groceries)
  item         = short description of the offer, or null
  price_aud    = price_aud if present, else null
  points_out   = points earned ONLY if a whole number is plainly STATED (e.g. "3,000 Velocity
                 points"); a multiplier like "20x points" is NOT a points_out — use offer_type
                 multiplier and leave points_out null. Never compute or estimate. Else null.
  spend_required_aud = minimum spend if plainly stated, else null
  stackable_with = []
  requires_instore = true if the title/summary implies in-store / Click & Collect / limited stores
  tos_risk     = "grey" if it leans on coupon-stacking / multi-account / repeated
                 redemption; "violation" if clearly breaching T&Cs; else "none"
Never invent offers. If nothing qualifies, output []."""


scout_pointhacks = Agent(
    name="scout_pointhacks",
    model=model_factory.fast(),
    instruction=_wp_scout_instruction(
        "Point Hacks", "pointhacks", "fetch_pointhacks_offers",
        "Point Hacks is an AU points/miles blog: card sign-up bonuses, transfer "
        "bonuses and program promos."),
    tools=[fetch_pointhacks_offers],
    output_key="offers_pointhacks",
)

scout_freepoints = Agent(
    name="scout_freepoints",
    model=model_factory.fast(),
    instruction=_wp_scout_instruction(
        "freepoints", "freepoints", "fetch_freepoints_offers",
        "freepoints is an AU loyalty-deals aggregator (Flybuys / Everyday Rewards / "
        "Qantas / Velocity at Coles, Woolworths, BigW and partners)."),
    tools=[fetch_freepoints_offers],
    output_key="offers_freepoints",
)

scout_rewards = Agent(
    name="scout_rewards",
    model=model_factory.fast(),
    instruction=SCOUT_INSTRUCTION,
    tools=[fetch_everyday_rewards_boosts],
    output_key="offers_rewards",
)

scout_stock = Agent(
    name="scout_stock",
    model=model_factory.fast(),
    instruction="For each in-store offer, check per-store stock near the user's "
                "home and emit StockSignal JSON. Note last_verified timestamps.",
    tools=[check_online_stock],
    output_key="stock_signals",
)
