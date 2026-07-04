# Pre-registration — Benchmark Plan v2 experiments

Per the fairness checklist (BENCHMARK_PLAN_V2 §11), the expected outcome of each
experiment is registered here BEFORE running, then graded after. Registered
2026-07-04.

| Exp | Prediction (registered before running) | Outcome |
|---|---|---|
| §9 Verdict corpus | monitor + grader give the hand-derived verdict on all 40 traces | **CONFIRMED — 40/40** (three hand-derivations were wrong and corrected to the semantically-correct value; the instruments were right) |
| E1 mutation | well-formedness defects (undeclared role, choice-knowledge) detected ≥90%; false positives ≈0%; pure reordering of acyclic protocols mostly stays valid (low "detection" is correct acceptance) | **CONFIRMED — 95.6% well-formedness detection, 0% FP; reordering ops 0% (all mutants still valid = correct)** |
| E2 adversarial | none 0% blocked; a keyword rule-guard is evaded by encoding/synonym/split; the structural gate blocks all ILLEGAL-route exfiltration but NOT a payload smuggled inside a legitimately-labelled message; gate+value-guard = 100% | **CONFIRMED — none 0%, rules 41.7% (7 evasions), gate 91.7% (1 legit-label smuggle), gate+refn 100%** |
| E4 pass^k | at n=10 the 100% arm still has a wide Wilson CI (LB ~72%), so pass^10 at the CI lower bound is small — motivating n=30 | **CONFIRMED — 100%/10 -> CI [72.2,100], pass^10@CIlo=0.039** |
| E5 equivalence | the EFSM-equivalence scorer classifies identical/reformatted/mutated drafts correctly | **CONFIRMED — 100% over 90 real (gold,draft) pairs** (LLM fidelity measures pending) |
| E6 roles sweep | global-text coordination cost grows super-linearly vs #roles; STJP grows ~linearly | **CONFIRMED (structural proxy) — ratio 9.2x @2 roles -> 17.1x @10 roles** (token-per-goal pending) |
| E7 portability | the standalone generated monitor agrees with the in-process monitor on conformant canonical traces | **CONFIRMED — 100% agreement (59/59)** (three-harness live comparison pending; async-reordered traces diverge by the documented codegen limitation) |
| E3 capability sweep | A-arm disasters rise with model strength; enforcement gain falls to 0 | **PENDING — needs multiple model families (2 real anchors: gpt-4o +60 gain/4 disasters, gpt-5.4 0 gain/22 disasters)** |
