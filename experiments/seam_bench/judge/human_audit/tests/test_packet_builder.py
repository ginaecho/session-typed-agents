from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.seam_bench.judge.human_audit import packet_builder as pb
from experiments.seam_bench.judge.payloads import sanitize_protocol
from experiments.seam_bench.t0.gold_pairs import extract_gold_pairs

FORBIDDEN_STRATUM_KEYS = {
    "stratum", "expected_label", "is_repeat", "repeat_of", "source_ref",
    "operator", "seed_case", "candidate_id", "case_id", "intent_method",
}


def _build(tmp_path: Path, **kwargs):
    kwargs.setdefault("seed", 13)
    kwargs.setdefault("target", pb.DEFAULT_TARGET)
    kwargs.setdefault("easy_negatives", None)
    kwargs.setdefault("hard_negatives", None)
    kwargs.setdefault("repeats", pb.DEFAULT_REPEATS)
    kwargs.setdefault("candidates_path", pb.DEFAULT_CANDIDATES)
    return pb.build_packet(**kwargs)


def test_determinism_full_packet(tmp_path):
    items1, stats1 = _build(tmp_path)
    items2, stats2 = _build(tmp_path)
    assert items1 == items2
    assert stats1 == stats2


def test_default_composition_counts(tmp_path):
    items, stats = _build(tmp_path)
    assert stats["total_items"] == pb.DEFAULT_TARGET == 220
    assert stats["n_gold"] == 23
    assert stats["n_easy_negative"] == 23
    assert stats["n_hard_negative"] == 154
    assert stats["n_repeats"] == 20
    # 0 skips on the current calibration_candidates.jsonl schema (every row
    # already carries a usable intent) — see packet_builder.py module
    # docstring for the fallback logic this still exercises.
    assert stats["hard_negative_stats"]["candidates_skipped"] == 0
    assert stats["hard_negative_stats"]["hard_negatives_shortfall"] == 0


def test_packet_fields_are_blind(tmp_path):
    items, _ = _build(tmp_path)
    packet, key = pb.split_packet_and_key(items)
    for rec in packet:
        assert set(rec.keys()) == set(pb.PACKET_FIELDS)
        for forbidden in FORBIDDEN_STRATUM_KEYS:
            assert forbidden not in rec
    # key file DOES carry the stratum info (that's the point — it's the
    # separate file audit_app.py never reads)
    for rec in key:
        assert rec["stratum"] in ("gold", "easy_negative", "hard_negative")
        assert rec["expected_label"] in ("fit", "no_fit")


def test_item_ids_carry_no_stratum_signal(tmp_path):
    items, _ = _build(tmp_path)
    packet, _ = pb.split_packet_and_key(items)
    for rec in packet:
        assert rec["item_id"].startswith("item-")
        for bad in ("gold", "mutant", "swap", "negative", "repeat", "hard", "easy"):
            assert bad not in rec["item_id"].lower()


def test_all_protocol_text_is_sanitizer_output(tmp_path):
    """Every card's protocol_text must equal what payloads.sanitize_protocol
    would produce — i.e. the human sees exactly what a judge sees."""
    items, _ = _build(tmp_path, target=40, repeats=4)
    packet, key = pb.split_packet_and_key(items)
    key_by_id = {k["item_id"]: k for k in key}
    golds_by_id = {g.id: g for g in extract_gold_pairs()}
    for rec in packet:
        k = key_by_id[rec["item_id"]]
        if k["stratum"] == "gold" and not k["is_repeat"]:
            gold = golds_by_id[k["source_ref"]["case_id"]]
            expected = sanitize_protocol(gold.protocol).text
            assert rec["protocol_text"] == expected


def test_easy_negatives_have_no_fixed_points(tmp_path):
    items, _ = _build(tmp_path)
    _, key = pb.split_packet_and_key(items)
    for rec in key:
        if rec["stratum"] == "easy_negative" and not rec["is_repeat"]:
            ref = rec["source_ref"]
            assert ref["intent_case"] != ref["protocol_case"]


