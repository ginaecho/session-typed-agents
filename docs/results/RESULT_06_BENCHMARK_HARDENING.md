# Result 6 — Making the evaluation bulletproof (Benchmark Plan v2)

**At a glance (2026-07-04).** Seven experiments plus a verdict corpus, each
testing ONE component of STJP so a number is attributable. Everything that can
be measured deterministically was run for real with the Scribble compiler;
everything needing multiple model families or a live LLM loop is a connected
harness with real anchors and clearly-tagged synthetic placeholders.

| What we now know (real numbers) | Result |
|---|---|
| The monitor + severity grader give the right verdict | **40/40** hand-derived traces |
| The checker catches malformed protocols | **95.6%** of well-formedness defects, **0%** false positives |
| The gate stops a hostile agent | none **0%** → keyword rules **41.7%** → structural gate **91.7%** → gate+value-guard **100%** blocked |
| n=10 is genuinely too few | a 10/10 arm has a 95% CI of **[72%, 100%]**; pass¹⁰ at the floor is **0.039** |
| We can compare two protocols by MEANING | equivalence scorer **100%** over 90 real (gold, draft) pairs — "gold" meaning a known-correct reference protocol |
| It scales | global-text coordination cost is **9×→17×** STJP's from 2→10 roles |
| Enforcement is portable | the standalone monitor matches the in-process one **100%** |

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The story at a glance (STAR)](#the-story-at-a-glance-star)
- [How this experiment is set](#how-this-experiment-is-set)
- [The three findings that matter most](#the-three-findings-that-matter-most)
- [What is still pending (honestly)](#what-is-still-pending-honestly)
- [Where everything lives](#where-everything-lives)
- [Run it on Azure AI Foundry (later)](#run-it-on-azure-ai-foundry-later)
<!-- MENU:END -->

## The story at a glance (STAR)

- **Situation** — Earlier results proved STJP works, but the benchmark measuring it needed its own hardening so every number is attributable to one component and honest about what is real vs. still pending.
- **Task** — Run seven experiments plus a verdict corpus, each isolating ONE component of STJP, using real deterministic computation wherever possible and clearly tagging anything still synthetic.
- **Action** — Deterministic runs against the Scribble compiler: a 40-trace hand-derived verdict corpus, mutation-tested checker soundness, a layered adversarial gate test (12 exfiltration attempts), Wilson-interval reliability analysis at n=10, a 90-pair equivalence scorer, and a 2-to-10-role coordination-cost scaling check.
- **Result** — Monitor + severity grader correct on **40/40** traces; checker catches **95.6%** of malformed protocols at **0%** false positives; gate blocks rise **0% → 41.7% → 91.7% → 100%** across layered defenses; a 10/10 arm's real 95% CI is **[72%, 100%]**; equivalence scorer **100%** over 90 pairs; global-text coordination cost is **9x→17x** STJP's from 2→10 roles.

## How this experiment is set

- **Case(s):** not a single live-agent case — deterministic scripts and a hand-derived verdict corpus over generated protocols and traces (see [`docs/reference/BENCHMARK_PLAN_V2.md`](../reference/BENCHMARK_PLAN_V2.md))
- **Arms/settings:** seven experiments (E1–E7, each isolating one STJP component) plus the verdict corpus; E1 (checker soundness), the verdict corpus, the gate-defense ladder, the Wilson-CI analysis, the equivalence scorer, and the coordination-cost scaling check are reported here as real numbers — E3/E5/E6/E7's live-run percentages are still pending (see "What is still pending")
- **Trials:** varies by experiment — see [`docs/reference/BENCHMARK_PLAN_V2.md`](../reference/BENCHMARK_PLAN_V2.md) for each experiment's n
- **Who plays the roles:** no LLM in the reported deterministic experiments — real Scribble-compiler runs and scripted mutation/adversarial tests; not applicable to the still-pending live-run experiments
- **Isolation:** not applicable (deterministic, no agents)
- **Harness & budgets:** `experiments/scripts/{mutation_bench,adversarial_bench,stats,translation_fidelity,efsm_equiv,roles_sweep,capability_sweep,cross_runtime,make_figs_v2}.py`; not applicable
- **Where the raw data is:** [`experiments/reports/`](../../experiments/reports/); verdict corpus in [`experiments/tests/verdict_corpus/`](../../experiments/tests/verdict_corpus/)

## The three findings that matter most

1. **We stopped grading our own homework.** The verdict corpus (§9) tests the
   *testers* — 40 traces whose answer we know by hand, run through the monitor
   and the S0–S4 grader. It passed 40/40, and it caught three of *our own*
   hand-derivations that were wrong (the instruments were right). E1 then
   mutation-tests the checker itself: it detects 95.6% of genuinely-malformed
   protocols and wrongly rejects 0% of good ones.

2. **The gate's honest number is 91.7%, not 100% — and that's the point.**
   Against 12 exfiltration attempts, a keyword blocklist is evaded seven ways
   (base64, hex, synonyms, split payloads, typos). The STJP structural gate
   blocks every *illegal-route* attempt and is disguise-proof — but one attack
   smuggled raw figures inside a *legitimately-labelled* public-summary
   message, which the gate deliberately does not inspect. Adding the value
   guard closes it to 100%. Reporting the real 91.7% and the layered fix is
   stronger and more honest than a bare "gate 100%".

3. **"n=10 always worked" is not the same as "reliable".** With Wilson
   intervals, our real 10/10 arm sits at [72%, 100%] — so pass¹⁰ at the CI
   floor is 0.039, i.e. up to a 1-in-1 chance a ten-run batch fails. This is
   the concrete, computed argument for the plan's move to n=30, not an
   assertion.

## What is still pending (honestly)

- **E3 capability sweep** (story vs model strength) — needs multiple model
  families; two real anchors already exist (gpt-4o vs gpt-5.4).
- **E5 fidelity over 100 intents**, **E6 token-per-goal**, **E7 three-harness
  comparison** — the *deterministic cores* are built and validated
  (equivalence scorer, cost proxy, standalone-monitor agreement); the
  live-run percentages need an LLM / extra adapters / Azure.

Every synthetic figure and table cell is tagged "projected (synthetic);
measurement pending" so nothing ships accidentally.

## Where everything lives

- Design + per-experiment detail: `docs/reference/BENCHMARK_PLAN_V2.md`
- Pre-registered predictions vs outcomes: `docs/predictions/BENCHMARK_V2_PREREGISTRATION.md`
- Runnable harnesses: `experiments/scripts/{mutation_bench,adversarial_bench,stats,translation_fidelity,efsm_equiv,roles_sweep,capability_sweep,cross_runtime,make_figs_v2}.py`
- Verdict corpus: `experiments/tests/verdict_corpus/`
- Results + figures + tables: `experiments/reports/`

## Run it on Azure AI Foundry (later)

This run's real numbers came from deterministic scripts against the Scribble compiler (no Azure AI Foundry involved); the still-pending experiments (E3, E5, E6, E7) are the ones that will need a live LLM loop or Azure. To connect any of these to Azure AI Foundry-hosted agents, follow the standard recipe in [`1_TECH_SETUP.md` section 5](../1_TECH_SETUP.md#5-running-stjp-with-azure-ai-foundry-hosted-agents) plus the four registration points listed in [`experiments/CLAUDE.md`](../../experiments/CLAUDE.md) (`registry.py` SCENARIOS, `case_runner.py` `_FOUNDRY_INSTALL_KEYS` and `FOUNDRY_KEYS`, `evaluate_run.py` `VOCABULARY_ARMS`).
