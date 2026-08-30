# DuckFleet — building-in-public posting log

Purpose: so any Claude Code session (or the author) can continue the build-in-public thread
without starting from scratch. It holds the **voice**, the **running narrative**, and the
**archive** of posts (published + drafts). Update it whenever a post ships or a new draft is
written.

Primary channel: **LinkedIn** (first-person, from the author). Repo: github.com/duckfleet/fleet.

---

## Voice and style (derived from the author's own posts — match it, don't smooth it)
- **First person, real project.** The author is building this and saying what happened. Not a
  brand account, not a launch announcement.
- **Honest over polished.** Name what's still too technical, what broke, what's unfinished.
  Failure modes are content, not something to hide. This is the whole credibility of the thread.
- **Concrete, specific example carries the abstract point.** Rubber ducks → Qantas points, real
  maths, "refreshing forums A LOT." The story does the work; don't lead with a thesis and no
  proof.
- **Open the aperture, then land on the specific.** Posts often start with a broad framing
  ("building AI agents feels like the early 2000s web") and narrow to this week's concrete thing.
- **End with a genuine open question to the reader.** Not engagement-bait; a real question the
  author is actually curious about. Every post so far ends this way.
- **No AI-slop cadence. No em-dashes in the copy.** Short sentences, plain words, a little dry
  humor. Occasional emphasis ("A LOT"). The 🦆 duck is the brand — keep it, used sparingly.
