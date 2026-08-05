# STJP Benchmark Plan v3 — the design and reasoning behind the campaign

> ## ⚠️ READ THIS FIRST — current state (2026-08-05)
> This is a long design document that grew in layers. **The numbers in the
> title, in §1's older bullets, and in §5 describe earlier versions of the
> plan.** The current campaign is:
> - **9 setups** (called "arms"), not 8 — the authoritative list, with plain
>   meanings and old-name mapping, is **§10.8**.
> - **4 AI models**, not 2 — see the "AI models" bullet in §1.
> - New readers and any agent taking over the work should start from
>   **[`BENCHMARK_HANDOFF.md`](BENCHMARK_HANDOFF.md)**, which is the single
>   clean entry point: it lists every document, the 9 arms, the reasoning,
>   and the exact steps to run the campaign. Come back here only for the
>   full design rationale.
> Sections §2–§9 and §10.1–§10.7 are kept as written to preserve the design
> history; where they say "8 settings", "2 models", or old arm names, §10.8
> and §1 override them.

**Date: 2026-08-01 (design), amended through 2026-08-05.** This is the design
document for the STJP real-case benchmark campaign — why it is built the way
it is. It supersedes `reference/BENCHMARK_PLAN_V2.md`. It states what runs,
where it runs, which tools must be installed, how results are graded, and
what result tables the campaign produces. The step-by-step "how to run it" is
[`BENCHMARK_IMPLEMENTATION_STEPS.md`](BENCHMARK_IMPLEMENTATION_STEPS.md).

---

## 1. Scope and parameters

- **Trials per cell:** n = X, **X = 10 now**, raised later (30+ for headline
  claims) without changing any other part of the plan.
- **AI models (all four, in every test cell — revised 2026-08-05): a
  balanced 2-by-2 set.** We test two model "families" (closed-source and
  open-weight) at two strength levels (strong and weak): **gpt-5.6-sol**
  (closed-source, strong; capacity 500), **gpt-5-mini** (closed-source,
  weaker; keeps every earlier published Mini result comparable),
  **DeepSeek-V4-Pro** (open-weight, strong; deployed 2026-08-05,
  GlobalStandard capacity 500), and **DeepSeek-V4-Flash** (open-weight,
  weaker; the same 2026-04-23 model generation as V4-Pro, but a
  smaller/faster version, capacity 125 — a pure size difference inside the
  open-weight family, mirroring the sol-vs-mini difference inside the
  closed family). This lets us classify the three ways performance can
  scale with model strength (no effect from enforcement / gets better with
  a stronger model / gets worse with a stronger model) **separately for
  each family**, and lets us claim "the scheduler's benefit does not
  depend on which model you use" using both families as evidence. All four
  are deployments on the same Foundry account. Older `gpt-5.4` results
  stay in their own historical column (never combined with
  `gpt-5.6-sol`); `DeepSeek-V3.2` stays deployed but is not used as a test
  column. Both DeepSeek models need one small check run per setup before
  they can be used in the campaign, because their output-formatting habits
  differ from the other family's.
- **Pre-registered appendix probes (never full matrix columns):**
  **gpt-5-nano** capability floor, one case: at what model size does even
  enforcement stop rescuing the team? Named reserves, run only if a
  reviewer or an anomaly demands them: **qwen3-32b** (second open-weight
  *family* — the rebuttal to "all your open points are DeepSeek";
  GlobalStandard in-region, not deployed;
  `az cognitiveservices account deployment create ... --model-name
  qwen3-32b --model-format Alibaba --sku-name GlobalStandard`) and
  **Kimi-K2.6** (third large open family). DeepSeek-R1-class reasoning
  models are excluded deliberately: their long-reasoning token profiles
  are not comparable on the primary cost metric.
- **Cases:** the real-skill / purpose-built cases (see
  [`BENCHMARK_CASE_RANKING.md`](BENCHMARK_CASE_RANKING.md) for the full list and the order to
  run them). Each declares its own worst-possible-failure ("catastrophe").
- **Matrix per case (current):** **9 arms × 4 models × n trials** — the 9
  arms are listed in §10.8; the 4 models are the bullet above. (The older
  "8 settings + 3 MAF kinds × 2 models" wording elsewhere in this file is
  superseded.)
- **Balanced branches:** cases with a decision point split trials equally
  across the branches, so no arm is helped or hurt by drawing easier cases.

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

### 2.2 Classic Agent Service (the per-message-control surface) — SUPERSEDED

> **Superseded 2026-08-05 by
> [`BENCHMARK_IMPLEMENTATION_STEPS.md`](BENCHMARK_IMPLEMENTATION_STEPS.md):**
> the campaign runs on **Foundry Hosted Agents only** (azd-deployed hosted
> groups; classic agents are not used). The per-message gate and the EFSM
> scheduler move *inside* each group's authored WorkflowAgent, so
> settings 5–8 are expressible on the hosted surface after all. The text
> below is retained for the historical record of pre-supersession runs.

