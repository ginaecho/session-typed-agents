"""batch_report.py — recompute report.json for many trial dirs FAST.

engine_ladder.py's `report` re-projects EFSMs (spawning the Scribble JVM) per
directory; over hundreds of trial dirs that is minutes of pure JVM startup.
This tool loads the case's EFSMs ONCE and recomputes every report in a single
process. Verdict logic is imported from engine_ladder (same code path).

    python experiments/subagent_trials/batch_report.py --case revenue_audit \
        --root /tmp/ladder_run/revenue_audit
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from stjp_core.compiler.efsm_parser import get_all_efsms          # noqa: E402
from stjp_core.critic.policies import parse_policy_text           # noqa: E402
from cases import CASES                                            # noqa: E402
from engine_ladder import ARMS, _disasters_and_findings, _goal_reached  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, choices=sorted(CASES))
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    case = CASES[args.case]
    root = Path(args.root)

    with tempfile.TemporaryDirectory() as td:
        scr = Path(td) / f"{case['module']}.scr"
        scr.write_text(case["protocol"], encoding="utf-8")
        efsms = get_all_efsms(scr, case["protocol_name"], case["roles"])
    policies = parse_policy_text(case["policy"]) if case.get("policy") else None

    n_done = n_skip = 0
    for d in sorted(root.glob("*__trial_*")):
        sp = d / "state.json"
        if not sp.exists():
            n_skip += 1
            continue
        state = json.loads(sp.read_text(encoding="utf-8"))
        rows = []
        for trial in state["trials"]:
            mon, dis, find = _disasters_and_findings(state, trial, efsms, policies)
            reached = _goal_reached(state, trial)
            clean = bool(reached and dis == 0 and mon == 0 and find == 0)
            secs = None
            if trial.get("started") and trial.get("ended"):
                secs = round(trial["ended"] - trial["started"], 2)
            rows.append({"trial": trial["trial"], "status": trial["status"],
                         "reached_goal": reached, "clean": clean,
                         "disasters": dis, "monitor_violations": mon,
                         "critic_findings": find,
                         "messages": len([e for e in trial["trace"] if e["delivered"]]),
                         "gate_rejections": len(trial["rejections"]),
                         "agent_calls": trial["agent_calls"],
                         "seconds": secs})
        n = len(rows)
        reached_n = sum(1 for r in rows if r["reached_goal"])
        gcr = reached_n / n if n else 0.0
        calls = sum(r["agent_calls"] for r in rows)
        report = {
            "case": state["case"], "arm": state["arm"],
            "label": ARMS[state["arm"]]["label"], "trials": n,
            "GCR_pct": round(100 * gcr, 1),
            "CGC_pct": round(100 * sum(1 for r in rows if r["clean"]) / n, 1) if n else 0.0,
            "disasters": sum(r["disasters"] for r in rows),
            "cost_to_goal_calls": (round(calls / gcr, 1) if gcr > 0 else None),
            "total_agent_calls": calls,
            "avg_seconds_per_trial": None,
            "total_gate_rejections": sum(r["gate_rejections"] for r in rows),
            "total_monitor_violations": sum(r["monitor_violations"] for r in rows),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "per_trial": rows,
        }
        (d / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        n_done += 1
    print(f"recomputed {n_done} reports ({n_skip} skipped, no state.json) under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
