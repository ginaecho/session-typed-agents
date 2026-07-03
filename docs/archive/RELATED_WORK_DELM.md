# DeLM (arXiv 2606.10662) vs / with STJP — is it a threat, and how to reuse it

**Reviewed 2026-06-17.** *DeLM: Decentralized Language Models* (Yuzhen Mao,
Azalia Mirhoseini). Code: github.com/yuzhenmao/DeLM.

## 1. What DeLM is

A **runtime execution model** for multi-agent LLM systems that removes the
central orchestrator. Parallel agents **asynchronously claim subtasks** from a
queue, **read accumulated progress** from a **shared verified context**, do local
reasoning, and **write back compact verified updates** — building on each other
without routing everything through a controller. Reported: ~50% cost reduction +
accuracy gains on SWE-bench Verified and LongBench-v2.

## 2. Is it a threat to STJP? No — different layer (you are right)

The decisive fact, confirmed from the paper: **DeLM has no formal checker.**
"Verified" in "shared verified context" means *compact, self-/peer-verified
updates* (an LLM-level consistency step), **not** a session-type / deadlock /
projection guarantee. So:

| axis | DeLM | STJP |
|---|---|---|
| layer | **runtime substrate** (how work is distributed & shared) | **coordination contract** (who may say what, in what order, with what values) |
| guarantee | empirical (cost/accuracy on benchmarks) | **formal** (deadlock-freedom, projection-soundness via Scribble) |
| "verified" | self/peer-consistency of an update | monitor-checked against a proven protocol |
| coordination shape | emergent from shared context + queue | declared, validated, projected |
| failure it targets | central-controller bottleneck, cost | wrong order, hallucinated inputs, unauthorized irreversible acts, deadlock |

They answer different questions. DeLM makes a decentralized system **fast and
cheap**; STJP makes a multi-agent system **correct and safe**. A DeLM system with
no contract can still deadlock, skip authorization, or build on a hallucinated
"verified" update — exactly the failures STJP catches.

## 3. How to reuse DeLM — four concrete integrations

The strongest framing: **STJP is the type system; DeLM is the runtime. Put the
type system on DeLM's runtime.**

1. **Type-directed context splitting.** DeLM splits/shares context heuristically.
   STJP's **projection already computes, per role, exactly which messages that
   role reads and writes** — a *principled* context split. Replace DeLM's
   implicit slicing with STJP local types: each DeLM agent's view of the shared
   context = its projected local type's RECV set. This is the user's own
   observation (projection ≈ context splitting) made rigorous, and it directly
   improves DeLM's accuracy (agents see exactly what they need, no more).

2. **Make "verified context" actually verified.** DeLM's write-back is
   self-verified. Insert the **STJP monitor as the verifier**: an update is
   admitted to the shared context only if it conforms to the writer's local type
   + refinement + choice guards. "Verified" stops meaning "the LLM thinks it's
   fine" and starts meaning "a deterministic checker proved it conforms." This is
   a drop-in hardening of DeLM's core primitive.

3. **EFSM-gated task claiming = liveness-safe decentralization.** DeLM agents
   asynchronously *claim* subtasks. STJP's EFSM says which roles have an
   **enabled action** in the current global state. Use it as the **claim
   eligibility predicate**: only an enabled role may claim. This gives DeLM's
   queue a deadlock-freedom guarantee it currently lacks — and is exactly the
   "projection must *schedule*, not just judge" lesson from our own runs
   (`STJP_RESEARCH_REPORT.md` §5.1), now applied to a decentralized substrate.

4. **Provenance on the shared substrate.** Our v3 C1 provenance gate
   (`criticality_gate.py`) checks a derived value traces to real data. On DeLM's
   shared context this becomes a write-admission rule: an update that cites
   another agent's result must be derivable from it — preventing the
   "build-on-a-hallucination" failure that an unverified shared context invites.

## 4. What STJP can borrow from DeLM (the other direction)

- **Decentralized execution to cut our cost.** Our cost analysis
  (`RUN_REPORT_2026-06-11.md` §4.4) found the turn-loop (poll every role,
  re-read static text) dominates tokens. DeLM's **async claim + shared context**
  is a concrete alternative to round-robin polling — and our EFSM gives the
  safe claim predicate. This is the most promising path to the "scheduling +
  projected views" savings we identified, with a real implementation to copy.
- **Compact verified updates** as the model for our "projected views": send each
  agent only the delta to the shared context its local type lets it observe,
  rather than the full session history.

## 5. One-paragraph positioning (for papers/talks)

> Decentralized runtimes like DeLM remove the orchestrator bottleneck and cut
> cost, but coordinate through an *unverified* shared context — they can still
> deadlock, skip authorizations, or build on hallucinated updates. STJP supplies
> the missing formal layer: a Scribble-verified protocol projected into per-agent
> local types that (a) define a principled context split, (b) turn "verified
> context" into monitor-checked conformance, and (c) gate task-claiming on
> proven liveness. The two compose: DeLM as the fast substrate, STJP as the
> correctness contract running on it.

## 6. To-do if pursued

1. Prototype: drive a 2–3 role case on a DeLM-style shared-context loop where the
   STJP monitor is the write-admission verifier; compare cost vs our round-robin
   `foundry_runner` at equal GCR.
2. Implement EFSM enabled-set as the claim predicate (reuse `efsm_parser`).
3. Measure: does type-directed context splitting beat DeLM's default on one of
   our cases? (accuracy + tokens.)
