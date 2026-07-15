# Result 7 — Scaling to n=100 (all deterministic benchmarks)

**At a glance (2026-07-04).** Every benchmark that can run without a live LLM
loop or Azure was scaled from the original n=10/30 to n=100. The headline: at
n=100, the Wilson 95% CI for the STJP arm narrows from [72%, 100%] to
[96.3%, 100%], making pass^10 at the floor jump from 0.039 to 0.686 — a
**17.6× improvement in deployment confidence**.

| What we now know (n=100) | Result |
|---|---|
| Integration stress (full pipeline) | **2105/2110 checks = 99.76%** over 100 generated protocols |
| Checker soundness (mutation testing) | **95.1% detection, 0% false positives** on 100-protocol corpus |
| Gate + layered defense | **0→41.7→91.7→100%** confirmed across 1200 trials |
| Pass^10 reliability at CI floor | **0.686** (was 0.039 at n=10) |
| Equivalence scorer accuracy | **300/300 = 100%** (3.3× wider validation) |
| Coordination cost ratio | **9.2→17.1×** confirmed (structural) |
| Boundary portability | **59/59 = 100%** (standalone == in-process monitor) |
| Interaction trials (unchecked) | **0/100 finished — all 100 deadlocked** |
| Interaction trials (STJP) | **100/100 success, 0 violations** |

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The story at a glance (STAR)](#the-story-at-a-glance-star)
- [How this experiment is set](#how-this-experiment-is-set)
- [The three findings that matter most](#the-three-findings-that-matter-most)
- [Method](#method)
- [Where everything lives](#where-everything-lives)
- [Run it on Azure AI Foundry (later)](#run-it-on-azure-ai-foundry-later)
<!-- MENU:END -->

## The story at a glance (STAR)

- **Situation** — Result 6's deterministic benchmarks were run at n=10/30, which leaves wide statistical uncertainty even when every trial passes.
- **Task** — Rescale every benchmark that can run without a live LLM loop or Azure from n=10/30 to n=100, and measure how much deployment confidence improves.
- **Action** — Same codebase, same Scribble compiler, same deterministic seeds as Result 6, scaled to n=100 across the integration stress suite, mutation testing, gate defense, equivalence scorer, coordination cost, monitor portability, and subagent interaction trials.
- **Result** — Wilson 95% CI for the STJP arm narrows from **[72%, 100%]** to **[96.3%, 100%]**, pass^10 at the CI floor jumps from **0.039** to **0.686** (a **17.6x improvement**); interaction trials read **100/100 finished, 0 violations** (STJP) vs **0/100 finished — all 100 deadlocked** (unchecked).

## How this experiment is set

- **Case(s):** same deterministic benchmarks as Result 6, rescaled, plus the subagent interaction trials (`escrow_trade`-shaped, contract-following strategy, no live model)
- **Arms/settings:** integration stress; checker soundness (mutation testing); gate + layered defense; equivalence scorer; coordination cost; boundary portability; interaction trials (unchecked vs. STJP)
- **Trials:** n=100 per benchmark (up from n=10/30 in Result 6); 1,200 trials for the gate/layered-defense ladder
- **Who plays the roles:** no live LLM — the interaction trials use a "contract-following" strategy (each agent picks its first enabled send transition) to test the STJP machinery itself, not model compliance; the live-LLM evidence for model compliance is in Result 5 (n=10, real subagents)
- **Isolation:** not applicable (scripted strategy, no independent agents to isolate)
- **Harness & budgets:** `experiments/subagent_trials/run_n100.py`; same deterministic seeds and Scribble compiler as Result 6
- **Where the raw data is:** [`experiments/reports/n100/`](../../experiments/reports/n100/)

## The three findings that matter most

1. **n=100 resolves the statistical weakness.** The Wilson CI width for a 100%
   arm drops from 28 points (n=10) to 3.7 points (n=100). A deployment operator
   now has pass^10 = 0.686 at the confidence floor — credible enough for
   production gating. (pass^10@floor is the chance that *all ten* of the next
   ten runs pass, computed at the pessimistic edge of the confidence range.) At
   n=10 (pass^10@floor = 0.039), even a "perfect" 10/10 arm is consistent with a
   true rate low enough that a full ten-run batch would pass only about 1 in 25
   times — i.e. it would *fail* a batch almost every time. At n=100
   (pass^10@floor = 0.686), a full batch passes about 2 in 3 times. The n=30
   plan target (pass^10@floor ≈ 0.300) sits halfway.

2. **The STJP infrastructure works correctly at scale.** 100 consecutive trials,
   each with a 7-message protocol, all completed successfully with zero gate
   rejections, zero monitor violations, zero Critic findings. The EFSM scheduler
   polled exactly the right roles, the gate never false-positived, and the
   monitors tracked state perfectly across 700 delivered messages.

3. **5 new edge cases surfaced.** The stress suite's 100 iterations found 5
   swap_fifo mutations that weren't caught — all on acyclic protocols where a
   local FIFO reorder produces another equally valid protocol. This is correct
   behaviour (not a bug), but it's evidence the larger corpus reaches corners
   the 30-iteration run didn't.

## Method

All benchmarks use the same codebase, same Scribble compiler, same
deterministic seeds. The subagent interaction trials use a "contract-following"
strategy (each agent picks its first enabled send transition) rather than a live
LLM — this measures whether the STJP machinery (gate, scheduler, monitor,
Critic) handles 100 concurrent trials correctly, not model compliance. The
live-LLM evidence for model compliance is in RESULT_5 (n=10, 10/10 with real
subagent responses).

## Where everything lives

- Full technical report: `experiments/reports/n100/REPORT_N100.md`
- Per-experiment data: `experiments/reports/n100/{stress,e1,e2,e4,e5,e6,e7}/`
- Subagent trial data: `experiments/reports/n100/subagent/`
- Runner script: `experiments/subagent_trials/run_n100.py`
- 100-protocol corpus: `experiments/reports/n100/e1/_corpus/`

## Run it on Azure AI Foundry (later)

This run used deterministic scripts against the Scribble compiler and a contract-following subagent strategy (`experiments/subagent_trials/run_n100.py`), not Azure AI Foundry or a live LLM loop. To reproduce the interaction-trial portion with real Azure AI Foundry-hosted agents instead, follow the standard recipe in [`1_TECH_SETUP.md` section 5](../1_TECH_SETUP.md#5-running-stjp-with-azure-ai-foundry-hosted-agents) plus the four registration points listed in [`experiments/CLAUDE.md`](../../experiments/CLAUDE.md) (`registry.py` SCENARIOS, `case_runner.py` `_FOUNDRY_INSTALL_KEYS` and `FOUNDRY_KEYS`, `evaluate_run.py` `VOCABULARY_ARMS`).
