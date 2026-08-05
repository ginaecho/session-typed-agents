"""End-to-end offline smoke: the full `run --mock` episode through the CLI,
then `optimize` over the corpus it wrote, then a second episode using the
mined prompt pack. This is the whole loop, network-free."""
from __future__ import annotations

import json
from pathlib import Path

from experiments.intent_loop.cli import main


def test_full_mock_episode_then_optimize_then_pack_run(tmp_path: Path,
                                                       capsys):
    out1 = tmp_path / "session1"
    corpus = tmp_path / "corpus.jsonl"
    rc = main(["run", "--mock", "--out", str(out1),
               "--corpus", str(corpus)])
    assert rc == 0

    # Audit-completeness of the session dir.
    for artifact in ("document.md", "transcript.json", "intent_distilled.md",
                     "protocol.scr", "faithfulness.json", "record.json"):
        assert (out1 / artifact).exists(), artifact
    assert (out1 / "drafts" / "attempt_1.scr").exists()
    assert (out1 / "drafts" / "attempt_2.scr").exists()

    record = json.loads((out1 / "record.json").read_text(encoding="utf-8"))
    assert record["valid"] is True
    assert record["faithfulness"]["faithful"] is True
    assert record["meter"]["validator"] == "mock"
    # First attempt was rejected, repair fixed it.
    assert [a["valid"] for a in record["draft_attempts"]] == [False, True]
    # The hidden-notes fact made it into the distilled requirements.
    texts = [r["text"] for r in record["distilled"]["requirements"]]
    assert any("100,000" in t for t in texts)

    pack_path = tmp_path / "pack.json"
    rc = main(["optimize", "--corpus", str(corpus), "--out", str(pack_path),
               "--version", "vtest"])
    assert rc == 0
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    assert len(pack["exemplars"]) == 1          # the faithful episode
    assert len(pack["rulebook"]) >= 1           # the brace-balance family

    out2 = tmp_path / "session2"
    rc = main(["run", "--mock", "--out", str(out2), "--corpus", str(corpus),
               "--pack", str(pack_path)])
    assert rc == 0
    assert (out2 / "protocol.scr").exists()

    rc = main(["show-corpus", "--corpus", str(corpus)])
    assert rc == 0
    listed = capsys.readouterr().out
    assert "2 episode(s): 2 valid, 2 faithful" in listed
