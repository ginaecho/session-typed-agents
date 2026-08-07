"""experiments.baselines — per-framework runners for the case_runner benchmark.

A "baseline" is one way of driving an N-role multi-agent pipeline for a given
Case. We compare baselines against each other (and against the session-typed
WITH-spec arms) to measure: how often do agents complete the goal, how many
attempts does it take, how many tokens does it cost?

Each runner implements BaselineRunner (see base.py). The full scenario set
lives in registry.py.

Current scenarios:
  WITHOUT-side (no protocol spec):
    - bare         : Foundry Agent Service, free-form prompt only
    - maf_native   : Microsoft Agent Framework (GroupChat) -> Azure OpenAI direct
    - maf_foundry  : Microsoft Agent Framework (GroupChat) -> Foundry agents
  WITH-side (projected local types + refinement guards):
    - spec         : Foundry Agent Service, verbose Claude-style spec
    - min          : Foundry Agent Service, minimal SEND/RECV spec
"""

from baselines.base import BaselineRunner, AttemptResult
from baselines.registry import (SCENARIOS, ABLATION_SCENARIOS,
                                LEGACY_SCENARIOS, ALL_SCENARIOS, make_runner)

__all__ = ["BaselineRunner", "AttemptResult", "SCENARIOS",
           "ABLATION_SCENARIOS", "LEGACY_SCENARIOS", "ALL_SCENARIOS",
           "make_runner"]
