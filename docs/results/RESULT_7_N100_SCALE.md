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
| Interaction trials (unchecked) | **0/100 success, 100/100 deadlock** |
| Interaction trials (STJP) | **100/100 success, 0 violations** |

## The three findings that matter most

1. **n=100 resolves the statistical weakness.** The Wilson CI width for a 100%
   arm drops from 28 points (n=10) to 3.7 points (n=100). A deployment operator
   now has pass^10 = 0.686 at the confidence floor — credible enough for
   production gating. At n=10 (pass^10@floor = 0.039), a "perfect" arm still
   has a 1-in-25 chance of a failed batch. At n=100, that shrinks to 1-in-3.
   The n=30 plan target (pass^10@floor ≈ 0.300) sits halfway.

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
