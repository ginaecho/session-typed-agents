from __future__ import annotations

from pathlib import Path

from experiments.intent_loop.corpus import append_record, read_corpus
from experiments.intent_loop.optimize import (build_prompt_pack,
                                              harvest_rulebook,
                                              mine_exemplars, PromptPack)
from experiments.intent_loop.schema import LoopRecord


def _record(eid: str, valid: bool, faithful: bool | None,
            validator_msgs: list[str] = ()) -> LoopRecord:
    attempts = ([{"k": i + 1, "valid": False, "validator_msg": m,
                  "chars": 100} for i, m in enumerate(validator_msgs)]
                + ([{"k": len(validator_msgs) + 1, "valid": True,
                     "validator_msg": "", "chars": 100}] if valid else []))
    return LoopRecord(
        episode_id=eid, intent_sha256="x" * 64, intent_chars=500,
        distilled={"mission": f"mission for {eid}",
                   "requirements": [{"rid": "R1", "kind": "ordering",
                                     "text": "A before B", "who": [],
                                     "source": "document"}]},
        transcript=[], draft_attempts=attempts,
        final_protocol=(f"global protocol {eid}(role A, role B) {{ }}"
                        if valid else None),
        valid=valid,
        faithfulness=({"faithful": faithful} if faithful is not None
                      else None),
        meter={}, ts="2026-08-05T00:00:00+00:00")


def test_corpus_roundtrip(tmp_path: Path):
    path = tmp_path / "corpus.jsonl"
    append_record(_record("e1", True, True), path)
    append_record(_record("e2", False, None), path)
    records = list(read_corpus(path))
    assert [r.episode_id for r in records] == ["e1", "e2"]
    assert records[1].final_protocol is None


def test_exemplar_mining_filters_unfaithful():
    records = [_record("good", True, True),
               _record("valid_but_unfaithful", True, False),
               _record("invalid", False, None)]
    faithful_only = mine_exemplars(records)
    assert [c.item_id for c in faithful_only] == ["good"]
    permissive = mine_exemplars(records, require_faithful=False)
    assert {c.item_id for c in permissive} == {"good",
                                              "valid_but_unfaithful"}


def test_rulebook_maps_known_families_and_dedupes():
    msgs = ["line 3: mismatched input '}' expecting ';'",
            "line 9: mismatched input '}' expecting ';'",
            "Role TaxVerifier is not declared in header"]
    records = [_record("e1", False, None, validator_msgs=msgs[:2]),
               _record("e2", False, None, validator_msgs=msgs[2:])]
    lessons = harvest_rulebook(records)
    assert len(lessons) == 2  # two families, syntax family deduped
    assert any("grammar in the primer" in l for l in lessons)
    assert any("Declare every role" in l for l in lessons)


def test_prompt_pack_build_save_load_select(tmp_path: Path):
    path = tmp_path / "corpus.jsonl"
    append_record(_record("quarterly", True, True), path)
    append_record(_record("shipping", True, True), path)
    pack = build_prompt_pack(path, version="test")
    assert pack.built_from["episodes"] == 2
    saved = pack.save(tmp_path / "pack.json")
    loaded = PromptPack.load(saved)
    assert loaded.version == "test"
    assert len(loaded.exemplars) == 2
    picks = loaded.select_exemplars("mission for quarterly", k=1)
    assert len(picks) == 1
    assert "quarterly" in picks[0][1]
