# Implementation Plan — nuscr backend + "unsafe skills" demo

Date: 2026-07-06. Status: in progress.

> Progress (2026-07-06, cloud session): Phase 1 replicated WITHOUT Docker in
> the Claude Code sandbox — nuscr built by GitHub Actions on the user's fork
> (`ci-build` branch, OCaml 5.3) and consumed as a native binary via the new
> `STJP_NUSCR_BIN`; scribble-java master built from source via Maven Central
> (see `NUSCR_CLOUD_INSTALL.md`). Phases 2.3–2.5 DONE: revised skills validate
> through BOTH backends live; the cheap-LLM A/B ran as 4 cases x 3 arms x n=10
> on Haiku-class subagents (`experiments/subagent_trials/skills_cases.py`);
> results in `docs/results/RESULT_8_SKILL_SAFETY.md` (0% GCR unvalidated vs
> 100%/100% STJP at -45% tokens; contract-as-text arm exposes 20 duplicate
> irreversible acts).


> Progress (2026-07-06): Phase 1.1–1.4 DONE. nuscr coinductive fork builds as
> Docker image `nuscr-coind:latest`; `stjp_core/compiler/` now has a
> `ProtocolCompiler` interface (`compiler_iface.py`) with `get_compiler()`
> selecting `scribble` (default) or `nuscr`, a `.scr`→`.nuscr` adapter
> (`nuscr_syntax.py`), a Docker-backed `NuscrCompiler` (`nuscr_compiler.py`), and
> a nuscr FSM-DOT parser (`efsm_parser.parse_nuscr_fsm_dot`). Tests in
> `tests/test_nuscr_backend.py` pass, including Docker-backed validate/project and
> **coinductive projection** of a recursive protocol. Finding: nuscr supports only
> a *fragment* — the finance protocol is rejected ("Non tail-recursive protocol not
> implemented"), so the harness default stays `scribble` (Phase 1.5). Skills-safety
> Phase 2.1–2.2 DONE (5 cases with before-evidence).

This plan covers two deliverables the user asked for:

1. **Integrate the latest nuscr** (the coinductive-projection fork at
   `phou/nuscr_coinduction`, branch `coinductive_projection`) as a protocol
   compiler backend, and make STJP work with it.
2. **A "real skills gone wrong" demo**: take genuine agent skills from public
   repos, show that WITHOUT protocol validation they deadlock or violate a
   safety ordering (do B before A → disaster), then ship **revised skills**
   whose composed global protocol is validated by the compiler, and show the
   revised set runs safely *and* cheaper — using a cheap LLM (Haiku-class) as
   the subagent runner.

---

## 0. Findings that shape the plan (read first)

- **nuscr is NOT Scribble-compatible.** The nuscr project itself says so:
  different surface syntax, OCaml/`opam` toolchain, top-down MPST only. Existing
  `.scr` files will **not** parse in nuscr unchanged. So we cannot "swap the jar
  for a binary" — we need a small syntax adapter and a new backend, keeping
  `scribble-java` in place.
- **The fork's value is coinductive projection** (`coinductive_projection`
  branch, HEAD `cc7c72e`). Coinductive projection can project **recursive /
  looping** protocols that stock projection rejects at the merge step. That is
  exactly what the loop-shaped cases (`retry_loop`, `iterative_polling`,
  `nested_retry`) need — several were only made to pass by flattening the loop.
- **Current compiler surface is tiny and well-isolated** — swapping is feasible:
  - [stjp_core/config.py](../../stjp_core/config.py) — `SCRIBBLE_PATH`, `JAVA_HOME`.
  - [stjp_core/compiler/validator.py](../../stjp_core/compiler/validator.py) —
    `ScribbleValidator.validate_protocol()` (silence = success) and
    `get_projection(protocol, role)`; shells out to
    `java org.scribble.cli.CommandLine`.
  - [stjp_core/compiler/efsm_parser.py](../../stjp_core/compiler/efsm_parser.py)
    — parses Scribble's `-fsm` Graphviz DOT into `EFSM`/`Transition`. Regex
    expects `Role!Label(Type)` / `Role?Label(Type)` edge labels.
  - Everything downstream (monitor, generation, gate, scheduler) consumes the
    parsed `EFSM`, not raw compiler output — so if the new backend produces the
    same `EFSM`, nothing downstream changes.
- **Never edit `scribble-java/`** (repo invariant) and, symmetrically, keep the
  vendored `nuscr_coinduction` a clean upstream checkout.
