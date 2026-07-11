"""leakage_check.py — D4 done-criterion: asserts split hygiene is green.

Three checks over the split-populated JSONL files written by splitter.py:

  1. no signature (family) appears in two splits.
  2. no SEED family straddles: for every genuine corpus/named-case seed
     (common.all_seeds()), all records sharing that seed's own family sit
     in exactly the split that seed's family was assigned to.
  3. re-derives the strat table from the files on disk (not from
     splitter.py's cached strat_table.json) and prints it, cross-checking
     against the cached one so a hand-edited split file would be caught.

Exit code 0 (green) iff all three pass — this is the W3 done-criterion.

Usage:
    python leakage_check.py --split-dir splits/ \
        --files d1_dataset.jsonl d2_backtranslate.jsonl d3_repair.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
for p in (REPO_ROOT, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common import all_seeds, read_jsonl                                 # noqa: E402
from signature import SignatureCache                                     # noqa: E402
from splitter import compute_strata, strat_table, print_strat_table, SPLITS  # noqa: E402


def check_no_family_in_two_splits(rows_by_file: dict[str, list[dict]]) -> tuple[bool, list]:
    fam_splits: dict[str, set] = defaultdict(set)
    for rows in rows_by_file.values():
        for row in rows:
            fam = row.get("family")
            split = row.get("split")
            if fam and split:
                fam_splits[fam].add(split)
    offenders = [{"family": f, "splits": sorted(s)} for f, s in fam_splits.items() if len(s) > 1]
    return len(offenders) == 0, offenders


def check_no_seed_straddle(rows_by_file: dict[str, list[dict]], sig_cache: SignatureCache
                           ) -> tuple[bool, list]:
    seeds = all_seeds()
    fam_splits: dict[str, set] = defaultdict(set)
    for rows in rows_by_file.values():
        for row in rows:
            fam = row.get("family")
            split = row.get("split")
            if fam and split:
                fam_splits[fam].add(split)

    offenders = []
    for s in seeds:
        try:
            fam = sig_cache.signature(s.text)
        except Exception as e:
            offenders.append({"seed_case": s.seed_case, "error": f"signature failed: {e}"})
            continue
        splits = fam_splits.get(fam, set())
        if len(splits) > 1:
            offenders.append({"seed_case": s.seed_case, "family": fam,
                             "splits": sorted(splits)})
    return len(offenders) == 0, offenders


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split-dir", required=True)
    ap.add_argument("--files", nargs="+", required=True,
                    help="filenames (relative to --split-dir) to check")
    ap.add_argument("--cache", default=str(HERE / ".sig_cache.json"))
    args = ap.parse_args(argv)

    split_dir = Path(args.split_dir)
    rows_by_file = {f: read_jsonl(split_dir / f) for f in args.files}
    sig_cache = SignatureCache(Path(args.cache) if args.cache else None)

    ok1, offenders1 = check_no_family_in_two_splits(rows_by_file)
    ok2, offenders2 = check_no_seed_straddle(rows_by_file, sig_cache)

    strata = compute_strata(rows_by_file)
    fam_split = {}
    for rows in rows_by_file.values():
        for row in rows:
            if row.get("family") and row.get("split"):
                fam_split[row["family"]] = row["split"]
    table = strat_table(strata, fam_split, rows_by_file)

    cached_table_path = split_dir / "strat_table.json"
    ok3, table_diff = True, None
    if cached_table_path.exists():
        cached = json.loads(cached_table_path.read_text(encoding="utf-8"))
        ok3 = cached == table
        if not ok3:
            table_diff = {"cached_rows": len(cached), "recomputed_rows": len(table)}

    print("=" * 70)
    print("LEAKAGE CHECK")
    print("=" * 70)
    print(f"[1] no family in two splits: {'PASS' if ok1 else 'FAIL'} "
          f"({len(offenders1)} offending families)")
    if offenders1:
        for o in offenders1[:10]:
            print(f"      {o}")
    print(f"[2] no seed family straddles: {'PASS' if ok2 else 'FAIL'} "
          f"({len(offenders2)} offending seeds)")
    if offenders2:
        for o in offenders2[:10]:
            print(f"      {o}")
    print(f"[3] strat table matches splitter.py's cached table: "
          f"{'PASS' if ok3 else 'FAIL (or no cached table found)'}")
    print()
    print_strat_table(table)
    print()

    all_ok = ok1 and ok2 and ok3
    print(f"VERDICT: {'GREEN — all leakage checks pass' if all_ok else 'RED — see offenders above'}")
    sig_cache.save()
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
