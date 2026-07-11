from __future__ import annotations

import json

import pytest

from experiments.seam_bench.judge.run_panel import judge_case
from experiments.seam_bench.judge.tests.conftest import MockAnthropic
from stjp_core.config import SCRIBBLE_PATH


def _verdict_json(vote="yes", confidence=0.9, quote=""):
    return json.dumps({"vote": vote, "confidence": confidence, "evidence": ([{"quote": quote, "source": "protocol"}] if quote else []), "missing": []})


def test_judge_case_end_to_end_with_real_cache(tmp_path, corpus_000):
    if not SCRIBBLE_PATH.exists():
        pytest.skip("real Scribble toolchain not installed in this environment")

    from experiments.seam_bench.judge.cache import VerdictCache

    def responder(kwargs):
        system = kwargs.get("system", "")
        output_config = kwargs.get("output_config")
        if output_config is None:
            if "written by someone who only saw a formal protocol" in system:
                return "R0 and R1 exchange booleans, R2 acknowledges, R1 and R3 negotiate, R3 reports back."
            return "A paraphrase: four roles coordinate a short handshake."
        schema = output_config["format"]["schema"]
        if "probes" in schema["properties"]:
            return json.dumps({
                "probes": [{
                    "query_text": "does R0 ever send M1 to R1?",
                    "kind": "reachable", "role": "R0", "label": "M1", "direction": "send", "peer": "R1",
                    "response_role": "", "response_label": "", "response_direction": "", "response_peer": "",
                }],
            })
        content = kwargs["messages"][0]["content"]
        quote = "M1(Bool) from R0 to R1;" if "PROTOCOL" in content else ("R0 and R1 exchange booleans" if "ORIGINAL" in content else "")
        return _verdict_json(vote="yes", confidence=0.9, quote=quote)

    client = MockAnthropic(responder)
    cache = VerdictCache(tmp_path / "cache")
    result, verdicts, payload = judge_case(client, cache, "R0 and R1 exchange booleans", corpus_000)

    assert len(verdicts) == 5
    classes_seen = sorted(v.class_ for v in verdicts)
    assert classes_seen == ["back", "back", "fwd", "fwd", "probe"]
    assert result.verdict == "accept"
    assert not result.vetoed
    assert not result.escalate
