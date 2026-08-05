from __future__ import annotations

import json

from experiments.intent_loop import mockdata
from experiments.intent_loop.faithfulness import (back_translate,
                                                  evaluate_faithfulness)
from experiments.intent_loop.llm import MockChat
from experiments.intent_loop.schema import DistilledIntent, Requirement


def _distilled() -> DistilledIntent:
    raw = json.loads(mockdata.INTERROGATOR_DONE)["distilled"]
    return DistilledIntent.from_dict(raw)


def test_faithful_episode_aggregates_true():
    llm = MockChat(mockdata.EVAL_SCRIPT)
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT)
    assert report.recall == 1.0
    assert report.ungrounded == []
    assert report.backtranslation["score"] == 92
    assert report.faithful
    assert report.gold_equivalent is None


def test_missing_requirement_fails_verdict():
    coverage = json.loads(mockdata.COVERAGE_REPLY)
    coverage["verdicts"] = coverage["verdicts"][:-1]  # drop R5's verdict
    llm = MockChat([json.dumps(coverage), mockdata.BACKTRANSLATION_REPLY,
                    mockdata.COMPARE_REPLY])
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT)
    # Unverdicted requirement counts as a miss, never a free pass.
    r5 = next(v for v in report.coverage if v.rid == "R5")
    assert r5.covered == "no"
    assert report.recall == 0.8
    assert not report.faithful


def test_low_backtranslation_score_fails_verdict():
    llm = MockChat([mockdata.COVERAGE_REPLY, mockdata.BACKTRANSLATION_REPLY,
                    json.dumps({"score": 40, "missing": ["the audit rule"],
                                "added": []})])
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT)
    assert report.recall == 1.0
    assert not report.faithful


def test_back_translator_never_sees_the_intent():
    llm = MockChat([mockdata.BACKTRANSLATION_REPLY])
    back_translate(llm, mockdata.FIXED_DRAFT)
    stage, system, user = llm.calls[0]
    assert stage == "backtranslate"
    combined = system + user
    # The intent/mission text must be absent from everything the
    # back-translator was shown (the J-back isolation property).
    assert "quarterly report workflow" not in combined.lower()
    assert "mission" not in combined.lower()


def test_policy_requirements_are_reported_not_scored():
    """A separation-of-duties rule ("the approver and the payer must be
    different people") cannot be expressed as a session type. It must not
    be sent to the coverage checker, must not drag recall down, and must
    still appear in the report as a deployment-layer obligation."""
    distilled = _distilled()
    distilled.requirements.append(Requirement(
        rid="R6", kind="policy",
        text="The Approver and the Analyst must be different people.",
        who=["Approver", "Analyst"], source="answer"))
    llm = MockChat(mockdata.EVAL_SCRIPT)
    report = evaluate_faithfulness(llm, distilled, mockdata.FIXED_DRAFT)

    # The checker never saw the policy requirement.
    _stage, _system, coverage_user = llm.calls[0]
    assert "different people" not in coverage_user
    # It is reported, but excluded from recall — so the verdict still stands.
    r6 = next(v for v in report.coverage if v.rid == "R6")
    assert r6.covered == "out_of_scope"
    assert report.recall == 1.0
    assert report.faithful
    assert "Reported but NOT scored: 1 policy" in report.rule
    assert report.scope["policy"] == 1 and report.scope["graded"] == 5


def test_policy_requirements_excluded_from_backtranslation_reference():
    distilled = _distilled()
    distilled.requirements.append(Requirement(
        rid="R6", kind="policy",
        text="The Approver and the Analyst must be different people.",
        who=[], source="answer"))
    md = distilled.to_markdown(include_policy=False)
    assert "different people" not in md
    assert "different people" in distilled.to_markdown()


