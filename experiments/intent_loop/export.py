"""export.py — turn loop episodes into fine-tuning datasets.

optimize.py trains the translator at the PROMPT level (few-shot exemplars +
a validator-error rulebook) with no weight updates. This module is the
escalation path: the same corpus, emitted as chat-format JSONL that Azure
OpenAI / OpenAI fine-tuning accepts directly, so no episode ever has to be
re-run to become training data.

Two datasets, because the production loop has two skills to learn:

  drafting  (distilled spec) -> a protocol that is BOTH Scribble-valid and
      faithful. Unfaithful protocols are excluded even when they validate:
      a valid-but-wrong protocol is precisely the failure this project
      exists to prevent, and training on it teaches the model to produce
      more of them.
  repair    (spec, broken draft, the validator's verbatim counterexample)
      -> the draft that validated next. Mined from consecutive attempts
      within one episode, so every pair is a real rejection the real
      checker produced, not a synthetic corruption.

Quality gates are explicit and reported (`stats`), never silent: a caller
always learns how many episodes were dropped and why. Splitting is by
INTENT hash, not by row, so two episodes on the same intent document can
never straddle train/validation — the classic leak that makes a fine-tune
look better than it is.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Iterator

from experiments.intent_loop.corpus import DEFAULT_CORPUS_PATH, read_corpus
from experiments.intent_loop.drafter_llm import (SCRIBBLE_PRIMER,
                                                 _rulebook_block,
                                                 _exemplars_block)
from experiments.intent_loop.schema import DistilledIntent, LoopRecord

# The training-time system prompts. Deliberately the ZERO-SHOT forms (no
# exemplars, no rulebook): a fine-tune should internalize what the prompt
# pack currently carries, so the served model needs a shorter prompt than
# the prompted baseline. Keep these in sync with drafter_llm.py's templates
# — a fine-tune trained against a stale system prompt underperforms at
# serve time for reasons that are invisible in the metrics.
DRAFT_SYSTEM = (
    "You translate a distilled task specification into ONE Scribble global "
    "protocol.\n\n" + SCRIBBLE_PRIMER + "\n\nHard rules:\n"
    "- Output ONLY the protocol text. No prose, no markdown fences.\n"
    "- Realize EVERY requirement in the checklist: orderings as message "
    "order, authorizations as an approval message BEFORE the act it "
    "authorizes, branches as `choice at <deciding role>`, termination as a "
    "final message that reaches whoever the completion signal names.\n"
    "- Use ONLY the listed roles. Invent clear CamelCase message labels.")

REPAIR_SYSTEM = (
    "You repair a Scribble global protocol that the real Scribble validator "
    "rejected. You will be given the task specification, the broken "
    "protocol, and the validator's verbatim error output. Fix the error "
    "while preserving the intended interaction. Output ONLY the corrected "
    "protocol text, no prose, no fences.\n\n" + SCRIBBLE_PRIMER)


def _spec_text(record: LoopRecord) -> str:
    """The drafter's actual input: the distilled spec, rendered exactly as
    the live loop renders it (protocol-scoped — policy requirements are not
    the drafter's job, so training on them would teach it to hallucinate
    structure for constraints a session type cannot express)."""
    return DistilledIntent.from_dict(record.distilled).to_markdown(
        include_policy=False)


def _chat(system: str, user: str, assistant: str) -> dict:
    return {"messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user},
                         {"role": "assistant", "content": assistant}]}


def drafting_examples(records: Iterable[LoopRecord]
                      ) -> Iterator[tuple[str, dict]]:
    """(intent_sha256, chat example) for every valid AND faithful episode."""
    for rec in records:
        if not rec.valid or not rec.final_protocol:
            continue
        if not (rec.faithfulness or {}).get("faithful"):
            continue
        user = (f"=== TASK SPECIFICATION ===\n{_spec_text(rec)}\n\n"
                f"Write the protocol.")
        yield rec.intent_sha256, _chat(DRAFT_SYSTEM, user,
                                       rec.final_protocol.strip())


def repair_examples(records: Iterable[LoopRecord]
                    ) -> Iterator[tuple[str, dict]]:
    """(intent_sha256, chat example) for each rejected->accepted attempt pair.

    Needs the attempt TEXTS, which the corpus row does not carry (it stores
    the verdict and size only). `attach_attempt_texts` fills them in from
    the session directories; episodes still missing them are skipped rather
    than guessed.
    """
    for rec in records:
        attempts = rec.draft_attempts or []
        spec = _spec_text(rec)
        for prev, nxt in zip(attempts, attempts[1:]):
            if prev.get("valid") or not nxt.get("valid"):
                continue
            broken, fixed = prev.get("text"), nxt.get("text")
            if not broken or not fixed:
                continue
            user = (f"=== TASK SPECIFICATION ===\n{spec}\n\n"
                    f"=== BROKEN PROTOCOL ===\n{broken}\n\n"
                    f"=== VALIDATOR ERROR (verbatim) ===\n"
                    f"{prev.get('validator_msg', '')}\n\n"
                    f"Output the corrected protocol.")
            yield rec.intent_sha256, _chat(REPAIR_SYSTEM, user, fixed.strip())


def attach_attempt_texts(records: Iterable[LoopRecord],
                         sessions_dir: Path) -> list[LoopRecord]:
    """Re-attach each attempt's protocol text from sessions/<dir>/drafts/.

    Matching is by episode_id, and a session whose record.json names a
    different episode is skipped — session directory names are chosen by
    the caller and are not a reliable key.
    """
    by_episode: dict[str, Path] = {}
    if sessions_dir.is_dir():
        for d in sessions_dir.iterdir():
            rec_path = d / "record.json"
            if not rec_path.exists():
                continue
            try:
                eid = json.loads(rec_path.read_text(encoding="utf-8")
                                 ).get("episode_id")
            except json.JSONDecodeError:
                continue
            if eid:
                by_episode.setdefault(eid, d)
    out = []
    for rec in records:
        d = by_episode.get(rec.episode_id)
        if d:
            for att in rec.draft_attempts or []:
                p = d / "drafts" / f"attempt_{att.get('k')}.scr"
                if p.exists():
                    att["text"] = p.read_text(encoding="utf-8")
        out.append(rec)
    return out


def _split_of(intent_sha: str, validation_fraction: float) -> str:
    """Deterministic split BY INTENT: every episode of one intent document
    lands on the same side, so a near-duplicate can never leak across."""
    if validation_fraction <= 0:
        return "train"
    bucket = int(hashlib.sha256(intent_sha.encode()).hexdigest()[:8], 16) % 100
    return "validation" if bucket < validation_fraction * 100 else "train"


def build_dataset(corpus_path: Path = DEFAULT_CORPUS_PATH, *,
                  sessions_dir: Path | None = None,
                  kinds: tuple[str, ...] = ("drafting", "repair"),
                  validation_fraction: float = 0.0) -> dict:
    """Return {"train": [...], "validation": [...], "stats": {...}}."""
    records = list(read_corpus(corpus_path))
    if sessions_dir is not None:
        records = attach_attempt_texts(records, sessions_dir)

    rows: list[tuple[str, dict, str]] = []
    if "drafting" in kinds:
        rows += [(sha, ex, "drafting")
                 for sha, ex in drafting_examples(records)]
    if "repair" in kinds:
        rows += [(sha, ex, "repair") for sha, ex in repair_examples(records)]

    train, validation = [], []
    for sha, ex, _kind in rows:
        (validation if _split_of(sha, validation_fraction) == "validation"
         else train).append(ex)

    n_valid = sum(1 for r in records if r.valid)
    n_faithful = sum(1 for r in records
                     if (r.faithfulness or {}).get("faithful"))
    return {
        "train": train, "validation": validation,
        "stats": {
            "episodes": len(records),
            "episodes_valid": n_valid,
            "episodes_faithful": n_faithful,
            "dropped_invalid": len(records) - n_valid,
            "dropped_valid_but_unfaithful": n_valid - n_faithful,
            "drafting_examples": sum(1 for _s, _e, k in rows
                                     if k == "drafting"),
            "repair_examples": sum(1 for _s, _e, k in rows if k == "repair"),
            "train": len(train), "validation": len(validation),
            "split_by": "intent sha256 (no cross-split intent leakage)",
            "note": "drafting examples require valid AND faithful episodes; "
                    "repair examples require a rejected attempt followed by "
                    "an accepted one, with both texts recoverable from the "
                    "session directory",
        },
    }


def to_jsonl(examples: list[dict]) -> str:
    return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in examples)


def write_dataset(dataset: dict, out_dir: Path) -> dict[str, str]:
    """Write train/validation JSONL + a stats sidecar; return the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for split in ("train", "validation"):
        if not dataset[split]:
            continue
        p = out_dir / f"{split}.jsonl"
        p.write_text(to_jsonl(dataset[split]), encoding="utf-8")
        written[split] = str(p)
    stats_path = out_dir / "stats.json"
    stats_path.write_text(json.dumps(dataset["stats"], indent=2),
                          encoding="utf-8")
    written["stats"] = str(stats_path)
    return written
