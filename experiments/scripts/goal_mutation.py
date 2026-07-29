"""goal_mutation.py — mutation adequacy for a case's goal + policy set.

Discrimination (goal_quality.py) tells you a goal separates arms on the traces
you HAPPENED to collect. Mutation adequacy asks the stronger question: if the
world went subtly wrong, would the goal+policy set NOTICE? It is the
software-engineering test-adequacy idea applied to a benchmark's own checks.

Method: take a GOLD trace that passes all goals and violates no policy (a
successful checked-arm trial), then apply targeted TRACE mutations that each
correspond to a real failure mode, and verify the goal+policy set FAILS the
mutant. A mutant that still passes everything is a hole in the checks.

  drop_anchor      remove a goal's anchor event        -> that goal must fail
  corrupt_payload  break a data-quality predicate       -> that goal must fail
  reorder_safety   move an `after` before its `before`  -> a [sequence] must fire
  duplicate_once   duplicate an at-most-once event      -> an [aggregate] must fire
  swap_roles       swap sender/receiver of the 'first'  -> a [separation] must fire

Score = mutants killed / mutants applicable. See GOAL_QUALITY_AUDIT.md D-gate-2.

Usage:
  python scripts/goal_mutation.py <case_id> <run_dir> [--arm min_llmvalid]
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
REPO = EXPERIMENTS_DIR.parent
CASES_DIR = EXPERIMENTS_DIR / "cases"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXPERIMENTS_DIR))
sys.path.insert(0, str(REPO))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from case_loader import Case
from evaluate_run import _parse_trials, verify_strict, verify_role_pair
from policy_eval import load_policies, _relaxed_findings
from stjp_core.critic.policies import SequencePolicy, AggregatePolicy, SeparationPolicy


def _goal_set(case: Case):
    return SimpleNamespace(goals=case.goals)


def _gold_trace(run_dir: Path, arm: str) -> list[dict] | None:
    """First successful trial's flat events for the given (checked) arm."""
    trials = _parse_trials(run_dir / f"events_{arm}.jsonl")
    for t in trials:
        if t.get("succeeded_strict") and t["events_all_flat"]:
            return t["events_all_flat"]
    # fall back to any trial with events
    for t in trials:
        if t["events_all_flat"]:
            return t["events_all_flat"]
    return None


def _goals_all_pass(goal_set, events, branch=None) -> bool:
    s = verify_strict(goal_set, events, branch)
    r = verify_role_pair(goal_set, events, branch)
    return all(s.values()) and all(r.values())


def _policy_clean(events, policies) -> bool:
    return not _relaxed_findings(events, policies)


def _gold_is_clean(goal_set, policies, gold) -> tuple[bool, bool]:
    return _goals_all_pass(goal_set, gold), _policy_clean(gold, policies)


# --- mutation operators: each returns (mutant_events, expectation) or None ---

def m_drop_anchor(gold, goal_set, policies):
    for g in goal_set.goals:
        for i, e in enumerate(gold):
            if (e["sender"] == g.anchor_sender and e["receiver"] == g.anchor_receiver
                    and e["label"] == g.anchor_label):
                mut = gold[:i] + gold[i+1:]
                return ("drop_anchor", f"goal {g.id} anchor removed", mut, "goal_fail")
    return None


def m_corrupt_payload(gold, goal_set, policies):
    for g in goal_set.goals:
        pred = (g.predicate or "").strip()
        if pred in ("True", "true", "len(x) >= 0"):
            continue  # liveness goal: no payload to corrupt
        for i, e in enumerate(gold):
            if (e["sender"] == g.anchor_sender and e["receiver"] == g.anchor_receiver
                    and e["label"] == g.anchor_label):
                mut = copy.deepcopy(gold)
                mut[i]["payload"] = "___not_a_valid_value___"
                return ("corrupt_payload", f"goal {g.id} payload broken", mut, "goal_fail")
    return None


def m_reorder_safety(gold, goal_set, policies):
    for p in policies:
        if not isinstance(p, SequencePolicy):
            continue
        bi = ai = None
        for i, e in enumerate(gold):
            if _match(p.before, e):
                bi = i
            if _match(p.after, e) and ai is None:
                ai = i
        if bi is not None and ai is not None and bi < ai:
            mut = copy.deepcopy(gold)
            after_ev = mut.pop(ai)
            mut.insert(bi, after_ev)  # move `after` in front of `before`
            return ("reorder_safety", f"policy {p.id}: after moved before before",
                    mut, "policy_fire")
    return None