The 8-setting ladder needs per-message interception (the monitor gate) and
per-turn control (the scheduler). These run on the Foundry **Agent Service**:
one classic agent per role per setting (`stjp-<case>-<setting>-<role>`) and
one thread per role per trial. These appear in the portal's
previous/classic agents view (NOT the "New Foundry" page). Visibility rules
and deep links: `reference/FOUNDRY_VISIBILITY.md`.

### 2.3 Evidence, three layers, every trial

1. **Local:** `experiments/cases/<case>/runs/<dir>/events_*.jsonl`,
   `summary.json`, `summary_policy.json`, `summary_eval.json`, the
   persisted per-role prompts under `prompts/<setting>/`, **and the exact
   user-intent text the run used as a standalone `intent.md` at the run
   root** (provenance header: source, scale, sha256, size — see §10.4;
   `intent_distilled.md` + `role_briefs.yaml` are copied alongside when the
   distillation front-end produced them).
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

> Arm names superseded — see §10.8.

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
| `maf_groupchat` | none; **orchestrator holds the intent**, participants hold distilled role briefs (repaired 2026-08-05, §10.3; pre-repair broadcast twin: `maf_groupchat_legacy`) | MAF GroupChat, LLM speaker-select | Can the MAF runtime coordinate on its own? (MAF used as designed) |
| `maf_groupchat_llmvalid` | participants: distilled brief + validated protocol text; **orchestrator holds the intent** (repaired 2026-08-05; pre-repair broadcast twin: `maf_groupchat_llmvalid_legacy`) | MAF GroupChat, LLM speaker-select | Does pasting the validated protocol to every participant coordinate the group? |
| `maf_groupchat_llmvalid_orch` | **orchestrator** holds intent + protocol; each participant holds only its projected local contract (byte-identical to the `min` ladder prompts) | MAF GroupChat, LLM speaker-select | Does the natural orchestrated design do better / cheaper? (= "MAF + STJP compile-time artifacts") |

All three kinds are **implemented** in `baselines/registry.py`. The arm
keys are unchanged from V3 so existing runbooks and reports keep working;
what changed on 2026-08-05 is the **prompt policy behind the same keys**
(the repair, §10). Pre-repair rows are identified by
`prompts_schema_version: 1` (absent) in their `prompts/<arm>/index.json`;
repaired rows carry `prompts_schema_version: 2`. Never mix the two eras in
one table column. The pre-repair broadcast prompts remain runnable as
`*_legacy` via `--arms`, e.g. to price the broadcast confound.

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

**Priority order:** [`BENCHMARK_CASE_RANKING.md`](BENCHMARK_CASE_RANKING.md) ranks every runnable
case (role count, developer/industry applicability, provenance, protocol
richness) into a 6-case headline tier, a supporting tier, and a
no-campaign-budget tier — use it to sequence the campaign.

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

---

## 10. V3.1 amendment (2026-08-05): a more realistic task description, given out fairly

We found two fairness problems in our original (V3) design. Both are about
the **user's task description** — this project calls it the "intent," what
the user actually wants done — and both are now fixed in our test-running
code. This section is the written record of that design decision; the
actual code fix landed the same day, in these files: `instructions.py`,
`registry.py`, `case_loader.py`, `case_runner.py`, `maf_groupchat.py`,
`scripts/intent_pipeline.py`.

### 10.1 The two problems

**Problem A — the task description we tested with was unrealistically
short.** Every case's task description was just a 5-line paragraph in its
`case.yaml` settings file. Real task descriptions are whole documents — for
example `docs/handbook_markdown.pdf`, about 300 KB in size — where the
actual requirements are buried in background information, policy text, and
formatting. In real life, someone (or some front-end tool) has to *ask
questions* and *boil the document down* to the real goals before any team
can start work. Our benchmark did not model that step, or count its cost
anywhere. And at paragraph length, the cost of including the task
description is too small to show the real difference our approach claims
to make: that giving each role only its own instructions (a technique we
call "projection") should save more, the bigger and more complex the task
description is.

**Problem B — our comparison setups ("baselines") sent the whole task
description to every single role.** We checked the actual saved prompts
from a real run
(`finance/runs/20260727T182045-gpt-54-p65284-n10-dual/prompts/`) and
confirmed:

- the `bare` setup put the **full task description and goals into all six
  roles' instructions** (about 1.9 KB each, times 6 roles — re-sent on
  every single AI call);
- the `global_decentralized` setup put the task description plus the
  entire protocol into every role (about 6.1 KB each, times 6 roles);
