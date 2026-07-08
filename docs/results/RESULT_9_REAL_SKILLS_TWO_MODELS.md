# Result 9 — Real skills from Anthropic and GitHub, run by two different AI models

**Date: 2026-07-08 · Written by: Fable 5, the coordinating AI for this
experiment. 120 trials, all completed, zero infrastructure errors.**

This report is written to be readable with no prior knowledge of this
project. Every technical word is explained where it first appears.

---

## 1. What question does this experiment answer?

Teams of AI assistants are usually built by giving each assistant a "skill" —
a text file of instructions describing its job. Skill files are shared
publicly the way code libraries are: Anthropic publishes some, GitHub
publishes some, and developers download and combine them.

The questions:

1. **If you build a team out of real, well-written, publicly shared skill
   files — with no coordination plan — does the team work? What does it
   cost?**
2. **Does adding an STJP coordination contract (a machine-checked plan of
   who sends what to whom, in what order) fix it, and how much does it
   save?**
3. **Does the answer change if you swap the small AI model for a smarter
   one?**

## 2. The two teams we built (from real public files)

We did not write the job instructions ourselves. Two inexpensive AI agents
were sent out to fetch them from public repositories, record where each file
came from, and check its license permits reuse.

**Team 1 — the "announcement team"** (folder name `doc_pipeline`), built
from Anthropic's public skills repository (github.com/anthropics/skills,
each skill individually Apache-2.0 licensed):

