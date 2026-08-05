"""skill.py — turn a validated episode into a reusable SKILL.

This is the point of the loop, and the thing that was missing. A run is not
finished when a protocol validates; it is finished when what the run LEARNED
is written down in a form that makes the next run cheaper:

  the protocol      the Scribble global type the validator accepted, with
                    its guard sidecar — the artifact itself.
  the decisions     every question the loop had to ask, and the answer the
                    user gave. These are the facts that were NOT in the
                    original document; without them the next person starts
                    from the same ambiguity.
  the lessons       every rejection the REAL validator produced, paired
                    with what fixed it. This is the LLM's learning, in the
                    validator's own words, and it is what `optimize.py`
                    folds back into the drafter's prompt so the same
                    mistake is not made twice.
  the shape         roles (with what each must not do), interactions,
                    goals — so a reader can review the coordination without
                    reading Scribble.

Written as Markdown with YAML front matter, i.e. the same artifact class
the paper is about: a natural-language coordination document. The
difference from the ones found in the wild is that this one was
type-checked before it was written, and it carries the evidence.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _lessons_from_attempts(attempts: list[dict]) -> list[dict]:
    """(rejection, what changed next) for every attempt the validator
    refused. The pair is what makes it a lesson rather than a complaint."""
    out = []
    for prev, nxt in zip(attempts, attempts[1:]):
        if prev.get("valid"):
            continue
        msg = str(prev.get("validator_msg", "")).strip()
        if not msg:
            continue
        out.append({
            "attempt": prev.get("k"),
            "validator_said": msg.splitlines()[0][:200],
            "outcome": ("accepted next" if nxt.get("valid")
                        else "still rejected"),
        })
    return out


def build_skill(record: dict, *, checks: Optional[dict] = None,
                decisions: Optional[list[dict]] = None,
                validator_label: str = "scribble-java",
                intent_name: str = "") -> str:
    """Render the SKILL.md for one episode."""
    d = record.get("distilled") or {}
    faith = record.get("faithfulness") or {}
    attempts = record.get("draft_attempts") or []
    lessons = _lessons_from_attempts(attempts)
    valid = bool(record.get("valid"))
    name = (intent_name or (d.get("mission", "") or "coordination")
            ).strip().split("\n")[0][:60]

    L: list[str] = []
    L += ["---",
          f"name: {record.get('episode_id', 'episode')}",
          f"description: {name}",
          f"validated_by: {validator_label}",
          f"protocol_valid: {str(valid).lower()}",
          f"generated: {_now()}",
          "---", ""]

    L += [f"# {name}", "",
          "> This skill was **type-checked before it was written**. The "
          "protocol below was accepted by the real Scribble checker; the "
          "rejections it survived are recorded at the end so the same "
          "mistakes are not repeated.", ""]

    if not valid:
        L += ["> **WARNING — the protocol below was NEVER ACCEPTED by the "
              "validator.** It is recorded so the failure can be studied, "
              "not so it can be used. Everything after this line is a "
              "draft, not a contract.", ""]

    L += ["## Mission", d.get("mission", "—"), ""]

    roles = d.get("roles") or []
    if roles:
        L += ["## Roles", "",
              "| Role | Kind | Job | Must not |", "|---|---|---|---|"]
        for r in roles:
            L.append(f"| **{r.get('name', '')}** | {r.get('kind', 'agent')} "
                     f"| {str(r.get('description', '')).replace('|', '/')} "
                     f"| {'; '.join(r.get('must_not', [])) or '—'} |")
        L.append("")

    goals = d.get("goals") or []
    if goals:
        L += ["## Goals — what must be true at the end", ""]
        for g in goals:
            L.append(f"- **{g.get('gid')}**{' (FINAL)' if g.get('final') else ''} "
                     f"{g.get('text', '')}"
                     + (f" — signalled by `{g.get('marker')}`"
                        if g.get("marker") else ""))
        L.append("")

    inters = d.get("interactions") or []
    if inters:
        L += ["## Interactions", "",
              "| # | From → To | What | Carries | How often |",
              "|---|---|---|---|---|"]
        for i in inters:
            carries = "; ".join(
                f"{f.get('name')}: {f.get('type', 'string')}"
                + (f" ({f.get('constraint')})" if f.get("constraint") else "")
                for f in i.get("carries", [])) or "—"
            L.append(f"| {i.get('iid')} | {i.get('sender')} → "
                     f"{i.get('receiver')}"
                     f"{' *(conditional)*' if i.get('optional') else ''} "
                     f"| {str(i.get('what', '')).replace('|', '/')} "
                     f"| {carries} | {i.get('cardinality') or '—'} |")
        L.append("")

    invs = d.get("invariants") or []
    if invs:
        L += ["## Session invariants — must hold for the whole run", ""]
        L += [f"- **{v.get('name')}**: {v.get('bound')}"
              + (f" (resets on {v.get('resets_on')})" if v.get("resets_on")
                 else "")
              + (f" — on breach: {v.get('on_breach')}" if v.get("on_breach")
                 else "") for v in invs]
        L.append("")

    if record.get("final_protocol"):
        L += ["## The protocol", "",
              f"Accepted by `{validator_label}`." if valid
              else "**Not accepted by the validator.**", "",
              "```scribble", record["final_protocol"].strip(), "```", ""]

    if decisions:
        L += ["## Decisions taken during authoring", "",
              "Facts that were NOT in the original document — the loop had "
              "to ask. Anyone reusing this skill inherits these answers "
              "instead of rediscovering the ambiguity.", ""]
        for i, qa in enumerate(decisions, start=1):
            L += [f"{i}. **{qa.get('question', '').strip()}**",
                  f"   {qa.get('answer', '').strip()}"]
        L.append("")

    if lessons:
        L += ["## What the validator taught us", "",
              "Each line is a real rejection by the real checker, and what "
              "happened next. These feed the drafter's rulebook so the same "
              "error is not repeated.", "",
              "| Attempt | The checker said | Outcome |", "|---|---|---|"]
        for x in lessons:
            L.append(f"| {x['attempt']} | `{x['validator_said']}` "
                     f"| {x['outcome']} |")
        L.append("")

    if checks:
        blockers = [f for f in checks.get("findings", [])
                    if f.get("severity") == "blocker"]
        L += ["## Structural review", "",
              f"- turn order: {checks.get('turn_order', {}).get('polling', {}).get('enabled_polls', '?')} "
              f"enabled polls vs "
              f"{checks.get('turn_order', {}).get('polling', {}).get('round_robin_polls', '?')} "
              f"round-robin — "
              f"{checks.get('turn_order', {}).get('polling', {}).get('wasted_polls', '?')} "
              f"calls a protocol-driven scheduler never makes",
              f"- structural blockers: {len(blockers)}"]
        for b in blockers:
            L.append(f"  - **{b.get('kind')}** at {b.get('where')}: "
                     f"{b.get('detail', '')[:180]}")
        L.append("")

    if faith:
        scope = faith.get("scope") or {}
        L += ["## Faithfulness to the intent", "",
              f"- requirements graded: {scope.get('graded', '?')} "
              f"(recall {round((faith.get('recall') or 0) * 100)}%)",
              f"- reported but not graded: {scope.get('policy', 0)} policy, "
              f"{scope.get('interior', 0)} intra-role interior",
              f"- back-translation: "
              f"{(faith.get('backtranslation') or {}).get('score', '?')}/100",
              f"- verdict: **{'faithful' if faith.get('faithful') else 'not faithful'}**",
              "", f"> {faith.get('rule', '')}", ""]

    L += ["---", "",
          "*Generated by the STJP intent loop: interrogate the stakeholder, "
          "distil typed requirements, draft a Scribble global type, prove "
          "it with the real checker, and record what was learned.*"]
    return "\n".join(L) + "\n"


def write_skill(session_dir: Path, record: dict, **kwargs) -> Path:
    path = session_dir / "SKILL.md"
    path.write_text(build_skill(record, **kwargs), encoding="utf-8")
    return path


def collect_decisions(session_dir: Path) -> list[dict]:
    """Every Q&A that shaped this episode: the interrogation rounds plus
    any refinement answers recorded by a later pass."""
    out: list[dict] = []
    tr = session_dir / "transcript.json"
    if tr.exists():
        try:
            data = json.loads(tr.read_text(encoding="utf-8"))
            for qa in data.get("transcript", []):
                out.append({"question": qa.get("question", ""),
                            "answer": qa.get("answer", "")})
        except json.JSONDecodeError:
            pass
    dec = session_dir / "decisions.json"
    if dec.exists():
        try:
            for a in json.loads(dec.read_text(encoding="utf-8")
                                ).get("answers", []):
                out.append({"question": a.get("question", ""),
                            "answer": a.get("answer", "")})
        except json.JSONDecodeError:
            pass
    return out