- the `maf_groupchat` setups put the full task description into **every
  participant AND the orchestrator** (the planning role) — which is not
  even how Microsoft's Agent Framework (MAF) is meant to be used: normally
  the orchestrator does the planning, and participants just receive
  assigned tasks;
- our own `min` (STJP) setups carried **no task description at all** —
  only about 1.2–2.3 KB of each role's own local instructions.

At paragraph length, this unfairness is small, so our 23 already-published
test runs on the step-by-step ladder of setups (see §10.5) are still valid
*at that short length* — their prompts are unchanged, word-for-word. But at
real document length, our original design would have compared "every role
carries the entire handbook" against "no role carries anything" — the
savings we measured would partly just reflect an unfairly weak comparison
setup. On top of that, on the Azure Foundry platform, the broadcast setups
would have silently gotten cut off at its 8,000-character prompt limit.

### 10.2 The fair intent-carrying principle

> **The full task description goes only to whichever part of the system
> does the planning for that design. Individual worker roles carry only
> their own, role-specific instructions.**

Each design now pays its task-description cost only where it genuinely
belongs:

| Design | Who reads the full task description | When that cost is paid |
|---|---|---|
| **STJP** (our approach) | whoever drafts the protocol (stage S1) | **once, when the protocol is written** (already counted and disclosed) |
| **MAF** | the **orchestrator** role (kept in its own instructions) | **on every turn it picks the next speaker**, while the test is running |
| **Bare group** (no protocol at all) | the "distillation front end" — a person or an AI that writes short per-role briefs, exactly as real teams do | **once, when the team is set up** (disclosed in §10.3) |

This makes the case for our approach (STJP) stronger, not weaker: we now
measure our savings against comparison setups that *also* keep the full
task description away from individual roles. What's left to measure is the
real structural benefit — validated message ordering, the safety checker,
and the scheduler — not just the trivial saving of "don't send everyone the
whole handbook." We kept the old broadcast-everything setups around (under
the "legacy" label) specifically so we can measure the size of that old
unfairness: `bare_legacy` compared to the corrected `bare`, and
`maf_groupchat_legacy` compared to the corrected `maf_groupchat`, differ
**only** in whether the task description is included in worker
instructions — we verified this with a direct line-by-line file comparison
("diff").

**Our core set of 7 setups (same names as in our published tables).** Our
fix keeps the long-standing setup names (this project calls a setup an
"arm" — one configuration being tested, such as with or without a safety
checker) — so a colleague can re-run the exact same commands and simply get
the corrected prompts back. The code list `registry.SCENARIOS` holds the
five-setup ladder that every one of our published findings came from
(`bare`, `maf`, `min_llmvalid`, `gate`, `sched`), plus the two extra
MAF-based setups added for the fair-comparison question. Setups whose
prompt rules changed are marked *(repaired)*:

