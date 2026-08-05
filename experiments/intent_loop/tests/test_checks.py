"""Deadlock precursors and turn order — the two properties the framework is
for. All offline: these run on the parsed structure, no JVM."""
from __future__ import annotations

from experiments.intent_loop.protocol_checks import check_protocol

PREAMBLE = """module T;
data <java> "java.lang.String" from "rt.jar" as String;
"""

UNINFORMED = PREAMBLE + """
global protocol P(role A, role B, role C) {
    Start(String) from A to B;
    choice at B {
        Yes(String) from B to C;
        Done(String) from C to A;
    } or {
        No(String) from B to A;
    }
}
"""

NO_EXIT = PREAMBLE + """
global protocol P(role A, role B) {
    rec LOOP {
        Ping(String) from A to B;
        Pong(String) from B to A;
        continue LOOP;
    }
}
"""

CLEAN = PREAMBLE + """
global protocol P(role A, role B, role C) {
    Start(String) from A to B;
    choice at B {
        YesToC(String) from B to C;
        YesToA(String) from B to A;
        Done(String) from C to A;
    } or {
        NoToC(String) from B to C;
        NoToA(String) from B to A;
    }
}
"""


def _kinds(report, severity="blocker"):
    return {f["kind"] for f in report["findings"]
            if f["severity"] == severity}


def test_uninformed_branch_is_a_blocker():
    """C acts on one branch only and is never told the decision on the
    other — the classic MPST rejection, and a real deadlock."""
    r = check_protocol(UNINFORMED)
    assert "uninformed-branch" in _kinds(r)
    assert r["blockers"] >= 1
    detail = next(f["detail"] for f in r["findings"]
                  if f["kind"] == "uninformed-branch")
    assert "C" in detail and "never told" in detail


def test_loop_without_exit_is_a_blocker():
    r = check_protocol(NO_EXIT)
    assert "no-loop-exit" in _kinds(r)


def test_clean_protocol_has_no_blocker():
    r = check_protocol(CLEAN)
    assert r["blockers"] == 0
    assert r["verdict"] == "no structural blocker found"


def test_self_send_is_flagged_as_interior_leak():
    p = PREAMBLE + """
global protocol P(role A, role B) {
    Work(String) from A to A;
    Hand(String) from A to B;
}
"""
    r = check_protocol(p)
    assert "self-send" in _kinds(r, "warning")


def test_turn_order_names_one_enabled_sender_per_step():
    r = check_protocol(CLEAN)
    t = r["turn_order"]
    steps = t["turns"]
    assert steps[0]["role"] == "A" and "Start" in steps[0]["action"]
    # At the choice, the deciding role is the one enabled.
    decide = next(s for s in steps if s["action"].startswith("decide"))
    assert decide["role"] == "B"
    # Everyone else is explicitly waiting — that is what makes an idle poll
    # visibly wasteful.
    assert set(steps[0]["waiting"]) == {"B", "C"}
    p = t["polling"]
    assert p["round_robin_polls"] == p["enabled_polls"] * 3
    assert p["wasted_polls"] == p["round_robin_polls"] - p["enabled_polls"]


def test_declared_joins_are_carried_into_the_report():
    r = check_protocol(CLEAN, declared_joins=[
        {"iid": "I9", "waits_for": ["I7", "I8"], "what": "verify"}])
    join = next(f for f in r["findings"] if f["kind"] == "declared-join")
    assert "I7, I8" in join["detail"]


ID_LABELS = PREAMBLE + """
global protocol P(role A, role B) {
    I1(String) from A to B;
    I2(String) from B to A;
    I3Score(String) from A to B;
}
"""


def test_identifier_labels_block_even_though_scribble_accepts_them():
    """The whole point: a protocol of I1/I2/I3 type-checks and says nothing.
    Valid is a floor, so meaninglessness has to be a blocker of its own."""
    r = check_protocol(ID_LABELS)
    assert "meaningless-vocabulary" in _kinds(r)
    assert "id-as-label" in _kinds(r, "warning")
    detail = next(f["detail"] for f in r["findings"]
                  if f["kind"] == "meaningless-vocabulary")
    assert "valid is not the same as faithful" in detail


def test_meaningful_labels_pass():
    p = PREAMBLE + """
global protocol P(role A, role B) {
    PreflightVerdict(String) from A to B;
    ApprovalGranted(String) from B to A;
}
"""
    assert "meaningless-vocabulary" not in _kinds(check_protocol(p))


def test_dropped_and_invented_handovers_are_found():
    """Grounding, mechanically: a declared handover with no message is a
    lost requirement; a message between an undeclared pair is invented."""
    declared = [{"sender": "A", "receiver": "B", "what": "the request"},
                {"sender": "B", "receiver": "C", "what": "the outcome"}]
    p = PREAMBLE + """
global protocol P(role A, role B, role C) {
    TheRequest(String) from A to B;
    Surprise(String) from B to A;
}
"""
    r = check_protocol(p, interactions=declared)
    assert "dropped-interaction" in _kinds(r)          # B -> C never happens
    assert "ungrounded-message" in _kinds(r, "warning")  # B -> A undeclared


def test_faithfulness_failures_become_lessons(tmp_path):
    from experiments.intent_loop.loop import learn_from_faithfulness
    path = tmp_path / "lessons.json"
    faith = {"recall": 0.06, "ungrounded": ["Surprise from B to A"],
             "structural": {"findings": [
                 {"kind": "meaningless-vocabulary", "where": "protocol",
                  "detail": "..."},
                 {"kind": "dropped-interaction", "where": "B → C",
                  "detail": "..."}]}}
    lessons = learn_from_faithfulness(faith, path=path)
    joined = " ".join(lessons).lower()
    assert "name what the message carries" in joined
    assert "must appear as a message" in joined
    assert "invented structure" in joined
    assert "under half the checklist" in joined


def test_report_states_that_scribble_is_the_authority():
    """A clean precheck must never read as proof of deadlock-freedom."""
    r = check_protocol(CLEAN)
    assert "real Scribble checker" in r["authority_note"]
    assert "proves nothing" in r["authority_note"]
