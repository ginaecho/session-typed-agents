"""Per-role instruction builders.

Builder functions, one per scenario family on the "Foundry stack":

  - build_bare_instructions       : intent + role list, no protocol spec
  - build_bare_fairintent_instructions : like bare, but the worker carries a
                                    distilled per-role task brief instead of
                                    the full user intent (fair intent-carrying
                                    policy; single-variable delta vs bare)
  - build_spec_instructions       : full projected EFSM + refinement guards
                                    via generate_claude_subagent (verbose)
  - build_spec_minimal_instructions : minimal SEND/RECV per-state table
                                      + payload guards (terse)

The MAF runners (maf_native, maf_foundry) also use build_bare_instructions
so that the WITHOUT-side comparison is apples-to-apples on the prompt:
only the orchestration layer differs across bare / maf_native / maf_foundry.

Intent-carrying policy (docs/BENCHMARK_PLAN_V3.md, V3.1 amendment): builders
that put the user intent into a WORKER prompt use ``case.intent_effective`` —
identical to ``case.intent`` at the default short scale, but the full
intent/intent.md document at --intent-scale doc. Fair-intent arms never put
the intent document into worker prompts at all; workers get the distilled
role brief and the intent is carried only by that architecture's planner
(MAF orchestrator at runtime / STJP drafter at compile time / the
distillation step for bare teams).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from stjp_core.compiler.efsm_parser import get_all_efsms
from stjp_core.compiler.refinement_checker import load_refinements_for_protocol
from stjp_core.generation.skills_parser import parse_skills_file
from stjp_core.generation.agent_generator import generate_claude_subagent
from stjp_core.compiler.protocol_parser import parse_protocol_file

if TYPE_CHECKING:  # pragma: no cover
    from case_loader import Case


def agent_name(case: "Case", role: str, scenario_key: str) -> str:
    """Stable Foundry agent name — namespaced by case + scenario."""
    return f"stjp-{case.case_id}-{scenario_key}-{role.lower()}"


def _roles_block(case: "Case") -> str:
    """Prose role descriptions, included in EVERY arm's prompt.

    Held constant across all arms (bare, MAF, spec, min) so the variable
    actually being measured is "what protocol info comes ON TOP of the
    shared intent + role descriptions." Without this, spec/min arms get
    role descriptions implicitly via their projected local types (which
    list each role's sends/receives), while bare/MAF-intent-only arms
    have only role NAMES — a confound that would unfairly punish them.
    """
    if not case.role_descriptions:
        return ""
    lines = ["Role descriptions (what each agent does):"]
    for r in case.roles:
        desc = case.role_descriptions.get(r)
        if desc:
            lines.append(f"  - {r}: {desc}")
    lines.append("")
    return "\n".join(lines)


def _termination_block(case: "Case") -> str:
    """Explicit termination signal so bare/MAF arms know when to stop.

    Protocol-equipped arms know when they're done because their projected
    local type reaches an accepting state. Bare arms have no such signal
    and will either loop forever or WAIT forever. This prose hint is
    semantically equivalent to what the projection conveys.
    """
    return (f"Stop participating (reply WAIT) once the final report has been "
            f"delivered to the user (i.e. once a message labelled "
            f"'{case.terminal_label}' or semantically equivalent has been "
            f"sent and no further action is needed of you).")


def build_bare_instructions(case: "Case", role: str) -> str:
    """WITHOUT instructions: intent + goals + peer list, no protocol spec.

    Used by 'bare_legacy', 'maf_groupchat_legacy', 'maf_native',
    'maf_foundry' — so that the WITHOUT-side comparison isolates the
    orchestration layer, not the prompt.

    NOTE this is the BROADCAST-intent builder: every worker carries the
    whole user intent. Since the 2026-08-05 repair the default `bare` /
    `maf_groupchat` arms use build_bare_fairintent_instructions instead;
    this builder survives in the *_legacy arms to price that confound.
    """
    peer_list = ", ".join(r for r in case.roles if r != role)
    return f"""You are the **{role}** in a small multi-agent {case.case_id} pipeline.

User intent:
{case.intent_effective}

Goals:
{case.goals_text()}

{_roles_block(case)}You communicate with the other agents ({peer_list}).

{_termination_block(case)}

Output rules:
- Reply with a SINGLE JSON object, no prose, no fences.
- Schema: {{"send_to": "<RoleName or null>", "label": "<MessageLabel>", "payload": "<value or empty>", "rationale": "<one sentence>"}}
- If nothing to send, reply: {{"send_to": null, "label": "WAIT", "payload": "", "rationale": "..."}}
"""


def build_bare_fairintent_instructions(case: "Case", role: str) -> str:
    """FAIR-INTENT bare worker: distilled role brief instead of the full intent.

    Single-variable delta vs build_bare_instructions: the ``User intent:``
    block is replaced by the role's distilled task brief (produced once, at
    team set-up, by the interrogation/distillation front-end —
    scripts/intent_pipeline.py). Goals, role descriptions, termination hint
    and output rules are byte-identical to the bare arm.

    Rationale (docs/BENCHMARK_PLAN_V3.md V3.1): no practitioner pastes a
    handbook-sized intent into all N worker prompts — someone (a human or a
    front-end LLM) distills it into per-role instructions first. Charging
    the baselines for the broadcast is a confound; this arm charges them
    only for the distilled brief, plus the disclosed one-time distillation
    cost. Fail-fast if the case has no role_briefs.yaml yet.

    Since the 2026-08-05 repair this builder IS the `bare` arm (and the MAF
    participants of `maf_groupchat`); the broadcast original lives on as
    `bare_legacy` via build_bare_instructions.
    """
    brief = case.require_role_brief(role)
    peer_list = ", ".join(r for r in case.roles if r != role)
    return f"""You are the **{role}** in a small multi-agent {case.case_id} pipeline.

