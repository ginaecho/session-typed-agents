# Diary

Newest entries first. Older entries are preserved verbatim from when they
were written — references to `finance_demo/` in older entries are stale
(folder renamed to `stjp_core/` on 2026-05-15) but not edited so the
history reads as it was.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [2026-07-06 — implementation log: nuscr backend + real-skills safety cases](#2026-07-06--implementation-log-nuscr-backend--real-skills-safety-cases)
  - [The two requested implementations (verbatim intent)](#the-two-requested-implementations-verbatim-intent)
  - [Deliverable 1 — nuscr coinductive backend](#deliverable-1--nuscr-coinductive-backend)
  - [Deliverable 2 — "unsafe skills" demo (before → after)](#deliverable-2--unsafe-skills-demo-before--after)
    - [Cases (real, non-malicious, permissively-licensed skills)](#cases-real-non-malicious-permissively-licensed-skills)
    - [Revised (validated) skills](#revised-validated-skills)
    - [Real run on the cheap model (gpt-4o)](#real-run-on-the-cheap-model-gpt-4o)
  - [Other additions today](#other-additions-today)
  - [Grouped hosted agents (Agent Framework workflow) — in progress](#grouped-hosted-agents-agent-framework-workflow--in-progress)
  - [Still pending](#still-pending)
- [2026-06-26 — dependency profile cleanup and README alignment](#2026-06-26--dependency-profile-cleanup-and-readme-alignment)
  - [1. Requirements split clarified and aligned](#1-requirements-split-clarified-and-aligned)
  - [2. README setup instructions updated](#2-readme-setup-instructions-updated)
  - [3. Local environment verification](#3-local-environment-verification)
- [2026-06-18 — token-efficiency demo (companion to the deadlock demo)](#2026-06-18--token-efficiency-demo-companion-to-the-deadlock-demo)
- [2026-06-17 (evening) — the deadlock demo (centerpiece)](#2026-06-17-evening--the-deadlock-demo-centerpiece)
- [2026-06-17 (afternoon)](#2026-06-17-afternoon)
  - [7-8 (later 2026-06-17) — drafting fix, v3 build, stability n=10](#7-8-later-2026-06-17--drafting-fix-v3-build-stability-n10)
- [2026-06-17](#2026-06-17)
  - [1. Drafting prompt v2 (reason-then-code)](#1-drafting-prompt-v2-reason-then-code)
  - [2. Criticality-aware tests (v3)](#2-criticality-aware-tests-v3)
  - [3. Simpler demo](#3-simpler-demo)
  - [4. Governance toolkit](#4-governance-toolkit)
  - [5. DeLM (arXiv 2606.10662)](#5-delm-arxiv-260610662)
  - [6. Docs location](#6-docs-location)
  - [Full session index (merged from SESSION_2026-06-17.md on 2026-07-03)](#full-session-index-merged-from-session_2026-06-17md-on-2026-07-03)
    - [1. Better LLM→Scribble drafting prompt (done + smoke-tested)](#1-better-llmscribble-drafting-prompt-done--smoke-tested)
    - [2. Criticality-aware test redesign (designed + gates implemented + smoke)](#2-criticality-aware-test-redesign-designed--gates-implemented--smoke)
    - [3. Simpler demo (done)](#3-simpler-demo-done)
    - [4. Microsoft Agent Governance Toolkit (assessed)](#4-microsoft-agent-governance-toolkit-assessed)
    - [5. DeLM paper (arXiv 2606.10662) reuse brainstorm](#5-delm-paper-arxiv-260610662-reuse-brainstorm)
    - [6. Today's docs (this set)](#6-todays-docs-this-set)
    - [Open threads (next session)](#open-threads-next-session)
- [2026-06-12 (covering 06-11 evening session)](#2026-06-12-covering-06-11-evening-session)
  - [1. Standalone benchmark demo (`pitch/STJP_Benchmark_Demo.html`)](#1-standalone-benchmark-demo-pitchstjp_benchmark_demohtml)
  - [2. Stale goals.yaml caught a 0%-scoring bug](#2-stale-goalsyaml-caught-a-0-scoring-bug)
  - [3. Live runs (real Azure AI Foundry / MAF agents)](#3-live-runs-real-azure-ai-foundry--maf-agents)
  - [4. Benchmark scoring v2.1 — consequence-graded violations](#4-benchmark-scoring-v21--consequence-graded-violations)
  - [5. Banking case live — S4 in dollars](#5-banking-case-live--s4-in-dollars)
  - [6. Evolution demo designed (not yet built)](#6-evolution-demo-designed-not-yet-built)
  - [7. docs/ cleanup](#7-docs-cleanup)
- [2026-06-08](#2026-06-08)
  - [1. New `.github/copilot-instructions.md`](#1-new-githubcopilot-instructionsmd)
  - [2. Verified: case-switching regenerates graphs (already fixed)](#2-verified-case-switching-regenerates-graphs-already-fixed)
  - [3. Proposal: an application-level "Scene" view for the demo](#3-proposal-an-application-level-scene-view-for-the-demo)
- [2026-06-01](#2026-06-01)
  - [What was broken and what was fixed](#what-was-broken-and-what-was-fixed)
    - [1. State-machine graph style: complex Scribble layout → simple topology](#1-state-machine-graph-style-complex-scribble-layout--simple-topology)
    - [2. Graphs missing for most scenarios on case switch](#2-graphs-missing-for-most-scenarios-on-case-switch)
    - [3. VALID/UNSAFE graphs not updating after drafting](#3-validunsafe-graphs-not-updating-after-drafting)
  - [Files modified](#files-modified)
  - [Verification](#verification)
  - [Drafting still blocked by Azure auth](#drafting-still-blocked-by-azure-auth)
  - [Open threads (pick up next session)](#open-threads-pick-up-next-session)
  - [Pointers](#pointers)
- [2026-05-21](#2026-05-21)
  - [The n=10 finance result — the headline](#the-n10-finance-result--the-headline)
  - [stjp_core restructured — 7 packages](#stjp_core-restructured--7-packages)
  - [Portability fixes — the repo moved under a spaced path](#portability-fixes--the-repo-moved-under-a-spaced-path)
  - [Evaluation wiring](#evaluation-wiring)
  - [dual_demo — now any 2 of the 8 arms](#dual_demo--now-any-2-of-the-8-arms)
  - [Three new benchmark cases](#three-new-benchmark-cases)
  - [Docs](#docs)
  - [Open threads (pick up next session)](#open-threads-pick-up-next-session-1)
  - [Pointers](#pointers-1)
- [2026-05-20](#2026-05-20)
  - [The blocker, and how it cleared](#the-blocker-and-how-it-cleared)
  - [What was built](#what-was-built)
    - [`experiments/scripts/run_subset.py` — arm-subset driver](#experimentsscriptsrun_subsetpy--arm-subset-driver)
  - [The n=2 finance run — arms: unsafe / llmvalid / spec_llmvalid](#the-n2-finance-run--arms-unsafe--llmvalid--spec_llmvalid)
    - [The monotonic story holds](#the-monotonic-story-holds)
  - [Caveats / things to check](#caveats--things-to-check)
  - [Open threads (pick up next session)](#open-threads-pick-up-next-session-2)
  - [Next session plan](#next-session-plan)
  - [Files added / modified today](#files-added--modified-today)
    - [Added](#added)
    - [Memory](#memory)
  - [Pointers](#pointers-2)
- [2026-05-18](#2026-05-18)
  - [The research question reshaped twice today](#the-research-question-reshaped-twice-today)
  - [Final 8-arm matrix (LLM + validator focus)](#final-8-arm-matrix-llm--validator-focus)
  - [What was built today](#what-was-built-today)
    - [experiments/baselines/ — multi-framework runner abstraction](#experimentsbaselines--multi-framework-runner-abstraction)
    - [experiments/scripts/ — the LLM+validator harnesses](#experimentsscripts--the-llmvalidator-harnesses)
    - [Per-arm projection/monitor/goals plumbing (Tier 1 + Tier 2)](#per-arm-projectionmonitorgoals-plumbing-tier-1--tier-2)
    - [Observational fallback for unprojectable protocols](#observational-fallback-for-unprojectable-protocols)
    - [Bugs found and fixed](#bugs-found-and-fixed)
    - [Wave-based execution (rate limit defense)](#wave-based-execution-rate-limit-defense)
    - [`--resume` mode](#--resume-mode)
  - [Key empirical findings (n=1, need n=10 confirmation)](#key-empirical-findings-n1-need-n10-confirmation)
    - [From the `code_review` 7-arm smoke (mid-session)](#from-the-code_review-7-arm-smoke-mid-session)
    - [From the `finance` 8-arm smoke (n=1, late session)](#from-the-finance-8-arm-smoke-n1-late-session)
  - [Drafter outcome on finance — the LLM+validator story, concretely](#drafter-outcome-on-finance--the-llmvalidator-story-concretely)
  - [n=10 finance smoke — interrupted by 429s, then by laptop concern](#n10-finance-smoke--interrupted-by-429s-then-by-laptop-concern)
  - [Files added / modified today](#files-added--modified-today-1)
    - [Added (new)](#added-new)
    - [Modified](#modified)
  - [Open threads (pick up next session)](#open-threads-pick-up-next-session-3)
  - [Next session plan](#next-session-plan-1)
  - [Pointers](#pointers-3)
  - [End-of-day wrap-up (added evening 2026-05-18)](#end-of-day-wrap-up-added-evening-2026-05-18)
- [2026-05-15](#2026-05-15)
  - [What we did](#what-we-did)
    - [1. Workspace reorganization (∼20 files touched)](#1-workspace-reorganization-∼20-files-touched)
    - [2. Logs cleanup](#2-logs-cleanup)
    - [3. Authored cases for shapes D / E / F (with Scribble validation)](#3-authored-cases-for-shapes-d--e--f-with-scribble-validation)
    - [4. Live mirror to `stjp_core/` for the HTML](#4-live-mirror-to-stjp_core-for-the-html)
    - [5. Token-cost tracking](#5-token-cost-tracking)
    - [6. Spec minimization experiment (key empirical pivot)](#6-spec-minimization-experiment-key-empirical-pivot)
    - [7. 3-arm + retry-to-success refactor (`case_runner.py`)](#7-3-arm--retry-to-success-refactor-case_runnerpy)
    - [8. Smoke validation (post-refactor, n=1, `code_review`)](#8-smoke-validation-post-refactor-n1-code_review)
  - [Key empirical findings (n=1, need n=100 confirmation)](#key-empirical-findings-n1-need-n100-confirmation)
  - [Files added / modified / deleted today](#files-added--modified--deleted-today)
    - [Added](#added-1)
    - [Modified](#modified-1)
    - [Deleted (33 files)](#deleted-33-files)
  - [Open threads (pick up next session)](#open-threads-pick-up-next-session-4)
  - [Next session plan](#next-session-plan-2)
  - [Pointers](#pointers-4)
  - [Risk register](#risk-register)
- [2026-05-13](#2026-05-13)
  - [What we tackled today](#what-we-tackled-today)
  - [What was built](#what-was-built-1)
    - [1. Gap closure — predicate compiled into the projected tool](#1-gap-closure--predicate-compiled-into-the-projected-tool)
    - [2. WITH vs WITHOUT benchmark infrastructure](#2-with-vs-without-benchmark-infrastructure)
    - [3. Smoke test (n=1) — passed](#3-smoke-test-n1--passed)
  - [Open thread (pick this up next session)](#open-thread-pick-this-up-next-session)
  - [Auth gotcha worth remembering](#auth-gotcha-worth-remembering)
  - [Files added or changed today](#files-added-or-changed-today)
  - [Pointers](#pointers-5)
<!-- MENU:END -->

# 2026-07-06 — implementation log: nuscr backend + real-skills safety cases

(Moved here from `docs/IMPLEMENTATION_2026-07-06.md` on 2026-07-08, per the
diary convention. **Update 2026-07-08:** the "still pending" items at the
bottom have since landed — the formal report is
[`../results/RESULT_8_SKILL_SAFETY.md`](../results/RESULT_8_SKILL_SAFETY.md),
confirmed at n=100 and extended to Anthropic/Copilot skills in
[`../results/RESULT_9_REAL_SKILLS_TWO_MODELS.md`](../results/RESULT_9_REAL_SKILLS_TWO_MODELS.md).)

What was implemented that day, the new additions, and how they map to the two
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
  [tools/nuscr/Dockerfile](../../tools/nuscr/Dockerfile) that adds the protobuf +
  pkg-config depexts the fork's own Dockerfile omits (its `opam install` fails
  without them). The vendored checkout stays a clean upstream copy.
- New compiler abstraction in `stjp_core/compiler/`:
  - [compiler_iface.py](../../stjp_core/compiler/compiler_iface.py) — a
    `ProtocolCompiler` interface + `get_compiler()` factory selecting the backend
    via `STJP_COMPILER_BACKEND` (`scribble` default, or `nuscr`), with a
    `ScribbleCompiler` adapter over the existing scribble-java path.
  - [nuscr_syntax.py](../../stjp_core/compiler/nuscr_syntax.py) — a small `.scr` →
    `.nuscr` adapter (strips the Scribble-only `module`/`data` preamble; remaps a
    few Java payload types).
  - [nuscr_compiler.py](../../stjp_core/compiler/nuscr_compiler.py) — a Docker-backed
    `NuscrCompiler`: `validate` (nuscr `check`), `project_efsm` (nuscr `--fsm`
    parsed into the same `EFSM` dataclass), `project_local_type` (with
    `inductive-full` / `coinductive-full` / `coinductive-plain` modes), and
    `roles_and_protocols` (nuscr `--enum`).
  - `efsm_parser.parse_nuscr_fsm_dot` — parses nuscr's DOT (unquoted node ids +
    trailing comma) into the shared `EFSM`.
- Tests: [tests/test_nuscr_backend.py](../../stjp_core/tests/test_nuscr_backend.py) —
  `ALL PASS`, including Docker-backed validate/project and **coinductive
  projection** of a recursive protocol.
- **Honest finding:** nuscr is deliberately *not* Scribble-compatible and
  supports only a fragment — e.g. the finance protocol is rejected ("Non
  tail-recursive protocol is not implemented"). So the harness default stays
  `scribble`; nuscr is opt-in and its distinct value is coinductive projection of
  recursive protocols that stock projection leaves as a bare `rec`.

Plan of record: [reference/NUSCR_AND_SKILL_SAFETY_PLAN.md](../reference/NUSCR_AND_SKILL_SAFETY_PLAN.md).

---

## Deliverable 2 — "unsafe skills" demo (before → after)

**Status: 5 cases built with before-evidence; revised skills validated; one real
Foundry run completed on the cheap model.**

### Cases (real, non-malicious, permissively-licensed skills)

| Case | Source (license) | Failure when NOT validated |
|---|---|---|
| `trade_deadlock` | escrow (a neutral third party that holds funds until both sides deliver) buyer/seller (existing) | deadlock — "Buyer would wait forever" |
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

Connected the cases into the 8-arm harness (`unchecked_skills` = original unsafe vs
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
  [.github/foundry-deployment.md](../../.github/foundry-deployment.md) (account
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
- Complete the remaining cheap-model runs (`airline_seat`, `content_pipeline`,
  `code_execution`, `booking_saga`) and write the formal
  `docs/results/RESULT_8_SKILL_SAFETY.md`.

---

# 2026-06-26 — dependency profile cleanup and README alignment

Focused on making dependency setup explicit by use case and security posture.

## 1. Requirements split clarified and aligned

Updated the dependency profile files under `stjp_core/` so install paths are
clearer:
- `requirements-secure.txt` is the security-clean baseline for compiler /
  validator / monitor workflows.
- `requirements-core.txt` contains the broader Foundry + Azure stack.
- `requirements-demo.txt` contains the optional Flask/ASGI live-demo layer.
- `requirements-full.txt` composes core + demo for development convenience.
- `requirements.txt` now points to the secure baseline by default.

## 2. README setup instructions updated

`stjp_core/README.md` now matches the split dependency model and documents:
- the recommended default install (`requirements.txt`) for security-passable
  setups,
- optional install commands for core Foundry features and the Flask demo,
- warnings that the demo path is experimental and may include known
  vulnerabilities via transitive dependencies.

## 3. Local environment verification

Validated the optional demo environment path by installing demo-related web
packages in the local `stjp_core/.venv` (including Flask stack components), to
confirm the documented install flow is executable.

---

# 2026-06-18 — token-efficiency demo (companion to the deadlock demo)

The deadlock demo proved STJP prevents catastrophic (infinite) waste but NOT that
it is token-efficient in the normal case (there unchecked and spec used the same
~24.8k tokens; the difference was 0% vs 100%). Built a fair efficiency case
`report_pipeline` (6-role strict linear pipeline; everyone completes 100%, so it
is purely about token cost). Ran bare (intent-only) vs spec vs min on the same
round-robin runner, gpt-5.4, n=6.

Result: ALL 100% complete; total tokens/trial bare 24.1k, spec 18.4k, **min 8.8k
(-63% vs bare)**. Mechanism (both halves shrink with a clear small contract):
deliberation/output tokens per call bare 1534 -> min 552 (-64%; the "agents keep
thinking how to proceed" waste), and prompt/input tokens bare 13.4k -> min 5.5k
(lean contract is a fraction of the prose/verbose-EFSM size). Doc:
TOKEN_EFFICIENCY_DEMO.md. The bigger lever (EFSM scheduler -83% calls vs polling
every idle agent) is shown in the delm_runner oracle smoke test (a quick
end-to-end check); connecting the real LLM into the scheduler is the
remaining online step.

---

# 2026-06-17 (evening) — the deadlock demo (centerpiece)

Pivoted after feedback that the multi-arm comparisons were muddy and not
convincing. Audited the design and found real issues: an over-strict free-text
goal predicate (agents completed the trade but scored "fail" for not saying a
magic word), too many entangled variables, and the deadlock thesis never actually
tested (all arms used the safe protocol).

Rebuilt around the actual thesis with ONE clean case `trade_deadlock`:
- Unchecked human-written per-agent skills (Buyer: pay-after-delivery; Seller:
  ship-after-payment) = a circular wait no human/LLM flags in isolation.
- Validated = Scribble rejects the cycle, forces escrow-first, projects to local
  types (spec + lean min).
New arm `unchecked_skills` (build_unchecked_skills_instructions reads
cases/<case>/unchecked_skills/<role>.md). Probe (deadlock_probe.py, 2 agents)
confirmed real gpt-5.4 agents deadlock on the unchecked skills.

Result (n=6, gpt-5.4): unchecked 0/6 settlement, **0 messages emitted** (pure
mutual-wait deadlock), 24.8k tokens/trial wasted, cost-of-success INF. spec 6/6
at 24.8k; min 6/6 at 12.0k (token-optimal). Scribble caught the deadlock at
design time, 0 runtime cost. Doc: DEADLOCK_DEMO.md (also defines violation /
forbidden-interaction semantics, and the deadlock-vs-violation distinction: a
monitor judging messages can't see a deadlock; only the static checker can).

---

# 2026-06-17 (afternoon)

## 7-8 (later 2026-06-17) — drafting fix, v3 build, stability n=10

**Drafting further improved** (DRAFTING_IMPROVEMENTS.md): diagnosed the real error
("Unfinished roles" — the model half-applies the choice fan-out, skipping roles
idle in a branch). Built a deterministic `fanout_normalizer.py` (insert-only,
minimal-target, provably leaves valid protocols unchanged) connected into
`ArchitectAgent(auto_fanout=True)`. A/B (gpt-5.4, fresh intent): first-pass
0/4 -> 3/4, fix-rounds 2.25 -> 0.25. SLM verdict: not yet (Scribble loop already
guarantees correctness; collect dataset, train only at volume).

**v3 roadmap — 4 steps built + verified offline** (STJP_V3_PLAN.md):
- step 1 `governance/policy_export.py`: STJP -> toolkit PolicyDocument (finance 30
  rules, banking 44; ordering + stateful choice-guard + refinement; default deny).
- step 2 `governance/audit_export.py`: verdicts -> toolkit audit entries with
  OWASP/NIST tags (intent 180 deny, gate 100 allow/5 deny on real traces).
- steps 4+5 `runtime/delm_runner.py` + smoke: DeLM-style runtime (DeLM =
  "Decentralized Language Models," an external fast controller-free
  multi-agent runtime; see §5 below), STJP monitor =
  write-verifier, EFSM enabled-set = claim predicate, type-directed views.
  -83% agent calls vs round-robin; deadlock-free both branches; enforce blocks /
  observe flags the value-wrong branch; order-jumping structurally impossible.

**Fresh n=10 stability run** (20260617T081755): reproduces the grand run. Headline
cost/time-to-goal (tokens|sec per delivered report): A inf (0%, 15 S4 disasters),
B 27k|59s (100%), C 332k|518s (50% — stalls), C-min 167k|491s (50%), C+ 79k|126s
(100%, 0 disasters). C's inflated cost-to-goal (stalls) is the measured motivation
for the v3 DeLM scheduler. Full table: RUN_REPORT_2026-06-17.md.

**Also**: corrected this session's docs mis-dated 2026-06-13 -> 2026-06-17
(today's real date, per run timestamps).

---

# 2026-06-17

Seven workstreams. Headlines below; the full session index (formerly the
separate `SESSION_2026-06-17.md`, merged here 2026-07-03) follows the headlines.

## 1. Drafting prompt v2 (reason-then-code)
`prompts.py` SCRIBBLE_SYSTEM_PROMPT_V2 + FIX_V2; `ArchitectAgent(use_v2_prompt=True)`
default, False reverts. A/B smoke (real gpt-5.4, fresh Incident-Response intent):
fix-rounds 2.33->1.00, eventual validity 2/3->3/3, ~23% faster. The lever was
(a) let the reasoning model plan first, (b) one canonical choice-notification
fan-out template that structurally kills the external-choice/wait-for-cycle pair.

## 2. Criticality-aware tests (v3)
The user's insight: protocol-following is only *provably* valuable on CRITICAL
dependencies (data-before-act / read-all-context / authorize-before-irreversible),
not universally. `BENCHMARK_DESIGN_V3_CRITICALITY.md`: three classes C1/C2/C3,
the two-variant fairness design (neutral vs critical so the benchmark can show
itself NOT helping when it shouldn't), CGC metric (Critical-Goal Completion —
goals AND all critical properties satisfied). Implemented
`criticality_gate.py` + `finance/protocols/criticality.yaml`; smoke on the grand
n=10 traces computes + discriminates, surfaced the coverage-proxy zero-value
limitation (documented). FROZE the prior design first in
`BENCHMARK_DESIGN_V2_FROZEN.md` for fallback (v3 is additive).

## 3. Simpler demo
`pitch/STJP_Simple_Demo.html` — light, lay-audience, single-narrative, interactive
toggle replay of real chaos-vs-gate traces. Dense demo kept + linked.

## 4. Governance toolkit
`GOVERNANCE_TOOLKIT_ASSESSMENT.md` — MS Agent Governance Toolkit Policy Engine is a
generic tool-call allow/deny gate with hand-written rules; STJP is a message-level
gate with auto-derived deadlock-free ordered rules. Reuse their audit/compliance
schema + identity; contribute STJP-as-policy-generator + ordering/stateful/
provenance conditions they lack.

## 5. DeLM (arXiv 2606.10662)
`RELATED_WORK_DELM.md` — NOT a threat (decentralized runtime, no formal checker;
"verified context" = self-verified). Complementary: STJP projection = principled
context split; STJP monitor = real verifier for DeLM's shared context; EFSM
enabled-set = deadlock-safe claim predicate. Borrow DeLM's async substrate for our
cost savings.

## 6. Docs location
All today's docs in docs/ per standing policy; README index updated.

## Full session index (merged from SESSION_2026-06-17.md on 2026-07-03)

### 1. Better LLM→Scribble drafting prompt (done + smoke-tested)
- **Why:** drafting looped (draft → Scribble rejects → re-draft); banking took 4
  fixes. Cause: the v1 prompt said "return ONLY code" (suppressing gpt-5.4's
  reasoning) and the dominant errors were the external-choice/wait-for-cycle pair.
- **What:** added `SCRIBBLE_SYSTEM_PROMPT_V2` / `SCRIBBLE_FIX_PROMPT_V2`
  (`stjp_core/authoring/prompts.py`) — reason-then-code + ONE canonical
  choice-notification fan-out template + a worked valid example.
  `ArchitectAgent(use_v2_prompt=True)` default; `False` falls back.
- **Result (A/B, real gpt-5.4):** fix-rounds 2.33 → **1.00**, eventual validity
  2/3 → **3/3**, ~23% faster. `RUN_REPORT_2026-06-17.md §1`.

### 2. Criticality-aware test redesign (designed + gates implemented + smoke)
- **Why:** v2's GCR (goal-completion rate) credits *order-following*; on gpt-5.4 the global-text arm
  hit 100% anyway, so a reviewer can call protocol overhead incidental. The user's
  insight: following a protocol is only *provably* valuable on **critical
  dependencies** (must get real data before acting; must read all context;
  must be authorized before an irreversible act).
- **What:** `BENCHMARK_DESIGN_V3_CRITICALITY.md` — three criticality classes
  (C1 provenance / C2 context-completeness / C3 authorization), the
  **two-variant** fairness design (neutral vs critical, so the benchmark can show
  its own method *not* helping when it shouldn't), and **CGC** (Critical-Goal
  Completion = goals AND all critical props). Implemented post-hoc gates in
  `experiments/scripts/criticality_gate.py` + `finance/protocols/criticality.yaml`.
- **Result:** gates compute and discriminate on the grand n=10 traces; surfaced
  the documented coverage-proxy limitation (noisy on zero values). The user's
  `len(context)` idea is included as the *weak* form; token-coverage is the
  primary, a semantic faithfulness judge the strong form. `RUN_REPORT_2026-06-17.md §2`.
- **Fallback:** `BENCHMARK_DESIGN_V2_FROZEN.md` snapshots the prior design so we
  can revert; v3 is purely additive.

### 3. Simpler demo (done)
- `pitch/STJP_Simple_Demo.html` — light, lay-audience, single-narrative: 5-step
  "how it works", an interactive **toggle replay** (real intent-only-chaos vs
  STJP-gate-clean traces from the grand run), three headline numbers. The dense
  `STJP_Benchmark_Demo.html` is unchanged and linked from it.

### 4. Microsoft Agent Governance Toolkit (assessed)
- `GOVERNANCE_TOOLKIT_ASSESSMENT.md` — their Policy Engine is a generic
  allow/deny gate at **tool-call** boundaries with **hand-written** field-op-value
  rules; STJP is a gate at **message** boundaries with **auto-derived, ordered,
  deadlock-free** rules. Complementary. **Reuse:** their audit/ExecutionContext
  schema (→ free OWASP/NIST/EU-AI-Act/SOC2 compliance packaging), fail-closed +
  conflict-resolution vocabulary, folder-hierarchy merge (for layered/org
  invariants), SPIFFE/DID identity (closes our role-spoofing gap). **Enhance:**
  STJP can emit projected contracts as their `PolicyDocument`s, and contributes
  ordering/liveness + stateful choice-guard + provenance conditions their
  stateless model lacks. Next: `stjp_core/governance/policy_export.py`.

### 5. DeLM paper (arXiv 2606.10662) reuse brainstorm
- `RELATED_WORK_DELM.md` — confirmed **not a threat**: DeLM is a decentralized
  *runtime substrate* with **no formal checker** ("verified context" = self-
  verified updates). Complementary. **Reuse:** STJP projection = principled
  type-directed context split; STJP monitor = the real "verifier" for DeLM's
  shared context; EFSM enabled-set = deadlock-safe task-claim predicate;
  provenance gate = write-admission rule. **Borrow back:** DeLM's async
  claim+shared-context as the path to our identified scheduling/cost savings.

### 6. Today's docs (this set)
`BENCHMARK_DESIGN_V2_FROZEN.md`, `BENCHMARK_DESIGN_V3_CRITICALITY.md`,
`GOVERNANCE_TOOLKIT_ASSESSMENT.md`, `RELATED_WORK_DELM.md`,
`RUN_REPORT_2026-06-17.md`, the session index (now this section); DIARY + README
index updated.

### Open threads (next session)
1. Author finance/banking **neutral vs critical variants** with planted
   provenance tokens; re-run the 5-arm matrix on both → the real v3 headline chart.
2. Semantic faithfulness judge for C2 (strong coverage).
3. Label-alignment for the criticality grader so intent-only arms get C1/C2 scores.
4. `policy_export.py` (STJP → governance PolicyDocument).
5. Prototype STJP-monitor-as-DeLM-verifier on a 2–3 role case.

---

# 2026-06-12 (covering 06-11 evening session)

Big session: live benchmark demo built, two real Foundry runs, the v2.1
consequence-graded scoring designed AND implemented, banking case brought live,
docs/ cleaned up.

## 1. Standalone benchmark demo (`pitch/STJP_Benchmark_Demo.html`)

New demo toolchain at `pitch/demo_build/` (`template.html` + `build_demo.py
<run_dir>[=label] ...`). Five sections: pipeline artifact explorer (intent →
global type → Scribble verdict incl. the rejected deadlocking draft → projected
local contract → goals → monitor), three-setting cards, live trace replay
(protocol graph + message sequence chart + goal ladder + token/time counters,
all driven by recorded events.jsonl), cross-arm scoreboard, benchmark-design
summary. Auto-detects per-run protocol vocabulary (v1 = 2026-05 labels,
v2 = current draft). The old `STJP Demo (standalone).html` is a packed bundle —
kept but no longer the thing to edit.

## 2. Stale goals.yaml caught a 0%-scoring bug

`llm_drafts/valid/goals.yaml` (finance) anchored G1/G2/G4/G5 on labels absent
from the current v1.scr (`HighRevenue`, `FinalizeReport`) and had dropped the
`branch:` tags — protocol-perfect runs scored 0% strict (20260601 run: 11/11
events accepted, succeeded=False). Re-anchored by hand; that run re-scores
100%. Lesson recorded: after regenerating a draft, verify goal anchor labels
exist in the protocol. The banking auto-re-anchor repeated the same two
mistakes the same day (payload predicate on a payloadless label, missing
branch tags) — this is systematic in `re_anchor_goals.py`, fix it there
eventually.

## 3. Live runs (real Azure AI Foundry / MAF agents)

(MAF = Microsoft Agent Framework; used throughout this diary for the
comparison-runtime arms.)

- `case_runner.py` gained `--arms a,b,c` (slice-assigns SCENARIOS).
- finance `runs/20260611T175113-n1-dual`: A intent-only 19/19 events
  off-protocol 0 goals; B global-text passed G1–G5 but never delivered (0%);
  C spec 0 violations 6/6 goals (attempt 2); C-min failed on a branch slip.
- Cost anatomy (`docs/RUN_REPORT_2026-06-11.md`): C's 63k tokens are NOT the
  contract (2.7–4.6k chars/role; min variant 1.0–2.0k — smaller than the bare
  prompt) but 54 calls × ~1.1k prompt-tok/call from WAIT-polling + a stalled
  attempt. Savings levers, in order: EFSM-driven scheduling, projected views,
  prompt caching, role-level retry — i.e. let the projection drive the runtime.

## 4. Benchmark scoring v2.1 — consequence-graded violations

Answering the "violation by definition" reviewer objection
(`docs/BENCHMARK_DESIGN.md` v2.1 addendum): align labels semantically first,
then grade each deviation S0 benign / S1 waste / S2 skipped obligation /
S3 never-terminated / S4 unauthorized irreversible act, against a per-case
partial order + irreversibility annotations (`protocols/severity.yaml`).
Implemented post-hoc in `experiments/scripts/severity_grader.py` — old runs
re-scored without reruns. Finance n=10 re-scored: A's 184 raw violations →
134 benign + 4 real disasters ("report before approval"); C is NOT spotless
(2 disasters from choosing the standard branch on high trials — local types
constrain paths, not choices; the choice needs the refinement guard).
Validation: P(goal-fail | S2+/S4) = 100% in every arm of every run.

## 5. Banking case live — S4 in dollars

Protocols LLM-drafted live (Scribble rejected 4 unsafe drafts, accepted the
5th; `drafts_log.json`), goals re-anchored + hand-fixed, severity.yaml added,
run `runs/20260611T183251-n2-dual` (n=2, 4 arms): typed arms 100% first
attempt (C-min matched C at 37% fewer tokens); intent-only **debited before
authorization twice** (the S4 headline); typed arm's 8 raw monitor violations
collapsed to 1 harmless S2 (skipped Notify) — the letter-vs-consequence gap
demonstrated on our own arm. Full numbers in RUN_REPORT Part 2.

## 6. Evolution demo designed (not yet built)

`docs/EVOLUTION_DEMO_DESIGN.md`: "the demand changed on Tuesday" act —
banking + new ComplianceScreen role; intent-only absorbs the change
statistically (disaster / half-landing — the new obligation fired on some but
not all triggering branches — / regression metrics), STJP absorbs it as a
re-validated diff with provable blast radius (unchanged contracts hash-equal).
Build plan needs only ordered-pair goal predicates, the severity grader
(done), and a banking v2 protocol dir.

## 7. docs/ cleanup

Superseded docs moved to `docs/archive/` (v1 design, legacy RESULTS, skills
compiler proposal, application-scene proposal, 13-May discussion record);
`docs/README.md` index added. GAP_CLOSED kept (cited by three live files).

---

# 2026-06-08

Tooling + onboarding session. Created the Copilot onboarding file, learned the
codebase from `.claude/` + `docs/`, verified a demo behaviour, and drafted a
proposal for a more concrete demo view.

## 1. New `.github/copilot-instructions.md`

Authored a first-class onboarding doc for future Copilot/agent sessions at
`.github/copilot-instructions.md` (none existed before). It captures what can't
be learned from a single file:

- **Repo shape** — `stjp_core/` (library), `experiments/` (8-arm benchmark),
  `scribble-java/` (vendored stock compiler), `docs/` + root `*.md` (design).
  Flagged that the **root `README.md` describes an older aspirational layout**
  (`tools/`, `stjp/`, `examples/`, `vendor/`) that does **not** match disk —
  trust the actual tree and the two subdir `CLAUDE.md` policy files.
- **Setup/env** — Python 3.13, shared `stjp_core/.venv`, single
  `requirements.txt`, Java 17, `az login`, the `.env` keys, and the
  `asyncio`-backport-must-not-be-installed gotcha.
- **Build/test/run** — there is **no pytest/lint/build installed**; tests are
  plain scripts with `__main__` guards (e.g.
  `python stjp_core\tests\test_change_request.py`); plus the benchmark and app
  commands.
- **Architecture** — the NL→Scribble→project→generate→monitor→evaluate pipeline,
  LLM-in-the-cold-path, Set A vs. Set B (+ the `protocol_unprojectable`
  "not a success signal" trap).
- **The layering model** — `scribble-java/` is stock upstream and **must never
  be forked/edited**; `.refn` sidecar, `// @use` composition, native delegation.
- **Conventions** — `from stjp_core.<package>...` imports, Foundry-first LLM
  routing, library-only data layout under `experiments/cases/<case>/`, stale
  skills files, the Scribble-rejects-paths-with-spaces constraint (repo sits
  under `OneDrive - Microsoft`), Windows Azure auth.
- **Docs map** with a caveat that **`ROADMAP.md` Phase-2 status is aspirational**
  (`smt.py`/`subtype.py`/`cli.py` don't exist) — trust the status matrix in
  `docs/SCRIBBLE_EXTENSIONS.md` §5.
- Recorded that the **live demo default is the Flask UI** at
  `experiments/apps/live_demo/app.py` (→ `http://127.0.0.1:5005/`); the old
  `stjp_core/apps/stjp_dual_demo.py` dual demo is legacy.

(The `.claude/settings.local.json` held only bash command permissions — no
conventions worth encoding. No MCP servers configured; none judged relevant.)

## 2. Verified: case-switching regenerates graphs (already fixed)

Question raised: when a user picks a different case, do the state-machine graph,
the message-sequence graph, and the Scribble protocol all regenerate per
scenario (and pre-render)? **Confirmed yes** in
`experiments/apps/live_demo/static/app.js`:

- `selectCase()` (line ~88) resets state, **wipes the previous case's protocol
  panes and SVGs** (line ~110), fetches that case's canonical `v1.scr` (+ any
  pre-saved valid/unsafe LLM drafts), then `loadProtocolSources()` →
  `parseScribble` on all three → `renderProtoCards()` paints **both** the
  state-machine and message-sequence graphs.
- The **canonical** graphs render immediately on selection with **no LLM call**
  (parsed client-side from the on-disk `.scr`); the comment at line ~114 records
  the earlier fix for the ~10 cases without pre-saved drafts. Matches the
  2026-06-01 entry below.
- **Caveat:** the *LLM-drafted* valid/unsafe graphs only pre-render if drafts
  already exist on disk; otherwise the panel shows "(no draft yet)" until the
  Draft step runs. The canonical graph always renders.

## 3. Proposal: an application-level "Scene" view for the demo

Feedback that the demo is **too theoretical** (state machines, EFSMs, Scribble)
for a non-expert audience — inspired by ZipperGen/ZipperChat
(`zippergen.io`, `github.com/zippergen-io/zippergen`), whose *examples* read well
because they're concrete (user emails a team → agent checks a calendar → agent
replies). The ask is explicitly the **concrete application scenario**, NOT the
MSC formalism.

Wrote the design (no code yet) at
**`docs/APPLICATION_SCENE_VIEW_PROPOSAL.md`**. In short: add a third per-case
**Scene** tab that re-skins the *same* run as a real-world story — avatars +
plain-language cards ("📅 The Assistant checked the team calendar") driven by the
**existing** `events_<arm>.jsonl` SSE stream (no backend change), with
click-through detail (payload, refinement verdict, system prompt) and a
human-step context+form dialog. Concreteness comes from a tiny per-case
`scene.yaml` sidecar mapping `(sender, receiver, label)` → icon + sentence, with
a generic fallback so cases without one still render. Proposes a flagship
everyday `scheduling` case (email → calendar → reply) and a 3-phase rollout.

**Next:** answer the 5 open questions in the proposal (flagship domain;
explicit `scene.yaml` vs. auto-derive; whether the human form feeds back into the
run; replace-vs-add the formal views; icon-cards vs. richer skeuomorphic scene),
then turn it into an implementation plan and build Phase 1.

---

# 2026-06-01

Short UI session. The live demo's graph rendering was broken in three
distinct ways; all three are now fixed. The state-machine and
message-sequence views in `experiments/apps/live_demo/` are fully dynamic
across all 13 benchmark cases.

## What was broken and what was fixed

### 1. State-machine graph style: complex Scribble layout → simple topology

The user wanted the state-machine graphs to match the reference image
(`state_machine_graph.png`): roles arranged in a circle, dashed edges for
each role-pair in the protocol. The existing renderer (`buildMachineLayout`
/ `drawMachine`) drew a detailed Scribble EFSM with numbered states,
branch clusters, merge nodes, and edge labels — visually overwhelming and
fragile on protocols with nested choices, `rec` blocks, or sub-protocol
calls.

**Fix:** Both rendering sites now delegate to `drawInteractionsGraph`,
the robust topology renderer that was already used for the "live
interactions" view:

- `renderMachineSingle` (stage-2 proto cards: VALID / UNSAFE / CANONICAL)
- `renderMachine` (per-arm "state machine" tab: EXPECTED + ACTUAL panes)

The topology renderer only needs roles + message pairs, which
`parseScribble` always produces. Every case draws correctly, including
those with nested choices (`banking`, `finance_nested`) and recursion
(`rag`, `retry_loop`, `iterative_polling`, `nested_retry`).

### 2. Graphs missing for most scenarios on case switch

**Root cause:** stage 2 ("Drafted protocols + canonical reference") is
`collapsed` by default and was only opened when a saved LLM draft loaded
via `selectCase`. Only 3 of 13 cases (`banking`, `finance`, `rag`) had
saved drafts under `protocols/llm_drafts/`. The other 10 cases left
stage 2 collapsed — the canonical state-machine and message-sequence
graphs were present in the DOM but invisible.

**Diagnosis method:** ran a standalone Node.js parser test against all 13
canonical `.scr` files — all parsed correctly (roles + messages present).
Then checked `protocols/llm_drafts/` on disk: only 3 cases had the
directory. This confirmed the parser was fine; the issue was CSS
visibility.

**Fix:** `selectCase` now calls `openStage("stage-drafts")` unconditionally,
so the canonical graphs render immediately on every case pick regardless
of whether LLM drafts exist.

### 3. VALID/UNSAFE graphs not updating after drafting

**Root cause:** `renderKept` (called when the draft SSE stream emits
`phase: "done"`) updated the text panes (`#valid-pre`, `#unsafe-pre`) and
`state.draftKept`, but never re-parsed the draft text into
`state.parsedProtocols` or called `renderProtoCards`. The VALID/UNSAFE
cards stayed at "(protocol unavailable)" even after a successful draft.

**Fix:** `renderKept` now:

1. Parses each kept draft via `parseScribble` into `state.parsedProtocols`
2. Calls `renderProtoCards()` to re-render all three proto cards
3. Refreshes the per-arm "state machine" view if it's currently active

This makes the full rendering pipeline dynamic: select a case → canonical
renders; draft completes → VALID/UNSAFE render; switch cases → everything
clears and re-renders for the new case.

## Files modified

| File | Changes |
|------|---------|
| `experiments/apps/live_demo/static/app.js` | `renderMachineSingle`: replaced `buildMachineLayout` + `drawMachine` with `drawInteractionsGraph` |
| | `renderMachine`: replaced layout+overlay pass with two `drawInteractionsGraph` calls (expected = no arm overlay, actual = arm's live trace) |
| | `selectCase`: added unconditional `openStage("stage-drafts")` |
| | `renderKept`: added `parseScribble` for valid/unsafe drafts, `renderProtoCards()` call, and active-arm machine-view refresh |

## Verification

Ran a standalone parser test (Node.js) against all 13 canonical protocols:

```text
auction              roles=4  msgs=9   branches=0
banking              roles=5  msgs=24  branches=4
clinical_enrollment  roles=5  msgs=9   branches=0
code_review          roles=5  msgs=7   branches=0
finance              roles=6  msgs=14  branches=2
finance_nested       roles=5  msgs=28  branches=4
intel_report         roles=6  msgs=10  branches=0
iterative_polling    roles=3  msgs=10  branches=2
nested_retry         roles=4  msgs=24  branches=4
rag                  roles=6  msgs=13  branches=3
retry_loop           roles=3  msgs=11  branches=2
travel               roles=6  msgs=18  branches=2
travel_saga          roles=5  msgs=9   branches=0
```

All 13 produce non-empty roles and messages. No JS errors in the edited
file.

## Drafting still blocked by Azure auth

Draft attempts during this session failed with `Tenant provided in token
does not match resource tenant`. The Foundry endpoint requires the
Microsoft tenant (`16b3c013-...`). Run `az login --tenant
16b3c013-d300-468d-ac64-7eda0820b6d3` before drafting. See 2026-05-13
entry for the auth gotcha.

## Open threads (pick up next session)

1. **Fix `az login` to Microsoft tenant** so Draft & Verify works for
   all cases. The VALID/UNSAFE graphs are connected and will render the
   moment a draft succeeds.
2. **n=10 runs on banking / travel / rag.** These cases have canonical
   protocols but still need `draft_llm_protocols.py` + `re_anchor_goals.py`
   before the 8-arm matrix can run.
3. **The old complex state-machine code** (`buildMachineLayout`,
   `drawMachine`, `computeOverlay`, `SM_DIMS`, `SM_DIMS_COMPACT`) is now
   dead code in `app.js`. Can be removed in a cleanup pass if the simple
   topology graph is confirmed as the permanent style.
4. **Per-arm "live interactions" and "state machine" tabs now show the same
   graph type.** Consider whether to merge them into one tab, or
   differentiate (e.g. "state machine" could show a different layout, or
   the interactions view could add the local-types panel while the machine
   view stays graph-only).

## Pointers

- Reference image for the simple topology style: `state_machine_graph.png`
  (repo root)
- Live demo: `python experiments/apps/live_demo/app.py` → `http://127.0.0.1:5005/`
- The topology renderer: `drawInteractionsGraph` in `app.js` (line ~1200)
- The parser: `parseScribble` in `app.js` (line ~990)
- Previous diary entry (2026-05-21): n=10 finance result, stjp_core
  7-package restructure

---

# 2026-05-21

A very large session (began 2026-05-20 evening, the n=10 result landed
2026-05-21). Two headlines: **`stjp_core/` was restructured into a 7-package
layout**, and the **n=10 finance run confirmed the monotonic ladder** the
project predicts.

## The n=10 finance result — the headline

8-arm matrix, 10 trials each. Run dir
`cases/finance/runs/20260521T111637-n10-dual/`.

```
arm                       Set B success   Set A (viol/events)   tokens/trial
─────────────────────────────────────────────────────────────────────────────
bare                            0%            378 / 378            118K
maf_native                      0%            458 / 458             39K
maf_foundry                     0%            478 / 478             43K
maf_groupchat                   0%            184 / 184             15K
maf_groupchat_unsafe           10%              0 / 155 (obs.)       34K
maf_groupchat_llmvalid         40%             63 / 157             35K
spec_llmvalid                  80%              0 / 106             34K
min_llmvalid                   60%             23 / 143             28K
```

The **monotonic ladder** holds at n=10: no protocol → 0%; validator-rejected
global type → 10%; validator-accepted global type (text only) → 40%;
projected per-role local type + monitor → 60–80%. Validation earns the first
step, projection earns the second.

Two findings: **`spec_llmvalid` is strongest — 80% and 0 monitor violations**
(perfect conformance whenever it ran). `min_llmvalid` 60% with 23 violations —
the terser SEND/RECV projection lets a little more drift through (at n=1 both
were 100%; n=10 separates them). And bare burns **118K tokens/trial** wandering
off-protocol vs ~28–34K for the projected arms (63–87% cheaper).

> Caveat: `success_rate_pct` (summary.json, single-attempt all-goals) and
> `evaluate_run`'s `strict_pct` (per-goal OR'd across attempts) differ slightly
> — e.g. unsafe 10% vs 20%. Both are Set-B-strict; the latter is more lenient.

## stjp_core restructured — 7 packages

The previously-flat ~36 modules now live in: `compiler/` (Scribble layer),
`authoring/` (LLM intent → protocol), `generation/` (skill/agent markdown),
`monitor/` (the local typed monitor), `evaluation/` (goals + run summary),
`foundry/` (Azure/Foundry layer), `apps/` (runnable entry points), `tests/`.
`config.py` stays at the top. Imports are now
`from stjp_core.<package>.<module> import …`.

Done via a one-shot `_migrate.py` (since deleted): created the packages, moved
35 modules, rewrote **116 imports across 39 files** (stjp_core + experiments),
repointed experiments' `sys.path` from `STJP_CORE` to `TESTING_IDEAS`, added a
repo-root bootstrap to `apps/` + `tests/`. Verified: compileall, all 7
packages import, Scribble validate+project, `--summarize-only`, and a live
n=1 smoke test.

Two restructure-induced path bugs found + fixed: `apps/stjp_serve.py` and
`apps/stjp_dual_demo.py` wrote/served from `apps/` instead of `stjp_core/`
after the move (`Path(__file__).parent` shifted) — repointed at `stjp_core/`.

## Portability fixes — the repo moved under a spaced path

The repo now sits under `OneDrive - Microsoft/…` (a space in the path), and it
was relocated from `Documents/05_Research/SessionTypes/…`. Three stale-path
bugs fixed: `config.py` (`SCRIBBLE_PATH` now relative to the repo, `JAVA_HOME`
from the environment); `_smoke_all.sh` and `.claude/settings.local.json`
(repointed). **Scribble's CLI rejects a `.scr` path containing a space**
("Bad module arg") — `validator.py` / `efsm_parser.py` now pass the module
path *relative* to Scribble's working dir so the space never reaches it.
`requirements.txt` added (frozen from the venv; the broken `asyncio==4.0.0`
PyPI entry is commented out).

## Evaluation wiring

`EXPERIMENT_DESIGN_v2.md` reconciled to the **two-set framing**: Set A
(global-type conformance, the monitor) + Set B (goal achievement) + process
cost. `case_runner.py` now runs `evaluate_run.evaluate` at the **end of every
run** (strict + role-pair always; `--semantic` adds the LLM judge) — Set B is
no longer a separate manual step. **Branch-conditional goals**: a `case.yaml`
goal may carry `branch: <hint>`; off-branch it is vacuously satisfied instead
of failing for a missing anchor (`goal_elicitor.verify_goals_against_trace` +
`evaluate_run` verifiers are branch-aware; finance G1/G2 tagged `branch:
high`). Fixed a pre-existing `summarize_run` `KeyError` crash on subset runs.

## dual_demo — now any 2 of the 8 arms

`stjp_dual_demo.py` rewritten as a thin driver over the real `baselines`
machinery: `stjp_dual_demo.py <armA> <armB> [case] [n]` runs the 2 chosen
arms, mirrors them to `events_left/right.jsonl` + writes `dual_meta.json`.
`case_runner` got a configurable `DUAL_MIRROR` (replaced hardcoded
`LIVE_MIRROR_KEYS`). `stjp_comparison.html` reads the left/right files +
`dual_meta.json` for dynamic panel labels (fallback to WITHOUT/WITH).

## Three new benchmark cases

`banking` (amount-dependent choice + reject path), `travel` (transactional
all-or-nothing rollback), `rag` (bounded verification-loop recursion) — the
three tasks designed in `EXPERIMENT_DESIGN_v2.md` §4. Each has `case.yaml` +
`protocols/v1.scr` (**all Scribble-valid** — authored deadlock-free, every
role in every branch) + `v1.refn`. Verified: `Case.load` + projection of every
role + goals all succeed. The four WITH-llmvalid arms still need
`draft_llm_protocols.py` + `re_anchor_goals.py` per case.

## Docs

- **New:** `docs/SCRIBBLE_EXTENSIONS.md` — how Scribble is extended
  (refinements via `.refn`, composition via `// @use`, higher-order native);
  Scribble itself is unmodified — everything is layered.
- **Rewritten:** `stjp_core/README.md`, `stjp_core/CLAUDE.md` (package layout);
  `experiments/README.md`, `experiments/baselines/README.md` (the 8-arm matrix
  — they documented the old 5-arm / 2-arm setup).
- **Fixed:** `index_builder.py` was broken against the 8-arm `summary.json`
  (read `summary["without"]`/`["with"]` — `KeyError`); rewritten for the
  `scenarios` schema; `INDEX.html` regenerated.

## Open threads (pick up next session)

1. **n=10 on banking / travel / rag.** They're scaffolded; run
   `draft_llm_protocols.py <case>` + `re_anchor_goals.py <case> valid|unsafe`
   per case (~5–10 min each, Azure), then `case_runner.py <case> 10`.
2. **spec_llmvalid (80%) vs min_llmvalid (60%).** Spec is now ahead with 0
   violations; min let 23 through. Investigate whether the minimal SEND/RECV
   format is worth its cost saving, or whether spec should be the default.
3. **n=10 finance with `--semantic`** — the third (LLM-judged) Set B lens, for
   the full three-metric table. ~400 LLM calls; cached.
4. **`ROADMAP.md` Phase-2 overclaims** — it marks subtyping / Z3 discharge as
   shipped, but `smt.py`/`subtype.py` don't exist. Correct the status.
5. **`.claude/settings.local.json`** — the 5 entries are stale one-off command
   strings; paths fixed but they're near-useless as allow-rules.

## Pointers

- n=10 result table: top of this entry; `runs/20260521T111637-n10-dual/`.
- **Full result write-up** (8-arm setup, Set A/B definitions, concrete
  error/success examples from the traces): `docs/RESULTS_finance_n10.md`.
- Package layout + what each does: `stjp_core/README.md`.
- Evaluation framework: `docs/EXPERIMENT_DESIGN_v2.md`.
- The 8-arm matrix: `experiments/baselines/README.md`.
- Scribble extension mechanism: `docs/SCRIBBLE_EXTENSIONS.md`.
- dual demo: `python stjp_core/apps/stjp_dual_demo.py <armA> <armB> [case] [n]`
  then `stjp_serve.py` → `stjp_comparison.html?live=1`.

---

# 2026-05-20

Short, focused session. One blocker cleared, one clean result, one new
tool. The headline: **the MAF arms are unblocked** — the 400 error that
killed every MAF arm on 2026-05-18 did not recur, and an n=2 finance run
produced the monotonic result the experiment predicts.

## The blocker, and how it cleared

The 2026-05-18 evening run left all 5 MAF arms dead: every trial failed
with a truncated `ChatClientException: Error code: 400` from
`OpenAIChatCompletionClient` (0 events, 0 tokens). The diary's open
issue #2 guessed "oversized prompt or MAF SDK regression" and flagged
that the full error body had been truncated by line-based log capture.

This session: the user ran `az login` between sessions. Today's run
went through cleanly **with zero code changes** — all MAF arms produced
real traces. `az account show` confirms the session is on the correct
Microsoft tenant (`16b3c013-...`, `tzuchunchen@microsoft.com`).

Conclusion: the 400 was almost certainly **environmental — a stale /
wrong-tenant `az` CLI token**, not a prompt-size or SDK problem.
`OpenAIChatCompletionClient` authenticates via `AzCliCredential`, so a
stale CLI session breaks it; MAF surfaces the AAD failure as an opaque
400. **Caveat: the May-18 error body was never captured, so this is the
leading hypothesis, not a proven root cause.** Either way the fix is
cheap and is now recorded in memory [[maf-sdk-gotchas]] (gotcha #4):
before diagnosing a MAF 400, run `az account show`; if it is not the
Microsoft tenant, `az login --tenant 16b3c013-d300-468d-ac64-7eda0820b6d3`
and re-run.

## What was built

### `experiments/scripts/run_subset.py` — arm-subset driver

`case_runner.py` only runs the full 8-arm `SCENARIOS` matrix; there was
no way to re-run just a few arms. `run_subset.py` fills that gap:

```
python experiments/scripts/run_subset.py <case_id> <n> <arm_key> [<arm_key> ...]
```

It filters the shared `SCENARIOS` list in place (so `registry.make_runner`,
`case_runner`, and the summary code all observe the subset), then
delegates to `case_runner.run_case`. The wave logic, `summary.json`, and
`print_summary` all cover only the selected arms. Reusable for any
future targeted re-run.

## The n=2 finance run — arms: unsafe / llmvalid / spec_llmvalid

Ran `maf_groupchat_unsafe`, `maf_groupchat_llmvalid`, `spec_llmvalid` at
n=2. Run dir `cases/finance/runs/20260520T115634-n2-dual/`; log
`experiments/logs/finance_subset_n2.log`.

```
metric                    maf-gc-unsafe   maf-gc-llmvalid   spec-llmvalid
─────────────────────────────────────────────────────────────────────────
success rate                     0% (0/2)        50% (1/2)      100% (2/2)
avg attempts (all)                  3.00             3.00            1.50
avg seconds/trial                     94              103             184
avg tokens/trial (cum)            35,830           43,130          36,177
avg calls/trial                     30.0             31.5            36.0
total events                          32               42              22
total violations                       0*              13               3**
```

\* observational mode — Scribble refused projection ("Safety violation
at session state 89"), so there is no monitor to emit verdicts.
\*\* all 3 from trial 1 / attempt 1; attempt 2 was a clean 8/8 → trial passed.

### The monotonic story holds

The three arms land exactly where the research claim predicts — each
pipeline stage earns a measurable step:

- **`spec_llmvalid` — 100%.** Validated protocol, *projected* per role +
  monitored. Both trials hit 6/6 goals on clean 8-step traces.
- **`maf_groupchat_llmvalid` — 50%.** Same validated protocol, *global
  text only, no projection*. Trial 1 limped to 6/6 on attempt 3; trial 2
  failed all 3 attempts. The 13 violations are the predicted drift:
  `Writer → Writer` self-loops, `TaxVerifier → TaxVerifier`,
  `RevenueAnalyst → ExpenseAnalyst` (`unexpected_peer`). Projection is
  what stops the drift.
- **`maf_groupchat_unsafe` — 0%.** Scribble-rejected protocol. Never
  closes — best trial reached 4/6 goals, with the same self-loop drift.

So: not-validated 0% → validated-but-not-projected 50% →
validated+projected 100%. Validation earns the first step, projection
earns the second.

## Caveats / things to check

1. **n=2 is tiny.** The 50% for `maf_groupchat_llmvalid` is literally
   1/2 — pure variance until n≥5-10 (still Bug 1.5 from the 2026-05-18
   entry). The n=2 numbers are a *preview*, not a result.
2. **`spec_llmvalid` trial-1 / attempt-1 quirk.** That attempt took the
   *standard* branch and the monitor flagged `Approval` / `FinalizeReport`
   / `GenerateReport` as `off_protocol` (steps 4-6) — yet trial 2's
   standard branch ran fully clean (8/8). Possibly a transient agent skip,
   possibly a projected-local-type quirk on the standard branch. Did not
   block success (attempt 2 took the high branch and passed). Worth a
   5-minute look at the standard-branch projection before a big run.

## Open threads (pick up next session)

1. **Full 8-arm n=10 finance run.** The MAF arms are unblocked — the
   whole matrix can now run. This is item #1 from the 2026-05-18
   next-session plan, finally executable. ~60-90 min on laptop; use
   `case_runner.py finance 10` (all arms) or `run_subset.py` for a
   subset. `--resume` if interrupted.
2. **Investigate the `spec_llmvalid` standard-branch `off_protocol`
   flags** (caveat #2 above) before committing to n=10.
3. Everything still open from the 2026-05-18 entry: branch-asymmetric
   goal fix (G1), wiring `evaluate_run.py` into end-of-run, VM
   provisioning for the eventual n=100, LLM drafts for a second case.

## Next session plan

```
1. (small) Re-verify az session is on the Microsoft tenant
   (az account show). If MAF arms 400, az login first.

2. (5 min) Look at spec_llmvalid standard-branch projection — why did
   trial-1/attempt-1 flag off_protocol at steps 4-6?

3. (medium) Full 8-arm n=10 finance run. ~60-90 min. This is the run
   that turns the n=2 preview into a real result table.

4. (writeup) The monotonic 0% / 50% / 100% result is a tight paper
   figure once it has n=10 behind it.
```

## Files added / modified today

### Added
- `experiments/scripts/run_subset.py` — arm-subset benchmark driver
- `experiments/cases/finance/runs/20260520T115634-n2-dual/` — n=2 run
- `experiments/logs/finance_subset_n2.log` — run log

### Memory
- `maf-sdk-gotchas` — added gotcha #4 (MAF 400 = stale `az` token)

## Pointers

- n=2 result table: top of this entry.
- `run_subset.py` usage: `run_subset.py <case> <n> <arm> [<arm> ...]`.
- Known arm keys (8): `bare`, `maf_native`, `maf_foundry`,
  `maf_groupchat`, `maf_groupchat_unsafe`, `maf_groupchat_llmvalid`,
  `spec_llmvalid`, `min_llmvalid` — see `experiments/baselines/registry.py`.
- The MAF 400 → `az login` fix is in memory [[maf-sdk-gotchas]] and the
  auth gotcha (Microsoft vs Siemens tenant) is in the 2026-05-13 entry.

---

# 2026-05-18

A very long session. The benchmark grew from 3 arms → 5 → 6 → 7 → 11 → 8,
each iteration sharpening the research question. The headline outcome:
**the LLM + Scribble validator + projection pipeline now composes
end-to-end, and we can prove it experimentally.**

Best single result from today, n=1 finance, `WITH-spec-llmvalid`:

```
   1. Fetcher        → RevenueAnalyst : FetchRevenueData
   2. ExpenseAnalyst → RevenueAnalyst : AnalyzeExpenses
   3. RevenueAnalyst → TaxSpecialist  : HighRevenue       ← G1 ✓
   4. TaxSpecialist  → RevenueAnalyst : AuditCompleted    ← G2 ✓
   5. RevenueAnalyst → TaxVerifier    : NotificationBranch
   6. TaxVerifier    → RevenueAnalyst : Approval          ← G3 ✓
   7. RevenueAnalyst → Writer         : FinalizeReport    ← G4, G5 ✓
   8. Writer         → Fetcher        : GenerateReport

   succeeded: true   attempts: 1   tokens: 23,440   5/5 goals
```

This is 8 agents following an **LLM-drafted, Scribble-validated, machine-
projected** local type per role, monitored against the same global type,
scored against re-anchored goals — first attempt, every step OK, all 5
goals pass. The full LLM+validator+projection+monitor loop is working.

## The research question reshaped twice today

Started the day with the existing 3-arm setup (bare / spec / min, all
canonical, code_review). Two reframings from the user reshaped the
experiment:

**Reframing 1 (mid-session):** "The MAF agents should also get the
global type as text — only then is the comparison fair." Adding
`maf_groupchat_global` and watching it hit 100% on `code_review` told us
session-type machinery isn't necessarily what's load-bearing; **the
*shared vocabulary* of an agreed protocol is what makes 5 agents
compose**. This sharpened the claim from "session types beat free-form"
to "session types provide the vocabulary; projection + monitor become
load-bearing on harder protocols."

**Reframing 2 (late session):** "Test the value of the **validator**
specifically — show that an LLM-drafted protocol that *fails* Scribble
makes agents behave badly, while one that *passes* makes them work."
This shifted the experiment from "do session types work" to **"does the
LLM+validator co-design pipeline produce a usable session type?"** —
which is a much sharper, more falsifiable claim.

The canonical-protocol arms (`spec_canonical`, `min_canonical`,
`maf_groupchat_global`) were intentionally dropped from the final
matrix — they answer a different question (human-written protocols
work) that we already showed in earlier sessions.

## Final 8-arm matrix (LLM + validator focus)

| # | arm | input given to agents | what it tests |
|---|---|---|---|
| 1 | bare | intent only (Foundry) | baseline: no protocol, raw SDK |
| 2 | maf_native | intent only (MAF/OpenAI direct) | baseline: no protocol, MAF runtime |
| 3 | maf_foundry | intent only (MAF/Foundry chat) | baseline: no protocol, MAF on Foundry |
| 4 | maf_groupchat | intent only (MAF GroupChat) | baseline: no protocol, emergent orchestration |
| 5 | maf_groupchat_unsafe | LLM-drafted **unsafe** global text (Scribble rejected); observational mode (no monitor — projection refuses) | "what happens when agents follow an unsafe protocol?" |
| 6 | maf_groupchat_llmvalid | LLM-drafted **valid** global text (Scribble passed) | "does telling agents the validated protocol help?" |
| 7 | spec_llmvalid | LLM-valid projected to per-role local types (verbose Claude markdown) | "does projection + monitor add value on top of the validated global type?" |
| 8 | min_llmvalid | LLM-valid projected to per-role local types (minimal SEND/RECV table) | minimal-projection variant |

Each arm gets the same intent paragraph + the same 5 goals. The
**global type information** (none / valid text / unsafe text / projected
per role) is the only thing that varies between rows.

## What was built today

### experiments/baselines/ — multi-framework runner abstraction

Replaced the hard-coded SCENARIOS list in `case_runner.py` with a
registry-driven abstraction.

| file | purpose |
|---|---|
| `base.py` | `BaselineRunner` ABC + `AttemptResult` dataclass. Each runner reports its *active protocol* (`active_protocol_path()`) and its *goal set* (`goal_set()`) — defaults to canonical, overridable per arm. Also `reset_for_trial()` hook for per-trial agent rebuild. |
| `instructions.py` | `build_bare/spec/min/global_spec_instructions(case, role, protocol_path_override=...)`. The override is what lets LLM-drafted arms project from a non-canonical .scr. When override is set, **canonical skills files are deliberately NOT loaded** (Bug 2 fix — see below). |
| `registry.py` | SCENARIOS list (8 entries). Factories for LLM-drafted arms fail-fast at setup() if `protocols/llm_drafts/<kind>/v1.scr` is missing, with remediation message. |
| `foundry_runner.py` | FoundryRunner (covers bare/spec_llmvalid/min_llmvalid). Threaded per-attempt thread creation = inherent per-trial freshness. |
| `_maf_common.py` | MAFRunnerBase with recipient-addressed loop (`send_to` picks next speaker). Covers maf_native + maf_foundry. Rebuilds agent objects on `reset_for_trial()`. |
| `maf_native.py` | MAF Agent + `OpenAIChatCompletionClient` against Azure OpenAI directly. |
| `maf_foundry.py` | MAF Agent + `FoundryChatClient.as_agent(...)` (which creates an ephemeral Foundry-backed agent — NOT `FoundryAgent(agent_name=...)` which only attaches to pre-existing agents). |
| `maf_groupchat.py` | MAFGroupChatRunner with `GroupChatBuilder` + LLM orchestrator_agent. Parameterised by `instructions_builder` so the same class powers `maf_groupchat`, `maf_groupchat_unsafe`, `maf_groupchat_llmvalid`. Wraps `workflow.run` in `asyncio.wait_for(..., timeout=180s)` to cap deadlocks on the unsafe arm. |

### experiments/scripts/ — the LLM+validator harnesses

| file | purpose |
|---|---|
| `draft_llm_protocols.py` | Drives `architect.py` N times on a case's intent. For each draft: writes to `protocols/llm_drafts/<kind>/v1.scr` (subdirs because Scribble requires module-name == filename-stem), Scribble-validates, scores unsafe drafts by deadlock-suggestive keywords. If no valid draft after N fresh tries, switches to **fix mode**: feeds the best failing draft + its Scribble error back to the architect for iterative refinement. **For finance: 10/10 fresh drafts failed Scribble; 1 fix iteration succeeded.** This IS the "LLM + validator" co-design value, demonstrated. |
| `re_anchor_goals.py` | LLM-assisted goal re-anchoring. For each canonical goal, asks the LLM to map it to a `(sender, receiver, label)` in the new protocol that preserves the goal's semantic intent. Now includes **post-validation + retry** (parses the new protocol's edges; if LLM picks a tuple that doesn't exist, retries up to 3 times with explicit feedback listing the valid edges; only marks `no_equivalent` after retries fail). Predicate prompt explicitly states payloads arrive as Python strings (so `x.lower() == "true"` for Bool, `float(x) > 50000` for Double — NOT `x is True`). |

### Per-arm projection/monitor/goals plumbing (Tier 1 + Tier 2)

`case_runner.run_scenario` now calls `runner.active_protocol_path()` and
`runner.goal_set()` instead of using `case.protocol_path` / `case.goal_set()`
globally. So:

- `bare`/`maf_*` arms (no protocol given): monitor uses canonical (purely
  for observation — agents have nothing to conform to anyway)
- `spec_llmvalid`/`min_llmvalid`: monitor uses LLM-valid; goals come from
  `protocols/llm_drafts/valid/goals.yaml` (the re-anchored set)
- `maf_groupchat_llmvalid`: same as above for monitor + goals
- `maf_groupchat_unsafe`: monitor would-use unsafe, but Scribble refuses
  to project — graceful **observational fallback** kicks in (see below)

`load_goal_set_from_yaml(yaml_path, intent)` in `case_loader.py` parses
the re-anchored goals back into a `GoalSet`.

### Observational fallback for unprojectable protocols

The unsafe protocol's whole point is that **Scribble refuses to project
it** (inconsistent external choice subjects → no consistent local type
exists for TaxVerifier). Our pipeline was crashing on this with a
RuntimeError from `get_all_efsms`. Now `case_runner.run_scenario` catches
that, emits a `protocol_unprojectable` marker, builds an empty-monitor
emitter (no per-role state machines = no verdicts), and runs the arm
purely observationally. Agents try to follow the unsafe global type;
their event count, completion status, and accidental goal-pass are all
recorded without protocol verdicts.

This is methodologically the right thing: **the unsafe arm tests
behaviour, not conformance**, because conformance against an
unprojectable protocol is undefined. Scribble's refusal to project IS
the validator working — at projection time, not just validation time.

### Bugs found and fixed

| # | bug | root cause | fix |
|---|---|---|---|
| 1 | Re-anchored Bool predicates always false on perfect traces | `x is True` checks Python identity, but our runtime serialises every payload via `str(...)` → `x` is the string `"True"` | Re-anchorer SYSTEM prompt explicitly says payloads arrive as strings; gives per-type examples |
| 2 | `spec_llmvalid` agents emit one event then everyone WAITs forever | `generate_claude_subagent` was injecting **canonical skills** (`Decision Rules`, `Execution Flow`, `Business Rules` sections from `skills/v1/*_skills.md`) that referenced canonical labels (`HighNotice`, `AuditedRevenue`, …) which DON'T exist in the LLM-valid protocol. Agents read contradictory instructions, output WAIT. | `build_spec/min_instructions`: when `protocol_path_override` is set, skip the canonical skills load. Projection + refinements (derived from the override path) are sufficient. |
| 3 | LLM picks `(sender, receiver, label)` tuples that don't exist in the protocol | LLM tendency to invent plausible-looking but wrong tuples (`TaxSpecialist → RevenueAnalyst : NotificationBranch` when NotificationBranch actually goes the other way) | Re-anchorer parses the new protocol, builds a valid-edge set, validates each LLM pick, retries with explicit feedback if invalid |
| 4 | `maf_groupchat_unsafe` thread crashed (no `attempt_end`, no data) | Scribble's projection refusal was an uncaught exception in case_runner | Observational fallback as described above |

### Wave-based execution (rate limit defense)

At n=10 with all arms parallel, the MAF arms (sharing the same
`gpt-4o` deployment via direct `OpenAIChatCompletionClient` calls)
collectively exceeded Azure's TPM quota, surfacing as `Error 429`s
which our runner counts as no-progress → spurious consec_wait bailouts
→ artificially low success rates on MAF arms.

`case_runner.run_case` now runs in two waves:

- **Wave 1**: Foundry-only arms in parallel (`bare`, `spec_llmvalid`,
  `min_llmvalid`). Foundry Agent Service handles 429s internally.
- **Wave 2**: MAF arms sequentially, one at a time. No cross-arm
  contention on the OpenAI deployment.

Slower wall clock (~60–90 min at n=10 finance) but no rate-limit
contamination.

### `--resume` mode

If a long run gets killed (laptop sleep, network blip, manual cancel),
`case_runner.py <case> <n> --resume <run_dir>` scans `events_<key>.jsonl`
for each arm, counts `trial_end` markers, and **skips arms with ≥
n_trials trial_ends**. Incomplete arms re-run from scratch (the
LiveEventEmitter already truncates JSONL at start). Then regenerates
summary.json over the full set.

Useful for the laptop scenario AND for the eventual VM run if a single
arm hits something transient.

## Key empirical findings (n=1, need n=10 confirmation)

### From the `code_review` 7-arm smoke (mid-session)

```
arm                            success  tokens/trial
─────────────────────────────────────────────────────
bare                              0%       58,524
maf_native                        0%       15,528
maf_foundry                       0%       14,919
maf_groupchat (intent only)       0%       23,153
maf_groupchat_global (canonical)  100%     10,399    ← !
spec                              100%     12,335
min                               100%     5,702
```

The eye-opener: `maf_groupchat_global` (MAF GroupChat given the
canonical Scribble text but no projection) hit **100% on code_review at
LOWER cost than verbose spec**. For straight-line protocols, the
**shared vocabulary alone** is enough — projection adds little. This is
where reframing #1 came from: the contribution of session types is the
shared vocabulary, projection earns its keep on harder protocols.

### From the `finance` 8-arm smoke (n=1, late session)

```
arm                            success  events/viols  tokens
────────────────────────────────────────────────────────────────
bare                              0%      27 / 27     45,988
maf_native                        0%      30 / 30     23,921
maf_foundry                       0%      36 / 36     17,413
maf_groupchat (intent only)       0%      18 / 18     12,694
maf_groupchat_unsafe              0%      17 /  0     38,183  ← observational
maf_groupchat_llmvalid       0% / 100%*   varies      ~32K    ← unstable
spec_llmvalid                     100%     8 /  0     23,440  ← perfect trace
min_llmvalid                  0% / 100%*   varies      ~16K    ← variance-sensitive
```

\* run-to-run variance is real at n=1 — these arms hit 100% in one
smoke and 0% in another, depending on which branch the LLM picks.

The conclusions from the n=1 finance run:

1. **The validator earns its keep on harder protocols.** code_review
   was easy enough that just describing the protocol worked. finance
   has branching + a refinement constraint — `maf_groupchat_unsafe`
   (Scribble-rejected) never closes; `maf_groupchat_llmvalid`
   (Scribble-validated) sometimes closes but is unstable.

2. **Projection is what makes coordination reliable.**
   `maf_groupchat_llmvalid` (validated global type, no projection)
   produced traces with `Writer → Writer` self-loops, `TaxVerifier`
   sending messages to itself, and other drift. `spec_llmvalid` (same
   global type, projected per role) produced a textbook-clean trace
   first attempt.

3. **Projection is also CHEAPER than the validated global type.**
   `min_llmvalid` ≈ 5K tokens per attempt when it succeeds;
   `maf_groupchat_llmvalid` ≈ 30K tokens per trial when it succeeds.
   Projection is ~3–6× cheaper because each agent sees only its slice.

## Drafter outcome on finance — the LLM+validator story, concretely

```
10/10 fresh LLM drafts: FAILED Scribble validation
  - 6/10 "Inconsistent external choice subjects for TaxVerifier"
  - 4/10 "Safety violation(s) at session state ..."

Fix mode (LLM gets Scribble's error feedback + previous draft):
  - 1/1 fix iteration: PASSED Scribble validation
```

This single artefact (`protocols/llm_drafts/valid/v1.scr`, 998 chars,
the LLM's fix-mode draft) is the experiment's central object. Every
"WITH" arm in the matrix is downstream of this protocol.

## n=10 finance smoke — interrupted by 429s, then by laptop concern

We launched n=10 finance smoke (`b7kf0t0bu`) but hit immediate Azure
OpenAI rate limit cascades on the MAF arms. Killed the run after
diagnosing, added wave-based execution. Re-launched (`bquas1m6m`)
running ~Wave 1 in parallel + Wave 2 sequential. User raised the
laptop-sleep concern. We:

- documented the impact (laptop sleep would corrupt the run)
- added `powercfg` workaround in conversation
- added `--resume` mode for partial recoveries
- documented the proper long-term answer (Azure VM)

n=10 run is still in progress at time of writing. **Next session: pick
up the smoke result; if interrupted, use `--resume`.**

## Files added / modified today

### Added (new)

- `experiments/baselines/__init__.py`
- `experiments/baselines/base.py` — BaselineRunner ABC + AttemptResult
- `experiments/baselines/instructions.py` — 4 builder functions
- `experiments/baselines/registry.py` — SCENARIOS + factories
- `experiments/baselines/_foundry_client.py` — lazy shared AgentsClient
- `experiments/baselines/foundry_runner.py` — FoundryRunner
- `experiments/baselines/_maf_common.py` — MAFRunnerBase
- `experiments/baselines/maf_native.py` — MAF + Azure OpenAI direct
- `experiments/baselines/maf_foundry.py` — MAF + Foundry chat
- `experiments/baselines/maf_groupchat.py` — MAF GroupChat + orchestrator
- `experiments/baselines/README.md` — what each baseline is, how to add new
- `experiments/scripts/draft_llm_protocols.py` — LLM+validator drafter
- `experiments/scripts/re_anchor_goals.py` — goal re-anchorer with validation
- `experiments/cases/finance/protocols/llm_drafts/valid/{v1.scr,goals.yaml}`
- `experiments/cases/finance/protocols/llm_drafts/unsafe/{v1.scr,goals.yaml}`
- `experiments/cases/finance/protocols/llm_drafts/drafts_log.json`
- numerous `experiments/cases/finance/runs/20260518T*` run dirs

### Modified

- `experiments/scripts/case_runner.py` — registry dispatch, per-arm
  protocol/goals, wave-based execution, observational fallback, --resume,
  per-trial reset hook
- `experiments/scripts/case_loader.py` — added `load_goal_set_from_yaml`
- `experiments/cases/finance/case.yaml` — (unchanged content; touched by run)

## Open threads (pick up next session)

1. **The n=10 finance smoke**. Check whether `bquas1m6m` completed.
   If yes → analyse table. If interrupted → `--resume <run_dir>`.

2. **Bug 1.5 (variance)**. At n=1, `min_llmvalid` and
   `maf_groupchat_llmvalid` flipped between 0% and 100% across two
   smokes — depending on whether the LLM picked the high or standard
   branch (G1 only fires in high). Need n≥5 per arm to smooth this out.
   n=10 should be sufficient; n=3 is borderline.

3. **G2 anchor quirk in `goals_valid.yaml`**: the LLM re-anchored G2
   ("audit non-empty") to `RevenueAnalyst → Writer : FinalizeReport` —
   semantically reasonable (FinalizeReport contains the audit result)
   but means G2 and G4/G5 all anchor to the same edge. Worth noting in
   the writeup. Could re-prompt the re-anchorer to prefer distinct
   anchors.

4. **`unsafe` arm's behavioural failure mode**. At n=1 it produced
   events but never closed. At n=10 we'll see whether the failure is
   consistent (always deadlocks) or sporadic (sometimes lucks into
   completion). The interesting empirical question: how often does the
   unsafety actually bite?

5. **VM provisioning** (still item #2 from 2026-05-15 diary). For
   n=100 × 6 cases, local is no longer reasonable. B2s in
   germanywestcentral, install deps, `nohup` the run. Resume mode
   handles transient failures.

6. **Spec generation for other cases**. We only have LLM drafts +
   re-anchored goals for `finance`. To run the 8-arm matrix on
   `iterative_polling`, `retry_loop`, `nested_retry` (etc.), need to
   run `draft_llm_protocols.py <case>` + `re_anchor_goals.py <case>
   valid` + `re_anchor_goals.py <case> unsafe` per case. ~5-10 min
   each.

7. **Drop spec_llmvalid if Bug 2 reproduces on other cases**. Bug 2
   fix worked for finance, but the canonical-skills-leak is a code
   pattern that could resurface. If it does, just keep `min_llmvalid`
   (which is more robust and cheaper anyway) as the projection arm.

## Next session plan

```
1. (small) Check b7kf0t0bu / bquas1m6m: did the n=10 finance smoke
   complete? Use --resume if partial. Report final table.

2. (small) Run draft_llm_protocols.py + re_anchor_goals.py for at least
   one more case (likely retry_loop or nested_retry — the loop+branch
   cases where the unsafe vs valid distinction is most interesting).

3. (medium) Run n=10 on that second case. Total wall ~60-90 min on
   laptop; or ~30 min on the VM.

4. (Azure) Provision the VM (B2s germanywestcentral). Use --resume
   mode for the eventual n=100 cross-case run.

5. (writeup) The 8-arm matrix + the drafter result (10/10 fresh fail,
   1 fix iter pass) + the n=10 finance table are a tight paper section.
   Worth drafting an outline before doing the n=100.
```

## Pointers

- 8-arm matrix table: top of this entry.
- Drafter result `protocols/llm_drafts/drafts_log.json` and the kept
  artefacts in `protocols/llm_drafts/{valid,unsafe}/`.
- LLM-valid protocol (Scribble passed, structurally different from
  canonical — RevenueAnalyst becomes the choice point, Writer only
  receives one FinalizeReport): `protocols/llm_drafts/valid/v1.scr`.
- Per-arm input docs: see "What each arm actually receives as input"
  table in conversation (or regenerate via the small dump script).
- Memory: [[baselines-architecture]] needs an update to reflect the
  8-arm layout (was 5 when written); [[maf-sdk-gotchas]] is still
  current.

## End-of-day wrap-up (added evening 2026-05-18)

After more iteration, applied 5 fairness fixes to the design + a
6th infrastructure fix:

1. **Role descriptions** in every arm's prompt (held-constant variable).
2. **G6 terminal goal** added; re-anchored for both LLM-drafted protocols.
3. **`max_steps` 12 → 24** (3× protocol-arm typical event count).
4. **Termination instruction** in every prompt builder.
5. **Intent verified literally identical** across all arms.
6. **Foundry network retry** with exponential backoff (DNS, 5xx, 429,
   timeouts) so transient blips don't kill arms — `_retry_transient`
   in `baselines/foundry_runner.py`.

Also built `experiments/scripts/evaluate_run.py` — the three-metric
post-hoc evaluator (strict / role-pair / semantic) with caching of
LLM judgments.

**The wrap-up design doc** for next session is
`docs/EXPERIMENT_DESIGN_v2.md`. It captures:
1. The three-metric fairness framework with worked examples
2. The matched-control input structure for non-MPST arms (6 blocks)
3. A concrete bare-Fetcher prompt + a sample trace scored under each
   metric to make the framework unambiguous
4. **Three benchmark tasks** for the full MPST-vs-intent-only comparison:
   Banking transaction, Travel booking with rollback, Multi-source RAG.
   Each task has safety invariants, milestones, terminal outcomes,
   negative properties, and one adversarial test case.

Open issues to address before the n=10 / n=20 runs:
- Branch-asymmetric goals (G1 on finance): apply "no anchor event →
  vacuously true" to all 3 verifiers; report per-branch in the
  writeup table.
- MAF 400 errors at end-of-day n=2: full error body got truncated by
  line-based log capture; need to dump and diagnose. Likely
  oversized prompt or MAF SDK regression.
- Three-metric evaluator is built but not yet auto-run; either connect
  into case_runner end-of-run, or commit to running
  `evaluate_run.py <case> <run_dir>` after each smoke.

End-of-day status: `bare`/`spec_llmvalid`/`min_llmvalid` produced
clean data with the new design (`spec_llmvalid` 2/2 success at n=2,
~267s wall clock per trial, half of bare's ~650s). MAF arms broken
on this run. Next session: investigate MAF 400, apply branch fix,
re-run n=10.

---

# 2026-05-15

A long session. The headline outcome: **end-to-end benchmark harness now
works at 3 scenario arms with retry-to-success and per-trial token
accounting**. A single n=1 smoke on `code_review` produces:

```
metric                       WITHOUT     WITH-verbose    WITH-minimal
─────────────────────────────────────────────────────────────────────
success rate                    0.0%         100.0%         100.0%
avg attempts (all)              3.00          1.00           1.00
avg tokens/trial (cum)        41,772        12,300          5,615
token savings vs bare              —          70.6%          86.6%
```

Strong empirical signal at n=1. VM provisioning + the full n=100 across
A–F is what's left.

## What we did

### 1. Workspace reorganization (∼20 files touched)

- **Renamed `finance_demo/` → `stjp_core/`.** It was always the STJP library
  layer; the name finally matches.
- **Top-level `docs/`** created; moved `DIARY_2026-05-13.md`, `GAP_CLOSED.md`,
  `FOUNDRY_VISIBILITY.md`, `EXPERIMENT_DESIGN.md`, `RESULTS.md`,
  `SKILLS_COMPILER_PROPOSAL.md`, `STJP_discussion_13May2025.md` there.
  Top-level polished docs (ROADMAP, RESEARCH, SCRIBBLE, MPST_STATIC, README)
  stayed put. Today's housekeeping later collapsed the dated diary files
  into this single `DIARY.md`.
- **Deleted 33 superseded files** in four categories: Foundry diagnostic
  one-offs (`diagnose_threads*`, `force_visible_thread`, …); legacy
  chat-completions experiment (`experiment_4_scenarios*`); superseded
  benchmark UI (`benchmark.html`, `benchmark_runner.py`); older live-demo
  iterations (`stjp_live_demo`, `stjp_make_*`, `stjp_graph.html`,
  `stjp_coverage.html`).
- **Moved `examples/composition_demo/` → `experiments/cases/composition/`.**
- **Updated all references**: `experiments/scripts/case_runner.py:34`
  (`FINANCE_DEMO` → `STJP_CORE`), `experiments/README.md:120`,
  `experiments/_smoke_all.sh:6`, `stjp_core/CLAUDE.md`,
  `stjp_core/README.md:173`, `stjp_core/orchestrator.py:51`, test docstrings.

### 2. Logs cleanup

- Deleted 11 stale `.log` files (everything older than today).
- Created `stjp_core/logs/` and `experiments/logs/`.
- `experiments/_smoke_all.sh` now tees into `experiments/logs/<case>_smoke.log`.
- No Python logging-to-file changes; project code emits to stdout, redirection
  is at the invocation layer.

### 3. Authored cases for shapes D / E / F (with Scribble validation)

Shape coverage before today: **A** (5 cases), **B** (1: finance), **C** (1:
finance_nested), D/E/F missing. Now:

| Shape | Case folder | Roles | Structural feature |
|---|---|---|---|
| **D** loop | `experiments/cases/iterative_polling` | Client, Server, Logger | `rec Loop` with degenerate Continue/Stop choice |
| **E** loop + simple branch | `experiments/cases/retry_loop` | Worker, Manager, Auditor | `rec Attempt` with Accept (terminates) / Retry (loops) |
| **F** loop + nested branch | `experiments/cases/nested_retry` | Author, Reviewer, Editor, Publisher | `rec Round` with revise-vs-accept outer, major/minor + publish/schedule inner |

All three pass Scribble compiler validation (`ScribbleValidator`). Skills
markdown is generated on the fly by `agent_generator.generate_claude_subagent`
at runtime; pre-authored `skills/v1/*.md` files are optional.

> Note: "shape D" as the user defined it (loop without branching) isn't
> expressible in standard Scribble — a `rec` always needs a terminating
> choice. `iterative_polling` uses the smallest possible Continue/Stop
> branching to remain valid.

### 4. Live mirror to `stjp_core/` for the HTML

- Added `mirror_path: Path | None` kwarg to `LiveEventEmitter`
  (`stjp_core/stjp_live_emitter.py`). Every JSONL line is also written to
  the mirror file.
- `case_runner.run_scenario` mirrors `events_bare.jsonl` and
  `events_spec.jsonl` (only those two — the existing HTML knows those
  filenames). The `events_min.jsonl` from the third arm is in the run dir
  + `summary.json` only.
- Verified working via every smoke run today.

### 5. Token-cost tracking

- Capture `run.usage.{prompt,completion,total}_tokens` from each
  `client.runs.create_and_process(...)` call in
  `case_runner.run_traced_session`.
- Accumulate per-trial; emit per-step deltas in JSONL `extra.tokens`;
  emit per-trial cumulative totals in the `trial_end` marker.
- `summarize_run` aggregates per-scenario: avg tokens / prompt / completion
  / calls per trial.
- `print_summary` shows token savings % vs bare for each spec arm.

### 6. Spec minimization experiment (key empirical pivot)

Initial smoke showed verbose Claude markdown WITH used **~86% MORE tokens
per trial** than WITHOUT (12,241 vs 6,569 at n=1). Hypothesis "WITH is
cheaper because it terminates faster" was wrong at the per-trial level —
the larger system prompt dominated, terminating faster wasn't enough to
overcome it.

Iterated through three spec formats:

| Format | n=1 protocol-correct | n=1 tokens | Verdict |
|---|---|---|---|
| Verbose Claude markdown | 100.0% | 12,241 | safe but bloated |
| Minimal MPST `!`/`?` | **28.6%** ✗ | 8,426 | LLM mis-decodes session-type symbols |
| Minimal MPST `SEND`/`RECV` | 100.0% | **5,610** ✓ | accuracy + 54% cheaper than verbose |

The `!`/`?` notation broke the LLM: Merger emitted `Approval2` (a SEND)
when the protocol said `?Reviewer2.Approval2` (a RECV). Switching to
explicit `SEND` / `RECV` verbs (+ a one-line legend) restored 100%
accuracy AND captured the cost savings.

Decision: **keep both spec formats as separate scenarios** for the n=100
runs, so we have clean comparison data instead of choosing blindly.

### 7. 3-arm + retry-to-success refactor (`case_runner.py`)

Two coupled changes:

- **3 scenarios per case** instead of 2:
  ```python
  SCENARIOS = [
      ("bare", "WITHOUT-skills",    build_bare_instructions),
      ("spec", "WITH-verbose-spec", build_spec_instructions),
      ("min",  "WITH-minimal-spec", build_spec_minimal_instructions),
  ]
  ```
  Generic `run_scenario(scenario_key, scenario_name, builder, ...)` replaces
  the old `with_spec: bool`. `_agent_name` is keyed by scenario_key so each
  arm gets its own Foundry agent set (e.g. `stjp-code_review-min-author`).

- **Retry-to-success (MAX_ATTEMPTS=3)** per trial: agent threads are
  recreated fresh each attempt; goals checked at attempt end; loop exits
  on `all(goals_pass)`. New emitter markers `attempt_start`/`attempt_end`;
  `trial_end` now carries `succeeded`, `attempts`, and cumulative tokens.

- **New summary metrics**: `success_rate_pct`, `avg_attempts_all`,
  `avg_attempts_success`, `avg_tokens_per_success`. 3-column
  `print_summary`.

### 8. Smoke validation (post-refactor, n=1, `code_review`)

`experiments/cases/code_review/runs/20260515T201730-n1-dual/`. Result table
at the top of this entry. WITHOUT exhausted all 3 retries; both spec arms
succeeded first try. Minimal spec dominated on cost.

## Key empirical findings (n=1, need n=100 confirmation)

1. **Without protocol guidance, agents never succeed** within 3 retries
   on `code_review` (clean_pr branch). Goals are 0/4 across all attempts.
2. **Both spec formats restore 100% goal-pass on attempt 1** for
   `code_review`.
3. **Minimal SEND/RECV spec is ~54% cheaper** than verbose Claude
   markdown, **86.6% cheaper than bare** (cumulative tokens-to-success).
4. **Retry-to-success makes the cost gap legible**: without retry, n=1 made
   WITH look more expensive per trial; with retry, bare's wasted retries
   dominate and the WITH spec arms come out ahead by 4–7×.
5. **Async ordering remains a real failure mode**, even WITH spec — the
   `retry_loop` smoke (separate run) showed Manager sending Accept before
   Worker had finished sending AttemptResult to both peers. The protocol
   spec doesn't constrain *when* Manager observes Worker's emissions.

## Files added / modified / deleted today

### Added

- `experiments/cases/{iterative_polling,retry_loop,nested_retry}/`
  - `case.yaml`, `protocols/v1.scr`, `protocols/v1.refn`,
    `skills/v1/` (empty; auto-generated at runtime)
- `experiments/cases/composition/` (moved from `stjp_core/examples/`)
- `docs/DIARY.md` (consolidated; this file)
- `stjp_core/logs/`, `experiments/logs/` (empty dirs for future log routing)

### Modified

- `experiments/scripts/case_runner.py` — bulk of the work: 3-scenario
  refactor (`SCENARIOS`, `MAX_ATTEMPTS`, refactored `_agent_name`,
  `get_or_create_role_agents`, `run_scenario`); token capture from
  `run.usage`; retry-to-success loop; new aggregation + summary.
- `stjp_core/stjp_live_emitter.py` — added `mirror_path` kwarg.
- `experiments/README.md` — `finance_demo/` → `docs/` reference fix.
- `experiments/_smoke_all.sh` — tee to `experiments/logs/`, path updates.
- `stjp_core/CLAUDE.md` — title fix, removed refs to deleted scripts,
  noted new load-bearing drivers.
- `stjp_core/README.md`, `stjp_core/orchestrator.py`, test docstrings —
  `finance_demo` → `stjp_core`.

### Deleted (33 files)

Foundry diagnostics: `diagnose_threads.py`, `diagnose_threads_fast.py`,
`probe_foundry_setup.py`, `dump_conversations.py`,
`force_visible_thread.py`, `restore_strict_instructions.py`,
`update_instructions_for_orchestration.py`, `reset_agents.py`,
`wire_connected_agents.py`, `check_foundry_agents.py`,
`register_agent_service.py`, `run_foundry_orchestration.py`,
`verify_foundry_visibility.py`.

Legacy chat-completions: `experiment_4_scenarios.py`,
`experiment_4_scenarios_chatcompletions.py`, `experiment_harness.py`,
`smoke_test_azure.py`, `smoke_test_foundry_agent.py`.

Superseded benchmark UI: `benchmark.html`, `benchmark_runner.py`,
`benchmark_report.html`, `benchmark_live.jsonl`,
`generated_agents/benchmark_results.json`.

Older live-demo iterations: `stjp_live_demo.py`,
`stjp_make_demo_events.py`, `stjp_make_artifacts.py`, `stjp_graph.html`,
`stjp_coverage.html`, `events.jsonl`.

11 stale `.log` files in `stjp_core/` and `experiments/`.

## Open threads (pick up next session)

1. **VM provisioning** (task #11). Foundry endpoint is in
   `germanywestcentral`; spin the VM in the same region. Recommended size
   B2s (~$30/mo); install Python 3.11+, az CLI, Java 11. Copy
   `stjp_core/` + `experiments/` + `scribble-java/`, recreate `.venv`,
   `pip install -r requirements.txt` (need to create this — for now,
   freeze: `pip freeze > requirements.txt` from local `.venv`).
2. **Azure Storage Static Website** (tasks #16, #18). User picked option
   A: 5-second-cadence upload of `events_*.jsonl` + `summary.json` from
   the VM to a `$web` container. Stable URL teammates can open. Write
   `experiments/scripts/publish_run.py` to do the upload step;
   `case_runner` calls it at intervals during runs.
3. **Big run** (task #13). All 6 cases × 3 arms × n=100 × MAX_ATTEMPTS=3.
   Smoke D and F first (n=1 each, ~10 min total) to confirm rec works
   end-to-end before committing. Estimated **$90–110 Foundry spend, 5–7
   days wall clock** (bare retries dominate).
4. **stjp_comparison.html still only shows 2 panels.** The 3rd arm
   (`events_min.jsonl`) is in the run dir + summary.json but not the
   live UI. Either upgrade the HTML to 3 panels or add a scenario toggle.
5. **Async-ordering hint in spec.** retry_loop smoke showed Manager firing
   Accept before Worker had sent AttemptResult to all peers. Possibly add
   a "wait for all peers' last message in state X before transitioning"
   nuance to the spec, or accept it as a known failure mode.
6. **Foundry agent garbage collection.** With 3 arms × 6 cases × 5–6
   roles ≈ 100 agents accumulating. Add a clean-up routine before/after
   each big run.

## Next session plan

In rough order — each is gated on the previous succeeding:

```
1. (small) Smoke iterative_polling (D) + nested_retry (F) at n=1, local.
   ~10 min total. Validates rec end-to-end before committing the big run.

2. (Azure) Provision VM (B2s, germanywestcentral). User-driven; I provide
   commands and verify after each step.

3. (Azure) Install deps + clone project on VM. Verify `az login` works
   on the Microsoft tenant (16b3c013-..., per 2026-05-13 entry below).

4. (Azure) Set up Storage Static Website + write publish_run.py.
   Verify with one n=1 case_runner run on the VM that publishes correctly.

5. (Big) Run all 6 cases × 3 arms × n=100 on the VM, with periodic
   `nohup`/`screen` so SSH disconnect doesn't kill it.

6. (Analyze) Once the runs finish, aggregate the 6 summary.json files
   into a single cross-case dashboard. Update INDEX.html in experiments/
   to also show success rate, avg attempts, tokens-per-success per case.
```

## Pointers

- Previous entry below: 2026-05-13 (gap closure for refinement
  call-site enforcement)
- Roadmap context: `ROADMAP.md` §1.1–1.6 (Phase 1 shipped); §2.1–2.6 (Phase
  2 in flight)
- Benchmark README: `experiments/README.md` — case.yaml schema + how to
  add a new case
- Live demo: `stjp_core/stjp_dual_demo.py` (legacy single-case) and
  `experiments/scripts/case_runner.py` (current, 3-arm, retry-to-success)
- Live HTML: `stjp_core/stjp_comparison.html?live=1` served via
  `stjp_core/stjp_serve.py 8765` (locally)
- All 8 cases authored:
  - A (linear): `auction`, `clinical_enrollment`, `code_review`,
    `intel_report`, `travel_saga`
  - B (simple branch): `finance`
  - C (nested branch): `finance_nested`
  - D (loop): `iterative_polling`
  - E (loop+branch): `retry_loop`
  - F (loop+nested branch): `nested_retry`
  - (special): `composition` — Banking + Inventory → ECommerce, doesn't
    fit the case.yaml schema, kept for the composition demo.

## Risk register

- Foundry rate limits at n=100 × 3 arms × 3 retries × 6 cases — may hit
  429s on the VM. No retry/backoff in the current `case_runner.py`. If
  we see throttling in the big run, add it.
- Foundry Microsoft-tenant vs Siemens-tenant trap (see 2026-05-13 entry).
  If `az account show` returns the Siemens identity, the run fails with
  a tenant mismatch. `az login --tenant 16b3c013-d300-468d-ac64-7eda0820b6d3`.
- Each retry creates fresh threads — at n=100 × 3 arms × 3 retries × 5–6
  roles ≈ 9000+ Foundry threads accumulating per case. Add a post-run
  thread cleanup step.

---

# 2026-05-13

## What we tackled today

The question that started the session: **refinement-typed session types with
assertions — is the Bocchi/Honda/Tuosto/Yoshida-style "MPST with assertions"
formalism implemented as a Scribble extension in this repo, and have those
assertions been projected to local typed skills?**

Short answer that we discovered by reading the code: **partially.** The
`.refn` sidecar + `refinement_checker.py` give you the predicates, but they
sat outside the projected agents. The runtime check was happening at the
wrong place — `SessionMonitor` was reading captured trace events after the
fact, not inside the agent's tool at the call site, which is what the design
in `testing_ideas/STJP_discussion_13May2025.md` §"Monitor design" and the
PNG `testing_ideas/monitoring_tool_from_intent.png` actually specify.

That gap is what we closed today.

## What was built

### 1. Gap closure — predicate compiled into the projected tool

| File | Change |
|---|---|
| `refinement_checker.py` | + `class RefinementViolation(Exception)` |
| `agent_generator.py` | rewrite — both generators now take a `refinements` dict; Python stub emits per-`(peer, label)` `send_*` tool methods whose body contains the compiled predicate as literal Python; `act()` consults a `_REFINEMENT_GUARDS` dispatch table so direct callers cannot bypass; Claude subagent markdown gets a `## Refinement Invariants (HARD — enforced at call site)` section plus per-action annotations |
| `test_callsite_refinement.py` | new — 10 focused checks (violating payload raises, state does not advance, history stays empty, passing payload advances correctly, bypass via `.act()` still blocked, unrefined sends pass through). **All 10 pass.** |
| `GAP_CLOSED.md` | doc — before/after diagram, the three concrete edits, and what remains open (static SMT discharge, JSON-schema tool descriptions, sync of prose decision rules with `.refn`, receiver-side assumption checks) |

The figure in `monitoring_tool_from_intent.png` — `func_check_A_to_B_Transfer(msg)
:= if msg.amount < 50000 then ALLOW else REJECT` — is now realised directly:
each refined send compiles to a named guard function at module scope, called
from both the convenience method and `act()`.

### 2. WITH vs WITHOUT benchmark infrastructure

| File | Change |
|---|---|
| `experiment_via_agent_service.build_spec_instructions` | now calls `generate_claude_subagent(...)` so the LLM-facing instructions include the new "## Refinement Invariants (HARD)" section and per-state EFSM transitions |
| `experiment_via_agent_service.get_or_create_role_agents` | now **refreshes** existing agents' instructions via `client.update_agent` rather than silently reusing stale text |
| `benchmark_runner.py` | new — sequential WITH (10 trials) then WITHOUT (10 trials); writes per-trial summary to `benchmark_live.jsonl`; renders final self-contained `benchmark_report.html` |
| `benchmark.html` | new — live polling dashboard (side-by-side WITH/WITHOUT, per-trial bar chart, violation breakdown table). **Superseded** by `stjp_comparison.html` per the user's preference, see "Open thread" below. |

### 3. Smoke test (n=1) — passed

```
                                WITH            WITHOUT
global conformance              1/1 (100.0%)    0/1 (0.0%)
goal pass rate                  100.0%          0.0%
off_protocol violations         0               24
premature_termination           0               6
total violations                0               30
elapsed per trial               130 s           256 s (hit MAX_STEPS)
```

The bare agents got lost without the projected EFSM telling them whose turn
it is and which message label to use — they emitted off-protocol messages
and timed out before reaching `GenerateReport`. The WITH agents finished
cleanly. This is the kind of gap we want to demonstrate at n=10.

## Open thread (pick this up next session)

The user wants the live demo to use the **existing** `stjp_comparison.html`
in `finance_demo/`, not the new `benchmark.html` I built. The comparison
page was designed to consume the per-event streams `events_spec.jsonl` (WITH)
and `events_bare.jsonl` (WITHOUT) that `stjp_dual_demo.py` already writes
via `LiveEventEmitter`.

To resume:

1. **Read `stjp_comparison.html`** to confirm exactly which JSONL files /
   field names it expects.
2. **Bump `stjp_dual_demo.py` default to n=10** (currently 1).
3. **Confirm `stjp_dual_demo.py` picks up the new compiled-refinement
   instructions.** It imports from `experiment_via_agent_service` and uses
   `build_spec_instructions(role)`, which we already upgraded — so this
   should work automatically. Verify by inspecting `stjp-fetcher` in the
   Foundry portal after one trial: the agent's instructions should contain
   the `## Refinement Invariants (HARD)` section.
4. **Launch sequence:**
   ```powershell
   # terminal 1 — local server, opens browser
   .venv\Scripts\python.exe stjp_serve.py
   # then change URL to http://127.0.0.1:8765/stjp_comparison.html
   #
   # terminal 2 — the run
   .venv\Scripts\python.exe stjp_dual_demo.py 10
   ```

If `stjp_comparison.html` expects something `stjp_dual_demo.py` doesn't
currently emit, the gap is in the dual-demo driver, not in the comparison
page or the gap-closure work.

`benchmark.html` and `benchmark_runner.py` can stay around as the static
post-run report path; they're orthogonal to the live comparison page.

## Auth gotcha worth remembering

The Foundry project endpoint `https://foundary-tzuc06.services.ai.azure.com/...`
is on the **Microsoft tenant** (`16b3c013-d300-468d-ac64-7eda0820b6d3`,
`tzuchunchen@microsoft.com`), **not** the Siemens tenant
(`cfd26b50-fb8f-44cf-87b2-d5df3d15d884`, `gina.chen.ext@siemens-healthineers.com`).
If `az account show` returns the Siemens identity, any Foundry call fails
with `Token tenant ... does not match resource tenant`. Fix:

```powershell
az login --tenant 16b3c013-d300-468d-ac64-7eda0820b6d3
```

## Files added or changed today

```
finance_demo/
  refinement_checker.py        (edit: + RefinementViolation)
  agent_generator.py           (rewrite: compile predicates into tools)
  test_callsite_refinement.py  (new)
  GAP_CLOSED.md                (new)
  experiment_via_agent_service.py  (edit: spec instructions + update_agent)
  benchmark_runner.py          (new)
  benchmark.html               (new — superseded by stjp_comparison.html)
  benchmark_report.html        (generated artefact, n=1 smoke run)
  benchmark_live.jsonl         (generated artefact, n=1 smoke run)
  generated_agents/benchmark_results.json  (generated artefact)
  DIARY_2026-05-13.md          (this file)
```

## Pointers

- `GAP_CLOSED.md` — what the refinement-projection gap was and how it was
  closed; the canonical doc for the technical contribution.
- `testing_ideas/STJP_discussion_13May2025.md` — the conversation that
  motivated this work, including the empirical finding that LLM agents
  follow structural local types at near-100% but fail value-dependent
  constraints.
- `testing_ideas/monitoring_tool_from_intent.png` — the figure whose
  three-stage design (Local type with `where` clause → compiled boolean
  function → monitor runtime) the gap closure implements.
