from __future__ import annotations

from pathlib import Path

from experiments.intent_loop.corpus import append_record
from experiments.intent_loop.export import (build_dataset, drafting_examples,
                                            repair_examples)
from experiments.intent_loop.schema import LoopRecord


def _rec(eid: str, valid: bool, faithful: bool | None, sha: str = "a" * 64,
         attempts=None) -> LoopRecord:
    return LoopRecord(
        episode_id=eid, intent_sha256=sha, intent_chars=400,
        distilled={"mission": f"m-{eid}", "roles": [],
                   "requirements": [
                       {"rid": "R1", "kind": "ordering", "text": "A then B",
                        "who": [], "source": "document"},
                       {"rid": "R2", "kind": "policy",
                        "text": "Approver and payer must differ.",
                        "who": [], "source": "answer"}],
                   "completion_signal": "done", "open_questions": []},
        transcript=[],
        draft_attempts=attempts if attempts is not None else [
            {"k": 1, "valid": True, "validator_msg": "", "chars": 30,
             "text": f"global protocol {eid}(role A, role B) {{ }}"}],
        final_protocol=(f"global protocol {eid}(role A, role B) {{ }}"
                        if valid else None),
        valid=valid,
        faithfulness=({"faithful": faithful} if faithful is not None else None),
        meter={}, ts="2026-08-05T00:00:00+00:00")


def test_only_valid_and_faithful_episodes_become_drafting_examples():
    records = [_rec("good", True, True), _rec("unfaithful", True, False),
               _rec("broken", False, None)]
    ids = [ex["messages"][2]["content"] for _sha, ex
           in drafting_examples(records)]
    assert len(ids) == 1 and "good" in ids[0]


def test_policy_requirements_are_not_in_the_training_prompt():
    """A fine-tune must not learn to encode constraints a session type
    cannot express — the spec it trains on is protocol-scoped."""
    _sha, ex = next(drafting_examples([_rec("good", True, True)]))
    user = ex["messages"][1]["content"]
    assert "A then B" in user
    assert "must differ" not in user


def test_repair_pairs_come_from_consecutive_attempts():
    rec = _rec("r", True, True, attempts=[
        {"k": 1, "valid": False, "validator_msg": "line 2: mismatched input",
         "chars": 10, "text": "global protocol r(role A) {"},
        {"k": 2, "valid": True, "validator_msg": "", "chars": 12,
         "text": "global protocol r(role A, role B) { }"}])
    pairs = list(repair_examples([rec]))
    assert len(pairs) == 1
    user = pairs[0][1]["messages"][1]["content"]
    assert "mismatched input" in user and "BROKEN PROTOCOL" in user
    assert pairs[0][1]["messages"][2]["content"].endswith("}")


def test_split_is_by_intent_so_one_intent_never_straddles(tmp_path: Path):
    corpus = tmp_path / "c.jsonl"
    for i in range(6):
        # two episodes per intent document, three documents
        append_record(_rec(f"e{i}", True, True, sha=f"{i // 2}" * 64), corpus)
    ds = build_dataset(corpus, validation_fraction=0.5)
    seen: dict[str, str] = {}
    for split in ("train", "validation"):
        for ex in ds[split]:
            mission = ex["messages"][1]["content"]
            key = mission.split("m-")[1][:2]
            assert seen.setdefault(key, split) == split
    assert ds["stats"]["split_by"].startswith("intent sha256")


def test_stats_report_what_was_dropped(tmp_path: Path):
    corpus = tmp_path / "c.jsonl"
    append_record(_rec("ok", True, True), corpus)
    append_record(_rec("unfaithful", True, False), corpus)
    append_record(_rec("broken", False, None), corpus)
    stats = build_dataset(corpus)["stats"]
    assert stats["episodes"] == 3
    assert stats["dropped_invalid"] == 1
    assert stats["dropped_valid_but_unfaithful"] == 1
    assert stats["drafting_examples"] == 1
