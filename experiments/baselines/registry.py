"""SCENARIOS registry — single source of truth for which arms case_runner runs.

Adding a new baseline:
  1. Implement a BaselineRunner subclass in baselines/<name>.py
  2. Import the class here.
  3. Add a SCENARIOS entry: (scenario_key, scenario_name, factory).
     The factory takes (case) and returns the constructed runner.

The order here is also the display order in print_summary.

ARM RENAME (2026-08-05, project-owner directive — BENCHMARK_PLAN_V3 §10.8,
"Final arm naming"): the 10-arm canonical matrix for THIS benchmark
(skills_safety/sdlc_release_gate) was renamed to a uniform vocabulary. Every
OLD key below stays resolvable (make_runner, --arms, ALL_SCENARIOS) via a
LEGACY_SCENARIOS alias bound to the IDENTICAL factory/builder — so run dirs
produced before the rename still summarize. Never compare an old-key run dir
to a new-key run dir as if they were the same trial population; they ARE the
same population (byte-identical prompts/config) — only the display key
differs — but keep the provenance clear in any report.

    new name              | old name (now a legacy alias)      | meaning
    -----------------------|-------------------------------------|--------------------------------------------------------
    skills                 | (replaces `bare` as baseline;        | real published skill files (skills_original /
                            |  structurally = `unchecked_skills`   | unchecked_skills) + user intent; round-robin; no protocol
                            |  promoted to core)                   |
    maf_skills              | (new)                                | same skill files + intent, MAF GroupChat runtime
    globalvalid             | global_decentralized                 | whole validated plan as text, round-robin, observe-only
    maf_globalvalid          | maf_groupchat_llmvalid               | whole validated plan as text, MAF runtime
    localvalid               | min_llmvalid                         | validated projected per-role local contract, round-robin, observe-only
    maf_localvalid            | maf_groupchat_llmvalid_orch          | same local contracts, MAF runtime (orchestrator holds intent+plan)
    localvalid_gate            | min_llmvalid_gate                    | local contract + gate blocks rule-breaking messages
    maf_localvalid_gate        | (new)                                | same contracts + pre-broadcast gate on MAF GroupChat
    localvalid_sched            | min_llmvalid_sched                   | + EFSM-driven turn selection (full STJP)
    maf_localvalid_sched          | (new — feasibility confirmed:        | MAF GroupChat + local contracts + EFSM-driven speaker
                            |  GroupChatBuilder(selection_func=...)                            |  is a documented, first-class          | selection without a gate (scheduling-only isolation)
                            |  alternative to orchestrator_agent)   |

`bare` and `maf_groupchat` (the old no-protocol baselines) are NOT renamed —
they are REPLACED as the canonical baseline by `skills`/`maf_skills` and
demoted to LEGACY_SCENARIOS aliases (still resolvable under their old keys).
The 3 ablation-tier isolations (`min_llmvalid_gate_lastrecv`,
`min_llmvalid_gate_nohint`, `spec_llmvalid_gate`) are untouched by this
rename — they are not part of the 10-arm canonical table above.
"""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from baselines.foundry_runner import FoundryRunner
from baselines.instructions import (
    build_bare_instructions,
    build_bare_fairintent_instructions,
    build_global_spec_instructions,
    build_global_spec_fairintent_instructions,
    build_spec_instructions,
    build_spec_minimal_instructions,
    build_unchecked_skills_instructions,
)

if TYPE_CHECKING:  # pragma: no cover
    from case_loader import Case
    from baselines.base import BaselineRunner


def _foundry_factory(scenario_key, scenario_name, builder):
    """Bind a FoundryRunner factory to (key, name, builder)."""
    def factory(case):
        return FoundryRunner(case, scenario_key, scenario_name, builder)
    return factory


def _maf_native_factory(case):
    # Lazy-import so importing the registry doesn't pull MAF unless needed.
    from baselines.maf_native import MAFNativeRunner
    return MAFNativeRunner(case, "maf_native", "WITHOUT-maf-native")


def _maf_foundry_factory(case):
    from baselines.maf_foundry import MAFFoundryRunner
    return MAFFoundryRunner(case, "maf_foundry", "WITHOUT-maf-foundry")