| # | arm key (core matrix) | what the worker's instructions include | what the planner includes | how success is graded |
|---|---|---|---|---|
| 1 | `bare` *(repaired)* | a short, distilled role brief, plus goals/roles/ending-condition text shared by everyone | — (the brief's cost was paid once, at team set-up) | role_pair† (looser match) |
| 2 | `min_llmvalid` | each role's own short, projected instructions ("local contract"); watched but not enforced | task description used only once, when the protocol was written | strict (exact match) |
| 3 | `min_llmvalid_gate` | same short local instructions, plus the safety checker | " | strict |
| 4 | `min_llmvalid_sched` | same as the gate setup, plus the scheduler (**this is full STJP**) | " | strict |
| M1 | `maf_groupchat` *(repaired)* | same brief as `bare` (**MAF with nothing else added**) | orchestrator holds the full task description | role_pair† |
| M2 | `maf_groupchat_llmvalid` *(repaired)* | brief plus the full validated protocol written out as text (our previously published `maf` setup) | orchestrator holds the full task description | strict |
| M3 | `maf_groupchat_llmvalid_orch` | each role's own short, projected instructions — word-for-word identical to the `min_llmvalid` prompts (**this is MAF plus STJP**) | orchestrator holds the full task description plus the validated protocol | strict |

**Our extra comparison setups (5 setups, in `registry.ABLATION_SCENARIOS`)**
— these are only run, using the `--arms` option, on the specific case(s)
where they matter, never on every case: `min_llmvalid_gate_lastrecv`
(**must run on at least 1 branching case per campaign** — our scheduler's
time savings are only a fair claim if they beat the cheap "ask whoever
received the last message" shortcut with no protocol at all — see
FAIRNESS_REVIEW, Problem 4); `min_llmvalid_gate_nohint` (blocking the
sender vs. just hinting at what to do, addressing Problem 5; run on one
case); `spec_llmvalid_gate` (how much detail the instructions include,
ladder setting 5; one case); `global_decentralized` *(repaired)* (full
protocol text vs. each role's own instructions, setting 3; one case);
`unchecked_skills` (our deadlock demonstration, setting 2; only on cases
that have a version where roles can get stuck waiting on each other).

The safety checker and the scheduler still cannot be inserted inside MAF's
own, closed-off group chat system (our honesty note in §2.1 still applies):
`maf_groupchat_llmvalid_orch` only measures MAF combined with the files
STJP generates ahead of time; the complete STJP system (with live
enforcement) is measured separately, on the classic surface (ladder
settings 5 through 8).

**Marking old vs. new results.** Because the four corrected setups keep
their original names, every test run's file `prompts/<arm>/index.json` now
carries a tag, `prompts_schema_version: 2`. Rows from before the fix (which
have no version tag, meaning version 1) must never be shown in the same
results-table column as version-2 rows, for those four setups. Each run's
`intent.md` file and each role's prompt fingerprint (a "sha256," a short
unique code) make it easy to check mechanically which version a row
belongs to.

**Old ("legacy") setups (8 of them) — not run by default, only with
`--arms`.** The code list `registry.LEGACY_SCENARIOS` keeps these
runnable: `bare_legacy`, `global_decentralized_legacy`,
`maf_groupchat_legacy`, `maf_groupchat_llmvalid_legacy` (the old,
pre-fix broadcast-everything prompts of the setups with the same names —
run one next to its corrected twin to measure exactly how much the old
broadcasting unfairness was worth); `maf_native`, `maf_foundry` (plain
runtime comparisons, appendix only); `maf_groupchat_unsafe` (our **safety
negative-control test** — deliberately causing deadlock on a protocol
Scribble rejects; this is never used for a token-cost claim, so its
broadcast prompt doesn't cause a problem here); and `spec_llmvalid` (a more
verbose, watch-only version of the contract, replaced by `min_llmvalid`
which does the same job at about 46% of the token cost — not part of the
main ladder). The old broadcast-everything prompts remain **invalid for
measuring efficiency at document scale**: their token cost mixes together
"writing out the whole protocol" with "sending the whole task description
to everyone," and at document length they get cut off by Foundry's
8,000-character prompt limit anyway.

**An openly disclosed, deliberately cautious imbalance.** Our
fairly-designed comparison setups' workers carry a short distilled brief
that our own `min` (STJP) workers do not — the STJP prompts stay
word-for-word identical to our already-published runs. This means the
comparison setups actually carry strictly *more* task-related text than
our own approach does. This works **against** our own approach: if STJP's
projected instructions still win on token cost and completion rate despite
this handicap, that makes the result stronger, not weaker. (If we ever add
briefs to the STJP setups too, that would count as a new prompt version —
see `experiments/CLAUDE.md`.)

### 10.3 The intent pipeline (write → ask questions/boil down → brief)

The script `scripts/intent_pipeline.py` builds, for each case, a set of
files under `experiments/cases/<case>/intent/`:

1. **`author`** — writes `intent.md`, the full, document-length task
   description. Where it came from is recorded in `provenance.json`, as
   either **`git`** (quoted *word-for-word* from the real project's own
   repository, when it clearly states its own intent — our preferred
   source) or **`llm_authored`** (a realistic-sounding stakeholder document
   written by an AI model from the case materials, covering every goal in
   prose). An automatic **label-leak guard** rejects any draft that
   contains a message label from the real or AI-drafted protocol —
   otherwise, setups that are supposed to "never see the protocol's
   vocabulary" would secretly get handed the answer key.
2. **`distill`** — the "ask questions and boil it down" step. Produces
   `intent_distilled.md` (the mission, the distilled goals, any
   constraints, and how to know the job is done) and `role_briefs.yaml`
   (one short brief, no more than 700 characters, per role). These briefs
   are given, word-for-word, to **every** comparison setup that is
   supposed to be fair — so they are the same fixed text everywhere, not
   an advantage for any one setup. The label-leak guard checks these too.
3. **`check` / `approve`** — the goal-coverage check. The exact-match
   rules written in each case's `case.yaml` file remain the only true
   answer key (this rule is called "answer-key invariance" in
   FAIRNESS_REVIEW, Problem 2 — boiling down the text can reword the
   goals, but can never change what actually gets graded). A person signs
   off that the distilled goal list covers every original goal (recorded
   as `goals_coverage_approved` in `provenance.json`). No loose or
   approximate text-matching is ever used as proof.

**We disclose the cost of this setup step:** every AI call this pipeline
makes is tracked in `provenance.json` and reported as a one-time
"distillation" cost line, alongside the already-disclosed cost of drafting
the protocol. (We estimate this cost as roughly one token per 4
characters, because Foundry's utility tools don't report exact usage
counts — this approximation is stated directly in the file.)

**Computer-generated mode — our default for the whole campaign.** Building
the task-description package is a **separate step done before testing
starts**, not part of the test run itself. Before a campaign, running
`intent_pipeline.py synth --all` prepares every case automatically,
without anyone watching: it writes the document if `intent.md` doesn't
exist yet, boils it down, runs an **automatic AI check** that every
original goal is still covered, and approves it automatically. This means
that by the time the AI roles actually start working, the task description
has already been "written, boiled down, and approved," so no setup ever
has to stop mid-campaign because something is missing. Because no person
reviews each individual package, the approval is recorded as
`approved_by: "auto-llm"`, together with the per-goal coverage results —
this is our openly disclosed label that the task-description package is
**computer-generated** (close to a real one, but produced entirely by
machine, start to finish). Every report must state this openly. A person
can still approve one by hand (recorded as `approved_by: "human"`), which
overrides the automatic approval and is never later overwritten by a fresh
automatic run. If the automatic coverage check still fails, even after one
automatic retry, the process stops with a clear error and no approval is
recorded — a case that can't be boiled down faithfully must be fixed by
hand, never silently tested anyway. This automatic coverage check is only
a setup tool; it never affects grading — the exact-match rules in
`case.yaml` remain the only true answer key.

### 10.4 Two lengths of task description, and how we save them

Test runs use one of two lengths, chosen with the setting `case_runner.py
--intent-scale {short,doc}`:

- **short** (the default): the short paragraph from `case.yaml`. All of
  the old prompts stay word-for-word unchanged, so existing results stay
  comparable.
- **doc**: the full document, `intent/intent.md`, is used as the task
  description. Only the parts of the system that are supposed to read the
  full task description (the old broadcast-everything worker setups, the
  MAF orchestrator, and the protocol drafter/distiller) actually receive
  the document. Our fairly-designed worker prompts do not change at all
  when we switch to this longer length — that lack of change **is** the
  very thing we're testing.

Every test run saves the exact task-description text it used, in a file
called **`runs/<dir>/intent.md`** (a standalone file with a header
recording where the text came from, its length setting, a fingerprint —
"sha256" — and its character count), plus copies of `intent_distilled.md`
and `role_briefs.yaml` when those exist. A run without an `intent.md` file
at the top of its folder is not considered a complete, auditable record.

### 10.5 What this fix changes, and what it doesn't

- The prompts for ladder settings 2 and 4 through 8 are **unchanged,
  word-for-word** (we checked this against the saved files from the
  2026-07-27 finance test run). Settings 1 and 3 (`bare` and
  `global_decentralized`) and the MAF setups keep their names, but now
  carry **corrected prompts** as of 2026-08-05 (tagged
  `prompts_schema_version: 2`). Our 23 already-published, citable test
  runs still stand as **version-1, short-length results**; any results
  table that mixes old and new versions for the four corrected setups must
  clearly split its rows by version. Settings 1 and 3 must be re-run under
  version 2 before those two rows can be shown alongside new results.
- The MAF campaign (§9, step 3) has **not** run yet — it will now run
  using the fair setups as its headline results, so none of our existing
  MAF results are affected.
- We are adding a new headline table (making a seventh kind of result
  table for §7): **intent-scaling** — showing goal-completion rate, tokens
  per test run, and calls per test run, for each setup family, at both the
  short and document length. We expect this to show: the fair comparison
  setups' worker cost staying flat; the MAF orchestrator's cost growing as
  the document gets bigger (because it makes more speaker-selection
  calls); the old broadcast-everything setups' cost exploding (or getting
  cut off); and our STJP setups staying flat, apart from a one-time,
  openly disclosed cost when the protocol is compiled.
