"""azure_eval.py — score the round trip with Microsoft's own evaluator.

The faithfulness question in its sharpest form: a strong model reads ONLY the
drafted protocol and writes down what it thinks the user asked for; how close
is that to what the user actually asked for? If the two agree, the protocol
carries the intent. If they diverge, the protocol type-checks but means
something else.

Two things make that measurement trustworthy, and the app was doing neither
until now:

  * THE GRADER MUST NOT BE THE DRAFTER. Back-translation was running on the
    same model that wrote the protocol, which is a model marking its own
    homework — it reconstructs the intent it had in mind rather than the one
    a reader would take from the text. The judge is now a separate,
    stronger deployment.
  * THE COMPARISON SHOULD NOT BE OUR OWN PROMPT. A similarity score from a
    prompt we wrote is a number whose calibration only we vouch for.
    `azure.ai.evaluation.SimilarityEvaluator` is Microsoft's published
    evaluator on the standard 1-5 scale, so the figure is one a reviewer can
    look up rather than take on trust.

This module is an adapter, not a dependency: it plugs into the `compare_fn`
hook `evaluate_faithfulness` already exposes. If the package or the endpoint
is missing, the loop keeps using the built-in comparator and says which one
produced the number — a score whose provenance is unclear is worse than a
plainly-labelled home-made one.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any, Optional


#: Variables that make `DefaultAzureCredential` try a service principal
#: FIRST and give up if it fails, never reaching the `az login` identity.
#: Observed here: a stale AZURE_CLIENT_SECRET in the shell made every
#: evaluator call fail with "Invalid client secret provided" while the rest
#: of the app worked fine, because the app uses the repo's own az-CLI
#: credential shim instead. The evaluator constructs its credential
#: internally, so the only lever is the environment it sees.
_SP_VARS = ("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID",
            "AZURE_USERNAME", "AZURE_PASSWORD",
            "AZURE_CLIENT_CERTIFICATE_PATH")


@contextlib.contextmanager
def _without_stale_service_principal():
    """Hide service-principal variables for the duration of one call.

    Deliberately narrow: restored immediately afterwards, so nothing else
    in the process is affected. If a colleague's SP credentials are VALID
    they will want them used — so this is only reached after the SP path
    has already been shown to fail, and the failure is reported either way
    rather than silently swallowed.
    """
    saved = {k: os.environ.pop(k, None) for k in _SP_VARS}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def available() -> tuple[bool, str]:
    try:
        import azure.ai.evaluation  # noqa: F401
    except Exception as e:
        return False, f"azure-ai-evaluation not importable: {e}"
    return True, "azure-ai-evaluation present"


def _model_config(settings) -> dict[str, Any]:
    """The evaluator's model config, from the app's own settings.

    Azure OpenAI only: the evaluator needs a deployment name and endpoint.
    An empty key means the `az login` identity, which is how this checkout
    authenticates everywhere else.
    """
    cfg: dict[str, Any] = {
        "azure_endpoint": settings.endpoint,
        "azure_deployment": getattr(settings, "evaluator_model", "")
        or settings.judge_model or settings.model,
        "api_version": settings.api_version,
    }
    if settings.api_key:
        cfg["api_key"] = settings.api_key
    return cfg


def similarity_scorer(settings=None, query: Optional[str] = None):
    """Return a `compare_fn(original, reconstructed) -> dict` or None.

    None means "not usable here" — the caller then falls back to the
    built-in comparator rather than reporting a score it could not compute.
    """
    ok, _why = available()
    if not ok:
        return None
    from experiments.intent_loop import settings as settings_mod
    s = settings or settings_mod.load()
    if s.provider != "azure" or not s.endpoint:
        return None

    from azure.ai.evaluation import SimilarityEvaluator
    evaluator = SimilarityEvaluator(model_config=_model_config(s))
    the_query = query or ("What coordination did the stakeholder ask for — "
                          "which participants, exchanging what, in what "
                          "order, and what must be true at the end?")

    def compare(original: str, reconstructed: str) -> dict:
        try:
            with _without_stale_service_principal():
                raw = evaluator(query=the_query, response=reconstructed,
                                ground_truth=original)
        except Exception as e:
            # Never fabricate a score. Report the failure so the caller can
            # fall back and the artifact records why.
            return {"score": 0, "missing": [], "added": [],
                    "scorer": "azure-similarity (FAILED)",
                    "error": f"{type(e).__name__}: {str(e)[:300]}"}
        # The evaluator returns a 1-5 Likert score under a key that has
        # differed across versions; accept any of them rather than pinning.
        likert = next((raw[k] for k in ("similarity", "gpt_similarity",
                                        "similarity_score") if k in raw),
                      None)
        if likert is None:
            return {"score": 0, "missing": [], "added": [],
                    "scorer": "azure-similarity (no score in response)",
                    "raw": {k: str(v)[:80] for k, v in raw.items()}}
        try:
            val = float(likert)
        except (TypeError, ValueError):
            val = 0.0
        # 1-5 -> 0-100, so it sits on the same axis as the built-in score
        # and the existing >= 70 threshold keeps its meaning (4/5).
        pct = max(0.0, min(100.0, (val - 1.0) / 4.0 * 100.0))
        return {"score": round(pct), "missing": [], "added": [],
                "scorer": "azure-ai-evaluation SimilarityEvaluator",
                "likert_1_to_5": val,
                "note": "Microsoft's published evaluator; 1-5 mapped onto "
                        "0-100. It returns a magnitude only, so the "
                        "missing/added lists stay empty — use the built-in "
                        "comparator when you need to know WHAT differed."}

    return compare