# ---------------------------------------------------------------------------
# skills / maf_skills — real published skill files as the baseline
# (2026-08-05 rename: replaces bare / maf_groupchat as the no-protocol
# baseline). Same builder (build_unchecked_skills_instructions) that used to
# back the ablation-tier `unchecked_skills` arm — that key survives as a
# LEGACY_SCENARIOS alias below.
# ---------------------------------------------------------------------------

def _skills_factory(case):
    """WITHOUT-side baseline: hand-authored, never-Scribble-checked per-role
    skill files (experiments/cases/<case>/unchecked_skills/<role>.md, a copy
    of skills_original/) + user intent, round-robin runner, no protocol
    vocabulary and no monitor gate. Replaces `bare` as THIS benchmark's
    canonical no-protocol baseline: real-skill-file prose is what a team
    would actually author, not an abstract "no info" control."""
    return FoundryRunner(case, "skills", "WITHOUT-skills",
                         build_unchecked_skills_instructions)


def _maf_skills_factory(case):
    """MAF GroupChat runtime with the SAME real skill-file worker prompts as
    `skills`, plus the standard LLM orchestrator prompt (intent-carrying,
    no protocol) — MAF's own speaker-selection baseline, on real skills
    instead of a bare/intent-only prompt. Replaces `maf_groupchat` as THIS
    benchmark's canonical MAF no-protocol baseline."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    return MAFGroupChatRunner(
        case, "maf_skills", "WITHOUT-maf-skills",
        instructions_builder=build_unchecked_skills_instructions)


def _maf_groupchat_factory(case):
    """MAF GroupChat, REPAIRED prompt policy (2026-08-05) — MAF used the way
    MAF is designed to be used. Same key as before the repair; the persisted
    prompt sha + prompts_schema_version distinguish pre/post-repair runs.

    The orchestrator (MAF's planner) holds the full user intent; every
    participant holds only its distilled role brief (+ the shared goals /
    role-description / termination prose every arm gets). No protocol info
    anywhere. The pre-repair broadcast-intent variant survives as
    `maf_groupchat_legacy` for pricing the broadcast confound. See
    BENCHMARK_PLAN_V3 §10.

    2026-08-05 arm rename: `maf_skills` replaces this as THIS benchmark's
    canonical MAF no-protocol baseline; this key survives as a
    LEGACY_SCENARIOS alias (identical factory, old key)."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    return MAFGroupChatRunner(
        case, "maf_groupchat", "WITHOUT-maf-groupchat",
        instructions_builder=build_bare_fairintent_instructions)


