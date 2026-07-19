# STJP — a compiler for AI-agent interactions

`stjp_core/` is the **library layer** of STJP (Session-Typed Protocols for
agents). It makes the interactions *among* a team of AI agents correct **by
construction**.

You describe, in plain English, how several agents should work together. STJP
compiles that description into a **protocol that is mathematically proven
deadlock-free before any agent runs**, hands each agent its own contract, and
then watches the running session with deterministic code — checking that every
message arrives in the right order, with the right label, carrying a payload
that satisfies the agreed constraints. Twenty years of session-type theory,
pointed at agents.

The theory underneath is **multiparty session types (MPST)** on top of
[Scribble](http://www.scribble.org/). You don't need to know that to use the
library, but it's why the guarantees hold.

> **Scope.** This README covers the `stjp_core/` library and its runnable apps.
> The Scribble compiler lives in `../scribble-java/` (cloned locally during
> setup from [scribble/scribble-java](https://github.com/scribble/scribble-java);
> the directory is gitignored, so it is absent in a fresh clone until you run
> the setup step); the research and design write-ups in
> [`../docs/`](../docs/). The LLM-driven cross-case benchmark and the Flask live
> demo live in the `experiments/` harness of the development tree — they are kept
> **out of this security-governed repository** because they pull in dependencies
> with known vulnerabilities (see the install profiles below).

---

## Why it matters in one picture

```
WITHOUT STJP                         WITH STJP
agents free-text at each other       agents follow a proven protocol
   │                                    │
   ├─ can deadlock (each waiting        ├─ deadlock-freedom checked at
   │  on the other) — silent, fatal     │  compile time — caught before run
   ├─ can drift off the plan            ├─ every message checked live against
   │  with nobody noticing              │  each agent's local contract
   └─ burns tokens re-deliberating      └─ contract replaces re-deliberation
      the same coordination               (smaller prompts, fewer turns)
```

The LLM sits in the **cold path**. Once a protocol converges, every execution
is checked by a deterministic monitor with **no LLM in the loop** — so the
guarantees cost nothing per run and can't be "argued out of" by a model.

---

## Install — pick a profile by what you need

STJP is now committed inside a Microsoft-governed repository, where the GitHub
dependency policy scanner blocks packages with known vulnerabilities. The
dependencies are therefore split into **profiles** so you only pull in what a
given task requires — and the default profile is **security-clean**.

| Install | Command | What you get | Security |
|---|---|---|---|
| **Default (recommended)** | `pip install -r requirements.txt` | The verification core: compiler, validator, projection, runtime monitor, goal checking, case loading. | ✅ Zero known vulnerabilities — passes the GitHub Policy Service scan. |
| **Core / Foundry** | `pip install -r requirements-core.txt` | Adds the Azure AI Foundry + Azure OpenAI + agent-framework stack needed for **any LLM call** (protocol drafting, the benchmark runs). | ⚠️ Pulls transitive vulnerabilities via the Azure / agent SDKs. |
| **Demo / Full** *(development tree only)* | `requirements-demo.txt` / `requirements-full.txt` | The Flask / ASGI live-demo web layer (on top of core). Shipped only in the development tree, not in this repo. | ⚠️ Experimental; adds further transitive vulnerabilities (aiohttp, Starlette, …). |

`requirements.txt` simply re-exports `requirements-secure.txt` (the audited,
vulnerability-free pin list). **If you only need to compile, validate, project,
and monitor protocols, the default install is all you need — and it is the only
profile that passes the Microsoft security scan.**

### What actually runs on the default (secure) install

Verified against a clean virtualenv with `requirements.txt` only:

| Runs on default install ✅ | Needs `requirements-core.txt` (Azure/LLM) ⚠️ |
|---|---|
| `compiler/` — validate, project, parse, compose, refinements | `authoring/architect.py` — LLM drafts a protocol |
| `monitor/` — walk each role's local type against a trace | `generation/skills_generator.py`, `skills_synthesizer.py` |
| `evaluation/` — goal achievement against a trace | `foundry/` — every Foundry / Azure OpenAI call |
| `generation/` analysis passes (structural / security / completeness) | `../experiments/baselines/` — the benchmark runners |
| `authoring/change_request.py` in mock mode (no Azure) | the full `case_runner.py` benchmark run |
| case loading + the post-run analyzers (`regrade_conformance`, `criticality_gate`, `severity_grader`, `index_builder`) | the Flask live demo's *draft* / *run* actions (page itself boots on default + Flask) |

> The split is by **import**: only `foundry/`, `authoring/architect.py`,
> `generation/skills_*` and `experiments/baselines/` import an LLM SDK at module
> load. Everything else — the entire deterministic verification path — imports
> on the secure baseline alone.

### Prerequisites

- **Python 3.13** (project virtualenv: `stjp_core/.venv`)
- **Java 17** — for the vendored Scribble compiler (`java` on `PATH`)
- **Scribble** — cloned and pre-built at `../scribble-java/` (from [scribble/scribble-java](https://github.com/scribble/scribble-java); gitignored, so clone it once during setup)
- **Azure OpenAI / AI Foundry** — *only* for the LLM profiles: a GPT deployment plus the Azure CLI (`az login`)

```powershell
cd stjp_core
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # secure default

# .env (only needed for the LLM profiles — see CLAUDE.md for the full key list):
#   AZURE_AI_PROJECT_ENDPOINT=...
#   AZURE_OPENAI_DEPLOYMENT=...
# az login
```

---

## The pipeline

```
        natural-language intent / requirement
                       │
        ┌──────────────▼───────────────┐
        │  authoring/   (LLM)          │  architect.py, evolution_loop.py
        │  intent → Scribble .scr      │  change_request.py, prompts.py, rules.py
        └──────────────┬───────────────┘
                       │  .scr   (+ .refn refinement sidecar)
        ┌──────────────▼───────────────┐
        │  compiler/    (Scribble)     │  validator.py    — well-formedness + deadlock-freedom
        │  validate, project           │  efsm_parser.py  — projection → per-role state machine
        └──────────────┬───────────────┘
                       │  per-role local type (state machine)
        ┌──────────────▼───────────────┐
        │  generation/                 │  agent_generator.py, skills_generator.py
        │  local type → agent contract │  refinements compiled into call-site guards
        └──────────────┬───────────────┘
                       │  per-role agents
        ┌──────────────▼───────────────┐
        │  monitor/                    │  monitor.py — walks each role's state machine
        │  trace → conformance verdicts│  against its observed trace   (Set A)
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼───────────────┐
        │  evaluation/                 │  goal_elicitor.py — goal achievement
        │  goals + run summary         │  (Set B)
        └──────────────────────────────┘
```

The **projected local type** is each role's own slice of the global protocol,
expressed as an extended finite-state machine (a state machine whose
transitions are "send / receive label X to / from role Y"). The monitor walks
that machine against what the role actually did.

---

## Package layout

`stjp_core/` is a Python package, organised by responsibility. `config.py`
stays at the top because every package shares it. Imports are
`from stjp_core.<package>.<module> import …`.

> **Library-only since 2026-05-29.** Protocols, skills, and run outputs all
> live under `../experiments/cases/<case>/`. This package holds code only — the
> authoring entry points take an explicit `case_dir`. (See `CLAUDE.md`.)

```
stjp_core/
  config.py        shared paths — Scribble dist, JAVA_HOME, repo-relative resolution
  compiler/        the Scribble layer (validate, project, parse, compose, refinements)
  authoring/       LLM: intent → validated protocol
  generation/      projected local type → agent / skill markdown (+ static checks)
  monitor/         the local-typed runtime monitor
  evaluation/      goal achievement + run aggregation
  foundry/         Azure / AI Foundry connection layer (LLM calls)
  runtime/         decentralized-runtime experiments (DeLM-style)
  governance/      policy / audit export for the MS Agent Governance Toolkit
  apps/            runnable entry points
  tests/           focused offline tests
```

### `compiler/` — the Scribble layer
Turns a `.scr` into validated, projected types.

| File | Purpose |
|---|---|
| `validator.py` | Runs the Scribble compiler: well-formedness + **deadlock-freedom** check, then endpoint `-project`. |
| `efsm_parser.py` | Runs Scribble `-fsm`; parses the output into a per-role state machine (the projected local type). |
| `protocol_parser.py` | Parses a `.scr` into a structured `ParsedProtocol` (roles, messages, branches). |
| `composer.py` | Resolves cross-file `// @use` directives; splices sub-protocols into one validated `.scr`. |
| `refinement_checker.py` | Parses the `.refn` sidecar; evaluates sandboxed payload predicates (conditional MPST). |

### `authoring/` — LLM intent → protocol
The closed loop that turns a natural-language requirement into a validated
protocol. **This is where the LLM lives.**

| File | Purpose |
|---|---|
| `architect.py` | LLM Architect — requirement → Scribble `.scr`; error-driven repair. |
| `evolution_loop.py` | The closed loop: generate → validate → fix → skills → commit. |
| `change_request.py` | Classify + apply a change request to an existing protocol (has a **mock mode** that runs with no Azure). |
| `fanout_normalizer.py` | Normalizes one-to-many message fan-out before validation. |
| `version_control.py` | Multi-protocol version tracking: diff, rollback, merge. |
| `prompts.py` / `rules.py` | LLM system prompts; Scribble-syntax knowledge base used during error recovery. |

### `generation/` — projected type → agent / skill markdown
Produces (and statically checks) the per-role agents.

| File | Purpose |
|---|---|
| `agent_generator.py` | Projected state machine → `SKILL.md` / subagent `.md` / Python stub, with refinement predicates **compiled into call-site guards**. |
| `capability_projector.py` | State machine → minimum required tool set for a role. |
| `skills_generator.py` | LLM-generates a per-role `<Role>_skills.md`. |
| `skills_parser.py` | Parses a skills `.md` into structured form. |
| `skills_compiler.py` | 3-pass skills verification (structural / security / completeness). |
| `structural_checker.py` | Pass 1 — skills match the protocol's roles / messages / branches. |
| `security_scanner.py` | Pass 2 — injection / dangerous-pattern scan, grounded in the OWASP Top-10 for LLM Applications. |
| `completeness_checker.py` | Pass 3 — every action has purpose, pre/postconditions, branch coverage. |
| `skills_synthesizer.py` | **Reverse pipeline**: per-role skill files → reconstructed global `.scr`. |

### `monitor/` — the local-typed runtime monitor
Walks each role's **projected local type** against the role's observed trace.
This is **Set A — global-type conformance**; verdicts are produced only when a
global type was given and projected.

| File | Purpose |
|---|---|
| `monitor.py` | `SessionMonitor` — walks a role's state machine vs. its trace; emits conformance verdicts (off-protocol, refinement-failed, …). |
| `stjp_live_emitter.py` | Streams per-event JSONL while driving the monitor (live UI feed). |

### `evaluation/` — goal achievement + run aggregation
Deterministic, no LLM in the loop.

| File | Purpose |
|---|---|
| `goal_elicitor.py` | Intent → math-checkable goals; `verify_goals_against_trace` (branch-aware) — **Set B**. |
| `_summary.py` | Standalone aggregator: run JSONL → per-trial summary. |

### `foundry/` — Azure / AI Foundry connection layer
Every LLM call routes through here so it is visible in the Foundry portal.
**Requires the `requirements-core.txt` profile.**

| File | Purpose |
|---|---|
| `llm_client.py` | `LLMClient` — public entry point; resolves to the Foundry path by default (`STJP_LLM_BACKEND=chat` for the direct path). |
| `foundry_client.py` | `FoundryLLMClient` — single-shot calls through the `stjp-utility` agent. |
| `foundry_tracing.py` | `enable_foundry_tracing()` — wires OpenTelemetry → Application Insights. |
| `session_helpers.py` | `build_view` / `parse_action` / `latest_assistant_text` — the per-role turn-loop primitives used by the benchmark. |
| `az_credential.py` | `AzCliCredential` — Azure auth via `az login` (Windows-safe). |

See `CLAUDE.md` for the Foundry-first policy (every LLM call is portal-visible).

### `apps/` — runnable entry points
| File | Purpose | Profile |
|---|---|---|
| `orchestrator.py` | Interactive protocol-evolution CLI (`--case <id>`). | core |
| `stjp_dual_demo.py` | WITH-vs-WITHOUT live demo (writes `events_*.jsonl` for `stjp_comparison.html`). | core |
| `stjp_serve.py` | Tiny stdlib HTTP server for the comparison HTML. | default |

Each app bootstraps `sys.path` at the top so it runs directly
(`python stjp_core/apps/<app>.py`).

### `tests/`
`test_change_request.py` — an **offline** end-to-end test (mock classify → mock
sub-protocol → the **real** composer → real Scribble validation). It runs on
the **default secure install** with no Azure, and is a good smoke test that
your Java + Scribble setup works:

```powershell
python stjp_core/tests/test_change_request.py    # expect "ALL PASS"
```

---

## The protocol-evolution app (`apps/orchestrator.py`)

Describe a protocol in English; the system generates → validates → fixes →
generates skills → version-controls it. (Needs the **core** profile + `az login`.)

```
python stjp_core/apps/orchestrator.py --case <case_id>            # interactive
python stjp_core/apps/orchestrator.py --case <case_id> --auto     # scripted demo
```

### Skills Compiler — the second verification layer

Scribble validates the protocol *shape*; the Skills Compiler
(`generation/skills_compiler.py`) validates the *implementation*, in three passes:

| Pass | Checks | Analogy |
|---|---|---|
| **Structural** | skills files match the protocol's roles / messages / branches | function bodies match their headers |
| **Security** | no markdown injection, dangerous actions, or prompt overrides | a static security scanner (SAST) |
| **Completeness** | every action has purpose, pre/postconditions, branch coverage | 100% case coverage in a switch |

The security pass is grounded in the OWASP Top-10 for LLM Applications
(markdown injection, shell execution, role-hijack / instruction-override);
patterns live in `generation/security_scanner.py`.

---

## Run (from the repo root)

```powershell
python stjp_core/tests/test_change_request.py          # offline, default install — verifies Java + Scribble
python stjp_core/apps/orchestrator.py --case finance   # protocol-evolution CLI   (core profile)

# In the development tree (not this repo):
python experiments/scripts/case_runner.py finance 1    # the benchmark            (core profile)
python experiments/apps/live_demo/app.py               # Flask live demo          (demo profile)
```

---

## Pointers

- `CLAUDE.md` — Foundry-first policy, env vars, agent/thread cleanup.
- [`../docs/diary/DIARY.md`](../docs/diary/DIARY.md) — newest-first development log.
- [`../docs/reference/GLOSSARY.md`](../docs/reference/GLOSSARY.md) — every term spelled out.
- [`../docs/archive/BENCHMARK_DESIGN.md`](../docs/archive/BENCHMARK_DESIGN.md) — the gated-layer benchmark and its headline numbers.
- [`../docs/reference/SCRIBBLE_EXTENSIONS.md`](../docs/reference/SCRIBBLE_EXTENSIONS.md) — how STJP extends Scribble (refinements, composition, higher-order).
- [`../ROADMAP.md`](../ROADMAP.md) — the three-phase project plan.
- `experiments/` (development tree) — the multi-arm benchmark harness and Flask live demo.
</content>
</invoke>
