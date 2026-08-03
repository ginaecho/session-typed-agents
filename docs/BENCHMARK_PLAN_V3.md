# STJP Benchmark Plan v3 — Foundry hosted, real toolchains, 8 settings + MAF kinds

> **Operational companion:** [`reference/HOW_TO_RUN_BENCHMARKS.md`](reference/HOW_TO_RUN_BENCHMARKS.md)
> — the step-by-step runbook (classic ladder §2–5, hosted-group deploy §6,
> report format §7, error-avoidance checklist §8). This document is the design;
> that one is how to execute it.

**Date: 2026-08-01.** This is the authoritative plan for the STJP real-case
benchmark campaign. It supersedes `reference/BENCHMARK_PLAN_V2.md`. It states
exactly what runs, where it runs, which tools must be installed, how results
are graded, and what tables the campaign produces — in the evaluation style
of `reference/sections_eval_results.html` (the earlier 5-configuration
report), extended to the 8-setting ladder and the MAF kinds.

---

## 1. Scope and parameters

- **Trials per cell:** n = X, **X = 10 now**, raised later (30+ for headline
  claims) without changing any other part of the plan.
- **Models (both, every cell):** **gpt-5-mini** (cost-efficient; coordination
  errors most visible) and **gpt-5.4** (frontier capability; tests whether
  enforcement stays necessary as quality rises). Both are Azure AI Foundry
  model deployments.
- **Cases:** the twelve real-skill / purpose-built cases plus memory_race
  (§6). Each declares its own catastrophe.
- **Matrix per case:** (8 settings + 3 MAF kinds) × 2 models × n trials.
- **Balanced branches:** cases with a choice point allocate trials equally
  across branches (equal-n per branch) to prevent branch-composition
  confounds.

---

## 2. Execution surfaces on Azure AI Foundry

Every trial must leave server-side evidence on Azure AI Foundry, not only in
local logs and git. Two surfaces are used, for two different reasons.

### 2.1 Hosted agent groups (required — the primary evidence surface)

Each case is deployed as an Azure AI Foundry **hosted agent group** (portal
agent type **"Hosted"**; the `stjp-<case>-group` deployments), built on the
Microsoft Agent Framework's `WorkflowAgent` / `ResponsesHostServer`. Every
case is invoked **n = 10 per model = 20 traces per case**, and those traces
are visible on the portal's Hosted surface — the surface a reviewer audits.
This is a standing requirement: a run that is not visible here does not count
as delivered.

Plan to satisfy it:
1. Groups are model-pinned at deployment. Redeploy each existing group on
   **gpt-5-mini** and **gpt-5.4** (the current seven were pinned to
   gpt-5.6-sol and invoked once as a smoke demo — not a benchmark).
2. Author group definitions for the cases that never had one (finance, sdlc,
   gem, react18, multi_buyer, multi_seller); the pattern exists under
   `foundry_hosted_agents/` for three cases already.
3. Invoke each group n = 10 per model; capture each transcript; grade with the
   same Set B goal predicates (§4).
4. Add a **"Hosted group (Foundry)"** row to every case table.

Architectural honesty: a hosted group runs the framework's own internal
orchestration. The gate (per-message rejection) and the EFSM scheduler
(per-turn enabled-sender selection) **cannot be interposed inside a sealed
group**, so settings 5–8 are not expressible there. The hosted-group row
therefore measures *the group's own coordination* (analogous to the MAF
GroupChat kinds), and the gate/scheduler settings are measured on the classic
Agent Service surface (§2.2). Both surfaces are named per case so no reader
mistakes one for the other.

### 2.2 Classic Agent Service (the per-message-control surface)

The 8-setting ladder needs per-message interception (the monitor gate) and
per-turn control (the scheduler). These run on the Foundry **Agent Service**:
one classic agent per role per setting (`stjp-<case>-<setting>-<role>`) and
one thread per role per trial. These appear in the portal's
previous/classic agents view (NOT the "New Foundry" page). Visibility rules
and deep links: `reference/FOUNDRY_VISIBILITY.md`.