def _maf_groupchat_legacy_factory(case):
    """Pre-repair broadcast policy: full intent to every participant AND the
    orchestrator. Not how MAF is meant to be used — kept ONLY as the control
    that prices the broadcast confound and to reproduce pre-2026-08-05 runs
    (which recorded it under the key `maf_groupchat`)."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    return MAFGroupChatRunner(case, "maf_groupchat_legacy",
                              "WITHOUT-maf-groupchat-LEGACY",
                              instructions_builder=build_bare_instructions)


def _maf_localvalid_factory(case):
    """MAF + STJP compile-time artifacts, placed where the architecture wants
    them (the plan's `maf_localvalid` kind, §5.2):

      - ORCHESTRATOR: full user intent + the LLM-drafted, Scribble-validated
        GLOBAL protocol (source + paraphrase) — the planner knows the plan.
      - PARTICIPANTS: only their projected LOCAL contract (lean SEND/RECV
        table), byte-identical to the localvalid ladder prompts.

    vs maf_globalvalid (same protocol text broadcast to every participant):
    isolates "orchestrated placement" from "who knows the protocol". No
    No gate and no EFSM scheduler. The gated counterpart,
    `maf_localvalid_gate`, uses a custom MAF orchestrator to intercept output
    before broadcast. The EFSM-scheduled counterpart is
    `maf_localvalid_sched` (schedule="efsm", NO orchestrator agent at all —
    see MAFGroupChatRunner docstring). This kind measures compile-time
    artifacts only.

    2026-08-05 arm rename: was `maf_groupchat_llmvalid_orch`; that key
    survives as a LEGACY_SCENARIOS alias (identical factory, old key)."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    path = _require_llm_draft(case, "valid", "maf_localvalid")
    goals_path = _llm_drafted_goals_path(case, "valid")

    def builder(c, role):
        return build_spec_minimal_instructions(c, role,
                                               protocol_path_override=path)

    return MAFGroupChatRunner(
        case, "maf_localvalid", "WITHOUT-maf-localvalid-ORCH",
        instructions_builder=builder,
        protocol_path_override=path,
        goals_path_override=goals_path,
        orchestrator_protocol_path=path,
    )


def _maf_localvalid_gate_factory(case):
    """MAF GroupChat + projected local contracts + pre-broadcast STJP gate."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    path = _require_llm_draft(case, "valid", "maf_localvalid_gate")
    goals_path = _llm_drafted_goals_path(case, "valid")

    def builder(c, role):
        return build_spec_minimal_instructions(
            c, role, protocol_path_override=path)

    return MAFGroupChatRunner(
        case, "maf_localvalid_gate", "WITH-maf-localvalid-GATE",
        instructions_builder=builder,
        protocol_path_override=path,
        goals_path_override=goals_path,
        orchestrator_protocol_path=path,
        gate=True,
    )


def _maf_groupchat_llmvalid_orch_alias_factory(case):
    """LEGACY alias for `maf_localvalid` under its pre-2026-08-05 key
    (identical factory)."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    path = _require_llm_draft(case, "valid", "maf_groupchat_llmvalid_orch")
    goals_path = _llm_drafted_goals_path(case, "valid")

    def builder(c, role):
        return build_spec_minimal_instructions(c, role,
                                               protocol_path_override=path)

    return MAFGroupChatRunner(
        case, "maf_groupchat_llmvalid_orch", "WITHOUT-maf-gc-llmvalid-ORCH",
        instructions_builder=builder,
        protocol_path_override=path,
        goals_path_override=goals_path,
        orchestrator_protocol_path=path,
    )


def _maf_localvalid_sched_factory(case):
    """maf_localvalid_sched (NEW, 2026-08-05 — feasibility confirmed via
    direct read of the installed agent_framework_orchestrations package:
    GroupChatBuilder(selection_func=...) is a documented, first-class,
    mutually-exclusive alternative to orchestrator_agent; see
    agent_framework_orchestrations/_group_chat.py GroupChatOrchestrator /
    GroupChatSelectionFunction).

    Same localvalid (projected per-role local, min-format) contracts as
    `maf_localvalid`, but speaker selection is a PROGRAMMATIC function
    implementing the EFSM enabled-sender claim predicate — the full STJP
    execution plane's scheduler, ported to MAF's GroupChat — instead of an
    LLM orchestrator_agent. This arm deliberately has no gate so it isolates
    "protocol-derived speaker scheduling" on the MAF runtime, the MAF-side
    twin of `localvalid_sched` on the round-robin runtime."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    path = _require_llm_draft(case, "valid", "maf_localvalid_sched")
    goals_path = _llm_drafted_goals_path(case, "valid")

    def builder(c, role):
        return build_spec_minimal_instructions(c, role,
                                               protocol_path_override=path)

    return MAFGroupChatRunner(
        case, "maf_localvalid_sched", "WITHOUT-maf-localvalid-SCHED",
        instructions_builder=builder,
        protocol_path_override=path,
        goals_path_override=goals_path,
        schedule="efsm",
    )


def _maf_groupchat_global_factory(case):
    """Fair-comparison MAF GroupChat: agents get the GLOBAL protocol text but
    no projection and no monitor. Isolates the contribution of projection +
    monitoring (the spec-arm machinery) from the contribution of merely
    'knowing the protocol exists.'"""
    from baselines.maf_groupchat import MAFGroupChatRunner
    return MAFGroupChatRunner(case, "maf_groupchat_global",
                              "WITHOUT-maf-gc-global",
                              instructions_builder=build_global_spec_instructions)


def _llm_draft_path(case, kind: str):
    """Resolve experiments/cases/<case>/protocols/llm_drafts/<kind>/v1.scr.

    The file is named v1.scr (matching the inline `module v1;` declaration)
    so Scribble's projection step accepts it. Returns None if the file
    doesn't exist (e.g. draft_llm_protocols.py hasn't been run yet for
    this case). Callers should gracefully skip such arms.
    """
    p = case.case_dir / "protocols" / "llm_drafts" / kind / "v1.scr"
    return p if p.exists() else None


def _llm_drafted_goals_path(case, kind: str):
    """Path to re-anchored goals YAML for the LLM-drafted protocol, or None."""
    p = case.case_dir / "protocols" / "llm_drafts" / kind / "goals.yaml"
    return p if p.exists() else None


def _require_llm_draft(case, kind: str, scenario_key: str):
    """Fail-fast if the LLM-drafted .scr is missing — clear remediation message."""
    path = _llm_draft_path(case, kind)
    if path is None:
        raise FileNotFoundError(
            f"Missing LLM-drafted protocol for {scenario_key}: expected "
            f"{case.case_dir / 'protocols' / 'llm_drafts' / kind / 'v1.scr'}. "
            f"Run: python experiments/scripts/draft_llm_protocols.py {case.case_id}"
        )
    return path


def _make_maf_llm_drafted_factory(kind: str, scenario_key: str, scenario_name: str):
    """MAF GroupChat factory whose agents are prompted with an LLM-drafted
    global protocol AND whose monitor + goal verifier use that same protocol."""
    def factory(case):
        from baselines.maf_groupchat import MAFGroupChatRunner
        path = _require_llm_draft(case, kind, scenario_key)
        goals_path = _llm_drafted_goals_path(case, kind)

        def builder(c, role):
            return build_global_spec_instructions(c, role,
                                                  protocol_path_override=path)

        return MAFGroupChatRunner(
            case, scenario_key, scenario_name,
            instructions_builder=builder,
            protocol_path_override=path,
            goals_path_override=goals_path,
        )
    return factory


def _make_foundry_llm_drafted_factory(kind: str, scenario_key: str,
                                       scenario_name: str, spec_builder,
                                       gate: bool = False,
                                       schedule: str = "roundrobin",
                                       hints: bool = True):
    """Foundry spec/min factory: projects from the LLM-drafted global type,
    monitor + verifier use that same protocol (and its re-anchored goals).

    ``gate=True`` builds the C+ ENFORCED arm: same projected contract, but an
    in-line SessionMonitor REJECTS off-contract sends (off_protocol /
    unexpected_peer / refinement / choice_guard) before delivery and
    re-prompts the offending role. See FoundryRunner gate mode.

    ``schedule='efsm'`` (requires gate) additionally replaces round-robin
    polling with the EFSM enabled-sender claim predicate — the STJP execution
    plane (delm_runner Plane B) on real agents."""
    def factory(case):
        path = _require_llm_draft(case, kind, scenario_key)
        goals_path = _llm_drafted_goals_path(case, kind)

        def builder(c, role):
            return spec_builder(c, role, protocol_path_override=path)

        return FoundryRunner(
            case, scenario_key, scenario_name, builder,
            protocol_path_override=path,
            goals_path_override=goals_path,
            gate=gate,
            schedule=schedule,
            hints=hints,
        )
    return factory


# Pre-repair broadcast variant (intent + protocol text to every worker);
# recorded as `maf_globalvalid`/`maf_groupchat_llmvalid` in pre-2026-08-05 runs.
_maf_groupchat_llmvalid_legacy_factory = _make_maf_llm_drafted_factory(
    "valid", "maf_groupchat_llmvalid_legacy", "WITHOUT-maf-gc-llmvalid-LEGACY")
_maf_groupchat_unsafe_factory = _make_maf_llm_drafted_factory(
    "unsafe", "maf_groupchat_unsafe", "WITHOUT-maf-gc-unsafe")


def _maf_globalvalid_factory(case):
    """MAF GroupChat + validated protocol text, REPAIRED prompt policy
    (2026-08-05): participants get their distilled brief + the validated
    GLOBAL protocol text (the protocol broadcast IS this arm's treatment);
    the ORCHESTRATOR carries the full intent. vs maf_localvalid
    (participants get local contracts): isolates global-text-broadcast vs
    projection with no intent-carrying confound.

    2026-08-05 arm rename: was `maf_groupchat_llmvalid`; that key survives
    as a LEGACY_SCENARIOS alias (identical factory, old key). The pre-repair
    broadcast-intent variant survives separately as
    `maf_groupchat_llmvalid_legacy`."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    path = _require_llm_draft(case, "valid", "maf_globalvalid")
    goals_path = _llm_drafted_goals_path(case, "valid")

    def builder(c, role):
        return build_global_spec_fairintent_instructions(
            c, role, protocol_path_override=path)

    return MAFGroupChatRunner(
        case, "maf_globalvalid", "WITHOUT-maf-globalvalid",
        instructions_builder=builder,
        protocol_path_override=path,
        goals_path_override=goals_path,
    )


def _maf_groupchat_llmvalid_alias_factory(case):
    """LEGACY alias for `maf_globalvalid` under its pre-2026-08-05 key
    (identical factory)."""
    from baselines.maf_groupchat import MAFGroupChatRunner
    path = _require_llm_draft(case, "valid", "maf_groupchat_llmvalid")
    goals_path = _llm_drafted_goals_path(case, "valid")

    def builder(c, role):
        return build_global_spec_fairintent_instructions(
            c, role, protocol_path_override=path)

    return MAFGroupChatRunner(
        case, "maf_groupchat_llmvalid", "WITHOUT-maf-gc-llmvalid",
        instructions_builder=builder,
        protocol_path_override=path,
        goals_path_override=goals_path,
    )


_localvalid_factory = _make_foundry_llm_drafted_factory(
    "valid", "localvalid", "WITH-localvalid", build_spec_minimal_instructions)
_min_llmvalid_alias_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid", "WITH-min-llmvalid", build_spec_minimal_instructions)
_spec_llmvalid_gate_factory = _make_foundry_llm_drafted_factory(
    "valid", "spec_llmvalid_gate", "WITH-spec-llmvalid-GATE",
    build_spec_instructions, gate=True)
# GATE on the LEAN projected contract (same enforcement as spec_llmvalid_gate,
# same prompt as localvalid). Decomposes contract-verbosity from enforcement:
# localvalid vs localvalid_gate isolates the gate on identical prompts.
_localvalid_gate_factory = _make_foundry_llm_drafted_factory(
    "valid", "localvalid_gate", "WITH-localvalid-GATE",
    build_spec_minimal_instructions, gate=True)
_min_llmvalid_gate_alias_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_gate", "WITH-min-llmvalid-GATE",
    build_spec_minimal_instructions, gate=True)
