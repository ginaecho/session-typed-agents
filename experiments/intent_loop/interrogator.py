"""interrogator.py — the intake analyst: multi-turn interrogation loop.

BENCHMARK_PLAN_V3 §10.3 modeled interrogation as a one-shot distillation
("the interrogation step") and the fairness note said not to overclaim.
This module is the real thing: the interrogator reads the intent document,
asks the stakeholder batched questions across rounds, and only then emits
the distilled artifacts. What interrogation adds over one-shot distillation,
concretely:

  1. facts not in the document (StakeholderSim.hidden_notes) can be
     surfaced by asking;
  2. ambiguities become EXPLICIT — an unanswered question must land in
     `open_questions` or as a requirement with source="assumption", never
     as a silently invented fact;
  3. every requirement carries its provenance (document / answer /
     assumption), which the faithfulness suite and the training corpus
     keep.

Protocol-drafting is downstream: the distilled requirement checklist is
both the drafter's input AND the unit the faithfulness suite checks the
drafted protocol against, item by item (faithfulness.py). That closed loop
— distill, draft, check each distilled item — is what makes "the protocol
is faithful to the intent" an inspectable claim instead of a vibe.
"""
from __future__ import annotations

from experiments.intent_loop.llm import ChatLLM, Meter
from experiments.intent_loop.schema import (DistilledIntent, Goal,
                                            Interaction, InterrogationResult,
                                            QA, Requirement, parse_json_block)
from experiments.intent_loop.stakeholder import StakeholderSim

DEFAULT_MAX_ROUNDS = 5
DEFAULT_MAX_QUESTIONS_PER_ROUND = 4

_DISTILLED_JSON_SPEC = """{
  "action": "done",
  "distilled": {
    "mission": "<one-paragraph mission statement>",
    "roles": [{"name": "<RoleName>", "description": "<the job this role \
does — its responsibilities, in one or two sentences>"}],
    "goals": [{"gid": "G1", "text": "<an outcome that must be TRUE when \
the work is finished>", "evidence": "<how you would know it happened>"}],
    "interactions": [{"iid": "I1", "from": "<RoleName>", "to": "<RoleName>",
       "what": "<the information handed over, in plain language>",
       "when": "<the trigger or precondition>", "optional": false}],
    "non_goals": ["<something explicitly OUT of scope>"],
    "requirements": [
      {"rid": "R1",
       "kind": "role|ordering|authorization|value|branch|termination|policy|other",
       "text": "<ONE atomic, checkable sentence>",
       "who": ["<RoleName>", ...],
       "source": "document|answer|assumption"}
    ],
    "completion_signal": "<how everyone knows the task is finished>",
    "open_questions": ["<anything still unresolved>", ...]
  }
}"""

_SYSTEM_TEMPLATE = """You are an INTAKE ANALYST for a team that compiles \
multi-agent coordination protocols. A stakeholder handed you the intent \
document below. Your job: extract everything a protocol designer needs — \
the roles, who sends what to whom, in what order, which decisions branch \
on which values, which acts need prior authorization, value constraints \
(thresholds, non-empty fields), and how the session terminates.

You work in rounds. Each round, reply with EXACTLY ONE JSON object, no \
prose outside it:

To ask (max {max_q} questions, numbered, only questions the document does \
NOT already answer — check carefully first):
{{"action": "ask", "questions": ["1. ...", "2. ..."]}}

When you have enough to specify the protocol (or nothing useful remains to \
ask), finish with the full distilled output:
{spec}

Distillation rules:
- Cover all five, they are different things: WHO (roles), WHAT EACH ONE \
DOES (role descriptions — the job), WHO HANDS WHAT TO WHOM (interactions), \
WHAT CONSTRAINS them (requirements), and WHAT MUST BE TRUE AT THE END \
(goals). A goal is an outcome; a requirement constrains how you get there. \
Do not merge them.
- `interactions` must list EVERY handover the work needs, including the \
unhappy paths (rejection, retry, escalation). Mark `optional: true` when it \
only happens on some branch. These become the messages of the protocol, so \
an interaction you omit is a message nobody will build.
- `non_goals` is what must NOT be built. It is how a reader can tell an \
invented step from a required one, so state anything the document rules \
out or deliberately leaves alone.
- Requirements must be ATOMIC (one checkable fact each) and TYPED.
- Use kind "policy" for any requirement that constrains WHO may inhabit a \
role, or otherwise cannot be expressed as "which role sends which message \
in which order" — separation of duties ("the approver and the payer must \
be different people"), identity, access control, data retention, staffing. \
These are real requirements, but they are enforced by the deployment and \
identity layer, NOT by the interaction protocol, and they are recorded \
separately so nobody grades the protocol on them. Requirements about \
message ORDER, AUTHORIZATION-before-an-act, payload VALUES, BRANCHING and \
TERMINATION are protocol requirements — never label those "policy".
- Every requirement carries its source: "document" (stated in the \
document), "answer" (learned from a stakeholder answer), "assumption" \
(you chose it because the stakeholder said NOT SPECIFIED — keep these \
rare and conservative).
- If the stakeholder answered NOT SPECIFIED and no safe default exists, \
put the issue in open_questions instead of inventing a requirement.
- Do not use protocol-vocabulary jargon in requirement text (no message \
labels, no "Scribble", no state machines) — plain business language only.

=== INTENT DOCUMENT ===
{document}"""


