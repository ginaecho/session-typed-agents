"""fragile_goal_audit.py — detect FRAGILE goal predicates across all cases.

A goal is FRAGILE (measurement artifact, not a real failure) when, in a trace
that reached the terminal with ~zero violations, the goal's anchor message WAS
actually sent (matching sender->receiver:label) but the predicate REJECTS its
payload. That means the right thing happened and the check is too strict — the
finance G3 == "true" bug.

This is distinct from a REAL failure, where the anchor message is ABSENT (the
obligation was skipped / a branch not taken).

For each case's newest completed run, for each goal, per setting, we classify:
  PASS      - anchor sent, predicate accepts
  FRAGILE   - anchor sent (>=1 matching event) in a clean-terminal setting,
              predicate rejects ALL of them   <-- the bug we hunt
  ABSENT    - no anchor message at all (real miss / branch)
and print the rejected payloads as the proof.

Usage: python fragile_goal_audit.py <case_id> <run_dir>
"""
import json
import sys
from pathlib import Path

EXP = Path(r"c:/Users/tzuchunchen/Documents/05_Research/EAG/eag-innovation/agentic-governance/stjp/experiments")
sys.path.insert(0, str(EXP / "scripts"))
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(EXP.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import yaml
from stjp_core.compiler.refinement_checker import Refinement


def load_goals(case_dir: Path):
    for gp in [case_dir / "protocols" / "llm_drafts" / "valid" / "goals.yaml",
               case_dir / "case.yaml"]:
        if gp.exists():
            d = yaml.safe_load(gp.read_text(encoding="utf-8"))
            goals = d.get("goals") if isinstance(d, dict) else d
            if goals:
                term = None
                if gp.name == "case.yaml":
                    term = d.get("terminal_label")
                return goals, term
    return [], None


def trace_events(path: Path):
    """All delivered (non-marker) events across all trials in a settings file."""
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("marker") or not e.get("sender"):
            continue
        out.append(e)
    return out


def violations_in(path: Path):
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("marker"):
            continue
        if e.get("violation"):
            n += 1
    return n


def audit(case_id: str, run_dir: Path):
    case_dir = EXP / "cases" / case_id
    goals, term = load_goals(case_dir)
    if not goals:
        print(f"  {case_id}: no goals found"); return []
    settings = sorted(p.stem.replace("events_", "")
                      for p in run_dir.glob("events_*.jsonl"))
    findings = []
    for g in goals:
        gid = g["id"]; a = g.get("anchor", {})
        s, r, lab, pred = a.get("sender"), a.get("receiver"), a.get("label"), g["predicate"]
        refn = Refinement(sender=s, receiver=r, label=lab, predicates=[pred])
        for setting in settings:
            ev = trace_events(run_dir / f"events_{setting}.jsonl")
            if not ev:
                continue
            matching = [e for e in ev if e["sender"] == s and e["receiver"] == r
                        and e["label"] == lab]
            if not matching:
                continue  # ABSENT — not a fragility signal
            passes = [m for m in matching if refn.check(str(m.get("payload", "")))[0]]
            if passes:
                continue  # PASS
            # anchor sent but predicate rejects ALL — fragility suspect.
            reached_term = (term is None) or any(e["label"] == term for e in ev)
            viols = violations_in(run_dir / f"events_{setting}.jsonl")
            if reached_term:
                sample = [str(m.get("payload", ""))[:55] for m in matching[:2]]
                findings.append({
                    "case": case_id, "goal": gid, "setting": setting,
                    "predicate": pred, "rejected_payloads": sample,
                    "n_matching": len(matching), "violations": viols,
                })
    return findings


def main():
    findings = audit(sys.argv[1], Path(sys.argv[2]).resolve())
    if not findings:
        print(f"  ✓ {sys.argv[1]}: NO fragile goals (every sent-anchor payload accepted, or genuinely absent)")
        return
    print(f"  ⚠ {sys.argv[1]}: {len(findings)} FRAGILE goal×setting instances:")
    for f in findings:
        print(f"    goal {f['goal']} @ setting {f['setting']} — anchor sent {f['n_matching']}x, "
              f"predicate REJECTS it:")
        print(f"        predicate : {f['predicate']}")
        print(f"        payload(s): {f['rejected_payloads']}")


if __name__ == "__main__":
    main()