# The full STJP execution plane: lean projected contract + enforcement gate +
# EFSM enabled-sender scheduling. The scheduler is derived STATICALLY from the
# same projection that generates each role's prompt — a global-text arm cannot
# construct it without adding an LLM orchestrator. localvalid_gate vs
# localvalid_sched isolates the scheduler on identical prompts + enforcement.
_localvalid_sched_factory = _make_foundry_llm_drafted_factory(
    "valid", "localvalid_sched", "WITH-localvalid-SCHED",
    build_spec_minimal_instructions, gate=True, schedule="efsm")
_min_llmvalid_sched_alias_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_sched", "WITH-min-llmvalid-SCHED",
    build_spec_minimal_instructions, gate=True, schedule="efsm")
# CHEAP-HEURISTIC scheduling control: same prompt + gate as
# localvalid_sched, but the next actor is chosen by "ask whoever just
# received a message" (round-robin fallback) — a rule that needs NO
# protocol. min_llmvalid_gate_lastrecv vs localvalid_sched isolates what
# the protocol-derived EFSM scheduler adds beyond this trivial heuristic
# (expected: little on linear pipelines, a real gap on branching / fan-in /
# concurrent cases). See docs/BENCHMARK_FAIRNESS_REVIEW.md, Problem 4.
# NOT part of the 2026-08-05 rename table (ablation-tier only); key unchanged.
_min_llmvalid_gate_lastrecv_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_gate_lastrecv", "WITH-min-GATE-LASTRECV",
    build_spec_minimal_instructions, gate=True, schedule="lastreceiver")
