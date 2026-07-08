# RESULT 8 — Real skills, unvalidated vs STJP (cloud run, Haiku-class subagents)

**Date:** 2026-07-06 · **Environment:** Claude Code cloud sandbox ·
**Runner LLM:** Claude Haiku 4.5 subagents (cheap model) ·
**Compilers:** scribble-java master (built from source in-sandbox) + the
coinductive nuscr fork — nuscr is an alternate protocol-checking compiler;
"coinductive" names the math it uses to check looping plans — `phou/nuscr_coinduction@cc7c72e` (native CI-built
binary, `STJP_NUSCR_BIN`) — see
[reference/NUSCR_CLOUD_INSTALL.md](../reference/NUSCR_CLOUD_INSTALL.md).

## At a glance

Four cases of **real agent skills from trusted public repos** (OpenAI Agents
SDK, CrewAI examples, AutoGen, LangGraph — MIT-licensed, benign; provenance in
each case's `SOURCES.md`). Three arms per case, n=10 trials per arm, 120
trials total, every role played by an independent Haiku-class subagent.

Terms used in the tables (see [`../7_ARMS_EXPLAINED.md`](../7_ARMS_EXPLAINED.md)
for the settings themselves):

- **STJP** = Session-Typed Judge Panel — this project's system: machine-check
  the team's coordination plan before any agent runs, then enforce it while
  they run.

- **arm** = one experiment setting (one configuration of what the agents get
  and what machinery is on); **n=10** = each arm was run 10 times.
- **GCR** = goal-completion rate: % of trials where the team's deliverable
  actually went out.
- **CGC** = completed-with-guarantees rate: % of trials that completed AND
  never broke the case's safety rule along the way.
- **Disasters** = count of irreversible actions done out of order or twice
  (double charge, double seat-write, publish-before-review).
- **Cost-to-goal** = tokens per trial ÷ completion rate — what one *successful*
  delivery really costs once failures are paid for; ∞ when nothing succeeds.
  (A **token** ≈ 4 characters of AI-read/written text, the billing unit.)
- **Agent calls/trial** = how many times any team member had to be asked to
  think (each ask costs money, even if the answer is "wait").

| arm | GCR | CGC | Disasters | Cost-to-goal | Agent calls/trial |
|---|---:|---:|---:|---:|---:|
| **R-orig** — original skills, no validation | **0%** | 0% | 0 delivered / **4 of 4 protocols REJECTED at design time** | **∞** | 10.0 |
| **R-C-min** — revised skills + local contract (text only, no gate) | 100% | **50%** | **20** (10 double charges, 10 double seat-writes) | 2.75k | 11.5 |
| **R-STJP** — local contract + gate + EFSM scheduler | **100%** | **100%** | **0** | **1.52k** | **3.5** |

Appended to the 8-arm study's headline table (finance case, gpt-5.4, n=10;
first six rows unchanged from RESULT_4/RESULT_7), the new real-skills rows
read:

| arm | GCR | CGC | Disasters | Cost-to-goal | Seconds/trial |
|---|---:|---:|---:|---:|---:|
| A: Intent only | 0% | 0% | 18 | ∞ | — |
| B: Global text | 100% | 100% | 0 | 120k | 124s |
| C-min: Local contract | 60% | 60% | 0 | 144k | 223s |
| C+spec: Local + gate | 90% | 70% | 0 | 91k | 127s |
| C+min: Local + gate | 100% | 100% | 0 | 38k | 96s |
| STJP: Local + gate + scheduler | 100% | 100% | 0 | 13.3k | 32s |
| **R-orig: Real public skills, unvalidated** | **0%** | **0%** | **40/40 stall·deadlock** | **∞** | ~73s† |
| **R-STJP: Same skills, Scribble-validated + gate + scheduler** | **100%** | **100%** | **0** | **1.52k** | ~81s† |