def _questions_block(questions: list[str]) -> str:
    return "\n".join(questions)


def run_interrogation(llm: ChatLLM, stakeholder: StakeholderSim,
                      document: str, *,
                      max_rounds: int = DEFAULT_MAX_ROUNDS,
                      max_questions_per_round: int = DEFAULT_MAX_QUESTIONS_PER_ROUND,
                      meter: Meter | None = None,
                      progress=None) -> InterrogationResult:
    """Drive interrogator <-> stakeholder until 'done' or max_rounds.

    On hitting max_rounds without a 'done', one final forced call demands
    the distillation from what was gathered (forced_finish=True in the
    result — corpus consumers can treat those episodes differently).

    `progress(stage, detail)` fires at every sub-step — `asking`, `asked`,
    `answered`, `distilling` — and `progress` also receives the transcript
    so far. Interrogation over a document-scale intent is several minutes
    of real model work; reporting only when the whole phase ends makes a
    working system look hung, which is how this callback came to exist.
    """
    def _emit(stage: str, **detail) -> None:
        if progress is not None:
            progress(stage, detail)
    system = _SYSTEM_TEMPLATE.format(
        document=document, max_q=max_questions_per_round,
        spec=_DISTILLED_JSON_SPEC)
    history: list[dict[str, str]] = [
        {"role": "user",
         "content": "Begin. Ask your first questions, or finish immediately "
                    "if the document already answers everything."}]
    transcript: list[QA] = []
    rounds = 0
    forced = False
    distilled_raw: dict | None = None

    while True:
        _emit("thinking", round=rounds + 1,
              note="the analyst is reading the document and composing "
                   "questions")
        reply = llm.complete_with_history(system, history,
                                          stage="interrogator")
        history.append({"role": "assistant", "content": reply})
        try:
            obj = parse_json_block(reply)
        except ValueError:
            # One nudge, then treat a second failure as fatal — a model that
            # cannot emit the envelope twice will not emit it a third time.
            history.append({"role": "user",
                            "content": "Reply with exactly one JSON object "
                                       "in the specified envelope."})
            reply = llm.complete_with_history(system, history,
                                              stage="interrogator")
            history.append({"role": "assistant", "content": reply})
            obj = parse_json_block(reply)

        action = obj.get("action")
        if action == "done":
            _emit("distilling", round=rounds,
                  note="questions exhausted — writing the checklist")
            distilled_raw = obj.get("distilled", {})
            break

        if action != "ask" or not obj.get("questions"):
            raise ValueError(
                f"interrogator round {rounds + 1}: unrecognized envelope "
                f"{obj!r} (expected action ask|done)")

        rounds += 1
        questions = [str(q) for q in obj["questions"]][:max_questions_per_round]
        _emit("asked", round=rounds, questions=questions)
        answers = stakeholder.answer(_questions_block(questions))
        transcript.append(QA(round=rounds,
                             question=_questions_block(questions),
                             answer=answers))
        _emit("answered", round=rounds,
              transcript=[qa.to_dict() for qa in transcript])
        if rounds >= max_rounds:
            forced = True
            history.append({"role": "user",
                            "content": "STAKEHOLDER ANSWERS:\n" + answers
                                       + "\n\nQuestion budget exhausted. "
                                         "Finish NOW with the action=done "
                                         "envelope; unresolved points go to "
                                         "open_questions."})
            reply = llm.complete_with_history(system, history,
                                              stage="interrogator")
            history.append({"role": "assistant", "content": reply})
            obj = parse_json_block(reply)
            distilled_raw = obj.get("distilled", {})
            break
        history.append({"role": "user",
                        "content": "STAKEHOLDER ANSWERS:\n" + answers
                                   + "\n\nNext round: ask more, or finish."})

    distilled = _parse_distilled(distilled_raw or {})
    m = meter if meter is not None else getattr(llm, "meter", None)
    return InterrogationResult(
        distilled=distilled, transcript=transcript, rounds_used=rounds,
        forced_finish=forced,
        meter=(m.to_dict() if isinstance(m, Meter) else {}))


def _parse_distilled(raw: dict) -> DistilledIntent:
    reqs = []
    for i, r in enumerate(raw.get("requirements", []), start=1):
        if "rid" not in r:
            r = {**r, "rid": f"R{i}"}
        reqs.append(Requirement.from_dict(r))
    goals = []
    for i, g in enumerate(raw.get("goals", []), start=1):
        goals.append(Goal.from_dict({**g, "gid": g.get("gid") or f"G{i}"}))
    interactions = []
    for i, x in enumerate(raw.get("interactions", []), start=1):
        ix = Interaction.from_dict({**x, "iid": x.get("iid") or f"I{i}"})
        if ix.sender and ix.receiver:      # a half-declared handover is noise
            interactions.append(ix)
    return DistilledIntent(
        mission=str(raw.get("mission", "")).strip(),
        roles=[{"name": str(r.get("name", "")),
                "description": str(r.get("description", ""))}
               for r in raw.get("roles", [])],
        requirements=reqs, goals=goals, interactions=interactions,
        non_goals=[str(n) for n in raw.get("non_goals", [])],
        completion_signal=str(raw.get("completion_signal", "")).strip(),
        open_questions=[str(q) for q in raw.get("open_questions", [])])
