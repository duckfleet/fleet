# DuckFleet — Project Context for Claude Code

**One-liner:** DuckFleet — an agent fleet that hunts loyalty points while you sleep,
starting with the $3.50 rubber duck that was secretly a business-class seat.

**Mascot:** 🦆 — the duck is the brand; keep it in the README and product surfaces.

**Repo:** github.com/duckfleet/fleet (the **living product** — build here)
**Domain:** duckfleet.dev · **Identity:** duckfleet.dev@gmail.com

> This project started as a hackathon entry (Google "All Things Agentic", Aug 2026). That
> entry is **submitted and frozen** as a separate fork (`avipaul6/fleet`). This repo is now
> the ongoing product and is free to evolve — do NOT try to keep it in sync with the fork,
> and ignore any remaining hackathon-deadline framing.

---

## ⭐ North star (the product)
Turn DuckFleet into a **real, self-hostable product that anyone with an LLM key can run** —
Claude (Anthropic), ChatGPT (OpenAI), or Gemini (Google). Goals, in order:
1. **Provider-agnostic core.** A user brings their own model + key; DuckFleet runs on it. No
   lock-in to any one vendor.
2. **Actually usable.** Lower the "still too technical" wall: easy setup, sensible defaults,
   clear docs, a path that doesn't require deep cloud knowledge.
3. **Trustworthy by design.** Governance stays the point — it refuses, asks, and logs. A
   product that takes real-world actions has to earn being left running unattended.
4. **Distribution in public.** Keep shipping in the open (repo, write-ups, posts).

We are now deliberately building the product/usability layer that was *deferred* during the
contest. Multi-tenant scale and anything that spends the author's money for strangers stay
off the table (see cost boundary below), but self-host, provider breadth, and usability are
in scope now.

---

## What it is
A background multi-agent fleet that ingests loyalty offers overnight, computes offer-stacking
value and cents-per-point, decides whether an errand is worth the time/fuel, optionally
verifies stock by a gated phone call, and delivers a ranked morning action list. It runs on a
schedule and emails the user what's worth doing — and, just as importantly, what it skipped
and why.

## Core principles — durable, do NOT re-litigate
1. **Governance is a feature, not a report.** `guardrails/gates.py` enforces spend caps,
   call-hours, one-call-per-store, ToS filtering, mandatory AI self-identification on calls,
   human approval gates, and a structured audit log. Every real-world action routes through a
   gate. No exceptions.
2. **LLM finds, Python computes.** The model finds stacks; deterministic Python does ALL
   arithmetic (`compute_stack_value`, `worth_it_verdict`, economics). Never let the model do
   maths it can delegate — the numbers a user acts on must be correct.
3. **Runtime-agnostic logic is the real IP.** `agents/`, `schemas/`, `guardrails/` know
   nothing about the platform they run on. Deployment/hosting targets are thin adapters under
   `runtimes/`. Never put agent/guardrail/schema logic in a runtime folder. A new provider or
   host should be a re-wire, not a rewrite.
4. **Provider / bring-your-own-key.** Model config per tier is `{provider, model,
   api_key_env}`. Keys are read ONLY from the user's own env / secret store, never bundled or
   committed. This is what makes DuckFleet shippable to strangers at $0 inference cost to us.
5. **Honesty over polish.** Real skip reasons, never confabulated ones. Anything simulated is
   labelled simulated. This is a product stance, not a demo trick.
6. **Schemas are the contract.** `schemas/` (Pydantic v2) locks the Offer / ActionItem /
   Profile shapes before scouts or runtimes are added.

## Multi-provider model system (the current focus)
`agents/model_factory.py` resolves two tiers from env: `DUCKFLEET_MODEL_FAST` and
`DUCKFLEET_MODEL_STRONG`. Today it resolves native Gemini (via ADK) and `vertex_ai/...`
(Claude on Vertex via the ADK LiteLlm wrapper). **The product needs it to resolve any of:**
- **Anthropic** (Claude, direct API) — see the `claude-api` skill for current model IDs/pricing
- **OpenAI** (ChatGPT models, direct API)
- **Google Gemini** (AI Studio key, not only Vertex)
- **Vertex / Bedrock / others** as optional enterprise paths

The ADK `LiteLlm` wrapper already gives most of this; the work is: (a) a clean provider →
model → key-env resolution in `model_factory.py`, (b) sensible per-provider defaults for the
FAST/STRONG tiers, (c) a setup path that tells a user exactly which env var to set, and (d)
keeping the ADK dependency from leaking provider assumptions into `agents/`. Whether to stay
on ADK long-term or decouple the orchestration is an open design question — decide it
deliberately, don't drift.

Agents + tiers: coordinator / valuer / caller = STRONG; scouts / worth_it / presenter = FAST.

## Architecture
`agents/fleet.py::run_fleet(replay)` chains: get offers (live scout OR replay fixtures) →
ToS gate → deterministic valuation + spend gate → preference gate (honest skip reasons) →
worth-it (real Maps Routes, or frozen drive in replay) → presenter → history + audit + email.
Returns `brief`, `assessed`, `audit`, `economics`, `call_candidates`.

`--replay` is a first-class run mode: agents run against deterministic fixtures
(`fixtures/replay_offers.json`, or any file via `DUCKFLEET_REPLAY_FIXTURE`) producing a
known-good brief with no live calls. Powers the eval suite, the sample-brief page, and local
dev. Keep it working.

## Coding conventions
- Python 3.11+, Pydantic v2 for all schemas.
- Scrapers: read-only, rate-limited, respect robots.txt. Prefer stable feeds (OzBargain RSS)
  over brittle HTML.
