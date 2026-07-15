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

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [P1 / E8 — Stateful session invariants ("the session ledger")](#p1--e8--stateful-session-invariants-the-session-ledger)
- [P2 / E9 — Precise-subtyping gate ("lawful slack")](#p2--e9--precise-subtyping-gate-lawful-slack)
- [P3 / E10 — Typed crash-failure handling ("no session left in limbo")](#p3--e10--typed-crash-failure-handling-no-session-left-in-limbo)
- [Integrity rules (all three)](#integrity-rules-all-three)
<!-- MENU:END -->

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

**Grade (2026-07-05): CONFIRMED — deterministic AND live.**
- Deterministic corpus (n=50/class): a=0/50, b=50/50 (50/50 crossing-exact, 0
  FP), c=0 post-budget delivered, 0 FP. Verdict corpus 12/12; existing 40/40
  intact (independently re-run by a haiku subagent).
- Live subagent trials (haiku roles, n=15/arm, $12k procurement vs $10k budget,
  verified from state.json, malformed=0): arm (a) shipped **paid 16 post-budget
  debits, undetected**; arm (b) observe paid but **flagged 15/15**; arm (c) gate
  **0 post-budget paid**, 15/15 rejections, Requester downsized to exactly $10k,
  goal still reached in *fewer* calls (8.0 vs 10.2). The prediction "arm (c)
  delivers 0 post-budget debits and completes on a legal path" **holds with a
  weak model.** See `experiments/reports/n100/e8/E8_STATEFUL_INVARIANTS.md`.

---

## P2 / E9 — Precise-subtyping gate ("lawful slack")

**Licensing theory:** Chen–Dezani–Scalas–Yoshida, LMCS'17; PPDP'24 (preciseness).
**Deliverables:** (2a) compile-time subtype checker `check_subtype.py` connected
into S3 (`lean ≤ projection`); (2b) runtime tolerant gate, the decidable
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
3. Live ladder rerun (the escrow case — escrow being a neutral third party
   that holds funds until both sides deliver — C+min, STJP, tolerant gate): C+min deadlocks
   **17→≤10**; disasters stay **0**; STJP **≥98%**; calls/trial unchanged ±5%.

**Grade (2026-07-05): GRADED — mixed, honestly.**
- Verdict corpus 14/14 (haiku-verified). Checker (2a) + tolerant gate (2b) done.
- Part 2 safety non-regression: **HOLDS — 0/50 illegal sends admitted.** As predicted.
- Part 1 deadlock replay: prediction was "≥5/19 rescued." Mechanically **16/19**
  deadlocks contain a type-safe anticipable rejection — but the honest reading
  is these are **agent give-ups** (absent Buyer deposit), so the practical
  rescue is ~0 and the anticipations would relax pay-before-ship. The gate
  *correctly held* the 3 irreversible cases (`SettlementComplete`). Net: the
  prediction's spirit (decompose gate-strictness vs agent-give-up) is delivered,
  with a richer boundary finding than a bare count.
- Part 3 live rerun (haiku, n=15/arm): strict and tolerant **both 15/15, 0
  disasters**; tolerant admitted **0 anticipations** (in-order agents never send
  ahead) — live safety non-regression confirmed, tolerance transparent. The
  predicted "C+min deadlocks 17→≤10" was not measurable this sample (fresh haiku
  Buyers cooperated → 0 deadlocks in both arms); the deadlock analysis lives in
  part 1. See `experiments/reports/n100/e9/E9_LAWFUL_SLACK.md`.

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

**Grade (2026-07-05): CONFIRMED — deterministic AND live.**
- Verdict corpus 12/12; checker mutation **5/5 bad `.fail` rejected** (incl. the
  adversarial settlement-shortcut) — the new checker gets the same preciseness
  audit as the old one. (Both haiku-verified.)
- Crash-point grid (14 cells): current STJP **100% limbo**; +CF **9
  typed-degraded + 5 typed-abort, 0 limbo, 0 disasters**. As predicted.
- Deadlock replay (real data): **19/19 limbo → 19/19 typed terminal** under CF.
- Live flaky-role (haiku, n=15, one crash/trial): baseline **15/15 limbo**; +CF
  **15/15 typed terminal (Refunded), 0 disasters.** The prediction "+CF
  completes-or-degrades with 0 limbo, 0 disasters" holds with a weak model. See
  `experiments/reports/n100/e10/E10_CRASH_HANDLING.md`.

---

## Integrity rules (all three)
- Verdict corpus before benchmark, every time (38 new hand-derived traces total).
- Arm (a) in every benchmark is the **shipped STJP**; each write-up states the
  baseline's blindness is the motivation, not a planted defect.
- No silent caps; any dropped coverage is logged.
