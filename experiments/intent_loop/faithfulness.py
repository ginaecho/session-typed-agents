"""faithfulness.py — does the validated protocol say what the intent said?

Validity (Scribble accepts it) and faithfulness (it means what the user
meant) are different properties; the seam plans call the second one the
hard one. This suite scores faithfulness with three graded instruments,
cheapest first, and never lets a single LLM opinion be the whole verdict:

  1. Requirement coverage (primary). The interrogation produced ATOMIC,
     typed requirements; a checker LLM must locate each one in the
     protocol and cite evidence, and must list protocol interactions that
     no requirement grounds. Decomposed checks beat one holistic "is it
     faithful?" question: omissions are exactly the failure mode holistic
     similarity scoring is blind to. Recall over requirements + a
     hallucination list, each item auditable by a human.
  2. Back-translation comparison (the round-trip idea; same shape as the
     judge panel's J-back class and data/d2_backtranslate's round-trip
     probe). One call sees ONLY the protocol and reconstructs the intent
     it encodes — `back_translate()`'s signature has no intent parameter,
     which is the isolation mechanism, not a convention — then a separate
     comparator scores the reconstruction against the distilled intent
     (0-100, with missing/added lists). An external similarity scorer
     (e.g. azure-ai-evaluation's SimilarityEvaluator) can replace the
     comparator seat via `compare_fn` without touching anything else.
  3. Gold EFSM-equivalence (exact, mechanical, optional). When a known-
     correct reference protocol exists (benchmark cases), the E5 checker
     (eval/validity.bisim_equivalent) gives a judge-free verdict. Not
     available for genuinely new intents — which is why 1 and 2 exist.

For calibrated headline numbers, the seam_bench judge panel (J-fwd /
J-back / J-probe with human-audit calibration) remains the reference
instrument; `run_seam_panel` is a thin optional bridge to it. This
module's suite is the fast in-loop signal the training corpus records for
every episode.
"""
from __future__ import annotations

from typing import Callable, Optional

from experiments.intent_loop.llm import ChatLLM
from experiments.intent_loop.schema import (CoverageVerdict, DistilledIntent,
                                            FaithfulnessReport,
                                            parse_json_block)

DEFAULT_BACKTRANSLATION_THRESHOLD = 70

_COVERAGE_SYSTEM = """You audit whether a Scribble global protocol realizes \
a checklist of requirements. For EVERY requirement, decide:
- "yes": the protocol clearly realizes it (cite the message(s)/structure),
- "partial": partly realized or realized ambiguously,
- "no": absent or contradicted.
Also list protocol interactions that NO requirement justifies (possible \
hallucinated structure) under "ungrounded".
Reply with EXACTLY ONE JSON object:
{"verdicts": [{"rid": "R1", "covered": "yes|partial|no", "evidence": "..."}],
 "ungrounded": ["<interaction and why it is not grounded>", ...]}"""

_BACKTRANSLATE_SYSTEM = """You are shown ONLY a Scribble global protocol. \
Write the natural-language task request a stakeholder would have given to \
get exactly this coordination: who is involved, what happens in what \
order, what is decided where, what needs approval, and how it ends. Plain \
business language; do not mention Scribble, protocols, message labels, or \
state machines. Reply with the request text only."""

_COMPARE_SYSTEM = """You compare two task descriptions: the ORIGINAL \
distilled intent and a RECONSTRUCTION written by someone who only saw the \
formal protocol. Score how completely the reconstruction preserves the \
original's requirements (coverage of meaning, not wording): 0 = unrelated, \
100 = every requirement preserved, nothing substantive added.
Reply with EXACTLY ONE JSON object:
{"score": <0-100>, "missing": ["<requirement absent from the \
reconstruction>", ...], "added": ["<substantive claim the original never \
made>", ...]}"""


def check_requirement_coverage(
        llm: ChatLLM, distilled: DistilledIntent, protocol_text: str
) -> tuple[list[CoverageVerdict], list[str]]:
    """Audit the PROTOCOL-EXPRESSIBLE requirements only. Policy requirements
    (POLICY_KIND) are never sent to the checker: asking whether a session
    type enforces "the approver and payer must be different people" invites
    a meaningless verdict either way."""
    scored = distilled.protocol_requirements()
    reqs_text = "\n".join(
        f"- [{r.rid}][{r.kind}] {r.text}"
        + (f" (roles: {', '.join(r.who)})" if r.who else "")
        for r in scored)
    user = (f"=== REQUIREMENTS ===\n{reqs_text}\n\n"
            f"=== PROTOCOL ===\n{protocol_text}")
    obj = parse_json_block(llm.complete(_COVERAGE_SYSTEM, user,
                                        stage="coverage"))
    known = {r.rid for r in scored}
    verdicts = [CoverageVerdict(rid=str(v.get("rid")),
                                covered=str(v.get("covered", "no")).lower(),
                                evidence=str(v.get("evidence", "")))
                for v in obj.get("verdicts", [])
                if str(v.get("rid")) in known]
    # A requirement the checker skipped is a MISS, not a free pass.
    seen = {v.rid for v in verdicts}
    verdicts += [CoverageVerdict(rid=r.rid, covered="no",
                                 evidence="checker returned no verdict")
                 for r in scored if r.rid not in seen]
    verdicts += [CoverageVerdict(
        rid=r.rid, covered="out_of_scope",
        evidence="policy requirement — not expressible as a session type; "
                 "enforced by the deployment/identity layer")
        for r in distilled.policy_requirements()]
    ungrounded = [str(u) for u in obj.get("ungrounded", [])]
    return verdicts, ungrounded