# HINTS ablation: same prompt + gate as localvalid_gate, but WITHOUT the
# per-turn liveness nudge ("you are at state N; the available action is
# SEND X to Y"). localvalid_gate vs min_llmvalid_gate_nohint separates
# pure enforcement (block + explain rejections) from per-turn ground-truth
# guidance. See docs/BENCHMARK_FAIRNESS_REVIEW.md, Problem 5.
# NOT part of the 2026-08-05 rename table (ablation-tier only); key unchanged.
_min_llmvalid_gate_nohint_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_gate_nohint", "WITH-min-GATE-NOHINT",
    build_spec_minimal_instructions, gate=True, hints=False)
# Global protocol text, but on the DECENTRALIZED round-robin runner (no central
# orchestrator) — the "B with autonomous local agents" control. Isolates
# "global text vs projected local contract" from "orchestrated vs decentralized":
# compare against localvalid (local types, same runner) and against
# maf_globalvalid (global text, orchestrated). See
# docs/WHY_B_MATCHES_C_ANALYSIS.md (orchestration confound).
# REPAIRED (2026-08-05): worker carries its distilled role brief + the
# broadcast global protocol (the protocol broadcast IS the treatment); the
# full-intent broadcast of the pre-repair prompt policy survives as
# `global_decentralized_legacy`.
#
# 2026-08-05 arm rename: renamed to `globalvalid` and promoted from
# ABLATION_SCENARIOS to the 10-arm core matrix; `global_decentralized`
# survives as a LEGACY_SCENARIOS alias (identical factory, old key).
_globalvalid_factory = _make_foundry_llm_drafted_factory(
    "valid", "globalvalid", "WITH-globalvalid",
    build_global_spec_fairintent_instructions)
