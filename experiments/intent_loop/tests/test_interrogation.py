from __future__ import annotations

import json

from experiments.intent_loop import mockdata
from experiments.intent_loop.interrogator import run_interrogation
from experiments.intent_loop.llm import MockChat
from experiments.intent_loop.schema import parse_json_block
from experiments.intent_loop.stakeholder import NOT_SPECIFIED, StakeholderSim


def test_scripted_interrogation_surfaces_hidden_fact():
    interrogator = MockChat(mockdata.INTERROGATOR_SCRIPT)
    stakeholder = StakeholderSim(MockChat(mockdata.STAKEHOLDER_SCRIPT),
                                 mockdata.DEMO_DOCUMENT,
                                 hidden_notes=mockdata.HIDDEN_NOTES)
    result = run_interrogation(interrogator, stakeholder,
                               mockdata.DEMO_DOCUMENT)
    assert result.rounds_used == 1
    assert not result.forced_finish
    assert len(result.transcript) == 1
    d = result.distilled
    assert d.role_names() == ["Requester", "Analyst", "Approver"]
    assert len(d.requirements) == 5
    # The hidden-notes fact (the $100,000 rule) surfaced via an answer.
    r3 = next(r for r in d.requirements if r.rid == "R3")
    assert r3.source == "answer"
    assert "100,000" in r3.text


def test_max_rounds_forces_distillation():
    ask = json.dumps({"action": "ask", "questions": ["1. Anything else?"]})
    done = mockdata.INTERROGATOR_DONE
    # Keeps asking; only the forced-finish prompt produces the distillation.
    def script(system, last_user):
        if "Question budget exhausted" in last_user:
            return done
        return ask
    interrogator = MockChat(script)
    stakeholder = StakeholderSim(MockChat([NOT_SPECIFIED]),
                                 mockdata.DEMO_DOCUMENT)
    result = run_interrogation(interrogator, stakeholder,
                               mockdata.DEMO_DOCUMENT, max_rounds=2)
    assert result.forced_finish
    assert result.rounds_used == 2
    assert len(result.distilled.requirements) == 5


def test_json_recovery_after_one_bad_reply():
    replies = ["sure, I will ask some questions!",  # not JSON -> nudge
               mockdata.INTERROGATOR_DONE]
    interrogator = MockChat(replies)
    stakeholder = StakeholderSim(MockChat([]), mockdata.DEMO_DOCUMENT)
    result = run_interrogation(interrogator, stakeholder,
                               mockdata.DEMO_DOCUMENT)
    assert result.distilled.mission


def test_parse_json_block_variants():
    obj = {"a": 1, "b": {"c": [1, 2]}}
    fenced = "Here you go:\n```json\n" + json.dumps(obj) + "\n```"
    bare = "prefix " + json.dumps(obj) + " suffix"
    assert parse_json_block(fenced) == obj
    assert parse_json_block(bare) == obj
