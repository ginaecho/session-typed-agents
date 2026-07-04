# Result 6 — Making the evaluation bulletproof (Benchmark Plan v2)

**At a glance (2026-07-04).** Seven experiments plus a verdict corpus, each
testing ONE component of STJP so a number is attributable. Everything that can
be measured deterministically was run for real with the Scribble compiler;
everything needing multiple model families or a live LLM loop is a wired
harness with real anchors and clearly-tagged synthetic placeholders.

| What we now know (real numbers) | Result |
|---|---|
| The monitor + severity grader give the right verdict | **40/40** hand-derived traces |
| The checker catches malformed protocols | **95.6%** of well-formedness defects, **0%** false positives |
| The gate stops a hostile agent | none **0%** → keyword rules **41.7%** → structural gate **91.7%** → gate+value-guard **100%** blocked |
| n=10 is genuinely too few | a 10/10 arm has a 95% CI of **[72%, 100%]**; pass¹⁰ at the floor is **0.039** |
| We can compare two protocols by MEANING | equivalence scorer **100%** over 90 real (gold,draft) pairs |
| It scales | global-text coordination cost is **9×→17×** STJP's from 2→10 roles |
| Enforcement is portable | the standalone monitor matches the in-process one **100%** |

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