### 2.3 Evidence, three layers, every trial

1. **Local:** `experiments/cases/<case>/runs/<dir>/events_*.jsonl`,
   `summary.json`, `summary_policy.json`, `summary_eval.json`, and the
   persisted per-role prompts under `prompts/<setting>/`.
2. **Git:** the run directories are force-added past `.gitignore` and pushed.
3. **Foundry:** classic agents + threads (ladder), hosted-group traces
   (hosted rows), and OpenTelemetry spans in Application Insights (MAF kinds).
   An anti-fabrication check greps distinctive model-generated sentences from
   the local events against the server-side thread store (as in RESULT_13).

---

## 3. Required toolchains (all installed and verified real)

| Tool | Role in the pipeline | Install / invocation | Status (verified 2026-08-01) |
|---|---|---|---|
| **scribble-java** | Validates the global protocol (deadlock-freedom) and **projects** it to one EFSM per role | `java -cp scribble-cli/lib/* ...` against `scribble-java/scribble-cli/target/scribble-cli-0.5.1-SNAPSHOT.jar` | **Built and live** — projections run this session |
| **nuscr** (coinductive fork) | Second, independent validator for the backend-comparison claim (coinductive check that scribble-java's finite check can miss) | Docker image `nuscr-coind` from `tools/nuscr/Dockerfile`, or a native binary via `STJP_NUSCR_BIN`; driver `stjp_core/compiler/nuscr_compiler.py` | **Available via Docker**; used by `backend_compare.py` |
| **Microsoft Agent Framework (MAF)** | The alternative runtime for the MAF kinds; also the hosting layer for the hosted groups | pip `agent-framework` 1.10.0 (Microsoft, `af-support@microsoft.com`); real `GroupChatBuilder(...).build()` + `workflow.run()` | **Installed and real** — genuine MAF orchestration, not a hand-rolled loop |

Pre-flight gate for the campaign: a `tool_preflight` step asserts all three
respond (scribble projects a known protocol; nuscr validates one; MAF imports
and builds a trivial group) before any trial runs. A tool failure aborts the
campaign rather than silently degrading a setting.

---

## 4. Evaluation methodology

### 4.1 Conformance and goal achievement

**Protocol conformance (Set A).** Let T be a run's event trace and M_r the
projected EFSM for role r. A message event e = (s, r, ℓ, v) *conforms* iff it
is accepted by M_s (a structurally legal send at s's current state) and
satisfies any refinement predicate φ_ℓ(v) from the guard sidecar. The
**violation rate** of a trace is the fraction of events rejected by at least
one role's monitor. Conformance is deterministic, per-message, and requires
no LLM judge.

**Goal achievement (Set B).** Each case defines k goals G1…Gk, each anchored
to a message edge (s, r, ℓ) with a payload predicate φ_i(v). A trial
*succeeds* iff all k goals are satisfied in at least one of its allowed
attempts. Two grading rungs: **strict** requires exact (s, r, ℓ) plus φ_i;
**role-pair** requires (s, r) plus φ_i under any label. Settings shown the
protocol vocabulary are graded strictly; settings never shown the labels
(settings 1–2, and the no-protocol MAF kind) are graded role-pair — a
fairness correction, marked **†** in all tables. Audit finding that motivates
it: many † successes never emit the terminal message, so a † result is a
weaker claim than a strict one.

**Design principle.** Reporting Set A and Set B separately is the empirical
instantiation of the theory that **type safety and progress are distinct
guarantees**: a team can hold zero violations while failing its goals (the
protocol is followed but the session runs out of steps), or reach its goals
while accumulating violations (right outcome, wrong path). Both patterns
occur in the data.

### 4.2 Consequence-graded violations: the S0–S4 severity scale

Each surviving deviation is graded by consequence on five levels, computed
against the partial order of data and authority dependencies declared in the
protocol:

| Level | Meaning | Counted? |
|---|---|---|
| **S0** | benign — reordering of independent messages | no |
| **S1** | waste — duplicate/no-op message; costs tokens, breaks nothing | yes (cost) |
| **S2** | broken obligation — skipped read or wrong ordering | yes (violation) |
| **S3** | non-termination — session exhausts its step budget | yes (violation) |
| **S4** | unauthorized irreversible act — the case's catastrophe (charge-before-hold, publish-before-review, release-before-receipt, deploy-before-tests, lost update) | yes (disaster) |

S4 is scored by the declarative Critic policy files (`protocols/v1.policy`,
run via `policy_eval.py --relaxed` so improvised no-protocol labels are
matched by family). Empirical validation to report: whether **every attempt
containing an S2+ violation goes on to fail its goal**.

### 4.3 Statistical methodology

All confidence intervals are **Wilson score intervals** (95%, z = 1.96),
well-behaved at 0% and 100%. Key cross-setting deltas carry two-sided
**Fisher exact** p-values. **Token counts** are the primary efficiency
metric; wall-clock is reported only as *indicative* (parallel waves and
rate-limit contention make it non-comparable). Balanced branch allocation
(§1) prevents branch-composition confounds. Verification standard: every
trial verdict is independently re-derived from the raw logs by a second
goal-checker; per-trial token variance confirms live API calls; a fragile-goal
audit confirms each 0/10 reflects genuinely absent messages, not artifacts.
All trace analysis is exact — ordered, per-trial, per-attempt walks of the
events; matchers written against the observed label vocabulary. No fuzzy
substring heuristic is ever used as evidence.

---

## 5. Experimental configurations

### 5.1 The 8-setting ladder

Each setting adds one mechanism; all share the same intent, role
descriptions, model, turn limit (`max_steps`) and retry rules.

| # | Setting | Protocol info in prompt | Enforcement | Scheduling |
|---|---|---|---|---|
| 1 | Intent only | none (task description) | none | round-robin |
| 2 | Real skills, no protocol | real published skill files, verbatim | none | round-robin |
| 3 | Global protocol (as text) | full validated global protocol | none | round-robin |
| 4 | Local contract (not enforced) | projected local contract per role | none (observe only) | round-robin |
| 5 | Local contract + gate (verbose) | projected local contract (full prose) | gate rejects violations | round-robin |
| 6 | Local contract + gate (lean) | projected local contract (SEND/RECV table) | gate rejects violations | round-robin |
| 7 | Local contract + gate, no turn hint | as 6, minus per-turn liveness nudge | gate rejects violations | round-robin |
| 8 | Full STJP | as 6 | gate rejects violations | **EFSM-driven** |

The ladder isolates: *knowledge* (1→3), *localization* (3→4), *enforcement*
(4→6), *the liveness hint* (6→7), and *scheduling* (7→8).

### 5.2 The MAF kinds (real Microsoft Agent Framework)

Three MAF kinds run on every case × both models × n, alongside the ladder:

| MAF kind | Protocol info | Delivery | Question it answers |
|---|---|---|---|
| `maf_groupchat` | none | MAF GroupChat, LLM speaker-select | Can the MAF runtime coordinate on its own? |
| `maf_groupchat_llmvalid` | full validated protocol text to **every** participant | MAF GroupChat, LLM speaker-select | The earlier report's `maf` arm, kept identical for comparability |
| `maf_groupchat_llmvalid_orch` | **orchestrator** holds the protocol; each participant holds only its projected local contract | MAF GroupChat, LLM speaker-select | Does the natural orchestrated design do better / cheaper? |

Appendix-only MAF controls (not in the per-case matrix): `maf_native`,
`maf_foundry` (runtime baselines), `maf_groupchat_global` (same text,
canonical source), `maf_groupchat_unsafe` (deadlock negative control — the
Scribble-rejected protocol; used where an unsafe draft exists).

### 5.3 Mapping to the earlier 5-configuration report

| Earlier report's arm | This plan | Note |
|---|---|---|
| `bare` | setting 1 | intent only |
| `maf` | `maf_groupchat_llmvalid` | not a ladder setting; a MAF kind |
| `min_llmvalid` | setting 4 | local contract, observe-only |
| `gate` | setting 6 | local contract + gate (lean) |
| `sched` | setting 8 | Full STJP |

---

## 6. Cases

Twelve real/purpose-built cases plus memory_race, ordered by coordination
complexity. Nine compose **real published skills** (AutoGen, OpenAI Agents
SDK, LangGraph, CrewAI, awesome-copilot, AgenticPay); finance is purpose-built
(6 roles, value-dependent audit branch, 6 goals); agenticpay_settlement is
the escrow-sequenced linear case (4 roles, strict deposit→ship→release→settle,
4 goals); memory_race is the authored read-modify-write race (a lost update
Scribble's deadlock check alone cannot catch, verified by a stateful world
oracle). Each case declares its own S4 catastrophe. Full stories: 7_RUN.

---

## 7. Result tables the campaign produces

For each case, and in the model-scaling / cost / cross-case summaries, the
report reproduces the earlier report's table shapes:

1. **Main per-case table** — per setting and MAF kind, both models
   side-by-side: goal completion % with Wilson 95% CI, violation rate (Set A),
   disaster trials (S4), calls/trial, tokens/trial. Provenance line names the
   exact run folder per model.
2. **Per-goal table** — strict completion per goal (G1…Gk) per setting,
   to localize *where* a configuration regresses (e.g. a terminal-goal
   budget-exhaustion vs a structural failure).
3. **Model-scaling table** — Mini → Full delta per setting on completion and
   tokens, classifying each into the three regimes: *enforcement-independent*
   (constant), *positively scaling* (needs the frontier model),
   *negatively scaling* (knowledge-only trap).
4. **Cost decomposition / scheduling dividend** — calls/trial, tokens/call,
   tokens/trial, savings vs. bare; shows the saving comes from *fewer calls*,
   not shorter ones, and (separately) the history-re-reading compounding.
5. **Cross-case comparison** — the scheduling dividend as a function of
   protocol complexity (linear → branching → looping).
6. **Fair-comparison note** — the per-setting prompt-content table, the
   shared-prose adjustment (what is normalized away and why; what is the
   treatment and must not be), and the settings 1–2 violation caveat.

---

## 8. Design principles the report will defend

1. **Type safety does not imply progress.** A configuration can hold zero
   violations and still fail half its goals when the session exhausts its
   steps; progress needs a scheduler that polls only enabled roles.
2. **Model scaling is not a substitute for structural enforcement.** A
   stronger, more verbose model with no enforcement can regress (each message
   correct, the budget exhausted before the terminal goal). "Use a bigger
   model" is not a fix.
3. **The cheapest correct system is the most constrained.** The scheduler's
   savings come from *not making calls whose answers cannot advance the
   protocol* — the EFSM's enabled-set at each state is exactly the set of
   roles worth polling.

---

## 9. Execution order and status

Deployment rule: **one job per model deployment at a time** (parallel across
deployments; strictly one launcher). Stalls measured from launch time.

1. **In progress:** memory_race n=10 re-runs on both models (value-layer fix
   verified; occupying both deployments).
2. **Next — hosted-group campaign (§2.1):** redeploy the seven groups per
   model, author the six missing case groups, invoke n=10 per model, grade,
   add the hosted-group rows. *This is the standing hosted-agent requirement.*
3. **Then — MAF campaign (§5.2):** three MAF kinds × all cases × both models,
   after a 1-trial smoke of `maf_groupchat_llmvalid_orch` confirming the
   persisted orchestrator prompt carries the protocol.
4. **Then — any ladder re-runs** needed for X > 10.
5. **After each stage:** verify (independent re-derivation + S4 policy scoring
   + per-goal + fragile-goal audit), add only verified rows, commit evidence
   to origin and sync to the upstream benchmark repo.

Nothing enters a report table before its run completes at the full n and
passes verification. A partial or in-flight run is never citable.
