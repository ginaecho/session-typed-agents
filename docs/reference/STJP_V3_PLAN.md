# STJP v3 — plan: a governed, decentralized session-typed runtime

**Drafted 2026-06-17.** Synthesizes `../archive/GOVERNANCE_TOOLKIT_ASSESSMENT.md` (MS Agent
Governance Toolkit) and `../archive/RELATED_WORK_DELM.md` (DeLM — "Decentralized
Language Models," an external paper/runtime for fast, controller-free multi-agent
execution) into a concrete next-version architecture. The thesis in one line:

> **v1/v2 proved STJP makes coordination correct. v3 makes it (a) *governed* —
> STJP becomes a policy generator other systems consume — and (b) *decentralized*
> — STJP's projection becomes the safety layer of a fast, controller-free
> runtime.** The formal contract stays the core; we plug it into two ecosystems
> instead of running it only in our own round-robin harness.

## 1. Where v3 sits

```
        intent ──► global type ──Scribble──► projected local types  (STJP core: unchanged)
                                                 │
            ┌────────────────────────────────────┼─────────────────────────────────────┐
            ▼ governance plane                    ▼ execution plane                       
   PolicyDocument (toolkit schema)        DeLM-style shared-context runtime              
   + audit/compliance + identity          + STJP monitor as write-verifier              
   (STJP = policy SOURCE)                 + EFSM enabled-set as claim predicate          
```

Two planes, one contract. The governance plane answers *"is this allowed, and
prove it for audit"*; the execution plane answers *"run it fast without a central
orchestrator, safely"*. Both are driven by the same projected local types we
already generate.

## 2. Plane A — Governance (reuse the toolkit)

**Goal:** STJP stops being a bespoke monitor and becomes a *policy generator* that
emits standards-shaped artifacts, so any toolkit-compatible runtime can enforce
STJP protocols and produce compliance evidence (OWASP Agentic Top-10, NIST AI
RMF, EU AI Act, SOC 2).

### A1. Policy export (`stjp_core/governance/policy_export.py`) — ✅ DONE 2026-06-17
Project a case → a `PolicyDocument` in the toolkit's schema. **Implemented and
verified:** `python -m stjp_core.governance.policy_export <case>` emits
`protocols/policy.generated.json` — finance = 30 rules (4 refinement, 3 stateful
choice-guard), banking = 44 rules (4 refinement, 4 choice-guard), default `deny`
(fail-closed), `conflictResolution: DENY_OVERRIDES`, and an `stjpExtensions` block
declaring the three condition types below. Mapping:
- each EFSM transition → an `allow` rule (priority by state) keyed on
  `(sender, receiver, label)` + the current session state;
- each refinement/choice guard → a `condition` (field-op-value where possible;
  our richer predicate attached as `message`/metadata);
- the gate's reject-before-delivery → `deny` + the re-prompt as the rule `message`;
- a default `deny` (fail-closed) — matches the toolkit's posture.
Deliverable: one finance case exported + loadable by the toolkit's engine.

### A2. Audit-compatible verdicts — ✅ DONE 2026-06-17 (`stjp_core/governance/audit_export.py`)
Verified post-hoc on the grand n=10 run: intent-only arm → 180 entries all `deny` (OWASP/NIST-tagged); gate arm → 100 allow / 5 deny. `python -m stjp_core.governance.audit_export <run_dir> <arm>`.
Re-shape `stjp_live_emitter` records to be a superset of the toolkit's audit
entry (add `agent_identity`, `session_id`, `decision`, `matched_rule = EFSM
transition/guard`). A run then yields a **compliance audit trail**, not just a
benchmark log — the enterprise story.

### A3. Identity binding (reuse SPIFFE/DID)
Today the monitor trusts the role label in a message. Adopt the toolkit's
attribution so "this message really came from the RevenueAnalyst agent" is
cryptographic — closes a spoofing gap. Monitor consumes the identity in its
`ExecutionContext`.

### A4. Contribute upstream (enhance their engine)
Propose three condition-type extensions their stateless rule model lacks, with
STJP as the reference backend: **sequence/after** (ordering, from our EFSM),
**stateful-value** (choice guards over prior messages), **provenance/context**
(v3 criticality C1/C2). This is STJP's differentiated contribution to the
ecosystem.

## 3. Plane B — Decentralized execution (compose with DeLM)

**Goal:** replace our round-robin `foundry_runner` (whose cost is dominated by
polling every role each turn — `../results/RUN_REPORT_2026-06-11.md` §4.4) with a
DeLM-style **shared-context + async-claim** substrate, made *safe* by STJP.

