"""
Load a case.yaml into structured Python objects.

A case is the configuration for one benchmarked protocol — the prose intent,
role list, protocol+refinement paths, terminal label, max steps, branch
hints, and goal predicates.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CaseGoal:
    """Goal predicate anchored to a specific (sender, receiver, label) interaction."""
    id: str
    description: str
    metric: str
    predicate: str                  # python expression with `x` bound to payload
    anchor_sender: str
    anchor_receiver: str
    anchor_label: str
    threshold: str
    branch: str = ""                # if set, goal applies only to this branch
    # Goal taxonomy (docs/reference/GOAL_QUALITY_AUDIT.md D-taxonomy). One of:
    #   liveness | ordering | aggregate | data_quality | world_state
    # Optional in case.yaml; auto-inferred by goal_quality.classify_goal when "".
    category: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CaseGoal":
        anchor = d.get("anchor") or {}
        return cls(
            id=d["id"],
            description=d["description"],
            metric=d.get("metric", ""),
            predicate=d["predicate"],
            anchor_sender=anchor.get("sender", ""),
            anchor_receiver=anchor.get("receiver", ""),
            anchor_label=anchor.get("label", ""),
            threshold=d.get("threshold", ""),
            branch=d.get("branch", ""),
            category=d.get("category", ""),
        )


@dataclass
class Case:
    """One benchmark case loaded from case.yaml."""
    case_id: str
    description: str
    version: str
    protocol_name: str               # the Scribble `global protocol <NAME>` declaration
    roles: list[str]
    terminal_label: str
    max_steps: int
    branch_hints: list[str]
    intent: str
    goals: list[CaseGoal] = field(default_factory=list)
    # Prose role descriptions; held-constant across all arms in their prompts
    # so the variable being measured is "what protocol info comes on top".
    # Empty dict if not present in case.yaml.
    role_descriptions: dict[str, str] = field(default_factory=dict)

    # Resolved absolute paths
    case_dir: Path = field(default=Path("."))
    protocol_path: Path = field(default=Path("."))
    refinements_path: Path = field(default=Path("."))
    skills_dir: Path = field(default=Path("."))
    runs_dir: Path = field(default=Path("."))

    @classmethod
    def load(cls, case_dir: Path | str) -> "Case":
        case_dir = Path(case_dir).resolve()
        cfg_path = case_dir / "case.yaml"
        if not cfg_path.exists():
            raise FileNotFoundError(f"missing {cfg_path}")
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        version = cfg.get("version", "v1")

        case = cls(
            case_id=cfg["case_id"],
            description=cfg.get("description", "").strip(),
            version=version,
            protocol_name=cfg["protocol_name"],
            roles=list(cfg["roles"]),
            terminal_label=cfg["terminal_label"],
            max_steps=int(cfg.get("max_steps", 12)),
            branch_hints=list(cfg.get("branch_hints", []) or []),
            intent=cfg.get("intent", "").strip(),
            goals=[CaseGoal.from_dict(g) for g in (cfg.get("goals") or [])],
            role_descriptions=dict(cfg.get("role_descriptions", {}) or {}),
            case_dir=case_dir,
            protocol_path=case_dir / "protocols" / f"{version}.scr",
            refinements_path=case_dir / "protocols" / f"{version}.refn",
            skills_dir=case_dir / "skills" / version,
            runs_dir=case_dir / "runs",
        )
        if not case.protocol_path.exists():
            raise FileNotFoundError(f"missing protocol: {case.protocol_path}")
        case.runs_dir.mkdir(parents=True, exist_ok=True)
        return case

    def goal_set(self):
        """Build a goal_elicitor.GoalSet from this case's goals (for verify_goals_against_trace)."""
        from stjp_core.evaluation.goal_elicitor import GoalSet, Goal
        goals = [Goal(
            id=g.id, description=g.description, metric=g.metric,
            predicate=g.predicate,
            anchor_sender=g.anchor_sender, anchor_receiver=g.anchor_receiver,
            anchor_label=g.anchor_label, threshold=g.threshold,
            branch=g.branch,
        ) for g in self.goals]
        return GoalSet(intent=self.intent, goals=goals)

    def goals_text(self) -> str:
        return "\n".join(f"  - {g.id}: {g.description}" for g in self.goals)


def load_goal_set_from_yaml(yaml_path: Path | str, intent: str):
    """Build a GoalSet from a re-anchored-goals YAML.

    Used by LLM-drafted runners (spec_llmvalid, min_llmvalid,
    maf_groupchat_llmvalid, maf_groupchat_unsafe) whose monitor scores
    traces against a non-canonical protocol with different message labels.
    The re-anchorer (experiments/scripts/re_anchor_goals.py) produces
    these files; format matches the goals: section of case.yaml.
    """
    from stjp_core.evaluation.goal_elicitor import GoalSet, Goal
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    raw_goals = data.get("goals") or []
    goals = []
    for d in raw_goals:
        cg = CaseGoal.from_dict(d)
        goals.append(Goal(
            id=cg.id, description=cg.description, metric=cg.metric,
            predicate=cg.predicate,
            anchor_sender=cg.anchor_sender, anchor_receiver=cg.anchor_receiver,
            anchor_label=cg.anchor_label, threshold=cg.threshold,
            branch=cg.branch,
        ))
    return GoalSet(intent=intent, goals=goals)
