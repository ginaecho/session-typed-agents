"""loop.py — one full episode: interrogate -> draft/validate/repair ->
faithfulness -> corpus.

The episode is the unit of everything downstream: one corpus row, one
session directory of artifacts (every prompt-consuming input and every
verdict persisted — the same audit-completeness bar the benchmark harness
holds runs to), and one data point for prompt-pack comparison.

Stage wiring:
  interrogation   interrogator.run_interrogation over StakeholderSim
  drafting        drafter_llm.ChatDrafter through the UNCHANGED t0
                  production loop (repair_loop.run_repair_chain: draft ->
                  real Scribble validate -> counterexample-guided repair,
                  <= max_repair_rounds)
  faithfulness    faithfulness.evaluate_faithfulness on the final valid
                  protocol (skipped when no attempt validated — validity
                  is a precondition of faithfulness, not a substitute)
  corpus          corpus.append_record, failures included
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
from experiments.intent_loop.interrogator import (DEFAULT_MAX_ROUNDS,
                                                  run_interrogation)
from experiments.intent_loop.llm import ChatLLM, Meter
from experiments.intent_loop.protocol_checks import check_protocol
from experiments.intent_loop.schema import LoopRecord
from experiments.intent_loop.stakeholder import StakeholderSim
from experiments.seam_bench.t0.drafter import split_guard_sidecar
from experiments.seam_bench.t0.repair_loop import (MAX_REPAIR_ROUNDS,
                                                   run_repair_chain)

ValidateFn = Callable[[str], tuple[bool, str]]


#: Lessons the learner carries between episodes — the persistent half of
#: "learn from the interactions". Within an episode ChatDrafter remembers
#: every rejection it has seen; this file is how that survives the episode,
#: so run N+1 begins already knowing what run N was taught.
LESSONS_PATH = Path(__file__).resolve().parent / "lessons.json"


def standing_lessons(path: Path = LESSONS_PATH) -> list[str]:
    try:
        return list(json.loads(path.read_text(encoding="utf-8"))["lessons"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []


def learn_from_attempts(attempts: list[dict], *,
                        path: Path = LESSONS_PATH,
                        max_lessons: int = 12) -> list[str]:
    """Fold this episode's REAL rejections into the standing lessons.

    Only the validator's own verdicts are used — never an inference about
    why a draft "probably" failed — so a lesson always traces to something
    the checker actually said. Deduplicated by error family, newest first,
    capped so the drafter's prompt cannot grow without bound.
    """
    from experiments.intent_loop.optimize import (KNOWN_ERROR_LESSONS,
                                                  _error_family)
    import re

    existing = standing_lessons(path)
    learned: list[str] = []
    for att in attempts:
        if att.get("valid"):
            continue
        msg = str(att.get("validator_msg", "")).strip()
        if not msg:
            continue
        lesson = next((text for pat, text in KNOWN_ERROR_LESSONS
                       if re.search(pat, msg)), None)
        if lesson is None:
            lesson = (f"A draft was rejected with: \"{_error_family(msg)}\" "
                      f"— avoid re-creating that condition.")
        if lesson not in learned:
            learned.append(lesson)

    merged = learned + [l for l in existing if l not in learned]
    merged = merged[:max_lessons]
    try:
        path.write_text(json.dumps({"lessons": merged,
                                    "updated": _utcnow()}, indent=2),
                        encoding="utf-8")
    except OSError:
        pass
    return merged


def _faithfulness_complaints(report, structural: dict) -> str:
    """Turn the grading into instructions the drafter can act on.

    Concrete and quotable: which requirement is missing, which message is
    invented, which label is an identifier. "Be more faithful" is not
    actionable; "R7 is not realized; PairWorker → Ledger is not a declared
    handover; I3Score is an identifier" is.
    """
    lines: list[str] = []
    missing = [c for c in report.coverage
               if c.covered in ("no", "partial")]
    if missing:
        lines.append("Requirements not realized:")
        lines += [f"  - {c.rid} ({c.covered}): {c.evidence[:200]}"
                  for c in missing[:12]]
    if report.ungrounded:
        lines.append("\nStructure no requirement justifies (remove it, or "
                     "it was a handover we failed to capture):")
        lines += [f"  - {u[:200]}" for u in report.ungrounded[:8]]
    bt = report.backtranslation or {}
    if bt.get("missing"):
        lines.append("\nLost when the protocol is read back on its own:")
        lines += [f"  - {m[:200]}" for m in bt["missing"][:6]]
    for f in structural.get("findings", []):
        if f.get("kind") in ("id-as-label", "meaningless-vocabulary",
                             "dropped-interaction", "ungrounded-message"):
            lines.append(f"  - [{f['kind']}] {f['where']}: "
                         f"{f['detail'][:180]}")
    return "\n".join(lines) or "The protocol does not express the intent."


def learn_from_faithfulness(faith: dict, *,
                            path: Path = None,
                            max_lessons: int = 12) -> list[str]:
    """Faithfulness failures become standing lessons too.

    Rejections by the type checker were already taught; a protocol that
    passes the checker and still misses the point is the harder lesson and
    the one the user actually cares about. Only observed failures produce
    lessons — never a general exhortation to "be faithful".
    """
    path = path or LESSONS_PATH
    learned: list[str] = []
    structural = (faith or {}).get("structural") or {}
    kinds = {f.get("kind") for f in structural.get("findings", [])}
    if "meaningless-vocabulary" in kinds or "id-as-label" in kinds:
        learned.append(
            "Message labels must name what the message CARRIES "
            "(PreflightVerdict, ApprovalGranted), never the interaction id "
            "(I1, I3Score). A protocol of identifiers type-checks and "
            "communicates nothing.")
    if "dropped-interaction" in kinds:
        learned.append(
            "Every declared interaction must appear as a message. Dropping "
            "one satisfies the checker and silently loses a requirement.")
    if (faith or {}).get("ungrounded") or "ungrounded-message" in kinds:
        learned.append(
            "Do not add messages that no requirement or declared "
            "interaction calls for — invented structure is as unfaithful "
            "as missing structure.")
    recall = (faith or {}).get("recall")
    if isinstance(recall, (int, float)) and recall < 0.5:
        learned.append(
            "Work through the requirement checklist item by item and make "
            "each one visible in the protocol as an ordering, an approval "
            "before the act it authorizes, a branch, or a terminating "
            "message — a protocol that realizes under half the checklist "
            "is not a translation of the intent.")
    if not learned:
        return standing_lessons(path)
    existing = standing_lessons(path)
    merged = (learned + [l for l in existing if l not in learned])[:max_lessons]
    try:
        path.write_text(json.dumps({"lessons": merged, "updated": _utcnow()},
                                   indent=2), encoding="utf-8")
    except OSError:
        pass
    return merged


def mock_validate(text: str) -> tuple[bool, str]:
    """Offline stand-in used ONLY when the caller explicitly opts in
    (--mock / tests). Checks the crudest structural facts so the repair
    path is exercisable without a JVM. Never a substitute for the real
    validator — outputs produced under it are labeled validator=mock."""
    if "global protocol" not in text:
        return False, "mock-validator: missing 'global protocol' header"
    if text.count("{") != text.count("}"):
        return False, "mock-validator: unbalanced braces"
    return True, ""


def real_validate() -> ValidateFn:
    from experiments.seam_bench.eval import validity
    return validity.validate


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_episode(
    llm: ChatLLM, document: str, *,
    out_dir: Path,
    hidden_notes: Optional[str] = None,
    stakeholder_llm: Optional[ChatLLM] = None,
    drafter_chat: Optional[ChatLLM] = None,
    eval_llm: Optional[ChatLLM] = None,
    prompt_pack=None,                      # optimize.PromptPack | None
    exemplar_k: int = 3,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    max_repair_rounds: int = MAX_REPAIR_ROUNDS,
    validate_fn: Optional[ValidateFn] = None,
    validator_label: str = "scribble-java",
    gold_protocol: Optional[str] = None,
    bisim_fn=None,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    episode_id: Optional[str] = None,
    progress: Optional[Callable[[str, dict], None]] = None,
    stakeholder_mode: str = "document",
    faithfulness_rounds: int = 3,
) -> LoopRecord:
    """Run one episode end-to-end and persist everything under out_dir.

    `progress(stage, detail)` is called at each stage boundary (stages:
    start, interrogated, drafted, evaluated, done) so a UI or an agent can
    follow a long episode instead of waiting blind on one call.
    """
    def _emit(stage: str, **detail) -> None:
        if progress is not None:
            progress(stage, detail)

    out_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(document.encode("utf-8")).hexdigest()
    episode_id = episode_id or f"ep-{sha[:10]}"
    validate = validate_fn if validate_fn is not None else real_validate()
    meter = getattr(llm, "meter", None) or Meter()

    (out_dir / "document.md").write_text(
        f"<!-- episode: {episode_id} | sha256: {sha} | "
        f"chars: {len(document)} -->\n" + document, encoding="utf-8")

    _emit("start", episode_id=episode_id, intent_chars=len(document),
          validator=validator_label)

    # ── 1. interrogation ────────────────────────────────────────────────
    # Sub-events are forwarded AND the transcript is flushed to disk after
    # every round, so a caller polling the session directory sees the Q&A
    # while the interrogation is still going. Interrogating a 20k-character
    # document is minutes of model time; without this it looks hung.
    def _interro_progress(stage: str, detail: dict) -> None:
        if stage == "answered" and detail.get("transcript"):
            (out_dir / "transcript.json").write_text(
                json.dumps({"transcript": detail["transcript"],
                            "in_progress": True}, ensure_ascii=False,
                           indent=2), encoding="utf-8")
        _emit(stage, **{k: v for k, v in detail.items() if k != "transcript"})

    stakeholder = StakeholderSim(stakeholder_llm or llm, document,
                                 hidden_notes=hidden_notes,
                                 mode=stakeholder_mode)
    interro = run_interrogation(llm, stakeholder, document,
                                max_rounds=max_rounds,
                                progress=_interro_progress)
    distilled = interro.distilled
    _emit("interrogated", rounds=interro.rounds_used,
          forced_finish=interro.forced_finish,
          roles=len(distilled.roles), goals=len(distilled.goals),
          interactions=len(distilled.interactions),
          requirements=len(distilled.requirements),
          from_answers=sum(1 for r in distilled.requirements
                           if r.source == "answer"),
          open_questions=len(distilled.open_questions))
    (out_dir / "transcript.json").write_text(
        json.dumps(interro.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (out_dir / "intent_distilled.md").write_text(distilled.to_markdown(),
                                                 encoding="utf-8")

    # ── 2. draft -> validate -> repair (t0 production loop, unchanged) ──
    # The rulebook is what the learner already knows: lessons harvested
    # from every REAL rejection in past episodes. Without an explicit pack
    # we still load the standing one, so each run starts where the last one
    # left off instead of re-learning the same syntax from scratch.
    rulebook = list(prompt_pack.rulebook) if prompt_pack else standing_lessons()
    drafter = ChatDrafter(drafter_chat or llm, rulebook=rulebook,
                          model_label=getattr(llm, "label", "chat"))
    spec_text = distilled.to_markdown()
    exemplars = (prompt_pack.select_exemplars(spec_text, exemplar_k)
                 if prompt_pack else None)
    initial = drafter.draft(spec_text, 1, exemplars=exemplars)[0]
    # split="train": loop episodes feed the training corpus (RunRecord's
    # schema admits only the seam splits; these records never enter a
    # held-out eval set).
    records = run_repair_chain(
        drafter, system="intent-loop", item_id=episode_id, split="train",
        intent=spec_text, initial_draft=initial,
        max_rounds=max_repair_rounds, validate_fn=validate,
        bisim_fn=(bisim_fn or (lambda a, b: (False, "no bisim_fn"))))

    drafts_dir = out_dir / "drafts"
    drafts_dir.mkdir(exist_ok=True)
    attempts = []
    final_protocol: Optional[str] = None
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
        (out_dir / "protocol.scr").write_text(final_protocol,
                                              encoding="utf-8")
    # Learn from THIS episode's rejections regardless of the outcome — a
    # run that never validated is the most instructive kind, which is the
    # whole reason a false verdict is a signal rather than a failure.
    lessons = learn_from_attempts(attempts)
    _emit("drafted", valid=valid, attempts=len(attempts),
          repair_rounds=max(0, len(attempts) - 1),
          lessons_known=len(lessons))

    # ── 3. faithfulness — and a second loop, because VALID IS A FLOOR ───
    # Scribble type-checks structure, not meaning: a protocol of `I1, I2,
    # I3` between the right roles is accepted and says nothing. So a
    # protocol that validates is graded, and if it does not express the
    # intent it is sent back to be revised and RE-VALIDATED. Convergence
    # here is two-dimensional; stopping at the checker's verdict is what
    # produced an accepted protocol nobody could read.
    faith_dict = None
    if valid:
        for round_no in range(faithfulness_rounds + 1):
            protocol_only, _refn = split_guard_sidecar(final_protocol)
            report = evaluate_faithfulness(
                eval_llm or llm, distilled, protocol_only,
                gold_protocol=gold_protocol, bisim_fn=bisim_fn)
            faith_dict = report.to_dict()
            structural = check_protocol(
                protocol_only,
                interactions=[i.to_dict() for i in distilled.interactions])
            faith_dict["structural"] = structural
            _emit("evaluated", round=round_no, faithful=report.faithful,
                  recall=report.recall,
                  backtranslation=report.backtranslation.get("score"),
                  ungrounded=len(report.ungrounded),
                  meaning_blockers=structural["blockers"])

            meaning_ok = report.faithful and structural["blockers"] == 0
            if meaning_ok or round_no >= faithfulness_rounds:
                break

            complaints = _faithfulness_complaints(report, structural)
            revised = drafter.refaithful(spec_text, final_protocol,
                                         complaints)
            rev_only, _r = split_guard_sidecar(revised)
            ok, msg = validate(rev_only)
            k = len(attempts) + 1
            (drafts_dir / f"attempt_{k}.scr").write_text(revised,
                                                          encoding="utf-8")
            (drafts_dir / f"attempt_{k}.verdict.txt").write_text(
                f"valid: {ok}\nvalidator: {validator_label}\n"
                f"(faithfulness revision {round_no + 1})\n\n{msg}",
                encoding="utf-8")
            attempts.append({"k": k, "valid": ok, "validator_msg": msg,
                             "chars": len(revised),
                             "faithfulness_revision": round_no + 1})
            if not ok:
                # The revision broke the structure. Keep the accepted one:
                # a valid-but-poor protocol beats an invalid one, and the
                # rejection is recorded so the next run learns from it.
                _emit("revision_rejected", round=round_no + 1,
                      validator_msg=msg[:200])
                break
            final_protocol = revised
            (out_dir / "protocol.scr").write_text(final_protocol,
                                                  encoding="utf-8")

        (out_dir / "faithfulness.json").write_text(
            json.dumps(faith_dict, ensure_ascii=False, indent=2),
            encoding="utf-8")
        learn_from_faithfulness(faith_dict)

    # ── 4. corpus row (failures included — see corpus.py) ───────────────
    meter_dict = meter.to_dict() if isinstance(meter, Meter) else {}
    meter_dict["validator"] = validator_label
    record = LoopRecord(
        episode_id=episode_id, intent_sha256=sha,
        intent_chars=len(document), distilled=distilled.to_dict(),
        transcript=[qa.to_dict() for qa in interro.transcript],
        draft_attempts=attempts, final_protocol=final_protocol,
        valid=valid, faithfulness=faith_dict, meter=meter_dict,
        ts=_utcnow())
    append_record(record, corpus_path)
    (out_dir / "record.json").write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8")
    _emit("done", valid=valid,
          faithful=bool((faith_dict or {}).get("faithful")),
          out_dir=str(out_dir))
    return record