- **"unsafe" already has a canonical example**: `experiments/cases/trade_deadlock`
  (Buyer "don't pay until goods arrive" vs Seller "don't ship until paid") and
  the skill-compaction pipeline
  ([stjp_core/generation/skill_compactor.py](../../stjp_core/generation/skill_compactor.py))
  already turns per-role skill markdown into local types, synthesises a global
  type, and lets the compiler judge it. The demo extends this with **real**
  skills from public repos.
- **Haiku is not on Azure AI Foundry.** The repo is Foundry-first (gpt-5.4 via
  Agent Service). "Run tests with Haiku subagents" needs one of: (a) the
  `runSubagent` Haiku-class agents already available in this workspace, or (b) a
  new cheap-model backend (`STJP_LLM_BACKEND=chat` already exists as the escape
  hatch). See **Decision D3**.

---

## Decisions (confirmed 2026-07-06)

- **D1 — Add nuscr as a selectable backend** behind an adapter; scribble-java
  stays the default + comparison oracle. (No rip-and-replace.)
- **D2 — Build/run nuscr via Docker.** The fork ships a `Dockerfile`; the Python
  backend invokes nuscr with `docker run` (mount the protocol file, space-free
  container path). No WSL/native-opam dependency on the host.
- **D3 — Cheap LLM = a cheap Azure model (gpt-4o-mini class).** Deploy it as a
  **hosted agent** (see §2.4b) so every role's trace is visible in the Foundry
  portal (Agents → Threads → Tracing). Note: the direct `STJP_LLM_BACKEND=chat`
  path is Foundry-*invisible*, so for the demo trials the cheap model runs
  through the Foundry Agent Service (hosted), not the raw chat path. Set the
  deployment name in `.env`; record model + cost basis in the result doc.
- **D4 — Skill sources: ALL 5 approved (2026-07-06).**
  1. `openai/openai-agents-python` (airline/customer-service) — wrong-order (refund before cancel).
  2. `crewAIInc/crewAI-examples` (content pipeline) — wrong-order (publish before review).
  3. `microsoft/autogen` (coder + code-executor) — deadlock / execute-before-review.
  4. `langchain-ai/langgraph` (supervisor + booking saga) — deadlock + saga ordering.
  5. `anthropics/skills` (buyer/seller pair) — deadlock (pay↔ship).
  Each gets a `SOURCES.md` (repo, commit, license) and a safety review before import.
- **D5 — Deliverable location:** demo cases under
  `experiments/cases/skills_safety/<name>/`; results under
  `docs/results/RESULT_8_SKILL_SAFETY.md`.

---

## Part 1 — Integrate nuscr (coinductive fork)

### Phase 1.1 — Vendor + build the toolchain

- Clone `https://github.com/phou/nuscr_coinduction.git` (branch
  `coinductive_projection`) into `nuscr-coinduction/` at repo root (sibling of
  `scribble-java/`). Add to `.gitignore` like `scribble-java/` (do **not** mirror
  the OCaml build tree into the eag-innovation monorepo).
- Build path (per D2 — Docker):
  - `docker build -t nuscr-coind .` in the fork checkout (uses the shipped
    `Dockerfile`).
  - Invoke as `docker run --rm -v <case_dir>:/work nuscr-coind nuscr /work/<file>`;
    pin the image tag so results are reproducible.
  - Record the exact working build + run recipe in
    [docs/1_TECH_SETUP.md](../1_TECH_SETUP.md) and a new
    `/memories/repo/nuscr-build.md`.
- Smoke test (a quick end-to-end check): `docker run … nuscr --help`, then project one bundled example
  (`nuscr examples/… --project Role@Proto`) and one `--fsm` to capture the exact
  CFSM/DOT output format this fork emits (it may differ from mainline).

### Phase 1.2 — `.scr` → `.nuscr` syntax adapter

- Add `stjp_core/compiler/nuscr_syntax.py`: translate the subset of Scribble
  syntax the cases use into nuscr syntax (message decls `L(T) from A to B;`,
  `choice at R { … } or { … }`, `rec X { … continue X; }`, roles, `do`/`aux`).
  Start from the actual `.scr` files under `experiments/cases/*/protocols/`.
- Round-trip test: translate every case's `v1.scr`, confirm nuscr **parses** it
  (validation verdict may differ — that is the point for the recursive cases).

### Phase 1.3 — `NuscrCompiler` backend behind a common interface

