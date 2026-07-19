# MPST as Static-Time Validator for Agent Interaction Efficiency

How multiparty session types prove agent-system interactions are efficient and cost-saving *before* anything runs, and how monitors derived from local projection enforce that property at runtime — decentralised, no central observer.

This is the technical heart of `AI_verf`. Drafted 2026-05-02. Companion: `PROPOSAL.md` (architecture), `RESEARCH.md` (bibliography).

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. The MPST loop in agent terms](#1-the-mpst-loop-in-agent-terms)
- [2. Eight static-time guarantees → cost / efficiency translation](#2-eight-static-time-guarantees--cost--efficiency-translation)
  - [2.1 Bounded message count](#21-bounded-message-count)
  - [2.2 Deadlock-freedom — no token-burning stuck states](#22-deadlock-freedom--no-token-burning-stuck-states)
  - [2.3 No off-protocol detours](#23-no-off-protocol-detours)
  - [2.4 Maximal parallelism by construction](#24-maximal-parallelism-by-construction)
  - [2.5 Tight capability projection — minimum permissions per role](#25-tight-capability-projection--minimum-permissions-per-role)
  - [2.6 Bounded recursion — no infinite-loop billing surprises](#26-bounded-recursion--no-infinite-loop-billing-surprises)
  - [2.7 Refinement contracts cut bad inputs early](#27-refinement-contracts-cut-bad-inputs-early)
  - [2.8 Static composition — sessions you can plug together](#28-static-composition--sessions-you-can-plug-together)
- [3. From local projection to runtime monitor](#3-from-local-projection-to-runtime-monitor)
  - [3.1 The monitor is *generated*, not authored](#31-the-monitor-is-generated-not-authored)
  - [3.2 Monitor algorithm](#32-monitor-algorithm)
  - [3.3 Where the monitor sits](#33-where-the-monitor-sits)
  - [3.4 Cost of the monitor itself](#34-cost-of-the-monitor-itself)
  - [3.5 The runtime data model: State + Assignee + Audit Trail](#35-the-runtime-data-model-state--assignee--audit-trail)
  - [3.6 Failure modes the monitor catches](#36-failure-modes-the-monitor-catches)
- [4. Composition theorem in plain language](#4-composition-theorem-in-plain-language)
- [5. Worked example (sketch)](#5-worked-example-sketch)
- [6. Honest boundaries](#6-honest-boundaries)
- [7. Pointer to implementation](#7-pointer-to-implementation)
- [8. References (load-bearing for this document)](#8-references-load-bearing-for-this-document)
<!-- MENU:END -->

## 1. The MPST loop in agent terms

In MPST, you write a **global type** `G` describing the protocol of a multi-party interaction (e.g., a router agent, a tool-using executor, a verifier sub-agent, plus their tools and the orchestrator):

```
G  ::=  p → q : { ℓᵢ(τᵢ) . Gᵢ }ᵢ            choice/branching
     |  μX. G                                 recursion
     |  X                                     recursion variable
     |  end                                   termination
```

`p → q : ℓ(τ)` reads "participant `p` sends label `ℓ` carrying payload of type `τ` to participant `q`." Refinement-MPST extends `τ` with logical predicates (e.g., `{x: Int | x > 0}`).

You then **project** `G` onto each role `p`, producing a local type `L_p` — a finite-state automaton describing exactly what messages `p` may send and receive at each protocol point. The metatheoretic guarantees come from three properties of well-formed global types:

- **Communication safety**: every send has a matched receive of compatible type.
- **Session fidelity**: the execution trace refines `G`.
- **Progress / deadlock-freedom**: a well-typed configuration never gets stuck in a single session.

For agents, the participants are: the orchestrator, each named sub-agent / skill, each tool (MCP server endpoint), and the LLM endpoint itself (treated as a `dyn` gradual participant — see Igarashi et al. ICFP'17).

---

## 2. Eight static-time guarantees → cost / efficiency translation

Each item below is a property MPST establishes before runtime, with its translation to dollars, tokens, or wall-clock latency.

### 2.1 Bounded message count
A well-formed `G` has finite or bounded-recursive message exchanges. Projection lets you compute, for each role, a worst-case message count `N_p` per session.

**Cost claim.** Every well-typed run uses at most `N_p` LLM/tool invocations at role `p`. Token cost is bounded by ` ∑_p N_p × max_payload_size_p` × per-token rate. This becomes a contractual SLA, not a hope.

### 2.2 Deadlock-freedom — no token-burning stuck states
The dominant failure mode of multi-agent systems is silent stalls: agent A waits for B's response that never comes (different assumptions, different schemas, or a missing handoff). The system keeps emitting reasoning tokens, retry tokens, "let me think" tokens — until a timeout or a billing alert.

**Cost claim.** Honda/Yoshida 2008 (and Scalas/Yoshida 2019 for the modern formulation) prove a well-typed configuration never deadlocks within a single session. Cuts the dominant cost-runaway pathology.

### 2.3 No off-protocol detours
Communication safety means every message label/payload `p` emits is one the protocol permits at that point. In agent terms: if `L_planner` says "next, emit `tool_call(search, q: NonEmptyString)`," then alternatives like "let me reconsider" or "let me ask the user first" are statically rejected.

**Cost claim.** Eliminates the meandering-agent failure mode where reasoning loops produce tokens without protocol progress. Compare to AgentSpec (ICSE'26): they catch >90% of unsafe executions with rules; MPST catches *all* off-protocol detours by construction, plus gives the structural guarantees AgentSpec lacks.

### 2.4 Maximal parallelism by construction
In MPST, message exchanges not constrained by causality are syntactically independent. Parameterised MPST (Yoshida et al. 2010) extends this to fan-out across `n` workers. The projection engine identifies, for each protocol prefix, the set of message exchanges with no causal dependency — which can be issued concurrently.

**Cost claim.** Minimum wall-clock latency. If your protocol is "summariser fans out to `k` reviewers in parallel, then aggregates," the projection proves the `k` calls can run concurrently and the aggregation must wait. No emergent serialisation; no missed parallelism.

### 2.5 Tight capability projection — minimum permissions per role
Each role's local type uses only the message labels it sends/receives. The set of *outgoing* labels is the role's *minimum required capability set*. Static check: declared capability surface (Claude Code `allowed-tools`, MCP server allowlist, OpenAI Agents SDK `tools=`) ⊇ projected required capabilities.

**Cost claim.** Two effects. (i) Security: agents cannot invoke tools they don't need. (ii) Cost: over-provisioned `allowed-tools` lists tend to be invoked speculatively ("let me also check the database") — projection rejects that as off-protocol. Empirically, capability-tightening is one of the highest-ROI cost interventions in production agent systems.

### 2.6 Bounded recursion — no infinite-loop billing surprises
Recursive types `μX. G` need a termination guarantee. *Less is More* MPST has decidable termination for projections under standard restrictions (no unguarded recursion, no infinite branching). For agent loops (reflection, retry, deliberation), this means the loop must have a bounded depth or a guarded termination condition — statically checked.

**Cost claim.** No "agent kept asking itself questions until the rate limit kicked in" stories. The bound `k` on iterations is a number you can audit before deploy.

### 2.7 Refinement contracts cut bad inputs early
Bocchi et al. ECOOP'24 attach SMT-discharged predicates to message payloads. For agents: tool-call arguments carry refinements (`{path: String | path matches ^/safe/.+$}`, `{n: Int | 1 ≤ n ≤ 100}`). Where the predicate's free variables are statically known, Z3 discharges them at type-check time. Where they depend on LLM output, the refinement becomes a runtime monitor check.

**Cost claim.** A malformed tool argument that would have wasted an LLM call (and possibly an entire downstream session) is rejected before the call ever happens. Refinement-cuts before LLM calls is one of the cheapest correctness gates available.

### 2.8 Static composition — sessions you can plug together
Hybrid MPST (PACMPL'23) gives compositional guarantees for systems with multiple concurrent sessions. For agents: independently-verified skills can be composed without re-verification, as long as their session interfaces are compatible.

**Cost claim.** Verification is pay-once-per-skill, not pay-per-deployment. The compositional reasoning collapses what would be quadratic recheck cost into linear.

---

## 3. From local projection to runtime monitor

The Bocchi/Chen/Demangeon/Honda/Yoshida theorem (FORTE'13, TCS'17) is the keystone: **if every endpoint's local monitor enforces its projected local type, the global protocol is observably satisfied**. No central observer is required. Each agent's wrapper checks only its own boundary; global compliance falls out of local compliance for free.

### 3.1 The monitor is *generated*, not authored
For each role `p`, the projection produces a local type `L_p`, which compiles to a finite-state automaton `M_p = (S, s_0, Σ, δ, F)`:
- `S`: states of the local protocol
- `s_0`: initial state
- `Σ`: alphabet of messages (label + payload type)
- `δ : S × Σ → S`: transition function (potentially refined by SMT predicates)
- `F`: accepting (termination) states

The monitor for role `p` is precisely an interpreter of `M_p` with a state pointer. Generation is mechanical; authoring is unnecessary.

### 3.2 Monitor algorithm
```
monitor_p(trace_event e):
    s = current_state
    candidates = { t ∈ δ(s, _) : label(e) = label(t) }
    if candidates is empty:
        violation(reason="off-protocol", expected=δ(s, _), got=e)
        return
    for t in candidates:
        if refinement(t).holds_for(e.payload):
            current_state = target(t)
            return
    violation(reason="refinement-failed", transition=candidates, got=e)
```

The monitor sees: every outgoing message (tool call, sub-agent invocation, handoff, reply to parent) and every incoming message. It does **not** see the LLM's internal reasoning; it sees the boundary. That's the point — the boundary is the protocol surface.

### 3.3 Where the monitor sits
For each supported harness, the monitor lives at a different attachment point, but the algorithm is identical:

| Harness | Attachment point | Trace source |
|---|---|---|
| Claude Code subagent | wraps subagent stdin/stdout | session JSONL + hook events |
| OpenAI Agents SDK | `Runner` event hook | built-in tracing |
| LangGraph node | node decorator | LangSmith run tree |
| AutoGen agent | message middleware | conversation log |
| MCP tool call | server-side or client-side gateway | OTel `gen_ai.tool.call` span |
| Generic | OTel exporter | `gen_ai.*` semantic-convention spans |

The shared substrate is **OTel GenAI semantic conventions** (`gen_ai.agent.*`, `gen_ai.tool.*`, experimental as of March 2026 but now in OTel 1.37). For non-instrumented harnesses, the framework-native trace is parsed into the same internal event shape.

### 3.4 Cost of the monitor itself
Per-event cost: an automaton step (O(1)) plus, if a transition has a refinement, an SMT check or a JIT-compiled predicate evaluation (microseconds for typical predicates). Compare to LLM-as-judge, which costs one extra LLM call per check (hundreds of milliseconds, $0.001–$0.01 each). The MPST monitor is 3+ orders of magnitude cheaper per check, deterministic, and produces a cited violation rather than a probabilistic verdict.

### 3.5 The runtime data model: State + Assignee + Audit Trail

The monitor's runtime view collapses to three coordinates. They are not new — they fall out of MPST projection directly:

| Runtime view | MPST counterpart | Where Scribble emits it |
|---|---|---|
| **State (status)** | Current node in the role's projected EFSM | `scribblec.sh -fsm Proto Role` |
| **Assignee (owner)** | The role / participant `p` from the global type | Embedded in every transition label (`p!ℓ`, `p?ℓ`) |
| **Audit Trail (history)** | The execution trace = a path through the global type's unfolding | The sequence of transitions taken from `s_0` to current state |

Together: a **Graph** — the projected protocol automaton with traces overlaid. *The structure under the interface.*

This is the right export schema for three concurrent needs:
- **SARIF** for static violations (CI integration).
- **A graph view** (state nodes, role-coloured edges, trace path highlighted; deviations flagged) for runtime conformance.
- **Linear/Jira-shaped audit records** for compliance contexts.

The differentiation vs. LangSmith run trees or OTel trace browsers: **the nodes are typed protocol states, not span IDs**. LangSmith shows what happened; AI_verf shows what happened *against what was projected*, with deviations flagged. Without that distinction, AI_verf is a competitor; with it, AI_verf is the structural layer those tools lack.

Concrete example from `examples/agent_workflow/AgentWorkflowFixed.scr` — Scribble's projection for role E:

```
state Loop:
  O?apply(String) → state Apply       (Assignee: O sends, E receives)
  O?skip()        → state Loop        (loopback; Assignee: O sends)
  O?abort()       → state Terminate   (Assignee: O sends)
state Apply:
  O!applied(String) → state Terminate (Assignee: E sends)
```

Three runtime fields written for free: State (`Loop`/`Apply`/`Terminate`), Assignee (`O` or `E` per transition), Audit Trail (the sequence of transitions taken). The graph IS the spec.

Caveat: "Assignee" assumes one canonical sender per message. Multi-cast / broadcast (less common in agents but real for fan-out) needs a small data-model extension — make it explicit, do not hide it.

### 3.6 Failure modes the monitor catches
- **Off-protocol message** — agent emitted a label not in the current state's transitions.
- **Refinement violation** — message label correct, payload predicate fails.
- **Premature termination** — agent halted in a non-accepting state.
- **Capability escalation** — agent invoked a tool not in its projected outgoing set.
- **Deadlock precursor** — no transition matches and no incoming expected; escalate before tokens are wasted on retry.

---

## 4. Composition theorem in plain language

> **Theorem (Bocchi, Chen, Demangeon, Honda, Yoshida — FORTE'13; refined in TCS'17).** Let `G` be a well-formed global type with projections `{L_p}` for participants `p`. If, in any execution, every participant `p` is monitored against `L_p` and no monitor reports a violation, then the joint behaviour observably satisfies `G`.

In practice: deploy one monitor per agent role. Each monitor only knows its own local type. If they all pass, the entire multi-agent session has obeyed the global protocol. The user does not need to set up a central observer, and no monitor has to know about the others. This decentralisation is what makes the architecture scalable to large agent systems and respectful of multi-tenant boundaries.

---

## 5. Worked example (sketch)

A simple Claude Code subagent flow: `orchestrator` delegates to `searcher` (Read-only), which produces candidates; `verifier` (Read-only + grep) checks them; `executor` (Edit + Bash) applies the chosen fix.

Global type:
```
μLoop.
  orchestrator → searcher : query(q: NonEmptyString) .
  searcher → orchestrator : candidates(cs: List[Patch] {len(cs) ≤ 5}) .
  orchestrator → verifier : verify(c: Patch) .
  verifier → orchestrator : { ok(c).
                                orchestrator → executor : apply(c) .
                                executor → orchestrator : applied(result) .
                                end
                            | retry. Loop }
```

Static checks produce:
- `L_searcher` allows only `query` in, `candidates` out — capability is `[Read, Grep]`. Reject any subagent declaration with `[Read, Grep, Bash]`.
- `L_executor` allows only `apply` in, `applied` out — but its projected outgoing set includes `Edit` and `Bash` capability tokens (via the `apply` action's refinement). Reject if `tools` frontmatter omits them.
- The `retry` branch is bounded: under `Less is More` projection, the recursion is well-formed only if `candidates` shrinks per iteration (a refinement) or a max iteration count is supplied. Otherwise, type-check fails.
- Refinement `len(cs) ≤ 5` is discharged at runtime on the searcher's output — wasted token budget on a 50-candidate list is rejected before the verifier is even invoked.

Per-role monitors are generated automatically. At runtime, the searcher's monitor accepts only the `candidates(...)` reply with a list of `≤ 5`. The verifier's monitor allows only `ok(c) | retry` as outputs. The executor's monitor catches if it ever tries to write to a path outside the patch.

---

## 6. Honest boundaries

What MPST static-time validation **cannot** do:

- Cannot verify the *content* of an LLM's reasoning matches its action (that is HyperLTL territory, k-safety; phase 5 of the project plan).
- Cannot verify intent or alignment (calibrated LLM-as-judge, not a typing system).
- Cannot prove the answer to an open-ended question is correct (no oracle).
- Cannot statically discharge refinements that depend on LLM-generated values — those become runtime checks.
- Recursion bounds and projection are conservative — some legitimate agent behaviours will be rejected (false positives). The escape hatch (`@unsafe` annotation) preserves capability and refinement checks while disabling structural ones for marked regions.

The product surface must distinguish "MPST-proved efficiency property" from "calibrated content-quality estimate." The first is hard guarantee; the second is bounded-confidence. That distinction is the differentiator vs. every existing eval framework.

---

## 7. Pointer to implementation

- Reuse `mpstk` (Scala, Scalas) or `nuScr` (OCaml, MRG) for the projection engine — do not reimplement.
- Use Z3 (or cvc5) for SMT-discharged refinements.
- Use the OpenTelemetry GenAI semantic conventions as the canonical event schema; framework-specific adapters convert to it.
- Per-role monitor generation is a tree-walk over the projected local type producing a small interpreter — target output is a single Python or TypeScript file per role for easy embedding.
- For the LLM-as-`dyn` boundary, follow Igarashi/Thiemann/Tsuda/Vasconcelos/Wadler ICFP'17: insert casts at the protocol/LLM boundary; the cast *is* the monitor.

---

## 8. References (load-bearing for this document)

- Honda, Yoshida, Carbone. *Multiparty Asynchronous Session Types*. POPL'08; JACM'16.
- Scalas, Yoshida. *Less is More: Multiparty Session Types Revisited*. POPL'19.
- Igarashi, Thiemann, Tsuda, Vasconcelos, Wadler. *Gradual Session Types*. ICFP'17 / JFP'19.
- Bocchi, Chen, Demangeon, Honda, Yoshida. *Monitoring Networks through Multiparty Session Types*. FORTE'13; TCS'17.
- Bocchi et al. *Refinements for Multiparty Message-Passing Protocols*. ECOOP'24.
- Yoshida, Deniélou, Bejleri, Hu. *Parameterised Multiparty Session Types*. 2010.
- *Hybrid Multiparty Session Types*. PACMPL'23.
- Wang, Poskitt, Sun. *AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents*. ICSE'26.

Full bibliography in `RESEARCH.md`.
