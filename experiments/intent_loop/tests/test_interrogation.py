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


def test_finishing_without_asking_is_refused():
    """The failure that defeats the whole app: on a 64k-char document
    gpt-5.4 read it, decided it knew enough, and produced 47 requirements
    from 0 Q&A rounds — the worst faithfulness of any run. Asking is the
    mechanism, so it is no longer optional."""
    replies = [mockdata.INTERROGATOR_DONE,        # tries to finish first
               mockdata.INTERROGATOR_ROUND1,      # pushed back -> asks
               mockdata.INTERROGATOR_DONE]        # then may finish
    interrogator = MockChat(replies)
    stakeholder = StakeholderSim(MockChat(mockdata.STAKEHOLDER_SCRIPT),
                                 mockdata.DEMO_DOCUMENT,
                                 hidden_notes=mockdata.HIDDEN_NOTES)
    result = run_interrogation(interrogator, stakeholder,
                              mockdata.DEMO_DOCUMENT)
    assert result.rounds_used == 1
    assert len(result.transcript) == 1
    # The push-back names the three things worth asking about.
    pushback = next(u for _s, _sys, u in interrogator.calls
                    if "may not finish yet" in u)
    for word in ("ROLES", "INTERACTIONS", "GOALS"):
        assert word in pushback


def test_a_model_that_never_asks_is_recorded_not_looped_forever():
    """Insisting without a bound is a hang. A model that refuses to ask is
    accepted after MAX_PUSHBACKS and flagged, because an unbounded retry
    loop is the very failure this project keeps hitting."""
    interrogator = MockChat([mockdata.INTERROGATOR_DONE])   # always finishes
    stakeholder = StakeholderSim(MockChat([]), mockdata.DEMO_DOCUMENT)
    result = run_interrogation(interrogator, stakeholder,
                              mockdata.DEMO_DOCUMENT)
    assert result.rounds_used == 0
    assert result.forced_finish is True      # visible as "never interrogated"
    assert result.distilled.requirements     # the checklist still lands


def test_min_rounds_zero_allows_an_immediate_finish():
    """The push-back must be a policy, not a hard-coded loop — a caller
    measuring what the document alone supports can switch it off."""
    interrogator = MockChat([mockdata.INTERROGATOR_DONE])
    stakeholder = StakeholderSim(MockChat([]), mockdata.DEMO_DOCUMENT)
    result = run_interrogation(interrogator, stakeholder,
                              mockdata.DEMO_DOCUMENT, min_rounds=0)
    assert result.rounds_used == 0
    assert result.distilled.requirements


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
