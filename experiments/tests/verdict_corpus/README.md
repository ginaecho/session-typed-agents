# Verdict corpus — testing the testers (BENCHMARK_PLAN_V2 §9)

40 traces with **known-correct verdicts**, run against the two instruments
every downstream experiment trusts:

- **Monitor group** (24) — `stjp_core.monitor.SessionMonitor` over projected
  EFSMs. Asserts the exact set of alarm categories (`off_protocol`,
  `unexpected_peer`, `premature_termination`, `refinement_failed`,
  `choice_guard_violation`) or conformance. Includes async-commuting cases
  (independent channels reorder; a role's send/receive to the same peer are
  different channels and commute) and value-dependent choice guards
  (wrong branch = violation; guard not evaluable = silent).
- **Grader group** (16) — `experiments/scripts/severity_grader.AttemptGrader`
  over a finance-shaped severity spec. Asserts the S0–S4 buckets, including
  the documented **payload-blind `Approval(False)`** milestone case (label
  alignment, not payload — a future payload-aware fix will deliberately trip
  `G11` and force a conscious update).

Run:

```bash
python experiments/tests/verdict_corpus/run_verdict_corpus.py    # exit 0 iff 40/40
```

Building the corpus surfaced (and now pins down) two real semantics that a
naive reader would get wrong: **both endpoints** of a message independently
flag a fault (a bad label trips the sender AND the receiver), and a role's
send-to-peer commutes past its own pending receive-from-peer under async
MPST subtyping. If any of the 40 ever fails, either a genuine regression
landed or the semantics changed on purpose — reconcile before trusting a run.

One sentence for the paper: *"the monitor and severity grader pass a 40-trace
verdict corpus including adversarial interleavings and consequence-graded
violations."*
