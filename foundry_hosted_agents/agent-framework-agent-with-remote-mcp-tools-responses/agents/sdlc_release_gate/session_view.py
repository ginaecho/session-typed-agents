"""session_view.py — per-turn view/action helpers, copied VERBATIM from
stjp_core/foundry/session_helpers.py (spec §3: "reuse the format of ...
build_view — copy the exact format string into the container"). The Docker
build context for this service is this directory only, so importing
stjp_core directly is not possible; this file is a byte-for-byte copy of the
two pure functions this container needs. Do not edit the format strings here
without also updating the source file (or the two will drift).
"""
from __future__ import annotations

import json
from typing import Optional


def build_view(role: str, history: list[dict], hint: Optional[str]) -> str:
    """Build the per-actor view of session history for one turn.

    Verbatim copy of stjp_core/foundry/session_helpers.py::build_view.
    """
    relevant = [e for e in history
                if e["sender"] == role or e["receiver"] == role]
    lines = [f"You are: {role}"]
    if not relevant:
        lines.append("Session history (your view): (no messages yet)")
    else:
        lines.append("Session history (your view):")
        for i, e in enumerate(relevant, 1):
            payload = f"({e['payload']})" if e['payload'] else "()"
            lines.append(f"  {i}. {e['sender']} -> {e['receiver']} : "
                         f"{e['label']}{payload}")
    if hint:
        lines.append(f"\n(Hint: this scenario is a {hint}-revenue case.)")
    lines.append("\nWhat is your next action? Reply with a single JSON object.")
    return "\n".join(lines)


def parse_action(text: str) -> dict:
    """Lift a JSON action object out of a possibly fenced assistant reply.

    Verbatim copy of stjp_core/foundry/session_helpers.py::parse_action.
    Raises ValueError if no object-shaped substring is present.
    """
    text = (text or "").strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.startswith("```")]
        text = "\n".join(lines).strip()
    s = text.find("{")
    e = text.rfind("}")
    if s < 0 or e < 0:
        raise ValueError(f"No JSON found: {text[:160]}")
    return json.loads(text[s:e + 1])


def parse_action_or_none(text: str) -> Optional[dict]:
    """Best-effort JSON action lift; returns None instead of raising.

    Matches experiments/baselines/maf_groupchat.py::_parse_action — used by
    the MAF loop, where GroupChatBuilder streams every participant/
    orchestrator reply and an unparseable one should just be skipped, not
    abort the trial.
    """
    try:
        return parse_action(text)
    except (ValueError, json.JSONDecodeError):
        return None
