# Result 9 — Real skills from Anthropic and GitHub, run by two different AI models

**Date: 2026-07-08 · Written by: Fable 5 (the coordinating AI for this
experiment) · Status: DRAFT — numbers pending, run in progress.**

This report is written to be readable with no prior knowledge of this
project. Every technical word is explained where it first appears.

---

## 1. What question does this experiment answer?

Teams of AI assistants are usually built by giving each assistant a "skill" —
a text file of instructions describing its job. Skill files are shared
publicly the way code libraries are: Anthropic publishes some, GitHub
publishes some, and developers download and combine them.

The question: **if you build a team out of real, well-written, publicly
shared skill files — with no coordination plan — does the team work? And how
much does it cost?** Then: **does adding an STJP coordination contract (a
machine-checked plan of who sends what to whom, in what order) fix it, and
does the answer change with a smarter AI model?**

## 2. The two teams we built (from real public files)

We did not write the job instructions ourselves. Two inexpensive AI agents
were sent to fetch them from public repositories:

**Team 1 — "Announcement team"** (case name `doc_pipeline`), built from
Anthropic's public skills repository (github.com/anthropics/skills, each
skill Apache-2.0 licensed):
- a **Writer** using the `internal-comms` skill (writes company announcements),
- a **BrandReviewer** using the `brand-guidelines` skill (checks brand
  colors, fonts, style),
- a **DocLead** using the `doc-coauthoring` skill (finalizes and distributes
  documents),
- plus a **Requester** (the person asking for the announcement).

The safety rule a real company would care about: **the announcement must not
be distributed before the brand review has approved it** — and it must not
be distributed twice.

**Team 2 — "Code-change team"** (case name `pr_merge`), built from GitHub's
public Copilot customization collection (github.com/github/awesome-copilot,
MIT licensed):
- an **Author** using the `address-comments` agent file (prepares a change),
- a **CodeReviewer** using the `code-review-generic` instructions (quality
  review, can block a merge),
- a **SecurityReviewer** using the `se-security-reviewer` agent file
  (security review),
- a **Merger** using the `principal-software-engineer` agent file (the tech
  lead who decides to merge).

The safety rule: **the change must not be merged before the security review
has passed** — and it must not be merged twice.

The point about the originals: **each file is good at describing one job,
and none of them says anything about the order the team must work in.**
That ordering normally lives in a human's head. Full download details,
licenses and links: `experiments/cases/skills_safety/doc_pipeline/SOURCES.md`
and `experiments/cases/skills_safety/pr_merge/SOURCES.md`.

## 3. How one test run works

Everything runs on this repository's trial engine
(`experiments/subagent_trials/engine.py`) — deterministic code, no cloud
services. One **trial** = one complete attempt by the team to do its job
from scratch. We run **10 trials** per configuration, because a single
attempt can succeed or fail by luck.

A trial proceeds in **rounds**. In each round the engine asks some team
members: "here is what you've received so far — what do you do next?" The
member answers with either a message to send ("send `DraftComms` to
BrandReviewer") or "wait". Every answer comes from a real AI model call —
each role is played by a **freshly started, independent AI assistant** that
sees only its own instructions and its own inbox, never another member's.

Each team was tested in **three settings** (a "setting" is what, in earlier
reports of this project, is called an "arm" — the thing we vary on purpose):

1. **Original skills, no coordination plan.** Each member gets the real
   downloaded skill text plus the overall task description. Everyone is
   asked every round. Whatever anyone sends is delivered.
2. **Corrected skills, plan as text only.** Each member gets a minimally
   corrected skill that includes its own slice of the coordination plan —
   written down as text, but *nothing enforces it*.
3. **Full STJP.** Same corrected skills, plus the machinery: a **gate**
   (a program that checks each outgoing message against the plan and blocks
   wrong ones before delivery) and a **scheduler** (a program that only asks
   a member to act when the plan says it could be that member's turn).
   The plan itself was checked by the Scribble protocol compiler — a
   program that mathematically verifies no member can end up waiting
   forever — before any AI was called.

And the whole grid was run **twice with different AI models playing the
team members**:
- **Claude Haiku 4.5** — the small, cheapest model tier;
- **Claude Sonnet** — the mid-tier model, noticeably smarter and pricier.

That is 2 teams × 3 settings × 2 models × 10 trials = **120 trials**.

## 4. What we measured (in plain words)

- **Finished the job** — the percentage of the 10 trials in which the
  team's final deliverable actually went out (the announcement shipped /
  the change merged). In the raw data this is `gcr_pct`.
- **Finished it safely** — the percentage of trials that finished AND never
  broke the safety rule along the way. In the raw data: `cgc_pct`.
- **Safety violations** ("disasters") — the count, across all 10 trials, of
  irreversible actions taken out of order or twice: shipping before brand
  approval, merging before security clearance, double-shipping,
  double-merging. In the raw data: `total_disasters`.
- **AI calls per trial** — how many times any team member had to be asked
  to think. Every ask costs money, whether the member acts or says "wait".
- **Estimated text cost per trial** — how much text the AI had to read and
  write per attempt, estimated as characters ÷ 4 (the usual rough size of
  one "token", the unit AI usage is billed in). Comparable within this
  report, not across reports that used other models.
- **Cost per delivered result** — text cost divided by the success rate:
  what one *successful* delivery really costs once you pay for the failed
  attempts too. If nothing ever succeeds, this is infinite (∞).

## 5. Results

*(numbers pending — run in progress)*

## 6. What this means

*(pending)*

## 7. Honest limits

*(pending)*

## 8. Where the raw data is

- Trial-by-trial state and every prompt/reply:
  `experiments/subagent_trials/runs/ss2026_new_skills/<model>__<team>__<setting>/`
- Per-run scoreboards: `report.json` in each of those folders
- Aggregates: `experiments/subagent_trials/reports/ss2026_new_skills/`
- The downloaded source skills with provenance:
  `experiments/cases/skills_safety/_incoming/`
