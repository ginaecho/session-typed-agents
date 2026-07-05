"""aggregate_ladder.py — build the finance-style ladder table from per-trial reports.

Scans a run root for <arm>__trial_*/report.json produced by engine_ladder.py and
emits the GCR / CGC / Disasters / Cost-to-goal / Seconds table (per arm), plus a
JSON summary. Trials with no report.json (agent never finished) are counted as
NOT reached (a fair, non-inflating default) and flagged.

Cost is native in **agent-calls** (no Foundry ⇒ tokens not metered). With
`--dollars` (default on) a `Cost-to-goal ($, est.)` column is derived by pricing
each call as one lean haiku call — ~1k input + ~50 output tokens at Haiku 4.5's
$1/$5 per 1M ⇒ ≈ $0.00125/call (override with `--price-per-call`). This is an
estimate overlaid on the measured calls, not a metered token figure; see
experiments/reports/n100/COST_ESTIMATE.md.

    python experiments/subagent_trials/aggregate_ladder.py \
        --root /tmp/ladder_run/escrow_trade --case escrow_trade \
        --out experiments/reports/n100/ladder_escrow
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

# default price of one lean production agent call, haiku 4.5:
# ~1000 input tokens @ $1.00/1M + ~50 output tokens @ $5.00/1M ≈ $0.00125
DEFAULT_PRICE_PER_CALL = 0.00125

ARM_ORDER = ["intent", "global_text", "local_obs", "local_gate", "min_gate", "stjp"]
ARM_LABEL = {
    "intent": "A: Intent only", "global_text": "B: Global text",
    "local_obs": "C-min: Local contract", "local_gate": "C+spec: Local + gate",
    "min_gate": "C+min: Local + gate", "stjp": "STJP: +scheduler",
}


def collect(root: Path, arm: str, limit: int | None = None) -> dict:
    dirs = sorted(root.glob(f"{arm}__trial_*"))
    if limit is not None:
        dirs = dirs[:limit]
    reached = clean = disasters = calls = 0
    secs = []
    missing = n = 0
    for d in dirs:
        n += 1
        rp = d / "report.json"
        if not rp.exists():
            missing += 1
            continue
        rep = json.loads(rp.read_text(encoding="utf-8"))
        t = rep["per_trial"][0]
        if t["reached_goal"]:
            reached += 1
        if t["clean"]:
            clean += 1
        disasters += t["disasters"]
        calls += t["agent_calls"]
        if t["seconds"] is not None:
            secs.append(t["seconds"])
    gcr = reached / n if n else 0.0
    return {
        "arm": arm, "label": ARM_LABEL[arm], "n": n,
        "reached": reached, "clean": clean, "missing": missing,
        "GCR_pct": round(100 * gcr, 1),
        "CGC_pct": round(100 * clean / n, 1) if n else 0.0,
        "disasters": disasters,
        "total_calls": calls,
        "avg_calls_per_trial": round(calls / n, 1) if n else None,
        "cost_to_goal_calls": round(calls / gcr, 1) if gcr > 0 else None,
        "avg_seconds": round(sum(secs) / len(secs), 1) if secs else None,
    }


def _usd(cost_calls, price):
    """Dollar cost from a cost-in-calls figure, or None if cost is undefined."""
    return round(cost_calls * price, 4) if cost_calls is not None else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dollars", action=argparse.BooleanOptionalAction, default=True,
                    help="add an estimated Cost-to-goal ($) column (default on; "
                         "--no-dollars to omit)")
    ap.add_argument("--price-per-call", type=float, default=DEFAULT_PRICE_PER_CALL,
                    help=f"USD per lean agent call for the $ estimate "
                         f"(default {DEFAULT_PRICE_PER_CALL} = ~1k in + ~50 out at haiku $1/$5 per 1M)")
    args = ap.parse_args()
    root = Path(args.root)
    price = args.price_per_call
    rows = [collect(root, a) for a in ARM_ORDER]
    rows = [r for r in rows if r["n"] > 0]
    if args.dollars:
        for r in rows:
            r["cost_to_goal_usd"] = _usd(r["cost_to_goal_calls"], price)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {"case": args.case, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "cost_unit": "LLM agent-calls (no Foundry; tokens not metered)",
               "rows": rows}
    if args.dollars:
        summary["dollar_estimate"] = {
            "price_per_call_usd": price,
            "basis": "one lean haiku call ~1k input + ~50 output tokens at Haiku 4.5 $1/$5 per 1M",
            "note": "estimate overlaid on measured calls, not metered tokens; see COST_ESTIMATE.md",
        }
    (out / "ladder_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # markdown table
    dollar_hdr = " Cost-to-goal ($, est.) |" if args.dollars else ""
    dollar_sep = "---|" if args.dollars else ""
    hdr = f"| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) |{dollar_hdr} n (missing) |"
    sep = f"|---|---|---|---|---|---|{dollar_sep}---|"
    intro = ("Cost unit = **LLM agent-calls** (tokens are not metered without "
             "Foundry; calls are the model-independent coordination-cost proxy). "
             "Cost-to-goal = total calls / GCR-fraction, the finance table's "
             "\"true cost per delivered result\".")
    if args.dollars:
        intro += (f"\n\nThe **$** column is an estimate: cost-to-goal (calls) × "
                  f"≈ **${price:g}** per lean haiku call (~1k in + ~50 out at $1/$5 per 1M). "
                  f"Method: [`COST_ESTIMATE.md`](../COST_ESTIMATE.md#per-arm-cost-to-goal-in-dollars-the--column-in-the-ladder-tables).")
    lines = [f"# Ladder table — {args.case} (no Foundry, cheap subagents)", "",
             intro, "", hdr, sep]
    for r in rows:
        c2g = r["cost_to_goal_calls"] if r["cost_to_goal_calls"] is not None else "∞"
        cpt = r["avg_calls_per_trial"] if r["avg_calls_per_trial"] is not None else "—"
        miss = f"{r['n']} ({r['missing']})" if r["missing"] else f"{r['n']}"
        dollar_cell = ""
        if args.dollars:
            usd = r.get("cost_to_goal_usd")
            dollar_cell = f" ${usd:.2f} |" if usd is not None else " ∞ |"
        lines.append(f"| {r['label']} | {r['GCR_pct']}% | {r['CGC_pct']}% | "
                     f"{r['disasters']} | {cpt} | {c2g} |{dollar_cell} {miss} |")
    (out / "ladder_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {out}/ladder_summary.json and ladder_table.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
