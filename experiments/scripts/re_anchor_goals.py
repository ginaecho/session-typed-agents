"""re_anchor_goals.py — LLM-assisted goal re-anchoring.

For each canonical goal (from case.yaml), ask an LLM to map it to a
(sender, receiver, label) tuple in a target protocol — or mark it
"no_equivalent" if the new protocol has no edge that preserves the goal's
semantic intent. Save the re-anchored goal set as a YAML alongside the
target .scr.

Used by Tier 2 of the LLM+validator experiment so the spec_llmvalid /
maf_groupchat_llmvalid arms can be scored against goals that match their
own protocol's labels (rather than the canonical's).

Usage:
  python scripts/re_anchor_goals.py <case_id> <kind>
  python scripts/re_anchor_goals.py finance valid
  python scripts/re_anchor_goals.py finance unsafe
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv


HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
TESTING_IDEAS = EXPERIMENTS_DIR.parent
STJP_CORE = TESTING_IDEAS / "stjp_core"
CASES_DIR = EXPERIMENTS_DIR / "cases"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TESTING_IDEAS))
load_dotenv(STJP_CORE / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# NOTE: LLMClient is imported lazily inside re_anchor() so that the
# no-LLM `--check` mode works without the Azure/OpenAI stack installed.
from case_loader import Case
from stjp_core.compiler.protocol_parser import parse_protocol_file


def _valid_edges(scr_path: Path) -> set[tuple[str, str, str]]:
    """Set of (sender, receiver, label) tuples that appear in the protocol.

    The re-anchorer's LLM tends to invent role pairs (e.g. picking
    `TaxSpecialist -> RevenueAnalyst : NotificationBranch` when the protocol
    actually has NotificationBranch going the other way). We validate each
    suggested anchor against this set and retry with feedback if it lies.
    """
    parsed = parse_protocol_file(scr_path)
    return {(m.sender, m.receiver, m.message_name) for m in parsed.messages}


def _edges_summary(edges: set[tuple[str, str, str]]) -> str:
    """Bulleted list of valid edges, for showing the LLM on retry."""
    return "\n".join(f"  - {s} -> {r} : {l}" for s, r, l in sorted(edges))


def _edge_types(scr_path: Path) -> dict[tuple[str, str, str], str]:
    """Map each (sender, receiver, label) edge to its payload type name."""
    parsed = parse_protocol_file(scr_path)
    return {(m.sender, m.receiver, m.message_name): (m.payload_type or "")
            for m in parsed.messages}


def check_invariance(case: Case, goals_data: dict,
                     scr_path: Path) -> tuple[list[str], list[str]]:
    """Verify a re-anchored goal set only re-points anchors — never
    changes what it takes to pass.

    Why this exists: re-anchoring must not make the exam easier for the
    protocol arms. A real example of the drift this catches — the finance
    goal "tax verifier must approve explicitly" was once re-anchored with
    an extra accepted answer ('"true" in x') that the canonical goal set
    (used to grade the bare arm) did not accept. Different answer keys
    make the arms incomparable.

    Returns (errors, warnings):
      errors   — predicate/branch changed although the anchor's payload
                 type is the SAME as the canonical one (pure weakening or
                 tightening; comparability is broken). Also structural
                 problems: unknown goal id, anchor not an edge of the
                 target protocol.
      warnings — predicate changed AND the payload type changed too (e.g.
                 canonical String -> drafted Bool). The change may be a
                 legitimate type translation ('"approved" in x' cannot
                 match a payload that is only ever "True"/"False"), but a
                 human must confirm it does not also weaken the goal.
    """
    errors: list[str] = []
    warnings: list[str] = []
    canon = {g.id: g for g in case.goals}
    canon_types = _edge_types(case.protocol_path)
    new_types = _edge_types(scr_path)

    for d in goals_data.get("goals", []):
        gid = d.get("id", "?")
        g = canon.get(gid)
        if g is None:
            errors.append(f"{gid}: no canonical goal with this id in case.yaml")
            continue
        anchor = d.get("anchor") or {}
        tup = (anchor.get("sender"), anchor.get("receiver"),
               anchor.get("label"))
        if tup not in new_types:
            errors.append(f"{gid}: anchor {tup[0]} -> {tup[1]} : {tup[2]} "
                          f"is not an edge of {scr_path.name}")
            continue
        if (d.get("branch") or "") != (g.branch or ""):
            errors.append(f"{gid}: branch changed "
                          f"{g.branch!r} -> {d.get('branch')!r}")
        pred = (d.get("predicate") or "").strip()
        if pred == g.predicate.strip():
            continue
        old_t = canon_types.get(
            (g.anchor_sender, g.anchor_receiver, g.anchor_label), "")
        new_t = new_types[tup]
        if (new_t or "") == (old_t or ""):
            errors.append(
                f"{gid}: predicate changed although the payload type is the "
                f"same ({old_t or 'none'}): canonical {g.predicate!r} vs "
                f"re-anchored {pred!r} — this changes the pass condition, "
                f"not the anchor")
        else:
            warnings.append(
                f"{gid}: predicate translated with a payload type change "
                f"({old_t or 'none'} -> {new_t or 'none'}): {g.predicate!r} "
                f"-> {pred!r} — confirm the translation does not weaken "
                f"the goal")
    return errors, warnings


SYSTEM = """You are a session-types analyst. Given a goal (a predicate over
a specific message in a multi-party protocol) and a NEW global protocol
written in Scribble, map the goal to the message in the new protocol that
best preserves the goal's semantic intent.

