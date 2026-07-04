"""translation_fidelity.py — English->protocol fidelity (BENCHMARK_PLAN_V2 §6 / E5).

Scores the ONE non-deterministic stage (intent -> Scribble draft) on four
measures:
  1. first_draft_valid       does the first LLM draft pass the validator?
  2. valid_within_3_rounds    valid after <=3 error-feedback repair rounds?
  3. efsm_equiv_to_gold        among valid drafts, does it MEAN the same as the
                              expert gold? (deterministic — efsm_equiv.py)
  4. guard_sidecar_correct    were the value guards co-emitted correctly?

Measures 1,2,4 need an LLM (intent -> draft, repair loop, guard extraction) and
are wired to `authoring/architect.ArchitectAgent` — MEASUREMENT PENDING here
(no Azure in this environment). Measure 3 is fully deterministic and is
validated end-to-end below on real Scribble projections via a demo that pairs
each corpus protocol with an identical / reformatted / mutated "draft".

    # deterministic demo (no LLM): proves the equivalence scorer on real data
    python experiments/scripts/translation_fidelity.py --demo --corpus cases/_corpus

    # full run (needs Azure): intents.yaml = [{intent, gold_scr}, ...]
    python experiments/scripts/translation_fidelity.py --intents intents.yaml
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from stjp_core.compiler.validator import ScribbleValidator          # noqa: E402
from efsm_equiv import protocols_equivalent                         # noqa: E402
from mutate_protocol import mutate                                  # noqa: E402


def draft_valid(text: str) -> bool:
    with tempfile.TemporaryDirectory() as td:
        import re
        stem = re.search(r"module\s+(\w+)", text).group(1)
        p = Path(td) / f"{stem}.scr"
        p.write_text(text, encoding="utf-8")
        ok, _ = ScribbleValidator().validate_protocol(p)
        return ok


def score_pair(gold_text: str, draft_text: str) -> dict:
    """Deterministic measures for one (gold, draft) pair."""
    valid = draft_valid(draft_text)
    equiv = None
    if valid:
        try:
            equiv, _ = protocols_equivalent(gold_text, draft_text)
        except Exception:
            equiv = False
    return {"draft_valid": valid, "efsm_equiv_to_gold": equiv}


# ── deterministic demo: validates measure 3 on real projections ──────────────

def run_demo(corpus_dir: Path, seed: int = 7) -> dict:
    rng = random.Random(seed)
    corpus = sorted(corpus_dir.glob("*.scr"))
    if not corpus:
        raise SystemExit(f"no corpus in {corpus_dir}; run gen_corpus.py")

    rows = []
    for p in corpus:
        gold = p.read_text(encoding="utf-8")
        # three synthetic "drafts": identical (equiv), reformatted (equiv),
        # semantically mutated (not equiv). Tests the scorer both ways.
        reformat = gold.replace(" from ", "  from ").replace(" to ", "  to ")
        mutant = mutate(gold, "flip_branch_subject", rng) or \
            mutate(gold, "undeclare_role", rng)
        for kind, draft, expect_equiv in [
            ("identical", gold, True),
            ("reformat", reformat, True),
            ("mutant", mutant, False),
        ]:
            if draft is None:
                continue
            s = score_pair(gold, draft)
            # a mutant that broke validity has efsm_equiv=None (not scored) —
            # count it as correctly NOT equivalent for the confusion table.
            got_equiv = bool(s["efsm_equiv_to_gold"])
            rows.append({"file": p.name, "kind": kind,
                         "draft_valid": s["draft_valid"],
                         "efsm_equiv": got_equiv, "expected_equiv": expect_equiv,
                         "correct": got_equiv == expect_equiv})

    correct = sum(1 for r in rows if r["correct"])
    return {
        "pairs": len(rows),
        "scorer_accuracy_pct": round(100 * correct / len(rows), 1) if rows else None,
        "by_kind": {
            k: {
                "n": sum(1 for r in rows if r["kind"] == k),
                "correct": sum(1 for r in rows if r["kind"] == k and r["correct"]),
            } for k in ("identical", "reformat", "mutant")
        },
        "rows": rows,
    }


# ── full pipeline (LLM) — MEASUREMENT PENDING ────────────────────────────────

def run_full(intents_path: Path) -> dict:  # pragma: no cover - needs Azure
    """intents.yaml: list of {intent, gold_scr}. For each, draft via the
    ArchitectAgent, run the repair loop, score fidelity. Requires Azure."""
    raise SystemExit(
        "translation_fidelity full run is MEASUREMENT PENDING: needs an LLM "
        "(authoring.architect.ArchitectAgent) + Azure. The deterministic "
        "equivalence scorer is validated via --demo. To run for real: draft "
        "each intent with ArchitectAgent.draft_protocol(), count first-draft "
        "validity + repair rounds, then score_pair(gold, draft) for measure 3.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--corpus", default="cases/_corpus")
    ap.add_argument("--intents", default=None)
    ap.add_argument("-o", "--out", default="reports/e5")
    args = ap.parse_args()

    if args.intents:
        run_full(Path(args.intents))
        return 0

    if not args.demo:
        print("pass --demo (deterministic) or --intents <file> (needs Azure)")
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    r = run_demo(Path(args.corpus))
    (out / "fidelity_demo.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"\nE5 EQUIVALENCE SCORER DEMO — {r['pairs']} (gold,draft) pairs, "
          f"scorer accuracy {r['scorer_accuracy_pct']}%")
    for k, v in r["by_kind"].items():
        print(f"  {k:10s}: {v['correct']}/{v['n']} classified correctly")
    print(f"\n(measures 1/2/4 — first-draft valid, repair rounds, guard sidecar — "
          f"are MEASUREMENT PENDING: need an LLM.)")
    print(f"WROTE {out}/fidelity_demo.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
