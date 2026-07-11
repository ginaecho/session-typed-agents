from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.scripts.stats import wilson
from experiments.seam_bench.judge.human_audit import analysis


def test_wilson_spot_value_85_of_100():
    lo, hi = wilson(85, 100)
    assert lo == pytest.approx(0.7672, abs=1e-3)


def test_wilson_spot_value_170_of_200():
    lo, hi = wilson(170, 200)
    assert lo == pytest.approx(0.7939, abs=1e-3)
    # below the §6 0.80 gate threshold despite an 85% point estimate
    assert lo < analysis.GATE_THRESHOLD


def _key_row(item_id, stratum, expected_label, is_repeat=False, repeat_of=None):
    return {
        "item_id": item_id, "order_index": 0, "stratum": stratum,
        "expected_label": expected_label, "is_repeat": is_repeat,
        "repeat_of": repeat_of, "source_ref": {"kind": stratum},
    }


def _label_row(item_id, label):
    return {"item_id": item_id, "label": label, "note": "", "seconds_spent": 5.0,
            "ts": "2026-07-11T00:00:00Z"}


def test_join_left_join_and_orphan_detection():
    key = [_key_row("a", "gold", "fit"), _key_row("b", "gold", "fit")]
    labels = [_label_row("a", "fit"), _label_row("zzz", "no_fit")]
    joined, orphans = analysis.join(labels, key)
    assert orphans == ["zzz"]
    by_id = {r["item_id"]: r for r in joined}
    assert by_id["a"]["label"] == "fit"
    assert by_id["b"]["label"] is None


def test_per_stratum_agreement_counts():
    key = [
        _key_row("g1", "gold", "fit"), _key_row("g2", "gold", "fit"),
        _key_row("e1", "easy_negative", "no_fit"),
    ]
    labels = [
        _label_row("g1", "fit"),      # agree
        _label_row("g2", "no_fit"),   # disagree
        _label_row("e1", "unsure"),   # unsure
    ]
    joined, _ = analysis.join(labels, key)
    strata = analysis.per_stratum_agreement(joined)
    assert strata["gold"]["n"] == 2
    assert strata["gold"]["agree"] == 1
    assert strata["gold"]["agree_rate"] == pytest.approx(0.5)
    assert strata["easy_negative"]["unsure"] == 1
    assert strata["easy_negative"]["agree_rate"] == pytest.approx(0.0)


def test_intra_rater_consistency():
    key = [
        _key_row("orig1", "hard_negative", "no_fit"),
        _key_row("rep1", "hard_negative", "no_fit", is_repeat=True, repeat_of="orig1"),
        _key_row("orig2", "gold", "fit"),
        _key_row("rep2", "gold", "fit", is_repeat=True, repeat_of="orig2"),
    ]
    labels = [
        _label_row("orig1", "no_fit"), _label_row("rep1", "no_fit"),  # consistent
        _label_row("orig2", "fit"), _label_row("rep2", "no_fit"),      # inconsistent
    ]
    joined, _ = analysis.join(labels, key)
    result = analysis.intra_rater_consistency(joined)
    assert result["n_pairs"] == 2
    assert result["consistent"] == 1
    assert result["rate"] == pytest.approx(0.5)


def test_intra_rater_consistency_ignores_unlabeled_pairs():
    key = [
        _key_row("orig1", "hard_negative", "no_fit"),
        _key_row("rep1", "hard_negative", "no_fit", is_repeat=True, repeat_of="orig1"),
    ]
    labels = [_label_row("orig1", "no_fit")]  # rep1 not labeled yet
    joined, _ = analysis.join(labels, key)
    result = analysis.intra_rater_consistency(joined)
    assert result["n_pairs"] == 0
    assert result["rate"] is None


def test_ensemble_vs_human_placeholder_uses_expected_label():
    key = [_key_row("g1", "gold", "fit"), _key_row("g2", "gold", "fit")]
    labels = [_label_row("g1", "fit"), _label_row("g2", "no_fit")]
    joined, _ = analysis.join(labels, key)
    stat = analysis.ensemble_vs_human(joined, panel_verdicts=None)
    assert stat["is_placeholder"] is True
    assert stat["successes"] == 1
    assert stat["n"] == 2


