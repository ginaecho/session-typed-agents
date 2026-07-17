"""evaluate_run.py — three-metric post-hoc evaluator.

Takes a completed run_dir + case_id and computes THREE parallel success
metrics per arm, each measuring a different thing:

  1. STRICT label-match (`strict_pct`)
     Did the agent emit events whose (sender, receiver, label) tuple
     matches the goal's anchor AND whose payload satisfies the predicate?
     This is the current `verify_goals_against_trace` semantics.
     **N/A for arms that received NO protocol vocabulary** (bare, maf_native,
     maf_foundry, maf_groupchat — they were only told the intent, so it's
     unfair to test their ability to match labels they were never given).

  2. ROLE-PAIR match (`role_pair_pct`)
     Drop the label requirement. Does ANY event from the goal's sender to
     the goal's receiver carry a payload that satisfies the predicate?
     Applies to ALL arms. Tests "right participants exchanged the right
     kind of value" regardless of vocabulary.

  3. SEMANTIC goal achievement (`semantic_pct`)
     LLM-judged: given the goal's natural-language description and the
     full trace, did the conversation accomplish what the goal asks for?
     Applies to ALL arms. Most generous metric — tests "did agents do the
     right thing in spirit" regardless of vocabulary AND role assignment.

Usage:
  python scripts/evaluate_run.py <case_id> <run_dir>
  python scripts/evaluate_run.py finance experiments/cases/finance/runs/20260518T175717-n10-dual

Output:
  Writes <run_dir>/summary_eval.json (parallel structure to summary.json,
  with the 3 metrics) and prints an expanded table.

Cost note: semantic uses ~5 LLM calls per trial per arm. At n=10 finance
across 8 arms, ~400 LLM calls. Cached by (arm, trial, goal_id) hash so
re-running is free if you don't change the prompt.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from dotenv import load_dotenv


HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
TESTING_IDEAS = EXPERIMENTS_DIR.parent
STJP_CORE = TESTING_IDEAS / "stjp_core"
CASES_DIR = EXPERIMENTS_DIR / "cases"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXPERIMENTS_DIR))
sys.path.insert(0, str(TESTING_IDEAS))
load_dotenv(STJP_CORE / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from stjp_core.foundry.llm_client import LLMClient
from case_loader import Case
from baselines.registry import SCENARIOS, make_runner
from stjp_core.compiler.refinement_checker import Refinement


# ---------------------------------------------------------------------------
# Which arms received a protocol vocabulary in their prompt?
# Arms in this set get a `strict_pct`; others get N/A for that metric.
# ---------------------------------------------------------------------------

VOCABULARY_ARMS = {
    "maf_groupchat_unsafe",   # global type given as text
    "maf_groupchat_llmvalid", # global type given as text
    "spec_llmvalid",          # projected local types given
    "min_llmvalid",           # projected local types given
    "spec_llmvalid_gate",     # projected local types given + enforcement gate
    "min_llmvalid_gate",      # lean projected local types + enforcement gate
    "min_llmvalid_gate_nohint",   # gate WITHOUT the per-turn liveness nudge
    "min_llmvalid_gate_lastrecv", # gate + last-receiver heuristic scheduling
    "min_llmvalid_sched",     # lean projected + gate + EFSM scheduler
    "global_decentralized",   # global type text, decentralized runner
}


# ---------------------------------------------------------------------------
# Trial parser: JSONL -> list of (trial_idx, events, succeeded_strict)
# ---------------------------------------------------------------------------

def _parse_trials(events_path: Path) -> list[dict]:
    """Return list of trials, each with PER-ATTEMPT event groups.

    Schema:
      {trial: int, branch: str, succeeded_strict: bool,
       attempts: [ [event, event, ...],  # attempt 1
                   [event, event, ...] ], # attempt 2 (if retried)
       events_all_flat: [event, ...]}    # concatenation for semantic judge

    Per-attempt grouping is CRITICAL: retry-to-success means a successful
    trial's later attempt(s) might have the goal-satisfying event but the
    first attempt's events also live in the JSONL. Verifying per attempt
    matches the runner's semantics (any attempt succeeds -> trial succeeds).
    """
    if not events_path.exists():
        return []
    trials = []
    cur = None
    cur_attempt: list = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        m = ev.get("marker")
        if m == "trial_start":
            cur = {"trial": ev.get("trial"), "branch": ev.get("branch"),
                   "succeeded_strict": False, "attempts": [],
                   "events_all_flat": []}
            cur_attempt = []
        elif m == "trial_end":
            if cur:
                # Flush any open attempt (defensive — should normally end via attempt_end).
                if cur_attempt:
                    cur["attempts"].append(cur_attempt)
                    cur["events_all_flat"].extend(cur_attempt)
                    cur_attempt = []
                cur["succeeded_strict"] = bool(ev.get("succeeded"))
                trials.append(cur)
            cur = None
        elif m == "attempt_start":
            cur_attempt = []
        elif m == "attempt_end":
            if cur is not None:
                cur["attempts"].append(cur_attempt)
                cur["events_all_flat"].extend(cur_attempt)
                cur_attempt = []
        elif m == "protocol_unprojectable":
            continue
        else:
            if cur is None:
                continue
            cur_attempt.append({
                "sender": ev.get("sender", ""),
                "receiver": ev.get("receiver", ""),
                "label": ev.get("label", ""),
                "payload": str(ev.get("payload", "")),
            })
    return trials


# ---------------------------------------------------------------------------
# Verifier #1: strict label match (same as goal_elicitor.verify_goals_against_trace)
# ---------------------------------------------------------------------------

def verify_strict(goal_set, events: list[dict],
                  branch: str | None = None) -> dict[str, bool]:
    """{goal_id: pass/fail} via exact (sender, receiver, label) + predicate.

    A goal whose `branch` differs from the trial's branch is vacuously True
    (it belongs to a protocol path the trial did not take)."""
    out = {}
    for g in goal_set.goals:
        if g.branch and branch is not None and g.branch != branch:
            out[g.id] = True
            continue
        matching = [e for e in events
                    if e["sender"] == g.anchor_sender
                    and e["receiver"] == g.anchor_receiver
                    and e["label"] == g.anchor_label]
        if not matching:
            out[g.id] = False
            continue
        refn = Refinement(sender=g.anchor_sender, receiver=g.anchor_receiver,
                          label=g.anchor_label, predicates=[g.predicate])
        ok, _ = refn.check(matching[0]["payload"])
        out[g.id] = ok
    return out


# ---------------------------------------------------------------------------
# Verifier #2: role-pair only (drop label requirement)
# ---------------------------------------------------------------------------

def verify_role_pair(goal_set, events: list[dict],
                     branch: str | None = None) -> dict[str, bool]:
    """{goal_id: pass/fail} via (sender, receiver) + predicate (label ignored).

    A goal whose `branch` differs from the trial's branch is vacuously True."""
    out = {}
    for g in goal_set.goals:
        if g.branch and branch is not None and g.branch != branch:
            out[g.id] = True
            continue
        candidates = [e for e in events
                      if e["sender"] == g.anchor_sender
                      and e["receiver"] == g.anchor_receiver]
        if not candidates:
            out[g.id] = False
            continue
        refn = Refinement(sender=g.anchor_sender, receiver=g.anchor_receiver,
                          label="", predicates=[g.predicate])  # label unused by .check
        # Any candidate that passes counts.
        out[g.id] = any(refn.check(c["payload"])[0] for c in candidates)
    return out