- Every real-world action routes through a guardrail gate.
- `evals/` are red-team failure-mode checks; keep them green (they're CI + the reproducible
  trust story). Run `python -m evals.run` — fully local, no cloud/keys needed.

## Repo map
```
agents/            # fleet logic — orchestrator, scouts, valuer, worth-it, caller,
                   # presenter, onboarding, economics, delivery (runtime-agnostic; the IP)
schemas/           # Offer / ActionItem / Profile contracts (Pydantic v2)
guardrails/        # gates — spend, ToS, preferences, calls, AI self-ID, audit trail
evals/             # red-team failure-mode tests (local, deterministic)
fixtures/          # seeded offers incl. the hero "duck" stack + demo_skips (powers replay)
config/            # settings via env; loads profile.json / onboarding profile
adk_apps/          # thin wrappers to poke each agent in `adk web` (dev only)
scripts/           # dev runners (dev_fleet, dev_caller, gmail_authorize, …)
runtimes/
  gcp_adk/         # Cloud Run Job + Scheduler + one-click deploy (a hosting adapter)
  # add new provider/host adapters here as siblings — never shared logic
docs/              # architecture diagram
demo/gcp-hackathon/  # ARCHIVED hackathon material (video/podcast/shot-list) — reference only
devlog/            # dated build log + design rationale
social/            # building-in-public posting log: voice guide + post archive/drafts
CLAUDE.md README.md LICENSE .gitignore
```

## Cost & safety boundary (bake into the design)
- **Self-host (BYO key, BYO project):** the product. Unlimited users, $0 inference to us.
- **Public "try it" surfaces** (sample-brief page, replay demo): read-only, rate-limited,
  no phone calls, no spend. Bounded cost on our project.
- **Never** wire phone dialling or money-spending into a shared/public instance, and never
  hold strangers' keys centrally. Phone (Twilio) + Maps Routes are per-use costs that must
  run in the *user's own* project/account, not a centralised one.

## Current status (what's built & working)
- Full replay + live pipeline via `run_fleet` (agents above), all end-to-end tested.
- Guardrails enforced; 18 red-team evals green (`python -m evals.run`, no cloud).
- Gated phone call: `agents/verification.py` — real **Twilio** call + real **Cloud
  Text-to-Speech** audio; every gate enforced (approval, hours, one-per-store, AI self-ID).
- Email: `agents/delivery.py` — multipart HTML + plain text. HTML is the **editorial**
  design (type-led, email-safe: inline styles, tables for side-by-side, solid highlight,
  system-font fallback). Reframed as a decision log: "Checked N offers · Kept X · Refused Y",
  worth-doing pick, refused-with-reasons, gated-call ask, run cost. Real Gmail send works.
- Onboarding: chat → `profile.json` (`agents/onboarding.py`); hosted onboarding + sample-brief
  page in `runtimes/gcp_adk/` (Google sign-in, "email me a sample brief" via replay).
- Economics/history: per-run ROI (`agents/economics.py`); BigQuery sink (`agents/history.py`).
- **Deployed on GCP** (project `duckfleet-agents`, us-central1): Cloud Run Job
  `duckfleet-nightly` (`runtimes/gcp_adk/deploy.sh`), Scheduler-triggered nightly. Secrets in
  Secret Manager. `.env` is laptop-only (gitignored). A redeploy pushes code/config changes.
  This GCP path is one hosting adapter, not the product's identity.

## Roadmap (product)
- **Multi-provider support** (headline): finish `model_factory.py` for Anthropic / OpenAI /
  Gemini / Vertex with clean per-provider defaults and a setup path. This is the enabler for
  "anyone with a Claude/ChatGPT/Gemini key can run it."
- **Distribution via the user's assistant (MCP) — the active direction.** Ship DuckFleet as a
  connector users add to Claude / ChatGPT (Gemini consumer not yet), so they onboard by chatting
  and it runs on *their* model billing ($0 inference to us). Inverts where the LLM lives: the
  assistant orchestrates, our tools stay deterministic. Full design + phased plan in
  `devlog/2026-08-30-mcp-distribution.md`. The web page demotes to a landing/CTA surface.
- **Shopping-habits valuation:** add `regular_merchants` to the profile; treat spend you'd
  make anyway as free in `_value()` → fixes "spend $X get pts" offers that currently value low.
- **Online vs in-store `fulfilment` flag** (no drive penalty for online).
- **Behaviour-learning agent** — adapts the profile from feedback/behaviour over time.
- **Redemption-side** ("where can my points take me") — see `devlog/2026-08-19-roadmap-redemption.md`.
- **Loyalty-account actuation** (auto-activate boosts) — needs auth/ToS review; user-session only.

## Verify before relying on (models/APIs move fast — check docs)
Provider model IDs and pricing (Anthropic, OpenAI, Google), LiteLLM provider strings, ADK
API surface. Don't hardcode model IDs into the codebase — resolve from env and verify against
official docs (docs.claude.com, platform.openai.com, ai.google.dev). For Anthropic specifics,
use the `claude-api` skill rather than answering from memory.

## Working preferences
- **User drives all commits/pushes — do NOT commit or push.** Leave changes staged for review.
- Prefer fixing the **root cause** over a workaround.
- Public voice reads as a **real project**, first-person, no marketing/AI-slop cadence, no
  em-dashes in user-facing copy.
- **Building in public:** LinkedIn posts, the voice guide, and the post archive/drafts live in
  `social/posting-log.md`. Match that voice and update the log whenever a post ships or a draft
  is written, so any session can continue the thread.
