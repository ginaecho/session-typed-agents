"""The learning loop: what a rejected episode teaches, and how that
knowledge reaches the next attempt and the next run."""
from __future__ import annotations

from pathlib import Path

from experiments.intent_loop.drafter_llm import ChatDrafter
from experiments.intent_loop.llm import MockChat
from experiments.intent_loop.loop import learn_from_attempts, standing_lessons

PROTO = """module T;
data <java> "java.lang.String" from "rt.jar" as String;
global protocol P(role A, role B, role C) {
    Start(String) from A to B;
    choice at B {
        Yes(String) from B to C;
    } or {
        No(String) from B to A;
    }
}
"""


def test_repair_carries_every_previous_rejection():
    """The production loop hands the repairer only the LATEST error, so a
    model can oscillate between two wrong shapes until the budget is gone.
    The drafter must accumulate."""
    chat = MockChat(["fix one", "fix two", "fix three"])
    d = ChatDrafter(chat)
    d.repair("spec", PROTO, "Source role not enabled: C")
    d.repair("spec", PROTO, "Subject not enabled: A")
    d.repair("spec", PROTO, "Safety violation at state 42")

    third = chat.calls[2][2]
    assert "Source role not enabled: C" in third      # first error retained
    assert "Subject not enabled: A" in third          # second retained
    assert "do not repeat these" in third.lower()


def test_repair_includes_the_structural_diagnosis():
    """Scribble names the role but not the branch; the structural checker
    names both, and a repairer told the branch fixes it in one round."""
    chat = MockChat(["fixed"])
    ChatDrafter(chat).repair("spec", PROTO, "Source role not enabled: C")
    prompt = chat.calls[0][2]
    assert "STRUCTURAL DIAGNOSIS" in prompt
    assert "uninformed-branch" in prompt and "C" in prompt


def test_lessons_persist_across_episodes(tmp_path: Path):
    path = tmp_path / "lessons.json"
    assert standing_lessons(path) == []

    learn_from_attempts([
        {"k": 1, "valid": False,
         "validator_msg": "line 1:0 mismatched input 'global' expecting "
                          "MODULE_KW"},
        {"k": 2, "valid": True, "validator_msg": ""},
    ], path=path)
    after_first = standing_lessons(path)
    assert any("module" in l.lower() for l in after_first)

    # A second episode adds its own family without losing the first.
    learn_from_attempts([
        {"k": 1, "valid": False,
         "validator_msg": "Source role not enabled: Inspector"},
    ], path=path)
    after_second = standing_lessons(path)
    assert any("not enabled" in l.lower() or "choice" in l.lower()
               for l in after_second)
    assert any("module" in l.lower() for l in after_second)


def test_only_real_validator_verdicts_become_lessons(tmp_path: Path):
    """A lesson must trace to something the checker actually said — never
    to a guess about why a draft 'probably' failed."""
    path = tmp_path / "lessons.json"
    learn_from_attempts([
        {"k": 1, "valid": False, "validator_msg": ""},     # no verdict
        {"k": 2, "valid": True, "validator_msg": ""},      # accepted
    ], path=path)
    assert standing_lessons(path) == []


def test_repeated_errors_collapse_to_one_lesson(tmp_path: Path):
    """The same failure hit twenty times is still one thing to learn —
    digits and file names are normalised out of the family key."""
    path = tmp_path / "lessons.json"
    attempts = [{"k": i, "valid": False,
                 "validator_msg": f"weird error number {i} at line {i}"}
                for i in range(20)]
    learn_from_attempts(attempts, path=path)
    assert len(standing_lessons(path)) == 1


def test_lesson_list_is_bounded(tmp_path: Path):
    """The drafter's prompt cannot grow without bound as episodes pile up."""
    path = tmp_path / "lessons.json"
    attempts = [{"k": i, "valid": False,
                 "validator_msg": f"distinct failure mode {chr(65 + i)}"}
                for i in range(10)]
    learn_from_attempts(attempts, path=path, max_lessons=4)
    assert len(standing_lessons(path)) == 4