# ---------------------------------------------------------------------------
# Verifier #3: LLM-judged semantic goal achievement (with cache)
# ---------------------------------------------------------------------------

SEMANTIC_SYSTEM = """You are evaluating whether a specific goal was achieved
by a multi-agent conversation.

Reply with JSON only — no prose:
{"achieved": true|false, "reason": "<one sentence citing the event(s) you used>"}
"""


def _semantic_user_msg(goal, events: list[dict]) -> str:
    trace_lines = "\n".join(
        f"  {i+1:2d}. {e['sender']} -> {e['receiver']} : {e['label']}({e['payload']!r})"
        for i, e in enumerate(events)
    ) or "  (no events)"
    return f"""GOAL TO EVALUATE:
  ID: {goal.id}
  Description: {goal.description}
  Predicate (the goal's semantic check, where `x` is the payload string):
    {goal.predicate}
  Reference anchor (what the canonical protocol expected — agents may have
  used different labels/role-pairs if not given the protocol):
    {goal.anchor_sender} -> {goal.anchor_receiver} : {goal.anchor_label}

CONVERSATION TRACE:
{trace_lines}

Evaluate: did this conversation contain at least one event whose CONTENT
(payload + role context) semantically fulfills the goal's predicate,
regardless of what label or sender-receiver pair the agents actually used?

Be strict: require explicit semantic fulfillment. Don't accept vague mentions.
If no event clearly fulfills the goal's intent, reply achieved=false.
"""


