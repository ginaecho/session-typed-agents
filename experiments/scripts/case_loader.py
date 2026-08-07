"""
Load a case.yaml into structured Python objects.

A case is the configuration for one benchmarked protocol — the prose intent,
role list, protocol+refinement paths, terminal label, max steps, branch
hints, and goal predicates.

Intent artifacts (optional, produced by scripts/intent_pipeline.py) live under
experiments/cases/<case>/intent/:

    intent.md          document-scale user intent (the realistic input: a
                       stakeholder brief / handbook excerpt, NOT a 5-line
                       paragraph). Provenance recorded in provenance.json:
                       source is either "git" (quoted verbatim from the real
                       use case's own repo) or "llm_authored".
    intent_distilled.md  the interrogation/distillation front-end's output:
                       distilled goal statements + constraints + completion
                       signal, validated for coverage against case.yaml goals.
    role_briefs.yaml   per-role task briefs distilled from the intent — what
                       a worker carries under the fair intent-carrying policy
                       instead of the whole intent document.
    provenance.json    source, sha256s, setup-cost metering, approval flags.

`Case.intent` is ALWAYS the short case.yaml text (legacy arms depend on it
byte-for-byte). The document-scale intent is opt-in via
Case.load(..., intent_scale="doc") / case_runner --intent-scale doc, and is
exposed as `intent_effective`, which equals `intent` at the default scale.
"""

from __future__ import annotations

import json
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


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

    # Intent-scale switch: "short" (case.yaml intent — the default, keeps all
    # legacy arm prompts byte-identical) or "doc" (intent/intent.md document).
    intent_scale: str = "short"
    # Per-role distilled task briefs from intent/role_briefs.yaml ({} if absent).
    role_briefs: dict[str, str] = field(default_factory=dict)
    # intent/provenance.json contents ({} if absent).
    intent_provenance: dict = field(default_factory=dict)

    # Resolved absolute paths
    case_dir: Path = field(default=Path("."))
    protocol_path: Path = field(default=Path("."))
    refinements_path: Path = field(default=Path("."))
    skills_dir: Path = field(default=Path("."))
    runs_dir: Path = field(default=Path("."))
    intent_dir: Path = field(default=Path("."))

    @classmethod
    def load(cls, case_dir: Path | str,
             intent_scale: str = "short") -> "Case":
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
            intent_scale=intent_scale,
            case_dir=case_dir,
            protocol_path=case_dir / "protocols" / f"{version}.scr",
            refinements_path=case_dir / "protocols" / f"{version}.refn",
            skills_dir=case_dir / "skills" / version,
            runs_dir=case_dir / "runs",
            intent_dir=case_dir / "intent",
        )
        if not case.protocol_path.exists():
            raise FileNotFoundError(f"missing protocol: {case.protocol_path}")
        if intent_scale not in ("short", "doc"):
            raise ValueError(f"intent_scale must be 'short' or 'doc', "
                             f"got {intent_scale!r}")
        if intent_scale == "doc" and not case.intent_doc_path.exists():
            raise FileNotFoundError(
                f"intent_scale='doc' but {case.intent_doc_path} is missing. "
                f"Author it first: python experiments/scripts/intent_pipeline.py "
                f"author {case.case_id} [--from-file <real-intent.md>]")
        briefs_path = case.intent_dir / "role_briefs.yaml"
        if briefs_path.exists():
            raw = yaml.safe_load(briefs_path.read_text(encoding="utf-8")) or {}
            case.role_briefs = {str(k): str(v).strip()
                                for k, v in (raw.get("briefs") or raw).items()}
        prov_path = case.intent_dir / "provenance.json"
        if prov_path.exists():
            case.intent_provenance = json.loads(
                prov_path.read_text(encoding="utf-8"))
        case.runs_dir.mkdir(parents=True, exist_ok=True)
        return case

    # ------------------------------------------------------------------
    # Intent artifacts
    # ------------------------------------------------------------------

    @property
    def intent_doc_path(self) -> Path:
        return self.intent_dir / "intent.md"

    @property
    def intent_distilled_path(self) -> Path:
        return self.intent_dir / "intent_distilled.md"

    @property
    def intent_effective(self) -> str:
        """The intent text an arm's *intent-carrying* component receives.

        At the default "short" scale this is exactly `self.intent` (the
        case.yaml paragraph), so every legacy prompt stays byte-identical.
        At "doc" scale it is the full intent/intent.md document.
        """
        if self.intent_scale == "doc":
            return self.intent_doc_path.read_text(encoding="utf-8").strip()
        return self.intent

    def role_brief(self, role: str) -> Optional[str]:
        """Distilled per-role task brief, or None if not distilled yet."""
        return self.role_briefs.get(role)

    def require_role_brief(self, role: str) -> str:
        """Fail-fast brief lookup with a remediation message.

        The repaired fair-intent arms (bare, global_decentralized,
        maf_groupchat, maf_groupchat_llmvalid — post-2026-08-05 prompt
        policy) carry a distilled brief instead of the whole intent; running
        them without the distillation artifact would silently degrade to an
        unusable prompt, so we refuse instead.
        """
        brief = self.role_brief(role)
        if not brief:
            raise FileNotFoundError(
                f"No distilled role brief for {role!r} in "
                f"{self.intent_dir / 'role_briefs.yaml'}. The repaired "
                f"brief-carrying arms need the intent package, which is a "
                f"SEPARATE preprocessing stage — prepare it (unattended) "
                f"before the campaign with: python "
                f"experiments/scripts/intent_pipeline.py synth "
                f"{self.case_id}   (or `synth --all` for every case)")
        return brief

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