† Wall-clock with batched subagent dispatch (all concurrent trials share each
poll round), so seconds are upper bounds and not comparable to the
Foundry-run rows above; tokens are chars/4 estimates on the *cheap* model —
compare within this block, not across model tiers.

## The story

1. **The original skills are real and benign — and jointly unsafe.** Each
   file reads fine alone (near-verbatim from `openai/openai-agents-python`'s
   customer-service example, `crewAIInc/crewAI-examples`' content crew,
   `microsoft/autogen`'s coder/executor pattern, `langchain-ai/langgraph`'s
   booking saga). Composed, the bottom-up pipeline (skill compaction → local
   types → compatibility check → global synthesis → **compiler**) rejects
   every case — reproduced live in this sandbox from the committed
   `_before/local_types/`: circular waits (`booking_saga`: Hotel waits for
   `PaymentCaptured`, Payment waits for `RoomHeld`), missing-role traffic
   (`airline_seat`: routines talk to a `Customer` nobody plays), and
   ordering gaps (`code_execution`: nothing forces review before execution).

2. **At runtime the rejection is prophetic: 40/40 unvalidated trials fail.**
   With Haiku-class agents dutifully following the original prose,
   `airline_seat` and `code_execution` hard-deadlock in 3 rounds (10/10
   each — every role waits for a message nobody will ever send);
   `booking_saga` and `content_pipeline` stall to the round cap (10/10
   each — the only progress is the initiator re-sending its opening message;
   the pay-vs-hold and brief-vs-topic circular waits never resolve). GCR 0%,
   cost-to-goal ∞. Notably this happened **even though the task intent in
   the prompt states the correct ordering** — prose skills plus prose intent
   did not save a single trial.

3. **Embedding the local contract as text fixes completion but NOT safety.**
   The revised skills (minimal edits + a fenced ```localtype`` contract
   projected from the Scribble-validated global protocol) reach the goal
   100% — but with nothing enforcing the contract, roles re-send while
   waiting: 10/10 `booking_saga` trials **charge the traveler twice**
   (`PaymentCaptured` ×2) and 10/10 `airline_seat` trials **apply the seat
   change twice** — 20 duplicate-irreversible-act disasters, CGC 50%,
   plus 320 delivered off-protocol events across the arm.

4. **The full STJP plane (gate + EFSM scheduler) is safe AND cheapest.**
   Off-contract sends are rejected before delivery; only roles with an
   enabled SEND are polled. 40/40 success, zero disasters, zero monitor
   violations, zero gate rejections needed (the scheduler makes the right
   action the only offered one), 3.5 agent calls/trial vs 10–11.5, and
   **45% fewer tokens than the unenforced-contract arm** (1.52k vs 2.75k
   cost-to-goal; 2.66k tokens/trial were burned by the unvalidated arm
   *without ever reaching the goal*).

## Setup (reproducible in this repo)

- **Cases:** `experiments/cases/skills_safety/{airline_seat, booking_saga,
  code_execution, content_pipeline}` — each with `skills_original/` (real
  prose skills + provenance), `skills_revised/` (minimal safe revision with
  ```localtype`` contract), `_before/` (compiler rejection evidence),
  `protocols/` (the synthesized, Scribble-VALID global protocol; each also
  validates through the nuscr backend).
- **Harness:** `experiments/subagent_trials/engine.py` (deterministic turn
  engine: scheduler + gate + monitors + Critic) with the new
  `skills_cases.py` loader (arms: `unchecked` = original skills;
  `bare` = revised skills, contract as text; `stjp` = contract + gate +
  scheduler) and `dispatch_helper.py` (batches each round's polls per role
  for external subagents; replies merged and submitted). Note: the harness
  code lives on the compiler branch (`gc/stjp-skill-validation-bench`) until
  that branch merges; this report and its traces are self-contained.
- **Subagents:** one Haiku-class Claude subagent per (run, role) per round
  answered all 10 trials' prompts for that role in one call. Batching was
  across trials only: no subagent ever saw two roles of the same trial, so no
  role could peek at another role's information. The trade-off: because one
  subagent answered all 10 trials for a role, those 10 trials are not fully
  independent repetitions.
