# AI_ST_verf — Roadmap (Epic)

A compiler-with-prover for AI agent specifications, grounded in **multiparty session types** (MPST) on top of Scribble. This is the single planning document for the project, organised as a three-phase epic. Per-phase technical references live in `MPST_STATIC.md` (semantics + runtime data model) and `SCRIBBLE.md` (compiler integration). Bibliography is in `RESEARCH.md`.

Last updated 2026-05-07. Supersedes the previously fragmented `PROPOSAL.md`, `PLAN_STJP.md`, `EXTENSIONS_PROPOSAL.md`, `SUBSESSIONS.md`, `REFINEMENTS.md`.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

  - [Thesis](#thesis)
  - [Architecture](#architecture)
- [Phase 1 — Foundation: Scribble compiler, monitor, authoring loop, lexical sub-sessions](#phase-1--foundation-scribble-compiler-monitor-authoring-loop-lexical-sub-sessions)
  - [1.1 Scribble integration & monitor pipeline](#11-scribble-integration--monitor-pipeline)
  - [1.2 Runtime refinement contracts (Bocchi 2010)](#12-runtime-refinement-contracts-bocchi-2010)
  - [1.3 STJP authoring loop — forward (NL → Scribble)](#13-stjp-authoring-loop--forward-nl--scribble)
  - [1.4 STJP authoring loop — reverse (skills.md → Scribble)](#14-stjp-authoring-loop--reverse-skillsmd--scribble)
  - [1.5 Sub-session composition (lexical, cross-file)](#15-sub-session-composition-lexical-cross-file)
  - [1.6 Real-world audit](#16-real-world-audit)
- [Phase 2 — Static verification: refinement discharge, subtyping, capability cross-check](#phase-2--static-verification-refinement-discharge-subtyping-capability-cross-check)
  - [2.1 Static refinement discharge via Z3](#21-static-refinement-discharge-via-z3)
  - [2.2 Synchronous structural subtyping](#22-synchronous-structural-subtyping)
  - [2.3 Refinement-aware subtyping](#23-refinement-aware-subtyping)
  - [2.4 Conditional / asserted MPST (full integration)](#24-conditional--asserted-mpst-full-integration)
  - [2.5 Capability projection ↔ frontmatter cross-check](#25-capability-projection--frontmatter-cross-check)
  - [2.6 Hard-schema linter](#26-hard-schema-linter)
- [Phase 3 — Advanced research: composition, async, dynamic, NL frontend, harness backends](#phase-3--advanced-research-composition-async-dynamic-nl-frontend-harness-backends)
  - [3.1 Hybrid MPST projection-preserving composition](#31-hybrid-mpst-projection-preserving-composition)
  - [3.2 Async subtyping (bounded-buffer fragment)](#32-async-subtyping-bounded-buffer-fragment)
  - [3.3 Dynamic-multirole MPST](#33-dynamic-multirole-mpst)
  - [3.4 Probabilistic refinement](#34-probabilistic-refinement)
  - [3.5 Bounded recursion + cost annotations](#35-bounded-recursion--cost-annotations)
  - [3.6 Hyperproperty layer (HyperLTL)](#36-hyperproperty-layer-hyperltl)
  - [3.7 LLM-assisted protocol extraction (annotate-then-convert)](#37-llm-assisted-protocol-extraction-annotate-then-convert)
  - [3.8 OTel GenAI trace adapter](#38-otel-genai-trace-adapter)
  - [3.9 Harness-specific monitor codegen](#39-harness-specific-monitor-codegen)
  - [3.10 LLM-as-`dyn` role + gradual session typing](#310-llm-as-dyn-role--gradual-session-typing)
  - [3.11 NL round-trip renderer](#311-nl-round-trip-renderer)
  - [Phase summary table](#phase-summary-table)
  - [Honest scope statement](#honest-scope-statement)
  - [Risk register](#risk-register)
  - [Strategic decisions (load-bearing)](#strategic-decisions-load-bearing)
  - [References](#references)
<!-- MENU:END -->

## Thesis

The core gap practitioners feel — *declared agent spec vs. observed behaviour* — is exactly where today's agent verification ecosystem (LLM-as-judge, AgentSpec, Agent-C, LangGraph asserts, Guardrails, NeMo) is weakest. Hard-schema declarations describe **capability surface** (what an agent *can* touch); the **behavioural contract** lives in markdown prose; nothing today proves the two agree.

AI_ST_verf closes this gap by:

1. **Compiling** agent markdown (`SKILL.md`, subagent frontmatter, `AGENTS.md`, MCP manifests, CrewAI YAML) into multiparty session types with refinement contracts.
2. **Projecting** each global type onto per-role local types, and **statically** discharging refinements via SMT (Z3).
3. **Generating** per-role runtime monitors that walk projected EFSMs against OTel GenAI traces — deterministic, sub-millisecond per event, no LLM in the hot path.
4. **Evolving** protocols safely via subtyping (synchronous Gay-Hole bisimulation + Chen-Dezani-Padovani-Yoshida LMCS'17 preciseness, with refinement-aware extension via Z3).

The **moat** is Scribble — a 20-year industrial protocol DSL with parser, well-formedness checker, projection algorithm, EFSM emitter, and monitor codegen. AI_ST_verf builds a markdown frontend and agent-harness backends *on top* of Scribble; it does not fork or reimplement the compiler middle.

---

## Architecture

```
                ┌───────────────────────────────┐
                │  Host repo                    │
                │  ─ SKILL.md, agents/*.md      │
                │  ─ AGENTS.md, CLAUDE.md       │
                │  ─ MCP manifests, hooks       │
                │  ─ CrewAI YAML, Cursor .mdc   │
                └───────────────┬───────────────┘
                                │  Phase 2 / 3
                       ┌────────▼────────┐
                       │ Spec extractor  │   Hybrid: schema parser for
                       │ (hybrid)        │   hard parts + annotate-then-
                       └────────┬────────┘   convert LLM pipeline for prose
                                │
                ┌───────────────▼─────────────────────┐
                │  Core IR — a triple                 │
                │  • Global MPST type (Less is More)  │
                │  • Refinement contracts (SMT)       │
                │  • LTL safety/liveness properties   │
                └───────────────┬─────────────────────┘
                                │  Phase 1 (Scribble)
                ┌───────────────▼───────────────┐
                │ Endpoint projection           │   Per-role local type
                │ (Scribble core, vendored)     │   one per agent / role
                └───────────────┬───────────────┘
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
       ┌────────────┐   ┌──────────────┐   ┌─────────────────┐
       │ Static     │   │ Monitor      │   │ Round-trip      │
       │ checker    │   │ generator    │   │ confirmation UI │
       │ Phase 1+2  │   │ Phase 1      │   │ Phase 3         │
       │ (SMT for   │   │ Phase 3:     │   └─────────────────┘
       │ refine-    │   │ harness      │
       │ ments;     │   │ backends)    │
       │ Phase 2:   │   └──────┬───────┘
       │ subtyping) │          │
       └────────────┘          ▼
                        ┌──────────────────────────┐
                        │ Runtime conformance      │
                        │ Phase 1: trace files     │
                        │ Phase 3: OTel + harness  │
                        │ adapters                 │
                        └──────────────────────────┘
```

The IR is a **triple**, not a single artifact, because the three things to check are heterogeneous:

1. **Structural conformance** (deadlock-freedom, ordering, who-talks-to-whom) → MPST projection.
2. **Data conformance** (argument predicates, output shapes) → refinement contracts → SMT.
3. **Temporal conformance** (never-X-after-Y, eventually-return) → LTL monitors.

The runtime side produces **State + Assignee + Audit Trail = Graph** — protocol nodes, role-coloured edges, trace path overlaid, deviations flagged. See `MPST_STATIC.md` §3 for the runtime data model.

---

# Phase 1 — Foundation: Scribble compiler, monitor, authoring loop, lexical sub-sessions

**Status: shipped (v0.1–v0.3, v0.6 sub-session composer, skills synthesizer reverse pipeline).**
**Goal: prove the toolchain end-to-end on real protocols, with a runtime monitor that's deterministic and correct.**
**Theorems used: Honda-Yoshida-Carbone POPL'08 / JACM'16 (projection); Bocchi-Chen-Demangeon-Honda-Yoshida FORTE'13 / TCS'17 (local-monitor compliance ⇒ global compliance); Demangeon-Honda CONCUR'12 (nested protocols).**

## 1.1 Scribble integration & monitor pipeline

The compiler middle — parse, well-formedness, projection, EFSM emission — is the hardest part of any verification framework. Scribble already has it, peer-reviewed and deployed for ~20 years. AI_ST_verf vendors `scribble-java` (Imperial MRG) at `vendor/scribble-java/` and consumes its CLI via `scribblec.sh`.

**What ships:**

- `tools/monitor.py` — runtime conformance checker. For each role: project global type to local type, emit EFSM, filter trace events, walk EFSM step-by-step, report PASS/FAIL with precise state and expected transitions on violation.
- `tools/refinements.py` — sandboxed predicate evaluator + `.refn` parser.
- `examples/pingpong/`, `examples/agent_workflow/`, `examples/agentic_labelling/` — demonstrators including a real-world audit on the Agentic_Labelling pipeline that caught three unfinished roles after the happy-path approve.

**What this proves:** the Bocchi/Chen/Demangeon/Honda/Yoshida composition theorem (FORTE'13). Local-monitor compliance for every role implies global protocol satisfaction; no central observer needed; runtime cost O(1) per event, three orders of magnitude cheaper than LLM-as-judge.

## 1.2 Runtime refinement contracts (Bocchi 2010)

Scribble's payload types are nominal. Real protocols want **value-level constraints**: `deposit(int) where x > 0`, `open(String) where matches(r"^[A-Z]{2}-\d{6}$", x)`, `apply(Patch) where startswith(path, "/safe/")`.

**Design choice: layer, do not fork.** Refinements live in a sidecar `.refn` file alongside the `.scr`. Scribble parses the protocol shape unchanged; AI_ST_verf reads both and enforces refinements at runtime. Trade-off accepted: refinements are not part of Scribble's well-formedness check until Phase 2 adds Z3 discharge.

**Predicate language:** sandboxed Python expressions over a single bound variable `x`. Whitelist of helpers (`len`, `abs`, `min`, `max`, `matches`, `startswith`, `endswith`, `contains`). AST validator rejects everything outside the whitelist (no attribute access, no lambdas, no imports, no `__class__`/`__bases__` games). Same syntax maps cleanly to SMT-LIB in Phase 2.

**`.refn` format:**

```ini
# Banking.refn
[C -> B : open]
type:    str
require: matches(r"^[A-Z]{2}-\d{6}$", x)

[C -> B : deposit]
type:    int
require: x > 0
require: x <= 1000000

[B -> C : balance]
type:    int
require: x >= 0
```

**Demos (`examples/banking/`):** one good trace, six violation traces split across **payload-type**, **refinement**, and **protocol-shape** classes (distinct error tags so consumers can route them — CI gate vs. runbook trigger vs. alert).

**Research basis:** Bocchi, Honda, Tuosto, Yoshida — *A Theory of Design-by-Contract for Distributed Multiparty Interactions* (CONCUR 2010). The hybrid static-plus-dynamic pattern is legitimised by Vassor & Yoshida, *Refinements for Multiparty Message-Passing Protocols* (ECOOP 2024).

## 1.3 STJP authoring loop — forward (NL → Scribble)

The Session-Typed Judge Panel's **Revisor** role: a convergence loop that translates user intent into a Global Protocol the Checker (Scribble) accepts.

```
def revisor_draft(intent, goals, max_iter=20):
    for i in range(max_iter):
        if i == 0:
            response = llm.complete(SYSTEM_PROMPT, initial_prompt(intent, goals))
        else:
            response = llm.complete(SYSTEM_PROMPT, revision_prompt(
                intent, goals,
                previous_scr=attempts[-1].scr,
                error=attempts[-1].check_result.error_summary))
        scr, refinements, justification = parse_response(response)
        check_result = checker.check(scr)
        if check_result.valid:
            return DraftResult(success=True, ...)
    return DraftResult(success=False, ...)
```

**Why this works:** the system prompt (~3k tokens) is cached with `cache_control: ephemeral`; revision deltas are <500 tokens; the Scribble error message ("Unfinished roles: {EA=38}") is the supervision signal. Worst-case 20-iteration cost ≈ $0.15 in tokens — competitive with one LLM-as-judge call.

**LLM is in the cold path.** Once the protocol converges, every subsequent execution is verified by the deterministic Monitor with zero LLM involvement. Single-translation-error catches happen at authoring time, not at runtime.

**Demo:** `examples/finance_report/` — patent §7.1 worked example. Mock fixture demonstrates two-iteration convergence on the canonical "trailing choice that leaves a role unfinished" failure mode.

## 1.4 STJP authoring loop — reverse (skills.md → Scribble)

The reverse pipeline implements **synthesis from per-role skill files** to a global protocol — the projection-inverse problem. Used when teams author per-agent skills first and want to reconstruct (or validate) the global type.

```
*_skills.md per role  →  skills_parser.parse_all_skills()
                      →  LLM (SkillsSynthesizer)
                      →  Scribble .scr
                      →  Scribble compiler (validation loop)
                      →  if valid: Skills Compiler round-trip
```

**Hard-won lessons (folded into the LLM system prompt):**

1. **Inconsistent external choice subjects** — common messages in ALL branches must be factored OUT to the top level after the choice block.
2. **Safety violation (causal ordering)** — if the chooser must send a trigger msg to role R so R can do work needed later, that trigger MUST be at the END of EVERY branch (not top level). Duplicate it in all branches even if identical.
3. **Deadlock from partial branch participation** — if role X appears in only SOME branches of a choice, X deadlocks in the branches where it's absent. Fix: move X's interactions to the top level (always happens after the choice), or notify X in every branch.

**Status:** PASS — 6/6 roles, 11/11 message labels match; Skills Compiler round-trip PASS. Test entry: `test_skills_synthesizer.py`. Output artefact: `protocols/SynthesizedFromSkills.scr`.

**Research finding:** the projection-inverse problem is genuinely non-unique. The synthesizer placed `AuditedRevenue` at top level while the original had it inside the high branch only. Both are valid Scribble — the LLM found a different-but-valid global type. This is interesting evidence that the LLM is doing real projection-inverse search, not template-matching.

## 1.5 Sub-session composition (lexical, cross-file)

> "Combine more than 1 session into one whole session and still be safe, faithful, and verified."

Practical: `Banking.scr` and `Inventory.scr` developed separately, composed into `ECommerce.scr`. Phase 1 ships the **lexical** composer; Phase 3 will add the projection-preserving **Hybrid MPST** composer (Gheri-Yoshida OOPSLA'23) that allows independent per-team verification.

**Composition operators — what's in:**

| Operator | Phase | Notes |
|---|---|---|
| Hierarchical / nested (`do SubProto`) | **1 — shipped** | Cross-file extension of Scribble's intra-file `aux global protocol` + `do` mechanism |
| Sequential (`P_1 ; P_2`) | 1 | Reduces to nested with a trivial parent |
| Delegation (`(SubProto@role)` payload) | 1 | Already supported by Scribble's grammar |
| Parallel (`P_1 ∥ P_2`) | 3 | Future — needs careful interleaving semantics |
| **Hybrid build-back** (Gheri-Yoshida OOPSLA'23) | **3** | The only path to true projection-preserving per-team independent verification |
| Gateway (Barbanera et al. JLAMP'21) | 3 | Different use case: stitching two finished protocols at a gateway pair |

**Phase 1 design:** `// @use BankingSession from "../banking/Banking.scr";` — a directive that lives **inside a Scribble comment** so Scribble's parser ignores it. The composer reads `@use`s, resolves transitively (DFS, cycle detection), splices sub-protocols' `aux global protocol` blocks plus their data decls into a single composed `.scr`, and validates via `scribblec.sh`. Scribble's existing `STypeInliner` handles role substitution.

**Three error classes (with tags):**

| Class | Triggered by | Caught by |
|---|---|---|
| `ResolutionError` | file not found, named protocol not in file, cycle in `@use` | composer (pre-Scribble) |
| `RoleMappingError` | `do SubProto(...)` arity mismatch with sub's `role` declaration | composer (pre-Scribble) |
| `CompositionError` | spliced whole rejected by Scribble (Unfinished roles, choice-subject violations, etc.) | Scribble; surfaced verbatim |

**What this proves (transitively):** if `parent.scr` plus its `@use`-resolved sub-protocols compose into a `composed.scr` that Scribble accepts, then by Honda-Yoshida-Carbone POPL'08 the composite session is communication-safe, deadlock-free, and branch-complete. By construction (textual splicing + Scribble's substitution), each sub-protocol's interaction sequence appears verbatim under the parent's role mapping — the composite is faithful. Same guarantee Scribble already gives for `aux/do` within a single file; Phase 1 extends it across files; metatheorem unchanged.

**What this does NOT prove (deferred to Phase 3):** projection-preserving composition. Phase 1 always re-projects the spliced whole — independent teams cannot ship pre-verified sub-protocol artefacts and have those artefacts be guaranteed to compose. The Hybrid-MPST work in Phase 3 closes this.

**Demo:** `examples/composition_demo/` — Banking + Inventory → ECommerce; happy path + three error classes.

## 1.6 Real-world audit

`examples/agentic_labelling/LabellingPipelineGated.scr` — modelled the [Agentic_Labelling](https://github.com/ginaecho/Agentic_Labelling) 5-stage pipeline with quality-gate feedback loops. Scribble rejected with `Unfinished roles: {CL=46, FS=35, PN=57}` — after the happy-path `approve()`, three sub-agents are left in non-final states. See `examples/agentic_labelling/AUDIT.md` for findings and recommendations.

This is the load-bearing demonstration that the framework catches real bugs in real pipelines, not just toy examples.

---

# Phase 2 — Static verification: refinement discharge, subtyping, capability cross-check

**Status: in progress (subtyping shipped; static refinement discharge in flight).**
**Goal: take refinements and protocol evolution from runtime-only to compile-time-proven where decidable; preserve runtime fallback for the undecidable cases.**
**Theorems used: Gay & Hole 2005 (synchronous subtyping); Chen, Dezani, Padovani, Yoshida LMCS'17 (preciseness); Zhou, Ferreira, Hu, Neykova, Yoshida OOPSLA'20 (statically verified refinements); Vassor & Yoshida ECOOP'24 (specification-agnostic refinements).**

## 2.1 Static refinement discharge via Z3

Phase 1's runtime refinements are real but limited: a predicate that is unsatisfiable for all inputs (e.g., `x > 1 and x < 0`) won't be flagged at compile time. Phase 2 adds Z3 to the loop.

**Design:** `stjp/smt.py` translates the safe Python predicate fragment into SMT-LIB:

- Supported: arithmetic (`+ - * / // % **`), comparison (`< <= > >= == !=`), boolean (`and or not`), `len`, `abs`, `min`, `max`, `startswith`, `endswith`, `contains` (over QF-UFLIA + bit-vectors).
- Unsupported (returns `None`, falls back to runtime): regex via `matches(...)`, lambdas, attribute access, comprehensions, nonlinear arithmetic with division.

**Hard limit (Das & Pfenning, CONCUR 2020):** type equality with arithmetic refinements is **undecidable**. Full static checking will always be incomplete; runtime fallback is unavoidable. This is honest scope, not a flaw.

**API:**
- `discharge(predicate)` — checks satisfiability; rejects `x > 1 and x < 0` as unsatisfiable.
- `implies(p_strong, p_weak)` — decides via Z3 unsat-of-negation; returns a concrete witness when implication fails. The primitive Phase 2.3 (refinement-aware subtyping) builds on.

## 2.2 Synchronous structural subtyping

Validates protocol evolution: "is `P'` a safe drop-in replacement for `P`?" The exact decision procedure for the user's hot-swap claim.

**Foundational rule** (Gay-Hole 2005): **input is covariant** (P' offers superset of inputs), **output is contravariant** (P' offers subset of outputs), checked coinductively via bisimulation. **Chen-Dezani-Padovani-Yoshida (LMCS 2017)** prove this rule is **precise** — `P' ≤ P` iff replacing `P` with `P'` is safe in any well-typed context.

**Decidability:**
- Synchronous MPST: **decidable in polynomial time** via coinductive bisimulation.
- Asynchronous MPST: **undecidable in general** (Lange & Yoshida FoSSaCS'19; Bravetti-Carbone-Zavattaro 2017). Bounded-buffer fragments are decidable (Bocchi-Lange-Yoshida) — Phase 3 target.

**What ships:** `stjp/subtype.py` — synchronous Gay-Hole bisimulation over Scribble's projected EFSMs; `stjp/cli.py subtype` subcommand; `examples/subtype_demo/V1_baseline.scr`, `V2_equivalent.scr`, `V2_unsafe_extra_send.scr`, `V2_unsafe_fewer_recv.scr` covering structural pass/fail cases.

**Honest scope.** Pure structural subtyping in MPST is genuinely tight. Most "obvious" protocol changes are not global subtypes:

- Dropping a branch: makes one role's send-set smaller (contravariant ✓) but the symmetric receiver's recv-set smaller too (covariant ✗) — fails.
- Adding a branch: symmetric failure.
- Adding work after end / removing work before end: state-kind mismatch.
- Renaming labels: failure.

What **does** work as a structural subtype: the trivial case (`P' ≡ P`); coordinated dual changes that don't asymmetrically modify any role's local type (rare in practice).

**This is not a flaw of the algorithm — it is a property of MPST.** The literature is honest about this: practical protocol evolution typically uses **refinement subtyping** (the SAME structural protocol with payload predicates added on the substituting side), not structural subtyping. That is the next item.

## 2.3 Refinement-aware subtyping

Combines 2.1 and 2.2. Real evolution scenarios are: "deposits are now bounded above by $10k" (`x <= 10000` added), "amounts are non-negative" (`x >= 0` added). These are subtype-safe because every payload satisfying the refined type is also valid under the original.

**`stjp/subtype.py` extended.** At every shared transition, looks up `.refn` for both protocols and applies the four-case rule:

| P' has refinement | P has refinement | Verdict |
|---|---|---|
| no | no | structural-only |
| yes | no | strict subtype (P' more constrained) |
| no | yes | FAIL — P' allows broader payloads |
| yes | yes | check `P'.requires ⇒ P.requires` via Z3 (`stjp/smt.py:implies`) |

**`compare(a, b)`** — runs both directions; reports **equivalent** / **strict subtype** / **strict supertype** / **incomparable**. CLI `--compare` flag emits Z3 witnesses on failure tagged `[structural]` vs `[refinement]`.

**Demo additions:**
- `V3_refined.scr` + `V3_refined.refn` — same shape as V1 with payload predicates added; demonstrates `P' ≤ P` passes via refinement strengthening, `P ≤ P'` fails because P' is broader.
- `Counter_baseline.scr/.refn` (`x >= 0`) and `Counter_stricter.scr/.refn` (`x > 100`) — clean integer-payload pair that produces a Z3-extracted witness `x = 4` on the failing direction.

## 2.4 Conditional / asserted MPST (full integration)

Phase 1's `.refn` is the runtime side of Bocchi 2010 *asserted MPST*. Phase 2 promotes it to a first-class part of the type-check artefact:

- **Assertion well-typedness:** every refinement variable is in scope at its anchor (the message it refines). Implemented as a small AI_ST_verf component that consumes Scribble's projected EFSMs and verifies refinement scope.
- **Cross-message variable bindings:** predicates can reference values from earlier messages in the session. `[B -> C : balance] require: x >= prev.deposit_total` becomes expressible. Requires session-state threading in the SMT bridge.
- **Multi-payload messages:** `apply(String, int)` exposes `args[0]`, `args[1]` rather than only `x`. Scribble itself permits multi-payload; Phase 2 makes refinements track them.

**Research basis pulled in:** Zhou et al. OOPSLA'20 *Statically Verified Refinements for Multiparty Protocols* — the direct prior art that extends Scribble with refinement-typed payloads, projects to F\* APIs, discharges via Z3. We follow their decomposition rather than reinventing it.

## 2.5 Capability projection ↔ frontmatter cross-check

Each role's projected outgoing-message labels imply a minimum capability set. Example: a role whose outgoing labels include `apply(Patch)` needs `Edit` + `Write` capability. Compare against declared `tools` / `allowed-tools` frontmatter in `SKILL.md` and subagent metadata; flag over- and under-provisioned agents.

**Cost claim.** Two effects. (i) Security: agents cannot invoke tools they don't need. (ii) Cost: over-provisioned `allowed-tools` lists tend to be invoked speculatively ("let me also check the database") — projection rejects that as off-protocol. Empirically, capability-tightening is one of the highest-ROI cost interventions in production agent systems.

**Deliverable:** `verf lint` output that ties projection to capability declarations.

## 2.6 Hard-schema linter

Pure structural checks across the agent harness ecosystem — no MPST yet, but shippable on its own as a useful product:

- Parse all hard-schema artifacts (Claude Code skills, subagents, hooks; MCP; CrewAI YAML; Cursor `.mdc`; OpenHands microagents).
- Cross-reference: declared tools ⊇ tools mentioned in body; subagent assertions don't violate the harness's published semantics; MCP server references resolve.
- Output: a SARIF-compatible report so it plugs into CI.

Per-harness latch points are catalogued in `RESEARCH.md` Part II (Agent Harness Landscape). The Anthropic **Agent Skills Open Standard** (Dec 2025) is the most concretely machine-readable artifact today.

---

# Phase 3 — Advanced research: composition, async, dynamic, NL frontend, harness backends

**Status: research roadmap.**
**Goal: close the academic-grade composition story; wire AI_ST_verf into real agent harnesses; tackle the open NL→spec extraction problem with bidirectional round-tripping.**
**Theorems consulted: Gheri & Yoshida OOPSLA'23 (Hybrid MPST); Bravetti-Carbone-Zavattaro 2017 + Lange-Yoshida FoSSaCS'19 (async undecidability); Deniélou & Yoshida ESOP'11 / ICALP'12 (dynamic multirole); Fu POPL'25 (probabilistic refinement).**

## 3.1 Hybrid MPST projection-preserving composition

Phase 1's lexical composer always re-projects the spliced whole. Independent teams cannot ship pre-verified sub-protocol artefacts and have those artefacts be *guaranteed* to compose.

**Phase 3 implements** the Gheri-Yoshida composition algorithm:

- A `HybridType` ADT extending the global-type AST with external prefixes `p!q;ℓ` and `p?q;ℓ`.
- The localiser `loc(H)` and generalised projection `H↾E` onto a set of roles.
- The compatibility condition C: `H†↾E_i = loc(H_i)` for each sub-protocol `H_i`.
- The build-back recursion `B(H†)([H_1, …, H_N])` (Definitions 4.1, 4.6 of the OOPSLA'23 paper).
- Theorem 4.7 (compositionality) and Theorem 4.9 (projection composes over set inclusion).

**Why this matters:** verification becomes pay-once-per-skill, not pay-per-deployment. The compositional reasoning collapses what would be quadratic recheck cost into linear — and crucially, lets multi-team protocol authoring scale.

**Forward compatibility:** Phase 1's `do SubProto(parent_role_args)` lines are exactly the call-site encodings of the future hybrid-type external prefixes. The data structures stay compatible.

## 3.2 Async subtyping (bounded-buffer fragment)

Asynchronous MPST subtyping is **undecidable in general** (Lange-Yoshida FoSSaCS'19; Bravetti-Carbone-Zavattaro 2017). Bocchi-Lange-Yoshida give a **decidable bounded-buffer fragment** that is sound-but-incomplete.

**Phase 3 ships:** restricted decidable fragment checker that handles the cases practitioners actually hit (channel reorderings within bounded queue depth) and explicitly documents the undecidability cliff. Not pretending to solve the impossible.

## 3.3 Dynamic-multirole MPST

Today Scribble requires every role to participate from the start. Real agent systems spawn sub-agents on demand. The `examples/agent_workflow/AgentWorkflowFixed.scr` had to add wasteful `skip()` and `abort()` filler messages so that role E (Executor) "participated" in branches where it had no real work to do.

**Phase 3 implements** the dynamic-multirole extension (Deniélou & Yoshida, ESOP'11, ICALP'12) — roles can join via a `spawn` operator and leave via accepting termination. This eliminates filler messages and matches LLM orchestrators where sub-agents are truly spawned on demand.

**Deliverable:** `spawn role E` operator; projection accommodates absent-then-present roles.

## 3.4 Probabilistic refinement

For protocols where the choice subject is the LLM (`choice at LLM`), branches are inherently probabilistic. **Probabilistic refinement session types** (Fu, POPL'25) let us annotate `choice [p≥0.95] at LLM { ok(...) } or { retry(...) }` and prove safety with confidence bounds.

**Deliverable:** experimental `choice [p=…] at <dyn>` syntax; statistical monitor that aggregates over repeated samples (consistent with Cho et al. ICSME'25's finding that single-trace assertions break under LLM nondeterminism).

## 3.5 Bounded recursion + cost annotations

**Bounded recursion.** Scribble's `rec X { ... continue X; }` is unbounded. Agent reflection loops want explicit upper bounds: `rec X[k≤5] { ... }`. Static analysis enforces that the path through the body decreases a measure or hits the bound; runtime monitor counts iterations and aborts on overflow.

**Cost annotations.** The differentiating story for the efficiency pitch: `apply(Patch) [tokens=500, latency<2s, cost=$0.01] from O to E`. Static analysis sums per-role and per-branch costs, computing worst-case and expected-case bounds for whole-session resource usage. Delivers the "MPST as efficiency proof" pitch concretely.

**Deliverable:** `rec X[k≤N]` syntax + bounded-iteration monitor; `verf cost <protocol.scr>` reports bounds per role and overall.

## 3.6 Hyperproperty layer (HyperLTL)

For "did the agent's reasoning entail its action" — a 2-safety relation between CoT and tool call — single-trace logic is insufficient.

HyperLTL over multiple Scribble local types (Detecting Safety Violations Across Many Agent Traces, arXiv 2604.11806; CSL'26 *Reasoning About Quality in Hyperproperties*) — checks "did role A's reasoning entail role A's action" as a 2-safety relation, "the data agent role never reveals to client what only the privileged role saw" as session-typed information-flow, etc.

Out of scope until the core toolchain is polished; on the roadmap as the final research extension.

## 3.7 LLM-assisted protocol extraction (annotate-then-convert)

The hard problem.

- **Best LLMs hit ~52% accuracy** on full-document spec extraction (May 2026 surveys). The mitigation is **annotate-then-convert** (split sentence-level intent tagging from formalisation) plus **bidirectional round-tripping** with human confirmation.
- **Stage 1:** an LLM tags sentences with intent labels (`PRECONDITION`, `OBLIGATION`, `PROHIBITION`, `OUTCOME`, `MESSAGE`, `HANDOFF`).
- **Stage 2:** a deterministic converter lifts tags into the IR triple.
- **Stage 3:** the IR is rendered back to NL and the human is shown the round-trip diff. Specs whose round-trip diverges materially are rejected.

This pattern is converging in 2025–2026 NL→spec work (Req2LTL, AutoReSpec, VERGE) precisely because raw extraction is too unreliable to ship unattended.

**Deliverable:** `verf extract <repo>` proposes a Scribble protocol from prose, with round-trip confirmation flow. **Refuse to ship below a calibration threshold** measured against a hand-labeled corpus of ~30 curated agent specs.

## 3.8 OTel GenAI trace adapter

Scribble's runtime monitors today consume Java/Python channels. Agent systems emit OpenTelemetry GenAI semantic-convention spans (`gen_ai.tool.call`, `gen_ai.agent.handoff`, etc.). Build an adapter that maps the projected EFSM's transition labels to OTel span types and runs the monitor over a span stream.

**Why this is load-bearing:** OTel GenAI is the converging cross-framework standard (experimental as of March 2026, but Datadog ships it natively in OTel 1.37). Wiring through it makes AI_ST_verf framework-portable.

**Deliverable:** `verf monitor --role E --trace otel.jsonl` reports conformance.

## 3.9 Harness-specific monitor codegen

Today Scribble emits Java endpoint APIs. Phase 3 adds codegen for the harnesses AI_ST_verf cares about, each with the same EFSM but a harness-specific shim:

- **Claude Code subagent wrapper** (intercepts `tools` calls)
- **OpenAI Agents SDK middleware** (wraps `Runner` events)
- **LangGraph node decorator**
- **MCP gateway** (server-side or client-side)

**Deliverable:** `scribblec.sh -api Proto Role --target claude-code-subagent`.

## 3.10 LLM-as-`dyn` role + gradual session typing

The LLM is fundamentally untyped — it can emit anything. **Gradual Session Types** (Igarashi/Thiemann/Tsuda/Vasconcelos/Wadler ICFP'17) tells you precisely how to build the casts/monitors at the boundary: a `role <dyn>` keyword (or annotation) marks a role as gradual; the projection still produces an FSM; the runtime monitor inserts grammar/payload casts at every send/receive across the dyn boundary.

**Deliverable:** `role <dyn> LLM` syntax; projection generates cast-inserting monitor.

This is the most important single result for the project — the typed/untyped boundary is exactly where AI_ST_verf has to be sound, and gradual session typing gives the recipe.

## 3.11 NL round-trip renderer

Render a Scribble protocol back to natural-language English so the human can confirm the extracted spec matches their intent. Critical for 3.7 — without round-trip confirmation, the markdown→Scribble extractor is too unreliable to ship.

**Deliverable:** `verf explain <protocol.scr>` produces NL paraphrase per role and overall.

---

## Phase summary table

| Capability | Phase | Status | Theorem / paper |
|---|---|---|---|
| Scribble integration & monitor pipeline | 1 | shipped | Bocchi-Chen-Demangeon-Honda-Yoshida FORTE'13 |
| Runtime refinement contracts | 1 | shipped | Bocchi-Honda-Tuosto-Yoshida CONCUR'10 |
| STJP Revisor (forward NL → Scribble) | 1 | shipped (mock + real) | (engineering) |
| Skills synthesizer (reverse skills.md → Scribble) | 1 | shipped, tested | (engineering, projection-inverse search) |
| Sub-session composition (lexical, cross-file) | 1 | shipped | Demangeon-Honda CONCUR'12 + Honda-Yoshida-Carbone POPL'08 |
| Static refinement discharge (Z3) | 2 | in flight | Zhou-Ferreira-Hu-Neykova-Yoshida OOPSLA'20 |
| Synchronous structural subtyping | 2 | shipped | Gay-Hole 2005 + Chen et al. LMCS'17 (preciseness) |
| Refinement-aware subtyping | 2 | shipped | Combines 2.1+2.2 |
| Conditional MPST (assertions, cross-message bindings, multi-payload) | 2 | partial | Zhou et al. OOPSLA'20 |
| Capability ↔ frontmatter cross-check | 2 | designed | (engineering) |
| Hard-schema linter | 2 | designed | (engineering) |
| Hybrid MPST projection-preserving composition | 3 | research | Gheri-Yoshida OOPSLA'23 |
| Async subtyping (bounded-buffer fragment) | 3 | research | Bocchi-Lange-Yoshida (decidable fragment) |
| Dynamic-multirole MPST | 3 | research | Deniélou-Yoshida ESOP'11/ICALP'12 |
| Probabilistic refinement | 3 | research | Fu POPL'25 |
| Bounded recursion + cost annotations | 3 | designed | (engineering, novel for agents) |
| Hyperproperty layer (HyperLTL) | 3 | research | CSL'26 + arXiv 2604.11806 |
| NL → Scribble extraction (annotate-then-convert) | 3 | research | Req2LTL, AutoReSpec, VERGE 2025–2026 |
| OTel GenAI trace adapter | 3 | designed | OTel 1.37 GenAI semconv |
| Harness-specific monitor codegen | 3 | designed | (engineering) |
| LLM-as-`dyn` + gradual session typing | 3 | research | Igarashi-Thiemann-Tsuda-Vasconcelos-Wadler ICFP'17 |
| NL round-trip renderer | 3 | research | (engineering) |

---

## Honest scope statement

For **protocol shape, message structure, capability conformance, refinement predicates, and bounded temporal properties**, a session-typed verifier with SMT and runtime monitors gives a real "1+2=3" guarantee — these are mathematically provable.

For **intent and value alignment**, expect calibrated probabilistic verification, not proof. Calibrated LLM-as-judge against a golden set with ≥80% agreement, plus metamorphic relations, is the realistic ceiling.

The product surface must distinguish "MPST-proved efficiency property" from "calibrated content-quality estimate." The first is hard guarantee; the second is bounded-confidence. **That distinction is the differentiator vs. every existing eval framework. Conflating the two is the failure mode of every existing eval framework; not conflating them is what makes this project different.**

---

## Risk register

- **NL extraction unreliability (~52% best-case)** → round-trip + human confirmation mandatory; never ship "auto-extracted" specs without human acceptance.
- **LLM nondeterminism breaks single-trace assertions** → aggregate over repeated samples (Cho et al. ICSME'25 finding); report monitor verdicts as confidence-bounded for properties that intrinsically vary across runs.
- **Markdown semantics drift between Claude Code releases** → version-pin the harness adapter; treat skill/subagent schemas as "vendor specs you track." Anthropic's Agent Skills Open Standard (Dec 2025) reduces this risk on Claude Code; other harnesses are more volatile.
- **Protocol explosion** in real agent systems with many concurrent sessions → start with single-session per skill, add session composition (Hybrid MPST) at Phase 3.1.
- **Static rejection of legitimate behaviour** (false positives) — recursion bounds and projection are conservative. Mitigation: provide an `@unsafe` escape hatch that disables structural checks for a named region but keeps refinements and capability checks.
- **Adoption friction**: users won't author Scribble protocols. Mitigation: 3.7 extraction; aggressive defaults from frontmatter; never make MPST authoring the entry path.
- **Refinement undecidability cliff (Das-Pfenning CONCUR'20)** → runtime fallback for unsupported predicates is unavoidable; document explicitly.
- **Async subtyping undecidability (Lange-Yoshida FoSSaCS'19)** → ship the bounded-buffer fragment with the cliff explicitly documented.

---

## Strategic decisions (load-bearing)

1. **Layer on top of Scribble; do not fork.** Refinements live in sidecar `.refn` files; sub-sessions use `// @use` comments the parser ignores; subtyping is a new component consuming Scribble's projected EFSMs. Grammar forks burden maintenance for marginal benefit.
2. **Start with the synchronous decidable fragment** of subtyping. Polynomial-time, sound and complete, well-understood mathematically. Async fragments are Phase 3.
3. **Runtime fallback for unsupported predicates** is honest scope, not weakness. Bocchi 2010 + Das-Pfenning 2020 prove full static checking is undecidable.
4. **Pay-once-per-skill verification** is the long-game architectural goal. The Phase 3.1 Hybrid-MPST work is what enables it.
5. **OTel GenAI as the runtime substrate** — converging cross-framework standard, makes AI_ST_verf framework-portable.
6. **Distinguish provable from calibrated.** UI surfaces the distinction; "PROVED" never leaks into calibrated-only territory.

---

## References

See `RESEARCH.md` for full bibliography (~70 citations across MPST foundations, MPST extensions, choreographies, NL→spec extraction, agent verification 2024–2026, harness landscape, calibration). The load-bearing citations for this roadmap, grouped by phase:

**Phase 1:**
- Honda, Yoshida, Carbone. *Multiparty Asynchronous Session Types*. POPL'08; JACM'16.
- Scalas, Yoshida. *Less is More: Multiparty Session Types Revisited*. POPL'19.
- Bocchi, Chen, Demangeon, Honda, Yoshida. *Monitoring Networks through MPST*. FORTE'13; TCS'17.
- Bocchi, Honda, Tuosto, Yoshida. *A Theory of Design-by-Contract for Distributed Multiparty Interactions*. CONCUR'10.
- Demangeon, Honda. *Nested Protocols in Session Types*. CONCUR'12.

**Phase 2:**
- Gay, Hole. *Subtyping for Session Types in the Pi-Calculus*. Acta Informatica 2005.
- Chen, Dezani-Ciancaglini, Padovani, Yoshida. *On the Preciseness of Subtyping in Session Types*. LMCS'17.
- Zhou, Ferreira, Hu, Neykova, Yoshida. *Statically Verified Refinements for Multiparty Protocols*. OOPSLA'20.
- Vassor, Yoshida. *Refinements for Multiparty Message-Passing Protocols*. ECOOP'24.
- Das, Pfenning. *Session Types with Arithmetic Refinements*. CONCUR'20.

**Phase 3:**
- Gheri, Yoshida. *Hybrid Multiparty Session Types*. OOPSLA'23.
- Deniélou, Yoshida. *Dynamic Multirole Session Types*. ESOP'11; ICALP'12.
- Igarashi, Thiemann, Tsuda, Vasconcelos, Wadler. *Gradual Session Types*. ICFP'17.
- Fu. *Probabilistic Refinement Session Types*. POPL'25.
- Ghilezan, Pantović, Prokić, Scalas, Yoshida. *Precise Subtyping for Asynchronous Multiparty Sessions*. POPL'21 / TOPLAS'23.
- Bravetti, Carbone, Zavattaro. *Undecidability of Asynchronous Session Subtyping*. I&C 2017.
- Lange, Yoshida. *On the Undecidability of Asynchronous Session Subtyping*. FoSSaCS'19.
- Wang, Poskitt, Sun. *AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents*. ICSE'26.
