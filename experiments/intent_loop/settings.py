"""settings.py — bring your own LLM.

The app is useless to a colleague who cannot reach the author's Azure
resource, so the endpoint, key and model are configurable at runtime
instead of being baked into environment variables. Two providers cover
almost everything people actually have:

  azure   Azure OpenAI / AI Foundry: endpoint + deployment name. With an
          API key, or without one — an empty key falls back to the Azure
          AD credential from `az login`, which is how the author's own
          setup works and means no key is ever written to disk.
  openai  Any OpenAI-compatible endpoint (openai.com, vLLM, LiteLLM,
          Ollama's compat shim, a gateway): base URL + model name.

SECRET HANDLING, stated plainly because this is the part that can hurt.
The key is written to `.settings.json` beside this file, gitignored, in
plain text — the same trust level as the repo's own `.env`, and no better.
It is NEVER returned by the API: `masked()` is the only view any endpoint
serves, and it shows a fingerprint (last four characters) so you can tell
which key is loaded without disclosing it. The server binds to localhost
and has no authentication, so anyone who can reach it can spend the key —
do not expose it, and prefer the keyless Azure AD path where you can.

Resolution order is settings file → environment → built-in default, so an
existing environment-variable setup keeps working untouched and the file
only overrides what it actually sets.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
SETTINGS_PATH = HERE / ".settings.json"

#: The default model. gpt-5.4 is the frontier deployment in the benchmark
#: matrix; the cheaper gpt-5-mini is the one that could not clear the
#: projection errors on an 8-role protocol within the repair cap.
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_API_VERSION = "2024-12-01-preview"
PROVIDERS = ("azure", "openai")


#: The expert the learner interrogates when no human is in the room. A
#: STRONGER model than the learner on purpose: it stands in for the
#: stakeholder/architect, so the learner is questioning something that
#: knows more than it does — which is the whole point of asking.
DEFAULT_EXPERT_MODEL = "gpt-5.6-sol"

#: The JUDGE: reads the drafted protocol ALONE, writes down what it
#: thinks was asked for, and scores that against the real intent. It
#: must not be the model that drafted — a drafter reconstructs the
#: intent it had in mind, not the one a reader would take from the
#: text, which is marking your own homework.
DEFAULT_JUDGE_MODEL = "gpt-5.6-sol"

#: The deployment Microsoft's SimilarityEvaluator talks to. Separate from
#: `judge_model` because azure-ai-evaluation's internal client still sends
#: `max_tokens`, which every gpt-5/o-series deployment rejects outright
#: ("Unsupported parameter"). A non-reasoning deployment is also what
#: Microsoft calibrated these evaluators on, so this is the right tool
#: rather than a downgrade.
DEFAULT_EVALUATOR_MODEL = "gpt-4o"


@dataclass
class Settings:
    provider: str = "azure"
    endpoint: str = ""           # azure: resource endpoint; openai: base URL
    api_key: str = ""            # empty on azure => use `az login` identity
    model: str = DEFAULT_MODEL   # the LEARNER: reads intent, asks, drafts
    expert_model: str = DEFAULT_EXPERT_MODEL   # the ORACLE it interrogates
    judge_model: str = DEFAULT_JUDGE_MODEL     # grades the round trip
    evaluator_model: str = DEFAULT_EVALUATOR_MODEL  # MS SimilarityEvaluator
    use_azure_evaluator: bool = True           # Microsoft's scorer
    api_version: str = DEFAULT_API_VERSION
    max_tokens: int = 16384
    #: Repair rounds per episode. The old default of 3 came from the
    #: seam-bench production loop, which mirrors a live 4-reject->pass
    #: trace on SMALL protocols. On a document-scale intent an early
    #: rejection is normal and expected — it is the training signal, not a
    #: failure — so the budget has to be large enough for the drafter to
    #: work through a real error sequence (syntax -> projection -> safety).
    max_repair_rounds: int = 12
    #: USD per 1M tokens per deployment, e.g.
    #:   {"gpt-5.4": {"in": 1.25, "out": 10.0}}
    #: Empty by default and never guessed: list prices change, differ by
    #: region and by agreement, so a fabricated figure would be a confident
    #: number that is wrong. With none set, runs report real token counts
    #: and say the cost is unknown.
    prices: dict = field(default_factory=dict)

    # -- views ----------------------------------------------------------
    def key_fingerprint(self) -> str:
        """Enough to identify which key is loaded, not enough to use it."""
        if not self.api_key:
            return ""
        return f"…{self.api_key[-4:]}" if len(self.api_key) > 4 else "…"

    def masked(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("api_key")
        d["has_api_key"] = bool(self.api_key)
        d["api_key_fingerprint"] = self.key_fingerprint()
        d["auth"] = ("api key" if self.api_key
                     else "azure ad (az login)" if self.provider == "azure"
                     else "none — an OpenAI-compatible endpoint needs a key")
        d["configured"] = self.is_usable()
        return d

    def is_usable(self) -> bool:
        if not self.endpoint or not self.model:
            return False
        # Azure can authenticate without a key via `az login`; an
        # OpenAI-compatible endpoint cannot.
        return self.provider == "azure" or bool(self.api_key)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _from_env() -> Settings:
    """Whatever the environment already provides — so a checkout that was
    working before this file existed keeps working with no settings."""
    backend = os.environ.get("STJP_LLM_BACKEND", "foundry").lower()
    endpoint = (os.environ.get("AZURE_OPENAI_ENDPOINT")
                or os.environ.get("AZURE_AI_PROJECT_ENDPOINT") or "")
    return Settings(
        provider="azure" if backend != "openai" else "openai",
        endpoint=endpoint,
        api_key=os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY") or "",
        model=os.environ.get("AZURE_OPENAI_DEPLOYMENT") or DEFAULT_MODEL,
        expert_model=os.environ.get("STJP_EXPERT_DEPLOYMENT")
        or DEFAULT_EXPERT_MODEL,
        judge_model=os.environ.get("STJP_JUDGE_DEPLOYMENT")
        or DEFAULT_JUDGE_MODEL,
        evaluator_model=os.environ.get("STJP_EVALUATOR_DEPLOYMENT")
        or DEFAULT_EVALUATOR_MODEL,
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION",
                                   DEFAULT_API_VERSION))


def load(path: Path = SETTINGS_PATH) -> Settings:
    env = _from_env()
    if not path.exists():
        return env
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return env
    merged = env.to_dict()
    # Only override what the file actually sets, so a partial file (say,
    # just a model change) does not blank out a working environment.
    for k, v in raw.items():
        if k in merged and v not in ("", None):
            merged[k] = v
    if raw.get("provider") in PROVIDERS:
        merged["provider"] = raw["provider"]
    return Settings(**{k: merged[k] for k in Settings.__dataclass_fields__})


def save(settings: Settings, path: Path = SETTINGS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2),
                    encoding="utf-8")
    try:                      # best effort; a no-op on Windows ACLs
        path.chmod(0o600)
    except OSError:
        pass
    return path


def update(patch: dict[str, Any], path: Path = SETTINGS_PATH) -> Settings:
    """Apply a partial update. An absent `api_key` keeps the stored one —
    so a UI can save a model change without re-typing the secret — while an
    explicit empty string clears it (that is how you switch Azure back to
    `az login`)."""
    current = load(path)
    data = current.to_dict()
    for k, v in patch.items():
        if k not in data:
            continue
        if k == "api_key" and v is None:
            continue
        data[k] = v
    if data.get("provider") not in PROVIDERS:
        data["provider"] = "azure"
    try:
        data["max_tokens"] = max(1024, int(data.get("max_tokens") or 16384))
    except (TypeError, ValueError):
        data["max_tokens"] = 16384
    try:
        data["max_repair_rounds"] = max(
            1, int(data.get("max_repair_rounds") or 12))
    except (TypeError, ValueError):
        data["max_repair_rounds"] = 12
    settings = Settings(**{k: data[k] for k in Settings.__dataclass_fields__})
    save(settings, path)
    return settings
