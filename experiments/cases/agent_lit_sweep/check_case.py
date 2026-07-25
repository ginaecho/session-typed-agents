#!/usr/bin/env python3
"""check_case.py — prove the agent_lit_sweep case compiles, projects, and that
the shared-budget ledger actually refuses an overdraw.

Why this exists: the failure this case models was observed for real, in a
literature sweep run with several search agents and no protocol between them.
Two of those agents spent a shared budget of search calls down to zero and the
rest discovered the wall only after the fact. This script checks that the same
overspend, replayed against the compiled protocol, is refused *before* the
calls are spent rather than reported afterwards.

Run (needs Java and a built scribble-java at the path in stjp_core/config.py):
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
      python experiments/cases/agent_lit_sweep/check_case.py

Exit code 0 = all four checks pass, 1 = at least one failed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from stjp_core.compiler.validator import ScribbleValidator            # noqa: E402
from stjp_core.compiler.efsm_parser import get_all_efsms              # noqa: E402
from stjp_core.compiler.refinement_checker import (                   # noqa: E402
    load_refinements_for_protocol, validate_session_ledger)
from stjp_core.monitor.monitor import SessionMonitor, TraceEvent      # noqa: E402

PROTO = Path(__file__).resolve().parent / "protocols" / "v1.scr"
NAME = "LiteratureSweep"
ROLES = ["Coordinator", "Scout", "Verifier"]
BUDGET = 12          # must match `state searches_left` in v1.refn


def _spend(n: int, step: int) -> list[TraceEvent]:
    """One full budget-request round trip, as the protocol requires it."""
    return [
        TraceEvent("Scout", "Coordinator", "SearchSpend", str(n), step=step),
        TraceEvent("Coordinator", "Verifier", "BudgetNote", str(n), step=step + 1),
        TraceEvent("Coordinator", "Scout", "BudgetOk", str(n), step=step + 2),
    ]


def main() -> int:
    failures: list[str] = []

    # 1. The protocol is well formed. Scribble's convention is that silence
    #    means success, so an empty message with ok=True is the pass case.
    ok, msg = ScribbleValidator().validate_protocol(PROTO)
    print(f"[1] protocol well-formed          : {ok}")
    if not ok:
        failures.append(f"protocol rejected: {msg.strip()[:200]}")

    # 2. Every role projects to a local contract with at least one move.
    efsms = get_all_efsms(PROTO, NAME, ROLES)
    for role in ROLES:
        n = len(efsms[role].transitions)
        print(f"[2] projected {role:<12}       : {n} transitions")
        if n == 0:
            failures.append(f"{role} projected to an empty contract")

    # 3. The ledger sidecar is coherent against the protocol's labels.
    refn = load_refinements_for_protocol(PROTO)
    ledger = refn.get("__ledger__")
    if ledger is None:
        print("[3] ledger present                : False")
        failures.append("no __ledger__ in v1.refn")
        return _report(failures)
    labels = {t.label for f in efsms.values() for t in f.transitions}
    ok, errs = validate_session_ledger(ledger, labels)
    print(f"[3] ledger static check            : {ok} {errs if errs else ''}")
    if not ok:
        failures.append(f"ledger incoherent: {errs}")

    # 4. The gate refuses the spend that would overdraw the shared budget.
    #    Three requests of 5 against a budget of 12: the third must be
    #    rejected pre-delivery, and the budget must sit at 0, never below.
    events = [
        TraceEvent("Coordinator", "Scout", "Assignment", "sweep the literature", step=1),
        TraceEvent("Coordinator", "Verifier", "Watch", "sweep the literature", step=2),
    ]
    step = 3
    for n in (5, 5, 5):
        events += _spend(n, step)
        step += 3

    sm = SessionMonitor(efsms, refn, gate=True)
    sm.process_trace(events)
    remaining = sm.ledger.values["searches_left"]
    blocked = [v for v in sm.ledger_violations
               if "REJECTED pre-delivery" in (v.message or "")]
    print(f"[4] budget after 3x5 of {BUDGET}       : {remaining} "
          f"(blocked {len(blocked)} overdraw{'s' if len(blocked) != 1 else ''})")
    if remaining < 0:
        failures.append(f"budget went negative ({remaining}) — gate did not hold")
    if len(blocked) != 1:
        failures.append(f"expected exactly 1 blocked overdraw, got {len(blocked)}")

    return _report(failures)


def _report(failures: list[str]) -> int:
    print()
    if failures:
        print(f"FAIL ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — protocol validates, all roles project, ledger refuses the overdraw.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
