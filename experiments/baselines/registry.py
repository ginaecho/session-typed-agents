"""SCENARIOS registry — single source of truth for which arms case_runner runs.

Adding a new baseline:
  1. Implement a BaselineRunner subclass in baselines/<name>.py
  2. Import the class here.
  3. Add a SCENARIOS entry: (scenario_key, scenario_name, factory).
     The factory takes (case) and returns the constructed runner.

The order here is also the display order in print_summary.
"""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from baselines.foundry_runner import FoundryRunner
from baselines.instructions import (
    build_bare_instructions,
    build_global_spec_instructions,
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


def _maf_groupchat_factory(case):
    from baselines.maf_groupchat import MAFGroupChatRunner
    return MAFGroupChatRunner(case, "maf_groupchat", "WITHOUT-maf-groupchat",
                              instructions_builder=build_bare_instructions)


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


_maf_groupchat_llmvalid_factory = _make_maf_llm_drafted_factory(
    "valid", "maf_groupchat_llmvalid", "WITHOUT-maf-gc-llmvalid")
_maf_groupchat_unsafe_factory = _make_maf_llm_drafted_factory(
    "unsafe", "maf_groupchat_unsafe", "WITHOUT-maf-gc-unsafe")

_spec_llmvalid_factory = _make_foundry_llm_drafted_factory(
    "valid", "spec_llmvalid", "WITH-spec-llmvalid", build_spec_instructions)
_min_llmvalid_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid", "WITH-min-llmvalid", build_spec_minimal_instructions)
_spec_llmvalid_gate_factory = _make_foundry_llm_drafted_factory(
    "valid", "spec_llmvalid_gate", "WITH-spec-llmvalid-GATE",
    build_spec_instructions, gate=True)
# GATE on the LEAN projected contract (same enforcement as spec_llmvalid_gate,
# same prompt as min_llmvalid). Decomposes contract-verbosity from enforcement:
# min_llmvalid vs min_llmvalid_gate isolates the gate on identical prompts.
_min_llmvalid_gate_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_gate", "WITH-min-llmvalid-GATE",
    build_spec_minimal_instructions, gate=True)
# The full STJP execution plane: lean projected contract + enforcement gate +
# EFSM enabled-sender scheduling. The scheduler is derived STATICALLY from the
# same projection that generates each role's prompt — a global-text arm cannot
# construct it without adding an LLM orchestrator. min_llmvalid_gate vs
# min_llmvalid_sched isolates the scheduler on identical prompts + enforcement.
_min_llmvalid_sched_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_sched", "WITH-min-llmvalid-SCHED",
    build_spec_minimal_instructions, gate=True, schedule="efsm")
# CHEAP-HEURISTIC scheduling control: same prompt + gate as
# min_llmvalid_sched, but the next actor is chosen by "ask whoever just
# received a message" (round-robin fallback) — a rule that needs NO
# protocol. min_llmvalid_gate_lastrecv vs min_llmvalid_sched isolates what
# the protocol-derived EFSM scheduler adds beyond this trivial heuristic
# (expected: little on linear pipelines, a real gap on branching / fan-in /
# concurrent cases). See docs/BENCHMARK_FAIRNESS_REVIEW.md, Problem 4.
_min_llmvalid_gate_lastrecv_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_gate_lastrecv", "WITH-min-GATE-LASTRECV",
    build_spec_minimal_instructions, gate=True, schedule="lastreceiver")
# HINTS ablation: same prompt + gate as min_llmvalid_gate, but WITHOUT the
# per-turn liveness nudge ("you are at state N; the available action is
# SEND X to Y"). min_llmvalid_gate vs min_llmvalid_gate_nohint separates
# pure enforcement (block + explain rejections) from per-turn ground-truth
# guidance. See docs/BENCHMARK_FAIRNESS_REVIEW.md, Problem 5.
_min_llmvalid_gate_nohint_factory = _make_foundry_llm_drafted_factory(
    "valid", "min_llmvalid_gate_nohint", "WITH-min-GATE-NOHINT",
    build_spec_minimal_instructions, gate=True, hints=False)
