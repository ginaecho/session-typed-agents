# The results, in order — what we tested, why, and what we learned

This folder holds the evidence for every claim STJP (Session-Typed Judge
Panel — this project's system for checking and enforcing a team of AI agents'
coordination plan) makes. Each numbered
report (RESULT_1 … RESULT_9) answers **one question**, and they build on each
other — read them in order the first time.

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
**Result:** with no plan, the small model failed one team 0/10 and the
smarter model failed the *other* team 0/10 — same files, unpredictable
failure. With full STJP both models: 40/40, zero rule-breaking messages,
exactly 4 AI calls per trial, ~3× cheaper.
**Takeaway:** a smarter model moves the failure around; the plan removes it.
With STJP the cheapest model performs like the expensive one.

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