**✅ Prototype DONE 2026-06-17** — `stjp_core/runtime/delm_runner.py` +
`experiments/scripts/smoke_delm_runtime.py`. Offline mechanics smoke test (a
quick end-to-end check; deterministic oracle, finance valid draft) proves
B1+B2+B3 below in one runtime:
- terminates deadlock-free on **both** branches, 0 violations;
- **−83% agent calls** vs round-robin (11 scheduled polls vs 66) — the cost lever
  realized: only enabled senders are polled, never idle WAIT roles;
- ENFORCE blocks the value-wrong branch pre-delivery and recovers; OBSERVE
  delivers + flags it — same posture as the foundry gate/observer arms;
- order-jumping is *structurally* impossible (a role with no enabled send is never
  offered a turn), so only value-wrong writes ever reach the verifier.
The `Agent` interface accepts the Foundry LLM agent unchanged — swapping the oracle
for the LLM is the online step (the only thing left to measure: real cost-to-goal
on this substrate vs the round-robin runner).

### B1. STJP monitor as the shared-context write-verifier — ✅ (`STJPRuntime._probe/_commit`)
DeLM admits "verified" updates that are only self-verified. Insert the STJP
monitor as the admission check: an update enters the shared context iff it
conforms to the writer's local type + refinement + choice guard. "Verified"
becomes *formally* verified.

### B2. EFSM enabled-set = claim predicate — ✅ (`STJPRuntime.enabled_senders`)
Only a role with an enabled action in the current global state may claim the next
task. This gives DeLM's queue the deadlock-freedom guarantee it lacks, and is the
direct realization of our own lesson ("the projection must *schedule*, not just
judge" — §5.1).

### B3. Type-directed context splitting — ✅ (`SharedContext.view_for`)
Each agent's view of the shared context = its projected local type's RECV set
(principled, not heuristic). This is the user's "projection ≈ context-splitting"
insight made rigorous, and should improve both cost (less to read) and accuracy
(exactly what's needed).

### B4. Provenance on the substrate
The v3 C1 gate becomes a write-admission rule: an update citing another agent's
result must be derivable from it — prevents the build-on-a-hallucination failure
an unverified shared context invites.

## 4. The v3 benchmark (ties to criticality redesign)

Run the **5 arms × {neutral, critical} variants** (BENCHMARK_DESIGN_V3) on **two
runtimes**: the current round-robin and the new DeLM-style substrate. New columns:
- **cost-to-goal** and **time-to-goal** on each runtime (does decentralization
  cut the cost we identified, at equal CGC — Critical-Goal Completion?);
- **CGC** as the headline;
- **audit completeness** (does every decision produce a compliant entry?).
Expected story: the DeLM substrate cuts cost-to-goal substantially while the STJP
monitor holds CGC and S4=0 — *fast AND correct*, which neither alone delivers.

## 5. Sequenced roadmap (smallest valuable first)

| step | deliverable | depends on | size |
|---|---|---|---|
| 1 | ~~`policy_export.py` — finance → PolicyDocument~~ ✅ DONE (finance + banking) | — | S |
| 2 | ~~audit-compatible verdict export~~ ✅ DONE (real-trace verified) | — | S |
| 3 | neutral/critical case variants (finance, banking) | BENCHMARK_DESIGN_V3 | M |
| 4 | ~~DeLM-style runner: shared context + claim + **STJP monitor as verifier**~~ ✅ DONE (prototype + smoke) | EFSM enabled-set (exists) | M-L |
| 5 | ~~EFSM claim-predicate + type-directed context views~~ ✅ DONE (in step 4) | step 4 | M |
| 6 | v3 benchmark: 5 arms × 2 variants × 2 runtimes, n≥10, cost/time-to-goal | steps 3-5 | L |
| 7 | identity binding (SPIFFE/DID) | toolkit integration | M |
| 8 | upstream proposal: sequence/stateful/provenance conditions | step 1 | S (writing) |

**Done this session (2026-06-17): steps 1, 2, 4, 5** — policy export, audit
export, and the DeLM-style runtime (scheduler + verifier + type-directed views),
all verified offline on real artifacts. **Remaining:** step 3 (neutral/critical
case variants) and step 6 (the two-runtime benchmark) are the research payoff;
step 7 (identity) + step 8 (upstream proposal) are ecosystem positioning.

## 6. What does NOT change (guard rails)

- The **core stays formal**: Scribble validation, projection, monitor verdicts,
  choice guards, the gate. v3 wraps and distributes them; it does not replace the
  type theory with heuristics.
- **Reversibility**: each plane is additive and behind a flag/module, exactly like
  the v2 frozen-snapshot discipline. The round-robin runner and current metrics
  remain the baseline of record.
