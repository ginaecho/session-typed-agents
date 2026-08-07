"""corpus.py — the loop's training corpus (append-only JSONL).

Every loop episode — succeed or fail — appends one LoopRecord: the intent,
the full Q&A transcript, the distilled checklist, EVERY draft attempt with
its validator verdict, the final protocol, and the faithfulness report.
Failures are kept on purpose: rejected drafts + validator counterexamples
are exactly the (broken, error, fixed) triples that D3-style repair
training and optimize.py's rulebook need; only exemplar mining filters to
the clean successes.

Two consumers today:
  optimize.mine_exemplars   -> (intent, protocol) pairs for few-shot
      retrieval — only episodes that were BOTH valid and faithful (a valid
      but unfaithful protocol as an exemplar would teach the drafter the
      exact failure mode this app exists to prevent).
  optimize.harvest_rulebook -> validator-error families -> lesson lines.

Later consumer: SFT data generation (SEAM_TRAINING_EXECUTION_PLAN.md) —
the record deliberately keeps everything that plan's D1/D2/D3 datasets
would need, so no episode has to be re-run to become training data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from experiments.intent_loop.schema import LoopRecord

DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "corpus" / "loop_corpus.jsonl"


def append_record(record: LoopRecord, path: Path = DEFAULT_CORPUS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return path


def read_corpus(path: Path = DEFAULT_CORPUS_PATH) -> Iterator[LoopRecord]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield LoopRecord.from_dict(json.loads(line))
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                raise ValueError(f"{path}:{line_no}: bad corpus row: {e}") from e
