"""mutation_bench.py — E1: does the checker catch bad protocols? (§2)

For a corpus of VALID protocols:
  1. baseline: validate every untouched protocol -> FALSE-POSITIVE rate
     (a good protocol the validator wrongly rejects).
  2. per defect class: apply the mutation, validate the mutant, record whether
     the checker REJECTED it (true positive / caught) and which stage caught it
     (Scribble core message vs. a surviving mutant that still validated).

A "surviving mutant" (validator still accepts) is either a semantically-
equivalent mutation (harmless) or a real completeness gap; we report the count
honestly rather than hiding it.

    python experiments/scripts/mutation_bench.py --corpus protocols/corpus \
        --classes all --n 60 -o experiments/reports/e1

Writes <out>/mutation_results.csv and <out>/mutation_summary.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from stjp_core.compiler.validator import ScribbleValidator          # noqa: E402
from mutate_protocol import (mutate, CLASSES, WELLFORMED_DEFECTS,   # noqa: E402
                             REORDER_OPS)


def _module_stem(text: str) -> str:
    import re
    m = re.search(r"module\s+(\w+)\s*;", text)
    return m.group(1) if m else "mutant"


def run(corpus_dir: Path, classes: list[str], n: int, out: Path,
        seed: int = 1) -> dict:
    validator = ScribbleValidator()
    corpus = sorted(corpus_dir.glob("*.scr"))
    if not corpus:
        raise SystemExit(f"no .scr files in {corpus_dir} — run gen_corpus.py first")
    out.mkdir(parents=True, exist_ok=True)
    work = out / "_mutants"
    work.mkdir(exist_ok=True)
    rng = random.Random(seed)

    rows = []

    # 1. baseline false positives
    fp = 0
    for p in corpus:
        ok, err = validator.validate_protocol(p)
        rows.append({"file": p.name, "class": "BASELINE",
                     "verdict": "accept" if ok else "reject",
                     "error": "" if ok else err.splitlines()[0][:120]})
        if not ok:
            fp += 1

    # 2. mutants per class
    per_class = {}
    for cls in classes:
        caught = applied = survived = 0
        for p in corpus:
            text = p.read_text(encoding="utf-8")
            mutant = mutate(text, cls, rng)
            if mutant is None:
                continue                      # operator not applicable
            applied += 1
            stem = _module_stem(mutant)
            mp = work / f"{stem}.scr"
            mp.write_text(mutant, encoding="utf-8")
            ok, err = validator.validate_protocol(mp)
            mp.unlink(missing_ok=True)
            if ok:
                survived += 1
                rows.append({"file": p.name, "class": cls, "verdict": "SURVIVED",
                             "error": "(mutant still validates — equivalent or gap)"})
            else:
                caught += 1
                rows.append({"file": p.name, "class": cls, "verdict": "caught",
                             "error": err.splitlines()[0][:120]})
        per_class[cls] = {
            "applied": applied, "caught": caught, "survived": survived,
            "detection_rate_pct": round(100 * caught / applied, 1) if applied else None,
        }

    # write CSV + JSON
    with (out / "mutation_results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "class", "verdict", "error"])
        w.writeheader()
        w.writerows(rows)

    def _group_rate(names):
        a = sum(per_class[c]["applied"] for c in names if c in per_class)
        cc = sum(per_class[c]["caught"] for c in names if c in per_class)
        return {"applied": a, "caught": cc,
                "detection_rate_pct": round(100 * cc / a, 1) if a else None}

    summary = {
        "corpus_dir": str(corpus_dir),
        "corpus_size": len(corpus),
        "false_positives": fp,
        "false_positive_rate_pct": round(100 * fp / len(corpus), 1),
        "per_class": per_class,
        "wellformedness_defects": _group_rate(WELLFORMED_DEFECTS),
        "reordering_ops": _group_rate(REORDER_OPS),
        "note": ("wellformedness_defects carry the soundness claim (Scribble "
                 "should reject); reordering_ops usually yield another VALID "
                 "protocol on acyclic inputs, so low detection there is correct "
                 "behaviour, not a checker miss."),
    }
    (out / "mutation_summary.json").write_text(json.dumps(summary, indent=2),
                                               encoding="utf-8")
    # cleanup work dir
    for f in work.glob("*.scr"):
        f.unlink()
    work.rmdir()
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="protocols/corpus")
    ap.add_argument("--classes", default="all")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("-o", "--out", default="experiments/reports/e1")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    classes = CLASSES if args.classes == "all" else args.classes.split(",")

    summary = run(Path(args.corpus), classes, args.n, Path(args.out), args.seed)

    print(f"\nE1 MUTATION BENCH — corpus {summary['corpus_size']} protocols, "
          f"false positives {summary['false_positives']}/{summary['corpus_size']} "
          f"= {summary['false_positive_rate_pct']}%\n")
    def _row(cls):
        r = summary["per_class"][cls]
        dr = "n/a" if r["detection_rate_pct"] is None else f"{r['detection_rate_pct']}%"
        print(f"  {cls:22s} {r['applied']:8d} {r['caught']:7d} {r['survived']:9d} {dr:>10s}")

    hdr = f"  {'class':22s} {'applied':>8s} {'caught':>7s} {'survived':>9s} {'detection':>10s}"
    print("WELL-FORMEDNESS DEFECTS (soundness — Scribble should reject):")
    print(hdr); print("  " + "-" * 58)
    for cls in WELLFORMED_DEFECTS:
        if cls in summary["per_class"]:
            _row(cls)
    g = summary["wellformedness_defects"]
    print(f"  {'GROUP':22s} {g['applied']:8d} {g['caught']:7d} {'':9s} "
          f"{str(g['detection_rate_pct']) + '%':>10s}")
    print("\nREORDERING OPS (usually yield another VALID protocol — low = correct):")
    print(hdr); print("  " + "-" * 58)
    for cls in REORDER_OPS:
        if cls in summary["per_class"]:
            _row(cls)
    print(f"\nWROTE {args.out}/mutation_summary.json + mutation_results.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