def _cache_key(arm_key: str, trial_idx: int, goal_id: str,
                events: list[dict]) -> str:
    h = hashlib.sha256()
    for e in events:
        h.update(f"{e['sender']}|{e['receiver']}|{e['label']}|{e['payload']}\n".encode())
    return f"{arm_key}/{trial_idx}/{goal_id}/{h.hexdigest()[:16]}"


def verify_semantic(arm_key: str, trial_idx: int, goal_set, events: list[dict],
                     llm: LLMClient, cache: dict) -> dict[str, bool]:
    """{goal_id: pass/fail} via LLM judgment per goal. Cached."""
    out = {}
    for g in goal_set.goals:
        key = _cache_key(arm_key, trial_idx, g.id, events)
        if key in cache:
            out[g.id] = bool(cache[key].get("achieved"))
            continue
        user = _semantic_user_msg(g, events)
        try:
            reply = llm.generate(SEMANTIC_SYSTEM, user)
            text = (reply or "").strip()
            if text.startswith("```"):
                text = "\n".join(l for l in text.splitlines()
                                 if not l.startswith("```")).strip()
            s, e = text.find("{"), text.rfind("}")
            obj = json.loads(text[s:e+1])
        except Exception as exc:
            print(f"      [semantic] err on {g.id}: {type(exc).__name__}: {exc}")
            obj = {"achieved": False, "reason": f"judge_error: {exc}"}
        cache[key] = obj
        out[g.id] = bool(obj.get("achieved"))
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def evaluate(case: Case, run_dir: Path, semantic: bool = True) -> dict:
    """Compute Set B (goal-achievement) metrics for every arm in run_dir.

    semantic=True  -> also run the LLM-judged semantic metric (~5 LLM calls
                      per trial per arm).
    semantic=False -> strict + role-pair only (deterministic, free);
                      semantic_pct / semantic_per_goal are None.
    """
    cache_path = run_dir / "semantic_judgments_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) \
        if (semantic and cache_path.exists()) else {}
    llm = LLMClient() if semantic else None

    out = {"run_dir": str(run_dir), "arms": {}}

    for arm_key, arm_name, _factory in SCENARIOS:
        events_path = run_dir / f"events_{arm_key}.jsonl"
        trials = _parse_trials(events_path)
        if not trials:
            print(f"  [{arm_name}] no trials found; skipping")
            continue

        runner = make_runner(case, arm_key)
        goal_set = runner.goal_set()
        n_goals = len(goal_set.goals)
        has_vocab = arm_key in VOCABULARY_ARMS

        # Aggregate per-goal pass counts across trials, and per-trial all-goals-pass.
        strict_goal_passes = {g.id: 0 for g in goal_set.goals}
        rolepair_goal_passes = {g.id: 0 for g in goal_set.goals}
        semantic_goal_passes = {g.id: 0 for g in goal_set.goals}
        strict_full_trials = rolepair_full_trials = semantic_full_trials = 0

        print(f"  [{arm_name}] {len(trials)} trials, {n_goals} goals "
              f"(vocab={has_vocab})", flush=True)

        for t in trials:
            branch = t.get("branch")
            # Verify each attempt independently, then OR the results per goal.
            # Mirrors the runner's "any attempt succeeds -> trial succeeds".
            strict_t: dict = {g.id: False for g in goal_set.goals} if has_vocab else None
            rp_t: dict = {g.id: False for g in goal_set.goals}
            for attempt_events in t["attempts"]:
                if has_vocab:
                    s = verify_strict(goal_set, attempt_events, branch)
                    for gid, ok in s.items():
                        if ok:
                            strict_t[gid] = True
                r = verify_role_pair(goal_set, attempt_events, branch)
                for gid, ok in r.items():
                    if ok:
                        rp_t[gid] = True
            # Semantic verifier sees the full trial (all attempts) — it's
            # judging "did the conversation, taken together, achieve the goal?"
            # which matches the spirit of trial-level success. Skipped
            # entirely when semantic=False (no LLM budget spent).
            semantic_t = (verify_semantic(arm_key, t["trial"], goal_set,
                                          t["events_all_flat"], llm, cache)
                          if semantic else None)

            for gid, ok in rp_t.items():
                if ok:
                    rolepair_goal_passes[gid] += 1
            if semantic_t is not None:
                for gid, ok in semantic_t.items():
                    if ok:
                        semantic_goal_passes[gid] += 1
            if strict_t is not None:
                for gid, ok in strict_t.items():
                    if ok:
                        strict_goal_passes[gid] += 1
                if all(strict_t.values()):
                    strict_full_trials += 1
            if all(rp_t.values()):
                rolepair_full_trials += 1
            if semantic_t is not None and all(semantic_t.values()):
                semantic_full_trials += 1

            # Persist cache after each trial (cheap; protects against crashes).
            if semantic:
                cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")

        n = len(trials)
        def pct(x):
            return round(x / n * 100, 1) if n else 0.0

        out["arms"][arm_key] = {
            "arm_name": arm_name,
            "n_trials": n,
            "n_goals": n_goals,
            "has_vocabulary": has_vocab,
            "strict_pct": pct(strict_full_trials) if has_vocab else None,
            "role_pair_pct": pct(rolepair_full_trials),
            "semantic_pct": pct(semantic_full_trials) if semantic else None,
            "strict_per_goal": ({gid: pct(strict_goal_passes[gid])
                                  for gid in strict_goal_passes}
                                 if has_vocab else None),
            "role_pair_per_goal": {gid: pct(rolepair_goal_passes[gid])
                                    for gid in rolepair_goal_passes},
            "semantic_per_goal": ({gid: pct(semantic_goal_passes[gid])
                                    for gid in semantic_goal_passes}
                                   if semantic else None),
        }

    out_path = run_dir / "summary_eval.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWROTE {out_path.relative_to(TESTING_IDEAS)}")
    return out


