"""d1_expand.py — small end-to-end smoke (real Scribble, tiny budget)."""
from pathlib import Path

from common import DatasetRecord
import d1_expand as d1


def test_build_tiny_budget_produces_valid_unique_records(tmp_path):
    records, stats = d1.build(target=5, max_candidates=40, seed=42, workers=2,
                              curve_every=100,
                              cache_path=tmp_path / "sig_cache.json")
    assert stats["uniques_found"] == len(records)
    assert stats["uniques_found"] >= 1          # some budget may be spent on n/a ops
    families = [r.family for r in records]
    assert len(families) == len(set(families)), "dedupe must be by signature"
    for r in records:
        assert isinstance(r, DatasetRecord)
        assert r.source == "synthetic"
        assert r.split == "unassigned"
        assert r.family.startswith("efsmv1:")
        assert "global protocol" in r.protocol


def test_build_is_deterministic_given_seed(tmp_path):
    r1, s1 = d1.build(target=4, max_candidates=30, seed=7, workers=2,
                      curve_every=100, cache_path=tmp_path / "c1.json")
    r2, s2 = d1.build(target=4, max_candidates=30, seed=7, workers=2,
                      curve_every=100, cache_path=tmp_path / "c2.json")
    assert [r.protocol for r in r1] == [r.protocol for r in r2]
    assert [r.family for r in r1] == [r.family for r in r2]


def test_retry_shape_has_recursion_and_validates():
    import random
    from common import validate_text, has_recursion
    text = d1.retry_shape("retrytest", 4, 2, random.Random(1))
    assert has_recursion(text)
    vr = validate_text(text)
    assert vr.ok, vr.error


def test_compose_operator_produces_valid_signable_protocol(tmp_path):
    """Regression: composed texts carry `aux global protocol` blocks first;
    protocol_name/roles_of must resolve the MAIN header (not the aux child)
    or every signature call fails with 'Invalid aux protocol specified as
    root'. Also guards the module==filename requirement for the parent."""
    from common import all_seeds, roles_of, protocol_name, validate_text
    from signature import protocol_signature
    seeds = all_seeds()
    out = d1.gen_compose(5, 1, seeds, tmp_path)
    assert out is not None
    text, meta, _ = out
    assert meta["operator"] == "compose"
    assert "aux global protocol" in text
    assert meta["new_role"] in roles_of(text)
    assert protocol_name(text) and not protocol_name(text).startswith("SubTask")
    vr = validate_text(text)
    assert vr.ok, vr.error
    assert protocol_signature(text, assume_valid=True).startswith("efsmv1:")


def test_sweep_grid_fully_reachable():
    """Regression: dense sweep ordinal — every shape (incl. `retry`, the
    only recursion-bearing one) must be reachable through _PATTERN."""
    shapes = set()
    for idx in range(0, 9 * len(d1._SWEEP_GRID)):
        if d1._PATTERN[idx % len(d1._PATTERN)] == "sweep":
            shapes.add(d1._SWEEP_GRID[d1._sweep_ordinal(idx) % len(d1._SWEEP_GRID)][2])
    assert shapes == set(d1._SHAPES)


def test_make_refn_parses(tmp_path):
    import random
    text = ("module m;\n\ndata <java> \"java.lang.Double\" from \"rt.jar\" as Double;\n\n"
            "global protocol P(role A, role B) {\n"
            "    X(Double) from A to B;\n}\n")
    refn = d1.make_refn(text, 1.0, random.Random(1))
    assert refn is not None
    assert "require:" in refn