def test_repeats_are_exact_content_duplicates_with_min_gap(tmp_path):
    items, _ = _build(tmp_path)
    packet, key = pb.split_packet_and_key(items)
    packet_by_id = {p["item_id"]: p for p in packet}
    order_by_id = {k["item_id"]: k["order_index"] for k in key}

    n_repeats = 0
    for k in key:
        if not k["is_repeat"]:
            continue
        n_repeats += 1
        orig = packet_by_id[k["repeat_of"]]
        rep = packet_by_id[k["item_id"]]
        assert orig["intent"] == rep["intent"]
        assert orig["protocol_text"] == rep["protocol_text"]
        gap = abs(order_by_id[k["item_id"]] - order_by_id[k["repeat_of"]])
        assert gap >= pb.MIN_REPEAT_GAP
    assert n_repeats == 20


def test_resolve_candidate_intent_gold_seed_override():
    golds = extract_gold_pairs()
    lut = pb._gold_lookup(golds)
    auction = next(g for g in golds if g.id == "auction")
    row = {"seed_case": "auction", "intent": "a totally different stub sentence"}
    intent, method = pb.resolve_candidate_intent(row, lut)
    assert method == "gold_seed"
    assert intent == auction.intent
    assert intent != row["intent"]


def test_resolve_candidate_intent_falls_back_to_candidate_field():
    golds = extract_gold_pairs()
    lut = pb._gold_lookup(golds)
    row = {"seed_case": "corpus_099", "intent": "Coordinate A and B."}
    intent, method = pb.resolve_candidate_intent(row, lut)
    assert method == "candidate_field"
    assert intent == "Coordinate A and B."


def test_resolve_candidate_intent_skips_when_impossible():
    golds = extract_gold_pairs()
    lut = pb._gold_lookup(golds)
    row = {"seed_case": "corpus_099", "intent": ""}
    intent, method = pb.resolve_candidate_intent(row, lut)
    assert intent is None
    assert method is None


def test_hard_negative_skip_counting(tmp_path):
    golds = extract_gold_pairs()
    candidates_path = tmp_path / "candidates.jsonl"
    good_row = {
        "id": "cal-good", "seed_case": "corpus_1", "operator": "swap_order",
        "intent": "Coordinate A and B through a message exchange.",
        "mutant": "module m;\nglobal protocol P(role A, role B) { "
                  "M1(String) from A to B; }\n",
    }
    bad_row = {
        "id": "cal-bad", "seed_case": "corpus_2", "operator": "swap_order",
        "intent": "",
        "mutant": "module m;\nglobal protocol Q(role A, role B) { "
                  "M2(String) from A to B; }\n",
    }
    with candidates_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(good_row) + "\n")
        f.write(json.dumps(bad_row) + "\n")

    items, stats = pb.build_hard_negative_items(candidates_path, golds, count=5, seed=1)
    assert stats["candidates_total"] == 2
    assert stats["candidates_resolved"] == 1
    assert stats["candidates_skipped"] == 1
    assert stats["skipped_ids"] == ["cal-bad"]
    assert len(items) == 1
    assert items[0]["source_ref"]["candidate_id"] == "cal-good"


def test_hard_negatives_requested_exceeds_pool_reports_shortfall(tmp_path):
    golds = extract_gold_pairs()
    candidates_path = tmp_path / "candidates.jsonl"
    rows = [{
        "id": f"cal-{i}", "seed_case": f"corpus_{i}", "operator": "swap_order",
        "intent": "Coordinate A and B through a message exchange.",
        "mutant": (f"module m{i};\nglobal protocol P{i}(role A, role B) "
                   "{ M1(String) from A to B; }\n"),
    } for i in range(3)]
    with candidates_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    items, stats = pb.build_hard_negative_items(candidates_path, golds, count=10, seed=1)
    assert stats["hard_negatives_requested"] == 10
    assert stats["hard_negatives_sampled"] == 3
    assert stats["hard_negatives_shortfall"] == 7
