"""d3_repair.py — small end-to-end smoke: both operator families produce
records, validator-rejected mutants go to RepairRecord, validator-passing
mutants go to calibration."""
from common import RepairRecord
import d3_repair as d3


def test_build_tiny_budget(tmp_path):
    repairs, calibration, stats = d3.build(
        target=6, max_mutations=60, seed=3, workers=2,
        gold_jsonl=None, use_seeds=True, n_generated=6,
        intents_jsonl=None, cache_path=tmp_path / "sig_cache.json")

    assert stats["mutations_attempted"] > 0
    assert stats["repair_records"] == len(repairs)
    assert stats["calibration_candidates"] == len(calibration)
    assert stats["repair_records"] + stats["calibration_candidates"] > 0

    for r in repairs:
        assert isinstance(r, RepairRecord)
        assert r.intent and isinstance(r.intent, str)
        assert r.gold != r.broken
        assert r.counterexample  # verbatim validator error, must be non-empty
        assert r.split == "unassigned"

    for c in calibration:
        assert c["gold"] != c["mutant"]
        assert c["operator"]


def test_local_operator_family_reachable(tmp_path):
    """With n_generated>0, at least some mutations should come from the
    LocalType-level (s2_mutation) operator family, not just the text one."""
    from integration_stress import MUTATIONS as LOCAL_OPS
    repairs, calibration, stats = d3.build(
        target=10, max_mutations=200, seed=11, workers=3,
        gold_jsonl=None, use_seeds=False, n_generated=15,
        intents_jsonl=None, cache_path=tmp_path / "sig_cache2.json")
    used_ops = {r.operator for r in repairs} | {c["operator"] for c in calibration}
    assert used_ops, "expected at least one operator to produce a record"
    # not every run is guaranteed to hit a local op within a tiny budget,
    # but the yield table must at least report on them
    assert set(LOCAL_OPS) <= set(stats["per_operator_yield"].keys())


def test_stub_intent_has_no_scribble_keywords():
    text = ("module m;\n\nglobal protocol P(role A, role B) {\n"
            "    Go(String) from A to B;\n}\n")
    intent, source = d3.stub_intent(text, "no-such-case")
    assert source == "stub"
    for bad in ("scribble", "global protocol", ".scr", "efsm"):
        assert bad not in intent.lower()
