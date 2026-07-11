"""analysis.py — post-hoc analysis of a completed (or partial) human audit.

Run AFTER labeling:
    python -m experiments.seam_bench.judge.human_audit.analysis

Joins `labels.jsonl` (human verdicts) with `packet_key.jsonl` (the strata
audit_app.py never reads) and reports:

  1. Per-stratum agreement — for gold/easy_negative/hard_negative, how
     often the human's fit/no_fit label matched the packet's design
     `expected_label`.
  2. Intra-rater consistency on the ~20 repeat items — same content, two
     item_ids; agreement between the human's two labels for the pair is
     the §6 "per-seat self-consistency ... on duplicate canaries" check,
     applied to the human rater.
  3. The §6 human-agreement Wilson 95% lower bound, computed over the
     ORIGINAL (non-repeat) items only (n = 200 at the default packet
     size). Two modes:
       - PLACEHOLDER (default, no --panel-verdicts given): compares the
         human label against the packet's design `expected_label` — a
         proxy for "ensemble agrees with human" until real panel verdicts
         exist. Clearly flagged as a placeholder in the printed report.
       - REAL: if `--panel-verdicts PATH` points at a JSONL of
         {item_id, verdict: fit|no_fit} (the panel's aggregated per-item
         decision — see judge/aggregate.py), the join uses that instead,
         and the report is the actual §6 gate number.
  4. The full §6 gate checklist, with PASS/FAIL where this tool can
     compute the number and "N/A (panel-side)" where it can't (AUC,
     effective independent votes — those need panel runs, not this tool).

This module reuses `experiments/scripts/stats.py::wilson` (do not
re-implement the Wilson interval here).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
for p in (REPO_ROOT, REPO_ROOT / "experiments" / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from stats import wilson  # noqa: E402  (experiments/scripts/stats.py)

DEFAULT_LABELS = HERE / "labels.jsonl"
DEFAULT_KEY = HERE / "packet_key.jsonl"
GATE_THRESHOLD = 0.80
SELF_CONSISTENCY_THRESHOLD = 0.80


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def join(labels: list[dict], key: list[dict]) -> list[dict]:
    """Left join keyed on item_id: every key record, with its label
    attached if one exists (label=None otherwise). Labels with no matching
    key record are dropped with a warning printed by the caller."""
    labels_by_id = {r["item_id"]: r for r in labels}
    key_by_id = {r["item_id"]: r for r in key}

    orphan_labels = [iid for iid in labels_by_id if iid not in key_by_id]

    joined = []
    for k in key:
        lab = labels_by_id.get(k["item_id"])
        joined.append({
            **k,
            "label": lab["label"] if lab else None,
            "note": lab.get("note") if lab else None,
            "seconds_spent": lab.get("seconds_spent") if lab else None,
            "ts": lab.get("ts") if lab else None,
        })
    return joined, orphan_labels


def per_stratum_agreement(joined: list[dict]) -> dict[str, dict]:
    strata: dict[str, dict] = {}
    for rec in joined:
        if rec["label"] is None:
            continue
        s = rec["stratum"]
        bucket = strata.setdefault(s, {"n": 0, "agree": 0, "unsure": 0})
        bucket["n"] += 1
        if rec["label"] == "unsure":
            bucket["unsure"] += 1
        elif rec["label"] == rec["expected_label"]:
            bucket["agree"] += 1
    for s, bucket in strata.items():
        bucket["agree_rate"] = bucket["agree"] / bucket["n"] if bucket["n"] else 0.0
        bucket["unsure_rate"] = bucket["unsure"] / bucket["n"] if bucket["n"] else 0.0
    return strata


def intra_rater_consistency(joined: list[dict]) -> dict:
    by_id = {r["item_id"]: r for r in joined}
    n_pairs = 0
    consistent = 0
    both_labeled_pairs = []
    for rec in joined:
        if not rec["is_repeat"]:
            continue
        orig = by_id.get(rec["repeat_of"])
        if orig is None:
            continue
        if rec["label"] is None or orig["label"] is None:
            continue
        n_pairs += 1
        match = rec["label"] == orig["label"]
        if match:
            consistent += 1
        both_labeled_pairs.append(
            (rec["item_id"], orig["item_id"], rec["label"], orig["label"], match))
    rate = consistent / n_pairs if n_pairs else None
    return {
        "n_pairs": n_pairs, "consistent": consistent, "rate": rate,
        "pairs": both_labeled_pairs,
    }


def ensemble_vs_human(
    joined: list[dict], panel_verdicts: Optional[dict[str, str]],
) -> dict:
    """Wilson 95% lower bound on agreement, over ORIGINAL (non-repeat)
    items only. If `panel_verdicts` is None, `expected_label` (the
    packet's design assumption) stands in for the panel — flagged
    `is_placeholder=True`."""
    is_placeholder = panel_verdicts is None
    successes = 0
    n = 0
    for rec in joined:
        if rec["is_repeat"] or rec["label"] is None or rec["label"] == "unsure":
            continue
        n += 1
        other = (panel_verdicts.get(rec["item_id"]) if panel_verdicts
                  else rec["expected_label"])
        if other is not None and other == rec["label"]:
            successes += 1
    lo, hi = wilson(successes, n) if n else (0.0, 1.0)
    return {
        "is_placeholder": is_placeholder, "successes": successes, "n": n,
        "point": successes / n if n else 0.0, "wilson_lo": lo, "wilson_hi": hi,
    }


def swapped_pair_rejection(strata: dict[str, dict]) -> Optional[float]:
    """Human-side analogue of the §6 '>=95% rejection of swapped pairs'
    canary check: fraction of easy_negative items the human correctly
    called no_fit (i.e. agree_rate on that stratum, since expected_label
    for easy_negative is always 'no_fit')."""
    bucket = strata.get("easy_negative")
    return bucket["agree_rate"] if bucket else None


def load_panel_verdicts(path: Optional[str]) -> Optional[dict[str, str]]:
    if not path:
        return None
    rows = read_jsonl(Path(path))
    return {r["item_id"]: r["verdict"] for r in rows}


def print_report(
    strata: dict[str, dict], consistency: dict, gate_stat: dict,
    swap_rejection: Optional[float], total_items: int, total_labeled: int,
) -> None:
    print("=" * 72)
    print("Seam-Bench §6 human-audit report")
    print("=" * 72)
    print(f"\nlabeled {total_labeled} / {total_items} packet items\n")

    print("-- per-stratum agreement (human label vs. packet expected_label) --")
    for s in ("gold", "easy_negative", "hard_negative"):
        b = strata.get(s)
        if not b:
            print(f"  {s:16s} no labeled items yet")
            continue
        print(f"  {s:16s} n={b['n']:4d}  agree={b['agree']:4d} "
              f"({b['agree_rate']*100:5.1f}%)  unsure={b['unsure']:3d} "
              f"({b['unsure_rate']*100:4.1f}%)")

    print("\n-- intra-rater consistency (repeat items, human vs. own earlier label) --")
    if consistency["n_pairs"]:
        print(f"  n_pairs={consistency['n_pairs']}  consistent={consistency['consistent']}"
              f"  rate={consistency['rate']*100:.1f}%"
              f"  (§6 per-seat self-consistency threshold: "
              f"{SELF_CONSISTENCY_THRESHOLD*100:.0f}%)")
        verdict = "PASS" if consistency["rate"] >= SELF_CONSISTENCY_THRESHOLD else "FAIL"
        print(f"  -> {verdict}")
    else:
        print("  no repeat pairs with both sides labeled yet")

    print("\n-- §6 gate: human-agreement Wilson 95% lower bound >= "
          f"{GATE_THRESHOLD:.2f} --")
    tag = "PLACEHOLDER (vs. design expected_label — swap in --panel-verdicts " \
          "once panel verdicts exist)" if gate_stat["is_placeholder"] else \
          "REAL (vs. panel ensemble verdicts)"
    print(f"  mode: {tag}")
    print(f"  successes/n = {gate_stat['successes']}/{gate_stat['n']}"
          f"  point={gate_stat['point']*100:.1f}%"
          f"  wilson95=[{gate_stat['wilson_lo']*100:.1f}%, "
          f"{gate_stat['wilson_hi']*100:.1f}%]")
    if gate_stat["n"] == 0:
        print("  -> N/A (no non-repeat items labeled yet)")
    else:
        gate_pass = gate_stat["wilson_lo"] >= GATE_THRESHOLD
        print(f"  -> {'PASS' if gate_pass else 'FAIL'} "
              f"(lower bound {gate_stat['wilson_lo']*100:.1f}% "
              f"{'>=' if gate_pass else '<'} {GATE_THRESHOLD*100:.0f}%)")
    if gate_stat["n"] and gate_stat["n"] < 200:
        print(f"  NOTE: n={gate_stat['n']} < 200 — §6 requires n>=200 for "
              "an audit-power-honest gate; label more items.")

    print("\n-- full §6 gate checklist --")
    print("  [N/A - panel] AUC >= 0.85 gold vs. mutant (non-D2 strata, ensemble >= 0.90)")
    if swap_rejection is not None:
        sv = "PASS" if swap_rejection >= 0.95 else "FAIL"
        print(f"  [{sv}] >= 95% rejection of swapped pairs "
              f"(human proxy: {swap_rejection*100:.1f}% of easy_negative "
              "items correctly called no_fit)")
    else:
        print("  [N/A] >= 95% rejection of swapped pairs (no easy_negative labels yet)")
    if gate_stat["n"]:
        gp = "PASS" if gate_stat["wilson_lo"] >= GATE_THRESHOLD else "FAIL"
        print(f"  [{gp}] human-agreement Wilson 95% lower bound >= 0.80 (ensemble, n>=200)")
    else:
        print("  [N/A] human-agreement Wilson 95% lower bound >= 0.80 (ensemble, n>=200)")
    if consistency["n_pairs"]:
        cp = "PASS" if consistency["rate"] >= SELF_CONSISTENCY_THRESHOLD else "FAIL"
        print(f"  [{cp}] per-seat self-consistency >= 0.8 on duplicate canaries "
              "(human proxy)")
    else:
        print("  [N/A] per-seat self-consistency >= 0.8 on duplicate canaries")
    print("  [N/A - panel] effective independent votes >= 3")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default=str(DEFAULT_LABELS))
    ap.add_argument("--key", default=str(DEFAULT_KEY))
    ap.add_argument("--panel-verdicts", default=None,
                     help="optional JSONL of {item_id, verdict}; if omitted, "
                          "the Wilson-bound gate uses packet_key's "
                          "expected_label as a placeholder")
    args = ap.parse_args(argv)

    labels = read_jsonl(Path(args.labels))
    key = read_jsonl(Path(args.key))
    if not key:
        print(f"no packet_key.jsonl at {args.key} — build the packet first "
              "(packet_builder.py)")
        return 1

    joined, orphans = join(labels, key)
    if orphans:
        print(f"WARNING: {len(orphans)} labeled item_id(s) not found in "
              f"packet_key.jsonl (ignored): {orphans[:5]}"
              f"{'...' if len(orphans) > 5 else ''}")

    strata = per_stratum_agreement(joined)
    consistency = intra_rater_consistency(joined)
    panel_verdicts = load_panel_verdicts(args.panel_verdicts)
    gate_stat = ensemble_vs_human(joined, panel_verdicts)
    swap_rejection = swapped_pair_rejection(strata)

    total_labeled = sum(1 for r in joined if r["label"] is not None)
    print_report(strata, consistency, gate_stat, swap_rejection,
                 total_items=len(key), total_labeled=total_labeled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