- Grading rules are unchanged: setups using our fair task descriptions
  never see the protocol's own vocabulary, so they're graded with the
  looser role_pair† rule; `maf_groupchat_llmvalid_orch`'s participants
  carry each role's own local instructions, so that one is graded with the
  strict rule (this is recorded in the code list
  `evaluate_run.VOCABULARY_ARMS`).

### 10.6 Why we chose exactly these seven setups

> Arm names superseded — see §10.8.

Our previously published results (`sections_eval_results`) got **every
single** headline result from just five setups — `bare`, `maf` (short for
`maf_groupchat_llmvalid`), `min_llmvalid`, `gate`, `sched` — because that
step-by-step ladder isolates exactly one change per step: *does giving the
role knowledge of the protocol help* (bare → min_llmvalid); *does
enforcing it help* (min_llmvalid → gate); *does scheduling turns help*
(gate → sched); with MAF's own AI-driven turn-picking included as the
realistic industry alternative. Concretely: Finding 1 (the scheduler's
benefit doesn't depend on the AI model) needs `sched`; Finding 2 (knowledge
alone makes things worse, by 40 percentage points) needs `min_llmvalid`;
Finding 3 (the safety checker and MAF both get better with a stronger
model) needs `gate` and `maf`; Finding 4 (a 4.6-to-6.9-times cost gap at
equal completion rates) needs all five; Finding 5 (the up-and-down pattern
across the ladder) needs all five. None of our results tables use ladder
settings 2, 3, 5, 7, or the `lastrecv` shortcut comparison — those exist
only to *defend* our claims against specific objections. That is extra
("ablation") work, not part of the main test grid.

