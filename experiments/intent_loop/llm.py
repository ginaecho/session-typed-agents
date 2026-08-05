"""llm.py — the one LLM seam of the intent loop, plus metering.

Transport policy (stjp_core/CLAUDE.md "Foundry-first"): real calls route
through `stjp_core.foundry.llm_client.LLMClient`, so every interrogation
turn, draft, repair, and faithfulness check is visible in the Foundry portal
under Agents -> stjp-utility -> Threads. `FoundryChat` is a thin adapter;
`MockChat` is the deterministic offline stand-in every test and the
`--mock` CLI path use (same convention as seam_bench's MockIntentClient /
MockDrafter — nothing in tests touches the network).

Metering follows intent_pipeline.py's disclosure convention: the Foundry
utility path exposes no usage counts, so tokens are approximated as
chars/4 and every artifact that quotes them says "approx". The Meter is
passed around explicitly (no globals) and lands in provenance / corpus
rows so the loop's own setup cost is a disclosed line item, mirroring the
protocol-drafting cost disclosure in BENCHMARK_PLAN_V3 §10.3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class Meter:
    calls: int = 0
    approx_tokens_in: int = 0
    approx_tokens_out: int = 0
    by_stage: dict[str, int] = field(default_factory=dict)

    def add(self, stage: str, prompt_chars: int, reply_chars: int) -> None:
        self.calls += 1
        self.approx_tokens_in += max(1, prompt_chars // 4)
        self.approx_tokens_out += max(1, reply_chars // 4)
        self.by_stage[stage] = self.by_stage.get(stage, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {"calls": self.calls,
                "approx_tokens_in": self.approx_tokens_in,
                "approx_tokens_out": self.approx_tokens_out,
                "by_stage": dict(self.by_stage),
                "note": "tokens are chars/4 approximations (Foundry utility "
                        "path exposes no usage counts)"}


class ChatLLM(Protocol):
    """What every component of the loop needs from a model. Both methods
    return the assistant's text reply."""

    def complete(self, system: str, user: str, *, stage: str = "misc") -> str:
        ...

    def complete_with_history(self, system: str,
                              messages: list[dict[str, str]], *,
                              stage: str = "misc") -> str:
        ...


class FoundryChat:
    """Foundry-first adapter (lazy import: constructing one is the moment
    Azure config becomes required, never module import)."""

    def __init__(self, meter: Optional[Meter] = None,
                 deployment: Optional[str] = None):
        from stjp_core.foundry.llm_client import LLMClient
        self._client = LLMClient(deployment) if deployment else LLMClient()
        self.meter = meter if meter is not None else Meter()
        self.label = f"foundry:{deployment or 'default'}"

    def complete(self, system: str, user: str, *, stage: str = "misc") -> str:
        reply = self._client.generate(system, user)
        self.meter.add(stage, len(system) + len(user), len(reply))
        return reply

    def complete_with_history(self, system: str,
                              messages: list[dict[str, str]], *,
                              stage: str = "misc") -> str:
        reply = self._client.generate_with_history(system, messages)
        chars = len(system) + sum(len(m["content"]) for m in messages)
        self.meter.add(stage, chars, len(reply))
        return reply


class MockChat:
    """Deterministic, network-free ChatLLM for tests and `--mock` runs.

    `script` is a list of replies handed out in call order, or a callable
    `(system, last_user_content) -> str` for content-dependent stubs. Every
    call is recorded in `self.calls` as (stage, system, user) so tests can
    assert structural properties — e.g. that the back-translator was never
    shown the intent (the J-back isolation property, judge/classes.py).
    """

    def __init__(self,
                 script: "list[str] | Callable[[str, str], str] | None" = None,
                 meter: Optional[Meter] = None, label: str = "mock"):
        self._script = script
        self._i = 0
        self.calls: list[tuple[str, str, str]] = []
        self.meter = meter if meter is not None else Meter()
        self.label = label

    def _next(self, system: str, user: str) -> str:
        if callable(self._script):
            return self._script(system, user)
        if self._script:
            reply = self._script[self._i % len(self._script)]
            self._i += 1
            return reply
        return "{}"

    def complete(self, system: str, user: str, *, stage: str = "misc") -> str:
        self.calls.append((stage, system, user))
        reply = self._next(system, user)
        self.meter.add(stage, len(system) + len(user), len(reply))
        return reply

    def complete_with_history(self, system: str,
                              messages: list[dict[str, str]], *,
                              stage: str = "misc") -> str:
        last_user = next((m["content"] for m in reversed(messages)
                          if m["role"] == "user"), "")
        self.calls.append((stage, system, last_user))
        reply = self._next(system, last_user)
        chars = len(system) + sum(len(m["content"]) for m in messages)
        self.meter.add(stage, chars, len(reply))
        return reply
