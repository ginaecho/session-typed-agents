"""splitter.py — D4: assign splits by FAMILY (SEAM_TRAINING_EXECUTION_PLAN.md
§3 "D4 — Splits (leakage rules are the whole game)").

The unit of assignment is the FAMILY (the EFSM signature of the seed
skeleton — see signature.py), never the individual record. Every
paraphrase (D2) and mutant (D3) of a given base protocol carries that
base's `family` value (by construction in d1_expand.py / d2_backtranslate
.py / d3_repair.py), so grouping by `family` and assigning the WHOLE group
to one split is suficient to guarantee "all paraphrases and mutants of one
skeleton live on one side of the line" — the leakage rule in the plan.

Stratified by (role_count, has_recursion, depth_bucket), computed once per
family from its representative protocol text (`protocol` for
DatasetRecord rows, `gold` for RepairRecord rows — both carry the same
`family` value for records that share a base).

train ~80% / dev ~10% / test-syn ~10% of FAMILIES within each stratum
(never test-real — that split is D5/mined territory, W8's job).

Usage:
    python splitter.py --in d1.jsonl d2.jsonl d3.jsonl --out-dir splits/ \
        --seed 1
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
for p in (REPO_ROOT, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common import role_count, has_recursion, depth_bucket, read_jsonl, write_jsonl  # noqa: E402

SPLITS = ["train", "dev", "test-syn"]


def _record_text(row: dict) -> str | None:
    return row.get("protocol") or row.get("gold")


def compute_strata(rows_by_file: dict[str, list[dict]]) -> dict[str, tuple]:
    """family -> (role_count, has_recursion, depth_bucket), computed from
    the first record seen for that family across all input files."""
    strata: dict[str, tuple] = {}
    for rows in rows_by_file.values():
        for row in rows:
            fam = row.get("family")
            if not fam or fam in strata:
                continue
            text = _record_text(row)
            if not text:
                continue
            strata[fam] = (role_count(text), has_recursion(text), depth_bucket(text))
    return strata


def assign_splits(strata: dict[str, tuple], seed: int,
                  train_frac: float = 0.8, dev_frac: float = 0.1
                  ) -> dict[str, str]:
    by_stratum: dict[tuple, list[str]] = defaultdict(list)
    for fam, key in strata.items():
        by_stratum[key].append(fam)

    rng = random.Random(seed)
    assignment: dict[str, str] = {}
    for key, fams in by_stratum.items():
        fams = sorted(fams)          # deterministic order before shuffling
        rng.shuffle(fams)
        n = len(fams)
        n_dev = round(n * dev_frac)
        n_test = round(n * (1 - train_frac - dev_frac))
        # guarantee at least one family in dev/test-syn once the stratum is
        # big enough to spare one, so no stratum is silently train-only
        if n >= 3:
            n_dev = max(n_dev, 1)
            n_test = max(n_test, 1)
        n_dev = min(n_dev, n)
        n_test = min(n_test, n - n_dev)
        dev_fams = fams[:n_dev]
        test_fams = fams[n_dev:n_dev + n_test]
        train_fams = fams[n_dev + n_test:]
        for f in dev_fams:
            assignment[f] = "dev"
        for f in test_fams:
            assignment[f] = "test-syn"
        for f in train_fams:
            assignment[f] = "train"
    return assignment


def strat_table(strata: dict[str, tuple], assignment: dict[str, str],
                rows_by_file: dict[str, list[dict]]) -> list[dict]:
    fam_records: dict[str, int] = defaultdict(int)
    for rows in rows_by_file.values():
        for row in rows:
            fam = row.get("family")
            if fam:
                fam_records[fam] += 1

    table: dict[tuple, dict[str, dict[str, int]]] = defaultdict(
        lambda: {s: {"families": 0, "records": 0} for s in SPLITS})
    for fam, key in strata.items():
        split = assignment.get(fam)
        if not split:
            continue
        table[key][split]["families"] += 1
        table[key][split]["records"] += fam_records[fam]

    rows = []
    for key in sorted(table, key=lambda k: (k[0], k[1], k[2])):
        nr, rec, db = key
        row = {"role_count": nr, "has_recursion": rec, "depth_bucket": db}
        for s in SPLITS:
            row[f"{s}_families"] = table[key][s]["families"]
            row[f"{s}_records"] = table[key][s]["records"]
        rows.append(row)
    return rows


def print_strat_table(rows: list[dict]) -> None:
    hdr = (f"{'roles':>5} {'rec':>3} {'depth':>8} | "
          f"{'train(fam/rec)':>15} {'dev(fam/rec)':>13} {'test-syn(fam/rec)':>18}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['role_count']:>5} {str(r['has_recursion']):>3} {r['depth_bucket']:>8} | "
              f"{r['train_families']:>6}/{r['train_records']:<7} "
              f"{r['dev_families']:>4}/{r['dev_records']:<7} "
              f"{r['test-syn_families']:>7}/{r['test-syn_records']:<7}")


def apply_and_write(rows_by_file: dict[str, list[dict]], assignment: dict[str, str],
                    out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {"unassignable": 0}
    for name, rows in rows_by_file.items():
        out_rows = []
        for row in rows:
            fam = row.get("family")
            split = assignment.get(fam)
            if split is None:
                counts["unassignable"] += 1
                continue
            row = dict(row)
            row["split"] = split
            out_rows.append(row)
        write_jsonl(out_dir / name, out_rows)
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inputs", nargs="+", required=True,
                    help="one or more JSONL files (DatasetRecord or RepairRecord rows)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--train-frac", type=float, default=0.8)
    ap.add_argument("--dev-frac", type=float, default=0.1)
    args = ap.parse_args(argv)

    rows_by_file = {Path(p).name: read_jsonl(Path(p)) for p in args.inputs}
    strata = compute_strata(rows_by_file)
    assignment = assign_splits(strata, args.seed, args.train_frac, args.dev_frac)
    table = strat_table(strata, assignment, rows_by_file)

    out_dir = Path(args.out_dir)
    counts = apply_and_write(rows_by_file, assignment, out_dir)

    (out_dir / "family_registry.json").write_text(
        json.dumps(assignment, indent=0), encoding="utf-8")
    (out_dir / "strat_table.json").write_text(
        json.dumps(table, indent=2), encoding="utf-8")

    n_fam = len(strata)
    by_split = defaultdict(int)
    for s in assignment.values():
        by_split[s] += 1
    print(f"[splitter] {n_fam} families across {len(rows_by_file)} file(s); "
          f"train={by_split['train']} dev={by_split['dev']} "
          f"test-syn={by_split['test-syn']} families "
          f"(unassignable records skipped: {counts['unassignable']})")
    print()
    print_strat_table(table)
    print(f"\nwrote {out_dir}/ (family_registry.json, strat_table.json, "
          f"and one split-populated copy per input file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
