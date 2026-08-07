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

import re
from typing import Callable, Optional

from experiments.intent_loop.llm import ChatLLM
from experiments.intent_loop.schema import (CoverageVerdict, DistilledIntent,
                                            FaithfulnessReport,
                                            parse_json_block)

DEFAULT_BACKTRANSLATION_THRESHOLD = 70
STJP_RANKING_WEIGHTS = {"roles": 20, "directions": 40,
                        "interaction_constraints": 40}
MIN_INTERACTION_CONSTRAINT_SCORE = 90

_COVERAGE_SYSTEM = """You audit whether a Scribble global protocol realizes \
a checklist of requirements.

A protocol has TWO parts, and they answer different kinds of requirement:
  * the STRUCTURE (roles, message order, `choice`, `rec`) answers ordering, \
authorization-before-an-act, branching, termination and role requirements;
  * the GUARD SIDECAR (`<Label>.<field> :: <predicate>` lines) answers VALUE \
requirements — thresholds, non-empty fields, "accept only when the verdict \
is MATCH", "the compared count must exceed zero".

Judge a VALUE requirement against the SIDECAR, never against the message \
structure. No arrangement of messages can express "the count must be greater \
than zero", so demanding that of the structure is a category error. If the \
sidecar is missing or lacks the predicate, the requirement is not realized — \
say so AND say that a guard is what it needs.

For EVERY requirement, decide:
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
    # Split structure from guards so the checker can judge each requirement
    # against the part that can possibly satisfy it.
    from experiments.seam_bench.t0.drafter import split_guard_sidecar
    structure, guards = split_guard_sidecar(protocol_text)
    user = (f"=== REQUIREMENTS ===\n{reqs_text}\n\n"
            f"=== PROTOCOL STRUCTURE ===\n{structure}\n\n"
            + (f"=== GUARD SIDECAR (value constraints) ===\n{guards}\n"
               if guards else "=== GUARD SIDECAR ===\n(none emitted — so "
                              "every VALUE requirement is unenforced)\n"))
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
    verdicts += [CoverageVerdict(
        rid=r.rid, covered="out_of_scope",
        evidence="intra-role procedure — the untyped interior of one agent; "
                 "no protocol expresses it, so it is not graded")
        for r in distilled.interior_requirements()]
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


def _by_priority(verdicts, distilled) -> dict:
    """covered/partial/missing per priority, so "what did we fail" is
    answerable at a glance rather than by reading twenty rows."""
    by_rid = {r.rid: r for r in distilled.requirements}
    out: dict[str, dict[str, int]] = {}
    for v in verdicts:
        r = by_rid.get(v.rid)
        if r is None or r.kind in distilled.UNGRADED_KINDS:
            continue
        d = out.setdefault(r.priority, {"yes": 0, "partial": 0, "no": 0})
        d[v.covered if v.covered in d else "no"] += 1
    for d in out.values():
        t = sum(d.values()) or 1
        d["total"] = sum(d.values())
        d["recall_pct"] = round(d["yes"] / t * 100)
    return out


def _normalized_role(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _ratio_pct(numerator: int, denominator: int) -> int:
    return round(numerator / denominator * 100) if denominator else 100


def _ranked_stjp_score(distilled: DistilledIntent, protocol_text: str,
                       verdicts: list[CoverageVerdict]) -> dict:
    """Score the formal surface STJP is responsible for, in priority order.

    Roles and directed role pairs are mechanical. Interaction constraints
    reuse the per-requirement semantic verdicts because ordering,
    authorization, branching, value predicates, and termination are the
    constraints on those handovers. Partial evidence earns half credit in
    the displayed score but never counts as fully covered.
    """
    from experiments.intent_loop.protocol_graph import parse_protocol
    from experiments.seam_bench.t0.drafter import split_guard_sidecar

    protocol_only, _guards = split_guard_sidecar(protocol_text)
    ir = parse_protocol(protocol_only)

    expected_roles = {_normalized_role(r["name"]): r["name"]
                      for r in distilled.roles}
    actual_roles = {_normalized_role(role): role for role in ir.roles}
    matched_roles = set(expected_roles) & set(actual_roles)
    missing_roles = [expected_roles[key]
                     for key in sorted(set(expected_roles) - matched_roles)]
    unexpected_roles = [actual_roles[key]
                        for key in sorted(set(actual_roles) - matched_roles)]
    role_recall = _ratio_pct(len(matched_roles), len(expected_roles))
    role_precision = _ratio_pct(len(matched_roles), len(actual_roles))
    role_score = round((role_recall + role_precision) / 2)

    expected_pairs: dict[tuple[str, str], list[str]] = {}
    for interaction in distilled.interactions:
        pair = (_normalized_role(interaction.sender),
                _normalized_role(interaction.receiver))
        expected_pairs.setdefault(pair, []).append(interaction.iid)
    actual_pairs = {
        (_normalized_role(message.sender), _normalized_role(receiver))
        for message in ir.messages() for receiver in message.receivers}
    matched_pairs = set(expected_pairs) & actual_pairs
    covered_interactions = sum(len(expected_pairs[pair])
                               for pair in matched_pairs)
    expected_interactions = sum(len(iids)
                                for iids in expected_pairs.values())
    missing_interactions = [iid for pair, iids in expected_pairs.items()
                            if pair not in actual_pairs for iid in iids]
    unexpected_pairs = ([
        f"{sender} -> {receiver}"
        for sender, receiver in sorted(actual_pairs - set(expected_pairs))]
        if expected_pairs else [])
    direction_recall = _ratio_pct(covered_interactions,
                                  expected_interactions)
    direction_precision = (_ratio_pct(len(matched_pairs), len(actual_pairs))
                           if expected_pairs else 100)
    direction_score = round((direction_recall + direction_precision) / 2)

    by_id = {verdict.rid: verdict for verdict in verdicts}
    constraint_requirements = [
        requirement for requirement in distilled.protocol_requirements()
        if requirement.kind != "role"]
    yes = partial = no = 0
    unmet = []
    for requirement in constraint_requirements:
        covered = by_id.get(requirement.rid)
        state = covered.covered if covered is not None else "no"
        if state == "yes":
            yes += 1
        elif state == "partial":
            partial += 1
            unmet.append(requirement.rid)
        else:
            no += 1
            unmet.append(requirement.rid)
    constraint_total = len(constraint_requirements)
    constraint_score = (round((yes + 0.5 * partial) / constraint_total * 100)
                        if constraint_total else 100)

    overall = round(
        role_score * STJP_RANKING_WEIGHTS["roles"] / 100
        + direction_score * STJP_RANKING_WEIGHTS["directions"] / 100
        + constraint_score
        * STJP_RANKING_WEIGHTS["interaction_constraints"] / 100)
    return {
        "overall_coverage_pct": overall,
        "weights": STJP_RANKING_WEIGHTS,
        "roles": {
            "priority": "critical",
            "weight_pct": STJP_RANKING_WEIGHTS["roles"],
            "expected": len(expected_roles), "matched": len(matched_roles),
            "missing": missing_roles, "unexpected": unexpected_roles,
            "recall_pct": role_recall, "precision_pct": role_precision,
            "score_pct": role_score},
        "directions": {
            "priority": "critical",
            "weight_pct": STJP_RANKING_WEIGHTS["directions"],
            "expected": expected_interactions,
            "covered": covered_interactions,
            "rankable": bool(expected_pairs),
            "missing_interactions": missing_interactions,
            "unexpected_pairs": unexpected_pairs,
            "recall_pct": direction_recall,
            "precision_pct": direction_precision,
            "score_pct": direction_score},
        "interaction_constraints": {
            "priority": "high",
            "weight_pct": STJP_RANKING_WEIGHTS["interaction_constraints"],
            "expected": constraint_total, "yes": yes,
            "partial": partial, "no": no, "unmet": unmet,
            "score_pct": constraint_score,
            "minimum_for_faithful_pct": MIN_INTERACTION_CONSTRAINT_SCORE},
    }


def rerank_faithfulness_report(distilled: DistilledIntent,
                               protocol_text: str,
                               report: dict) -> dict:
    """Apply the current STJP ranking to a saved faithfulness report.

    This reuses its judge evidence and back-translation, so historical
    episodes can adopt a corrected scoring policy without another model call.
    """
    updated = dict(report)
    verdicts = [CoverageVerdict(
        rid=str(item.get("rid", "")),
        covered=str(item.get("covered", "no")),
        evidence=str(item.get("evidence", "")))
        for item in report.get("coverage", [])]
    ranking = _ranked_stjp_score(distilled, protocol_text, verdicts)
    scope = dict(report.get("scope") or {})
    scope["ranking"] = ranking
    updated["scope"] = scope

    roles = ranking["roles"]
    directions = ranking["directions"]
    constraints = ranking["interaction_constraints"]
    ungrounded = report.get("ungrounded") or []
    backtranslation = report.get("backtranslation") or {}
    updated["faithful"] = (
        roles["recall_pct"] == 100 and roles["precision_pct"] == 100
        and directions["recall_pct"] == 100
        and directions["precision_pct"] == 100
        and constraints["score_pct"] >= MIN_INTERACTION_CONSTRAINT_SCORE
        and not ungrounded
        and backtranslation.get("score", 0)
        >= DEFAULT_BACKTRANSLATION_THRESHOLD)
    excluded = []
    if distilled.policy_requirements():
        excluded.append(f"{len(distilled.policy_requirements())} policy")
    if distilled.interior_requirements():
        excluded.append(f"{len(distilled.interior_requirements())} interior")
    updated["rule"] = (
        "faithful iff STJP's ranked formal surface passes: exact role set "
        f"(got {roles['score_pct']}%), exact directed interaction topology "
        f"(got {directions['score_pct']}%), interaction constraints >= "
        f"{MIN_INTERACTION_CONSTRAINT_SCORE}% "
        f"(got {constraints['score_pct']}%), no ungrounded interactions "
        f"(got {len(ungrounded)}), and back-translation >= "
        f"{DEFAULT_BACKTRANSLATION_THRESHOLD} "
        f"(got {backtranslation.get('score', 0)}). Ranked STJP coverage: "
        f"{ranking['overall_coverage_pct']}%"
        + (f". Reported but not scored: {', '.join(excluded)}"
           if excluded else ""))
    return updated


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
    from experiments.seam_bench.t0.drafter import split_guard_sidecar
    _structure, guards_text = split_guard_sidecar(protocol_text)
    verdicts, ungrounded = check_requirement_coverage(llm, distilled,
                                                      protocol_text)
    # Recall is over PROTOCOL-EXPRESSIBLE requirements only; policy
    # requirements are reported, never scored (schema.POLICY_KIND).
    n = len(distilled.protocol_requirements())
    n_policy = len(distilled.policy_requirements())
    n_interior = len(distilled.interior_requirements())
    covered = sum(1 for v in verdicts if v.covered == "yes")
    recall = (covered / n) if n else 0.0

    reconstructed = back_translate(llm, protocol_text)
    original_md = distilled.to_markdown(include_policy=False)
    comparison = (compare_fn(original_md, reconstructed) if compare_fn
                  else compare_intents(llm, original_md, reconstructed))
    comparison.setdefault("scorer", "built-in comparator prompt")
    comparison.setdefault("judged_by", getattr(llm, "label", "?"))
    backtranslation = {"reconstructed": reconstructed, **comparison}

    gold_equivalent: Optional[bool] = None
    if gold_protocol is not None and bisim_fn is not None:
        gold_equivalent, _reason = bisim_fn(protocol_text, gold_protocol)

    # THE VERDICT TURNS ON "MUST", not on everything. A protocol with every
    # obligation covered and some conveniences blurred is sound; one missing
    # an authorization guard is not, however high its overall percentage.
    # No priorities assigned at all (an older episode, or a distiller that
    # skipped them) means we cannot tell obligations from conveniences — so
    # hold EVERYTHING to the obligation bar rather than quietly certifying a
    # protocol against an empty set of requirements.
    musts = distilled.must_requirements() or distilled.protocol_requirements()
    by_id = {v.rid: v for v in verdicts}
    must_yes = sum(1 for r in musts
                   if by_id.get(r.rid) and by_id[r.rid].covered == "yes")
    must_unmet = [r.rid for r in musts
                  if not (by_id.get(r.rid)
                          and by_id[r.rid].covered == "yes")]
    must_recall = (must_yes / len(musts)) if musts else None

    ranking = _ranked_stjp_score(distilled, protocol_text, verdicts)
    ranked_roles = ranking["roles"]
    ranked_directions = ranking["directions"]
    ranked_constraints = ranking["interaction_constraints"]
    faithful = (
        ranked_roles["recall_pct"] == 100
        and ranked_roles["precision_pct"] == 100
        and ranked_directions["recall_pct"] == 100
        and ranked_directions["precision_pct"] == 100
        and ranked_constraints["score_pct"]
        >= MIN_INTERACTION_CONSTRAINT_SCORE
        and not ungrounded
        and backtranslation["score"] >= backtranslation_threshold)
    excluded = []
    if n_policy:
        excluded.append(f"{n_policy} policy (no session type can express "
                        f"them)")
    if n_interior:
        excluded.append(f"{n_interior} intra-role interior (untyped by "
                        f"design)")
    rule = ("faithful iff STJP's ranked formal surface passes: exact role "
            f"set (got {ranked_roles['score_pct']}%), exact directed "
            f"interaction topology (got {ranked_directions['score_pct']}%), "
            f"interaction constraints >= {MIN_INTERACTION_CONSTRAINT_SCORE}% "
            f"(got {ranked_constraints['score_pct']}%), no ungrounded "
            f"interactions (got {len(ungrounded)}), and back-translation "
            f">= {backtranslation_threshold} "
            f"(got {backtranslation['score']}). Ranked STJP coverage: "
            f"{ranking['overall_coverage_pct']}%"
            + (f". Reported but NOT scored: " + "; ".join(excluded)
               if excluded else ""))
    # TWO DIMENSIONS, reported separately, because they are satisfied by
    # different parts of the artifact and conflating them produced a single
    # number nobody could act on. "16% faithful" hid the real finding: the
    # INTERACTIONS were largely right and the VALUE GUARDS were absent.
    #
    #   structure  ordering / authorization / branch / termination / role
    #              — what the protocol's shape can express
    #   values     value requirements — only the .refn guard sidecar can
    #              express these; no arrangement of messages will do
    STRUCTURE_KINDS = ("ordering", "authorization", "branch", "termination",
                       "role", "other")
    by_rid = {r.rid: r for r in distilled.requirements}
    dims: dict[str, dict[str, int]] = {}
    for v in verdicts:
        req = by_rid.get(v.rid)
        if req is None or req.kind in distilled.UNGRADED_KINDS:
            continue
        dim = "values" if req.kind == "value" else "structure"
        d = dims.setdefault(dim, {"yes": 0, "partial": 0, "no": 0})
        d[v.covered if v.covered in d else "no"] += 1
    for dim, d in dims.items():
        total = sum(d.values()) or 1
        d["total"] = sum(d.values())
        d["recall_pct"] = round(d["yes"] / total * 100)
    # Per-kind detail, so a reader can see WHICH kind of requirement failed.
    per_kind: dict[str, dict[str, int]] = {}
    for v in verdicts:
        req = by_rid.get(v.rid)
        if req is None or req.kind in distilled.UNGRADED_KINDS:
            continue
        k = per_kind.setdefault(req.kind, {"yes": 0, "partial": 0, "no": 0})
        k[v.covered if v.covered in k else "no"] += 1

    report = FaithfulnessReport(
        coverage=verdicts, recall=recall, ungrounded=ungrounded,
        backtranslation=backtranslation, gold_equivalent=gold_equivalent,
        faithful=faithful, rule=rule)
    # The share of the checklist that is genuinely coordination. A low
    # figure is a fact about the DOCUMENT, not a failure of the drafter,
    # and reporting recall without it invites the wrong conclusion.
    report.scope = {"graded": n, "policy": n_policy, "interior": n_interior,
                    "typed_surface_ratio":
                        round(distilled.typed_surface_ratio(), 3),
                    "must_total": len(musts), "must_covered": must_yes,
                    "must_unmet": must_unmet,
                    "must_recall_pct": (round(must_recall * 100)
                                        if must_recall is not None else None),
                    "all_recall_pct": round(recall * 100),
                    "dimensions": dims, "per_kind": per_kind,
                    "ranking": ranking,
                    "by_priority": _by_priority(verdicts, distilled),
                    "guards_emitted": bool(guards_text),
                    "note": "`dimensions` splits what the protocol SHAPE can "
                            "express from what only a refinement guard can. "
                            "A low overall recall with high structure recall "
                            "means the interactions are right and the value "
                            "guards are missing — a different repair from a "
                            "wrong interaction."}
    return report


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
