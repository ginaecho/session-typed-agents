# EXTENSIONS_PREREGISTRATION — three typed extensions (P1/P2/P3, E8/E9/E10)

*Registered 2026-07-05, on branch `gc/stjp_stateful_extension`, BEFORE the first
benchmark run. Grades are filled in after running; the deliberately-uncertain
predictions (esp. E9's deadlock-replay split) are marked as such. Discipline
inherited from E0: each prototype's hand-written verdict corpus must pass 100%
before its benchmark is trusted.*

Intellectual lineage (the paper's spine):
guards (Bocchi et al. CONCUR'10) → **stateful properties (Chen & Honda
CONCUR'12)** → **lawful slack (Chen–Dezani–Scalas–Yoshida LMCS'17 / PPDP'24)** →
**typed recovery (Viering et al. ESOP'18)**.

---

## P1 / E8 — Stateful session invariants ("the session ledger")

**Licensing theory:** Chen & Honda, CONCUR'12.
**Checker:** `SessionLedger` in `stjp_core/compiler/refinement_checker.py`;
central check in `SessionMonitor` (`stateful_invariant_violation`).
**Verdict corpus:** `experiments/tests/verdict_corpus/stateful/` — **must be 12/12.**

**Pre-registered predictions (E8, `budget_run`, per-message limit $5k, budget $10k):**
- Arm (a) current STJP (per-message guards only): **detects 0/50 overruns** —
  structurally blind, this is the shipped system and the motivation, not a
  strawman.
- Arm (b) +invariants, observe: **flags 50/50 at exactly the crossing message,
  0/50 false positives** on legal-total traces.
- Arm (c) +invariants, gate: **delivers 0 post-budget debits**; live trials
  complete with the Treasurer re-prompted onto a legal path.

**Grade (2026-07-05): CONFIRMED on the deterministic corpus.** a=0/50, b=50/50
(50/50 crossing-exact, 0 FP), c=0 post-budget delivered, 0 FP. Verdict corpus
12/12. Live-subagent portion: see E8 report.

---

## P2 / E9 — Precise-subtyping gate ("lawful slack")

**Licensing theory:** Chen–Dezani–Scalas–Yoshida, LMCS'17; PPDP'24 (preciseness).
**Deliverables:** (2a) compile-time subtype checker `check_subtype.py` wired into
S3 (`lean ≤ projection`); (2b) runtime tolerant gate, the decidable
independent-receive output-anticipation fragment only, behind `--tolerance`.
**Verdict corpus:** `verdict_corpus/subtype/` — **must be 14/14.**

**Pre-registered predictions (E9):**
1. Deadlock replay (UNCERTAIN, registered honestly): of the 19 genuine gated-arm
   deadlocks, **≥5 of 19 rescued** as safe anticipations; the rest are true
   agent give-ups. Whatever the split, it decomposes "gate too strict" vs
   "agent gave up."
2. Safety non-regression (MANDATORY control): rerun E2's 1,200 adversarial
   attempts + a 500-trace illegal-send corpus under the tolerant gate →
   **0 new deliveries** (the fragment is provably inside the precise relation).
3. Live ladder rerun (escrow C+min, STJP, tolerant gate): C+min deadlocks
   **17→≤10**; disasters stay **0**; STJP **≥98%**; calls/trial unchanged ±5%.

**Grade:** _pending_.

---

## P3 / E10 — Typed crash-failure handling ("no session left in limbo")

**Licensing theory:** Viering–Chen–Eugster–Hu–Ziarek, ESOP'18.
**Deliverables:** `.fail` sidecar (regions + handlers), 3 static validator
checks (coverage, handler projectability+deadlock-freedom, recoverability),
S4 handler-EFSM codegen, scheduler timeout→crash broadcast.
**Verdict corpus:** `verdict_corpus/crash/` — **must be 12/12**; plus E1-style
mutation of the new checker (uncovered pair / deadlocking handler / unreachable
terminal must all be rejected).

**Pre-registered predictions (E10, crash-point sweep):**
- Current STJP: **~100% limbo on any crash** (the 22-trial audit showed this
  accidentally; E10 shows it systematically).
- +CF: **100% typed terminal** (success / typed-degraded / typed-abort), **0
  disasters**, validator **rejects 100%** of seeded bad handlers.
- Live flaky-role trials (one role crashes p=0.3): +CF completes-or-degrades
  **30/30 with 0 limbo**; baseline limbos ≈ crash rate.

**Grade:** _pending_.

---

## Integrity rules (all three)
- Verdict corpus before benchmark, every time (38 new hand-derived traces total).
- Arm (a) in every benchmark is the **shipped STJP**; each write-up states the
  baseline's blindness is the motivation, not a planted defect.
- No silent caps; any dropped coverage is logged.