def test_interaction_payloads_and_cardinality_reach_the_spec():
    """Payload constraints and repeat bounds must survive into the text the
    drafter is given — a constraint that never reaches the prompt is a rule
    nothing will enforce."""
    from experiments.intent_loop.schema import Field, Interaction
    d = _distilled()
    d.interactions = [
        Interaction(iid="I1", sender="Analyst", receiver="Approver",
                    what="the analysis for sign-off", when="after review",
                    carries=[Field("amount", "double", "greater than 500"),
                             Field("justification", "string", "non-empty")],
                    cardinality="at most 3 times"),
        Interaction(iid="I2", sender="Approver", receiver="Analyst",
                    what="a rejection", optional=True,
                    cardinality="unbounded"),
    ]
    md = d.to_markdown()
    assert "Analyst → Approver" in md
    assert "amount: double (greater than 500)" in md
    assert "how often: at most 3 times" in md
    # The constraints are also collected as guard material.
    assert [f.name for _iid, f in d.value_constraints()] == ["amount",
                                                             "justification"]
    assert "compile to refinement guards" in md
    # An unbounded repeat is surfaced, not silently accepted.
    assert [i.iid for i in d.unbounded_repeats()] == ["I2"]


def test_drafter_asks_for_guards_only_when_constraints_exist():
    from experiments.intent_loop.drafter_llm import ChatDrafter
    from experiments.seam_bench.t0.drafter import GUARD_SIDECAR_SENTINEL
    plain = MockChat([mockdata.FIXED_DRAFT])
    ChatDrafter(plain).draft("a spec with no constraints", 1)
    assert GUARD_SIDECAR_SENTINEL not in plain.calls[0][1]

    withc = MockChat([mockdata.FIXED_DRAFT])
    ChatDrafter(withc).draft(
        "spec\n### Value constraints these payloads must satisfy "
        "(compile to refinement guards)\n- I1.amount: > 500", 1)
    assert GUARD_SIDECAR_SENTINEL in withc.calls[0][1]


def test_interior_requirements_are_reported_not_graded():
    """Intra-role procedure ("open that cell and fix the syntax") crosses no
    role boundary. Grading a protocol on it made recall report a failure of
    the drafter where the honest reading is "most of this document is not
    coordination"."""
    d = _distilled()
    d.requirements.append(Requirement(
        rid="R6", kind="interior",
        text="Open the failing cell only and fix its syntax.",
        who=["Analyst"], source="document"))
    llm = MockChat(mockdata.EVAL_SCRIPT)
    report = evaluate_faithfulness(llm, d, mockdata.FIXED_DRAFT)

    _stage, _system, coverage_user = llm.calls[0]
    assert "fix its syntax" not in coverage_user   # never sent to the checker
    r6 = next(v for v in report.coverage if v.rid == "R6")
    assert r6.covered == "out_of_scope"
    assert report.recall == 1.0 and report.faithful
    assert report.scope["interior"] == 1
    assert report.scope["graded"] == 5
    # 5 of 6 requirements are genuinely coordination.
    assert report.scope["typed_surface_ratio"] == round(5 / 6, 3)
    assert "intra-role interior" in report.rule


def test_joins_and_shared_resources_are_surfaced():
    from experiments.intent_loop.schema import (Interaction, Resource,
                                                SessionInvariant)
    d = _distilled()
    d.interactions = [
        Interaction(iid="I1", sender="A", receiver="B", what="x"),
        Interaction(iid="I2", sender="C", receiver="B", what="y"),
        Interaction(iid="I3", sender="B", receiver="A", what="verify",
                    waits_for=["I1", "I2"]),
    ]
    d.resources = [Resource("config.yaml", "file", "shared-write",
                            "one writer at a time"),
                   Resource("hive_table", "table", "read")]
    d.invariants = [SessionInvariant("repair_rounds", "<= 3",
                                     resets_on="pair accepted",
                                     on_breach="STOP and report")]
    assert [i.iid for i in d.joins()] == ["I3"]
    assert [r.name for r in d.shared_write_resources()] == ["config.yaml"]
    md = d.to_markdown()
    assert "waits for ALL of: I1, I2" in md
    assert "Joins" in md and "deadlocks" in md
    assert "shared-write" in md
    assert "repair_rounds" in md and "<= 3" in md


def test_gold_equivalence_uses_injected_bisim():
    calls = []
    def fake_bisim(a, b):
        calls.append((a, b))
        return True, "structurally equivalent"
    llm = MockChat(mockdata.EVAL_SCRIPT)
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT,
                                   gold_protocol="gold text",
                                   bisim_fn=fake_bisim)
    assert report.gold_equivalent is True
    assert calls == [(mockdata.FIXED_DRAFT, "gold text")]