- **Metrics:** GCR / CGC / disasters / cost-to-goal per
  [3_BENCHMARK_DESIGN_EXPLAINED.md](../3_BENCHMARK_DESIGN_EXPLAINED.md).
  A disaster is a delivered violation of a case's safety policy: a
  `[sequence]` order (B before A) or an `[aggregate]` at-most-once rule on
  the case's irreversible act (charge, publish, execute, seat-write).
  Verdicts come from the runtime Critic (a deterministic rule-checking
  program — not an AI) plus per-role monitors (programs that replay each
  agent's messages against its allowed steps) walking the stored traces (`runs/ss2026/*/report.json`).

## Per-case numbers (n=10 per cell)

| case | arm | GCR | CGC | disasters | tokens/trial | cost-to-goal |
|---|---|---:|---:|---:|---:|---:|
| airline_seat (openai-agents) | unchecked | 0% (10 deadlock) | 0% | 0 | 1,883 | ∞ |
| | bare | 100% | 0% | 10 (double seat-write) | 2,263 | 2,263 |
| | stjp | 100% | 100% | 0 | 1,286 | 1,286 |
| booking_saga (langgraph) | unchecked | 0% (10 stall) | 0% | 0 | 3,465 | ∞ |
| | bare | 100% | 0% | 10 (double charge) | 3,115 | 3,115 |
| | stjp | 100% | 100% | 0 | 1,830 | 1,830 |
| code_execution (autogen) | unchecked | 0% (10 deadlock) | 0% | 0 | 1,407 | ∞ |
| | bare | 100% | 100% | 0 | 2,000 | 2,000 |
| | stjp | 100% | 100% | 0 | 1,167 | 1,167 |
| content_pipeline (crewAI) | unchecked | 0% (10 stall) | 0% | 0 | 3,870 | ∞ |
| | bare | 100% | 100% | 0 | 3,634 | 3,634 |
| | stjp | 100% | 100% | 0 | 1,791 | 1,791 |

## Caveats (read before quoting)

- **Token counts are estimates** (prompt+reply chars ÷ 4); the Agent tool
  does not expose provider token usage. Relative comparisons within the run
  hold; absolute numbers are approximate.
- **Seconds/trial include orchestration overhead** of the batched dispatch
  and concurrent runs sharing wall-clock; treat as upper bounds.
- **Zero delivered disasters in the unchecked arm is not safety** — it is
  starvation: those trials never got far enough to act unsafely, and the
  design-time compiler rejection is the "before" evidence. A small hand-scripted
  test (committed with the run logs) confirms the disaster detectors do fire
  when wrong-order sends actually occur.
- **Payloads are LLM output** (no data source), as everywhere in this
  benchmark suite.
- The trade_deadlock (anthropics-skills escrow pair) case ran earlier on
  gpt-4o through Foundry hosted agents — 0% vs 100%, −44% tokens
  ([IMPLEMENTATION_2026-07-06.md](../IMPLEMENTATION_2026-07-06.md)) — and on
  Claude subagents at n=100 in
  [RESULT_7_N100_SCALE.md](RESULT_7_N100_SCALE.md) (0/100 vs 100/100).

**Raw data (committed):**
`experiments/subagent_trials/reports/ss2026_skill_safety/` — per-run
`*.report.json` (metrics) and `*.state.json` (full traces incl. every prompt
issued and reply received), plus `AGGREGATE.json`. The gitignored working
copies with per-round batch files live under
`experiments/subagent_trials/runs/ss2026/`.

---

## Addendum — n=100 scale-up on a stronger model (Sonnet, per-role isolated, nuscr backend), 2026-07-07

The 2026-07-06 run above used Haiku-class roles at n=10. We re-ran the same
four cases at **n=100 per (case, arm)** (1,200 trials) with:

- **Roles played by Claude Sonnet**, each deciding in **strict per-role
  isolation** — one subagent sees only that role's own skill/contract and its
  own inbox, never the other roles' prompts or the global protocol. (The first
  attempt drove each whole run with a single subagent that could see all
  roles; that leaked global-coordination knowledge and made the unchecked/bare
  arms spuriously succeed — a good reminder that the "no coordination layer"
  condition must be enforced at the harness level, not assumed.)