def test_ensemble_vs_human_real_panel_verdicts():
    key = [_key_row("g1", "gold", "fit"), _key_row("g2", "gold", "fit")]
    labels = [_label_row("g1", "fit"), _label_row("g2", "no_fit")]
    joined, _ = analysis.join(labels, key)
    # panel disagrees with expected_label on g2 but the human happens to
    # match the (wrong) panel verdict there -> successes counts panel-vs-
    # human agreement, not expected_label agreement.
    panel = {"g1": "fit", "g2": "no_fit"}
    stat = analysis.ensemble_vs_human(joined, panel_verdicts=panel)
    assert stat["is_placeholder"] is False
    assert stat["successes"] == 2
    assert stat["n"] == 2


def test_ensemble_vs_human_excludes_repeats_and_unsure():
    key = [
        _key_row("g1", "gold", "fit"),
        _key_row("rep1", "gold", "fit", is_repeat=True, repeat_of="g1"),
        _key_row("g2", "gold", "fit"),
    ]
    labels = [
        _label_row("g1", "fit"), _label_row("rep1", "fit"),
        _label_row("g2", "unsure"),
    ]
    joined, _ = analysis.join(labels, key)
    stat = analysis.ensemble_vs_human(joined, panel_verdicts=None)
    # only g1 counts: rep1 excluded (is_repeat), g2 excluded (unsure)
    assert stat["n"] == 1
    assert stat["successes"] == 1


def test_gate_pass_at_181_of_200():
    key = [_key_row(f"i{i}", "hard_negative", "no_fit") for i in range(200)]
    labels = [_label_row(f"i{i}", "no_fit" if i < 181 else "fit") for i in range(200)]
    joined, _ = analysis.join(labels, key)
    stat = analysis.ensemble_vs_human(joined, panel_verdicts=None)
    assert stat["successes"] == 181
    assert stat["n"] == 200
    assert stat["wilson_lo"] >= analysis.GATE_THRESHOLD


def test_gate_fail_at_150_of_200():
    key = [_key_row(f"i{i}", "hard_negative", "no_fit") for i in range(200)]
    labels = [_label_row(f"i{i}", "no_fit" if i < 150 else "fit") for i in range(200)]
    joined, _ = analysis.join(labels, key)
    stat = analysis.ensemble_vs_human(joined, panel_verdicts=None)
    assert stat["successes"] == 150
    assert stat["n"] == 200
    assert stat["wilson_lo"] < analysis.GATE_THRESHOLD


def test_swapped_pair_rejection():
    strata = {"easy_negative": {"n": 20, "agree": 19, "agree_rate": 0.95, "unsure": 0}}
    assert analysis.swapped_pair_rejection(strata) == pytest.approx(0.95)
    assert analysis.swapped_pair_rejection({}) is None


def test_load_panel_verdicts_none_when_no_path():
    assert analysis.load_panel_verdicts(None) is None


def test_load_panel_verdicts_from_file(tmp_path):
    p = tmp_path / "panel.jsonl"
    p.write_text(
        json.dumps({"item_id": "a", "verdict": "fit"}) + "\n"
        + json.dumps({"item_id": "b", "verdict": "no_fit"}) + "\n",
        encoding="utf-8")
    result = analysis.load_panel_verdicts(str(p))
    assert result == {"a": "fit", "b": "no_fit"}


def test_main_end_to_end_smoke(tmp_path, capsys):
    key_path = tmp_path / "packet_key.jsonl"
    labels_path = tmp_path / "labels.jsonl"
    key = [_key_row("g1", "gold", "fit"), _key_row("g2", "gold", "fit")]
    with key_path.open("w", encoding="utf-8") as f:
        for k in key:
            f.write(json.dumps(k) + "\n")
    with labels_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_label_row("g1", "fit")) + "\n")

    rc = analysis.main(["--labels", str(labels_path), "--key", str(key_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "§6 human-audit report" in out
    assert "gate" in out.lower()
