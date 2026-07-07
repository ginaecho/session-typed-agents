"""Stateful-invariant verdict corpus — 12 hand-derived traces.

Prototype 1's discipline (inherited from E0): the new checker's behaviour is
pinned by a hand-written corpus that must pass 12/12 BEFORE any benchmark (E8)
is allowed to trust it. Each case fixes the ledger clauses, a trace, and the
EXACT expected outcome (which step breaches, which are gate-blocked, how many
unevaluable). We test the SessionLedger directly — it is the new unit.

Run:  python experiments/tests/verdict_corpus/stateful/stateful_corpus.py
Exit 0 iff 12/12.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from stjp_core.compiler.refinement_checker import (   # noqa: E402
    parse_session_ledger, validate_session_ledger)


# Each case: id, refn (ledger clauses), trace [(label,payload)], gate,
# expect: {breach_steps:[...], blocked_steps:[...], unevaluable:int,
#          severities:{step:S-class}}  (only keys present are checked)
CASES = [
    # 1. cumulative overrun caught at the EXACT crossing message (default S2)
    dict(id="cum_overrun_at_3",
         refn="state t:money=0\nstate budget:money=10000\non Debit(a):t+=a\ninvariant t<=budget",
         trace=[("Debit", "4000"), ("Debit", "4000"), ("Debit", "4000")],
         gate=False,
         expect=dict(breach_steps=[3], severities={3: "S2"})),
    # 2. crossing at step 2 with a smaller budget
    dict(id="cum_overrun_at_2",
         refn="state t:money=0\nstate budget:money=8000\non Debit(a):t+=a\ninvariant t<=budget",
         trace=[("Debit", "5000"), ("Debit", "4000")],
         gate=False,
         expect=dict(breach_steps=[2])),
    # 3. legal exact total (== budget, not >) stays silent
    dict(id="cum_legal_exact",
         refn="state t:money=0\nstate budget:money=10000\non Debit(a):t+=a\ninvariant t<=budget",
         trace=[("Debit", "4000"), ("Debit", "4000"), ("Debit", "2000")],
         gate=False,
         expect=dict(breach_steps=[])),
    # 4. legal under-budget run stays silent
    dict(id="cum_legal_under",
         refn="state t:money=0\nstate budget:money=10000\non Debit(a):t+=a\ninvariant t<=budget",
         trace=[("Debit", "3000"), ("Debit", "3000"), ("Debit", "3000")],
         gate=False,
         expect=dict(breach_steps=[])),
    # 5. gate mode: the crossing message is rejected pre-delivery; a later
    #    smaller debit still fits (virtual state rolled back to pre-crossing).
    dict(id="gate_reject_crossing",
         refn="state t:money=0\nstate budget:money=10000\non Debit(a):t+=a\ninvariant t<=budget",
         trace=[("Debit", "4000"), ("Debit", "4000"), ("Debit", "4000"), ("Debit", "1000")],
         gate=True,
         expect=dict(breach_steps=[3], blocked_steps=[3])),
    # 6. irreversible-resource invariant configured to S4 via @S4
    dict(id="s4_irreversible",
         refn="state t:money=0\nstate budget:money=10000\non Debit(a):t+=a\ninvariant t<=budget @S4",
         trace=[("Debit", "4000"), ("Debit", "4000"), ("Debit", "4000")],
         gate=False,
         expect=dict(breach_steps=[3], severities={3: "S4"})),
    # 7. state PERSISTS across loop iterations by default (no reset)
    dict(id="persist_across_loop",
         refn="state t:money=0\nstate budget:money=10000\non Debit(a):t+=a\ninvariant t<=budget",
         trace=[("Debit", "3000")] * 4,   # 4th reaches 12000
         gate=False,
         expect=dict(breach_steps=[4])),
    # 8. `reset on <Label>` opts out: window resets each Cycle
    dict(id="reset_each_loop",
         refn=("state window:money=0 reset on Cycle\non Debit(a):window+=a\n"
               "invariant window<=5000"),
         trace=[("Cycle", ""), ("Debit", "3000"), ("Debit", "3000"),
                ("Cycle", ""), ("Debit", "4000"), ("Debit", "4000")],
         gate=False,
         expect=dict(breach_steps=[3, 6])),   # 6000>5000 @3; reset; 8000>5000 @6
    # 9. lower-bound invariant: a withdrawal drives balance negative
    dict(id="balance_negative",
         refn=("state bal:money=0\non Deposit(a):bal+=a\non Withdraw(a):bal-=a\n"
               "invariant bal>=0"),
         trace=[("Deposit", "100"), ("Withdraw", "150")],
         gate=False,
         expect=dict(breach_steps=[2])),
    # 10 & 11. commutativity: two labels updating the same var, both orders,
    #          reach the same breach at step 2.
    dict(id="interleave_AB",
         refn="state t:money=0\nstate cap:money=100\non A(a):t+=a\non B(a):t+=a\ninvariant t<=cap",
         trace=[("A", "60"), ("B", "60")],
         gate=False,
         expect=dict(breach_steps=[2])),
    dict(id="interleave_BA",
         refn="state t:money=0\nstate cap:money=100\non A(a):t+=a\non B(a):t+=a\ninvariant t<=cap",
         trace=[("B", "60"), ("A", "60")],
         gate=False,
         expect=dict(breach_steps=[2])),
    # 12. unevaluable (nonnumeric) payload is skipped + logged, NEVER a false
    #     block; the real overrun three messages later is still caught.
    dict(id="unevaluable_no_false_block",
         refn="state t:money=0\nstate budget:money=10000\non Debit(a):t+=a\ninvariant t<=budget",
         trace=[("Debit", "n/a"), ("Debit", "4000"), ("Debit", "4000"), ("Debit", "4000")],
         gate=False,
         expect=dict(breach_steps=[4], unevaluable=1)),
]


def run_case(case) -> tuple[bool, str]:
    ledger = parse_session_ledger(case["refn"])
    # well-formedness must hold for every corpus ledger
    labels = {lbl for (lbl, _) in case["trace"]}
    ok_v, errs = validate_session_ledger(ledger, labels | set(ledger.updates))
    if not ok_v:
        return False, f"ledger not well-formed: {errs}"
    ledger.reset()
    breach_steps, blocked_steps, sev = [], [], {}
    for i, (label, payload) in enumerate(case["trace"], 1):
        for lv in ledger.step(label, payload, step_no=i, gate=case["gate"]):
            breach_steps.append(i)
            sev[i] = lv.severity
            if lv.blocked:
                blocked_steps.append(i)
    exp = case["expect"]
    problems = []
    if "breach_steps" in exp and breach_steps != exp["breach_steps"]:
        problems.append(f"breach_steps={breach_steps} exp {exp['breach_steps']}")
    if "blocked_steps" in exp and blocked_steps != exp["blocked_steps"]:
        problems.append(f"blocked_steps={blocked_steps} exp {exp['blocked_steps']}")
    if "unevaluable" in exp and len(ledger.unevaluable) != exp["unevaluable"]:
        problems.append(f"unevaluable={len(ledger.unevaluable)} exp {exp['unevaluable']}")
    if "severities" in exp:
        for step, s in exp["severities"].items():
            if sev.get(step) != s:
                problems.append(f"sev@{step}={sev.get(step)} exp {s}")
    return (not problems), "; ".join(problems)


def main() -> int:
    passed, failed = 0, []
    print("── STATEFUL-INVARIANT verdict corpus (Prototype 1) ──")
    for case in CASES:
        ok, detail = run_case(case)
        print(f"  {'PASS' if ok else 'FAIL'}  {case['id']}" + (f"  — {detail}" if not ok else ""))
        passed += ok
        if not ok:
            failed.append(case["id"])
    total = len(CASES)
    print(f"\nSTATEFUL CORPUS: {passed}/{total} passed"
          + (f" — FAILURES: {failed}" if failed else "  ✓ checker trustworthy"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
