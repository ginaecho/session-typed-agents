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


def build_chat(meter: Optional["Meter"] = None, role: str = "learner"):
    """The one place the app asks for a model.

    Two roles, deliberately different models:

      learner  the model under training — reads the intent, asks the
               questions, drafts the Scribble, and is the one whose
               improvement we are actually after.
      expert   a STRONGER model standing in for the human stakeholder when
               no human is in the room. It answers the learner's questions
               about roles, interactions and goals. Using the same model
               for both would be the learner asking itself, which teaches
               it nothing it did not already believe.
    """
    from experiments.intent_loop import settings as settings_mod
    s = settings_mod.load()
    if not s.is_usable():
        return FoundryChat(meter=meter)
    if role == "expert" and s.expert_model:
        s = settings_mod.Settings(**{**s.to_dict(), "model": s.expert_model})
    return ApiChat(s, meter=meter)


#: Completion budget per call. Reasoning models (gpt-5 family, o-series)
#: count REASONING tokens against this same budget, so a budget sized for
#: the visible answer alone comes back empty — the model spent it all
#: thinking. Every stage here (distillation, drafting, coverage auditing)
#: is reasoning-heavy over a long input, so the default is generous.
DEFAULT_MAX_TOKENS = 16384


class EmptyReplyError(RuntimeError):
    """The model returned no visible text — on reasoning models this means
    the completion budget was exhausted by reasoning tokens."""


class ApiChat:
    """Talks to whatever the user configured — Azure OpenAI or any
    OpenAI-compatible endpoint — so the app works for anyone with an API
    rather than only inside the author's tenant.

    Two provider quirks are handled here rather than pushed onto the user:

    * `max_tokens` vs `max_completion_tokens`. Reasoning models reject the
      first, older deployments reject the second. Rather than keep a
      model-name table that goes stale every release, learn the accepted
      name from the service on the first 400 and remember it.
    * Empty visible replies. Reasoning models charge REASONING tokens
      against the same budget, so a budget sized for the answer alone comes
      back blank. Retry once at double, then fail loudly — an empty string
      otherwise surfaces as unparseable JSON three frames away.
    """

    def __init__(self, settings=None, meter: Optional[Meter] = None):
        from experiments.intent_loop import settings as settings_mod
        s = settings or settings_mod.load()
        if not s.is_usable():
            raise RuntimeError(
                "No LLM configured. Set an endpoint and model in the app's "
                "Settings (or POST /api/settings).")
        self.settings = s
        self.meter = meter if meter is not None else Meter()
        self.max_tokens = s.max_tokens
        self.label = f"{s.provider}:{s.model}"
        self._token_param = "max_tokens"
        self._client = self._build(s)

    @staticmethod
    def _build(s):
        if s.provider == "azure":
            from openai import AzureOpenAI
            if s.api_key:
                return AzureOpenAI(azure_endpoint=s.endpoint,
                                   api_key=s.api_key,
                                   api_version=s.api_version)
            # Keyless path: the Azure AD identity from `az login`. Uses the
            # repo's own credential shim, which works around azure-identity
            # failing to find az.cmd on Windows.
            from stjp_core.foundry.az_credential import make_token_provider
            return AzureOpenAI(
                azure_endpoint=s.endpoint,
                azure_ad_token_provider=make_token_provider(
                    "https://cognitiveservices.azure.com/.default"),
                api_version=s.api_version)
        from openai import OpenAI
        return OpenAI(api_key=s.api_key or "unused",
                      base_url=s.endpoint or None)

    def _create(self, messages: list[dict], max_tokens: int):
        try:
            return self._client.chat.completions.create(
                model=self.settings.model, messages=messages,
                **{self._token_param: max_tokens})
        except Exception as e:
            other = ("max_completion_tokens"
                     if self._token_param == "max_tokens" else "max_tokens")
            if other not in str(e):
                raise
            self._token_param = other
            return self._client.chat.completions.create(
                model=self.settings.model, messages=messages,
                **{self._token_param: max_tokens})

    def _call(self, messages: list[dict], stage: str,
              prompt_chars: int) -> str:
        for budget in (self.max_tokens, self.max_tokens * 2):
            reply = (self._create(messages, budget)
                     .choices[0].message.content) or ""
            if reply.strip():
                self.meter.add(stage, prompt_chars, len(reply))
                return reply
        raise EmptyReplyError(
            f"stage={stage}: {self.label} returned no visible text even at "
            f"{self.max_tokens * 2} completion tokens — on a reasoning model "
            f"that means reasoning consumed the whole budget. Raise "
            f"max_tokens in Settings, or shorten the input.")

    def complete(self, system: str, user: str, *, stage: str = "misc") -> str:
        return self._call([{"role": "system", "content": system},
                           {"role": "user", "content": user}],
                          stage, len(system) + len(user))

    def complete_with_history(self, system: str,
                              messages: list[dict[str, str]], *,
                              stage: str = "misc") -> str:
        chars = len(system) + sum(len(m["content"]) for m in messages)
        return self._call([{"role": "system", "content": system}] + messages,
                          stage, chars)


class FoundryChat:
    """Foundry-first adapter (lazy import: constructing one is the moment
    Azure config becomes required, never module import).

    Retries once with a doubled budget when a call comes back empty, then
    fails loudly: a silent empty reply becomes an unparseable-JSON error
    three frames away otherwise, which is a miserable thing to debug.
    """

    def __init__(self, meter: Optional[Meter] = None,
                 deployment: Optional[str] = None,
                 max_tokens: int = DEFAULT_MAX_TOKENS):
        from stjp_core.foundry.llm_client import LLMClient
        self._client = LLMClient(deployment) if deployment else LLMClient()
        self.meter = meter if meter is not None else Meter()
        self.max_tokens = max_tokens
        self.label = f"foundry:{deployment or 'default'}"

    def _guarded(self, call, stage: str, prompt_chars: int) -> str:
        reply = call(self.max_tokens) or ""
        if not reply.strip():
            reply = call(self.max_tokens * 2) or ""
        if not reply.strip():
            raise EmptyReplyError(
                f"stage={stage}: model returned no visible text even at "
                f"{self.max_tokens * 2} completion tokens — on a reasoning "
                f"model this means reasoning consumed the whole budget. "
                f"Raise FoundryChat(max_tokens=...) or shorten the input.")
        self.meter.add(stage, prompt_chars, len(reply))
        return reply

    def complete(self, system: str, user: str, *, stage: str = "misc") -> str:
        return self._guarded(
            lambda mt: self._client.generate(system, user, max_tokens=mt),
            stage, len(system) + len(user))

    def complete_with_history(self, system: str,
                              messages: list[dict[str, str]], *,
                              stage: str = "misc") -> str:
        chars = len(system) + sum(len(m["content"]) for m in messages)
        return self._guarded(
            lambda mt: self._client.generate_with_history(system, messages,
                                                          max_tokens=mt),
            stage, chars)


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