_global_decentralized_alias_factory = _make_foundry_llm_drafted_factory(
    "valid", "global_decentralized", "WITH-global-decentralized",
    build_global_spec_fairintent_instructions)
_global_decentralized_legacy_factory = _make_foundry_llm_drafted_factory(
    "valid", "global_decentralized_legacy", "WITH-global-decentralized-LEGACY",
    build_global_spec_instructions)


# UNCHECKED human-written per-agent skills (the deadlock demo's no-checker arm).
# FoundryRunner with the unchecked-skills builder; monitored against the canonical
# (safe) protocol so deadlock/off-protocol behaviour is observed.
#
# 2026-08-05 arm rename: this builder now ALSO backs the promoted core arm
# `skills` (see _skills_factory above, same builder). This factory/key
# survives as a LEGACY_SCENARIOS alias so pre-rename `unchecked_skills` run
# dirs stay resolvable.
def _unchecked_skills_factory(case):
    return FoundryRunner(
        case, "unchecked_skills", "WITHOUT-unchecked-skills",
        build_unchecked_skills_instructions)


# Superseded verbose observe-only contract (appendix-only; see LEGACY_SCENARIOS
# docstring below).
_spec_llmvalid_factory = _make_foundry_llm_drafted_factory(
    "valid", "spec_llmvalid", "WITH-spec-llmvalid", build_spec_instructions)