The fair-comparison question — "plain MAF, vs. MAF plus STJP, vs. our own
group plus STJP" — adds exactly two more setups: `maf_groupchat` (MAF
completely on its own, with no protocol at all) and
`maf_groupchat_llmvalid_orch` (MAF combined with the files STJP builds
ahead of time). That makes seven core setups per test cell. Any setup
beyond these seven must state exactly which objection it is meant to
answer, and which case it runs on.

### 10.7 Updated benchmark rules — what changed from our published methodology

Our previously published grading method (from `sections_eval_results`: the
Set A / Set B checks, the S0–S4 severity scale, strict vs. role-pair
grading, Wilson and Fisher statistics, tokens as our main cost measure,
evenly-split branches, and our five-finding report structure) **stays
exactly the same**. Everything listed below is the *complete* list of what
changes for a campaign run after this fix. Anything not listed here is
unchanged.

**Rule R1 — a new table defining each setup (replaces our previously
published Table 1).** We now separate "what information about the protocol
is given" into two parts: what the WORKER role's instructions carry,
versus what the PLANNER (or orchestrator) carries. The full
task-description document itself is never placed in a worker's
instructions:

| Arm | What the worker's instructions include | Planner, and where the task description lives | Enforcement (blocked or just watched) | Who picks the next turn |
|---|---|---|---|---|
| `bare` | a short, distilled role brief | the distiller (a one-time setup cost) | none | fixed turn order (round-robin) |
| `min_llmvalid` | each role's own short, projected instructions | the protocol drafter (paid once, when the protocol is written) | none (only watched) | fixed turn order |
| `gate` (`min_llmvalid_gate`) | same projected instructions | " | the checker blocks bad messages | fixed turn order |
| `sched` (`min_llmvalid_sched`) | same projected instructions | " | the checker blocks bad messages | **driven by the state-diagram (EFSM) scheduler** |
| `maf_groupchat` | a short, distilled role brief | **the orchestrator's instructions** (paid on every turn it picks a speaker) | none | the AI itself picks the next speaker |
| `maf` (`maf_groupchat_llmvalid`) | brief plus the whole validated protocol, written out as text | orchestrator's instructions | none | the AI picks the next speaker |
| `maf_orch` (`maf_groupchat_llmvalid_orch`) | each role's own short, projected instructions (identical to the `min_llmvalid` prompts) | orchestrator's instructions plus the whole protocol | none | the AI picks the next speaker |

("Round-robin" means a fixed order, taking turns one role after another.
"EFSM-driven" means the scheduler uses a state diagram of each role's
allowed next moves — an "EFSM" — to decide whose turn is genuinely useful
right now. "LLM speaker-select" means the AI itself decides who speaks
next.)

The ladder still isolates one thing at a time: knowledge (`bare` →
`min`), enforcement (`min` → `gate`), and scheduling (`gate` → `sched`).
The MAF block now additionally isolates two more things: which system runs
the team (`min` vs. `maf_orch` use identical worker instructions, so the
only difference is MAF vs. our own runtime), and how the protocol is given
to roles (`maf` vs. `maf_orch` use the same runtime, but one gives the
whole protocol as text and the other gives each role its own short slice).

