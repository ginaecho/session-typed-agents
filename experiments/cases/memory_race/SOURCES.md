# Source provenance — memory_race

**This case is AUTHORED, not mined from a public repository.** Unlike the
`skills_safety/*` cases (real published skills) and `agenticpay_settlement`
(adapted from a real repo), `memory_race` is an original construction whose
purpose is methodological: it exercises a failure class — a shared-memory lost
update — that the other cases do not, and that the static Scribble deadlock
check cannot catch on its own.

## Why it is authored, not mined
Public agent-skill repos coordinate via message passing; a genuine
read-modify-write data race over shared mutable state is a *systems* pattern
(databases, concurrent programming) rather than something published as an "agent
skill." Rather than misattribute it to a repo, it is written here from the
classic concurrency textbook lost-update pattern (two transactions read the same
value, both write back, one update is lost — e.g. Bernstein, Hadzilacos &
Goodman, *Concurrency Control and Recovery in Database Systems*, 1987; and the
standard "lost update" anomaly in the SQL isolation-levels literature).

## What it demonstrates
- **Deadlock-freedom ≠ race-freedom.** The unsafe interleaving is not a deadlock,
  so Scribble's deadlock check does not flag it (see
  `docs/reference/GOAL_QUALITY_AUDIT.md` Part C).
- **Three complementary detectors**, one per STJP layer:
  1. the SAFE protocol (`protocols/v1.scr`) serialises writers → the gate
     rejects a second concurrent write;
  2. the policies (`protocols/v1.policy`) name the disaster (stale read /
     double write / self-confirm) → scored by `scripts/policy_eval.py`;
  3. the stateful environment (`environment.py`) asserts the real final balance
     → catches even a trace with correct message shapes and a hallucinated
     `Done("180")` payload.

## Safety review
Benign arithmetic on an in-memory integer balance. No secrets, no external
side effects, no network, no code execution.
