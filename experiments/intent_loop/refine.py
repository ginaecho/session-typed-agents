"""refine.py — explain the draft, question it, and redraft with the answers.

The first draft is a proposal, not an answer. Three operations close the
loop around it:

  explain    Per message: which requirement it realizes and why it sits
             where it does. This is the "WHY is it presented so" view —
             without it a protocol diagram is just a shape, and a reviewer
             cannot tell a deliberate ordering from an accident.
  question   The LLM proposes the questions worth asking about THIS draft,
             anchored to real defects: requirements the faithfulness pass
             scored `no`/`partial`, messages no requirement grounds, and
             the interrogation's own unresolved questions. Questions are
             derived from measured gaps, never invented, so a clean draft
             yields few.
  refine     The answers (from the LLM's questions or typed by the user)
             become additional requirements with source `answer`, and the
             protocol is drafted again from the enriched checklist and
             re-graded.

Refinement produces a NEW episode rather than overwriting the old one, so
the corpus keeps the whole trajectory: draft 1 and its verdict, the
decisions taken, draft 2 and its verdict. That trajectory is the evidence
that refinement helped — or did not — and it is exactly what a later
fine-tune needs.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from experiments.intent_loop.corpus import DEFAULT_CORPUS_PATH, append_record
from experiments.intent_loop.drafter_llm import ChatDrafter
from experiments.intent_loop.faithfulness import evaluate_faithfulness
from experiments.intent_loop.llm import ChatLLM, Meter
from experiments.intent_loop.protocol_graph import parse_protocol
from experiments.intent_loop.schema import (DistilledIntent, LoopRecord,
                                            Requirement, parse_json_block)
from experiments.seam_bench.t0.drafter import split_guard_sidecar
from experiments.seam_bench.t0.repair_loop import (MAX_REPAIR_ROUNDS,
                                                   run_repair_chain)

_EXPLAIN_SYSTEM = """You explain a Scribble global protocol to a reviewer \
who wrote the requirements but does not read protocol syntax.

For EVERY message in the protocol, say which requirement id(s) it realizes \
and why it sits where it does (what must have happened before it, what it \
unblocks). If a message realizes no requirement, say so plainly — that is \
important, not embarrassing.

Reply with EXACTLY ONE JSON object:
{"messages": [{"label": "<MessageLabel>", "from": "<Role>", "to": "<Role>",
  "realizes": ["R1", ...], "why": "<one sentence>"}],
 "ordering_rationale": "<2-3 sentences: why this overall order, and what \
the branches are for>"}"""

_QUESTION_SYSTEM = """You review a FIRST DRAFT of a coordination protocol \
against the requirements it is meant to realize, and propose the questions \
whose answers would most improve the next draft.

Ground every question in a specific defect you were given: a requirement \
scored 'no' or 'partial', a protocol message that no requirement justifies, \
or an unresolved question from intake. Ask about the DECISION the drafter \
could not make — who decides, in what order, under what condition, what \
happens on the unhappy path. Never ask about anything already settled.

Each question must be answerable in one or two sentences by a business \
stakeholder who does not read protocol syntax.

Reply with EXACTLY ONE JSON object:
{"questions": [{"q": "<the question>", "because": "<the defect it targets, \
citing the requirement id or message label>", "kind": \
"ordering|authorization|branch|value|role|termination|policy"}]}"""

_REQUIREMENT_SYSTEM = """You convert answered questions into ATOMIC, TYPED \
requirements, in the same style as an existing checklist.

Reply with EXACTLY ONE JSON object:
{"requirements": [{"rid": "<new id, continuing the existing numbering>",
  "kind": "role|ordering|authorization|value|branch|termination|policy",
  "text": "<ONE atomic, checkable sentence in plain business language>",
  "who": ["<RoleName>", ...]}]}

Rules: one fact per requirement; no protocol jargon or message labels; use \
kind "policy" ONLY for constraints that cannot be expressed as message \
ordering (who may inhabit a role, identity, retention)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def explain_protocol(llm: ChatLLM, distilled: DistilledIntent,
                     protocol_text: str) -> dict:
    """Per-message rationale + the overall ordering argument."""
    user = (f"=== REQUIREMENTS ===\n{distilled.requirements_text()}\n\n"
            f"=== PROTOCOL ===\n{protocol_text}")
    obj = parse_json_block(llm.complete(_EXPLAIN_SYSTEM, user,
                                        stage="explain"))
    # Anchor the explanation to the messages that are really there, so a
    # hallucinated message cannot appear in the rationale view.
    real = {m.label for m in parse_protocol(protocol_text).messages()}
    msgs = [m for m in obj.get("messages", [])
            if str(m.get("label")) in real]
    known = {r.rid for r in distilled.requirements}
    for m in msgs:
        m["realizes"] = [r for r in m.get("realizes", []) if r in known]
    explained = {m["label"] for m in msgs}
    return {"messages": msgs,
            "ordering_rationale": str(obj.get("ordering_rationale", "")),
            "unexplained": sorted(real - explained),
            "generated_at": _now()}


