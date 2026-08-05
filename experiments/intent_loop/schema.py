"""schema.py — typed artifacts of the intent-interrogation loop.

The loop (BENCHMARK_PLAN_V3 §10.3 called this "the interrogation step" and
modeled it as a one-shot distillation; this app makes it a real multi-turn
Q&A) produces four artifact families, all defined here so every module and
the corpus JSONL agree on one shape:

  Requirement / DistilledIntent  what interrogation extracts. Requirements
      are ATOMIC and TYPED (ordering / authorization / value / branch /
      termination / role) because the faithfulness suite checks them one by
      one against the drafted protocol — a single prose blob cannot be
      checked item-wise, a typed checklist can.
  QA / InterrogationResult       the Q&A transcript (audit trail: which
      requirement came from the document vs. from an answer vs. remained
      an explicit assumption).
  FaithfulnessReport             per-requirement coverage + back-translation
      comparison + optional gold EFSM-equivalence, with the aggregate
      verdict rule stated in faithfulness.py.
  LoopRecord                     one corpus row = one full loop episode
      (intent -> dialogue -> distilled -> draft attempts -> final protocol
      -> faithfulness). This is the training corpus for both prompt
      optimization (optimize.py, no weight updates) and any later SFT run
      (SEAM_TRAINING_EXECUTION_PLAN.md).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

REQUIREMENT_KINDS = (
    "role",           # a participant and what it is responsible for
    "ordering",       # X must happen before Y
    "authorization",  # X may only happen after approval by R
    "value",          # a payload constraint (threshold, non-empty, enum)
    "branch",         # a decision point and who decides it
    "termination",    # how the session ends / who learns the outcome
    "other",
)


@dataclass
class Requirement:
    """One atomic, checkable requirement distilled from the intent."""
    rid: str                      # "R1", "R2", ...
    kind: str                     # one of REQUIREMENT_KINDS
    text: str                     # one sentence, plain language
    who: list[str] = field(default_factory=list)   # role names involved
    source: str = "document"      # "document" | "answer" | "assumption"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Requirement":
        kind = d.get("kind", "other")
        if kind not in REQUIREMENT_KINDS:
            kind = "other"
        return cls(rid=str(d["rid"]), kind=kind, text=str(d["text"]),
                   who=[str(w) for w in d.get("who", [])],
                   source=str(d.get("source", "document")))


@dataclass
class DistilledIntent:
    """The interrogation's structured output — the drafter's actual input."""
    mission: str
    roles: list[dict[str, str]]            # [{"name":..., "description":...}]
    requirements: list[Requirement]
    completion_signal: str
    open_questions: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def role_names(self) -> list[str]:
        return [r["name"] for r in self.roles]

    def requirements_text(self) -> str:
        return "\n".join(
            f"- [{r.rid}][{r.kind}] {r.text}"
            + (f" (roles: {', '.join(r.who)})" if r.who else "")
            for r in self.requirements)

    def to_markdown(self) -> str:
        lines = ["# Distilled intent", "", "## Mission", self.mission, "",
                 "## Roles"]
        lines += [f"- **{r['name']}** — {r.get('description', '')}"
                  for r in self.roles]
        lines += ["", "## Requirements", self.requirements_text(),
                  "", "## Completion signal", self.completion_signal]
        if self.open_questions:
            lines += ["", "## Open questions (explicitly unresolved)"]
            lines += [f"- {q}" for q in self.open_questions]
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["requirements"] = [r.to_dict() for r in self.requirements]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DistilledIntent":
        return cls(
            mission=str(d["mission"]),
            roles=[{"name": str(r["name"]),
                    "description": str(r.get("description", ""))}
                   for r in d.get("roles", [])],
            requirements=[Requirement.from_dict(r)
                          for r in d.get("requirements", [])],
            completion_signal=str(d.get("completion_signal", "")),
            open_questions=[str(q) for q in d.get("open_questions", [])],
            provenance=dict(d.get("provenance", {})))


@dataclass
class QA:
    round: int
    question: str
    answer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterrogationResult:
    distilled: DistilledIntent
    transcript: list[QA]
    rounds_used: int
    forced_finish: bool           # True = hit max_rounds, distillation forced
    meter: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"distilled": self.distilled.to_dict(),
                "transcript": [qa.to_dict() for qa in self.transcript],
                "rounds_used": self.rounds_used,
                "forced_finish": self.forced_finish,
                "meter": self.meter}


@dataclass
class CoverageVerdict:
    rid: str
    covered: str                  # "yes" | "partial" | "no"
    evidence: str                 # protocol lines / reasoning cited

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FaithfulnessReport:
    coverage: list[CoverageVerdict]
    recall: float                 # fraction of requirements covered "yes"
    ungrounded: list[str]         # protocol interactions no requirement grounds
    backtranslation: dict[str, Any]   # {"score": 0-100, "reconstructed": str,
                                      #  "missing": [...], "added": [...]}
    gold_equivalent: Optional[bool]   # E5 verdict when a gold protocol exists
    faithful: bool
    rule: str                     # human-readable statement of the verdict rule

    def to_dict(self) -> dict[str, Any]:
        return {"coverage": [c.to_dict() for c in self.coverage],
                "recall": self.recall, "ungrounded": self.ungrounded,
                "backtranslation": self.backtranslation,
                "gold_equivalent": self.gold_equivalent,
                "faithful": self.faithful, "rule": self.rule}


@dataclass
class LoopRecord:
    """One corpus row — everything one loop episode produced."""
    episode_id: str
    intent_sha256: str
    intent_chars: int
    distilled: dict[str, Any]
    transcript: list[dict[str, Any]]
    draft_attempts: list[dict[str, Any]]   # [{"k":1,"valid":bool,"validator_msg":str,"chars":int}]
    final_protocol: Optional[str]          # validated text, or None if never valid
    valid: bool
    faithfulness: Optional[dict[str, Any]]
    meter: dict[str, Any]
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LoopRecord":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


# ── JSON extraction (models wrap JSON in prose/fences more often than not) ──

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_block(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM reply.

    Tries, in order: fenced ```json blocks, the first balanced {...} span.
    Raises ValueError with the offending text excerpt on failure — callers
    decide whether to retry the LLM call.
    """
    for candidate in _FENCE_RE.findall(text):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError(
        f"no parseable JSON object in LLM reply "
        f"(first 200 chars: {text[:200]!r})")
