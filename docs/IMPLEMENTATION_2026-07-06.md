# Implementation log — 2026-07-06

What was implemented today, the new additions, and how they map to the two
requested deliverables.

## The two requested implementations (verbatim intent)

1. **Clone the latest nuscr (coinductive fork)**
   `https://github.com/phou/nuscr_coinduction.git` and **make STJP work with this
   new Scribble**.
2. **Demonstrate STJP is useful with real "skills" cases.** Take a real set of
   agent skills from public git repos (non-malicious). Show that, **if not
   validated by Scribble**, they deadlock or raise a safety concern (must do A
   before B, but the skill goes straight to B → disaster). Then provide **revised
   skills** whose composed global protocol **is validated by Scribble**, and show
   it now runs **safely and cheaper (money + tokens)**. Run the tests on a **cheap
   LLM** (e.g. Haiku-class) as subagents.

---

## Deliverable 1 — nuscr coinductive backend

**Status: built and tested.**

- Vendored the fork at `nuscr-coinduction/` (git-ignored, like `scribble-java/`).
  Built a working Docker image `nuscr-coind:latest` via a wrapper
  [tools/nuscr/Dockerfile](../tools/nuscr/Dockerfile) that adds the protobuf +
  pkg-config depexts the fork's own Dockerfile omits (its `opam install` fails
  without them). The vendored checkout stays a clean upstream copy.
- New compiler abstraction in `stjp_core/compiler/`:
  - [compiler_iface.py](../stjp_core/compiler/compiler_iface.py) — a
    `ProtocolCompiler` interface + `get_compiler()` factory selecting the backend
    via `STJP_COMPILER_BACKEND` (`scribble` default, or `nuscr`), with a
    `ScribbleCompiler` adapter over the existing scribble-java path.
  - [nuscr_syntax.py](../stjp_core/compiler/nuscr_syntax.py) — a small `.scr` →
    `.nuscr` adapter (strips the Scribble-only `module`/`data` preamble; remaps a
    few Java payload types).
  - [nuscr_compiler.py](../stjp_core/compiler/nuscr_compiler.py) — a Docker-backed
    `NuscrCompiler`: `validate` (nuscr `check`), `project_efsm` (nuscr `--fsm`
    parsed into the same `EFSM` dataclass), `project_local_type` (with
    `inductive-full` / `coinductive-full` / `coinductive-plain` modes), and
    `roles_and_protocols` (nuscr `--enum`).
  - `efsm_parser.parse_nuscr_fsm_dot` — parses nuscr's DOT (unquoted node ids +
    trailing comma) into the shared `EFSM`.
- Tests: [tests/test_nuscr_backend.py](../stjp_core/tests/test_nuscr_backend.py) —
  `ALL PASS`, including Docker-backed validate/project and **coinductive
  projection** of a recursive protocol.