def back_translate(llm: ChatLLM, protocol_text: str) -> str:
    """Reconstruct the intent from the protocol ALONE (no intent parameter
    — the J-back isolation property, enforced by this signature)."""
    return llm.complete(_BACKTRANSLATE_SYSTEM,
                        f"=== PROTOCOL ===\n{protocol_text}",
                        stage="backtranslate").strip()


def compare_intents(llm: ChatLLM, original: str, reconstructed: str) -> dict:
    user = (f"=== ORIGINAL ===\n{original}\n\n"
            f"=== RECONSTRUCTION ===\n{reconstructed}")
    obj = parse_json_block(llm.complete(_COMPARE_SYSTEM, user,
                                        stage="compare"))
    return {"score": int(obj.get("score", 0)),
            "missing": [str(m) for m in obj.get("missing", [])],
            "added": [str(a) for a in obj.get("added", [])]}


def evaluate_faithfulness(
        llm: ChatLLM, distilled: DistilledIntent, protocol_text: str, *,
        gold_protocol: Optional[str] = None,
        bisim_fn: Optional[Callable[[str, str], tuple[bool, str]]] = None,
        compare_fn: Optional[Callable[[str, str], dict]] = None,
        backtranslation_threshold: int = DEFAULT_BACKTRANSLATION_THRESHOLD,
) -> FaithfulnessReport:
    """Run the suite and aggregate.

    Verdict rule (stated in the report so no reader has to find this
    docstring): faithful iff every requirement is covered "yes" AND the
    checker found no ungrounded interactions AND the back-translation
    comparator scores >= threshold. "partial" counts as a miss — a
    training-signal metric should be conservative; the per-item evidence
    is retained precisely so a human can overrule it.
    """
    verdicts, ungrounded = check_requirement_coverage(llm, distilled,
                                                      protocol_text)
    # Recall is over PROTOCOL-EXPRESSIBLE requirements only; policy
    # requirements are reported, never scored (schema.POLICY_KIND).
    n = len(distilled.protocol_requirements())
    n_policy = len(distilled.policy_requirements())
    covered = sum(1 for v in verdicts if v.covered == "yes")
    recall = (covered / n) if n else 0.0

    reconstructed = back_translate(llm, protocol_text)
    original_md = distilled.to_markdown(include_policy=False)
    comparison = (compare_fn(original_md, reconstructed) if compare_fn
                  else compare_intents(llm, original_md, reconstructed))
    backtranslation = {"reconstructed": reconstructed, **comparison}

    gold_equivalent: Optional[bool] = None
    if gold_protocol is not None and bisim_fn is not None:
        gold_equivalent, _reason = bisim_fn(protocol_text, gold_protocol)

    faithful = (n > 0 and recall == 1.0 and not ungrounded
                and backtranslation["score"] >= backtranslation_threshold)
    rule = (f"faithful iff all {n} protocol-expressible requirements covered "
            f"'yes' (got {covered}), no ungrounded interactions "
            f"(got {len(ungrounded)}), and back-translation score >= "
            f"{backtranslation_threshold} (got {backtranslation['score']})"
            + (f"; {n_policy} policy requirement(s) reported but NOT scored "
               f"— no session type can express them"
               if n_policy else ""))
    return FaithfulnessReport(
        coverage=verdicts, recall=recall, ungrounded=ungrounded,
        backtranslation=backtranslation, gold_equivalent=gold_equivalent,
        faithful=faithful, rule=rule)


def run_seam_panel(intent_text: str, protocol_text: str, cache_dir=None):
    """Optional bridge to the calibrated seam_bench judge panel (J-fwd /
    J-back / J-probe; requires ANTHROPIC_API_KEY). Returns the PanelResult,
    or None with a printed reason when the panel cannot run here. Kept
    lazy: the loop must stay usable in environments without the Anthropic
    SDK or key."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("run_seam_panel: ANTHROPIC_API_KEY not set - skipping panel.")
        return None
    try:
        import anthropic
        from pathlib import Path
        from experiments.seam_bench.judge.cache import VerdictCache
        from experiments.seam_bench.judge.run_panel import judge_case
    except Exception as e:  # pragma: no cover - environment-dependent
        print(f"run_seam_panel: panel unavailable ({e}) - skipping.")
        return None
    cache = VerdictCache(Path(cache_dir) if cache_dir
                         else Path("experiments/intent_loop/.panel_cache"))
    result, _verdicts, _payload = judge_case(anthropic.Anthropic(), cache,
                                             intent_text, protocol_text)
    return result