# Global protocol text, but on the DECENTRALIZED round-robin runner (no central
# orchestrator) — the "B with autonomous local agents" control. Isolates
# "global text vs projected local contract" from "orchestrated vs decentralized":
# compare against spec_llmvalid (local types, same runner) and against
# maf_groupchat_llmvalid (global text, orchestrated). See
# docs/WHY_B_MATCHES_C_ANALYSIS.md (orchestration confound).
_global_decentralized_factory = _make_foundry_llm_drafted_factory(
    "valid", "global_decentralized", "WITH-global-decentralized",
    build_global_spec_instructions)


# UNCHECKED human-written per-agent skills (the deadlock demo's no-checker arm).
# FoundryRunner with the unchecked-skills builder; monitored against the canonical
# (safe) protocol so deadlock/off-protocol behaviour is observed.
def _unchecked_skills_factory(case):
    return FoundryRunner(
        case, "unchecked_skills", "WITHOUT-unchecked-skills",
        build_unchecked_skills_instructions)


#: (scenario_key, scenario_name, factory(case) -> BaselineRunner)
#: Display + run order is left -> right.
#:
#: 8-arm matrix focused on the LLM + Scribble-validator pipeline. Canonical
#: (human-written) protocol arms were intentionally removed: this experiment
#: tests "does the LLM+validator co-design produce a usable session type?",
#: not "do session types work" (we already showed that for code_review).
#:
#: Pairwise comparisons:
#:   - 1-4 vs 6  : does giving agents a validated global type beat intent only?
#:   - 5 vs 6    : does Scribble validation matter? (unsafe vs validated text)
#:   - 6 vs 7-8  : does projection earn its keep on top of validated global type?
#:
#: The "_llmvalid"/"_unsafe" arms require the artefacts produced by
#: experiments/scripts/draft_llm_protocols.py; their factories return runners
#: that fail-fast (clear error at setup()) if the .scr files don't exist.
SCENARIOS: list[tuple[str, str, Callable[..., "BaselineRunner"]]] = [
    ("bare",                   "WITHOUT-skills",          _foundry_factory("bare", "WITHOUT-skills",     build_bare_instructions)),
    ("maf_native",             "WITHOUT-maf-native",      _maf_native_factory),
    ("maf_foundry",            "WITHOUT-maf-foundry",     _maf_foundry_factory),
    ("maf_groupchat",          "WITHOUT-maf-groupchat",   _maf_groupchat_factory),
    ("maf_groupchat_unsafe",   "WITHOUT-maf-gc-unsafe",   _maf_groupchat_unsafe_factory),
    ("maf_groupchat_llmvalid", "WITHOUT-maf-gc-llmvalid", _maf_groupchat_llmvalid_factory),
    ("unchecked_skills",       "WITHOUT-unchecked-skills", _unchecked_skills_factory),
    ("global_decentralized",   "WITH-global-decentralized", _global_decentralized_factory),
    ("spec_llmvalid",          "WITH-spec-llmvalid",      _spec_llmvalid_factory),
    ("min_llmvalid",           "WITH-min-llmvalid",       _min_llmvalid_factory),
    ("spec_llmvalid_gate",     "WITH-spec-llmvalid-GATE", _spec_llmvalid_gate_factory),
    ("min_llmvalid_gate",      "WITH-min-llmvalid-GATE",  _min_llmvalid_gate_factory),
    ("min_llmvalid_gate_nohint", "WITH-min-GATE-NOHINT",  _min_llmvalid_gate_nohint_factory),
    ("min_llmvalid_gate_lastrecv", "WITH-min-GATE-LASTRECV", _min_llmvalid_gate_lastrecv_factory),
    ("min_llmvalid_sched",     "WITH-min-llmvalid-SCHED", _min_llmvalid_sched_factory),
]


def make_runner(case, scenario_key: str) -> "BaselineRunner":
    """Look up SCENARIOS by key and build the runner for this case."""
    for key, name, factory in SCENARIOS:
        if key == scenario_key:
            return factory(case)
    raise KeyError(f"unknown scenario_key: {scenario_key!r} "
                   f"(known: {[k for k, _, _ in SCENARIOS]})")