def propose_questions(llm: ChatLLM, distilled: DistilledIntent,
                      protocol_text: str,
                      faithfulness: Optional[dict] = None,
                      max_questions: int = 8) -> list[dict]:
    """Questions anchored to measured defects in THIS draft."""
    f = faithfulness or {}
    weak = [c for c in f.get("coverage", [])
            if c.get("covered") in ("no", "partial")]
    defects = ["=== REQUIREMENTS NOT FULLY REALIZED ==="]
    by_rid = {r.rid: r for r in distilled.requirements}
    for c in weak:
        req = by_rid.get(c.get("rid"))
        defects.append(f"[{c.get('rid')}] ({c.get('covered')}) "
                       f"{req.text if req else ''} — checker said: "
                       f"{str(c.get('evidence', ''))[:240]}")
    if f.get("ungrounded"):
        defects.append("\n=== PROTOCOL STRUCTURE NO REQUIREMENT JUSTIFIES ===")
        defects += [f"- {u}" for u in f["ungrounded"]]
    if distilled.open_questions:
        defects.append("\n=== UNRESOLVED FROM INTAKE ===")
        defects += [f"- {q}" for q in distilled.open_questions]

    user = ("\n".join(defects) + f"\n\n=== PROTOCOL ===\n{protocol_text}"
            f"\n\nPropose at most {max_questions} questions.")
    obj = parse_json_block(llm.complete(_QUESTION_SYSTEM, user,
                                        stage="questions"))
    out = []
    for q in obj.get("questions", [])[:max_questions]:
        out.append({"q": str(q.get("q", "")).strip(),
                    "because": str(q.get("because", "")).strip(),
                    "kind": str(q.get("kind", "other"))})
    return [q for q in out if q["q"]]


def requirements_from_answers(llm: ChatLLM, distilled: DistilledIntent,
                              answers: list[dict]) -> list[Requirement]:
    """Answered questions -> new typed requirements (source='answer')."""
    answered = [a for a in answers if str(a.get("answer", "")).strip()]
    if not answered:
        return []
    existing_ids = [r.rid for r in distilled.requirements]
    qa = "\n\n".join(f"Q: {a.get('question', '')}\nA: {a['answer']}"
                     for a in answered)
    user = (f"=== EXISTING REQUIREMENT IDS ===\n{', '.join(existing_ids)}\n\n"
            f"=== EXISTING CHECKLIST (style reference) ===\n"
            f"{distilled.requirements_text()}\n\n"
            f"=== ANSWERED QUESTIONS ===\n{qa}")
    obj = parse_json_block(llm.complete(_REQUIREMENT_SYSTEM, user,
                                        stage="refine_requirements"))
    out: list[Requirement] = []
    taken = set(existing_ids)
    for i, r in enumerate(obj.get("requirements", []), start=1):
        rid = str(r.get("rid") or f"RA{i}")
        while rid in taken:
            rid += "a"
        taken.add(rid)
        out.append(Requirement.from_dict({**r, "rid": rid,
                                          "source": "answer"}))
    return out


