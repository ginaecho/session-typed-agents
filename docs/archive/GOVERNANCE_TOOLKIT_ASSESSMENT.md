# STJP × Microsoft Agent Governance Toolkit — reuse & enhance

**Assessed 2026-06-17.** Sources: the toolkit landing page and the
**Agent OS Policy Engine 1.0** spec
(`microsoft.github.io/agent-governance-toolkit`). This is a fit analysis: what
STJP can *reuse* from the toolkit, and what STJP can *contribute back* that the
toolkit's policy model does not currently express.

## 1. What the toolkit is

A governance layer for autonomous agents: **policy enforcement**, cryptographic
**identity/attribution** (SPIFFE/DID/mTLS), tamper-evident **audit**, and
execution **sandboxing**. Nine named specs; the one that overlaps STJP is the
**Agent OS Policy Engine**.

### The Policy Engine, precisely
- **Policies = `PolicyDocument`** of priority-ordered `PolicyRule`s; each rule is
  a `condition` (field-operator-value), `action`, `priority`, `message`,
  `override`.
- **Operators:** `eq, ne, gt, lt, gte, lte, in, contains, matches` + pattern
  matching (substring/regex/glob).
- **Enforcement point:** a `PolicyInterceptor` at **tool-call** boundaries,
  checking, in order: human-approval, allowed-tools, blocked-patterns,
  call-count.
- **Inputs:** an `ExecutionContext` (agent identity, session, tool name + args,
  call counts, token usage, path, hashes).
- **Decisions:** `allow / deny / audit / block`, plus argument **sanitization**.
- **Semantics:** first-match by priority; **fail-closed** (unhandled exception ⇒
  deny); folder-hierarchy merge with "parent deny can't be overridden";
  conflict strategies (DENY_OVERRIDES, ALLOW_OVERRIDES, …).
- **Audit:** structured entry per decision (policy, matched rule, action,
  context snapshot, timestamp); compliance mappings (OWASP Agentic Top-10, NIST
  AI RMF, EU AI Act, SOC 2).

## 2. The exact correspondence to STJP

STJP's runtime monitor/gate **is a policy engine** — for a different policy
*source* and *enforcement granularity*:

| concept | Agent Governance Toolkit | STJP |
|---|---|---|
| enforcement point | tool call | **inter-agent message** (send/receive) |
| policy source | hand-written YAML rules | **auto-derived by projection** from a Scribble-verified global type |
| condition language | field-operator-value (stateless, single context) | refinement predicates (sandboxed Python) **+ stateful choice guards over message history** |
| ordering / liveness | not expressible (rules are per-action) | **native** — EFSM encodes sequence; deadlock-freedom *proven* before runtime |
| decision | allow/deny/audit/block + sanitize | accept / off_protocol / unexpected_peer / refinement / choice_guard; gate = **reject-before-delivery + re-prompt** |
| fail-closed | yes | gate denies on any verdict (same posture) |
| audit | structured per-decision entry | `events.jsonl` per-message verdict (same shape, finer grain) |

The headline: **the toolkit's engine needs a human to write the rules and cannot
express "B must happen before C" or "this value must derive from that message";
STJP's rules are generated from one sentence of intent and are proven
deadlock-free.** They sit at complementary layers (tool-call vs message) and
compose.

## 3. What STJP should REUSE (adopt their conventions)

1. **`ExecutionContext` + audit-entry schema.** Re-shape STJP's `events.jsonl`
   verdict records to be a superset of their audit entry (add agent identity,
   session id, decision, matched-rule = the EFSM transition/guard). One line of
   mapping unlocks their **compliance reporting** (OWASP/NIST/EU AI Act/SOC 2)
   for free — a strong enterprise story for STJP with zero new science.
2. **Fail-closed + conflict-resolution vocabulary.** STJP's gate is already
   fail-closed; adopt their named strategies (DENY_OVERRIDES, MOST_SPECIFIC_WINS)
   so multi-policy composition (e.g. STJP protocol policy + an org security
   policy) has defined semantics.
3. **Folder-hierarchy policy merge** as the model for **layered protocols**: an
   org-level invariant (`never debit before approval`) set high, a case-level
   protocol below — "parent deny can't be overridden" is exactly what we want
   for safety invariants that a generated protocol must not relax.
4. **Identity layer (SPIFFE/DID).** STJP currently trusts the role label in a
   message; their attribution layer would let the monitor *cryptographically*
   bind "this message really came from the RevenueAnalyst agent" — closes a
   spoofing gap we have not addressed.

## 4. What STJP CONTRIBUTES (enhance their engine)

1. **Protocol-derived policies.** STJP can **emit its projected contracts as
   `PolicyDocument`s** in their schema — turning "the LLM authored a Scribble
   protocol, validated and projected" into a *generator* of governance policies.
   Their engine gets rules it could never get a human to write correctly
   (deadlock-free by construction).
2. **Ordering & liveness policies.** Their rules are per-action and stateless;
   they cannot say "tool X only after tool Y in this session." STJP's EFSM is
   exactly a compiled stateful policy. Proposal: a new condition type in their
   model, `sequence`/`after`, backed by an STJP EFSM walker.
3. **Stateful, value-dependent conditions.** STJP choice guards
   (`when float(RawRevenueData) > 50000 require HighBranch`) are conditions over
   *prior observed values* — beyond their single-context field-op-value. A clean
   extension to their condition grammar.
4. **Provenance / context gates (v3 criticality).** The C1/C2 gates
   (`criticality_gate.py`) are governance checks their engine has no notion of:
   "the value you act on must derive from data you received", "you must consume
   all inputs before producing output." These map to OWASP Agentic risks
   (excessive agency, hallucinated-input) and are attractive upstream additions.

## 5. Recommended next steps (small, high-leverage)

1. Write `stjp_core/governance/policy_export.py`: project a case → a
   `PolicyDocument` (their schema). One case, one afternoon; proves the
   "STJP as policy generator" story concretely.
2. Re-shape the emitter's verdict record to be audit-entry-compatible
   (`stjp_core/monitor/stjp_live_emitter.py`), so a run produces a compliance
   audit trail, not just a benchmark log.
3. Open the conversation upstream: "ordering + stateful-value conditions +
   provenance gates" as condition-type extensions, with STJP as the reference
   backend.

**Verdict:** not a competitor — a *layer below* STJP's value-add and a natural
distribution channel for it. STJP supplies the one thing their policy model
structurally lacks (correct, ordered, generated-not-hand-written policies); they
supply the one thing STJP lacks (enterprise identity + compliance packaging).