def print_eval(case: Case, evout: dict) -> None:
    arms = evout["arms"]
    semantic_ran = any(a.get("semantic_pct") is not None for a in arms.values())
    print("\n" + "=" * 110)
    print(f"  SET B — GOAL-ACHIEVEMENT METRICS: {case.case_id}")
    print(f"    strict   : (sender, receiver, label) + predicate  — N/A for intent-only arms")
    print(f"    role-pair: (sender, receiver) + predicate          — applies to all")
    if semantic_ran:
        print(f"    semantic : LLM-judged 'goal intent achieved'       — applies to all")
    else:
        print(f"    semantic : SKIPPED — re-run with --semantic to enable the LLM judge")
    print("=" * 110)
    print(f"  {'arm':28s}  {'strict':>8s}  {'role-pair':>10s}  {'semantic':>10s}  vocab")
    print(f"  {'-'*28}  {'-'*8}  {'-'*10}  {'-'*10}  -----")
    for arm_key, _, _ in SCENARIOS:
        if arm_key not in arms:
            continue
        a = arms[arm_key]
        strict = f"{a['strict_pct']:>7.1f}%" if a["strict_pct"] is not None else "    N/A"
        rp = f"{a['role_pair_pct']:>9.1f}%"
        sm = (f"{a['semantic_pct']:>9.1f}%" if a["semantic_pct"] is not None
              else f"{'N/A':>10s}")
        print(f"  {arm_key:28s}  {strict}  {rp}  {sm}  {a['has_vocabulary']}")


def main():
    args = sys.argv[1:]
    semantic = "--no-semantic" not in args
    args = [a for a in args if a != "--no-semantic"]
    if len(args) < 2:
        print("usage: evaluate_run.py <case_id> <run_dir> [--no-semantic]")
        print("  --no-semantic: strict + role-pair only; skip the LLM judge.")
        sys.exit(2)
    case = Case.load(CASES_DIR / args[0])
    run_dir = Path(args[1]).resolve()
    if not run_dir.exists():
        print(f"run_dir does not exist: {run_dir}")
        sys.exit(2)
    out = evaluate(case, run_dir, semantic=semantic)
    print_eval(case, out)


if __name__ == "__main__":
    main()