You MUST reply with a single JSON object, no prose. Schema:
{
  "no_equivalent": false,
  "sender": "RoleName",
  "receiver": "RoleName",
  "label": "MessageLabel",
  "predicate": "python expr with x bound to the payload",
  "threshold": "<short human description>"
}

If the new protocol has no message that can carry the goal's intent, reply:
{"no_equivalent": true, "reason": "<one sentence>"}

Rules:
- Use ONLY message labels, role names, and payload types that appear in
  the new protocol. Do not invent.
- **At runtime, `x` is ALWAYS a Python string** — the verifier serialises
  every payload via `str(...)` before evaluating the predicate. Even for
  Bool or Double payload types in the Scribble protocol, `x` will be a
  string like "True", "False", "50000.0", etc. Write predicates that
  parse from string. Examples by Scribble payload type:
    Bool        -> `x.lower() == "true"`   (NEVER `x is True`)
    Int/Double  -> `float(x) > 50000`      (NEVER `x > 50000`)
    String      -> `len(x) > 0` or `"approved" in x.lower()`
- If a goal anchored to (sender_A → receiver_B : label_X) maps to a
  message between different roles in the new protocol, that's fine —
  pick the role pair that carries the goal's *meaning*.
- Prefer messages that appear in EVERY branch (so the goal is reachable
  on any protocol execution).
"""


USER_TEMPLATE = """Canonical goal (anchored to the ORIGINAL protocol):
  id: {gid}
  description: {description}
  metric: {metric}
  predicate: {predicate}
  anchor: sender={sender}, receiver={receiver}, label={label}
  threshold: {threshold}

NEW protocol (Scribble source):
---
{scribble}
---