#: (scenario_key, scenario_name, factory(case) -> BaselineRunner)
#: Display + run order is left -> right.
#:
#: THE CORE MATRIX (10 arms) — what `case_runner.py <case>` runs, and the
#: only arms every campaign cell needs. RENAMED 2026-08-05 (project-owner
#: directive, BENCHMARK_PLAN_V3 §10.8 "Final arm naming") from the prior
#: 7-arm matrix: `skills`/`maf_skills` (real skill-file baselines) replace
#: `bare`/`maf_groupchat`; `globalvalid` (ex `global_decentralized`) is
#: promoted from ablation-tier into the core matrix; every remaining arm
#: keeps its role under a uniform `(maf_)?(global|local)valid(_gate|_sched)?`
#: vocabulary; `maf_localvalid_sched` is genuinely new (EFSM-scheduled MAF
#: GroupChat — feasibility confirmed same day, see
#: baselines/maf_groupchat.py's MAFGroupChatRunner docstring). Every arm
#: still answers a question no other arm answers; see the module docstring
#: above for the full old-name/new-name/meaning table.
SCENARIOS: list[tuple[str, str, Callable[..., "BaselineRunner"]]] = [
    # -- no-protocol baselines (real skill files) --------------------------
    ("skills",                 "WITHOUT-skills",              _skills_factory),                    # replaces `bare`
    ("maf_skills",             "WITHOUT-maf-skills",          _maf_skills_factory),                 # replaces `maf_groupchat`
    # -- global-text ladder --------------------------------------------------
    ("globalvalid",            "WITH-globalvalid",            _globalvalid_factory),                # ex `global_decentralized`
    ("maf_globalvalid",        "WITHOUT-maf-globalvalid",     _maf_globalvalid_factory),             # ex `maf_groupchat_llmvalid`
    # -- projected local-contract ladder (the published 5-arm spine) --------
    ("localvalid",             "WITH-localvalid",             _localvalid_factory),                 # ex `min_llmvalid`: + knowledge
    ("maf_localvalid",         "WITHOUT-maf-localvalid-ORCH", _maf_localvalid_factory),              # ex `maf_groupchat_llmvalid_orch`: MAF + STJP artifacts
    ("localvalid_gate",        "WITH-localvalid-GATE",        _localvalid_gate_factory),             # ex `min_llmvalid_gate`: + enforcement
    ("maf_localvalid_gate",    "WITH-maf-localvalid-GATE",    _maf_localvalid_gate_factory),         # MAF + identical contracts + pre-broadcast gate
    ("localvalid_sched",       "WITH-localvalid-SCHED",       _localvalid_sched_factory),            # ex `min_llmvalid_sched`: + scheduling = full STJP
    ("maf_localvalid_sched",   "WITHOUT-maf-localvalid-SCHED", _maf_localvalid_sched_factory),       # NEW: MAF + STJP artifacts + EFSM scheduling
]

#: ABLATION arms — pre-registered mechanism isolations, run via --arms
#: ONLY on the case(s) where their question is live (never in every
#: campaign cell). Each defends one claim. NOT covered by the 2026-08-05
#: rename table (they are not part of the 10-arm canonical matrix); keys
#: unchanged.
#:   min_llmvalid_gate_lastrecv — REQUIRED on >=1 BRANCHING case per
#:       campaign: the scheduling dividend is only honest against the
#:       protocol-free "ask the last receiver" heuristic, not just
#:       round-robin (FAIRNESS_REVIEW Problem 4);
#:   min_llmvalid_gate_nohint — gate minus the per-turn liveness nudge:
#:       separates blocking from hinting (Problem 5); one case suffices;
#:   spec_llmvalid_gate — verbose-contract gate: prices contract
#:       verbosity (ladder setting 5); one case suffices.
ABLATION_SCENARIOS: list[tuple[str, str, Callable[..., "BaselineRunner"]]] = [
    ("min_llmvalid_gate_lastrecv", "WITH-min-GATE-LASTRECV", _min_llmvalid_gate_lastrecv_factory),
    ("min_llmvalid_gate_nohint", "WITH-min-GATE-NOHINT",  _min_llmvalid_gate_nohint_factory),
    ("spec_llmvalid_gate",     "WITH-spec-llmvalid-GATE", _spec_llmvalid_gate_factory),
]

