from __future__ import annotations

from experiments.intent_loop import mockdata
from experiments.intent_loop.drafter_llm import ChatDrafter, strip_fences
from experiments.intent_loop.llm import MockChat
from experiments.intent_loop.loop import mock_validate
from experiments.seam_bench.t0.repair_loop import run_repair_chain


def test_repair_chain_with_chat_drafter_recovers():
    drafter = ChatDrafter(MockChat(mockdata.DRAFTER_SCRIPT),
                          model_label="test-drafter")
    records = run_repair_chain(
        drafter, system="intent-loop", item_id="t1", split="train",
        intent="spec", max_rounds=3, validate_fn=mock_validate,
        bisim_fn=lambda a, b: (False, "unused"))
    assert [r.valid for r in records] == [False, True]
    assert records[0].validator_msg.startswith("mock-validator")
    assert records[-1].repair_rounds == 1
    # Usage is approx-metered, not the bare word-count fallback.
    assert "(chars/4 approx)" in records[0].model


def test_rulebook_and_exemplars_reach_the_prompt():
    chat = MockChat([mockdata.FIXED_DRAFT])
    drafter = ChatDrafter(chat, rulebook=["Always balance braces."])
    drafter.draft("spec text", 1,
                  exemplars=[("example intent", "example protocol")])
    stage, system, user = chat.calls[0]
    assert stage == "draft"
    assert "Always balance braces." in system
    assert "example protocol" in system
    assert "spec text" in user


def test_strip_fences():
    fenced = "```scribble\nglobal protocol P(role A, role B) { }\n```"
    assert strip_fences(fenced).startswith("global protocol")
    assert "```" not in strip_fences(fenced)
    plain = "global protocol P(role A, role B) { }"
    assert strip_fences(plain) == plain
