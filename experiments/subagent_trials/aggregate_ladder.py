"""aggregate_ladder.py — build the finance-style ladder table from per-trial reports.

Scans a run root for <arm>__trial_*/report.json produced by engine_ladder.py and
emits the GCR / CGC / Disasters / Cost-to-goal / Seconds table (per arm), plus a
JSON summary. Trials with no report.json (agent never finished) are counted as
NOT reached (a fair, non-inflating default) and flagged.

    python experiments/subagent_trials/aggregate_ladder.py \
        --root /tmp/ladder_run/escrow_trade --case escrow_trade \
        --out experiments/reports/n100/ladder_escrow
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ARM_ORDER = ["intent", "global_text", "local_obs", "local_gate", "min_gate", "stjp"]
ARM_LABEL = {
    "intent": "A: Intent only", "global_text": "B: Global text",
    "local_obs": "C-min: Local contract", "local_gate": "C+spec: Local + gate",
    "min_gate": "C+min: Local + gate", "stjp": "STJP: +scheduler",
}


def collect(root: Path, arm: str) -> dict:
    dirs = sorted(root.glob(f"{arm}__trial_*"))
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
        "cost_to_goal_calls": round(calls / gcr, 1) if gcr > 0 else None,
        "avg_seconds": round(sum(secs) / len(secs), 1) if secs else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    root = Path(args.root)
    rows = [collect(root, a) for a in ARM_ORDER]
    rows = [r for r in rows if r["n"] > 0]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {"case": args.case, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "cost_unit": "LLM agent-calls (no Foundry; tokens not metered)",
               "rows": rows}
    (out / "ladder_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # markdown table
    hdr = "| arm | GCR | CGC | Disasters | Cost-to-goal (calls) | Sec/trial | n (missing) |"
    sep = "|---|---|---|---|---|---|---|"
    lines = [f"# Ladder table — {args.case} (no Foundry, cheap subagents)", "",
             f"Cost unit = **LLM agent-calls** (tokens are not metered without "
             f"Foundry; calls are the model-independent coordination-cost proxy).", "",
             hdr, sep]
    for r in rows:
        c2g = r["cost_to_goal_calls"] if r["cost_to_goal_calls"] is not None else "∞"
        sec = r["avg_seconds"] if r["avg_seconds"] is not None else "—"
        miss = f"{r['n']} ({r['missing']})" if r["missing"] else f"{r['n']}"
        lines.append(f"| {r['label']} | {r['GCR_pct']}% | {r['CGC_pct']}% | "
                     f"{r['disasters']} | {c2g} | {sec} | {miss} |")
    (out / "ladder_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {out}/ladder_summary.json and ladder_table.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