- **Technical readers get a real technical takeaway** (the author's stated focus): contrast the
  *old* way (cloud deploy, one-click) with the *new* distribution world (add-to-your-assistant /
  MCP). Teach the shift, don't just narrate the project.
- Length: ~200–350 words. LinkedIn, so line breaks and breathing room, not dense paragraphs.

## Running narrative (the through-line)
Agents that do useful, boring, time-costly errands — outsource the legwork and *some* of the
judgment, not all of it. DuckFleet is the worked example: a governed fleet that hunts loyalty
points overnight and tells you what's actually worth doing. The arc being told in public:
1. The premise + the honest "still too technical" admission (Post 1).
2. The distribution reframing: old world = deploy it; new world = add it to the assistant you
   already use. (Post 2 — this one.)
3. The connector is REAL (Post 3 idea): actually shipped it, added it to Claude from a phone.
4. Reactive -> guided (Post 4 idea): shipping tools isn't enough; you have to teach the host.
5. (Later) the deliverability fight; onboarding-by-chat feel; the $0-inference cost model.

## Recurring themes for future posts
- Governance as a feature (it refuses, asks, logs) — why an agent that takes real actions has to
  earn being left running.
- "LLM finds, Python computes" and why the numbers must be deterministic.
- Deliverability as a real, unglamorous engineering story (own domain, SPF/DKIM/DMARC, the spam
  fight — see devlog).
- Old cloud deploy vs new assistant-native distribution (the technical through-line).

---

## Archive

### Post 1 — PUBLISHED (LinkedIn) · ~Aug 2026
Status: live. Theme: premise + honest "too technical" + hackathon entry. (Link: TODO — paste
the LinkedIn URL here when adding the next post, so future sessions can reference/quote it.)

> Building AI agents right now feels a lot like building a website in the early 2000s. Everyone's
> doing it, many of it is experimental, and somewhere in that pile is the stuff that quietly
> changes how things work.
>
> Right now I think the interesting use is agents that do useful, boring, time costly things. The
> errands that are genuinely worth doing but not worth your hour. The chasing. The comparing. The
> "is this actually a good deal or does it just look like one." Basically, outsource the legwork
> and some of the judgement. Not all of it.
>
> This month's attempt is a points hunter called 🦆 DuckFleet. The premise sounds like a joke: in
> 2025, rubber ducks at Big W could be stacked across promos into enough Qantas points for a
> business-class seat. Real deal, real maths, but catching it meant refreshing forums A LOT. So I
> built a fleet of agents to do that hunting overnight and just tell me what's actually worth doing.
>
> It's open source, and building it in public: the wins, the failure modes, and the parts that are
> honestly still way too technical for a normal person to use (there are plenty). It's also my
> entry for Google's All Things Agentic hackathon.
>
> So which of your useful but time-costly errands would you actually hand to an agent, and which
> would you never trust it with?

### Post 2 — DRAFT · Aug 30 2026
Theme: the distribution reframing. Old world = deploy it (one-click cloud). New world = add it to
the assistant you already use. The non-technical tester's "can't I just ask ChatGPT?" as the hinge.
Technical takeaway: inverting where the LLM lives. Review/edit before posting; paste the final URL
above once live.

> A month into building 🦆 DuckFleet in public, and this week taught me more about distribution
> than about agents.
>
> Quick recap: DuckFleet started as a hackathon entry and turned into the thing I keep poking at. A
> fleet of agents that hunts loyalty-points deals overnight and emails me a short brief of what's
> actually worth doing. Last post I was honest that big chunks of it were still too technical for a
> normal person. This week I fixed a pile of that. The morning brief now sends from its own domain,
> lands in a real inbox instead of spam, and reads like a decision log instead of a wall of numbers.
>
> Then I handed it to someone non-technical and hit the wall again, just in a new spot. They loved
> the sample. And then: "okay, so where do I actually go now?" I didn't have a good answer. Their
> next question was the better one: "I already have ChatGPT, can't I just ask it to do this?"
>
> That reframed the whole thing.
>
> Here is the technical bit, because I think it is a genuine shift. The old way to ship an agent is
> to deploy it. I even have a one-click deploy to Google Cloud, and for a developer that is fine.
> But "go set up a cloud project" is a wall for everyone else, and honestly for plenty of developers
> too.
>
> The new distribution channel is different. The agent becomes something you add to the assistant
> you already pay for. You onboard by chatting. It runs on your model, your billing. No deploy, no
> handing your keys to someone else's server. And the flip underneath it is the fun part: instead of
> my server paying to think, your assistant does the thinking and my code just does the boring maths
> and the guardrails.
>
> Old world: one-click deploy. New world: "add it to your assistant." Most of us are figuring out
> the second one right now, and I'll keep posting what I learn.
>
> So for the builders: are you still deploying your agents, or starting to ship them as something
> people add to Claude, ChatGPT, or Gemini? And what broke when you tried?

---

## Planned posts (briefs for a future drafting session)
Not written yet. Each brief has the hook, the story beat, the technical takeaway, the honest bits
to keep, and a candidate closing question. Draft in the voice above (first person, honest, no
em-dashes, one 🦆, real open question). Post 2 makes the promise; these two deliver on it.

### Post 3 — DRAFT-LATER · "The connector is real"
Theme: I said the new distribution was "add it to the assistant you already use." This week I
actually built it. DuckFleet is now a connector I added to Claude from my phone, and I asked it
to update my loyalty programs from the phone, no deploy, no terminal.
- **Story beat:** what it took end to end (a remote MCP server, hosted, on its own domain, with
  Google sign-in so each person gets their own data), and the small magic moment: told Claude
  "add Velocity to my programs," it saved it, and I confirmed it actually landed in the database.
- **Technical takeaway (the through-line):** the LLM-inversion in practice. The connector's tools
  are deterministic (fetch deals, do the maths); the assistant does the thinking on the user's own
  model. That is why it costs me almost nothing to run for someone else, versus the old world where
  my server paid to think.
- **Honest bits:** the fiddly parts. OAuth pointed at the wrong client, DNS and SSL cert waits, the
  ".dev domains must be HTTPS" gotcha. And the honest limit: true browse-and-tap install for
  strangers still needs directory approval; today it is "paste a URL," which is a paid-plan,
  desktop-settings thing, not yet a normal-person action.
- **Candidate question:** builders, have you shipped anything as a connector yet? Did the "no
  deploy" promise actually hold, and what broke?

### Post 4 — DRAFT-LATER · "Shipping the tools wasn't enough"
Theme: I shipped the connector and immediately hit a subtle wall. A new person adds it and then
what? By default an MCP connector is reactive: it only does something when you already know what
to ask. That is a poor first experience.
- **Story beat:** the fix is two small things most people skip. Server "instructions" (a note the
  assistant reads that shapes how it behaves the moment the connector is on) and "prompts" (named
  starters a user can click, like "Onboard me" or "Find deals worth chasing"). It turns "hi" into
  a guided flow.
- **Technical/product takeaway (the real point):** when you ship an agent as a connector, you are
  not just exposing functions, you are handing the hosting of the experience to someone else's
  assistant. You have to teach that assistant how to run your product: what to offer first, what
  rules to follow (here: never guess the maths, lead with the best pick, be honest about what you
  skip). Tools are the "what"; instructions and prompts are the "how to host it."
- **Honest bits:** prompt surfacing is client-dependent, so instructions are the reliable backbone.
  And this is a new muscle: we know how to design UIs, not how to design the way a third-party
  assistant should host our product.
- **Candidate question:** for people building agents/connectors, how are you handling the
  cold-start "what do I even ask?" problem? Onboarding inside someone else's chat is a strange new
  design surface.