**Rule R2 — the shape of the test grid.** Every case × **4 AI models**
(the 2-by-2 set: gpt-5.6-sol / gpt-5-mini / DeepSeek-V4-Pro /
DeepSeek-V4-Flash, see §1) × **7 setups** (previously 2 models × 5
setups), with the number of runs per §1, plus the pre-planned
`gpt-5-nano` capability-floor test.
Grading: `bare` and `maf_groupchat` use the looser role_pair† rule (since
they never see the protocol's own vocabulary); the other five setups,
which are shown the protocol, use the strict rule. The grading steps
themselves and what counts as success are unchanged.

**Rule R3 — which of our published numbers we can still use.** The
`min_llmvalid`, `gate`, and `sched` rows in our published tables used
prompts that are **still word-for-word identical today** — those numbers
can still be cited and combined with new runs. The published `bare` and
`maf` rows are from the **old, version-1 (broadcast-everything) prompts**:
they can still be cited as historical version-1 results, but any new table
can only show them in a column clearly labeled "version 1," or must
re-run them under version 2. As a result: Findings 1 and 2 (the
scheduler's benefit doesn't depend on model; knowledge alone makes things
worse) still stand without re-running anything; Findings 3 through 5, and
every "savings compared to `bare`" figure, must be recalculated once
`bare` and `maf` are re-run under version 2 (we expect little change at
short length, since the brief and the short paragraph are similar in
size — it's the document-length runs where version 1 and version 2 are
designed to diverge).

**Rule R4 — requirements before any test run on a case (new).** Before
any test run: (a) the task-description package must exist and be approved
(built with `intent_pipeline.py synth --all`; if it was
computer-approved, `approved_by: auto-llm`, the report says so openly);
(b) the AI-drafted protocol files must already exist; (c) the
`tool_preflight` startup check must pass. Every test run saves
`intent.md` (plus its distilled copies) at the top of its folder.

**Rule R5 — what we disclose (extended).** Our one-time setup-cost table
now has an added **distillation** row (tracked in `provenance.json`,
estimated as roughly 1 token per 4 characters, stated as an estimate),
next to the existing protocol-drafting cost row. The MAF setups' per-run
token counts naturally include the orchestrator's cost of carrying the
task description — that's a real feature of how MAF works, not a mistake
in our test, and we call it out clearly in our fair-comparison note. We
also disclose the deliberately cautious imbalance: our comparison-setup
workers carry a distilled brief that our own `min` (STJP) workers do not.

**Rule R6 — required extra checks (replaces the old "run every setup on
every case" rule).** Run `min_llmvalid_gate_lastrecv` on at least 1
branching case per campaign (our scheduler's benefit must beat the cheap
"ask the last receiver" shortcut, not just beat a fixed turn order); run
`unchecked_skills` wherever a version with a possible stuck-waiting loop
exists (this keeps the evidence behind our deadlock demonstration); run
the other three extra checks on one case each, and cite them in the
appendix.

**Rule R7 — a new headline results table.** The intent-scaling table (see
§10.4 and §7): our 7 setups, tested at both the short and document
length, reporting completion rate, tokens per test run, and calls per
test run — this is the actual measured evidence for our claim that
"giving each role only its own instructions keeps costs down as the task
description grows." As before, we only report timing (wall-clock) results
from runs done one at a time (`--sequential`).

### 10.8 Final arm naming (2026-08-05)

**Scope note.** This section is the single authoritative rename table for
this document. Everywhere ELSE in this file (§5 onward, including §10.1
through §10.7) still uses the setup names as they stood at the time each
of those sections and findings were written — that is deliberate: those
sections are a historical record of what was decided and published under
those names, and rewriting them would misstate history. Every new campaign
run, new report, and new piece of code from this date forward uses ONLY
the names in the table below; every old name below is a LEGACY alias,
resolvable but no longer used going forward (see "where the rename was
implemented," at the end of this section).

**The problem this fixes.** Our setup names had drifted into two
unrelated vocabularies that didn't describe what they meant: `bare` /
`maf_groupchat` (which nobody could tell apart from their names alone —
one is round-robin, one is Microsoft's own group-chat tool), and the
`min_llmvalid*` / `maf_groupchat_llmvalid*` family (a leftover from an
early internal codename, "min," for the terse per-role instruction
format). The project owner asked for one consistent, self-describing
vocabulary before the full campaign locks in its result-table headers, and
for the benchmark's baseline ("what if a team gets no formal protocol at
all?") to be built from a **real, published skill file** rather than an
abstract "the AI just gets the task description" control.

**The new rule for a setup's name**, going forward: `(maf_)?` (present
only if the setup runs on Microsoft's own group-chat tool, absent if it's
our own round-robin turn-taker) + `global` or `local` (whether a role's
instructions carry the WHOLE validated plan written out as text, or only
that role's own projected slice of it) + `valid` (a fixed word meaning
"drawn from the protocol our validator, Scribble, accepted as safe") +
`_gate` or `_sched` (present only if the safety checker blocks bad
messages, or additionally the state-diagram scheduler picks turns; absent
means round-robin turn order and a checker that only watches, never
blocks). The two setups that carry no protocol information at all (our
baseline) are named for what they actually are: `skills` and
`maf_skills` — a real, hand-authored, never-formally-checked per-role
skill file (the same files the deadlock demo in
`docs/results/RESULT_08_SKILL_SAFETY.md` uses), not an abstract
"no-information" control.

**The full rename table** (old name → still resolvable everywhere as a
LEGACY alias — an old-named run folder still summarizes and grades
correctly; it is never deleted or silently reinterpreted):

| new name | meaning | old name |
|---|---|---|
| `skills` | real published skill files (from `experiments/cases/skills_safety/sdlc_release_gate/skills_original` / `unchecked_skills`) + the user's task description; round-robin turn order; no protocol information at all | (replaces `bare` as our baseline) |
| `maf_skills` | the same skill files + task description, run on Microsoft's own group-chat tool instead of our round-robin turn-taker | (new) |
| `globalvalid` | the whole validated plan written out as text in every role's instructions; round-robin; the checker only watches, never blocks | `global_decentralized` |
| `maf_globalvalid` | the same whole-plan-as-text instructions, run on Microsoft's own group-chat tool | `maf_groupchat_llmvalid` |
| `localvalid` | each role's own validated, projected slice of the plan (a "local contract"); round-robin; the checker only watches, never blocks | `min_llmvalid` |
| `maf_localvalid` | the same per-role local contracts, run on Microsoft's own group-chat tool, with the orchestrator role holding the task description plus the whole plan | `maf_groupchat_llmvalid_orch` |
| `localvalid_gate` | the same per-role local contract, plus the checker now blocks rule-breaking messages before they're delivered | `min_llmvalid_gate` |
| `localvalid_sched` | the same as `localvalid_gate`, plus the state-diagram (EFSM) scheduler picks whose turn is next — our full STJP approach | `min_llmvalid_sched` |
| `maf_localvalid_sched` | Microsoft's own group-chat tool, per-role local contracts, but the next speaker is picked by the SAME state-diagram scheduler instead of an AI orchestrator role; no checker-blocking, because a hosted group-chat gives us no point to intercept a message before it's delivered | (new — see feasibility note below) |

Nothing else changes: this is a renaming of setup keys, not a change to
any setup's meaning, prompt content, or grading rule. Every prompt string
under a new name is byte-for-byte identical to what its old name used to
produce (checked mechanically — see
`experiments/scripts/tests/test_gate1_prompts_byte_identity.py`). `bare`
and `maf_groupchat` are not simply renamed — they are **replaced** as our
no-protocol baseline by `skills`/`maf_skills`, and demoted to
LEGACY-only aliases (still runnable, e.g. to reproduce an older cited
result, just no longer part of the core matrix). The three
already-published ablation-only setups (`min_llmvalid_gate_lastrecv`,
`min_llmvalid_gate_nohint`, `spec_llmvalid_gate`) are untouched — they are
not part of this 9-setup table.

**Feasibility of `maf_localvalid_sched` (checked before deciding to build
it).** Whether Microsoft's group-chat tool could be driven by our own
turn-picking rule, instead of always needing an AI orchestrator role to
pick the next speaker, was an open question until we read the installed
package's own source code. It can:
`agent_framework_orchestrations.GroupChatBuilder` accepts a plain
`selection_func` (a normal Python function, not an AI call) as a
documented, first-class alternative to `orchestrator_agent` — the two
options are mutually exclusive constructor arguments, and the library's
own example in that source file shows a deterministic round-robin
function used exactly this way. We built `maf_localvalid_sched` around
that: our own state-diagram (EFSM) "who has a valid move right now?"
rule, ported into that function, replacing the orchestrator entirely (so
this arm makes zero orchestrator AI calls). One thing this does NOT get
us: a way to block a rule-breaking message before it's delivered.
Microsoft's group-chat tool always broadcasts a role's reply to everyone
else the moment it arrives, before our turn-picking rule is even asked
who goes next — there is no hook in the library to intercept and reject a
message first. So `maf_localvalid_sched` isolates turn-scheduling only, on
Microsoft's own runtime; it has no gate-equivalent, and none is claimed.

**Where the rename was implemented** (so a reader can verify the claim
that nothing else changed): the shared setup list
`experiments/baselines/registry.py` (renamed keys, every old key kept as a
resolvable alias); `experiments/scripts/evaluate_run.py`'s
`VOCABULARY_ARMS` list (which setups get the strict grading rule) and
`experiments/scripts/case_runner.py`'s Foundry-vs-MAF setup lists;
`experiments/CLAUDE.md`'s setup table; the hosted-container setup list in
`foundry_hosted_agents/.../agents/sdlc_release_gate/main.py`
(`ARM_CONFIG`) and its artifact builder,
`experiments/scripts/build_hosted_artifacts.py`; and
`docs/reference/SDLC_HOSTED_WORKFLOW_SPEC.md`. See
`docs/BENCHMARK_IMPLEMENTATION_STEPS.md` §4.3 and `docs/BENCHMARK_CASE_RANKING.md`
for the same table applied to the run-order playbook.
