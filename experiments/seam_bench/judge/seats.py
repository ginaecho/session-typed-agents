"""Judge seats — plan v2.1 §5.1, §5.3, §5.4.

A seat is data, not code: model id, temperature, rubric emphasis, and a
class tag. A verdict is exactly one stateless SDK call — fresh context, no
tools, no session id, bounded ``max_tokens``, JSON-schema-forced output.
There is no judge "agent" object that could accumulate state between
calls; the ``anthropic.Anthropic`` client is injected by the caller so
tests can substitute a mock and assert on call counts/args.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


JudgeClass = Literal["fwd", "back", "probe"]
Vote = Literal["yes", "no", "abstain"]
EvidenceSource = Literal["intent", "protocol"]

# The owner (SEAM_TRAINING_EXECUTION_PLAN.md §5.3 v2.1) wants an Opus 4.6
# id slotted into the second J-back seat once its exact API model id is
# confirmed. Until then this defaults to Opus 4.8 and is config-swappable
# via env var so the swap is a one-line change, not a code change.
BACK2_MODEL_ID = os.environ.get("STJP_JUDGE_BACK2_MODEL_ID", "claude-opus-4-8")


@dataclass(frozen=True)
class SeatConfig:
    """One panel seat. Pure data — no behavior lives here."""

    seat_id: str
    class_: JudgeClass
    model_id: str
    temperature: float
    rubric_emphasis: str  # "roles" | "ordering" | "prohibitions" | "termination"
    weight: float = 1.0
    max_tokens: int = 1024
    paraphrase_slot: int = 0
    resample_temperature: float | None = None

    def resample_temp(self) -> float:
        if self.resample_temperature is not None:
            return self.resample_temperature
        # {0.3, 0.7} is the plan's temperature pool — resample at the other one.
        return 0.7 if self.temperature <= 0.5 else 0.3


def default_panel() -> list[SeatConfig]:
    """The default panel per §5.3 v2.1:

    2xJ-fwd (Opus 4.8 + Sonnet 5, distinct paraphrase slots) +
    2xJ-back (Sonnet 5 + a config-swappable seat, default Opus 4.8) +
    J-probe (deterministic, no model).
    """
    return [
        SeatConfig(
            seat_id="fwd-opus",
            class_="fwd",
            model_id="claude-opus-4-8",
            temperature=0.3,
            rubric_emphasis="roles",
            paraphrase_slot=0,
        ),
        SeatConfig(
            seat_id="fwd-sonnet",
            class_="fwd",
            model_id="claude-sonnet-5",
            temperature=0.7,
            rubric_emphasis="ordering",
            paraphrase_slot=1,
        ),
        SeatConfig(
            seat_id="back-sonnet",
            class_="back",
            model_id="claude-sonnet-5",
            temperature=0.3,
            rubric_emphasis="prohibitions",
        ),
        SeatConfig(
            seat_id="back-swappable",
            class_="back",
            model_id=BACK2_MODEL_ID,
            temperature=0.7,
            rubric_emphasis="termination",
        ),
        SeatConfig(
            seat_id="probe",
            class_="probe",
            model_id="",  # deterministic — no sampled model backs the verdict
            temperature=0.0,
            rubric_emphasis="reachability",
            weight=1.0,
        ),
    ]


VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "vote": {"type": "string", "enum": ["yes", "no", "abstain"]},
        "confidence": {"type": "number"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "source": {"type": "string", "enum": ["intent", "protocol"]},
                },
                "required": ["quote", "source"],
                "additionalProperties": False,
            },
        },
        "missing": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["vote", "confidence", "evidence", "missing"],
    "additionalProperties": False,
}


@dataclass
class Evidence:
    quote: str
    source: EvidenceSource


@dataclass
class Verdict:
    """Schema per §5.4: {vote, confidence, evidence: [{quote, source}], missing}."""

    vote: Vote
    confidence: float
    evidence: list[Evidence]
    missing: list[str]
    seat_id: str
    class_: JudgeClass
    model_id: str
    temperature: float
    weight: float = 1.0
    discarded: bool = False
    discard_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "vote": self.vote,
            "confidence": self.confidence,
            "evidence": [{"quote": e.quote, "source": e.source} for e in self.evidence],
            "missing": list(self.missing),
            "seat_id": self.seat_id,
            "class": self.class_,
            "model_id": self.model_id,
            "temperature": self.temperature,
            "weight": self.weight,
            "discarded": self.discarded,
            "discard_reason": self.discard_reason,
        }


class AnthropicLike(Protocol):
    """Structural type for the injected client — the real
    ``anthropic.Anthropic`` satisfies this; tests pass a mock."""

    messages: Any


def _extract_text(response: Any) -> str:
    """Pull the text out of a Messages API response — real SDK objects and
    simple test doubles (``SimpleNamespace(content=[SimpleNamespace(type="text", text=...)])``)
    both satisfy this."""
    for block in response.content:
        block_type = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if block_type == "text":
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            return text
    raise ValueError("no text block in response content")


def call_structured(
    client: AnthropicLike,
    model_id: str,
    temperature: float,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """One stateless, schema-forced call. No tools, no session, fresh
    context every time — the entire "process isolation" guarantee of
    §5.1 lives in the fact that this function has no persistent state and
    every call is independently constructible from its arguments."""
    response = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    text = _extract_text(response)
    return json.loads(text)


def call_text(
    client: AnthropicLike,
    model_id: str,
    temperature: float,
    system: str,
    user: str,
    max_tokens: int = 1024,
) -> str:
    """One stateless free-text call (paraphrase generation, blind
    back-translation, probe-query compilation prose)."""
    response = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return _extract_text(response)


def verdict_from_raw(data: dict[str, Any], seat: SeatConfig) -> Verdict:
    vote = data["vote"]
    confidence = max(0.0, min(1.0, float(data["confidence"])))
    evidence = [Evidence(quote=e["quote"], source=e["source"]) for e in data.get("evidence", [])]
    missing = list(data.get("missing", []))
    return Verdict(
        vote=vote,
        confidence=confidence,
        evidence=evidence,
        missing=missing,
        seat_id=seat.seat_id,
        class_=seat.class_,
        model_id=seat.model_id,
        temperature=seat.temperature,
        weight=seat.weight,
    )
