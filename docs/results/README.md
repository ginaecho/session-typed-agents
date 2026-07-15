# The results — the story that proves why STJP, step by step

This folder holds the evidence for every claim STJP (Session-Typed Judge
Panel — this project's system for checking and enforcing a team of AI agents'
coordination plan) makes. It is organized as **one story in four acts**
(Situation → Task → Action → Result), and every act is backed by runnable
demos and numbered reports (RESULT_1 … RESULT_11) — each report answers one
question and follows the same layout, so if you can read one you can read
them all.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The six words you need (everything else is explained inside each report)](#the-six-words-you-need-everything-else-is-explained-inside-each-report)
- [The story in four acts (STAR)](#the-story-in-four-acts-star)
  - [Act 1 — Situation: teams of good agents fail, silently and expensively](#act-1--situation-teams-of-good-agents-fail-silently-and-expensively)
  - [Act 2 — Task: what had to be proven](#act-2--task-what-had-to-be-proven)
  - [Act 3 — Action: the fix, added one layer at a time](#act-3--action-the-fix-added-one-layer-at-a-time)
  - [Act 4 — Result: stress-tested, scaled, and run on every real case](#act-4--result-stress-tested-scaled-and-run-on-every-real-case)
- [The real-case scoreboard (all nine, with benchmarks)](#the-real-case-scoreboard-all-nine-with-benchmarks)
- [The reports, one question each](#the-reports-one-question-each)
  - [RESULT_1 — Can anything except a compiler catch a deadlock?](#result_1--can-anything-except-a-compiler-catch-a-deadlock)
  - [RESULT_2 — Does a per-agent contract make the same work cheaper?](#result_2--does-a-per-agent-contract-make-the-same-work-cheaper)
  - [RESULT_3 — Does each added layer of protocol support help?](#result_3--does-each-added-layer-of-protocol-support-help)
  - [RESULT_4 — Is the full STJP stack the safest AND the cheapest?](#result_4--is-the-full-stjp-stack-the-safest-and-the-cheapest)
  - [RESULT_5 — Does it all work without Azure, with independent Claude agents?](#result_5--does-it-all-work-without-azure-with-independent-claude-agents)
  - [RESULT_6 — Can we trust our own measuring instruments?](#result_6--can-we-trust-our-own-measuring-instruments)
  - [RESULT_7 — Does everything hold at 100× the trials?](#result_7--does-everything-hold-at-100-the-trials)
  - [RESULT_8 — What happens with REAL skills from public repositories?](#result_8--what-happens-with-real-skills-from-public-repositories)
  - [RESULT_9 — Same real-skills test, run on two different models](#result_9--same-real-skills-test-run-on-two-different-models)
  - [RESULT_10 — The corrected code-review case: a loop, two concurrent reviewers, and a livelock](#result_10--the-corrected-code-review-case-a-loop-two-concurrent-reviewers-and-a-livelock)
  - [RESULT_11 — The corrected announcement case: the loop lives where the files put it](#result_11--the-corrected-announcement-case-the-loop-lives-where-the-files-put-it)
- [Older files kept for history](#older-files-kept-for-history)
- [Where the raw numbers live](#where-the-raw-numbers-live)
<!-- MENU:END -->

## The six words you need (everything else is explained inside each report)

- **Agent** — an AI assistant given written instructions and asked to do a job.
- **Protocol** — the written coordination plan for a team of agents: who sends
  which message to whom, in what order. STJP checks this plan with a compiler
  (a program that can mathematically prove the plan has no dead ends) before
  any agent runs.
- **Trial** — one complete attempt by a team of agents to finish its task.
  We repeat every experiment many times because a single attempt can succeed
  or fail by luck.
- **Setting** (older reports say **"arm"** — same thing) — one configuration
  of the experiment: what the agents are given and what machinery is switched
  on. We compare settings that differ in exactly one thing. All settings are
  drawn as pictures in [`../5_ARMS_EXPLAINED.md`](../5_ARMS_EXPLAINED.md).
- **Token** — the unit AI usage is billed in; roughly 4 characters of text.
  Fewer tokens = cheaper.
- **Disaster** — an irreversible action done before its required approval, or
  done twice (publishing an unreviewed article, charging a customer twice).

## The story in four acts (STAR)

### Act 1 — Situation: teams of good agents fail, silently and expensively

Real, well-written agent instruction files are published every day —
Anthropic's [skills](https://github.com/anthropics/skills), GitHub's
[awesome-copilot](https://github.com/github/awesome-copilot), the example
folders of every agent framework. Each file describes one job well. **None
of them says how a team of them must work together** — and a team wired
from them fails in ways no file predicts:

- **Deadlock** — everyone waits, forever, politely. Four agents each obeying
  a perfectly sound rule sent **zero messages** and burned ~25k tokens per
  attempt re-deciding "not my turn yet"
  ([RESULT_1](RESULT_1_DEADLOCK.md); the same circle reproduced on real
  AgenticPay-derived agents at three model tiers in the
  [live agenticpay run](../../experiments/cases/agenticpay_settlement/RESULTS_LIVE_SUBAGENTS.md)).
  Watch it happen: [the standalone demo](../../pitch/STJP%20Demo%20%28standalone%29.html).
- **Silent disaster** — the team "succeeds" while double-charging a traveler
  or shipping an unreviewed change: real public skills produced 20
  double-charge/double-write disasters across 40 trials
  ([RESULT_8](RESULT_8_SKILL_SAFETY.md)).
- **Unpredictable failure** — with no plan, a small model finished one team's
  job 0 times out of 10 while a smarter model finished the *other* team's job
  0 times out of 10, on identical files
  ([RESULT_9](RESULT_9_REAL_SKILLS_TWO_MODELS.md)). Buying a better model
  moves the failure; it does not remove it.
- **Livelock** — the newest and subtlest: on a looping review protocol, a
  one-word label mismatch made a team re-send messages forever, burning
  **42k tokens per trial with zero deliveries — even though the plan was
  pasted into every agent's instructions as text**
  ([RESULT_10](RESULT_10_PR_REVIEW_MERGE.md)).

### Act 2 — Task: what had to be proven

For "machine-check the plan, then enforce it" to be worth adopting, four
things must be shown, each with runnable evidence: (1) the failures above
are caught **before any money is spent**; (2) the machinery makes runs
**cheaper, not more expensive**; (3) the guarantees hold on **real public
files**, not just cases we wrote ourselves; (4) the numbers survive
**scale (n=100), stress (adversarial attack), and model swaps**.

### Act 3 — Action: the fix, added one layer at a time

The fix is a ladder, and every rung was measured separately: give each
agent only its own slice of the checked plan (its **contract** —
[RESULT_2](RESULT_2_TOKEN_EFFICIENCY.md): same work, **63% cheaper**); add
each layer in turn ([RESULT_3](RESULT_3_PROTOCOL_LADDER.md): 0% → 100%
completion up the ladder); switch on the **gate** (blocks a wrong message
before delivery) and the **scheduler** (only wakes the agent whose turn it
can be) — [RESULT_4](RESULT_4_FULL_STACK.md): the full stack is
simultaneously the **safest and the cheapest** setting, 9× cheaper than
the same plan pasted as text. And the whole thing runs without any cloud
dependency, on independent Claude agents
([RESULT_5](RESULT_5_SUBAGENT_VALIDATION.md)).

### Act 4 — Result: stress-tested, scaled, and run on every real case

The instruments themselves were tested (checker catches 95.6% of injected
plan faults with zero false alarms; the gate goes 0%→100% blocked as
layers add — [RESULT_6](RESULT_6_BENCHMARK_HARDENING.md)); everything was
re-run at n=100 ([RESULT_7](RESULT_7_N100_SCALE.md)); and **all nine real
cases** — teams built from files mined from public repositories — now have
executed benchmarks, including the two corrected looping cases run on
2026-07-15 ([RESULT_10](RESULT_10_PR_REVIEW_MERGE.md),
[RESULT_11](RESULT_11_DOC_COAUTHOR_SHIP.md)). The scoreboard is below.

## The real-case scoreboard (all nine, with benchmarks)

Nine cases are built from **real external sources** (every source file
deep-linked in each case's `SOURCES.md`). All nine have executed benchmark
runs. "No plan" = the real files as downloaded; "plan as text" = the
corrected plan pasted into every agent's instructions; "full STJP" =
contract + gate + scheduler.

| # | Real case (source) | No plan | Plan as text | Full STJP | Report |
|---|---|---|---|---|---|
| 1 | [airline_seat](../../experiments/cases/skills_safety/airline_seat/) (OpenAI Agents SDK, MIT) | 0 of 10 finished — all 10 deadlocked | 10/10 but **10 double seat-writes** | **10/10, 0 disasters, cheapest** | [RESULT_8](RESULT_8_SKILL_SAFETY.md) |
| 2 | [booking_saga](../../experiments/cases/skills_safety/booking_saga/) (LangGraph, MIT) | 0 of 10 finished — all 10 stalled | 10/10 but **10 double charges** | **10/10, 0 disasters** | [RESULT_8](RESULT_8_SKILL_SAFETY.md) |
| 3 | [code_execution](../../experiments/cases/skills_safety/code_execution/) (AutoGen, MIT code license) | 0 of 10 finished — all 10 deadlocked | 10/10 | **10/10, cheapest** | [RESULT_8](RESULT_8_SKILL_SAFETY.md) |
| 4 | [content_pipeline](../../experiments/cases/skills_safety/content_pipeline/) (CrewAI examples — pattern only, repo unlicensed) | 0 of 10 finished — all 10 stalled | 10/10 | **10/10, cheapest** | [RESULT_8](RESULT_8_SKILL_SAFETY.md) |
| 5 | [doc_pipeline](../../experiments/cases/skills_safety/doc_pipeline/) (anthropics/skills, Apache-2.0) | model-dependent coin flip (Haiku finished 10/10; **Sonnet finished 0 of 10**) | 20/20 but 120 rule-breaking msgs/run | **20/20 both models, 0 rule-breaking, ~3× cheaper** | [RESULT_9](RESULT_9_REAL_SKILLS_TWO_MODELS.md) |
| 6 | [pr_merge](../../experiments/cases/skills_safety/pr_merge/) (awesome-copilot, MIT) | coin flip (**Haiku finished 0 of 10**; Sonnet finished 10/10) | 20/20 but 120 rule-breaking msgs/run | **20/20 both models, 4 calls/trial** | [RESULT_9](RESULT_9_REAL_SKILLS_TWO_MODELS.md) |
| 7 | [agenticpay_settlement](../../experiments/cases/agenticpay_settlement/) (AgenticPay benchmark, MIT) | deadlock at **all 3 model tiers** | — | **completes at all 3 tiers, 7 messages** | [live run](../../experiments/cases/agenticpay_settlement/RESULTS_LIVE_SUBAGENTS.md) |
| 8 | [pr_review_merge](../../experiments/cases/skills_safety/pr_review_merge/) (awesome-copilot, MIT; corrected looping protocol) | 0 of 10 finished — all 10 deadlocked by round 2 | **0 of 10 finished — all 10 livelocked**, 42k tokens/trial burned | **10/10, 0 violations, 3.6× cheaper than the failing text arm** | [RESULT_10](RESULT_10_PR_REVIEW_MERGE.md) |
| 9 | [doc_coauthor_ship](../../experiments/cases/skills_safety/doc_coauthor_ship/) (anthropics/skills, Apache-2.0; corrected looping protocol) | 0 of 10 finished — all 10 hit the round budget | 10/10 but 220 rule-breaking msgs | **10/10, 0 violations, ~40% cheaper** | [RESULT_11](RESULT_11_DOC_COAUTHOR_SHIP.md) |

One additional case, [trade_deadlock](../../experiments/cases/trade_deadlock/),
is deliberately **not** counted as real: its skills were authored in-house
(with documented lineage) — see its
[`SOURCES.md`](../../experiments/cases/trade_deadlock/SOURCES.md). Its runs
back RESULT_1 and RESULT_7.

## The reports, one question each

### [RESULT_1 — Can anything except a compiler catch a deadlock?](RESULT_1_DEADLOCK.md)
**Why:** a deadlock (two agents each waiting forever for the other) burns money
and delivers nothing — and it is invisible in the written instructions.
**What it detects:** whether the static check — the compiler pass that
inspects the plan *before* running — is genuinely necessary, or whether
careful prose is enough.
**Result:** unchecked rules: 0 of 6 trials finished, zero messages exchanged,
infinite cost. Compiler-checked plan: 6 of 6 finished first try. Bonus
finding: of 10 AI-drafted plans, only 3 were safe — the compiler caught all 7
unsafe ones.
**Takeaway:** the deadlock is caught in milliseconds before spending, or
discovered at full price after. There is no middle option.

### [RESULT_2 — Does a per-agent contract make the same work cheaper?](RESULT_2_TOKEN_EFFICIENCY.md)
**Why:** most multi-agent spend goes to agents *figuring out whose turn it is*,
not doing work.
**What it detects:** the pure cost effect of giving each agent only its own
slice of the plan (its "contract"), on a task every setting completes.
**Result:** same finished report at 8,800 tokens with a lean contract vs
24,100 with none — **63% cheaper**, twice as fast.
**Takeaway:** a contract removes deliberation; the agent already knows what to
send, to whom, when.

### [RESULT_3 — Does each added layer of protocol support help?](RESULT_3_PROTOCOL_LADDER.md)
**Why:** to see the whole staircase, not just its two ends.
**What it detects:** how outcomes change step by step: no plan → rejected plan
→ plan pasted as text → per-agent contracts.
**Result:** 0% → 10% → 40% → 60–100% of trials completing correctly.
**Takeaway:** each layer pays; the best place to see, with real message
traces, what a "violation" concretely looks like.

### [RESULT_4 — Is the full STJP stack the safest AND the cheapest?](RESULT_4_FULL_STACK.md)
**Why:** safety features usually cost extra; we tested whether these do.
**What it detects:** whether contract + gate (a program that blocks a
wrong message before delivery) + scheduler (a program that only wakes an agent
whose turn it can be) beats every simpler setting on *both* axes — safety AND
cost — at once. The
predictions were written down and committed before the run — so the grading
is honest.
**Result:** 100% completion, 0 disasters, 13,300 tokens per delivered report —
**9× cheaper** than the same plan pasted as text, 4× faster.
**Takeaway:** the structure does the work, so you stop paying agents to think
about coordination.

### [RESULT_5 — Does it all work without Azure, with independent Claude agents?](RESULT_5_SUBAGENT_VALIDATION.md)
**Why:** to rule out that earlier results depended on one cloud stack or model.
**What it detects:** the same machinery driven by independently spawned Claude
agents, plus the newer components (skill compaction, protocol extension).
**Result:** unchecked prose skills 0/10 (all deadlock) vs STJP 10/10 at the
minimum possible number of AI calls; the compaction pipeline flagged the
unsafe design 10/10 and an AI repaired it first-try 10/10.
**Takeaway:** the guarantees travel across runtimes and models.

### [RESULT_6 — Can we trust our own measuring instruments?](RESULT_6_BENCHMARK_HARDENING.md)
**Why:** a benchmark is worthless if the checker misses bad plans or the gate
can be talked around.
**What it detects:** deliberately broken plans (does the checker catch them?),
deliberate attack messages (does the gate block them?), and the statistics
(how confident can we be after n runs?).
**Result:** checker caught 95.6% of injected faults with zero false alarms;
the gate went 0% → 100% blocked as layers were added; the confidence math is
worked out explicitly.
**Takeaway:** the testers were tested.

### [RESULT_7 — Does everything hold at 100× the trials?](RESULT_7_N100_SCALE.md)
**Why:** 10 trials can hide luck; 100 trials pin the numbers down.
**What it detects:** every deterministic benchmark re-run at n=100.
**Result:** unchecked 0/100 vs STJP 100/100; the statistical confidence range
narrows from "somewhere between 72–100%" to "96.3–100%".
**Takeaway:** the n=10 findings were not luck.

### [RESULT_8 — What happens with REAL skills from public repositories?](RESULT_8_SKILL_SAFETY.md)
**Why:** all earlier cases were written by us; real developers download agent
instructions from public repos (OpenAI Agents SDK, CrewAI, AutoGen, LangGraph
examples) and combine them.
**What it detects:** whether real, well-written, benign public skills are safe
to *combine* — and whether the compiler can tell you in advance.
**Result:** the compiler rejected all 4 combined plans at design time — and at
runtime every unvalidated trial failed (40/40). Writing the contract in as
text fixed completion but caused 20 double-charge/double-write disasters;
full STJP: 100% success, 0 disasters, cheapest. An n=100 re-run with a
stronger model (Sonnet) confirmed it: the weak settings fail *differently*
under a different model, but the compiler's design-time rejection doesn't
change.
**Takeaway:** each skill can be individually fine and the *combination* still
unsafe; only the plan-level check sees that.

### [RESULT_9 — Same real-skills test, run on two different models](RESULT_9_REAL_SKILLS_TWO_MODELS.md)
**Why:** the obvious objection to RESULT_8: "just use a smarter model."
**What it detects:** two new teams built from **Anthropic's and GitHub
Copilot's own public skill files**, the identical grid run twice — once with
a small model (Haiku), once with a mid-tier model (Sonnet) playing every role.
**Result:** with no plan, the small model finished one team's job 0 times
out of 10 and the smarter model finished the *other* team's job 0 times
out of 10 — same files, unpredictable failure. With full STJP both models: 40/40, zero rule-breaking messages,
exactly 4 AI calls per trial, ~3× cheaper.
**Takeaway:** a smarter model moves the failure around; the plan removes it.
With STJP the cheapest model performs like the expensive one.

### [RESULT_10 — The corrected code-review case: a loop, two concurrent reviewers, and a livelock](RESULT_10_PR_REVIEW_MERGE.md)
**Why:** re-reading the real awesome-copilot files showed the earlier pr_merge
protocol was too simple — real review is a multi-round loop with two
concurrent reviewers and a merge gated on both approvals. Does everything
still hold on the *faithful* protocol shape?
**What it detects:** the first live run of a looping (rec/choice) protocol
through the trial engine, and a failure mode linear cases cannot show.
**Result:** no plan: 0 of 10 finished (all 10 deadlocked in 2 rounds). Plan as text: **0 of 10 finished — a
one-word label mismatch produced a stable livelock** burning 42k tokens per
trial. Full STJP: 10/10, zero violations, with the gate visibly correcting
20 wrong-peer sends, at 3.6× less than the failing text arm.
**Takeaway:** on looping protocols, a text plan is not merely wasteful — it
can fail outright. Enforcement is what survives loops.

### [RESULT_11 — The corrected announcement case: the loop lives where the files put it](RESULT_11_DOC_COAUTHOR_SHIP.md)
**Why:** the earlier doc_pipeline case miscast a styling skill as an approval
gate; the corrected case puts the revision loop where the real files put it
(the document lead's reader test) and makes brand styling a transform step.
**What it detects:** the second looping real case, same three settings.
**Result:** no plan: 0 of 10 finished (all 10 hit the round budget, ~23k tokens/trial wasted). Plan
as text: 10/10 but 220 rule-breaking messages. Full STJP: 10/10, zero
violations, ~40% cheaper and 2.6× fewer AI calls than plan-as-text.
**Takeaway:** same story as nine cases before it — the structure, not the
model, does the work.

## Older files kept for history

- [`RUN_REPORT_2026-06-11.md`](RUN_REPORT_2026-06-11.md),
  [`RUN_REPORT_2026-06-17.md`](RUN_REPORT_2026-06-17.md) — raw technical run
  notes from June; their findings were rewritten in plain language as
  RESULT_3 and RESULT_4.
- [`RESULTS.md`](RESULTS.md) — the earliest experiment (May), on a legacy
  runner that has since been deleted. Kept because its monitoring approach is
  still the one used everywhere.

## Where the raw numbers live

Every report ends with a "where the raw data is" section pointing into
`experiments/` (message-by-message traces, per-run scoreboards). To re-derive
any number yourself, follow
[`../reference/HOW_TO_USE_TRACES.md`](../reference/HOW_TO_USE_TRACES.md).
The two 2026-07-15 runs' scoreboards live in
[`experiments/subagent_trials/reports/ss2026_corrected_cases/`](../../experiments/subagent_trials/reports/ss2026_corrected_cases/).