Map this goal to one message in the NEW protocol. Reply with JSON only.
"""


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.startswith("```")).strip()
    s = text.find("{")
    e = text.rfind("}")
    if s < 0 or e < 0:
        raise ValueError(f"No JSON found in re-anchor reply: {text[:200]}")
    return json.loads(text[s:e + 1])


def re_anchor(case: Case, kind: str) -> dict:
    drafts_dir = case.case_dir / "protocols" / "llm_drafts" / kind
    scr_path = drafts_dir / "v1.scr"
    if not scr_path.exists():
        raise FileNotFoundError(
            f"missing {scr_path}; run draft_llm_protocols.py first")
    out_path = drafts_dir / "goals.yaml"

    new_scribble = scr_path.read_text(encoding="utf-8")
    edges = _valid_edges(scr_path)
    edge_types = _edge_types(scr_path)
    canon_types = _edge_types(case.protocol_path)
    print(f"  source protocol: {scr_path.relative_to(TESTING_IDEAS)}")
    print(f"  output:          {out_path.relative_to(TESTING_IDEAS)}")
    print(f"  canonical goals: {len(case.goals)}")
    print(f"  protocol edges:  {len(edges)}")
    print()

    from stjp_core.foundry.llm_client import LLMClient
    llm = LLMClient()
    new_goals: list[dict] = []
    dropped: list[dict] = []

    MAX_RETRIES = 3

    for g in case.goals:
        print(f"  -> mapping {g.id} ({g.description[:60]})")
        base_user_msg = USER_TEMPLATE.format(
            gid=g.id, description=g.description, metric=g.metric,
            predicate=g.predicate, sender=g.anchor_sender,
            receiver=g.anchor_receiver, label=g.anchor_label,
            threshold=g.threshold, scribble=new_scribble,
        )
        user_msg = base_user_msg
        mapped = None
        outcome = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                reply = llm.generate(SYSTEM, user_msg)
                cand = _extract_json(reply)
            except Exception as e:
                print(f"     attempt {attempt}: LLM/parse error: "
                      f"{type(e).__name__}: {e}")
                continue

            if cand.get("no_equivalent"):
                mapped = cand
                outcome = "no_equivalent"
                break

            tup = (cand.get("sender"), cand.get("receiver"), cand.get("label"))
            if tup in edges:
                mapped = cand
                outcome = "ok"
                break

            # Invalid anchor — retry with explicit feedback so the LLM doesn't
            # repeat the same fabrication.
            print(f"     attempt {attempt}: picked impossible edge "
                  f"{tup[0]} -> {tup[1]} : {tup[2]} — retrying with edge list")
            user_msg = (
                base_user_msg
                + f"\n\nYour previous reply picked the tuple "
                  f"(sender={tup[0]}, receiver={tup[1]}, label={tup[2]}). "
                  f"That edge DOES NOT EXIST in the protocol.\n"
                + f"Choose from one of these existing edges (or reply "
                  f"no_equivalent if none fit):\n"
                + _edges_summary(edges)
            )

        if mapped is None:
            print(f"     gave up after {MAX_RETRIES} retries; marking no_equivalent")
            dropped.append({"id": g.id,
                            "reason": f"LLM kept picking impossible edges "
                                      f"after {MAX_RETRIES} retries"})
            continue

        if outcome == "no_equivalent":
            reason = mapped.get("reason", "(no reason given)")
            print(f"     no_equivalent: {reason}")
            dropped.append({"id": g.id, "reason": reason})
            continue

        # Build the case.yaml-shaped goal dict. Invariance rule: only the
        # ANCHOR may change. The predicate (the pass condition) stays the
        # canonical one whenever the new anchor carries the same payload
        # type — otherwise every arm sits a different exam. The LLM's
        # rewritten predicate is kept ONLY when the payload type changed
        # (e.g. canonical String -> drafted Bool, where '"approved" in x'
        # can never match a payload that is only ever "True"/"False"),
        # and that case is recorded in `predicate_note` for human review.
        tup = (mapped["sender"], mapped["receiver"], mapped["label"])
        old_type = canon_types.get(
            (g.anchor_sender, g.anchor_receiver, g.anchor_label), "")
        new_type = edge_types.get(tup, "")
        goal_out = {
            "id": g.id,
            "description": g.description,
            "metric": g.metric,
            "predicate": g.predicate,
            "anchor": {
                "sender": mapped["sender"],
                "receiver": mapped["receiver"],
                "label": mapped["label"],
            },
            "threshold": g.threshold,
        }
        if g.branch:
            goal_out["branch"] = g.branch
        llm_pred = (mapped.get("predicate") or "").strip()
        if llm_pred and llm_pred != g.predicate.strip():
            if (new_type or "") == (old_type or ""):
                print(f"     NOTE: discarding LLM predicate rewrite "
                      f"{llm_pred!r} (payload type unchanged: "
                      f"{old_type or 'none'}); keeping canonical")
            else:
                goal_out["predicate"] = llm_pred
                goal_out["threshold"] = mapped.get("threshold", g.threshold)
                goal_out["predicate_note"] = (
                    f"translated from canonical {g.predicate!r} because the "
                    f"payload type changed {old_type or 'none'} -> "
                    f"{new_type or 'none'}; review that it does not weaken "
                    f"the goal")
        new_goals.append(goal_out)
        print(f"     -> {mapped['sender']} -> {mapped['receiver']} : "
              f"{mapped['label']}  predicate={goal_out['predicate'][:50]}")

    # Write YAML — same shape as the goals: section of case.yaml so we can
    # reuse CaseGoal.from_dict to load it back.
    out_data = {
        "source_protocol": str(scr_path.relative_to(TESTING_IDEAS)),
        "re_anchored_from": str(case.case_dir.relative_to(TESTING_IDEAS) / "case.yaml"),
        "n_canonical_goals": len(case.goals),
        "n_kept": len(new_goals),
        "n_dropped": len(dropped),
        "dropped": dropped,
        "goals": new_goals,
    }
    # Invariance gate: refuse to write a goal set that changed pass
    # conditions rather than anchors. Warnings (type-translated
    # predicates) are printed but do not block.
    errors, warns = check_invariance(case, out_data, scr_path)
    for w in warns:
        print(f"  WARNING: {w}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
        raise SystemExit(
            f"re-anchored goals failed the invariance check "
            f"({len(errors)} error(s) above); nothing written")
    out_path.write_text(yaml.safe_dump(out_data, sort_keys=False),
                        encoding="utf-8")
    print()
    print(f"  WROTE {out_path.relative_to(TESTING_IDEAS)}")
    print(f"  kept {len(new_goals)} / {len(case.goals)} goals "
          f"({len(dropped)} marked no_equivalent)")
    return out_data


def check_existing(case: Case, kind: str) -> int:
    """Audit an already-written goals.yaml against the invariance rule.

    No LLM calls. Returns the number of errors (0 = comparable answer keys).
    """
    drafts_dir = case.case_dir / "protocols" / "llm_drafts" / kind
    scr_path = drafts_dir / "v1.scr"
    goals_path = drafts_dir / "goals.yaml"
    if not goals_path.exists():
        print(f"  nothing to check: {goals_path} does not exist")
        return 0
    goals_data = yaml.safe_load(goals_path.read_text(encoding="utf-8"))
    errors, warns = check_invariance(case, goals_data, scr_path)
    for w in warns:
        print(f"  WARNING: {w}")
    for e in errors:
        print(f"  ERROR: {e}")
    if not errors and not warns:
        print(f"  OK: {goals_path.relative_to(TESTING_IDEAS)} only re-points "
              f"anchors; pass conditions match case.yaml")
    elif not errors:
        print(f"  OK with {len(warns)} warning(s): predicate translations "
              f"follow payload-type changes; review them once")
    return len(errors)


def main():
    args = sys.argv[1:]
    check_only = "--check" in args
    args = [a for a in args if a != "--check"]
    if len(args) < 2:
        print("usage: re_anchor_goals.py <case_id> <kind:valid|unsafe> [--check]")
        print("  --check: audit the existing goals.yaml against case.yaml "
              "(no LLM calls); exit 1 on invariance errors.")
        sys.exit(2)
    case_id, kind = args[0], args[1]
    if kind not in ("valid", "unsafe"):
        print(f"kind must be 'valid' or 'unsafe', got {kind!r}")
        sys.exit(2)
    case = Case.load(CASES_DIR / case_id)
    print("=" * 72)
    print(f"  {'CHECK' if check_only else 'RE-ANCHOR'} GOALS  "
          f"case={case.case_id}  kind={kind}")
    print("=" * 72)
    if check_only:
        sys.exit(1 if check_existing(case, kind) else 0)
    re_anchor(case, kind)


if __name__ == "__main__":
    main()