- a **Writer** using the `internal-comms` skill (writes company
  announcements in the company's formats),
- a **BrandReviewer** using the `brand-guidelines` skill (checks brand
  colors, fonts, style),
- a **DocLead** using the `doc-coauthoring` skill (finalizes and
  distributes documents),
- plus a **Requester** (the person asking for the announcement).

The rule a real company would care about: **the announcement must not go
out before the brand review has approved it, and must not go out twice.**

**Team 2 — the "code-change team"** (folder name `pr_merge`), built from
GitHub's public Copilot customization collection
(github.com/github/awesome-copilot, MIT licensed):

- an **Author** using the `address-comments` agent file (prepares a code
  change and works the review loop),
- a **CodeReviewer** using the `code-review-generic` instructions
  (line-level quality review, can block a merge),
- a **SecurityReviewer** using the `se-security-reviewer` agent file
  (OWASP-style security review),
- a **Merger** using the `principal-software-engineer` agent file (the
  tech lead who makes the ship call).

The rule: **the change must not be merged before the security review has
passed, and must not be merged twice.**

The key property of the originals: **each file describes one job well, and
none of them says anything about the order the team must work in.** That
ordering normally lives in a human's head. Download details, exact source
URLs and licenses: `experiments/cases/skills_safety/doc_pipeline/SOURCES.md`
and `experiments/cases/skills_safety/pr_merge/SOURCES.md`. (Anthropic's
document-file skills — docx, pdf, pptx, xlsx — were deliberately *not*
used: their license forbids copying. The three we used are Apache-2.0.)

## 3. How one test run works

Everything runs on this repository's trial engine
(`experiments/subagent_trials/engine.py`) — plain deterministic code, no
cloud services. One **trial** is one complete attempt by the team to do its
job from scratch. We ran **10 trials** per configuration, because a single
attempt can succeed or fail by luck.

A trial proceeds in **rounds**. Each round, the engine asks some team
members: "here is what you've received so far — what do you do next?" The
member answers with either a message to send ("send `DraftComms` to
BrandReviewer") or "wait". Every answer comes from a real AI model call, and
each role is played by a **freshly started, independent AI assistant** that
sees only its own instructions and its own inbox — never another member's.

Each team was tested in **three settings**. (A "setting" is what earlier
reports in this project call an "arm" — the one thing we change on purpose
while keeping everything else identical.)

1. **Original skills, no coordination plan.** Each member gets the real
   downloaded skill text plus the overall task description — which, note,
   *does* state the correct order in plain English. Everyone is asked every
   round; whatever anyone sends is delivered. Budget: 4 rounds (enough to
   pass the 4 messages the job needs, with no room for waste).
2. **Corrected skills, plan as text only.** Each member's skill is
   minimally corrected to name its exact partner and its slice of the plan —
   written down as text, but *nothing enforces it*. Budget: 8 rounds.
3. **Full STJP.** Same corrected skills, plus the machinery: a **gate** (a
   program that checks each outgoing message against the plan and blocks
   wrong ones before delivery) and a **scheduler** (a program that only asks
   a member to act when the plan says it can be that member's turn). The
   plan itself was verified by the Scribble protocol compiler — a program
   that mathematically checks no member can end up waiting forever — before
   any AI was called. Budget: 12 rounds.

The whole grid ran **twice, with different AI models playing the team
members**:

- **Claude Haiku 4.5** — the small, cheapest model tier;
- **Claude Sonnet** — the mid-tier model, noticeably smarter and more
  expensive.

2 teams × 3 settings × 2 models × 10 trials = **120 trials**, played by 149
independently spawned AI assistants coordinated in the background.

## 4. What we measured (in plain words)

- **Finished the job** — percentage of the 10 trials in which the team's
  deliverable actually went out (announcement shipped / change merged),
  called `gcr_pct` in the raw data files.
- **Finished it safely** — percentage that finished AND never broke the
  team's safety rule (`cgc_pct` in the raw data).
- **Safety violations** — count of irreversible actions done out of order
  or twice (shipping before approval, double-merging, …); `total_disasters`
  in the raw data.
- **Rule-breaking messages** — messages that deviated from the verified
  plan (sent too early, sent twice, sent to the wrong member). These are
  detected after the fact by a checking program, not by an AI. Deviations
  are waste even when the team recovers: someone has to read and reconcile
  them.
- **AI calls per trial** — how many times any member had to be asked to
  think. Every ask costs money, even if the answer is "wait".
- **Estimated text cost per trial** — how much text the AI members read and
  wrote per attempt, estimated as characters ÷ 4 (one "token", the billing
  unit of AI usage, is about 4 characters). Comparable within this report
  only.

One measure we deliberately do NOT report: wall-clock seconds. All 12 runs
shared the same batched execution, so their elapsed times are identical by
construction and say nothing about the settings.

## 5. Results

**Team 1 — announcement team** (from Anthropic's public skills):

| Setting | AI model | Finished the job | Finished safely | Safety violations | Rule-breaking messages | AI calls per trial | Text cost per trial |
|---|---|---:|---:|---:|---:|---:|---:|
| Original skills, no plan | Haiku (small) | 10/10 | 10/10 | 0 | 120 | 16.0 | 5,770 tokens |
| Original skills, no plan | Sonnet (smarter) | **0/10** | 0/10 | 0 | 180 | 16.0 | 5,934 tokens (all wasted) |
| Corrected skills, plan as text | Haiku | 10/10 | 10/10 | 0 | 120 | 16.0 | 4,324 tokens |
| Corrected skills, plan as text | Sonnet | 10/10 | 10/10 | 0 | 120 | 16.0 | 4,380 tokens |
| **Full STJP (gate + scheduler)** | **Haiku** | **10/10** | **10/10** | **0** | **0** | **4.0** | **1,800 tokens** |
| **Full STJP (gate + scheduler)** | **Sonnet** | **10/10** | **10/10** | **0** | **0** | **4.0** | **1,808 tokens** |

**Team 2 — code-change team** (from GitHub's public Copilot files):

| Setting | AI model | Finished the job | Finished safely | Safety violations | Rule-breaking messages | AI calls per trial | Text cost per trial |
|---|---|---:|---:|---:|---:|---:|---:|
| Original skills, no plan | Haiku (small) | **0/10** | 0/10 | 0 | 120 | 16.0 | 5,295 tokens (all wasted) |
| Original skills, no plan | Sonnet (smarter) | 10/10 | 10/10 | 0 | 120 | 16.0 | 5,411 tokens |
| Corrected skills, plan as text | Haiku | 10/10 | 10/10 | 0 | 120 | 16.0 | 4,175 tokens |
| Corrected skills, plan as text | Sonnet | 10/10 | 10/10 | 0 | 120 | 16.0 | 4,246 tokens |
| **Full STJP (gate + scheduler)** | **Haiku** | **10/10** | **10/10** | **0** | **0** | **4.0** | **1,768 tokens** |
| **Full STJP (gate + scheduler)** | **Sonnet** | **10/10** | **10/10** | **0** | **0** | **4.0** | **1,776 tokens** |

## 6. What this means

**1. Without a coordination plan, whether the team works is a coin flip —
and a smarter model does not fix it, it just moves the failure.** The small
model's teams delivered the announcement 10/10 but failed the code change
0/10; the smarter model failed the announcement 0/10 and delivered the code
change 10/10. Same skills, same instructions, same budget. You cannot
predict from the skill files — or from the model's price tag — which team
will silently fail.

The traces show *how* they fail. The small model's code-change team
crawled: the Author re-submitted the same change every round, the reviewers
re-sent their verdicts, and the Merger never got to act before the budget
ran out — every trial burned ~5,300 tokens' worth of work and delivered
nothing. The smarter model's announcement team failed differently: the
BrandReviewer sent its first approval *to the wrong member* (back to the
Writer instead of on to the DocLead), and the DocLead — who never received
the draft content directly — kept waiting while the Requester and Writer
looped, re-requesting and re-drafting until the budget ran out.

**2. Writing the plan into each member's instructions fixes completion but
not discipline.** With corrected skills as text, both models delivered
20/20. But the checking program still logged 120 rule-breaking messages per
run — 12 per trial, mostly members re-sending things while waiting, because
everyone is still asked every round and nothing stops them. It works, at
4,200–4,400 tokens per delivery.

**3. Full STJP was flawless, and identical, on both models.** 40/40 trials
delivered, zero rule-breaking messages, zero safety violations — at exactly
4 AI calls per trial, which is the theoretical minimum (the job takes 4
messages, so 4 decisions). Cost: ~1,780–1,810 tokens, i.e. **3× cheaper
than the no-plan setting and 2.4× cheaper than the plan-as-text setting**,
with the difference coming from the scheduler never waking a member whose
turn it can't be, and the gate making wrong sends impossible rather than
merely inadvisable.

**4. The model comparison is the finding.** Between Haiku and Sonnet, the
full-STJP numbers differ by well under 1%. The structure did the work, so
the cheap model performed exactly like the expensive one. Put bluntly: with
STJP you can staff the team with the cheapest model available; without it,
even the expensive model fails half the time — and you don't get to know
which half in advance.

**5. One honest surprise: zero safety violations even without the plan.**
Unlike this project's earlier benchmark (where unvalidated teams
double-charged a traveler in 10/10 trials), neither model ever shipped
before approval or merged before clearance here — the task description's
plain-English warning was enough to prevent the *worst* outcome in these
two scenarios. The no-plan setting failed by stalling and duplicating, not
by doing the irreversible thing early. The cost of no-coordination showed
up as burned budget and silent non-delivery instead. (In the earlier
benchmark's four cases it showed up as both.)

## 7. Honest limits

- 10 trials per configuration is enough to see 0/10-vs-10/10 patterns, not
  to measure small differences precisely.
- The token numbers are character-count estimates (characters ÷ 4), not
  billing-grade meter readings, and each member also carries a fixed
  assistant-harness overhead that is the same in every setting — so
  *ratios* between settings are meaningful, absolute values are not.
- The two teams are strictly linear, four-message jobs. They have no
  branching decisions and no built-in deadlock trap, which is why the
  no-plan failures here are stalls rather than deadlocks; the earlier
  four-case benchmark (`RESULT_8_SKILL_SAFETY.md`) covers those harder
  shapes.
- The original-skills setting has the tightest round budget (4 rounds).
  The budget equals the number of messages the job needs, so a perfectly
  coordinated team fits, but there is no slack for waste — that is the
  point of the setting, but it does mean "0/10" reads as "could not finish
  within a fair budget", not "could never finish given unlimited retries".
- The protocol checker used here is the Scribble compiler built from
  source in this sandbox. The newer coinductive checker (the "new
  Scribble", nuscr fork) was verified earlier on this branch to produce
  identical state machines for cases of this shape; its prebuilt binary
  could not be installed in this particular sandbox session (the
  environment's permission system blocked installing an external
  executable), so it was not re-run here.

## 8. Where everything is

- Scoreboards (one JSON per run) + aggregate:
  `experiments/subagent_trials/reports/ss2026_new_skills/`
- Full trial-by-trial state, every message and every deviation:
  `*.state.json` in the same folder (copied from the live run directory)
- The two team definitions (skills, corrected skills, verified plan,
  safety rules): `experiments/cases/skills_safety/doc_pipeline/` and
  `experiments/cases/skills_safety/pr_merge/`
- The downloaded source skills with full provenance and licenses:
  `experiments/cases/skills_safety/_incoming/`
- How the runs were driven: `experiments/subagent_trials/dispatch_helper.py`
  (round batching) — each role-batch was answered by an independently
  spawned Claude subagent of the group's model.
