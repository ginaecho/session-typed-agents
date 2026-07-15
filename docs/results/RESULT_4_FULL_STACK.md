# Result 4 — The full STJP stack is the safest AND the cheapest (latest headline)

**Measured 2026-07-02. Case: `finance`. Model: gpt-5.4, real Azure AI Foundry agents. 7 settings × 10 trials. Pre-registered: the predictions were written and committed *before* the run, then graded honestly against the data.**

> **At a glance:** The full STJP stack — projected per-agent contract + enforcement gate + protocol-driven scheduler, all derived from one validated protocol — was simultaneously the **safest** setting (100% completion, 0 disasters) and the **cheapest and fastest** (13,300 tokens, 11.4 model calls, 32 seconds per delivered report). That is **9× cheaper** than the same validated protocol pasted as text on the same runtime, with the same perfect outcome.

Run directory: `experiments/cases/finance/runs/20260702T093703-n10-dual`.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The story at a glance (STAR)](#the-story-at-a-glance-star)
- [How this experiment is set](#how-this-experiment-is-set)
- [1. The headline table](#1-the-headline-table)
- [2. What each setting adds (reading the table top to bottom)](#2-what-each-setting-adds-reading-the-table-top-to-bottom)
- [3. Grading the pre-registered predictions (the honest part)](#3-grading-the-pre-registered-predictions-the-honest-part)
- [4. What changed mechanically vs earlier runs](#4-what-changed-mechanically-vs-earlier-runs)
- [5. Where to see the traces](#5-where-to-see-the-traces)
- [6. Infrastructure incidents (recorded for reproducibility)](#6-infrastructure-incidents-recorded-for-reproducibility)
- [7. Honest limits, unchanged](#7-honest-limits-unchanged)
- [8. Where the raw data is](#8-where-the-raw-data-is)
- [Run it on Azure AI Foundry (later)](#run-it-on-azure-ai-foundry-later)
<!-- MENU:END -->

## The story at a glance (STAR)

- **Situation** — On the `finance` case, run on real Azure AI Foundry hosted agents, seven settings are compared with predictions written and committed *before* the run so the grading is honest.
- **Task** — Determine whether the full STJP stack — projected per-agent contract + enforcement gate + protocol-driven scheduler — is simultaneously the safest and the cheapest way to run the case, against 6 other settings including intent-only and validated-text baselines.
- **Action** — 7 settings x 10 trials, gpt-5.4, real Azure AI Foundry hosted agents, pre-registered predictions graded against the resulting data.
- **Result** — Full STJP stack: **100%** completion, **0** disasters, **13,300 tokens**, **11.4** model calls, **32 seconds** per delivered report — **9x cheaper** than the same validated protocol pasted as text on the same runtime, with the same perfect outcome.

## How this experiment is set

- **Case(s):** [`finance`](../../experiments/cases/finance/)
- **Arms/settings:** 7 — intent only; validated text + central orchestrator; validated text, decentralized; lean contract, monitor only; full contract + gate; lean contract + gate; lean contract + gate + scheduler (full STJP)
- **Trials:** 10 per arm
- **Who plays the roles:** gpt-5.4, real Azure AI Foundry hosted agents, one per role per arm (`case_runner.py` / `FoundryRunner`; the scheduler arm uses `FoundryRunner(schedule="efsm")`)
- **Isolation:** each role is a separate Foundry agent with its own thread; sees only its own thread's history and its own contract, never another role's prompt
- **Harness & budgets:** `case_runner.py`; up to 3 attempts per trial, each capped at `max_steps: 24` (`case.yaml`); predictions were pre-registered before the run (`../archive/EXPERIMENT_DESIGN_V3_EXECUTION.md`)
- **Where the raw data is:** `experiments/cases/finance/runs/20260702T093703-n10-dual/` (run directory — not committed; per-trial numbers preserved in the report tables and `summary*.json` copies referenced in this document)

## 1. The headline table

Terms used in the table:
- **Completed** — % of trials that achieved every goal on the first attempt.
- **Disasters** — count of irreversible acts done before their authorization step (the worst failure class). Total across the arm's 10 trials.
- **Safe & complete** — completed **and** satisfied all three critical properties (used real data, read all inputs, got authorization before the irreversible step).
- **Cost of success** — tokens per trial ÷ completion rate: what one *delivered* report actually costs, charging the setting for its failures.

| Setting | Completed | Disasters | Safe & complete | Tokens/trial | Calls/trial | Sec/trial | **Cost of success** |
|---|---|---|---|---|---|---|---|
| Intent only (no protocol) | 0% | **18** | 0% | 71.3k | 58.2 | 206 | ∞ |
| Validated text + central orchestrator† | 70%† | 0 | 70% | 19.3k | 10.6 | 37 | 27.6k† |
| Validated text, decentralized | 100% | 0 | 100% | 120.3k | 41.8 | 124 | 120.3k |
| Lean contract, monitor only | 60% | 0 | 60% | 86.5k | 84.9 | 223 | 144.1k |
| Full contract + gate | 90% | 0 | 70%* | 82.0k | 45.8 | 127 | 91.1k |
| Lean contract + gate | **100%** | 0 | **100%** | 38.0k | 34.0 | 96 | 38.0k |
| **Lean contract + gate + scheduler (full STJP)** | **100%** | **0** | **100%** | **13.3k** | **11.4** | **32** | **13.3k** |

† 3 of the orchestrator setting's 10 trials died to client-library errors (HTTP 400s from a mid-experiment library upgrade), not model failures. All 7 trials that actually ran completed. Treat its numbers as a caveated reference, not a clean measurement.
\* A known measurement-noise artifact in one coverage proxy, not a real safety gap — its authorization and data-provenance checks were 100%.

---

## 2. What each setting adds (reading the table top to bottom)

- **Intent only:** agents get just the task description. They committed **18 disasters in 10 trials** (filing before audit/approval) and completed nothing. This is the floor, and it is genuinely unsafe.
- **Validated protocol as text:** every setting that held the validated protocol — in any form — had **zero disasters**. The protocol does the correctness work.
- **Lean contract, monitor only (no enforcement):** 60% — agents sometimes park at a state where they should act and stall. A contract alone tells; it doesn't push.
- **+ Gate:** the gate blocks a wrong message before delivery and asks the agent to retry. Lean contract + gate = 100% at a third of the text-paste cost.
- **+ Scheduler:** instead of polling every agent each round ("anything to do?" … "WAIT"), the protocol's state machine says exactly who can act, and only they get called. Same perfect outcome, at **1/9th** the cost of the text-paste setting.

---

## 3. Grading the pre-registered predictions (the honest part)

**Prediction 1 — "text-paste without an orchestrator will slip below 100%": WRONG, and informatively so.** The decentralized text-paste setting reached 100% with zero disasters — gpt-5.4 self-complies with a pasted protocol even with no one sequencing it. As pre-registered for this outcome, the correctness case for enforcement on this case/model rests not on outcome superiority but on the **guarantee**: the gate rejected **10–12 off-contract send attempts per trial** — the model *did* try to stray; enforcement caught it every time — plus the audit trail. (Never claim the gate beats text-paste on outcomes here; the protocol does that work.)

**Prediction 2 — "the scheduler cuts ≥60% of calls": CONFIRMED, beyond the margin.** 11.4 vs 34.0 calls (−66%) and 13.3k vs 38.0k tokens (−65%) against the *identical prompts and identical enforcement* on the polling runtime — and −89% against text-paste on the same runtime. The mechanism check passed: tokens *per call* stayed flat (1.12k vs 1.07k), so the entire saving is the scheduler never polling idle agents — exactly what the offline simulation predicted (−83% calls), now reproduced with real agents. Wall-clock followed: 32s vs 96s.

**Prediction 3 — "the lean contract alone beats text-paste": HALF-CONFIRMED, honestly mixed.** Without enforcement, the lean contract does *not* beat pasted text on completion (60% vs 100%) — its failures are stalls, not rule-breaking. Projection converts its per-call cost advantage into equal-or-better reliability only when paired with its execution plane: +gate = 100% at 1/3 the cost; +gate+scheduler = 100% at 1/9.

**Prediction 4 — orchestrator accounting: INCONCLUSIVE this run.** The orchestrator setting's client-library failures make its 70% unattributable. Prior clean runs (100%, ~26.5k cost-to-goal) remain the best reference — and even against that older number, full STJP now undercuts it 2× on cost with equal outcome: the first time a projected setting beats the orchestrated baseline on cost anywhere in this benchmark.

---

## 4. What changed mechanically vs earlier runs

- New runner mode: the scheduler (`FoundryRunner(schedule="efsm")`) polls only roles whose contract has an enabled send at the current state — about one model call per protocol message, polling waste eliminated. It requires the gate, so the scheduler's view of the protocol state tracks what was actually delivered.
- Two new settings isolate the pieces: *lean + gate* (separates enforcement from contract verbosity) and *lean + gate + scheduler* (the full stack).
- The gate did real work this run: 10–12 rejected sends per gate setting (`gated` markers in the event logs) — not just liveness nudges.
- The lean contract slightly *outperformed* the verbose one under enforcement (100% vs 90%) — consistent with the 8,000-character prompt-install limit penalizing verbose contracts, and more evidence for lean-by-default.

## 5. Where to see the traces

Azure AI Foundry portal (see `../reference/FOUNDRY_VISIBILITY.md` and `../1_TECH_SETUP.md` section 5):
- **Agents:** named `stjp-finance-<setting>-<role>`
- **Threads:** one per role per attempt (metadata records case/role/setting)
- **Tracing:** Application Insights, service name `stjp-case-runner`. The orchestrator setting bypasses the Agent Service by design; its calls appear only in the Tracing tab.

## 6. Infrastructure incidents (recorded for reproducibility)

1. A `git pull --rebase` during the first launch briefly emptied the working tree and killed 4 settings mid-run; that run was discarded and relaunched clean. **Standing rule: no history-rewriting git operations during live runs.**
2. The Azure CLI's default subscription was flipped twice mid-run by an external process, producing wrong-tenant tokens. Fixed durably: the credential helper now pins the tenant ID from `stjp_core/.env`.
3. The `agent_framework` library had to be upgraded mid-experiment for the orchestrator setting; the upgraded client threw the HTTP 400s noted above. The other 6 settings use a different SDK and were unaffected.
4. Runs use `C:\Python313\python.exe` — `stjp_core/.venv` is no longer the runner environment.

## 7. Honest limits, unchanged

- On this case and model, the *protocol* (however delivered) fixes correctness; proving enforcement is *necessary* still needs the criticality two-variant design (`../archive/BENCHMARK_DESIGN_V3_CRITICALITY.md`).
- The contract-**size** token lever is shown in [`RESULT_2_TOKEN_EFFICIENCY.md`](RESULT_2_TOKEN_EFFICIENCY.md), not here — the finance protocol is too small for it; this run isolates the **scheduling** lever.
- The orchestrator baseline needs a clean re-run on the fixed client before any new claim about it.

## 8. Where the raw data is

- Run directory: `experiments/cases/finance/runs/20260702T093703-n10-dual/` — per-message logs (`events_<setting>.jsonl`), metrics (`summary.json`, `summary_eval.json`), severity and criticality grading, and the full per-role prompts under `prompts/<setting>/`
- Pre-registered design (written before the run): `../archive/EXPERIMENT_DESIGN_V3_EXECUTION.md`

## Run it on Azure AI Foundry (later)

This run already used real Azure AI Foundry-hosted agents directly as its harness (see "Where to see the traces" above and `../reference/FOUNDRY_VISIBILITY.md`). The standard recipe for setting up or extending Foundry-hosted STJP runs is in [`1_TECH_SETUP.md` section 5](../1_TECH_SETUP.md#5-running-stjp-with-azure-ai-foundry-hosted-agents) plus the four registration points listed in [`experiments/CLAUDE.md`](../../experiments/CLAUDE.md) (`registry.py` SCENARIOS, `case_runner.py` `_FOUNDRY_INSTALL_KEYS` and `FOUNDRY_KEYS`, `evaluate_run.py` `VOCABULARY_ARMS`).
