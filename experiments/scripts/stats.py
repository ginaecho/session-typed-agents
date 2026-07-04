"""stats.py — operator-grade reliability stats (BENCHMARK_PLAN_V2 §5 / E4).

pass@1 asks "did one run work". An unattended deployment needs pass^k: "did ALL
of the last k runs work". A 97%-per-run system fails one 10-run batch in four.

Pure-Python (no scipy): Wilson score interval + pass^k. `summarize_arm` turns
successes/trials into the row the paper's Table 5 wants. `table_from_reports`
reads the subagent-trial report JSONs (real data) and emits that table.

    python experiments/scripts/stats.py --from-subagent-trials
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def wilson(successes: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Returns (lo, hi) in
    [0,1]. z=1.96 -> 95%."""
    if n == 0:
        return 0.0, 1.0
    phat = successes / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def pass_k(per_run_success: float, k: int = 10) -> float:
    """P(all k independent runs succeed) = p^k."""
    return per_run_success ** k


def summarize_arm(name: str, successes: int, n: int, k: int = 10) -> dict:
    p = successes / n if n else 0.0
    lo, hi = wilson(successes, n)
    return {
        "arm": name,
        "successes": successes,
        "n": n,
        "per_run_success_pct": round(100 * p, 1),
        "wilson95_lo_pct": round(100 * lo, 1),
        "wilson95_hi_pct": round(100 * hi, 1),
        "passk_point": round(pass_k(p, k), 3),
        "passk_at_ci_lo": round(pass_k(lo, k), 3),
        "k": k,
    }


def print_table(rows: list[dict]) -> None:
    hdr = (f"{'arm':22s} {'succ/n':>8s} {'per-run':>8s} "
           f"{'95% CI (Wilson)':>18s} {'pass^k':>7s} {'pass^k@CIlo':>11s}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        ci = f"[{r['wilson95_lo_pct']:.1f}, {r['wilson95_hi_pct']:.1f}]%"
        print(f"{r['arm']:22s} {str(r['successes']) + '/' + str(r['n']):>8s} "
              f"{r['per_run_success_pct']:7.1f}% {ci:>18s} "
              f"{r['passk_point']:7.3f} {r['passk_at_ci_lo']:11.3f}")


def table_from_reports(k: int = 10) -> list[dict]:
    """Build Table 5 from the REAL subagent-trial reports (n=10 each)."""
    rep = HERE.parent / "subagent_trials" / "reports"
    rows = []
    mapping = [
        ("A unchecked (prose skills)", "e2_unchecked_report.json"),
        ("C+ STJP (gate+sched)", "e2_stjp_report.json"),
        ("C+ STJP extended", "e3_ext_report.json"),
    ]
    for name, fname in mapping:
        p = rep / fname
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        rows.append(summarize_arm(name, d["success"], d["trials"], k))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-subagent-trials", action="store_true")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("-o", "--out", default="reports/e4")
    args = ap.parse_args()

    if args.from_subagent_trials:
        rows = table_from_reports(args.k)
        source = "real subagent-trial reports (n=10 each)"
    else:
        # illustrative n=30 placeholder ladder from the plan (SYNTH targets)
        rows = [summarize_arm("A intent [SYNTH]", 0, 30, args.k),
                summarize_arm("B global text [SYNTH]", 29, 30, args.k),
                summarize_arm("C local observer [SYNTH]", 24, 30, args.k),
                summarize_arm("C+ full STJP [SYNTH]", 30, 30, args.k)]
        source = "SYNTH placeholder targets (n=30) — replace with real n=30 runs"

    print(f"\nE4 RELIABILITY — {source}, pass^{args.k}\n")
    print_table(rows)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "passk_table.json").write_text(
        json.dumps({"k": args.k, "source": source, "rows": rows}, indent=2),
        encoding="utf-8")
    print(f"\nWROTE {out}/passk_table.json")
    if any("SYNTH" not in r["arm"] for r in rows):
        b = next((r for r in rows if r["per_run_success_pct"] < 100
                  and r["per_run_success_pct"] > 0), None)
        if b:
            print(f"\nRead-out: {b['arm']} at {b['per_run_success_pct']}% per run "
                  f"-> pass^{args.k} = {b['passk_point']} "
                  f"(≈1 in {round(1/(1-b['passk_point']))} batches of {args.k} fails).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