- **Honest finding:** nuscr is deliberately *not* Scribble-compatible and
  supports only a fragment — e.g. the finance protocol is rejected ("Non
  tail-recursive protocol is not implemented"). So the harness default stays
  `scribble`; nuscr is opt-in and its distinct value is coinductive projection of
  recursive protocols that stock projection leaves as a bare `rec`.

Plan of record: [reference/NUSCR_AND_SKILL_SAFETY_PLAN.md](reference/NUSCR_AND_SKILL_SAFETY_PLAN.md).

---

## Deliverable 2 — "unsafe skills" demo (before → after)

**Status: 5 cases built with before-evidence; revised skills validated; one real
Foundry run completed on the cheap model.**

### Cases (real, non-malicious, permissively-licensed skills)

| Case | Source (license) | Failure when NOT validated |
|---|---|---|
| `trade_deadlock` | escrow buyer/seller (existing) | deadlock — "Buyer would wait forever" |
| `airline_seat` | openai/openai-agents-python (MIT) | wrong-order — `SeatBooking` never receives `AssignFlight` |
| `content_pipeline` | crewAIInc/crewAI-examples (MIT) | publish-before-review — `Writer→Publisher` skips `Editor` |
| `code_execution` | microsoft/autogen (MIT) | execute-before-review — `Coder→Executor` skips `Reviewer` |
| `booking_saga` | langchain-ai/langgraph (MIT) | circular wait — `Payment`↔`Hotel` each wait first |

Each case lives under `experiments/cases/skills_safety/<case>/` with `case.yaml`,
`SOURCES.md` (repo / path / license provenance), `skills_original/` (the real
prose skills), and `_before/verdict.txt` (the compiler catching the unsafety at
design time via the bottom-up skill-compaction pipeline).

### Revised (validated) skills

- `skills_revised/` for the four new cases carry explicit `localtype` contracts
  that fix the ordering / break the cycle. Each compacts + synthesises a
  **Scribble-VALID** protocol at `protocols/<Proto>.scr` — and each **also
  validates through the new nuscr backend**, tying Deliverable 1 to Deliverable 2.

### Real run on the cheap model (gpt-4o)

Wired the cases into the 8-arm harness (`unchecked_skills` = original unsafe vs
`min_llmvalid` = validated) and ran on `gpt-4o` through Foundry hosted agents.
`trade_deadlock`, n=1:

| Metric | WITHOUT (unsafe original skills) | WITH (validated) |
|---|---|---|
| Success rate | 0.0% (deadlock) | 100.0% |
| Events delivered | 0 | 7 |
| Tokens / trial | 15,488 | 8,673 (−44%) |
| Agent calls / trial | 27 | 15 |

This is the requested result: unvalidated skills deadlock at 0% and higher cost;
the Scribble-validated skills complete 100% at lower token + call cost, on a cheap
model.

---

## Other additions today

- **gpt-4o deployment reference** captured at
  [.github/foundry-deployment.md](../.github/foundry-deployment.md) (account
  `foundary-tzuc06` / `rg-tzuc06`, tenant `16b3c013`, deployments incl. the cheap
  `gpt-4o`).
- **Repo fixes:** pointed all four `.env` loaders (`foundry_client`,
  `foundry_tracing`, `llm_client`, `apps/orchestrator`) at the canonical
  `stjp_core/.env`; fixed a broken `requirements-core.txt` pin
  (`github-copilot-sdk` `0.2.1` → `0.2.3`).

---

## Grouped hosted agents (Agent Framework workflow) — in progress

Beyond the per-role Agent Service agents, work is underway to host each use-case
role group as **one** Agent Framework **Workflow** (so Foundry shows a grouped
hosted agent with a single group-interaction trace, not scattered agents). The
`azd ai agent init` scaffold is created under `foundry_hosted_agents/`, and its
`main.py` is rewritten to host the `booking_saga` group
(`WorkflowBuilder` → `WorkflowAgent` → `ResponsesHostServer`), no GitHub PAT
required. **Deployment (`azd provision` / `azd deploy`) is billable and paused
pending explicit approval.**

## Still pending

- `azd provision` / `azd deploy` of the grouped workflow (awaiting go-ahead), then
  replicate for the other use cases.
- ~~Complete the remaining cheap-model runs~~ — **DONE in the cloud continuation below** (`airline_seat`, `content_pipeline`,
  `code_execution`, `booking_saga`) and write the formal
  `docs/results/RESULT_8_SKILL_SAFETY.md`.

---

## Cloud continuation (same day, Claude Code cloud session)

Everything below ran inside the Claude Code cloud sandbox (branch
`claude/stjp-skill-validation-bench-5t5qxi`), with **both compilers live** —
this closes the "still pending" cheap-model runs above.

1. **Toolchains installed under a restricted network policy.** The sandbox
   blocks Docker Hub blobs, opam.ocaml.org, and unscoped GitHub, so:
   scribble-java **master built from source** (Maven Central is allowed) into
   the expected `scribble-java/scribble-dist/target/lib/` layout, and the
   **coinductive nuscr fork built on a GitHub Actions runner** of the user's
   fork (`ginaecho/nuscr_coinduction`, workflow `build-nuscr.yml` on branch
   `ci-build`, OCaml 5.3 — 5.2 has no dependency solution) with the Linux
   binary committed to the fork's `ci-artifacts` branch and fetched over git.
   New env var `STJP_NUSCR_BIN` makes `NuscrCompiler` run the native binary
   instead of Docker. Full recipe + pitfalls (incl. the **broken 2017 Maven
   Scribble releases** that parse every protocol to zero declarations and so
   silently accept anything):
   [reference/NUSCR_CLOUD_INSTALL.md](reference/NUSCR_CLOUD_INSTALL.md).
   `stjp_core/tests/test_nuscr_backend.py` — ALL PASS incl. the runtime and
   coinductive-projection tests, no Docker.
2. **Design-time evidence reproduced live.** All four `skills_original` sets
   are rejected by the bottom-up pipeline (compatibility/synthesis from the
   committed `_before/local_types`); all four `skills_revised` sets compact →
   synthesize → validate **through both backends** in-sandbox.
3. **The cheap-model benchmark ran to completion** — 4 cases × 3 arms ×
   n=10 (120 trials), every role a Haiku-class Claude subagent, driven
   through the new `experiments/subagent_trials/skills_cases.py` +
   `dispatch_helper.py` on the deterministic engine. Headline: original
   skills **0% GCR (∞ cost-to-goal)**; contract-as-text **100% GCR but 50%
   CGC** (20 duplicate-irreversible-act disasters, incl. 10 double charges);
   full STJP **100%/100%, 0 disasters, −45% tokens, 3.5 vs 10+ agent
   calls/trial**. Write-up:
   [results/RESULT_8_SKILL_SAFETY.md](results/RESULT_8_SKILL_SAFETY.md);
   committed raw data:
   `experiments/subagent_trials/reports/ss2026_skill_safety/`.