- Extract a `ProtocolCompiler` protocol (interface) with:
  - `validate(protocol_path) -> (ok: bool, message: str)`
  - `project_efsm(protocol_path, protocol_name, role) -> EFSM`
- Refactor the existing `ScribbleValidator` to implement it (behaviour
  unchanged; keep `validate_protocol`/`get_projection` as thin shims so nothing
  else breaks).
- New `stjp_core/compiler/nuscr_compiler.py`:
  - `validate()` runs `nuscr <file>` (via `wsl`/`docker` per D2), maps
    exit/stderr to `(ok, message)`.
  - `project_efsm()` runs nuscr's `--project` + CFSM/`--fsm`, parses its output
    into the **same** `EFSM`/`Transition` dataclasses `efsm_parser.py` produces.
    Add `stjp_core/compiler/nuscr_fsm_parser.py` if the DOT dialect differs.
- Backend selector in `config.py`: `STJP_COMPILER_BACKEND = scribble | nuscr`
  (default `scribble`). A factory `get_compiler()` returns the right instance.
- **Space-in-path guard** must be preserved (repo sits under
  `OneDrive - Microsoft`): pass files by a space-free relative/WSL path exactly
  as `validator.py` does today.

### Phase 1.4 — Prove parity + the coinductive win

- **Parity:** for all non-recursive cases, `nuscr` and `scribble-java` agree on
  valid/invalid and produce EFSMs that drive the monitor to identical verdicts.
  Add `stjp_core/tests/test_nuscr_backend.py` (script-style `__main__`, prints
  `ALL PASS`, matching repo test convention — no pytest).
- **The win:** pick a recursive case (`retry_loop` / `iterative_polling`) whose
  loop currently needs flattening; show stock projection rejects the honest
  recursive `.scr` while the coinductive fork projects it. This is the concrete
  "new Scribble buys us something" result → short section in
  [docs/reference/SCRIBBLE_EXTENSIONS.md](SCRIBBLE_EXTENSIONS.md) §5 status matrix.

### Phase 1.5 — Connect the backend switch through the harness (thin)

- `case_runner.py` / compaction / gate read the compiler via `get_compiler()`
  so a single env var flips the whole pipeline. No arm changes required.

---

## Part 2 — "Unsafe skills" demo (real skills → deadlock/disaster → revised → safe + cheaper)

### Phase 2.1 — Select real, non-malicious skills

- Pull agent skill/prompt sets from **public, permissively-licensed** repos —
  coordination-heavy, multi-agent. Candidate shortlist (confirm in D4):
  - Escrow (a neutral third party that holds funds until both sides deliver) /
    marketplace buyer↔seller↔carrier flows.
  - "Approve-then-file" / "review-then-publish" agent pairs (order-sensitive).
  - Booking/saga flows (reserve → pay → confirm, with compensation).
  - Multi-agent code-review or RAG pipelines (fetch → analyse → report).
- **Safety review each source** before import: no exfiltration/jailbreak/malware
  content; skills must be benign coordination logic only. Record provenance
  (repo, commit, license) in each case's `SOURCES.md`.
- Land each imported skill set verbatim under
  `experiments/cases/skills_safety/<name>/skills_original/<Role>.md`.

### Phase 2.2 — Show they are unsafe (bottom-up, via the compiler)

- Run the existing bottom-up pipeline on each imported set:
  `python -m stjp_core.generation.skill_compactor <skills_dir> -o <Proto>.nuscr
  --protocol <Proto>` (compact → local types → synthesise global → **compiler
  validates**).
- Expected failure classes to demonstrate (at least one each):
  - **Deadlock / circular wait** — synthesis stuck, per-role "waiting for X from
    Y" (the trade_deadlock shape, but from real skills).
  - **Wrong-order / safety** — B happens before A (e.g. file-before-approve,
    ship-before-pay, publish-before-review) → the disaster branch.
- Capture each verdict as the "before" evidence (rejected protocol + the exact
  circular-wait / ordering diagnosis).

### Phase 2.3 — Author revised skills that validate

- Produce `skills_revised/<Role>.md` per case: minimal edits that add the
  missing coordinating message or fix the ordering (e.g. add an
  approval/notification step to both branches so every role learns the decision
  before acting). This mirrors how the valid finance draft fixes the unsafe one.
- Re-run compaction → the composed global type now **passes** the compiler.
  Project per-role local types + refinement guards as usual.

### Phase 2.4 — Run the A/B trials with a cheap LLM

