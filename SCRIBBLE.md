# Scribble: The Compiler Backbone of AI_verf

Scribble is the multiparty session type compiler that AI_verf builds on top of. This document covers why we picked it, what we installed, what we proved by running it, and the concrete extensions AI_verf needs to ship on top.

Drafted 2026-05-02.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Why Scribble is the moat](#1-why-scribble-is-the-moat)
- [2. What we installed](#2-what-we-installed)
  - [Repository](#repository)
  - [Build](#build)
  - [Smoke tests run](#smoke-tests-run)
  - [Cheat sheet (CLI)](#cheat-sheet-cli)
- [3. What Scribble caught immediately](#3-what-scribble-caught-immediately)
- [4. Improvement roadmap — Scribble extensions for agent verification](#4-improvement-roadmap--scribble-extensions-for-agent-verification)
- [5. Integration architecture](#5-integration-architecture)
- [6. Where the Scribble source lives](#6-where-the-scribble-source-lives)
- [7. Decision: fork or extend?](#7-decision-fork-or-extend)
- [8. References](#8-references)
<!-- MENU:END -->

## 1. Why Scribble is the moat

Multiparty session types are a 20-year body of theory; Scribble is the 20-year body of *engineering* that makes them shippable. It has:

- A working parser for the Scribble protocol DSL (`.scr` files).
- A well-formedness checker that catches deadlock-precursors and protocol-incoherence statically.
- An endpoint projection algorithm (global type → per-role local type).
- An EFSM (endpoint finite-state machine) emitter — the projected automaton each role's runtime monitor will interpret.
- A code generator (Java endpoint API today; Python, Go, F# in sister projects).
- A 20-year industrial track record: Ocean Observatories Initiative, Rumpsteak, JBoss, IDE integrations across 16+ host languages.
- Active research successor `nuScr` (OCaml) and modern theoretical implementation `mpstk` (Scala, "Less is More").

The competing approaches in agent verification — AgentSpec, Agent-C, LangGraph asserts, Guardrails, NeMo, LLM-as-judge — have nothing comparable. AgentSpec has a rule DSL (no projection); Agent-C has LTL→SMT (no protocol algebra); LangGraph has a graph builder (no theorem); Guardrails has validators (no global view). Reinventing Scribble's middle would burn the project for years with no payoff. Standing on it lets AI_verf hit a working prover in Phase 2.

---

## 2. What we installed

### Repository

- Cloned `github.com/scribble/scribble-java` to `vendor/scribble-java/`.
- Branch: master, depth 1. Java 17 + Maven wrapper (`mvnw`); no separate Maven install needed.

### Build

```bash
cd vendor/scribble-java
./mvnw -q -DskipTests clean install
```

Output distribution: `vendor/scribble-java/scribble-dist/target/scribble-dist-0.5.1-SNAPSHOT.zip`. Unzipped to `scribble-dist/` in the same target directory, exposing:

- `scribblec.sh` — the CLI driver
- `lib/` — the compiler jars

For convenience, the canonical command path is:

```
vendor/scribble-java/scribble-dist/target/scribble-dist/scribblec.sh
```

### Smoke tests run

| Test | Result |
|---|---|
| Build (`./mvnw -DskipTests clean install`) | Exit 0 |
| Well-formedness on `TwoBuyer.scr` (demo) | Silent (passed) |
| Projection of `TwoBuyer` onto role A | Local protocol emitted |
| EFSM of `TwoBuyer` role A | Graphviz dot emitted (3 states, 3 transitions) |
| Well-formedness on `examples/agent_workflow/AgentWorkflow.scr` | **Failed** — caught a real bug (see §3) |
| Well-formedness on `AgentWorkflowFixed.scr` | Silent (passed) |
| EFSM of fixed agent role E | 4-state automaton, 3 transitions — the runtime monitor |

### Cheat sheet (CLI)

```bash
SCR=vendor/scribble-java/scribble-dist/target/scribble-dist/scribblec.sh

# 1. Well-formedness check
$SCR Module.scr

# 2. Project onto a role (emits local type)
$SCR Module.scr -project ProtocolName RoleName

# 3. Emit endpoint FSM (Graphviz dot)
$SCR Module.scr -fsm ProtocolName RoleName

# 4. Generate Java endpoint API
$SCR -d output_dir Module.scr -api ProtocolName RoleName

# 5. Verbose / debug
$SCR -V Module.scr
```

---

## 3. What Scribble caught immediately

The agent demo `examples/agent_workflow/AgentWorkflow.scr` modelled an Orchestrator delegating to a Searcher, then looping through a Verifier with three branches (`ok` → invoke Executor; `retry` → re-verify; `giveup` → terminate).

Scribble rejected it on first run:

```
Safety violation(s) at session state 72:
  Trace=[O!S:query(String), S?O:query(String), S!O:candidates(String),
         O?S:candidates(String), O!V:verify(String), V?O:verify(String),
         V!O:giveup(), O?V:giveup()]
  Unfinished roles: {E=38}
```

Translation: when Verifier picks `giveup()`, **role E (Executor) is left in state 38 waiting for a message that will never arrive**. This is a textbook deadlock-precursor — and the exact failure mode hand-written agent systems silently hit in production: a sub-agent hangs forever, billing tokens or holding a session lock, with no signal to the orchestrator that anything is wrong.

The fix in `AgentWorkflowFixed.scr` adds `skip()` and `abort()` messages so E participates in every branch. Scribble's EFSM for the fixed E:

```
state Loop:
  O?apply(String) → state Apply
  O?skip()        → state Loop      (loopback)
  O?abort()       → state Terminate
state Apply:
  O!applied(String) → state Terminate
```

This automaton **is** the runtime monitor. Role E's wrapper accepts only these three labels in those states; anything else is a violation. No code AI_verf has to write — Scribble emits this directly.

The pedagogical point: forcing E into every branch is wasteful — real systems want to spawn E *only* on `ok`. That requires **dynamic-multirole MPST** (Deniélou & Yoshida, ESOP'11), which vanilla Scribble does not support. This is item #4 on the improvement roadmap.

---

## 4. Improvement roadmap — Scribble extensions for agent verification

The detailed extension list, with current status, theorems used, and deliverables, lives in `ROADMAP.md` as a Phase 1/2/3 epic. The natural attach points within Scribble's source tree are summarised in §6 below; refer to `ROADMAP.md` for the per-extension scope, decidability boundary, and references.

---

## 5. Integration architecture

```
┌─────────────────────────────────────────────────────────────┐
│  AI_verf frontend (NEW)                                     │
│  ─ markdown reader (SKILL.md, agents/*.md, AGENTS.md, ...)  │
│  ─ annotate-then-convert NL pipeline                        │
│  ─ round-trip renderer                                      │
│  ─ refinement / cost / dyn-role annotations on emit         │
│        emits .scr                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
            ┌──────────▼──────────┐
            │  Scribble (vendored)│   ← compiler middle
            │  ─ parser           │     (do NOT reinvent)
            │  ─ well-formedness  │
            │  ─ projection       │
            │  ─ EFSM emitter     │
            │  ─ Java codegen     │
            └──────────┬──────────┘
                       │
                emits per-role EFSM
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  AI_verf backend (NEW)                                      │
│  ─ Z3 refinement discharge (static + runtime)               │
│  ─ Cost analyzer (token / latency / $)                      │
│  ─ OTel GenAI trace adapter                                 │
│  ─ Harness-specific monitor codegen:                        │
│    • Claude Code subagent wrapper                           │
│    • OpenAI Agents SDK middleware                           │
│    • LangGraph node decorator                               │
│    • MCP gateway                                            │
│  ─ State+Assignee+Audit-Trail graph view (UI)               │
└─────────────────────────────────────────────────────────────┘
```

The frontend and backend are AI_verf's contribution. The middle is Scribble. This is the engineering bet.

---

## 6. Where the Scribble source lives

Within `vendor/scribble-java/`:

- `scribble-parser/` — `.scr` parser
- `scribble-ast/` — AST types
- `scribble-core/` — well-formedness, projection, EFSM construction
- `scribble-codegen/` — endpoint API code generation (Java)
- `scribble-runtime/` — Java runtime channels and monitors
- `scribble-cli/` — `scribblec` CLI
- `scribble-main/` — entry point binding
- `scribble-test/` — test harness
- `scribble-demos/scrib/` — sample protocols (TwoBuyer, ThreeBuyer, Smtp, Game, Nego, etc.) — useful as syntax references
- `scribble-dist/` — distribution packaging

Natural attach points within Scribble's source for the `ROADMAP.md` extensions:

- **NL frontend, round-trip renderer** (Phase 3.7, 3.11): a *new* AI_ST_verf module that reads markdown and writes `.scr`; no Scribble change needed.
- **OTel adapter, harness codegen** (Phase 3.8, 3.9): new modules consuming Scribble's projected EFSMs; either no Scribble change, or a small `--target` flag in `scribble-codegen/`.
- **Capability cross-check** (Phase 2.5): static lint that consumes projected EFSMs and frontmatter; no Scribble change.
- **Refinements (sidecar), sub-sessions (lexical `// @use`), subtyping** (Phase 1.2, 1.5, 2.2): all layer *on top* of Scribble; no grammar change. This is the strategic decision in §7 below.
- **Dynamic-multirole, cost annotations, probabilistic branches, bounded recursion, `<dyn>`** (Phase 3.3, 3.5, 3.4, 3.10): require grammar extensions in `scribble-parser/`, AST nodes in `scribble-ast/`, well-formedness rules in `scribble-core/`. Evaluate fork-vs-`nuScr`-vs-layer per §7.

---

## 7. Decision: fork or extend?

**Decision (current):** layer on top of Scribble for everything where the API surface is sufficient — refinements (sidecar `.refn`), sub-sessions (lexical `// @use` in comments), subtyping (separate component over projected EFSMs), capability cross-check, OTel adapter, harness codegen, NL frontend, round-trip renderer.

**For grammar-level extensions** (`<dyn>`, dynamic-multirole, cost, probabilistic, bounded recursion), the options are:

- **Option A — fork `scribble-java`** with grammar extensions, rebase quarterly. Worst: burdens maintenance for marginal benefit.
- **Option B — switch the compiler middle to `nuScr` (OCaml)** or `mpstk` (Scala) and contribute extensions upstream. `nuScr` is research-active with cleaner extension points; `mpstk` already implements the modern "Less is More" theory.
- **Option C — keep layering** by encoding everything in companion files (`.refn`, `.cost`, `.dyn`) read alongside `.scr`, discharged against the projected EFSM after Scribble has done its work.

The current plan starts with **Option C** for the layered extensions (Phase 1+2 ship this way) and revisits **Option B** (`nuScr` migration) once the design has stabilised in real use.

---

## 8. References

- Scribble project page: http://www.scribble.org/
- `scribble-java` (this install): https://github.com/scribble/scribble-java
- `nuScr` (OCaml successor): https://github.com/nuscr/nuscr
- `mpstk` ("Less is More" Scala impl.): https://github.com/alcestes/mpstk
- Honda, Yoshida, Carbone. *Multiparty Asynchronous Session Types*. POPL'08; JACM'16.
- Scalas, Yoshida. *Less is More: Multiparty Session Types Revisited*. POPL'19.
- Igarashi, Thiemann, Tsuda, Vasconcelos, Wadler. *Gradual Session Types*. ICFP'17.
- Bocchi, Chen, Demangeon, Honda, Yoshida. *Monitoring Networks through MPST*. FORTE'13.
- Bocchi et al. *Refinements for Multiparty Message-Passing Protocols*. ECOOP'24.
- Deniélou, Yoshida. *Dynamic Multirole Session Types*. ESOP'11.
- Fu. *Probabilistic Refinement Session Types*. POPL'25.

Full bibliography in `RESEARCH.md`.
