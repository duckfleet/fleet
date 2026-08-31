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
2. The distribution shift + proof it's real, in one post: old world = two doors that don't convert
   (deploy-it-yourself, web form); new world = a connector I added to Claude from my phone.
   (Post 2 — merged with the old "connector is real" beat.)
3. [MERGED into Post 2] "The connector is real" is no longer a standalone post; folded in above.
4. Reactive -> guided (Post 4 idea): shipping tools isn't enough; you have to teach the host.
5. (Later) the deliverability fight; onboarding-by-chat feel; the $0-inference cost model.

## Recurring themes for future posts
- Governance as a feature (it refuses, asks, logs) — why an agent that takes real actions has to
  earn being left running.
- "LLM finds, Python computes" and why the numbers must be deterministic.
- Deliverability as a real, unglamorous engineering story (own domain, SPF/DKIM/DMARC, the spam
  fight — see devlog).
- Old cloud deploy vs new assistant-native distribution (the technical through-line).

## Series + reach playbook (reuse for every post)
- **Series format:** numbered "Learning part N". Open with "Learning part N:" plus a one-line hook
  (a real quote works well), and link back to the previous part at the foot. Keep the voice human
  and deliberately not-over-polished (the author edits Claude's drafts down toward his own cadence).
- **Post 1:** https://www.linkedin.com/feed/update/urn:li:activity:7498643083623010304/
- **Hashtags:** 4–5, mix broad + niche, no spammy stacks. Default builder set: #BuildInPublic
  #AIAgents #ClaudeAI #MCP. #ClaudeAI + #MCP skew toward the Anthropic/Claude builder orbit. Author
  prefers NO @-mentions.
- **Links kill reach in the body.** Publish the post, then immediately add the link(s) as the FIRST
  COMMENT on your own post (you can only comment once the post is live). Keep the body link-free.
- **First 60–90 min is the reach lever:** reply fast to every comment; end each post on a genuine
  question to prime that.
- **Hook above the fold:** only the first ~2 lines show before "see more" — make them count.

---

## Archive

### Post 1 — PUBLISHED (LinkedIn) · ~Aug 2026 · "Learning part 1"
Status: live. Theme: premise + honest "too technical" + hackathon entry.
Link: https://www.linkedin.com/feed/update/urn:li:activity:7498643083623010304/
(This is the start of a numbered "Learning part N" series — each post links back to the previous.)

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

### Post 2 — FINAL · scheduled 7:30am Tue Sep 1 2026 (LinkedIn) · "Learning part 2"
Author's final version, in his own voice (kept deliberately human / not over-polished). Part of the
numbered "Learning part N" series; opens with the "Learning part 2:" label + the quote as the hook,
and links back to Part 1 at the foot. Author dropped the standalone technical paragraph to keep it
tight and human. Hook: the least technical person (a middle-aged mother) reached for ChatGPT, not a
download. Lesson: you now build two front doors (connector AND web), and even the connector must be
added from the web before it shows on your phone.
Images (thumbnail = first): 1) phone screenshot of Claude running "Set up my duck fleet preference";
2) the landing page showing BOTH doors ("Add to Claude" + "Open the web app").
Hashtags used: #BuildInPublic #AIAgents #ClaudeAI #MCP — chosen to reach the Anthropic/Claude
builder orbit (#ClaudeAI + #MCP are the closest hashtags get to Anthropic devrel + MCP
contributors). No @-mention, by author's choice.
Reach playbook for this post (see the shared playbook at the bottom of this file):
- Move BOTH links out of the body into the FIRST COMMENT right after posting (in-body links get a
  reach penalty on LinkedIn). Ready-to-paste comment text is under the post body below.
- Win the first hour: reply fast to every comment; lean on the closing question.
- Keep the "Learning part 2:" quote as the first line so the hook sits above the "see more" fold.
Paste this post's own URL below once live.

> Learning part 2: "I already have ChatGPT, can't I just ask it to do this?"
>
> I showed someone the DuckFleet agents over the weekend, and how the "agents" keep track of loyalty
> points for you. Her response was to get ChatGPT to do it. I found that really interesting, because
> she is a middle aged mother who is not technical at all. The instinct now is not "where do I
> download this," (or app) it is "can my AI assistant just do it."
>
> The onboarding experience is changing fast. But here is what I found: it is not actually
> straightforward to hand agents to someone like her. If you build something new, you can ship it as a
> custom connector, but she can only add it on the paid version of Claude, or as the single custom
> connector you get on the ChatGPT free plan.
>
> So these days, building an agent means building at least two front doors. One is the connector. One
> is a plain web version. And even the connector has a catch: you have to add it from the web first
> before it shows up on your phone. Once I did that, I opened Claude on my phone, said "add Velocity
> to my programs," and watched it save. No deploy, no terminal, no cloud project. It runs inside the
> assistant I already use. I just had to go through the web once to get it there.
>
> None of this is a clean "tap to install" yet, and building two front doors for one agent is more
> work, not less. If you are building agents right now, are you shipping a connector, a web app, or
> both? And has anyone cracked getting a non-technical person onto a connector without the web-first
> detour?
>
> Give it a go: https://app.duckfleet.dev/ and let me know if it worked or it was utterly confusing.
>
> Learning part 1: https://www.linkedin.com/feed/update/urn:li:activity:7498643083623010304/
>
> #BuildInPublic #AIAgents #ClaudeAI #MCP

**First comment (paste right after posting, for reach).** For max reach, delete the two link lines
from the body above and put them here instead:

> Give it a go: https://app.duckfleet.dev/ — let me know if it worked or was utterly confusing.
> Learning part 1: https://www.linkedin.com/feed/update/urn:li:activity:7498643083623010304/

---

## Planned posts (briefs for a future drafting session)
Not written yet. Each brief has the hook, the story beat, the technical takeaway, the honest bits
to keep, and a candidate closing question. Draft in the voice above (first person, honest, no
em-dashes, one 🦆, real open question). Post 2 makes the promise; these two deliver on it.

### Post 3 — DRAFT-LATER · "Learning part 3" (continues the numbered series)
The series is now "Learning part N" — each post opens with that label + a one-line hook and links
back to the previous part at the foot. Part 3 is the next in the sequence (candidate theme below,
formerly the "reactive -> guided" idea, or the deliverability story). Keep the human, not-polished
voice the author settled on for Part 2.

### (reference) old Post 3 brief — MERGED into Post 2 (Sep 1) · "The connector is real"
NOTE: no longer a standalone post. Its core (shipped it, added it to Claude from a phone, the
LLM-inversion, the honest install limit) is now the second half of the finalized Post 2 above. Kept
here for the detail beats in case a future follow-up wants them.
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
