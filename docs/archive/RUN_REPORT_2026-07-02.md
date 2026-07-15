# Run Report — 2026-07-02 (the pre-registered execution-plane run)

Grades the predictions of `../archive/EXPERIMENT_DESIGN_V3_EXECUTION.md` (written and
committed before the run) against real data. Finance case, gpt-5.4, real Azure
AI Foundry agents, n = 10 trials/arm, 7 arms, run dir
`cases/finance/runs/20260702T093703-n10-dual`. Graded with the built-in Set A/B
evaluators plus `severity_grader.py` and `criticality_gate.py` (all 7 arms).

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Headline table](#1-headline-table)
- [2. Grading the pre-registered predictions](#2-grading-the-pre-registered-predictions)
- [3. What changed mechanically vs prior runs](#3-what-changed-mechanically-vs-prior-runs)
- [4. Where to see the traces](#4-where-to-see-the-traces)
- [5. Infrastructure incidents (for reproducibility)](#5-infrastructure-incidents-for-reproducibility)
- [6. Honest limits, unchanged](#6-honest-limits-unchanged)
<!-- MENU:END -->

## 1. Headline table

GCR = strict goal-completion rate. Disasters = severity S4 (irreversible act
before authorization). Cost of success = tokens/trial ÷ GCR. CGC = goals AND
all critical properties (C1 provenance, C2 context, C3 authorization).

| arm | GCR | S4 | CGC | tokens/trial | calls/trial | sec/trial | **cost of success** |
|---|---|---|---|---|---|---|---|
| A `bare` (intent only) | 0% | **18** | 0% | 71.3k | 58.2 | 206 | ∞ |
| B-orch `maf_groupchat_llmvalid`† | 70%† | 0 | 70% | 19.3k | 10.6 | 37 | 27.6k† |
| B-dec `global_decentralized` | 100% | 0 | 100% | 120.3k | 41.8 | 124 | 120.3k |
| C-min `min_llmvalid` (observer) | 60% | 0 | 60% | 86.5k | 84.9 | 223 | 144.1k |
| C+spec `spec_llmvalid_gate` | 90% | 0 | 70%* | 82.0k | 45.8 | 127 | 91.1k |
| **C+min `min_llmvalid_gate`** | **100%** | 0 | **100%** | 38.0k | 34.0 | 96 | 38.0k |
| **STJP `min_llmvalid_sched`** | **100%** | **0** | **100%** | **13.3k** | **11.4** | **32** | **13.3k** |

† 3 of B-orch's 10 trials died to client-side HTTP 400 errors from the
agent-framework OpenAI client (the library had to be upgraded mid-experiment;
see §5). All 7 trials that actually ran completed. Treat B-orch's numbers as a
caveated reference, not a clean measurement.
\* C+spec's CGC dip is the known zero-value coverage-proxy noise
(RUN_REPORT_2026-06-17 §2), not a real safety gap; its C2-coverage reads 78%
with C1/C3 at 100%.

**The one-sentence result: the full STJP stack — statically projected skill +
enforcement gate + EFSM scheduler, all derived from one validated protocol —
is simultaneously the safest (100% GCR, 0 disasters, 100% CGC) and the
cheapest and fastest arm in the study (13.3k tokens, 11.4 calls, 32s per
delivered report — 9× cheaper than the same protocol pasted as text on the
same runner).**

## 2. Grading the pre-registered predictions

**P1 (correctness, unconfounded) — the falsifier branch fired, and it's
informative.** Predicted: B-dec (global text, no orchestrator) would slip
below 100%. Observed: B-dec reached 100% GCR / 0 disasters — gpt-5.4
self-complies with pasted protocol text even without an orchestrator holding
roles back. As pre-registered for this outcome: the correctness case for
enforcement on this case/model rests on *guarantee* (the gate rejected 10–12
off-contract send attempts per gate arm — the model did try to stray;
`gated` markers in the events files) and *audit trail*, not on outcome
superiority. The safety point stands where it always did: A (intent-only)
committed 18 disasters and completed nothing; every protocol-holding arm had
zero disasters. Unexpectedly, B-orch — the arm whose 100% was the old
headline — came in at 70% even discounting the infra failures' cause (its 3
lost trials were client errors), so "orchestrated global text" is no longer
the outcome benchmark it was; B-dec is, at 9× the STJP price.

**P2 (tokens) — confirmed, beyond the predicted margin.** Predicted ≥60% call
reduction vs C+min and lowest cost of success among decentralized arms.
Observed: 11.4 vs 34.0 calls (−66%) and 13.3k vs 38.0k tokens (−65%) against
the identical-prompt, identical-enforcement round-robin gate; 13.3k vs 120.3k
(−89%) against global-text-on-the-same-runner. Mechanism check passed:
prompt tokens per call are flat (1.12k sched vs 1.07k gate) — the entire
saving is the scheduler never polling idle agents, exactly what the offline
oracle predicted (−83% calls) now reproduced with real LLM agents. Wall-clock
followed: 32s vs 96s per trial.

**P3 (skill vs text, same plane) — half-confirmed, honestly mixed.** The lean
projected skill without enforcement (C-min) does NOT beat global text on
completion: 60% vs B-dec's 100%. Its failures are stalls (S3 liveness, 0
protocol violations — the agent parks at a state it should act in), the same
50–60% stall pattern as prior runs. Projection converts its per-call token
advantage (1.0k vs 2.8k prompt tokens/call vs B-dec) into equal-or-better
reliability only when paired with its execution plane: +gate = 100% at 1/3 of
B-dec's cost; +gate+scheduler = 100% at 1/9.

**P4 (orchestrator accounting) — inconclusive this run.** B-orch's 400-error
losses make its 70% unattributable between model and client library. Prior
stability runs (2026-06-17: 100%, 26.5k cost-to-goal) remain the best
reference for orchestrated global text. Even taking that older number at face
value, STJP now undercuts it by 2× on cost with equal outcome — the first
time a projected arm beats B on cost anywhere in this benchmark.

## 3. What changed mechanically vs prior runs

- New runner mode `FoundryRunner(schedule="efsm")`: polls only roles whose
  projected local state has an enabled SEND (requires the gate so monitor
  state tracks committed reality). One agent call per protocol message plus
  ~0.4 overhead — polling waste eliminated.
- New arms `min_llmvalid_gate` (decomposes enforcement from contract
  verbosity) and `min_llmvalid_sched` (the full stack).
- The gate arms this run show real interventions (10–12 rejected sends per
  arm): enforcement is doing work, not just the liveness nudge.
- C+spec (90%) vs C+min (100%): the lean contract slightly *outperformed* the
  verbose one under enforcement — consistent with the 8000-char install
  truncation penalizing verbose prompts, and more evidence for lean-by-default.

## 4. Where to see the traces

Azure AI Foundry portal: Agents named `stjp-finance-<arm>-<role>`; one thread
per role per attempt (metadata: case/role/scenario); Application Insights
tracing under service `stjp-case-runner`. The B-orch arm uses direct Azure
OpenAI chat completions (no Agent Service threads by design); as of this run
its calls are captured in the Tracing tab via the OpenTelemetry OpenAI
instrumentation installed 2026-07-02.

## 5. Infrastructure incidents (for reproducibility)

1. A `git pull --rebase` executed during the first launch briefly emptied the
   working tree and killed 4 arms mid-Scribble-call; that run was discarded
   and relaunched clean. Rule: no history-rewriting git operations during live
   runs.
2. The az CLI default subscription was flipped twice by an external process
   mid-run, minting wrong-tenant tokens (`Tenant provided in token does not
   match resource token`). Fixed durably: `AzCliCredential` now pins
   `STJP_AZURE_TENANT_ID` from `stjp_core/.env`.
3. `agent_framework` had to be upgraded (user-site beta lacked the `Agent`
   export) for the B-orch arm; the upgraded client threw HTTP 400s on 3/10
   trials. The 6 Foundry-stack arms are unaffected (different SDK).
4. `stjp_core/.venv` is no longer the runner env (rebuilt as the Flask demo
   env); runs use `C:\Python313\python.exe`.

## 6. Honest limits, unchanged

- This case/model shows the *protocol* (however delivered) fixes correctness;
  enforcement's necessity still needs the criticality two-variant design
  (`../archive/BENCHMARK_DESIGN_V3_CRITICALITY.md`).
- The contract-size token lever is shown on `report_pipeline`
  (TOKEN_EFFICIENCY_DEMO), not here — finance is too small; this run isolates
  the scheduling lever.
- B-orch needs a clean re-run on the fixed client before any claim about
  orchestrated baselines from this run's data.
