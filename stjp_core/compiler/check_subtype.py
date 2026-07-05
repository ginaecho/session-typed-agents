"""check_subtype.py — Prototype 2 ("lawful slack").

Theory: Chen–Dezani–Scalas–Yoshida, LMCS'17 / PPDP'24. Session subtyping
characterises every safe deviation from a local type; preciseness (soundness +
completeness) means the relation is maximal — anything inside is safe in all
contexts, anything outside fails in some context.

Two deliverables live here:

(2a) `is_subtype(sub, sup)` — decide T' <= T over two EFSMs by the standard
     simulation game (SYNCHRONOUS subtyping):
       * output covariance   — T' may SELECT A SUBSET of T's internal choices
                               (sends of T' ⊆ sends of T at related states);
       * input contravariance — T' may OFFER A SUPERSET of T's external branches
                               (receives of T' ⊇ receives of T);
       * payload sorts        — covariant on receive, contravariant on send
                               (v1: exact-match sorts, a flat lattice, which
                               satisfies both directions when equal).
     Wired into S3: after rendering the lean contract, parse it back to an EFSM
     and require `lean <= projection` — compression that drops a required
     behaviour fails the build.

(2b) `anticipable(efsm, state, peer, label)` — the runtime tolerant gate's ONE
     decidable, provably-safe relaxation: independent-receive output
     anticipation. A send s is admitted early iff, in the current state, the
     only pending obligations before s are RECEIVES, and s is enabled on EVERY
     branch reachable by completing those receives (so s does not depend on any
     pending input's outcome). Full asynchronous subtyping is undecidable; this
     fragment is a bounded forward search and is provably inside the precise
     relation. Everything outside it is rejected exactly as the strict gate does.
"""
from __future__ import annotations

from stjp_core.compiler.efsm_parser import EFSM


# ── (2a) compile-time subtype check ──────────────────────────────────────────

# v1 payload sort lattice: EXACT MATCH only. Equal sorts trivially satisfy both
# covariance (receive) and contravariance (send); non-trivial sort subtyping
# (e.g. int <: Double) is deliberately deferred so every accepted pair is
# provably safe. The `on_send` param is kept for when that lattice is added.
def _sort_ok(sub_sort: str, sup_sort: str, on_send: bool) -> bool:
    return sub_sort.strip() == sup_sort.strip()


def is_subtype(sub: EFSM, sup: EFSM) -> tuple[bool, str]:
    """Return (T' <= T, reason). `sub` is T' (e.g. the lean contract), `sup` is
    T (e.g. the projection). Coinductive simulation with an assumed set."""
    assumed: set[tuple[str, str]] = set()

    def sends(efsm, st):
        return [t for t in efsm.transitions_from(st) if t.direction == "send"]

    def recvs(efsm, st):
        return [t for t in efsm.transitions_from(st) if t.direction == "receive"]

    def sim(s_sub: str, s_sup: str) -> tuple[bool, str]:
        if (s_sub, s_sup) in assumed:
            return True, ""
        assumed.add((s_sub, s_sup))

        sub_sends, sup_sends = sends(sub, s_sub), sends(sup, s_sup)
        sub_recvs, sup_recvs = recvs(sub, s_sub), recvs(sup, s_sup)

        # POLARITY: if T is a send-state, T' must also be able to select a send
        # (the internal-choice subset must be non-empty — dropping the only send
        # leaves T' unable to progress where T must).
        if sup_sends and not sub_sends:
            return False, (f"T offers an internal choice at ({s_sup}) but T' "
                           f"drops it entirely at ({s_sub}) — no send to select")

        # OUTPUT COVARIANCE: every send T' offers must be a send T offers.
        for t in sub_sends:
            match = [u for u in sup_sends
                     if u.peer == t.peer and u.label == t.label
                     and _sort_ok(t.payload_type, u.payload_type, on_send=True)]
            if not match:
                return False, (f"output covariance: T' sends {t.peer}!{t.label} "
                               f"at ({s_sub}) which T does not offer at ({s_sup})")
            ok, why = sim(t.target, match[0].target)
            if not ok:
                return False, why

        # INPUT CONTRAVARIANCE: every receive T requires, T' must also offer.
        for u in sup_recvs:
            match = [t for t in sub_recvs
                     if t.peer == u.peer and t.label == u.label
                     and _sort_ok(t.payload_type, u.payload_type, on_send=False)]
            if not match:
                return False, (f"input contravariance: T requires receive "
                               f"{u.peer}?{u.label} at ({s_sup}) which T' does not "
                               f"offer at ({s_sub})")
            ok, why = sim(match[0].target, u.target)
            if not ok:
                return False, why

        # Termination consistency: if T can stop here, T' must be able to stop
        # too (no pending sends). (T' stopping while T still receives is caught
        # by input contravariance above.)
        if sup.is_accepting(s_sup) and sub_sends:
            return False, (f"T may terminate at ({s_sup}) but T' still owes a "
                           f"send at ({s_sub})")
        return True, ""

    return sim(sub.initial_state, sup.initial_state)


# ── (2b) runtime tolerant gate: independent-receive output anticipation ───────

def anticipable(efsm: EFSM, state: str, peer: str, label: str,
                max_depth: int | None = None) -> bool:
    """True iff a send (peer!label) may be SAFELY anticipated at `state`: the
    only pending obligations before it are receives, and it is enabled on EVERY
    branch reachable by completing those receives.

    Called only when the send is NOT strictly enabled at `state` (the tolerant
    gate's relaxation). Bounded forward search over receive-only transitions.
    """
    if max_depth is None:
        max_depth = len(efsm.states) + 1

    def go(st: str, depth: int, seen: frozenset) -> bool:
        outs = efsm.transitions_from(st)
        # directly enabled here?
        if any(t.direction == "send" and t.peer == peer and t.label == label
               for t in outs):
            return True
        sends = [t for t in outs if t.direction == "send"]
        recvs = [t for t in outs if t.direction == "receive"]
        # any OTHER send pending, or nothing pending, or depth exhausted, or a
        # loop back to a seen state without enabling s ⇒ not safely anticipable
        if sends or not recvs or depth <= 0 or st in seen:
            return False
        # only receives pending: s must be enabled on EVERY receive branch
        seen2 = seen | {st}
        return all(go(t.target, depth - 1, seen2) for t in recvs)

    # must NOT be directly enabled at `state` (that would be strict-legal, not
    # an anticipation) — but the recursion's base handles the deeper enable.
    if any(t.direction == "send" and t.peer == peer and t.label == label
           for t in efsm.transitions_from(state)):
        return False  # strictly enabled: not an anticipation
    outs = efsm.transitions_from(state)
    recvs = [t for t in outs if t.direction == "receive"]
    sends = [t for t in outs if t.direction == "send"]
    if sends or not recvs:
        return False
    return all(go(t.target, max_depth - 1, frozenset({state})) for t in recvs)