#: LEGACY / APPENDIX arms — excluded from the default matrix, kept
#: resolvable (make_runner, --arms) so pre-2026-08-05-rename AND
#: pre-2026-08-05-repair prompts can be reproduced and the appendix
#: controls invoked explicitly. Why each:
#:   bare / maf_groupchat / global_decentralized / maf_groupchat_llmvalid /
#:       min_llmvalid / maf_groupchat_llmvalid_orch / min_llmvalid_gate /
#:       min_llmvalid_sched / unchecked_skills — pre-2026-08-05-RENAME
#:       aliases: the same factory as the new-named core-matrix arm above,
#:       just resolvable under its old key so pre-rename run dirs
#:       (events_<oldkey>.jsonl, prompts/<oldkey>/) stay summarizable;
#:   *_legacy — the pre-2026-08-05-REPAIR broadcast-intent prompt policy of
#:       the same-named default arm (run one next to its repaired twin to
#:       PRICE the broadcast confound; pre-repair run dirs recorded these
#:       prompts under the unsuffixed keys);
#:   maf_native / maf_foundry — runtime baselines, appendix-only per §5.2;
#:   maf_groupchat_unsafe — the deadlock negative control, run explicitly
#:       where an unsafe draft exists (safety table, never a token claim);
#:   spec_llmvalid — verbose observe-only contract, superseded by
#:       localvalid (same correctness at ~46% of the token cost) and not
#:       a rung of the 8-setting ladder.
LEGACY_SCENARIOS: list[tuple[str, str, Callable[..., "BaselineRunner"]]] = [
    # -- pre-2026-08-05-RENAME aliases (identical factory, old key) --------
    ("bare",                   "WITHOUT-skills",          _foundry_factory("bare", "WITHOUT-skills", build_bare_fairintent_instructions)),
    ("maf_groupchat",          "WITHOUT-maf-groupchat",   _maf_groupchat_factory),
    ("global_decentralized",   "WITH-global-decentralized", _global_decentralized_alias_factory),
    ("maf_groupchat_llmvalid", "WITHOUT-maf-gc-llmvalid", _maf_groupchat_llmvalid_alias_factory),
    ("min_llmvalid",           "WITH-min-llmvalid",       _min_llmvalid_alias_factory),
    ("maf_groupchat_llmvalid_orch", "WITHOUT-maf-gc-llmvalid-ORCH", _maf_groupchat_llmvalid_orch_alias_factory),
    ("min_llmvalid_gate",      "WITH-min-llmvalid-GATE",  _min_llmvalid_gate_alias_factory),
    ("min_llmvalid_sched",     "WITH-min-llmvalid-SCHED", _min_llmvalid_sched_alias_factory),
    ("unchecked_skills",       "WITHOUT-unchecked-skills", _unchecked_skills_factory),
    # -- pre-2026-08-05-REPAIR broadcast-intent twins -----------------------
    ("bare_legacy",            "WITHOUT-skills-LEGACY",   _foundry_factory("bare_legacy", "WITHOUT-skills-LEGACY", build_bare_instructions)),
    ("global_decentralized_legacy", "WITH-global-decentralized-LEGACY", _global_decentralized_legacy_factory),
    ("maf_groupchat_legacy",   "WITHOUT-maf-groupchat-LEGACY", _maf_groupchat_legacy_factory),
    ("maf_groupchat_llmvalid_legacy", "WITHOUT-maf-gc-llmvalid-LEGACY", _maf_groupchat_llmvalid_legacy_factory),
    # -- appendix runtime baselines / negative control / superseded arm ----
    ("maf_native",             "WITHOUT-maf-native",      _maf_native_factory),
    ("maf_foundry",            "WITHOUT-maf-foundry",     _maf_foundry_factory),
    ("maf_groupchat_unsafe",   "WITHOUT-maf-gc-unsafe",   _maf_groupchat_unsafe_factory),
    ("spec_llmvalid",          "WITH-spec-llmvalid",      _spec_llmvalid_factory),
]

#: Every resolvable arm — used by make_runner, --arms validation, and all
#: summarize/eval paths (so run dirs produced before the consolidation stay
#: fully summarizable: those iterators check events-file existence anyway).
ALL_SCENARIOS: list[tuple[str, str, Callable[..., "BaselineRunner"]]] = (
    SCENARIOS + ABLATION_SCENARIOS + LEGACY_SCENARIOS)


def make_runner(case, scenario_key: str) -> "BaselineRunner":
    """Look up any registered arm (default matrix OR legacy) by key."""
    for key, name, factory in ALL_SCENARIOS:
        if key == scenario_key:
            return factory(case)
    raise KeyError(f"unknown scenario_key: {scenario_key!r} "
                   f"(known: {[k for k, _, _ in ALL_SCENARIOS]})")
