"""packet_builder.py — build the §6 human-audit packet (SEAM_TRAINING_
EXECUTION_PLAN.md §5.2, §6).

Assembles ~220 (intent, protocol) items for Gina to fit/no-fit label, drawn
from three strata plus an intra-rater repeat set:

  gold            the 23 hand-authored (intent, protocol) pairs
                   (experiments/seam_bench/t0/gold_pairs.py — imported, not
                   re-implemented). expected_label = "fit".
  easy_negative   swapped pairs: intent_A paired with a DIFFERENT gold's
                   protocol (deterministic cyclic derangement over the 23
                   golds, no fixed points). expected_label = "no_fit".
  hard_negative   W3's validator-passing near-miss mutants, sampled from
                   experiments/seam_bench/data/samples/calibration_candidates.jsonl.
                   Each candidate mutated a gold/seed protocol in a way the
                   Scribble validator still accepted (a semantic near-miss,
                   not a syntax error) — see d3_repair.py's module
                   docstring. expected_label = "no_fit".
  repeat          ~20 exact content duplicates (new item_id, same intent +
                   protocol_text) of already-selected items, spread through
                   the running order, for the §6 intra-rater consistency
                   check.

Every protocol (gold, swapped, or mutant) is rendered through the judge
payload sanitizer (judge/payloads.py::sanitize_protocol) before it reaches
the packet — the human sees exactly the comment-free canonical form an LLM
judge sees.

BLINDING: `audit_packet.jsonl` (what audit_app.py reads) carries only
{item_id, order_index, intent, protocol_text} — no field anywhere in that
file names a stratum, a case, an operator, or a source id. All of that
provenance lives in the separate `packet_key.jsonl`, which the app never
opens. item_id values are assigned from final shuffled position
("item-0001", ...), not from any semantic source id, so they carry no
stratum signal either.

CALIBRATION_CANDIDATES SCHEMA (read, not assumed): each row already carries
a non-empty `intent` field and an `intent_source` tag of either "stub"
(deterministic templated prose — used for the 177 candidates whose
`seed_case` is a bare seed-corpus protocol with no case.yaml, e.g.
"corpus_014") or "case_description" (the 23 candidates whose seed_case IS a
named case — but the embedded text is case.yaml's `description` field, a
short dev-notes paraphrase, NOT the same text as case.yaml's `intent`
field that gold_pairs.py extracts). Per the task instructions ("pair with
the ORIGINAL seed's intent where available"), this builder resolves intent
per candidate as:

  1. If seed_case matches one of the 23 gold case ids/families, use THAT
     gold's real case.yaml `intent` (the authoritative original-seed
     intent) — overriding the candidate's own `case_description` field.
  2. Otherwise (seed_case is a bare _corpus/ seed with no case.yaml, hence
     no real intent to translate from — see gold_pairs.py's module
     docstring), fall back to the candidate's own embedded `intent`
     ("stub") field — the best available proxy for that seed's intent.
  3. If neither is available (empty/missing `intent` AND no gold match),
     the candidate is SKIPPED and the skip is counted and reported —
     never silently dropped.

On the current data (2026-07-11 checkout) every one of the 200 candidates
has a usable intent under rule 1 or 2, so skips = 0; rule 3 exists for
robustness against future data where that is not true.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]  # judge/human_audit/packet_builder.py -> repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.seam_bench.t0.gold_pairs import GoldPair, extract_gold_pairs  # noqa: E402
from experiments.seam_bench.judge.payloads import (  # noqa: E402
    PayloadSanitizationError,
    sanitize_protocol,
)

DEFAULT_CANDIDATES = (
    REPO_ROOT / "experiments" / "seam_bench" / "data" / "samples"
    / "calibration_candidates.jsonl"
)
DEFAULT_OUT_DIR = HERE
DEFAULT_TARGET = 220
DEFAULT_REPEATS = 20
DEFAULT_SWAP_OFFSET = 1
MIN_REPEAT_GAP = 5  # minimum index distance a repeat is kept from its original


def read_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _gold_lookup(golds: list[GoldPair]) -> dict[str, GoldPair]:
    """id and family both resolve to their GoldPair — calibration
    candidates' `seed_case` values are observed to use either form
    (top-level cases: id == family; skills_safety subcases: id is the
    subcase name, family is "skills_safety/<subcase>")."""
    lut: dict[str, GoldPair] = {}
    for g in golds:
        lut[g.id] = g
        lut[g.family] = g
    return lut


def _sanitize_or_raise(text: str, where: str) -> str:
    try:
        return sanitize_protocol(text).text
    except PayloadSanitizationError as exc:
        raise PayloadSanitizationError(f"{where}: {exc}") from exc


def build_gold_items(golds: list[GoldPair]) -> list[dict]:
    items = []
    for g in golds:
        items.append({
            "intent": g.intent,
            "protocol_text": _sanitize_or_raise(g.protocol, f"gold {g.id}"),
            "stratum": "gold",
            "expected_label": "fit",
            "source_ref": {"kind": "gold", "case_id": g.id, "family": g.family},
        })
    return items


def build_easy_negative_items(
    golds: list[GoldPair], count: int, offset: int = DEFAULT_SWAP_OFFSET,
) -> list[dict]:
    """Cyclic derangement: golds[i].intent paired with golds[(i+offset) %
    n].protocol. offset != 0 (mod n) guarantees zero fixed points (every
    swapped pair really is a mismatch), which a plain random pairing would
    not guarantee deterministically. Deterministic in `golds`' input order
    (find_case_dirs sorts case dirs, so this is stable run to run)."""
    n = len(golds)
    if n == 0:
        return []
    offset = offset % n
    if offset == 0:
        offset = 1
    count = max(0, min(count, n))
    items = []
    for i in range(count):
        j = (i + offset) % n
        intent_case = golds[i]
        protocol_case = golds[j]
        items.append({
            "intent": intent_case.intent,
            "protocol_text": _sanitize_or_raise(
                protocol_case.protocol,
                f"easy_negative {intent_case.id}x{protocol_case.id}"),
            "stratum": "easy_negative",
            "expected_label": "no_fit",
            "source_ref": {
                "kind": "easy_negative",
                "intent_case": intent_case.id,
                "protocol_case": protocol_case.id,
            },
        })
    return items


def resolve_candidate_intent(
    row: dict, gold_lut: dict[str, GoldPair],
) -> tuple[Optional[str], Optional[str]]:
    """Returns (intent_text, method) or (None, None) if unresolvable.
    method in {"gold_seed", "candidate_field"}."""
    seed_case = row.get("seed_case")
    if seed_case in gold_lut:
        return gold_lut[seed_case].intent, "gold_seed"
    intent = row.get("intent")
    if intent and intent.strip():
        return intent.strip(), "candidate_field"
    return None, None


def build_hard_negative_items(
    candidates_path: Path, golds: list[GoldPair], count: int, seed: int,
) -> tuple[list[dict], dict[str, Any]]:
    gold_lut = _gold_lookup(golds)
    rows = read_jsonl(candidates_path)

    resolved: list[tuple[dict, str, str]] = []  # (row, intent, method)
    skipped: list[str] = []
    for row in rows:
        intent, method = resolve_candidate_intent(row, gold_lut)
        if intent is None:
            skipped.append(row.get("id", "<unknown>"))
            continue
        resolved.append((row, intent, method))

    rng = random.Random(seed)
    pool = list(resolved)  # stable order: file read order
    take = min(count, len(pool))
    shortfall = count - take
    sampled = rng.sample(pool, take) if take else []

    items = []
    for row, intent, method in sampled:
        items.append({
            "intent": intent,
            "protocol_text": _sanitize_or_raise(
                row["mutant"], f"hard_negative {row.get('id')}"),
            "stratum": "hard_negative",
            "expected_label": "no_fit",
            "source_ref": {
                "kind": "hard_negative",
                "candidate_id": row.get("id"),
                "seed_case": row.get("seed_case"),
                "operator": row.get("operator"),
                "intent_method": method,
            },
        })

    stats = {
        "candidates_total": len(rows),
        "candidates_resolved": len(resolved),
        "candidates_skipped": len(skipped),
        "skipped_ids": skipped,
        "hard_negatives_requested": count,
        "hard_negatives_sampled": len(items),
        "hard_negatives_shortfall": shortfall,
    }
    return items, stats


def add_repeats(
    items: list[dict], n_repeats: int, seed: int,
) -> list[dict]:
    """Pick n_repeats items (with their FINAL, already-assigned item_id) and
    append exact-content duplicates with fresh item_ids. Caller must run
    this AFTER item_id assignment (so repeat_of is stable) and BEFORE final
    ordering (so spread_out() can place the duplicates away from their
    originals)."""
    if n_repeats <= 0 or not items:
        return []
    rng = random.Random(seed)
    base = rng.sample(items, min(n_repeats, len(items)))
    repeats = []
    for src in base:
        rep = dict(src)
        rep["item_id"] = None  # assigned later, in spread_out
        rep["stratum"] = src["stratum"]
        rep["expected_label"] = src["expected_label"]
        rep["is_repeat"] = True
        rep["repeat_of"] = src["item_id"]
        rep["source_ref"] = {"kind": "repeat", "of": src["item_id"],
                              "original_source_ref": src["source_ref"]}
        repeats.append(rep)
    return repeats


def spread_out(
    originals: list[dict], repeats: list[dict], seed: int,
) -> list[dict]:
    """Shuffle originals, then insert each repeat at an evenly-spaced slot,
    nudged away from its own original if they'd land within
    MIN_REPEAT_GAP of each other. Returns the final ordered list (item_id /
    order_index NOT yet assigned — do that after this call, over the
    returned order)."""
    rng = random.Random(seed)
    result = list(originals)
    rng.shuffle(result)

    n_rep = len(repeats)
    for i, rep in enumerate(repeats):
        L = len(result)
        frac = (i + 1) / (n_rep + 1)
        pos = int(frac * L)
        orig_id = rep["repeat_of"]
        orig_pos = next(
            (j for j, x in enumerate(result) if x.get("item_id") == orig_id),
            None)
        tries = 0
        while (orig_pos is not None
               and abs(pos - orig_pos) < MIN_REPEAT_GAP
               and tries < L + 1):
            pos = (pos + 7) % (len(result) + 1)
            tries += 1
        result.insert(pos, rep)
    return result


def assign_ids(items: list[dict]) -> None:
    """In-place: item_id / order_index from FINAL position only — no
    semantic content, so the id itself carries no stratum signal."""
    for idx, item in enumerate(items):
        item["item_id"] = f"item-{idx + 1:04d}"
        item["order_index"] = idx


def build_packet(
    *, seed: int, target: int, easy_negatives: Optional[int],
    hard_negatives: Optional[int], repeats: int,
    candidates_path: Path,
) -> tuple[list[dict], dict[str, Any]]:
    golds = extract_gold_pairs()
    gold_items = build_gold_items(golds)

    n_easy = len(golds) if easy_negatives is None else easy_negatives
    easy_items = build_easy_negative_items(golds, n_easy)

    if hard_negatives is None:
        n_hard = max(0, target - len(gold_items) - len(easy_items) - repeats)
    else:
        n_hard = hard_negatives
    hard_items, hard_stats = build_hard_negative_items(
        candidates_path, golds, n_hard, seed)

    originals = gold_items + easy_items + hard_items
    # First pass: assign provisional ids so repeats can reference stable
    # `repeat_of` ids; final ids are reassigned after ordering. Each
    # provisional id maps 1:1 to the same dict object that ends up in
    # `final_order` (dicts are shared by reference, never copied here), so
    # capturing provisional_id -> object now lets us resolve the FINAL id
    # after assign_ids() mutates item_id in place below.
    provisional_to_obj: dict[str, dict] = {}
    for i, item in enumerate(originals):
        pid = f"__orig_{i}"
        item["item_id"] = pid
        item["order_index"] = None
        item["is_repeat"] = False
        item["repeat_of"] = None
        provisional_to_obj[pid] = item

    repeat_items = add_repeats(originals, repeats, seed=seed + 1)
    # add_repeats copied repeat_of from src["item_id"], which is the
    # provisional id at that point — stash it before assign_ids overwrites
    # every item_id (including the repeats') with final positional ids.
    for rep in repeat_items:
        rep["_repeat_of_provisional"] = rep["repeat_of"]

    final_order = spread_out(originals, repeat_items, seed=seed + 2)
    assign_ids(final_order)
    for item in final_order:
        if item["is_repeat"]:
            provisional = item.pop("_repeat_of_provisional")
            item["repeat_of"] = provisional_to_obj[provisional]["item_id"]

    stats = {
        "seed": seed,
        "target": target,
        "total_items": len(final_order),
        "n_gold": len(gold_items),
        "n_easy_negative": len(easy_items),
        "n_hard_negative": len(hard_items),
        "n_repeats": len(repeat_items),
        "hard_negative_stats": hard_stats,
    }
    return final_order, stats


PACKET_FIELDS = ("item_id", "order_index", "intent", "protocol_text")
KEY_FIELDS = (
    "item_id", "order_index", "stratum", "expected_label", "is_repeat",
    "repeat_of", "source_ref",
)


def split_packet_and_key(items: list[dict]) -> tuple[list[dict], list[dict]]:
    packet = [{k: item[k] for k in PACKET_FIELDS} for item in items]
    key = [{k: item[k] for k in KEY_FIELDS} for item in items]
    return packet, key


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET,
                     help="total item count including repeats (default 220)")
    ap.add_argument("--easy-negatives", type=int, default=None,
                     help="default: one swap per gold (23)")
    ap.add_argument("--hard-negatives", type=int, default=None,
                     help="default: fills target - gold - easy - repeats")
    ap.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    ap.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = ap.parse_args(argv)

    items, stats = build_packet(
        seed=args.seed, target=args.target,
        easy_negatives=args.easy_negatives,
        hard_negatives=args.hard_negatives,
        repeats=args.repeats,
        candidates_path=Path(args.candidates),
    )
    packet, key = split_packet_and_key(items)

    out_dir = Path(args.out_dir)
    packet_path = out_dir / "audit_packet.jsonl"
    key_path = out_dir / "packet_key.jsonl"
    stats_path = out_dir / "packet_build_stats.json"

    write_jsonl(packet_path, packet)
    write_jsonl(key_path, key)
    stats_path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {len(packet)} items -> {packet_path}")
    print(f"wrote key -> {key_path}")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
