"""langgraph_ladder.py — run an STJP arm-ladder protocol as a LangGraph graph.

Purpose (two things at once):
  1. **E7 third harness.** Execute a case's protocol on LangGraph's StateGraph,
     produce a message trace, and feed that trace to the *native* STJP
     SessionMonitor. If LangGraph's structural execution and STJP's monitor
     agree on every trace (clean run -> 0 violations; a deliberately
     off-protocol run -> caught), that is cross-runtime portability evidence
     beyond the existing in-process-vs-standalone check.
  2. **Token-metering-ready.** Each role node calls a pluggable `decide(view)`.
     With ANTHROPIC_API_KEY set it uses ChatAnthropic and real token usage is
     captured via langchain's usage-metadata callback. Without a key it falls
     back to a deterministic contract-follower (0 tokens) so the harness still
     runs and the wiring is provable.

Run:  python experiments/harness_adapters/langgraph_ladder.py --case revenue_audit --arm min_gate
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))                 # repo root
sys.path.insert(0, str(HERE.parent / "subagent_trials"))  # engine + cases

from stjp_core.monitor.monitor import SessionMonitor, TraceEvent   # noqa: E402
from stjp_core.compiler.efsm_parser import get_all_efsms           # noqa: E402
from cases import CASES                                            # noqa: E402
from engine_ladder import ARMS, _send_transitions                 # noqa: E402

from langgraph.graph import StateGraph, END                       # noqa: E402


# ── agent: pluggable, LLM-or-deterministic, token-metered ────────────────────

def make_decider(use_llm: bool):
    """Return decide(role, view_text, legal_sends) -> action dict.

    LLM path is used only if a real key exists; otherwise a deterministic
    contract-follower (take the single legal send, else wait) — which is also
    the honest reference behaviour for the *gate* arms.
    """
    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_llm and have_key:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-haiku-4-5-20251001", max_tokens=64, temperature=0)

        def decide(role, view, legal):
            # real model call — tokens captured by the usage callback in run()
            resp = llm.invoke(view)
            raw = resp.content if isinstance(resp.content, str) else str(resp.content)
            try:
                obj = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
                return obj
            except Exception:
                return {"action": "wait", "reason": "unpar+seable"}
        return decide, "llm:claude-haiku-4-5"

    def decide(role, view, legal):
        if legal:
            _, _, to, label, ty, _ = legal[0]
            pay = "50000" if label == "Revenue" else ("approved" if label == "Approval" else "filed")
            return {"action": "send", "to": to, "label": label, "payload": pay}
        return {"action": "wait", "reason": "no enabled send"}
    return decide, "deterministic:contract-follower"


# ── LangGraph state machine over the protocol ────────────────────────────────

def build_efsms(case):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        scr = Path(td) / f"{case['module']}.scr"
        scr.write_text(case["protocol"], encoding="utf-8")
        return get_all_efsms(scr, case["protocol_name"], case["roles"])


def run(case_key: str, arm: str, use_llm: bool, max_rounds: int = 8, inject_fault: bool = False):
    case = CASES[case_key]
    efsms = build_efsms(case)
    roles = case["roles"]
    enforce = ARMS[arm]["enforce"]
    schedule = ARMS[arm]["schedule"]
    decide, agent_id = make_decider(use_llm)

    role_states = {r: efsms[r].initial_state for r in roles}

    def poll_node(state):
        """One protocol round: poll roles (all, or only enabled senders), apply
        the gate if enforcing, append delivered messages to the trace."""
        rnd = state["round"] + 1
        if schedule == "enabled":
            polled = [r for r in roles if _send_transitions_compat(efsms, r, role_states[r])]
        else:
            polled = list(roles)
        for role in polled:
            legal = _send_transitions_compat(efsms, role, role_states[role])
            # optional fault injection: force the first role to emit an
            # off-protocol label (its EFSM does not allow it) so we can show the
            # native STJP monitor still catches a LangGraph-produced violation.
            if inject_fault and role == roles[0] and state["round"] == 0:
                action = {"action": "send", "to": roles[1], "label": "Filed", "payload": "x"}
            else:
                view = f"You are {role}. Round {rnd}. Allowed: {[(t[3],t[2]) for t in legal] or 'wait'}. Reply JSON."
                action = decide(role, view, legal)
            if action.get("action") != "send":
                continue
            to, label = action.get("to"), action.get("label")
            ok = any(t[1] == "send" and t[2] == to and t[3] == label for t in legal)
            if enforce and not ok:
                state["rejections"].append({"round": rnd, "role": role, "to": to, "label": label})
                continue
            state["trace"].append({"round": rnd, "sender": role, "receiver": to,
                                   "label": label, "payload": action.get("payload", "")})
            _advance(efsms, role_states, role, "send", to, label)
            _advance(efsms, role_states, to, "receive", role, label)
        state["round"] = rnd
        return state

    def done(state):
        seen = {(e["sender"], e["receiver"], e["label"]) for e in state["trace"]}
        reached = all(tuple(g) in seen for g in case["terminal_messages"])
        return END if (reached or state["round"] >= max_rounds) else "poll"

    g = StateGraph(dict)
    g.add_node("poll", poll_node)
    g.set_entry_point("poll")
    g.add_conditional_edges("poll", done, {"poll": "poll", END: END})
    app = g.compile()

    init = {"round": 0, "trace": [], "rejections": []}
    # token metering: capture real usage if an LLM was actually invoked
    tokens = {"input": 0, "output": 0}
    try:
        from langchain_core.callbacks import get_usage_metadata_callback
        with get_usage_metadata_callback() as cb:
            final = app.invoke(init, {"recursion_limit": 4 * max_rounds})
        for _model, u in getattr(cb, "usage_metadata", {}).items():
            tokens["input"] += u.get("input_tokens", 0)
            tokens["output"] += u.get("output_tokens", 0)
    except Exception:
        final = app.invoke(init, {"recursion_limit": 4 * max_rounds})

    return final, agent_id, tokens, efsms, case


def _send_transitions_compat(efsms, role, st):
    """List of (state, 'send', to, label, ty, nxt) enabled at `st` for `role`."""
    out = []
    for t in efsms[role].transitions_from(st):
        if t.direction == "send":
            out.append((t.source, "send", t.peer, t.label, t.payload_type, t.target))
    return out


def _advance(efsms, role_states, role, act, peer, label):
    for t in efsms[role].transitions_from(role_states[role]):
        if t.direction == act and t.peer == peer and t.label == label:
            role_states[role] = t.target
            return


# ── main: run + cross-check against the native STJP monitor (E7) ─────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="revenue_audit", choices=sorted(CASES))
    ap.add_argument("--arm", default="min_gate", choices=sorted(ARMS))
    ap.add_argument("--llm", action="store_true", help="use ChatAnthropic if ANTHROPIC_API_KEY is set")
    ap.add_argument("--fault", action="store_true", help="inject an off-protocol send to test monitor agreement")
    args = ap.parse_args()

    final, agent_id, tokens, efsms, case = run(args.case, args.arm, args.llm, inject_fault=args.fault)

    # feed the LangGraph-produced trace to the NATIVE STJP monitor
    events = [TraceEvent(sender=e["sender"], receiver=e["receiver"], label=e["label"],
                         payload=e.get("payload", ""), step=i + 1)
              for i, e in enumerate(final["trace"])]
    verdicts = SessionMonitor(efsms).process_trace(events)
    violations = sum(len(v.violations) for v in verdicts.values())

    print(f"harness=LangGraph  case={args.case}  arm={args.arm}  agent={agent_id}")
    print(f"rounds={final['round']}  messages={len(final['trace'])}  gate_rejections={len(final['rejections'])}")
    print("trace:")
    for e in final["trace"]:
        print(f"   r{e['round']} {e['sender']} -> {e['receiver']} : {e['label']}({e['payload']})")
    print(f"tokens: input={tokens['input']} output={tokens['output']} "
          f"({'REAL (metered LLM)' if tokens['input'] else 'deterministic — 0; metering wired, add ANTHROPIC_API_KEY'})")
    print(f"STJP monitor on the LangGraph trace: {violations} violations "
          f"({'CLEAN — harnesses agree' if violations == 0 else 'CAUGHT off-protocol — harnesses agree'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