def m_duplicate_once(gold, goal_set, policies):
    for p in policies:
        if not isinstance(p, AggregatePolicy):
            continue
        for i, e in enumerate(gold):
            if _match(p.count, e):
                mut = copy.deepcopy(gold)
                mut.insert(i + 1, copy.deepcopy(mut[i]))
                return ("duplicate_once", f"policy {p.id}: at-most-once event duplicated",
                        mut, "policy_fire")
    return None


def m_swap_roles(gold, goal_set, policies):
    for p in policies:
        if not isinstance(p, SeparationPolicy):
            continue
        # make the same sender do both `first` and `second`
        fi = si = None
        for i, e in enumerate(gold):
            if _match(p.first, e):
                fi = i
            if _match(p.second, e):
                si = i
        if fi is not None and si is not None:
            mut = copy.deepcopy(gold)
            mut[si]["sender"] = mut[fi]["sender"]
            return ("swap_roles", f"policy {p.id}: one role did both",
                    mut, "policy_fire")
    return None


def _match(pat, e) -> bool:
    def ok(a, b):
        return a == "*" or a == b
    return ok(pat.sender, e["sender"]) and ok(pat.receiver, e["receiver"]) \
        and ok(pat.label, e["label"])


MUTATORS = [m_drop_anchor, m_corrupt_payload, m_reorder_safety,
            m_duplicate_once, m_swap_roles]


def run(case: Case, run_dir: Path, arm: str) -> dict:
    goal_set = _goal_set(case)
    policies, psrc = load_policies(case.case_dir)
    gold = _gold_trace(run_dir, arm)
    out = {"case": case.case_id, "arm": arm, "policy_source": psrc,
           "gold_found": gold is not None, "mutants": []}
    if gold is None:
        print(f"  no gold trace for arm {arm} in {run_dir.name}")
        return out

    g_ok, p_ok = _gold_is_clean(goal_set, policies, gold)
    out["gold_goals_pass"] = g_ok
    out["gold_policy_clean"] = p_ok
    killed = applicable = 0
    for mut_fn in MUTATORS:
        res = mut_fn(gold, goal_set, policies)
        if res is None:
            out["mutants"].append({"op": mut_fn.__name__, "applicable": False})
            continue
        op, desc, mutant, expect = res
        applicable += 1
        goals_pass = _goals_all_pass(goal_set, mutant)
        policy_clean = _policy_clean(mutant, policies)
        if expect == "goal_fail":
            caught = not goals_pass
        else:  # policy_fire
            caught = not policy_clean
        killed += int(caught)
        out["mutants"].append({
            "op": op, "applicable": True, "description": desc,
            "expectation": expect, "goals_pass": goals_pass,
            "policy_clean": policy_clean, "killed": caught,
        })
    out["applicable"] = applicable
    out["killed"] = killed
    out["kill_rate_pct"] = round(killed / applicable * 100, 1) if applicable else None
    return out


def print_report(out: dict) -> None:
    print("\n" + "=" * 84)
    print(f"  GOAL/POLICY MUTATION ADEQUACY: {out['case']}  (gold arm={out['arm']})")
    print("=" * 84)
    if not out.get("gold_found"):
        print("  no gold trace available.")
        return
    print(f"  gold: goals_pass={out['gold_goals_pass']} "
          f"policy_clean={out['gold_policy_clean']}  "
          f"(a valid gold must be True/True)")
    print(f"  {'mutation':18s} {'applicable':>10s} {'killed':>7s}  detail")
    print(f"  {'-'*18} {'-'*10} {'-'*7}  {'-'*30}")
    for m in out["mutants"]:
        if not m["applicable"]:
            print(f"  {m['op']:18s} {'n/a':>10s} {'—':>7s}  (no matching goal/policy)")
            continue
        print(f"  {m['op']:18s} {'yes':>10s} {str(m['killed']):>7s}  {m['description'][:38]}")
    kr = out.get("kill_rate_pct")
    print(f"\n  KILL RATE: {out['killed']}/{out['applicable']}"
          f" = {kr}%  (100% = the checks catch every seeded failure)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "min_llmvalid"
    for a in sys.argv:
        if a.startswith("--arm="):
            arm = a.split("=", 1)[1]
    if "--arm" in sys.argv:
        arm = sys.argv[sys.argv.index("--arm") + 1]
    if len(args) < 2:
        print("usage: goal_mutation.py <case_id> <run_dir> [--arm <arm_key>]")
        sys.exit(2)
    case = Case.load(CASES_DIR / args[0])
    run_dir = Path(args[1]).resolve()
    out = run(case, run_dir, arm)
    print_report(out)
    dest = run_dir / "goal_mutation.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWROTE {dest}")


if __name__ == "__main__":
    main()
