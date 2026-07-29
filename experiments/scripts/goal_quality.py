"""goal_quality.py — turn goal quality into a MEASURED quantity.

A goal is only informative if it SEPARATES arms. This script reads one or more
completed runs' `summary_eval.json` (produced by evaluate_run.py) and computes,
per goal:

  discrimination = passrate(goal | CHECKED arms) - passrate(goal | UNCHECKED arms)

on the role_pair metric (comparable across ALL arms) and, where available, the
strict metric (vocabulary arms only). It then flags:

  naive       : every arm passes (disc ~ 0, high absolute)  -> carries no signal
  impossible  : no arm passes    (disc ~ 0, low absolute)   -> mis-anchored / unreachable
  vacuous     : goal.branch never matches the run's branch  -> auto-passes (see B3)
  informative : |discrimination| >= threshold               -> a good goal

and classifies each goal into the taxonomy (liveness / ordering / aggregate /
data_quality / world_state) so cases stay comparable.

See docs/reference/GOAL_QUALITY_AUDIT.md (A2, B3, B5, D-gate-1, D-taxonomy).

Usage:
  python scripts/goal_quality.py <case_id> <run_dir> [<run_dir> ...]
  # aggregates across all run_dirs given (e.g. gpt-5-mini + gpt-5.6-sol)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
REPO = EXPERIMENTS_DIR.parent
CASES_DIR = EXPERIMENTS_DIR / "cases"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXPERIMENTS_DIR))
sys.path.insert(0, str(REPO))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from case_loader import Case

# Arms that were given a checked/validated protocol vs. arms that were not.
CHECKED_ARMS = {
    "spec_llmvalid", "min_llmvalid", "spec_llmvalid_gate", "min_llmvalid_gate",
    "min_llmvalid_gate_nohint", "min_llmvalid_gate_lastrecv",
    "min_llmvalid_sched", "global_decentralized",
}
UNCHECKED_ARMS = {
    "bare", "unchecked_skills", "maf_native", "maf_foundry", "maf_groupchat",
}

DISCRIMINATION_MIN = 40.0   # percentage-points spread to count as informative


def classify_goal(goal) -> str:
    """Infer the taxonomy category when case.yaml doesn't set one."""
    if goal.category:
        return goal.category
    desc = (goal.description or "").lower()
    pred = (goal.predicate or "").strip()
    if any(w in desc for w in ("at most", "at-most", "once", "no double",
                               "duplicate", "exactly one")):
        return "aggregate"
    if any(w in desc for w in ("before", "after", "precede", "order",
                               "prior to", "first")):
        return "ordering"
    if pred in ("True", "true", "len(x) >= 0"):
        return "liveness"
    if any(op in pred for op in ("float(", ">", "<", "==", ">=", "<=")):
        return "data_quality"
    return "data_quality"


def _collect(run_dirs: list[Path]) -> dict:
    """Merge per-goal role_pair / strict pass-rates across runs, by arm."""
    # arm -> metric -> goal_id -> [pct, pct, ...]  (one per run)
    acc: dict = {}
    for rd in run_dirs:
        ev_path = rd / "summary_eval.json"
        if not ev_path.exists():
            print(f"  (skip {rd.name}: no summary_eval.json)")
            continue
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        for arm, a in ev.get("arms", {}).items():
            for metric in ("role_pair_per_goal", "strict_per_goal"):
                pg = a.get(metric)
                if not pg:
                    continue
                m = acc.setdefault(arm, {}).setdefault(metric, {})
                for gid, pct in pg.items():
                    m.setdefault(gid, []).append(pct)
    return acc


def _avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else None


def analyse(case: Case, run_dirs: list[Path]) -> dict:
    acc = _collect(run_dirs)
    goals = case.goals
    branch_hints = set(getattr(case, "branch_hints", []) or [])

    def group_rate(metric: str, gid: str, arms: set[str]):
        vals = []
        for arm in arms:
            xs = acc.get(arm, {}).get(metric, {}).get(gid)
            if xs:
                vals.append(_avg(xs))
        return _avg(vals) if vals else None

    out = {"case": case.case_id, "runs": [r.name for r in run_dirs],
           "discrimination_min": DISCRIMINATION_MIN, "goals": {}}
    for g in goals:
        cat = classify_goal(g)
        # role_pair is defined for all arms -> primary discriminator.
        rp_chk = group_rate("role_pair_per_goal", g.id, CHECKED_ARMS)
        rp_unc = group_rate("role_pair_per_goal", g.id, UNCHECKED_ARMS)
        disc = (round(rp_chk - rp_unc, 1)
                if rp_chk is not None and rp_unc is not None else None)
        # vacuous: a branch-scoped goal whose branch is never exercised.
        vacuous = bool(g.branch and branch_hints and g.branch not in branch_hints)
        # naive/impossible flags from the cross-arm picture.
        all_rates = [r for r in (rp_chk, rp_unc) if r is not None]
        naive = bool(all_rates) and all(r >= 95 for r in all_rates)
        impossible = bool(all_rates) and all(r <= 5 for r in all_rates)
        informative = disc is not None and abs(disc) >= DISCRIMINATION_MIN
        flag = ("vacuous" if vacuous else
                "impossible" if impossible else
                "naive" if naive else
                "informative" if informative else "weak")
        out["goals"][g.id] = {
            "category": cat,
            "description": g.description,
            "branch": g.branch or None,
            "role_pair_checked_pct": rp_chk,
            "role_pair_unchecked_pct": rp_unc,
            "discrimination_pts": disc,
            "flag": flag,
        }
    return out


def print_report(out: dict) -> None:
    print("\n" + "=" * 92)
    print(f"  GOAL QUALITY: {out['case']}   runs={out['runs']}   "
          f"informative >= {out['discrimination_min']} pts spread")
    print("=" * 92)
    print(f"  {'goal':6s} {'category':13s} {'chk%':>6s} {'unc%':>6s} "
          f"{'disc':>6s}  {'flag':12s} description")
    print(f"  {'-'*6} {'-'*13} {'-'*6} {'-'*6} {'-'*6}  {'-'*12} {'-'*30}")
    for gid, g in out["goals"].items():
        chk = "—" if g["role_pair_checked_pct"] is None else f"{g['role_pair_checked_pct']:.0f}"
        unc = "—" if g["role_pair_unchecked_pct"] is None else f"{g['role_pair_unchecked_pct']:.0f}"
        disc = "—" if g["discrimination_pts"] is None else f"{g['discrimination_pts']:+.0f}"
        print(f"  {gid:6s} {g['category']:13s} {chk:>6s} {unc:>6s} {disc:>6s}"
              f"  {g['flag']:12s} {g['description'][:34]}")
    weak = [gid for gid, g in out["goals"].items()
            if g["flag"] in ("naive", "impossible", "vacuous", "weak")]
    if weak:
        print(f"\n  ⚠ non-informative goals: {', '.join(weak)} — tighten the "
              f"predicate, add a policy, or add a world-state assertion.")
    else:
        print("\n  ✓ every goal discriminates checked vs unchecked arms.")


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("usage: goal_quality.py <case_id> <run_dir> [<run_dir> ...]")
        sys.exit(2)
    case = Case.load(CASES_DIR / args[0])
    run_dirs = [Path(a).resolve() for a in args[1:]]
    out = analyse(case, run_dirs)
    print_report(out)
    dest = run_dirs[0] / "goal_quality.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWROTE {dest}")


if __name__ == "__main__":
    main()