def refine_episode(
    llm: ChatLLM, *, parent_record: dict, parent_dir: Path, out_dir: Path,
    answers: list[dict], validate_fn: Callable[[str], tuple[bool, str]],
    validator_label: str, prompt_pack=None,
    max_repair_rounds: int = MAX_REPAIR_ROUNDS,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    bisim_fn=None, progress=None,
) -> LoopRecord:
    """Redraft the protocol with the answers folded in, and re-grade.

    The intent document and the interrogation are NOT repeated — this is a
    second pass over the same understanding, enriched by decisions. That
    is what makes the two episodes comparable: only the checklist changed.
    """
    def _emit(stage: str, **detail) -> None:
        if progress is not None:
            progress(stage, detail)

    out_dir.mkdir(parents=True, exist_ok=True)
    distilled = DistilledIntent.from_dict(parent_record["distilled"])
    _emit("start", parent=parent_dir.name,
          answers=len([a for a in answers if str(a.get("answer", "")).strip()]))

    new_reqs = requirements_from_answers(llm, distilled, answers)
    distilled.requirements.extend(new_reqs)
    # An answered question is no longer open.
    answered_text = {str(a.get("question", "")).strip() for a in answers
                     if str(a.get("answer", "")).strip()}
    distilled.open_questions = [q for q in distilled.open_questions
                                if q not in answered_text]
    _emit("requirements_added", added=len(new_reqs),
          total=len(distilled.requirements))

    (out_dir / "intent_distilled.md").write_text(distilled.to_markdown(),
                                                 encoding="utf-8")
    (out_dir / "decisions.json").write_text(
        json.dumps({"parent": parent_dir.name, "answers": answers,
                    "new_requirements": [r.to_dict() for r in new_reqs],
                    "at": _now()}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    for name in ("document.md",):          # keep the run dir self-contained
        src = parent_dir / name
        if src.exists():
            (out_dir / name).write_text(src.read_text(encoding="utf-8"),
                                        encoding="utf-8")

    spec_text = distilled.to_markdown()
    drafter = ChatDrafter(llm, rulebook=(list(prompt_pack.rulebook)
                                         if prompt_pack else []),
                          model_label=getattr(llm, "label", "chat"))
    exemplars = (prompt_pack.select_exemplars(spec_text, 3)
                 if prompt_pack else None)
    # Show the previous draft: refining means improving THIS protocol, not
    # starting over from a blank page and losing what was already right.
    prior = parent_record.get("final_protocol") or ""
    seed_user = (f"{spec_text}\n\n=== PREVIOUS DRAFT (improve it; keep what "
                 f"already satisfies the checklist) ===\n{prior}")
    initial = drafter.draft(seed_user, 1, exemplars=exemplars)[0]

    records = run_repair_chain(
        drafter, system="intent-loop-refine",
        item_id=parent_record.get("episode_id", "refine"), split="train",
        intent=spec_text, initial_draft=initial,
        max_rounds=max_repair_rounds, validate_fn=validate_fn,
        bisim_fn=(bisim_fn or (lambda a, b: (False, "no bisim_fn"))))

    drafts_dir = out_dir / "drafts"
    drafts_dir.mkdir(exist_ok=True)
    attempts, final_protocol = [], None
    for rec in records:
        (drafts_dir / f"attempt_{rec.k}.scr").write_text(rec.draft,
                                                         encoding="utf-8")
        (drafts_dir / f"attempt_{rec.k}.verdict.txt").write_text(
            f"valid: {rec.valid}\nvalidator: {validator_label}\n\n"
            f"{rec.validator_msg}", encoding="utf-8")
        attempts.append({"k": rec.k, "valid": rec.valid,
                         "validator_msg": rec.validator_msg,
                         "chars": len(rec.draft)})
        if rec.valid:
            final_protocol = rec.draft
    valid = final_protocol is not None
    if valid:
        (out_dir / "protocol.scr").write_text(final_protocol, encoding="utf-8")
    _emit("drafted", valid=valid, attempts=len(attempts))

    faith_dict = None
    if valid:
        protocol_only, _refn = split_guard_sidecar(final_protocol)
        report = evaluate_faithfulness(llm, distilled, protocol_only,
                                       bisim_fn=bisim_fn)
        faith_dict = report.to_dict()
        (out_dir / "faithfulness.json").write_text(
            json.dumps(faith_dict, ensure_ascii=False, indent=2),
            encoding="utf-8")
        _emit("evaluated", faithful=report.faithful, recall=report.recall)

    meter = getattr(llm, "meter", None)
    meter_dict = meter.to_dict() if isinstance(meter, Meter) else {}
    meter_dict.update({"validator": validator_label,
                       "refined_from": parent_dir.name})
    record = LoopRecord(
        episode_id=parent_record.get("episode_id", "refine"),
        intent_sha256=parent_record.get("intent_sha256", ""),
        intent_chars=parent_record.get("intent_chars", 0),
        distilled=distilled.to_dict(),
        transcript=parent_record.get("transcript", []),
        draft_attempts=attempts, final_protocol=final_protocol, valid=valid,
        faithfulness=faith_dict, meter=meter_dict, ts=_now())
    append_record(record, corpus_path)
    (out_dir / "record.json").write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8")
    _emit("done", valid=valid,
          faithful=bool((faith_dict or {}).get("faithful")),
          out_dir=str(out_dir))
    return record