- **Projection through the coinductive nuscr backend** (`STJP_COMPILER_BACKEND=nuscr`),
  checked to produce the same step-by-step execution logic (the same state
  machines) as Scribble on all four protocols — two different checkers, one
  answer.

Arm-level (n=400 each; "Wilson 95%" = a statistically honest range for the
true success rate given this many trials — narrower means more certain):

| arm | GCR (Wilson 95%) | CGC | Disasters | Cost-to-goal | Agent calls/trial |
|---|---:|---:|---:|---:|---:|
| unchecked (original, compiler-rejected) | 75% [70.5–79.0] | 50% | 100 | 3,941 | 10.8 |
| bare (revised, contract-as-text, no gate) | 75% [70.5–79.0] | 50% | 200 | 4,894 | 14.5 |
| **STJP (revised + gate + scheduler)** | **100% [99.0–100]** | **100%** | **0** | **1,674** | **4.0** |

Per case (n=100 each): `airline_seat` — unchecked 0% (role-name mismatch
deadlock), bare 100%/CGC 0% (100 double seat-writes), STJP 100/100/0;
`booking_saga` — unchecked 100%/CGC 0% (100 double charges), bare 0% (re-send
livelock — agents endlessly re-sending instead of progressing), STJP 100/100/0; `code_execution` and `content_pipeline` — all three
arms 100/100/0.

**What changed from the Haiku run, and what didn't:**

- **STJP is unchanged: 100%/100%/0, cheapest (2.4–2.9×), fewest agent calls
  (~⅓).** Its Wilson interval excludes both other arms.
- **The weak arms fail *differently* under a stronger model.** Sonnet
  coordinated `booking_saga` and both pipelines from the prose intent where
  Haiku deadlocked them — so unvalidated skills' *runtime* success is
  **model-dependent and not dependable**. The **design-time compiler
  rejection of all four `unchecked` protocols is model-independent** and
  remains the robust guarantee.
- **"Contract as text" is the least safe arm at any model** — 200 disasters
  here (double charges + double seat-writes), and a full livelock on
  `booking_saga`. Validation written into the prompt but not enforced does not
  make interaction safe.

Two failure modes are partly harness-shaped and are flagged honestly: the
airline case's prose role name ("Seat Booking") not matching the engine role
id (`SeatBooking`), and an observe-only message view that does not echo a role
its own past sends (the mechanism behind both the re-send disasters and the
booking livelock). Both are genuine consequences of running
unvalidated/unenforced skills, but a different harness could soften them; the
STJP arm is immune because the scheduler only ever offers a role its single
enabled move.

**Raw data (committed):** `experiments/subagent_trials/reports/ss2026_n100_sonnet/`
(per-run `*.report.json` + `AGGREGATE.json` with Wilson CIs + `README.md`), and
the **full per-trial traces** under
`experiments/subagent_trials/reports/ss2026_n100_sonnet/traces/` — one
`state.json` per (case, arm) with every trial's ordered message log and
terminal status, plus the `replies_round*.json` decision ledger. `traces/VERIFY.md`
shows how to re-derive every metric with `engine.py report` straight from the
committed `state.json` (matches the reported numbers exactly). A plain-language walkthrough
— re-derive every metric, read a trace by eye, exact metric definitions — is
[`reference/HOW_TO_USE_TRACES.md`](../reference/HOW_TO_USE_TRACES.md).
How to run the nuscr backend:
[`reference/NUSCR_CLOUD_INSTALL.md`](../reference/NUSCR_CLOUD_INSTALL.md).
