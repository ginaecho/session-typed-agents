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
from experiments.intent_loop.schema import LoopRecord
from experiments.intent_loop.stakeholder import StakeholderSim
from experiments.seam_bench.t0.drafter import split_guard_sidecar
from experiments.seam_bench.t0.repair_loop import (MAX_REPAIR_ROUNDS,
                                                   run_repair_chain)

ValidateFn = Callable[[str], tuple[bool, str]]


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
                                 hidden_notes=hidden_notes)
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
    rulebook = list(prompt_pack.rulebook) if prompt_pack else []
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
    _emit("drafted", valid=valid, attempts=len(attempts),
          repair_rounds=max(0, len(attempts) - 1))

    # ── 3. faithfulness (only a valid protocol can be faithful) ─────────
    faith_dict = None
    if valid:
        protocol_only, _refn = split_guard_sidecar(final_protocol)
        report = evaluate_faithfulness(
            eval_llm or llm, distilled, protocol_only,
            gold_protocol=gold_protocol, bisim_fn=bisim_fn)
        faith_dict = report.to_dict()
        (out_dir / "faithfulness.json").write_text(
            json.dumps(faith_dict, ensure_ascii=False, indent=2),
            encoding="utf-8")
        _emit("evaluated", faithful=report.faithful, recall=report.recall,
              backtranslation=report.backtranslation.get("score"),
              ungrounded=len(report.ungrounded))

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