Your task brief (distilled from the user intent at team set-up):
{brief}

Goals:
{case.goals_text()}

{_roles_block(case)}You communicate with the other agents ({peer_list}).

{_termination_block(case)}

Output rules:
- Reply with a SINGLE JSON object, no prose, no fences.
- Schema: {{"send_to": "<RoleName or null>", "label": "<MessageLabel>", "payload": "<value or empty>", "rationale": "<one sentence>"}}
- If nothing to send, reply: {{"send_to": null, "label": "WAIT", "payload": "", "rationale": "..."}}
"""


def _paraphrase_global_protocol(case: "Case",
                                 protocol_path: "Optional[Path]" = None) -> str:
    """Render the global protocol as a natural-language interaction sequence.

    Deterministic — same input always gives the same paraphrase. The point
    is to make the .scr semantics readable for an LLM that may not parse
    Scribble syntax confidently. Branches are listed as alternatives;
    everything stays surface-level (no projection, no refinement).

    Pass ``protocol_path`` to paraphrase a non-canonical .scr (e.g. an
    LLM-drafted unsafe/valid variant); defaults to case.protocol_path.
    """
    path = protocol_path if protocol_path is not None else case.protocol_path
    parsed = parse_protocol_file(path)
    lines = [
        f"Global protocol: {parsed.protocol_name}",
        f"Participants: {', '.join(parsed.roles)}",
        "",
        "Interaction sequence (each line is one message in protocol order):",
    ]
    if not parsed.branches:
        for i, m in enumerate(parsed.messages, 1):
            ctx = f"  [branch={m.branch_context}]" if m.branch_context else ""
            lines.append(
                f"  {i:2d}. {m.sender} -> {m.receiver} : "
                f"{m.message_name}({m.payload_type or '()'})" + ctx
            )
    else:
        # Group by branch_context: top-level messages first, then each branch.
        top = [m for m in parsed.messages if not m.branch_context]
        for i, m in enumerate(top, 1):
            lines.append(
                f"  {i:2d}. {m.sender} -> {m.receiver} : "
                f"{m.message_name}({m.payload_type or '()'})"
            )
        for branch in parsed.branches:
            lines.append("")
            lines.append(f"  -- Branch [{branch}] --")
            in_branch = [m for m in parsed.messages if m.branch_context == branch]
            for j, m in enumerate(in_branch, 1):
                lines.append(
                    f"    {j:2d}. {m.sender} -> {m.receiver} : "
                    f"{m.message_name}({m.payload_type or '()'})"
                )
        if parsed.choice_roles:
            lines.append("")
            lines.append(f"  Branch chosen by: {', '.join(parsed.choice_roles)}")
    return "\n".join(lines)


def build_global_spec_instructions(case: "Case", role: str,
                                    protocol_path_override: Optional[Path] = None
                                    ) -> str:
    """WITHOUT-side fair-comparison baseline: agents get the full global protocol.

    Each agent receives the same intent + goals as the bare/MAF arms PLUS the
    full global protocol — both the raw Scribble text (for syntax-aware models)
    and a deterministic natural-language paraphrase (for the rest). The agent
    must self-project the global type into its own local actions: figure out
    which messages it sends vs receives, in what order, with what payload.

    Pass ``protocol_path_override`` to inject a non-canonical .scr (e.g. an
    LLM-drafted unsafe/valid variant). The monitor still verifies traces
    against ``case.protocol_path`` (the ground-truth spec), so off-protocol
    behaviour from following an unsafe draft still shows up as violations.

    Crucially, this arm does NOT include:
      - the projected EFSM per role (the spec arm's contribution)
      - refinement invariants compiled into the prompt
      - any runtime monitor enforcement at the LLM call site

    So comparing `maf_groupchat_global` vs `spec` / `min` isolates the value
    added by *projection + monitoring*, not the value of "knowing the protocol
    exists." This is the fair WITHOUT-side anchor when the research claim is
    "session-type machinery contributes beyond just describing the protocol."
    """
    peer_list = ", ".join(r for r in case.roles if r != role)
    path = protocol_path_override if protocol_path_override is not None \
        else case.protocol_path
    parsed = parse_protocol_file(path)
    paraphrase = _paraphrase_global_protocol(case, protocol_path=path)

    return f"""You are the **{role}** in the {case.case_id} pipeline.

User intent:
{case.intent_effective}

Goals:
{case.goals_text()}

{_roles_block(case)}You communicate with the other agents ({peer_list}).

Global protocol (Scribble source — authoritative):
---
{parsed.raw_content}
---

Global protocol (natural-language summary of the message sequence):
{paraphrase}

It is YOUR responsibility to:
- Figure out which messages YOU ({role}) send and which messages YOU receive
  by reading the global protocol above.
- Emit messages in the correct protocol order.
- Use the EXACT message labels from the protocol (case-sensitive), not paraphrases.
- Stop participating once you have sent every message the protocol requires of you.

{_termination_block(case)}

Output rules:
- Reply with a SINGLE JSON object, no prose, no fences.
- Schema: {{"send_to": "<RoleName or null>", "label": "<MessageLabel>", "payload": "<value or empty>", "rationale": "<one sentence>"}}
- If nothing to send (waiting for an incoming message), reply:
  {{"send_to": null, "label": "WAIT", "payload": "", "rationale": "<reason>"}}
"""


def build_global_spec_fairintent_instructions(case: "Case", role: str,
                                              protocol_path_override:
                                              Optional[Path] = None) -> str:
    """FAIR-INTENT global-text worker: brief + full global protocol.

    Single-variable delta vs build_global_spec_instructions: the ``User
    intent:`` block is replaced by the role's distilled brief; the global
    protocol text (Scribble source + paraphrase) stays broadcast — that
    broadcast IS this arm's treatment. Since the 2026-08-05 repair this
    builder IS `global_decentralized` (ladder setting 3) and
    `maf_groupchat_llmvalid` (MAF kind); the broadcast-intent originals
    live on as the `*_legacy` arms. Isolates "global text vs projected
    local contract" from "who carries the intent document"
    (BENCHMARK_PLAN_V3 §10.2).
    """
    brief = case.require_role_brief(role)
    peer_list = ", ".join(r for r in case.roles if r != role)
    path = protocol_path_override if protocol_path_override is not None \
        else case.protocol_path
    parsed = parse_protocol_file(path)
    paraphrase = _paraphrase_global_protocol(case, protocol_path=path)

    return f"""You are the **{role}** in the {case.case_id} pipeline.

Your task brief (distilled from the user intent at team set-up):
{brief}

Goals:
{case.goals_text()}

{_roles_block(case)}You communicate with the other agents ({peer_list}).

Global protocol (Scribble source — authoritative):
---
{parsed.raw_content}
---

Global protocol (natural-language summary of the message sequence):
{paraphrase}

It is YOUR responsibility to:
- Figure out which messages YOU ({role}) send and which messages YOU receive
  by reading the global protocol above.
- Emit messages in the correct protocol order.
- Use the EXACT message labels from the protocol (case-sensitive), not paraphrases.
- Stop participating once you have sent every message the protocol requires of you.

{_termination_block(case)}

Output rules:
- Reply with a SINGLE JSON object, no prose, no fences.
- Schema: {{"send_to": "<RoleName or null>", "label": "<MessageLabel>", "payload": "<value or empty>", "rationale": "<one sentence>"}}
- If nothing to send (waiting for an incoming message), reply:
  {{"send_to": null, "label": "WAIT", "payload": "", "rationale": "<reason>"}}
"""


def build_unchecked_skills_instructions(case: "Case", role: str) -> str:
    """UNCHECKED human-written per-agent skill (the deadlock demo's no-checker arm).

    Gives the agent ONLY its own hand-authored skill from
    cases/<case>/unchecked_skills/<role>.md plus the intent + output rules — the
    same per-agent-contract FORMAT as the validated spec arm, but the skill was
    never passed through Scribble. When those skills encode a circular wait, the
    agents deadlock at runtime. This is the fair counterpart to spec_llmvalid:
    same shape, only difference is "checked vs not."
    """
    skill_path = case.case_dir / "unchecked_skills" / f"{role}.md"
    skill = skill_path.read_text(encoding="utf-8") if skill_path.exists() else \
        f"You are the {role}. (No skill file found.)"
    peer_list = ", ".join(r for r in case.roles if r != role)
    return f"""You are the **{role}** in the {case.case_id} pipeline.

User intent:
{case.intent_effective}

{_roles_block(case)}Your skill (your per-agent contract — follow it strictly):
---
{skill}
---

You communicate with the other agents ({peer_list}).

{_termination_block(case)}

Output rules:
- Reply with a SINGLE JSON object, no prose, no fences.
- Schema: {{"send_to": "<RoleName or null>", "label": "<MessageLabel>", "payload": "<value or empty>", "rationale": "<one sentence>"}}
- If your skill says you must wait, reply: {{"send_to": null, "label": "WAIT", "payload": "", "rationale": "..."}}
"""


def build_spec_instructions(case: "Case", role: str,
                             protocol_path_override: Optional[Path] = None) -> str:
    """WITH instructions: full EFSM + compiled refinement invariants.

    Smoke at n=1 with a stripped MPST-only spec (~120 tokens/role) showed
    protocol-correctness dropping from 100% to 28.6% — agents lost the
    semantic framing they need to produce correct payloads. We keep the
    verbose Claude-subagent markdown for accuracy; the minimal variant
    (build_spec_minimal_instructions) recovers cost without losing accuracy.

    Pass ``protocol_path_override`` to project from a non-canonical .scr
    (e.g. an LLM-drafted Scribble-valid variant). Refinements are read
    from the same path; if no .refn sidecar exists for it, the arm
    inherits an empty refinement set.
    """
    path = protocol_path_override if protocol_path_override is not None \
        else case.protocol_path
    efsms = get_all_efsms(path, case.protocol_name, case.roles)
    refinements = load_refinements_for_protocol(path)

    # IMPORTANT: skills files in case.skills_dir were generated for the
    # CANONICAL protocol. They contain Decision Rules / Execution Flow /
    # Business Rules sections that reference canonical message labels. When
    # we're using a protocol override (e.g. LLM-valid draft), those rules
    # contradict the projected EFSM — the LLM reads "send HighRevenue" from
    # skills while the state machine has only "send FetchRevenueData",
    # gets confused, and outputs WAIT forever. Skip skills on override.
    skills_struct = None
    if protocol_path_override is None:
        skills_path = case.skills_dir / f"{role}_skills.md"
        if skills_path.exists():
            skills_struct = parse_skills_file(skills_path)

    ag = generate_claude_subagent(
        efsm=efsms[role],
        skills=skills_struct,
        protocol_name=case.protocol_name,
        refinements=refinements,
    )

    return f"""You are the **{role}** in the {case.case_id} pipeline.

User intent:
{case.intent_effective}

Goals:
{case.goals_text()}

{_roles_block(case)}Your role specification (projected local type + refinement invariants):
---
{ag.content}
---

{_termination_block(case)}

Output rules -- VERY IMPORTANT:
- Each turn you'll be asked "what is your next action?" given the current session state.
- Reply with a SINGLE JSON object, no prose, no markdown fences.
- Schema: {{"send_to": "<RoleName or null>", "label": "<MessageLabel>", "payload": "<value or empty>", "rationale": "<one sentence>"}}
- If nothing to send (waiting for an incoming message), reply:
  {{"send_to": null, "label": "WAIT", "payload": "", "rationale": "<reason>"}}
- Use ONLY message labels listed in your role spec above.
- Use ONLY peer roles listed in your spec.
- A payload that fails a Refinement Invariant will be REJECTED by the runtime monitor.
"""


def build_spec_minimal_instructions(case: "Case", role: str,
                                     protocol_path_override: Optional[Path] = None
                                     ) -> str:
    """WITH-minimal: terse MPST local type + refinement guards using SEND/RECV verbs.

    The n=1 smoke for code_review showed this format reaching 100% protocol-
    correct at ~46% of the verbose-spec token cost. Earlier attempts using
    '!' / '?' notation broke the LLM (it mis-decoded the symbols and emitted
    payloads as SENDs when the protocol said RECV). SEND/RECV is the sweet spot.

    Pass ``protocol_path_override`` to project from a non-canonical .scr
    (e.g. an LLM-drafted Scribble-valid variant); see build_spec_instructions.
    """
    path = protocol_path_override if protocol_path_override is not None \
        else case.protocol_path
    efsms = get_all_efsms(path, case.protocol_name, case.roles)
    refinements = load_refinements_for_protocol(path)
    efsm = efsms[role]

    by_state: dict[str, list] = {}
    for t in efsm.transitions:
        by_state.setdefault(str(t.source), []).append(t)

    def state_key(s: str):
        return (0, int(s)) if s.isdigit() else (1, s)

    lines = [
        f"{role}@{case.protocol_name} local type "
        f"(SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):",
    ]
    initial = str(efsm.initial_state) if efsm.initial_state is not None else None
    accepting = {str(s) for s in (efsm.accepting_states or set())}

    from stjp_core.compiler.refinement_checker import choice_guards_for
    guards = choice_guards_for(refinements, role)

    for state in sorted(by_state.keys(), key=state_key):
        tag = ""
        if state == initial:
            tag = " (start)"
        elif state in accepting:
            tag = " (end)"
        state_send_labels = {t.label for t in by_state[state]
                             if t.direction == "send"}
        for t in by_state[state]:
            verb = "SEND" if t.direction == "send" else "RECV"
            prep = "to" if t.direction == "send" else "from"
            payload = f"({t.payload_type})" if t.payload_type else "()"
            lines.append(
                f"  state {state}{tag}: {verb} {t.label}{payload} {prep} {t.peer} -> state {t.target}"
            )
        # Decision rule AT the choice state (value-dependent choice guard).
        for g in guards:
            if g.require in state_send_labels and \
                    any(o in state_send_labels for o in g.over):
                lines.append(
                    f"  state {state} DECISION RULE (HARD): IF {g.when} "
                    f"THEN SEND {g.require}; ELSE SEND {', '.join(g.over)}. "
                    f"Wrong branch = choice_guard_violation."
                )

    role_refs = [(k, r) for k, r in refinements.items()
                 if k[0] == role and not isinstance(r, dict) and hasattr(r, "predicates")]
    if role_refs:
        lines.append("")
        lines.append("Payload guards (HARD; runtime rejects violations):")
        for (_, receiver, label), refn in role_refs:
            t = refn.declared_type or "any"
            preds = " AND ".join(refn.predicates) if refn.predicates else "any"
            lines.append(f"  -> {receiver}.{label} (type {t}): require {preds}")

    lines.append("")
    # Prepend role descriptions block to the minimal spec (held-constant
    # across all arms; see _roles_block docstring).
    rb = _roles_block(case).strip()
    if rb:
        lines.insert(0, rb + "\n")
    lines.append(_termination_block(case))
    lines.append("")
    lines.append(
        'Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>",'
        '"payload":"<v>","rationale":"<1 line>"}'
    )
    lines.append('Use send_to=null, label="WAIT" if nothing to send.')
    return "\n".join(lines)
