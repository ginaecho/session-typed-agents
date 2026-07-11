"""splitter.py / leakage_check.py — pure-logic tests over synthetic
fixtures (no Scribble calls: role_count/has_recursion/depth_bucket are
plain regex over text, so this stays fast)."""
import json

import splitter as sp
import leakage_check as lc


def _proto(n_roles: int, choices: int = 0, rec: bool = False) -> str:
    roles = ", ".join(f"role R{i}" for i in range(n_roles))
    body = []
    if rec:
        body.append("rec Loop {")
    for i in range(choices):
        body.append(f"choice at R0 {{ M{i}(String) from R0 to R1; }} or {{ M{i}b(String) from R0 to R1; }}")
    body.append("Done(String) from R0 to R1;")
    if rec:
        body.append("continue Loop; }")
    return f"module m;\n\nglobal protocol P({roles}) {{\n" + "\n".join(body) + "\n}\n"


def _make_dataset_rows(n_families: int, records_per_family: int) -> list[dict]:
    rows = []
    for f in range(n_families):
        text = _proto(2 + (f % 4), choices=f % 3, rec=(f % 5 == 0))
        family = f"efsmv1:fake{f:04d}"
        for k in range(records_per_family):
            rows.append({
                "id": f"d-{f}-{k}", "family": family, "split": "unassigned",
                "intent": f"intent {f}.{k}", "protocol": text, "refn": None,
                "source": "synthetic", "seed_case": f"synthetic:{f}",
                "gen": {}, "provenance": None,
            })
    return rows


def test_assign_splits_keeps_family_together(tmp_path):
    rows = _make_dataset_rows(n_families=30, records_per_family=4)
    f1 = tmp_path / "d1.jsonl"
    f1.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    rows_by_file = {"d1.jsonl": rows}
    strata = sp.compute_strata(rows_by_file)
    assignment = sp.assign_splits(strata, seed=1)

    # every record of a family must resolve to the same split
    fam_to_split_seen = {}
    for r in rows:
        s = assignment[r["family"]]
        fam_to_split_seen.setdefault(r["family"], s)
        assert fam_to_split_seen[r["family"]] == s

    splits_present = set(assignment.values())
    assert splits_present <= {"train", "dev", "test-syn"}
    assert "train" in splits_present  # 30 families, train should be nonempty


def test_assign_splits_roughly_80_10_10():
    strata = {f"fam{i}": (3, False, "flat") for i in range(200)}
    assignment = sp.assign_splits(strata, seed=5)
    from collections import Counter
    c = Counter(assignment.values())
    assert 150 <= c["train"] <= 180
    assert 10 <= c["dev"] <= 30
    assert 10 <= c["test-syn"] <= 30


def test_leakage_check_green_on_correct_split(tmp_path):
    rows = _make_dataset_rows(n_families=20, records_per_family=3)
    rows_by_file = {"d1.jsonl": rows}
    strata = sp.compute_strata(rows_by_file)
    assignment = sp.assign_splits(strata, seed=2)
    for r in rows:
        r["split"] = assignment[r["family"]]

    ok1, off1 = lc.check_no_family_in_two_splits(rows_by_file)
    assert ok1, off1


def test_leakage_check_catches_split_family(tmp_path):
    rows = _make_dataset_rows(n_families=5, records_per_family=4)
    # deliberately corrupt: same family split across two splits
    rows[0]["split"] = "train"
    rows[1]["split"] = "dev"
    for r in rows[2:]:
        r["split"] = "train"
    rows_by_file = {"d1.jsonl": rows}

    ok1, off1 = lc.check_no_family_in_two_splits(rows_by_file)
    assert not ok1
    assert any(o["family"] == rows[0]["family"] for o in off1)
