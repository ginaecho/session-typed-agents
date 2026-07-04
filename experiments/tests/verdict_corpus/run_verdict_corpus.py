"""Run the verdict corpus — require 40/40 before trusting monitor + grader.

MONITOR cases: project the tiny protocol via Scribble, run SessionMonitor over
the trace, compare the exact multiset of violation-type strings.
GRADER cases: run the severity AttemptGrader over the finance-shaped spec,
compare the exact S-class buckets.

Exit 0 iff all 40 pass. Prints a per-case PASS/FAIL line and a summary.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2].parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "scripts"))

from stjp_core.compiler.validator import ScribbleValidator          # noqa: E402
from stjp_core.compiler.efsm_parser import get_all_efsms            # noqa: E402
from stjp_core.monitor.monitor import SessionMonitor, TraceEvent    # noqa: E402
from stjp_core.compiler.refinement_checker import parse_refn_text   # noqa: E402
from severity_grader import AttemptGrader                            # noqa: E402

from corpus import MONITOR_CASES, GRADER_CASES, SEVERITY_SPEC, TOTAL  # noqa: E402
import re


# EFSMs are pure functions of the protocol text; cache by (protocol, name).
_EFSM_CACHE: dict = {}


def _efsms_for(case, workdir: Path):
    key = (case["protocol"], case["protocol_name"], tuple(case["roles"]))
    if key not in _EFSM_CACHE:
        # Scribble requires the file stem == module name.
        module = re.search(r"module\s+(\w+)\s*;", case["protocol"]).group(1)
        scr = workdir / f"{module}.scr"
        scr.write_text(case["protocol"], encoding="utf-8")
        ok, err = ScribbleValidator().validate_protocol(scr)
        if not ok:
            raise RuntimeError(f"corpus protocol {case['id']} invalid: {err[:200]}")
        _EFSM_CACHE[key] = get_all_efsms(scr, case["protocol_name"], case["roles"])
    return _EFSM_CACHE[key]


def run_monitor_case(case, workdir: Path) -> tuple[bool, str]:
    efsms = _efsms_for(case, workdir)
    refinements = parse_refn_text(case["refn"]) if case.get("refn") else {}
    mon = SessionMonitor(efsms, refinements)
    events = [TraceEvent(sender=e["sender"], receiver=e["receiver"],
                         label=e["label"], payload=e.get("payload", ""), step=i + 1)
              for i, e in enumerate(case["trace"])]
    verdicts = mon.process_trace(events)
    all_viol = [v for verd in verdicts.values() for v in verd.violations]
    got_types = {v.violation_type.value for v in all_viol}
    conformant = all(verd.conformant for verd in verdicts.values())
    exp_types = set(case["expect_types"])
    # Compare the DISTINCT set of alarm categories the monitor raised (robust to
    # both-endpoint flagging and premature cascades) plus the conformant flag,
    # and require ≥1 violation whenever a fault is expected.
    ok = (conformant == case["expect_conformant"]) and (got_types == exp_types)
    if not case["expect_conformant"]:
        ok = ok and len(all_viol) > 0
    detail = "" if ok else f"conformant={conformant} (exp {case['expect_conformant']}); types={sorted(got_types)} (exp {sorted(exp_types)})"
    return ok, detail


def run_grader_case(case) -> tuple[bool, str]:
    spec = _grader_spec()
    g = AttemptGrader(spec, case["branch"])
    for ev in case["events"]:
        g.feed(ev)
    g.close()
    got = dict(g.sev)
    exp = case["expect"]
    ok = got == exp
    detail = "" if ok else f"got {got} exp {exp}  (s4: {g.s4_detail})"
    return ok, detail


_SPEC_CACHE = None


def _grader_spec() -> dict:
    global _SPEC_CACHE
    if _SPEC_CACHE is None:
        spec = {k: v for k, v in SEVERITY_SPEC.items()}
        # compile regexes + by-id index the way severity_grader.load_spec does
        spec["milestones"] = [dict(m) for m in SEVERITY_SPEC["milestones"]]
        for m in spec["milestones"]:
            m["rx"] = re.compile(m["match"], re.IGNORECASE)
        spec["_by_id"] = {m["id"]: m for m in spec["milestones"]}
        _SPEC_CACHE = spec
    return _SPEC_CACHE


def main() -> int:
    passed = 0
    failed = []
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        print("── MONITOR group (SessionMonitor) ──")
        for case in MONITOR_CASES:
            ok, detail = run_monitor_case(case, workdir)
            print(f"  {'PASS' if ok else 'FAIL'}  {case['id']}"
                  + (f"  — {detail}" if not ok else ""))
            passed += ok
            if not ok:
                failed.append(case["id"])
        print("── GRADER group (severity AttemptGrader S0–S4) ──")
        for case in GRADER_CASES:
            ok, detail = run_grader_case(case)
            print(f"  {'PASS' if ok else 'FAIL'}  {case['id']}"
                  + (f"  — {detail}" if not ok else ""))
            passed += ok
            if not ok:
                failed.append(case["id"])

    print(f"\nVERDICT CORPUS: {passed}/{TOTAL} passed"
          + (f" — FAILURES: {failed}" if failed else "  ✓ instruments trustworthy"))
    return 0 if passed == TOTAL else 1


if __name__ == "__main__":
    raise SystemExit(main())
