"""optimize.py — prompt-level training: the no-weight-update learning loop.

The user's question "can we just use the prompt to fine-tune this LLM
instead of really tuning the model itself?" — this module is the yes. Two
prompt-level mechanisms, both mined from the corpus the loop logs itself,
both pure data (auditable, versioned, transferable across models, zero GPU
cost):

  Few-shot exemplars   (intent, protocol) pairs from episodes that were
      BOTH Scribble-valid AND faithful, retrieved per-intent by BM25
      (reusing t0/exemplars.ExemplarIndex — the seam plan's S1 "+few-shot
      retrieval" system, now fed by live episodes instead of a static
      gold set).
  Rulebook             validator counterexamples grouped into error
      families; each recurring family becomes one standing lesson line in
      the drafter's system prompt. A failure the validator caught twice
      should never need catching a third time — that is the learning.

A PromptPack bundles both plus its build provenance. Packs are compared
the only honest way: run the same eval set with pack A vs pack B and
diff validity-first-try / repair-rounds / faithfulness rates (the corpus
records everything needed). When prompt-level gains plateau, the SAME
corpus is the SFT dataset — weight tuning is the escalation path
(SEAM_TRAINING_EXECUTION_PLAN.md), not the starting point.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from experiments.intent_loop.corpus import DEFAULT_CORPUS_PATH, read_corpus
from experiments.intent_loop.schema import LoopRecord
from experiments.seam_bench.t0.exemplars import (ExemplarCandidate,
                                                 ExemplarIndex)

# ── validator-error families -> lesson lines ────────────────────────────────
# Keyed by a regex over the validator's message; extend as new families
# appear in the corpus (harvest_rulebook prints unmatched families so they
# are visible, not silently generic).

KNOWN_ERROR_LESSONS: list[tuple[str, str]] = [
    (r"(?i)syntax|parse|mismatched|token recognition|extraneous input",
     "Emit strictly the grammar in the primer: every message is "
     "`Label(sort) from RoleA to RoleB;`, braces balanced, one statement "
     "per line, no comments the validator may not accept."),
    (r"(?i)unknown role|undeclared|not declared",
     "Declare every role in the protocol header and use exactly those "
     "spellings in every message line."),
    (r"(?i)unguarded|guardedness|continue",
     "Inside `rec X { ... }`, at least one message must occur before any "
     "`continue X;` (recursion must be guarded)."),
    # The single most common REAL rejection observed against scribble-java
    # on live drafts: "Source role not enabled: X" / "Subject not enabled:
    # X". It is the classic MPST projection failure — X acts inside a
    # branch it was never told about — and it is exactly the deadlock this
    # whole pipeline exists to prevent, so the lesson is stated in the
    # validator's own words to make it recognisable next time.
    (r"(?i)not enabled|enabling|unenabled",
     "\"Source/Subject role not enabled: X\" means X sends or is required "
     "to act inside a `choice` branch without having been told the "
     "decision. Fix: as the FIRST statement of every branch, have the "
     "deciding role send a distinct notification message to every role "
     "that acts later in that branch — including roles that only act in "
     "one branch."),
    (r"(?i)disambiguate name",
     "\"Cannot disambiguate name: x\" means the payload sort was never "
     "declared. Declare every sort in the preamble (`data <java> "
     "\"java.lang.String\" from \"rt.jar\" as String;`) and use the "
     "CAPITALISED declared name in messages."),
    (r"(?i)MODULE_KW|missing module",
     "The file must begin with `module <Name>;` before any data "
     "declaration or protocol."),
    (r"(?i)merge|project|mergeable|branch",
     "After a `choice at R`, every role whose later behavior differs by "
     "branch must RECEIVE a message inside each branch telling it which "
     "branch was taken, before it has to act."),
    (r"(?i)deadlock|wait-for|stuck|liveness",
     "Check that no role waits for a message that the sender can never "
     "reach on some branch — every send must be reachable on the branch "
     "that needs it."),
    (r"(?i)unreachable|dead code",
     "Remove interactions that can never execute; every declared message "
     "must be reachable from the protocol start."),
]

_GENERIC_LESSON = ("A previous draft was rejected with: \"{excerpt}\" - "
                   "avoid re-creating that condition.")


def _error_family(msg: str) -> str:
    """Normalize a validator message to a family key: first non-empty line,
    stripped of positions/identifiers, lowercased."""
    first = next((ln for ln in msg.splitlines() if ln.strip()), "")
    first = re.sub(r"\d+", "N", first)
    first = re.sub(r"[A-Za-z_]\w*\.scr", "FILE", first)
    return first.strip().lower()[:160]


def harvest_rulebook(records: Iterable[LoopRecord], *,
                     min_count: int = 1, max_lessons: int = 8) -> list[str]:
    """Validator counterexamples -> deduped lesson lines, most frequent
    families first. Known families map to curated lessons; unknown ones get
    the generic quoted-excerpt lesson (still useful — the model sees the
    real error text)."""
    families: dict[str, tuple[int, str]] = {}
    for rec in records:
        for att in rec.draft_attempts:
            if att.get("valid"):
                continue
            msg = str(att.get("validator_msg", "")).strip()
            if not msg:
                continue
            fam = _error_family(msg)
            count, _ = families.get(fam, (0, msg))
            families[fam] = (count + 1, msg)

    lessons: list[str] = []
    seen: set[str] = set()
    for fam, (count, msg) in sorted(families.items(),
                                    key=lambda kv: -kv[1][0]):
        if count < min_count:
            continue
        lesson = next((text for pat, text in KNOWN_ERROR_LESSONS
                       if re.search(pat, msg)), None)
        if lesson is None:
            lesson = _GENERIC_LESSON.format(excerpt=fam[:120])
        if lesson not in seen:
            seen.add(lesson)
            lessons.append(lesson)
        if len(lessons) >= max_lessons:
            break
    return lessons


def mine_exemplars(records: Iterable[LoopRecord], *,
                   require_faithful: bool = True) -> list[ExemplarCandidate]:
    """Episodes -> few-shot candidates. Valid-only always; faithful-only by
    default (see corpus.py module docstring for why)."""
    out: list[ExemplarCandidate] = []
    for rec in records:
        if not rec.valid or not rec.final_protocol:
            continue
        if require_faithful and not (rec.faithfulness or {}).get("faithful"):
            continue
        distilled_md = rec.distilled.get("mission", "")
        reqs = rec.distilled.get("requirements", [])
        intent_text = distilled_md + "\n" + "\n".join(
            f"- {r.get('text', '')}" for r in reqs)
        out.append(ExemplarCandidate(item_id=rec.episode_id,
                                     intent=intent_text.strip(),
                                     protocol=rec.final_protocol))
    return out


@dataclass
class PromptPack:
    """A versioned bundle of prompt-level learning. Swap packs to change
    drafting behavior; never edit one in place (comparability)."""
    version: str
    rulebook: list[str]
    exemplars: list[ExemplarCandidate]
    built_from: dict = field(default_factory=dict)

    def select_exemplars(self, intent: str, k: int = 3
                         ) -> list[tuple[str, str]]:
        if not self.exemplars or k <= 0:
            return []
        index = ExemplarIndex(self.exemplars)
        ranked = index.top_k(intent, k)
        return [(c.intent, c.protocol) for c in ranked]

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": self.version, "rulebook": self.rulebook,
                   "exemplars": [{"item_id": c.item_id, "intent": c.intent,
                                  "protocol": c.protocol}
                                 for c in self.exemplars],
                   "built_from": self.built_from}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "PromptPack":
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(version=d["version"], rulebook=list(d["rulebook"]),
                   exemplars=[ExemplarCandidate(**e) for e in d["exemplars"]],
                   built_from=dict(d.get("built_from", {})))


def build_prompt_pack(corpus_path: Path = DEFAULT_CORPUS_PATH, *,
                      version: str = "v1",
                      require_faithful: bool = True,
                      max_lessons: int = 8) -> PromptPack:
    records = list(read_corpus(corpus_path))
    exemplars = mine_exemplars(records, require_faithful=require_faithful)
    rulebook = harvest_rulebook(records, max_lessons=max_lessons)
    episodes_valid = sum(1 for r in records if r.valid)
    return PromptPack(
        version=version, rulebook=rulebook, exemplars=exemplars,
        built_from={"corpus": str(corpus_path),
                    "episodes": len(records),
                    "episodes_valid": episodes_valid,
                    "exemplars": len(exemplars),
                    "require_faithful": require_faithful})
