# Benchmark v2 — Tables 5 & 6

Regenerate the source numbers with:
`python experiments/scripts/stats.py --from-subagent-trials` (Table 5, real
n=10) and `python experiments/scripts/translation_fidelity.py --demo` (Table 6,
scorer column real). Replace the SYNTH rows/cells the moment n=30 / LLM runs
land — delete the "synthesized targets; measurement pending" note when you do.

## Table 5 — reliability (pass^k)

**Real, n=10 (subagent trials — E2/E3 of RESULT_5):**

| Arm | succ/n | per-run | 95% CI (Wilson) | pass^10 | pass^10 @ CI-LB |
|---|---|---|---|---|---|
| A unchecked (prose skills) | 0/10 | 0.0% | [0.0, 27.8]% | 0.000 | 0.000 |
| C+ STJP (gate+sched) | 10/10 | 100.0% | [72.2, 100.0]% | 1.000 | 0.039 |
| C+ STJP extended | 10/10 | 100.0% | [72.2, 100.0]% | 1.000 | 0.039 |

Read-out: even a "perfect" 10/10 arm has a Wilson lower bound of 72.2% at
n=10, so `pass^10` at the CI floor is only 0.039 — **this is exactly why the
plan calls for n=30.** The wide interval is the finding, not a defect.

**SYNTH targets, n=30 (placeholder — measurement pending):**

| Arm | succ/n | per-run | 95% CI (Wilson) | pass^10 | pass^10 @ CI-LB |
|---|---|---|---|---|---|
| A intent | 0/30 | 0.0% | [0.0, 11.4]% | 0.000 | 0.000 |
| B global text | 29/30 | 96.7% | [83.3, 99.4]% | 0.712 | 0.161 |
| C local observer | 24/30 | 80.0% | [62.7, 90.5]% | 0.107 | 0.009 |
| C+ full STJP | 30/30 | 100.0% | [88.6, 100.0]% | 1.000 | 0.300 |

*Placeholder values (synthesized targets); measurement pending.*

## Table 6 — translation fidelity (100 intents)

| Measure | Result | Status |
|---|---|---|
| First draft passes validator | 55% | *synthesized target; measurement pending* |
| Valid within ≤3 repair rounds | 93% (median 1) | *synthesized target; measurement pending* |
| **EFSM-equivalent to gold, among valid** | **scorer 100% accurate over 90 real (gold,draft) pairs** | **REAL (scorer validated; fidelity-over-intents pending)** |
| Guard sidecar co-emitted correctly | 71% | *synthesized target; measurement pending* |

The EFSM-equivalence *scorer* (the hard part — comparing meaning, not text) is
real and validated (`efsm_equiv.py`, `test_efsm_equiv.py`, the `--demo`). The
percentage OVER 100 intents needs the LLM draft loop and is pending. ("Gold"
pairs are known-correct reference protocols the LLM-drafted output is scored
against.)
