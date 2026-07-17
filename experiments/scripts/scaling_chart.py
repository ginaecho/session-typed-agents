"""scaling_chart.py — the "does the saving grow with team size?" experiment.

Why this experiment matters (docs/BENCHMARK_FAIRNESS_REVIEW.md, item 2 of
"How to make STJP's advantages genuinely convincing"): a single "9x cheaper"
number on one case can always be argued with. The structural claim cannot:
an agent that is handed only ITS OWN slice of the plan reads a prompt whose
size stays roughly constant as the team grows, while an agent handed the
WHOLE plan as text re-reads a prompt that grows with every added role. So
tokens-per-delivered-result should stay flat for the sliced arms and climb
for the whole-plan arm as the team grows — two lines that spread apart.
A small example: with 6 roles the whole plan is ~25 lines and one role's
slice is ~4; at 10 roles the plan is ~45 lines but the slice is still ~4.

This script has two halves:

  run   Drive the live benchmark over cases of growing team size, one arm
        at a time (sequential — trustworthy wall-clock), restricted to the
        arms the chart compares. Needs Azure credentials (same as
        case_runner.py). Roughly: n_cases x n_arms x n_trials full trials.

  plot  Needs NO Azure. Read each case's latest summary.json, pull
        tokens-per-success per arm, and write both the chart data
        (scaling_chart.json) and the chart itself (scaling_chart.png,
        if matplotlib is installed). Also overlays the no-LLM structural
        proxy from roles_sweep.py when its output file is present, so the
        measured curve can be compared against the predicted shape.

Usage:
  python scripts/scaling_chart.py run  [--cases report_pipeline,report_pipeline_large]
                                       [--trials 10] [--arms k1,k2,...]
  python scripts/scaling_chart.py plot [--cases ...] [-o experiments/reports/scaling]
                                       [--proxy experiments/reports/e6/roles_sweep.json]

Default arms (each isolates one thing on the chart):
  global_decentralized      whole plan as text, same runner as the others
  min_llmvalid_gate         per-role slice + enforcement gate (round-robin)
  min_llmvalid_gate_lastrecv  slice + gate + cheap "ask the last receiver"
                              heuristic (the non-protocol scheduling control)
  min_llmvalid_sched        slice + gate + protocol-derived EFSM scheduler
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
CASES_DIR = EXPERIMENTS_DIR / "cases"
sys.path.insert(0, str(HERE))

DEFAULT_CASES = ["report_pipeline", "report_pipeline_large"]
DEFAULT_ARMS = ["global_decentralized", "min_llmvalid_gate",
                "min_llmvalid_gate_lastrecv", "min_llmvalid_sched"]


def _n_roles(case_id: str) -> int:
    data = yaml.safe_load((CASES_DIR / case_id / "case.yaml")
                          .read_text(encoding="utf-8"))
    return len(data["roles"])


def _latest_run_dir(case_id: str) -> Path | None:
    case_dir = CASES_DIR / case_id
    latest = case_dir / "LATEST"
    if latest.exists():
        p = case_dir / "runs" / latest.read_text(encoding="utf-8").strip()
        if (p / "summary.json").exists():
            return p
    runs = sorted((case_dir / "runs").glob("*")) \
        if (case_dir / "runs").exists() else []
    for p in reversed(runs):
        if (p / "summary.json").exists():
            return p
    return None


# ---------------------------------------------------------------------------
# run — live benchmark over the case ladder (needs Azure)
# ---------------------------------------------------------------------------

def cmd_run(cases: list[str], arms: list[str], trials: int) -> int:
    import case_runner
    known = {k for k, _, _ in case_runner.SCENARIOS}
    unknown = [a for a in arms if a not in known]
    if unknown:
        print(f"unknown arms {unknown} (known: {sorted(known)})")
        return 2
    # Same slice-assign trick as case_runner --arms: every module holding a
    # reference to the registry list sees the filter.
    case_runner.SCENARIOS[:] = [s for s in case_runner.SCENARIOS
                                if s[0] in arms]
    for cid in cases:
        print(f"\n{'#'*72}\n#  SCALING RUN: {cid} ({_n_roles(cid)} roles), "
              f"n={trials}, arms={arms}\n{'#'*72}")
        # sequential=True: one arm at a time — the chart also quotes seconds,
        # and contended seconds are exactly what the fairness review forbids.
        case_runner.run_case(cid, trials, sequential=True)
    print("\nAll scaling runs finished. Now: "
          "python scripts/scaling_chart.py plot")
    return 0


# ---------------------------------------------------------------------------
# plot — chart data + PNG from existing summaries (no Azure)
# ---------------------------------------------------------------------------

def cmd_plot(cases: list[str], arms: list[str], out: Path,
             proxy_path: Path | None) -> int:
    rows = []
    for cid in cases:
        run_dir = _latest_run_dir(cid)
        if run_dir is None:
            print(f"  SKIP {cid}: no run with summary.json yet "
                  f"(run the 'run' subcommand first)")
            continue
        summary = json.loads((run_dir / "summary.json")
                             .read_text(encoding="utf-8"))
        mode = summary.get("execution_mode", "unknown")
        for arm in arms:
            sc = summary.get("scenarios", {}).get(arm)
            if not sc or not sc.get("n_trials"):
                print(f"  SKIP {cid}/{arm}: not in {run_dir.name}")
                continue
            rows.append({
                "case": cid,
                "n_roles": _n_roles(cid),
                "arm": arm,
                "tokens_per_success": sc.get("avg_tokens_per_success") or None,
                "tokens_per_trial": sc.get("avg_tokens_per_trial"),
                "calls_per_trial": sc.get("avg_calls_per_trial"),
                "seconds_per_success": sc.get("avg_seconds_per_success"),
                "success_rate_pct": sc.get("success_rate_pct"),
                "success_rate_ci95_pct": sc.get("success_rate_ci95_pct"),
                "execution_mode": mode,
                "run_dir": str(run_dir),
            })

    proxy_rows = []
    if proxy_path and proxy_path.exists():
        proxy_rows = json.loads(
            proxy_path.read_text(encoding="utf-8")).get("rows", [])

    out.mkdir(parents=True, exist_ok=True)
    (out / "scaling_chart.json").write_text(json.dumps({
        "what": "tokens-per-delivered-result vs team size, per arm",
        "claim_under_test": "per-role slices keep cost flat as the team "
                            "grows; whole-plan-as-text cost climbs",
        "rows": rows,
        "structural_proxy_rows": proxy_rows,
    }, indent=2), encoding="utf-8")
    print(f"  WROTE {out / 'scaling_chart.json'} ({len(rows)} points)")

    # Console table — always available, chart or not.
    if rows:
        print(f"\n  {'case':24s} {'roles':>5s} {'arm':28s} "
              f"{'tok/success':>12s} {'calls':>6s} {'succ%':>6s}")
        for r in sorted(rows, key=lambda r: (r["n_roles"], r["arm"])):
            tps = r["tokens_per_success"]
            print(f"  {r['case']:24s} {r['n_roles']:5d} {r['arm']:28s} "
                  f"{tps if tps is not None else float('nan'):12.0f} "
                  f"{r['calls_per_trial']:6.1f} {r['success_rate_pct']:6.1f}")
        if any(r["execution_mode"] != "sequential" for r in rows):
            print("  NOTE: some points come from parallel (contended) runs — "
                  "token numbers are fine, ignore their seconds.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not installed — JSON written, PNG skipped "
              "(pip install matplotlib)")
        return 0

    if not rows:
        print("  no data points; PNG skipped")
        return 0

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for arm in arms:
        pts = sorted((r for r in rows if r["arm"] == arm),
                     key=lambda r: r["n_roles"])
        if not pts:
            continue
        xs = [r["n_roles"] for r in pts]
        ys = [r["tokens_per_success"] if r["tokens_per_success"] is not None
              else float("nan") for r in pts]
        ax.plot(xs, ys, marker="o", label=arm)
    ax.set_xlabel("team size (number of roles)")
    ax.set_ylabel("tokens per delivered result")
    ax.set_title("Coordination cost vs team size\n"
                 "(flat = per-role slices scale; climbing = whole-plan text "
                 "does not)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    png = out / "scaling_chart.png"
    fig.savefig(png, dpi=150)
    print(f"  WROTE {png}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="drive live runs (needs Azure)")
    p_plot = sub.add_parser("plot", help="build chart from existing runs")
    for p in (p_run, p_plot):
        p.add_argument("--cases", default=",".join(DEFAULT_CASES),
                       help="comma-separated case ids, small team first")
        p.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    p_run.add_argument("--trials", type=int, default=10)
    p_plot.add_argument("-o", "--out",
                        default=str(EXPERIMENTS_DIR / "reports" / "scaling"))
    p_plot.add_argument("--proxy",
                        default=str(EXPERIMENTS_DIR / "reports" / "e6"
                                    / "roles_sweep.json"),
                        help="roles_sweep.py output to embed as the "
                             "structural-proxy overlay (optional)")
    args = ap.parse_args()

    cases = [c.strip() for c in args.cases.split(",") if c.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for cid in cases:
        if not (CASES_DIR / cid / "case.yaml").exists():
            print(f"unknown case: {cid}")
            return 2

    if args.cmd == "run":
        return cmd_run(cases, arms, args.trials)
    return cmd_plot(cases, arms, Path(args.out), Path(args.proxy))


if __name__ == "__main__":
    raise SystemExit(main())
