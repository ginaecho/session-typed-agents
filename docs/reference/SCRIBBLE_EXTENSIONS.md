# How Scribble Is Extended in AI_ST_verf

How the STJP toolchain adds **conditional (refinement) contracts**, **sub-protocols / children protocols (composition)**, and **higher-order session passing** on top of Scribble — and, just as importantly, what it does *not* change.

Companion docs: `SCRIBBLE.md` (why Scribble, what was installed, the fork-vs-extend decision), `MPST_STATIC.md` (the MPST semantics + runtime monitor), `ROADMAP.md` (phase plan), `GAP_CLOSED.md` (the refinement call-site closure). Drafted 2026-05-20.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [0. TL;DR — Scribble is *not* forked](#0-tldr--scribble-is-not-forked)
- [1. The stock Scribble surface the layers build on](#1-the-stock-scribble-surface-the-layers-build-on)
- [2. Conditional — refinement / asserted MPST (`.refn` sidecar)](#2-conditional--refinement--asserted-mpst-refn-sidecar)
  - [What it adds](#what-it-adds)
  - [How it is layered — the `.refn` file](#how-it-is-layered--the-refn-file)
  - [The predicate language (sandboxed)](#the-predicate-language-sandboxed)
  - [Where the check actually runs — the call site](#where-the-check-actually-runs--the-call-site)
  - [Status](#status)
- [3. Sub-protocols / children protocols — composition](#3-sub-protocols--children-protocols--composition)
  - [3a. Native: `aux global protocol` + `do` (within one file)](#3a-native-aux-global-protocol--do-within-one-file)
  - [3b. Layered: cross-file `// @use` composition (`composer.py`)](#3b-layered-cross-file--use-composition-composerpy)
  - [What composition proves — and what it does not](#what-composition-proves--and-what-it-does-not)
  - [Status](#status-1)
- [4. Higher-order — session delegation](#4-higher-order--session-delegation)
- [5. Full extension matrix — implemented vs. roadmap](#5-full-extension-matrix--implemented-vs-roadmap)
- [6. Why a grammar fork is still off the table](#6-why-a-grammar-fork-is-still-off-the-table)
- [7. One-paragraph summary for a new contributor](#7-one-paragraph-summary-for-a-new-contributor)
<!-- MENU:END -->

## 0. TL;DR — Scribble is *not* forked

**The vendored compiler in `scribble-java/` is stock upstream, unmodified.** Verified: `git -C scribble-java diff HEAD` is empty; the tree sits on upstream `master` (`723660a81`). There is **no grammar change, no new AST node, no new well-formedness rule** inside Scribble.

Every capability this project adds is a **layer**: companion files that sit *beside* the `.scr`, or Python components that consume Scribble's *output* (projected local types / EFSMs). This is the load-bearing strategic decision from `SCRIBBLE.md` §7 and `ROADMAP.md` ("Strategic decisions" #1):

> **Layer on top of Scribble; do not fork.** Grammar forks burden maintenance for marginal benefit.

Why this works: Scribble already gives the hard 20-year-engineered middle — parser, well-formedness checker (deadlock-freedom, choice-consistency), endpoint projection, EFSM emission. The project's contribution is a markdown frontend and agent-harness backends *around* that middle. Forking the grammar would put the project on a permanent rebase treadmill for features that are expressible as side-cars.

```
        NL intent ──► architect.py ──► .scr  ───────────────┐
                                        │                   │
                              ┌─────────▼─────────┐         │ sidecar, same basename
                              │  Scribble (stock) │         │
                              │  validator.py     │   .refn ◄┘   (refinement_checker.py)
                              │  efsm_parser.py   │
                              └─────────┬─────────┘
                       projected EFSM   │   per role
                              ┌─────────▼──────────────────┐
                              │ agent_generator.py         │  ◄── splices refinement
                              │  → SKILL.md / agent.md     │      guards INTO the
                              │  → monitor (monitor.py)    │      projected skill
                              └────────────────────────────┘
```

The three things below — conditional, sub-protocol, higher-order — are each placed on this picture and explained.

---

## 1. The stock Scribble surface the layers build on

These are **native** Scribble features; STJP uses them as-is via `validator.py` / `efsm_parser.py`.

| Native feature | Scribble syntax | STJP entry point |
|---|---|---|
| Well-formedness check | `scribblec Module.scr` (silence = valid) | `validator.ScribbleValidator.validate_protocol()` |
| Branching / choice | `choice at Role { … } or { … }` | parsed by `protocol_parser.py` |
| Recursion | `rec X { … continue X; }` | parsed by `protocol_parser.py` |
| Endpoint projection | `scribblec Module.scr -project Proto Role` | `validator.ScribbleValidator.get_projection()` |
| EFSM emission | `scribblec Module.scr -fsm Proto Role` (Graphviz dot) | `efsm_parser.get_efsm_from_scribble()` → `EFSM` |
| Nested protocols | `aux global protocol P(…) { … }` + `do P(args);` | see §3 |
| Session delegation | a message payload typed as a protocol | see §4 |

`choice` is the native *conditional control flow* (which branch). What stock Scribble cannot express is a **conditional on payload values** — `deposit(int) where x > 0`. That is extension §2.

---

## 2. Conditional — refinement / asserted MPST (`.refn` sidecar)

### What it adds

Scribble payload types are **nominal only** (`int`, `String`, `Double`). Real agent protocols need **value-level conditions**:

- `HighRevenue(Double) where x > 50000.0`
- `open(String) where matches(r"^[A-Z]{2}-\d{6}$", x)`
- `apply(Patch) where startswith(path, "/safe/")`

This is *asserted MPST* / *refinement types*: a logical predicate attached to a message payload. In the research vocabulary `ROADMAP.md` §2.4 calls it "Conditional / asserted MPST."

### How it is layered — the `.refn` file

Refinements live in a **sidecar file with the same basename** as the protocol: `P1_v2.scr` → `P1_v2.refn`. Scribble never sees it; `refinement_checker.load_refinements_for_protocol()` auto-discovers the sibling.

Format (`refinement_checker.py` parses it; one block per message):

```ini
# v1.refn   (protocols renamed 2026-05-29; formerly P1_v2.refn)
[Fetcher -> TaxSpecialist : HighRevenue]
type: float
require: x > 50000.0

[TaxVerifier -> RevenueAnalyst : RevenueAuditApproval]
type: str
require: len(x) > 0
```

A block is keyed by `(sender, receiver, label)` — exactly the coordinates of one Scribble message. `type:` drives payload coercion; each `require:` line is a predicate over the single bound variable `x`.

### The predicate language (sandboxed)

`refinement_checker.py` evaluates predicates as a **restricted Python expression fragment**, not arbitrary code:

- Allowed: arithmetic (`+ - * / // % **`), comparison, boolean (`and/or/not`), the conditional expression `a if c else b`.
- Allowed helpers: `len abs min max int float str bool` and `matches startswith endswith contains`.
- Allowed string methods on `x`: `lower upper strip lstrip rstrip startswith endswith replace`.
- An AST validator (`_validate_ast`) rejects everything else — no imports, no arbitrary attribute access, no lambdas, no dunder games.

`Refinement.check(payload_str)` coerces the payload to the declared type, then evaluates every predicate; returns `(ok, error)`.

### Where the check actually runs — the call site

The important part (closed in `GAP_CLOSED.md`, 2026-05-13): the refinement is **not** only checked post-hoc on a trace. `agent_generator.py` **compiles each predicate into the projected agent**:

- The per-role Python stub gets a `send_<peer>_<label>(...)` method whose body contains the compiled predicate as literal Python; a violation raises `RefinementViolation` *before* the message leaves.
- A `_REFINEMENT_GUARDS` dispatch table means even a direct `.act()` call cannot bypass the guard.
- The generated `SKILL.md` / agent markdown gets a `## Refinement Invariants (HARD — enforced at call site)` section plus per-action annotations, so the LLM sees the constraint too.

So "conditional" is enforced at three points: the LLM is *told* the predicate, the generated tool *guards* it at the send site, and the monitor *re-checks* it on the observed trace.

### Status

| Layer | Status | File |
|---|---|---|
| `.refn` parse + runtime predicate eval | **shipped** (Phase 1.2) | `refinement_checker.py` |
| Predicate compiled into projected skill / call-site guard | **shipped** (Phase 1, GAP_CLOSED) | `agent_generator.py` |
| Static SMT discharge via Z3 (catch unsatisfiable predicates at compile time) | **roadmap only — not implemented.** `ROADMAP.md` §2.1 describes `stjp/smt.py`; that file does not exist in `stjp_core/`. | — |

**Research basis:** Bocchi, Honda, Tuosto, Yoshida — *Design-by-Contract for Distributed Multiparty Interactions* (CONCUR'10); Zhou et al. — *Statically Verified Refinements for Multiparty Protocols* (OOPSLA'20); Vassor & Yoshida — *Refinements for Multiparty Message-Passing Protocols* (ECOOP'24, legitimises the hybrid static+runtime split); Das & Pfenning (CONCUR'20, why full static checking is undecidable → runtime fallback is honest scope, not a flaw).

---

## 3. Sub-protocols / children protocols — composition

"Combine more than one session into one whole session and still be safe, faithful, and verified." There are **two mechanisms**, one native and one layered.

### 3a. Native: `aux global protocol` + `do` (within one file)

Stock Scribble already supports nested protocols. An `aux global protocol` is a reusable child; a parent invokes it with `do`, passing a role mapping:

```scribble
aux global protocol BankingSession(role C, role B) {
    open(String)  from C to B;
    deposit(int)  from C to B;
    confirm(int)  from B to C;
    close()       from C to B;
}

global protocol FinancePipeline(role Client, role Bank, role Auditor) {
    do BankingSession(Client, Bank);   // C↦Client, B↦Bank
    do AuditSession(Client, Auditor);
    report(String) from Auditor to Client;
}
```

Scribble's `STypeInliner` performs the role substitution at projection time. STJP uses this as-is — no layer. The catch: the child must live in the **same `.scr` file** as the parent.

### 3b. Layered: cross-file `// @use` composition (`composer.py`)

Real teams develop `Banking.scr` and `Audit.scr` **separately** and want to compose them into `FinancePipeline.scr` without copy-paste. STJP adds this with a directive that lives **inside a Scribble comment**, so the stock parser ignores it:

```scribble
// FinancePipeline.scr
module pipeline.FinancePipeline;

// @use BankingSession from "../banking/Banking.scr";
// @use AuditSession  from "../audit/Audit.scr";

global protocol FinancePipeline(role Client, role Bank, role Auditor) {
    do BankingSession(Client, Bank);
    do AuditSession(Client, Auditor);
    report(String) from Auditor to Client;
}
```

`composer.py` does the work (`compose_and_validate()`):

1. **Parse** the parent `.scr`: module name, `data` decls, `// @use` directives, `aux`/`global` protocol blocks (brace-matched).
2. **Resolve** every `@use` transitively — DFS with **cycle detection** (`ResolutionError` on a cycle, a missing file, or a named protocol absent from the target file).
3. **Splice**: emit one composed `.scr` — deduplicated `data` decls, then every referenced `aux global protocol` block inlined, then the parent's `global protocol`.
4. **Validate**: run the spliced whole through stock Scribble (`ScribbleValidator`). Rejection surfaces as `CompositionError` verbatim.

The composed output is an ordinary `.scr` (see `experiments/cases/composition/pipeline/FinancePipeline_composed.scr` — the `aux` blocks now inline). Three tagged error classes: `ResolutionError`, `RoleMappingError`, `CompositionError`.

### What composition proves — and what it does not

**Proves (transitively):** if the spliced whole is accepted by Scribble, then by Honda-Yoshida-Carbone POPL'08 the composite session is communication-safe, deadlock-free, branch-complete; and by construction (textual splice + Scribble substitution) each child's interaction sequence appears verbatim under the parent's role mapping — the composite is *faithful*. This is exactly the guarantee Scribble already gives for intra-file `aux`/`do`; the `@use` layer extends it across files with the metatheorem unchanged.

**Does not prove:** *projection-preserving* composition. The lexical composer always **re-projects the spliced whole** — independent teams cannot ship pre-verified child artefacts and have those compositions be guaranteed without re-checking. Closing that needs Hybrid MPST (Gheri-Yoshida OOPSLA'23), which is `ROADMAP.md` Phase 3.1 — **roadmap only, not implemented.**

### Status

| Layer | Status | File |
|---|---|---|
| Native intra-file `aux` + `do` | **native Scribble** — used as-is | `validator.py`, `efsm_parser.py` |
| Cross-file `// @use` lexical composer | **shipped** (Phase 1.5) | `composer.py` |
| Sequential / delegation composition | shipped (reduce to nested `do`) | `composer.py` + native |
| Hybrid-MPST projection-preserving composition | **roadmap only** (Phase 3.1) | — |

**Research basis:** Demangeon & Honda — *Nested Protocols in Session Types* (CONCUR'12); Honda-Yoshida-Carbone POPL'08 (soundness inherited transitively); Gheri & Yoshida — *Hybrid Multiparty Session Types* (OOPSLA'23, the future projection-preserving path).

---

## 4. Higher-order — session delegation

"Higher-order" session types = a **session (channel) can itself be carried as a message payload** — one role hands off the continuation of a sub-protocol to another role. This is the session-types analogue of passing a function as an argument.

Stock Scribble's grammar **already supports this**: a message payload position can name a protocol-typed channel, e.g. delegating `BankingSession@C` so the receiver continues that role. `ROADMAP.md` §1.5 records it explicitly — *"Delegation `(SubProto@role)` payload — Already supported by Scribble's grammar."*

Therefore higher-order needs **no layer**: STJP uses the native grammar, and the same `validator.py` / `efsm_parser.py` path handles it. In agent terms, delegation is how an orchestrator hands a spawned sub-agent the remainder of a protocol role rather than mediating every message itself.

A caveat worth stating: the current STJP benchmark protocols (`experiments/cases/*`) are flat — they exercise choice, recursion, and `do`-style nesting, but do **not** yet use payload-level delegation. The capability is available in the compiler; it is simply not yet stressed by a case. If a case needs it, add the delegation payload to the `.scr` directly — no STJP code change required.

**Research basis:** Honda, Yoshida, Carbone POPL'08 (delegation is core MPST); Mostrous & Yoshida (higher-order session processes).

---

## 5. Full extension matrix — implemented vs. roadmap

Honest status. "Layered" = companion file / component, no Scribble change. "Native" = stock Scribble used as-is.

| Capability | Mechanism | Kind | Status | Where |
|---|---|---|---|---|
| Well-formedness, projection, EFSM | Scribble CLI | native | **shipped** | `validator.py`, `efsm_parser.py` |
| Choice / branching, recursion | `choice`, `rec` | native | **shipped** | `protocol_parser.py` |
| Conditional refinement contracts (runtime) | `.refn` sidecar | layered | **shipped** | `refinement_checker.py` |
| Refinement compiled into projected skill (call site) | predicate → guard | layered | **shipped** | `agent_generator.py` |
| Value-dependent choice guards (asserted MPST, stateful) | `[choice at Role]` in `.refn` | layered | **shipped 2026-06-12** | `refinement_checker.py` (ChoiceGuard), `monitor.py` (value tracking + `choice_guard_violation`), both contract builders; see `CHOICE_GUARDS_AND_GATE.md` |
| Enforcement gate (reject before delivery + re-prompt) | in-line SessionMonitor | layered | **shipped 2026-06-12** | `foundry_runner.py` gate mode, arm `spec_llmvalid_gate` |
| Sub-protocol, intra-file | `aux` + `do` | native | **shipped** | native |
| Sub-protocol, cross-file (children protocols) | `// @use` composer | layered | **shipped** | `composer.py` |
| Higher-order / session delegation | protocol-typed payload | native | **available** (no case uses it yet) | native |
| Runtime monitor (EFSM conformance) | EFSM walker | layered | **shipped** | `monitor.py` |
| Static SMT discharge of refinements (Z3) | `smt.py` | layered | **roadmap — not built** | ROADMAP §2.1 |
| Structural / refinement subtyping | `subtype.py` | layered | **roadmap — not built** | ROADMAP §2.2–2.3 |
| Hybrid-MPST projection-preserving composition | build-back | layered | **roadmap** | ROADMAP §3.1 |
| Dynamic-multirole (spawn roles on demand) | `spawn` | grammar | **roadmap** | ROADMAP §3.3 |
| Probabilistic branches, bounded recursion, cost annotations, `<dyn>` | grammar | grammar | **roadmap** | ROADMAP §3.4–3.5, 3.10 |

> Note: `ROADMAP.md`'s Phase-2 table marks subtyping and static refinement discharge as "shipped"/"in flight", but the corresponding files (`stjp_core/smt.py`, `stjp_core/subtype.py`, `stjp_core/cli.py`) **do not exist** in the codebase as of 2026-05-20. Treat the ROADMAP's Phase-2 status as aspirational; this matrix reflects the code on disk.

---

## 6. Why a grammar fork is still off the table

For the grammar-level roadmap items (`<dyn>`, dynamic-multirole, cost, probabilistic, bounded recursion), `SCRIBBLE.md` §7 keeps three options open:

- **A — fork `scribble-java`**: rebase quarterly; rejected as a maintenance sink.
- **B — switch the compiler middle to `nuScr` (OCaml)** or `mpstk` (Scala): cleaner extension points, contribute upstream; revisit once the design stabilises.
- **C — keep layering** via companion files discharged against the projected EFSM.

Current plan: ship Phases 1–2 with **C**, revisit **B** later. Nothing in the current code requires touching `scribble-java/`, which is why it remains a clean upstream checkout — and should stay that way.

---

## 7. One-paragraph summary for a new contributor

Scribble is vendored stock and never edited. STJP extends it by **layering**: a `.refn` sidecar adds value-level *conditional* refinement contracts (parsed and runtime-checked by `refinement_checker.py`, compiled into call-site guards by `agent_generator.py`); a `// @use` comment directive plus `composer.py` adds cross-file *sub-protocol / children-protocol* composition (splice-then-revalidate); and *higher-order* session delegation needs nothing new because Scribble's own grammar already carries protocol-typed payloads. Everything else in the research roadmap — Z3 discharge, subtyping, dynamic-multirole, probabilistic/cost annotations — is designed but not yet built, and most of it is intended to stay layered rather than forked.
