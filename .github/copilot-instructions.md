# AI_ST_verf / STJP — Copilot instructions

A compiler-with-prover for AI-agent specifications grounded in **multiparty
session types (MPST)** on top of the [Scribble](http://www.scribble.org/)
compiler. It turns a natural-language intent into a validated global protocol,
projects it to per-role local types (EFSMs), generates per-role agent markdown,
and monitors a live multi-agent session against the projected type — checking
message order, labels, and payload (refinement) constraints.

## Repository shape (read this first)

The repo has three top-level parts. **The root `README.md` describes an older
aspirational layout (`tools/`, `stjp/`, `examples/`, `vendor/`) that does NOT
exist on disk — trust the actual tree below over it.**

| Path | What it is |
|---|---|
| `stjp_core/` | The Python **library** (compiler/authoring/generation/monitor/evaluation/foundry/apps/tests). Library-only since 2026-05-29. |
| `experiments/` | The **benchmark harness** — the 8-arm WITH-vs-WITHOUT matrix. Imports `stjp_core` as a library. |
| `scribble-java/` | Vendored Scribble compiler (built; invoked by `stjp_core/compiler`). |
| `docs/`, root `*.md` | Design/research docs (`ROADMAP.md` = the plan; `MPST_STATIC.md`, `SCRIBBLE.md`, `RESEARCH.md` = reference). |

**`stjp_core/CLAUDE.md` and `experiments/CLAUDE.md` are authoritative policy
docs.** Read the relevant one before changing code in that subtree — they
encode rules (Foundry-first, the 8-arm matrix, persistence) not obvious from
the source.

## Environment & setup

- **Python 3.13**, single shared venv at `stjp_core/.venv`; one
  `stjp_core/requirements.txt` covers both `stjp_core/` and `experiments/`.
- **Java 17** on `PATH` for the vendored Scribble compiler.
- **Azure AI Foundry** deployment + `az login` for any LLM-using code.
- Windows / PowerShell is the primary environment.

```powershell
cd stjp_core
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create stjp_core\.env (keys below), then:
az login
```

`.env` (in `stjp_core/`): `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`
(model, e.g. gpt-5.4), `AZURE_OPENAI_ENDPOINT` (only for `STJP_LLM_BACKEND=chat`),
`STJP_LLM_BACKEND` (`foundry` default | `chat`). `requirements.txt` line 16
warns: do **not** install the `asyncio` PyPI backport — it shadows the stdlib.

## Build / test / run

There is **no `pytest`, lint, or build step installed.** Tests are plain
scripts with `if __name__ == "__main__":` guards that call their test functions
directly. Run from the repo root (each entry point has a `sys.path` bootstrap so
it imports `stjp_core` as a package):

```powershell
# Run a single test file (this is also how you run "one test"):
python stjp_core\tests\test_change_request.py        # prints "ALL PASS"

# Benchmark — one case, N trials:
python experiments\scripts\case_runner.py finance 1
python experiments\scripts\run_subset.py finance 1 bare spec_llmvalid   # subset of arms
python experiments\scripts\case_runner.py --all 10

# Apps:
python stjp_core\apps\orchestrator.py                # protocol-evolution CLI
python experiments\apps\live_demo\app.py             # live 8-arm demo (Flask UI) → http://127.0.0.1:5005/
python stjp_core\apps\stjp_dual_demo.py 10           # legacy WITH-vs-WITHOUT demo
```

## Architecture — the pipeline

The whole system is one pipeline; understanding it requires reading across
`stjp_core/`'s sub-packages:

```
NL intent → authoring/ (LLM) → .scr (+ .refn sidecar)
          → compiler/  (Scribble: validate + project to per-role EFSM)
          → generation/ (EFSM → SKILL.md / agent.md; refinements compiled into call-site guards)
          → monitor/   (walk each role's EFSM vs. its trace → Set A conformance verdicts)
          → evaluation/(goals vs. trace → Set B goal achievement)
```

The **LLM is in the cold path only**: once a protocol converges, every
execution is checked by the deterministic monitor with no LLM in the loop.
Conformance soundness rests on the MPST projection theorem — local conformance
for every role implies global protocol satisfaction (no central observer).

**Two-set evaluation**: Set A = global-type conformance (`monitor/monitor.py`,
`summary.json`); Set B = goal achievement (`evaluation/`, `summary_eval.json`).
Set B has three lenses of increasing leniency — `strict` (exact
`(sender,receiver,label)` + predicate), `role_pair` (label dropped), `semantic`
(LLM-judged). Strict is N/A for arms with no protocol vocabulary. A
`protocol_unprojectable` marker means the monitor was disabled for that arm, so
its zero-violation count is **not** a success signal. See
`docs/archive/EXPERIMENT_DESIGN_v2.md`.

### How Scribble is extended (the layering model)

The vendored `scribble-java/` is **stock upstream, never forked or edited** —
no grammar change, no new AST node. Every added capability is a *layer* beside
the `.scr` or a Python component consuming Scribble's output. **Never modify
`scribble-java/`; keep it a clean upstream checkout.** The three extensions
(`docs/reference/SCRIBBLE_EXTENSIONS.md`):

- **Conditional / refinement** — a `.refn` sidecar (same basename as the `.scr`)
  adds value-level predicates over payloads. Enforced at three points: the LLM
  is told the predicate, `generation/agent_generator.py` compiles it into a
  call-site guard, and `monitor/` re-checks it on the trace.
- **Composition** — cross-file `// @use <Proto> from "<path>";` directives live
  inside Scribble comments (stock parser ignores them); `compiler/composer.py`
  splices and re-validates. Native intra-file `aux`/`do` is used as-is.
- **Higher-order / delegation** — native Scribble grammar; no layer (no case
  exercises it yet).

## Key conventions

- **Imports are always `from stjp_core.<package>.<module> import …`.** Packages:
  `compiler`, `authoring`, `generation`, `monitor`, `evaluation`, `foundry`,
  `apps`, `tests` (+ `config.py` at top). Entry points self-bootstrap `sys.path`.
- **Foundry-first**: every LLM call routes through the Azure AI Foundry Agent
  Service so it is portal-visible. Use
  `from stjp_core.foundry.llm_client import LLMClient` (resolves to the Foundry
  backend by default). Do not add direct chat-completion calls except via the
  `STJP_LLM_BACKEND=chat` escape hatch. See `stjp_core/CLAUDE.md`.
- **Library-only data layout**: protocols, refinements, skills, and run outputs
  live under `experiments/cases/<case>/`, never in `stjp_core/`. The legacy
  `stjp_core/protocols/`, `skills/`, `version_history.json` and the
  `PROTOCOLS_DIR`/`SKILLS_DIR` config constants were removed 2026-05-29.
- **Skills files are not authoritative and are dead in the 8-arm matrix** — they
  were LLM-authored on top of protocols and drift. Don't treat them as source of
  truth; don't regenerate them into case dirs without rechecking
  (`experiments/CLAUDE.md`).
- **Scribble's CLI rejects paths containing spaces** — and this repo sits under
  `…\OneDrive - Microsoft\…`. `config.py` resolves `SCRIBBLE_PATH`/`JAVA_HOME`
  relative to the repo and the compiler wrappers pass paths relative to
  Scribble's working dir. Preserve that when touching `compiler/`.
- **Azure auth on Windows**: use `stjp_core/foundry/az_credential.py`'s
  `AzCliCredential`, not `azure-identity`'s — the official one can't find
  `az.cmd` without `shell=True`.
- **Naming**: `case_id` is lowercase snake_case; protocol role names are
  PascalCase.
- **Refinement guards** (`.refn` sidecar, `compiler/refinement_checker.py`) are
  compiled into call-site guards in generated agents — payload values in traces
  are pure LLM output with no data source, so these guards are what enforce
  value constraints.

## The benchmark matrix (experiments/)

`experiments/baselines/registry.py` is the single source of truth for the 8
arms; `baselines/instructions.py` holds the 4 instruction builders. Arms vary
only in *what protocol information the agent receives* (none → validated global
text → projected per-role local type + monitor). Per-arm rationale and the
"unsafe vs. valid" deadlock story live in `experiments/CLAUDE.md` and
`baselines/README.md` — not in `case.yaml`, which is the per-case spec only.
There are ~14 cases under `experiments/cases/` (e.g. `finance`, `banking`,
`code_review`, `composition`, `retry_loop`).

**The live demo** is the Flask UI at `experiments/apps/live_demo/` — run
`python experiments/apps/live_demo/app.py` (serves `http://127.0.0.1:5005/`).
Its `app.py` is the entry point; `runner.py` does LLM drafting and spawns
`experiments/scripts/run_subset.py` as a subprocess, tailing each arm's
`events_<arm>.jsonl` over SSE. (The older `stjp_core/apps/stjp_dual_demo.py`
+ `stjp_serve.py` + `stjp_comparison.html` dual demo is legacy.)

## Docs map & a caveat

Design/reference lives in `docs/` and root `*.md`:

| Doc | What it covers |
|---|---|
| `ROADMAP.md` | Three-phase plan. **Caveat: its Phase-2 status is aspirational** — files it references (`smt.py`, `subtype.py`, `cli.py`) do not exist. Trust the code on disk and the status matrix in `docs/reference/SCRIBBLE_EXTENSIONS.md` §5 for what's actually built. |
| `docs/reference/SCRIBBLE_EXTENSIONS.md` | The layering model (refinement/composition/higher-order) + honest implemented-vs-roadmap matrix. |
| `docs/archive/EXPERIMENT_DESIGN_v2.md` | Set A / Set B / process-cost metric framework. |
| `docs/reference/FOUNDRY_VISIBILITY.md` | The 3 Foundry portal surfaces (agents / threads / tracing) and exact wiring. |
| `docs/reference/GAP_CLOSED.md` | The refinement call-site closure. |
| `docs/diary/DIARY.md` | Newest-first development log — best place to learn recent changes. |
| `MPST_STATIC.md`, `SCRIBBLE.md`, `RESEARCH.md` | MPST/runtime model, the Scribble case, bibliography. |
