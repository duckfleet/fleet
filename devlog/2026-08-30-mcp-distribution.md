# Design — distribution via the user's assistant (MCP), not a web front

**Status:** v2 / active direction. Supersedes "web onboarding is the front door." This is the
delivery mechanism the product was missing.

## The problem this solves
The hosted web funnel (sign in, chat a profile, get a sample brief) captures interest but
cannot *convert* it. The moment someone says "I want this," the product has to actually run
for them: nightly hunts, live Maps calls, a morning email, later some gated actions. Two ways
to deliver that, both walled off on purpose:

- **Self-host** (their keys, their GCP project) — the "too technical" wall. A non-technical
  tester was lost; their instinct was "I have ChatGPT, can't I just ask it?"
- **Run it centrally** (our infra, our keys, their data) — the cost + safety boundary we will
  not cross (~$10–15/user/mo of inference, holding strangers' keys, spend/phone on a shared
  instance).

So after the sample lands there is genuinely no next step. That is not a UI gap; the delivery
mechanism for a stranger does not exist yet. The MCP / assistant path IS that mechanism.

## The decision
Make DuckFleet reachable **from inside the assistant the user already pays for** (Claude,
ChatGPT; Gemini consumer not yet — see landscape). Onboard by chatting, run on demand, and
schedule via the assistant. The web page demotes to a landing page whose CTA is "add the
connector," not a form.

## The key insight — invert where the LLM lives
This is not just another adapter under `runtimes/`. It moves the model to the other side of
the boundary:

- **Today:** our server owns the model (ADK + `agents/model_factory.py`). Every hunt burns
  *our* inference. That is the ~$10–15.
- **MCP:** the *user's assistant* owns the model. Our server becomes **deterministic tools +
  data** — fetch offers, compute stack value, worth-it, gates, profile read/write. The
  assistant does the finding and the talking on *its* billing; our code does the arithmetic
  and the guardrails.

This is literally Principle 2 ("LLM finds, Python computes") pushed across the network
boundary. It delivers **$0 inference to us, provider-agnostic, and usable** in one move.
Evidence: the Aug billing split was Vertex AI $2.94 vs Cloud Run $0.04 — delete the inference
line and the per-user marginal cost collapses to roughly an email send.

## Cost / safety boundary (unchanged, now easier to honor)
- Inference is on the user's assistant → $0 to us, no vendor lock-in.
- We hold a profile + cached public offer data (+ a privacy policy the directories require
  anyway). We never hold the user's model key.
- **Gated real-world actions (phone via Twilio, spend) stay OUT of any shared instance** —
  they run only in the user's own session/keys, exactly as `guardrails/gates.py` already
  demands. No change to the gate doctrine.

## Architecture
- **Keep** `agents/` (deterministic core), `schemas/`, `guardrails/` untouched — the IP.
- **New `runtimes/mcp/`** adapter (sibling to `runtimes/gcp_adk/`, never shared logic). It
  exposes the *deterministic* layer as MCP tools. The ADK/`model_factory` orchestration stays
  for the GCP nightly path; MCP is a **second orchestration mode over the same core**, with
  the assistant as orchestrator instead of the coordinator agent.
- **Local stdio server first** (their keys, their machine, zero hosting for us). This is the
  self-host story made trivial: "add DuckFleet to Claude Desktop" instead of "deploy to GCP."
  Ships fastest, proves the conversation shape.
- **Remote hosted second** (OAuth) for the Claude/ChatGPT connector *directories* — the actual
  distribution channel.

### Tool surface (deterministic; the assistant orchestrates)
- `get_offers(source)` — fetch/parse stable feeds (OzBargain RSS). No LLM.
- `value_offers(offers, profile)` — `compute_stack_value`, cents-per-point. Pure Python.
- `worth_it(offer, profile)` — drive/fuel/time economics + `worth_it_verdict`.
- `check_gates(action, profile)` — ToS / spend / preference / call gates, structured refusals.
- `save_profile` / `get_profile` — conversational onboarding replaces the web form.
- `explain` — the decision log ("kept X, refused Y, why").

The assistant reads offers + profile, does the fuzzy matching / summarizing itself, and calls
these tools for every number and every gate. Nothing that touches money or a phone runs
without the user present in their own session.

## Provider landscape + tier availability (verify — moves fast)
Custom-URL connector addition and directory listing differ in REACH: raw custom-URL is gated/
limited; vetted/directory tends to be broader. The directory is therefore the reach channel, not
a nice-to-have. Snapshot (Aug 2026, re-verify before promising):
- **Claude (most open):** custom remote-MCP connectors on ALL plans incl. Free per Anthropic docs
  (Free = ONE custom connector; paid = more). Best mass channel; lead here. Some third-party
  sources wrongly say Pro-only, and real free-account UX should be tested. Directory submission
  needs a Team/Enterprise org (+ tool annotations, privacy policy).
- **ChatGPT (paid + writes gated):** custom MCP via Developer mode = Plus/Pro/Business/Enterprise/
  Edu, NOT Free. Individual Plus/Pro = READ/fetch-only; WRITE tools (our `update_preferences`)
  need Business/Enterprise/Edu. So onboarding-by-chat WRITES are gated on individual plans — make
  the read value (get_offers + worth_it) stand alone. Apps Directory is the broader path.
- **Gemini:** consumer app has NO custom MCP yet (only CLI / Enterprise / invite-only Spark).
- **Implication:** lead with Claude; treat the DIRECTORIES (not custom-URL) as reach; keep
  non-connector on-ramps (web sample page, llms.txt / "paste this to your assistant") for free and
  unsupported users so nobody is fully locked out.

## Doctrine updates to CLAUDE.md (make deliberately)
- Multi-tenant is now **in** (it was hackathon-scoped out). The *spirit* survives: $0 inference
  to us, never hold strangers' keys, no phone/spend on a shared instance.
- MCP is a **first-class runtime** alongside `runtimes/gcp_adk/`. GCP stays one hosting adapter.
- The web page is a landing/CTA surface, not the onboarding product.

## Phased plan
1. **Local stdio MVP** — the deterministic tools above wrapping `run_fleet`/onboarding; add to
   Claude Desktop; dogfood the full conversation (onboard → hunt → explain).
2. **Remote + OAuth** — same tools, hosted, addable without a terminal.
3. **Directory submissions** — Claude connectors + ChatGPT apps.
4. **Landing page** — repoint `app.duckfleet.dev` CTA from "email me a sample" to "add the
   connector"; keep the sample as the taste.

## Open questions (decide deliberately, do not drift)
- How much of the current ADK/`model_factory` finding logic moves into assistant-side prompts
  vs stays as optional server-side LLM for the GCP path.
- Scheduling for "while you sleep": assistant-native scheduled tasks (per-provider, flaky) vs a
  thin always-on runner the user opts into. Tier-0 (pull: "run my hunt") may be enough for most.
- Where the profile lives in the local-stdio case (a local file vs the user's own Firestore).

## Building in public
Two posts queued from this work (briefs in `social/posting-log.md`):
- **Post 3 — "The connector is real":** shipped it, added it to Claude from a phone; the
  LLM-inversion in practice; honest bits (OAuth/DNS/SSL fiddliness, browse-install still needs
  directory approval).
- **Post 4 — "Shipping the tools wasn't enough":** reactive -> guided via server instructions +
  prompts; you hand the hosting of the experience to someone else's assistant and have to teach it.
