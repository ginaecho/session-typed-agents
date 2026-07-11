"""Crash-handling verdict corpus — 12 hand-derived cases (Prototype 3).

Discipline (E0): the new checker + resolver + timeout detector are pinned by a
hand-written corpus that must pass 12/12 BEFORE the E10 benchmark trusts them.
Cases cover: crash at region boundaries; crash of the coordinator -> ESCALATE;
timeout that resolves one poll before the limit (no false crash); two roles
timing out in the same round (deterministic tie-break); degraded-goal accounting;
and the four static validator checks (coverage / projectability / recoverability
/ no-authorization-bypass) including the adversarial settlement-shortcut.

Run:  python experiments/tests/verdict_corpus/crash/crash_corpus.py
Exit 0 iff 12/12.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "subagent_trials"))

from stjp_core.compiler.crash_handling import (   # noqa: E402
    parse_fail_text, validate_fail, resolve_crash, detect_crashes)
from stjp_core.critic.policies import parse_policy_text   # noqa: E402
from cases import CASES                                   # noqa: E402

ROLES = CASES["escrow_trade"]["roles"]
POLICIES = parse_policy_text(CASES["escrow_trade"]["policy"])
# worst-case in-region history (everything short of confirm/settle)
PRE = [{"sender": "Buyer", "receiver": "Escrow", "label": "Deposit"},
       {"sender": "Escrow", "receiver": "Seller", "label": "PaymentSecured"},
       {"sender": "Seller", "receiver": "Carrier", "label": "ShipGoods"},
       {"sender": "Carrier", "receiver": "Buyer", "label": "DeliverGoods"}]

GOOD_FAIL = """
region Trade covers ALL
on crash Buyer   : Escrow->Seller:AbortTrade ; goal := Refunded
on crash Seller  : Escrow->Buyer:AbortTrade ; goal := Refunded
on crash Carrier : Escrow->Buyer:AbortTrade ; Escrow->Seller:AbortTrade ; goal := Refunded
on crash Escrow  : ESCALATE
timeout * = 3 polls
"""


def _cases():
    good = parse_fail_text(GOOD_FAIL)
    cases = []

    # 1. good .fail validates (all 4 checks pass)
    cases.append(("good_fail_validates",
                  lambda: validate_fail(good, ROLES, POLICIES, PRE)[0] is True))
    # 2. crash Buyer with CF -> typed_degraded, goal Refunded
    cases.append(("crash_buyer_degraded",
                  lambda: resolve_crash(good, "Buyer")["outcome"] == "typed_degraded"
                  and resolve_crash(good, "Buyer")["goal"] == "Refunded"))
    # 3. crash Escrow (coordinator) -> typed_abort (ESCALATE)
    cases.append(("crash_escrow_escalate",
                  lambda: resolve_crash(good, "Escrow")["outcome"] == "typed_abort"))
    # 4. crash Carrier -> two handler messages (Abort to Buyer AND Seller)
    cases.append(("crash_carrier_multi_msg",
                  lambda: len(resolve_crash(good, "Carrier")["messages"]) == 2))
    # 5. without CF, any crash -> limbo (the shipped-system failure)
    cases.append(("no_cf_limbo",
                  lambda: resolve_crash(good, "Buyer", has_cf=False)["outcome"] == "limbo"))
    # 6. timeout detection: idle == budget -> crash fires
    cases.append(("timeout_fires_at_budget",
                  lambda: detect_crashes(good, {"Buyer": 3}) == ["Buyer"]))
    # 7. timeout resolves ONE poll before the limit -> NO false crash
    cases.append(("timeout_no_false_crash",
                  lambda: detect_crashes(good, {"Buyer": 2}) == []))
    # 8. two roles time out in the same round -> deterministic tie-break (sorted)
    cases.append(("two_timeouts_tiebreak",
                  lambda: detect_crashes(good, {"Seller": 3, "Buyer": 3}) == ["Buyer", "Seller"]))
    # 9. coverage: a missing handler is REJECTED
    bad_cov = parse_fail_text("region Trade covers ALL\n"
                              "on crash Buyer : Escrow->Seller:AbortTrade ; goal := Refunded\n"
                              "on crash Escrow : ESCALATE\n")
    cases.append(("uncovered_rejected",
                  lambda: validate_fail(bad_cov, ROLES, POLICIES, PRE)[0] is False))
    # 10. recoverability: a handler with no `goal :=` terminal is REJECTED
    bad_goal = parse_fail_text("region Trade covers ALL\n"
                               "on crash Buyer : Escrow->Seller:AbortTrade\n"
                               "on crash Seller : Escrow->Buyer:AbortTrade ; goal := Refunded\n"
                               "on crash Carrier : Escrow->Buyer:AbortTrade ; goal := Refunded\n"
                               "on crash Escrow : ESCALATE\n")
    cases.append(("nogoal_rejected",
                  lambda: any("recoverability" in e
                              for e in validate_fail(bad_goal, ROLES, POLICIES, PRE)[1])))
    # 11. projectability: a handler with sender==receiver is REJECTED
    bad_proj = parse_fail_text("region Trade covers ALL\n"
                               "on crash Buyer : Seller->Seller:AbortTrade ; goal := Refunded\n"
                               "on crash Seller : Escrow->Buyer:AbortTrade ; goal := Refunded\n"
                               "on crash Carrier : Escrow->Buyer:AbortTrade ; goal := Refunded\n"
                               "on crash Escrow : ESCALATE\n")
    cases.append(("bad_projection_rejected",
                  lambda: validate_fail(bad_proj, ROLES, POLICIES, PRE)[0] is False))
    # 12. authorization-bypass: a handler that settles without confirm is REJECTED
    bypass = parse_fail_text(
        "region Trade covers ALL\n"
        "on crash Buyer : Escrow->Seller:AbortTrade ; goal := Refunded\n"
        "on crash Seller : Escrow->Buyer:AbortTrade ; goal := Refunded\n"
        "on crash Carrier : Escrow->Buyer:SettlementComplete ; Escrow->Seller:SettlementComplete ; goal := Settled\n"
        "on crash Escrow : ESCALATE\n")
    cases.append(("bypass_rejected",
                  lambda: any("bypass" in e
                              for e in validate_fail(bypass, ROLES, POLICIES, PRE)[1])))
    return cases


def main() -> int:
    passed, failed = 0, []
    print("── CRASH-HANDLING verdict corpus (Prototype 3) ──")
    for cid, fn in _cases():
        try:
            ok = bool(fn())
        except Exception as e:
            ok, cid = False, f"{cid} (exception: {e})"
        print(f"  {'PASS' if ok else 'FAIL'}  {cid}")
        passed += ok
        if not ok:
            failed.append(cid)
    total = 12
    print(f"\nCRASH CORPUS: {passed}/{total} passed"
          + (f" — FAILURES: {failed}" if failed else "  ✓ checker trustworthy"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