- Harness: reuse the subagent-driven trial pattern from
  [docs/results/RESULT_5_SUBAGENT_VALIDATION.md](../results/RESULT_5_SUBAGENT_VALIDATION.md)
  (unchecked prose skills vs STJP). Per D3, drive each role with a **cheap Azure
  model (gpt-4o-mini class)** deployed as a **hosted agent** (§2.4b) so the trials
  are Foundry-visible.

### Phase 2.4b — Hosted agents so traces show in Foundry

Run the demo's per-role agents as **`azd` hosted agents** (Azure Developer CLI
Agent Framework) so every message/turn is visible in the Foundry portal under
Agents → Threads → Tracing — the same three surfaces documented in
[docs/reference/FOUNDRY_VISIBILITY.md](FOUNDRY_VISIBILITY.md).

One-time scaffold + deploy:

```bash
azd ext install azure.ai.agents
azd extension upgrade azure.ai.agents

azd auth login --client-id "<client id>" \
               --client-secret "<client secret>" \
               --tenant-id "<tenant id>"

azd ai agent init      # select "Agent Framework" + the MCP tools in the dialogue
```

`azd ai agent init` creates a **kickstarter template** we then adapt for the
demo roles (one hosted agent per protocol role; cheap gpt-4o-mini-class
deployment). Iterate with:

```bash
azd deploy                                  # push updated agent code
azd ai agent run                            # start the runtime locally
azd ai agent invoke --local "<role task>"   # drive one turn / smoke test
```

Wiring notes:
- Map each protocol role (Buyer, Seller, Auditor, …) to one hosted agent in the
  template's `config.json`; per-role system prompt = the projected local type +
  refinement guards (same builders as the 8-arm matrix).
- Keep the STJP **monitor/gate** outside the hosted agents (it walks the traces
  and accepts/blocks), consistent with today's `foundry_runner.py` split.
- Ensure tracing is on (`enable_foundry_tracing()` / the template's App Insights
  connection) so the Tracing tab is populated, not just Threads.
- Deliverable: both the **unsafe (original skills)** and **safe (revised,
  validated)** arms run through hosted agents, so the Foundry portal itself
  shows the deadlock/disaster in arm A and the clean run in arm B.
- Two arms per case, one variable changed (validation on/off):
  - **A (original skills, no validation):** expect deadlocks / disasters, high
    or infinite cost-to-goal, retries.
  - **B (revised skills, compiler-validated + monitor/gate):** expect completion,
    zero disasters, lower tokens/cost.
- Measure the standard metrics: GCR (goal-completion rate), disasters
  (severity levels S3/S4 — never-finished and irreversible-disaster
  outcomes), cost-to-goal (tokens), time-to-goal, monitor verdicts. Run n≥10
  (n≥100 if cheap enough) for a Wilson CI, consistent with the existing
  result docs.

### Phase 2.5 — Write it up

- New `docs/results/RESULT_8_SKILL_SAFETY.md` following the results template
  (at-a-glance → story → setup → numbers → meaning → caveats → raw data path).
- Index it in [docs/README.md](../README.md) and
  [docs/results/RESULTS.md](../results/RESULTS.md).
- Honest caveat to include: payload values are LLM output (no data source), and
  "cheaper" must be reported as tokens/cost-to-goal on the **cheap** model, not
  extrapolated to gpt-5.4.

---

## Risks / watch-items

- **nuscr Windows build (D2)** is the top risk — budget time for WSL/opam or
  Docker. If it stalls, Part 2 can proceed on `scribble-java` first and adopt
  nuscr for the recursive cases once the toolchain is green.
- **Syntax drift** between Scribble and nuscr — keep the adapter scoped to the
  subset the cases actually use; do not aim for a full translator.
- **Fork-specific output format** — the coinductive branch may print projections
  differently from mainline nuscr; lock the parser to the fork's actual output
  captured in Phase 1.1.
- **Skill provenance/licensing (D4)** — only permissive licenses; keep
  `SOURCES.md` per case; safety-review every imported skill.
- **"Cheaper" claim fairness** — one variable per comparison (validation on/off),
  same model, same prompts otherwise; report cost-to-goal, not raw tokens.

## Suggested order of execution

1. D1–D5 confirmed.
2. Phase 1.1 (build nuscr) — unblocks everything nuscr.
3. Phase 2.1–2.2 in parallel on `scribble-java` (does not need nuscr) —
   produces the "before" evidence early.
4. Phases 1.2–1.4 (adapter + backend + parity + coinductive win).
5. Phases 2.3–2.5 (revised skills, A/B trials on the cheap model, write-up).
