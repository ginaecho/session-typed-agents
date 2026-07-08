# STJP Documentation

Clean, organized guides to the Session-Typed Judge Panel (STJP) — the system for running session-typed agents safely. Start with section 1; read others as needed.

**Reorganized: 2026-07-03. Plain language, no jargon. Every term explained.**

---

## 🚀 Quick navigation

- **New to STJP?** → Start with `1_TECH_SETUP.md`
- **Want to understand the testing?** → Read `2_TESTING_STRATEGIES.md`
- **Need to run STJP locally?** → See `1_TECH_SETUP.md` section 5 ("Running STJP with Azure AI Foundry")
- **Creating your own use case?** → Follow `4_HOW_TO_CREATE_USE_CASES.md` step by step
- **Reading the benchmark results?** → Start with `5_RUN_REPORTS_EXPLAINED.md`
- **Understanding why safety matters?** → See `6_USE_CASE_DEADLOCK_SAFETY.md`
- **Running the nuscr / nuscribble compiler backend?** → See `reference/NUSCR_CLOUD_INSTALL.md` (install routes + `STJP_COMPILER_BACKEND=nuscr`)
- **Verifying the results from the raw traces?** → See `reference/HOW_TO_USE_TRACES.md` (re-derive every metric; read a trace by eye)
- **Real Anthropic + GitHub Copilot skills, run by two different models?** → See [`results/RESULT_9_REAL_SKILLS_TWO_MODELS.md`](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md)
- **Which developer use cases fit STJP (interview format)?** → See [`FABLE5_INTERVIEW_DEV_USE_CASES.md`](FABLE5_INTERVIEW_DEV_USE_CASES.md)

---

## 📚 The Four Sections

### Section 1: Tech Setup — `1_TECH_SETUP.md`

Everything you need to understand STJP technically.

What you'll learn:
- What Scribble is and why it matters
- How STJP extends Scribble (refinements, composition, higher-order)
- How STJP works end-to-end
- The glossary — every term explained in plain English
- How to set up hosted agents with Azure AI Foundry
- How the execution plane (scheduler) saves tokens

**Read time:** 15 minutes

---

### Section 2: Testing Strategies — `2_TESTING_STRATEGIES.md`

How we test STJP fairly, and why it took multiple tries to get it right.

What you'll learn:
- The four claims STJP makes (deadlock-freedom, interaction correctness, token savings, time savings)
- The evolution of our testing approach (mistakes we made, lessons learned)
- The fairness rules (one variable per comparison, no confounding)
- Two axes and four task shapes (how to design an unconfounded benchmark)
- How we grade results (GCR, CGC, cost-to-goal)
- The current 7 arms and what changed between them

**Read time:** 20 minutes

**Why this matters:** Without fairness rules, benchmarks lie. This section teaches you what a good benchmark looks like.

---

### Section 3: Benchmark Design Explained — `3_BENCHMARK_DESIGN_EXPLAINED.md`

How we measure STJP's impact and why the measurements matter.

What you'll learn:
- What a benchmark is (a fair comparison)
- The measurements: correctness (GCR, CGC), efficiency (tokens, cost-to-goal), adherence (violations)
- The three gating layers (completion → safety → efficiency)
- Severity grading (S0 to S4, from benign to disaster)
- Critical properties (C1 data provenance, C2 context completeness, C3 authorization)
- A concrete example: the finance benchmark
- Common benchmarking mistakes to avoid

**Read time:** 20 minutes

**Why this matters:** Understanding metrics prevents misinterpreting results. This section teaches you to read benchmark tables correctly.

---

### Section 4: How to Create Use Cases — `4_HOW_TO_CREATE_USE_CASES.md`

Step-by-step guide to building your own benchmark task and running STJP on it.

What you'll learn:
- The anatomy of a use case (protocol.scr, refinements, agents, test harness)
- How to write a Scribble protocol
- How to add value-level guards (refinements)
- How to implement agents
- How to write a test harness and measure results
- How to define success criteria
- Use case design patterns (deadlock-prone, coordination-heavy, safety-critical, scale)
- A checklist before running a benchmark

**Read time:** 30 minutes (reference guide; read while building)

**Why this matters:** If you want to test STJP on your own problem, this is the map.

---

### Section 5: Run Reports Explained — `5_RUN_REPORTS_EXPLAINED.md`

Reading the benchmark results in plain English: what the numbers mean and why they matter. Opens with a plain-English glossary so it is fully self-contained (every term — agent, protocol, gate, monitor, scheduler, GCR, cost-to-goal — defined before use).

What you'll learn:
- **Part 1 (finance run, 2026-07-02):** the headline result; how to read the results table (each column explained); what each arm represents and why it improved; the five pre-registered predictions and how they graded; severity grading in real runs (S0–S4 examples); critical-properties audit (C1, C2, C3 verified)
- **Part 2 (n=100 reliability run, 2026-07-04):** the seven experiments in plain English — each with *what it tests, why it was designed that way, and what impact the result has*: the instruments check (40/40), the safety checker (E1, 95%/0%), the security gate under attack (E2, 0→42→92→100%), the reliability math (E4, 17.6× tighter confidence), the meaning-preserving translator (E5, 300/300), the scaling behaviour (E6, 9→17×), and portability (E7, 59/59), plus the 100-run interaction trials (0/100 vs 100/100) with token/call figures

**Read time:** 35 minutes

**Why this matters:** Part 1's run showed STJP as 9× cheaper than global protocol; Part 2 proves each piece holds up under pressure at 100× the trials. This section explains both in plain English.

---

### Section 6: Use Cases — Why Interaction Safety Matters — `6_USE_CASE_DEADLOCK_SAFETY.md`

Concrete examples where protocols catch real problems that would crash unreliable systems.

What you'll learn:
- **Deadlock:** Trade execution where agents wait for each other forever
- **Wrong branch:** Revenue audit bypass (missing audit for high-revenue cases)
- **Authorization bypass:** Loan filing before approval
- **Data provenance:** Compliance agent guessing numbers instead of reading them
- **Concurrency confusion:** Agents receiving messages in wrong order
- For each: the scenario, failure mode, how STJP catches it, real-world impact

**Read time:** 20 minutes

**Why this matters:** This is why safety protocols aren't optional. These failures happen in production.

---

## 📁 File reference

### Main documents (read these)

| Document | Purpose |
|---|---|
| `1_TECH_SETUP.md` | **Foundation.** What is Scribble? How does STJP work? How do I run it? |
| `2_TESTING_STRATEGIES.md` | **Methodology.** How do we benchmark STJP fairly? What are the fairness rules? |
| `3_BENCHMARK_DESIGN_EXPLAINED.md` | **Metrics.** What do we measure? How do we interpret results? |
| `4_HOW_TO_CREATE_USE_CASES.md` | **Build guide.** How do I create my own test case? |
| `5_RUN_REPORTS_EXPLAINED.md` | **Results.** How do I read benchmark results? What do the numbers mean? |
| `6_USE_CASE_DEADLOCK_SAFETY.md` | **Safety cases.** Why do protocols matter? Real examples. |

### `reference/` — technical deep-dives (current, for researchers)

- `reference/GLOSSARY.md` — Plain-language glossary (same terms as `1_TECH_SETUP.md` section 4; the canonical version)
- `reference/SCRIBBLE_EXTENSIONS.md` — Deep dive on how STJP extends Scribble (technical)
- `reference/CHOICE_GUARDS_AND_GATE.md` — How value-dependent choice guards and the enforcement gate work (technical)
- `reference/NUSCR_CLOUD_INSTALL.md` — **How to run the coinductive nuscr ("nuscribble") backend** in the cloud env: Docker route, CI-artifact native-binary route, building scribble-java from source, the `STJP_COMPILER_BACKEND=nuscr` / `STJP_NUSCR_BIN` env vars, and the 2017-Maven-release pitfall
- `reference/NUSCR_AND_SKILL_SAFETY_PLAN.md` — The plan behind RESULT_8: swapping in the coinductive compiler and building the real-public-skills safety benchmark (unvalidated vs STJP)
- `reference/HOW_TO_USE_TRACES.md` — **How to verify the results yourself** from the committed raw traces: re-derive every metric with `engine.py report` straight from `state.json`, read a trace by eye, the exact GCR/CGC/disaster definitions, and what is (and isn't) committed. Companion to the in-tree `reports/ss2026_n100_sonnet/traces/VERIFY.md`
- `reference/FOUNDRY_VISIBILITY.md` — Exact code to make agents/threads/traces visible in the Azure AI Foundry portal
- `reference/STJP_V3_PLAN.md` — **Latest plan**: governance plane + decentralized execution plane (summarized in `1_TECH_SETUP.md` section 7)
- `reference/PROTOCOL_EVOLUTION.md` — How to update a protocol and re-validate (now includes the built incremental sub-protocol slice: child verified once, projection diff, monitor regen for affected roles only)
- `reference/CRITIC_REVISOR.md` — The Critic (cross-message policies: information flow, ordering, separation of duty, aggregates — static AND runtime) and the Revisor repair loop
- `reference/SKILL_COMPACTION.md` — Bottom-up STJP: compact EXISTING skill markdowns into local types, compose the global type, Scribble-validate it
- `reference/BENCHMARK_PLAN_V2.md` — Benchmark hardening (E1–E7 + verdict corpus): what each experiment measures, real numbers vs measurement-pending, and how to swap real data into the figures/tables
- `reference/GAP_CLOSED.md` — Refinement call-site closure record (referenced by `experiments/README.md` and `stjp_core/README.md`)

### `results/` — the evidence behind the guides (current, plain English)

Each follows the same template: at-a-glance summary → the story → how the test was set up → the numbers → what they mean → honest caveats → where the raw data is.

#### What has been compared (map across every results doc)

Every run compares the **same idea** — agents run with *less* protocol support
vs *more* — and isolates *one* variable at a time. The table shows what each
report holds fixed and what it varies, so you can see the whole comparison at a
glance:

| Report | Model / roles | Scale | Compiler | What is compared (the one variable) | Headline |
|---|---|---|---|---|---|
| RESULT_1 | deterministic | n=6–10 | scribble | validated vs unvalidated protocol (static check on/off) | only the checker catches the deadlock: 0/6 vs 6/6 |
| RESULT_2 | gpt-5.4 | n=10 | scribble | no contract vs lean projected contract (tokens) | same task, −63% tokens |
| RESULT_3 | gpt-5.4 | n=10 | scribble | the 8-setting ladder (no protocol → rejected → text → projected) | 0% → 10% → 40% → 60–100% |
| RESULT_4 | gpt-5.4 | n=10 | scribble | global-text vs full STJP stack (safety **and** cost together) | STJP safest **and** 9× cheapest |
| RESULT_5 | Haiku subagents | n=10 | scribble | unchecked prose skills vs STJP (Foundry-free components) | 0/10 deadlock vs 10/10 |
| RESULT_6 | deterministic | n=100 | scribble | "test the testers": mutation / adversarial gate / pass^k / fidelity | checker 95.6%/0% FP, gate 0→100% |
| RESULT_7 | mixed | n=100 | scribble | everything above re-run at 100× the trials (reliability) | Wilson CI narrows, pass^10 17.6× |
| RESULT_8 | Haiku **&** Sonnet | n=10 **&** n=100 | scribble **&** **nuscr** | **real public skills**: unchecked vs contract-as-text vs STJP | STJP only arm at 100%/100%/0 disasters, and cheapest |
| RESULT_9 | Haiku **vs** Sonnet (same grid twice) | n=10 × 12 runs | scribble | **real Anthropic + GitHub Copilot skills**: the same 3-setting ladder run once per model | no-plan failures flip BY MODEL (each fails a different team 0/10); STJP 40/40 identical on both, 3× cheaper |

The single load-bearing comparison in all of them is **"validate + enforce"
(STJP) vs "don't"** — RESULT_8 is the strongest form because the skills are
real open-source code and the roles are strong models deciding in isolation.

> **Decoding the shorthand in this list.** The entries below are terse on
> purpose (they are an index, not the report). If a term is unfamiliar, the
> plain-English version is in `5_RUN_REPORTS_EXPLAINED.md` (which opens with a
> glossary and explains every experiment). Quick key:
> - **E1–E7** = the seven "Benchmark Plan v2" experiments, each stress-testing
>   ONE piece of the system: **E1** = does the safety checker catch broken
>   protocols (mutation testing); **E2** = can a hostile agent leak data past the
>   gate (adversarial); **E3** = does the benefit hold across weak/strong models
>   (capability sweep, pending); **E4** = how reliable across many runs
>   (pass^k / Wilson stats); **E5** = does English→protocol translation keep the
>   meaning (fidelity); **E6** = does it stay cheap as the team grows (roles
>   sweep); **E7** = does it work outside our framework (portability).
> - **verdict corpus** = a hand-labelled test set that checks our *measuring
>   tools* are correct ("testing the testers").
> - **FP** = false-positive rate (how often the checker wrongly rejects a *good*
>   protocol — lower is better).
> - **pass^k** / **pass^10** = the chance that ALL of the next k runs succeed —
>   the reliability an unattended deployment actually needs. **@floor** =
>   computed at the pessimistic edge of the confidence range.
> - **Wilson CI** = Wilson confidence interval — a statistically honest range for
>   a success rate given a finite number of trials. A narrow range = more certain.
> - **n=10 / n=100** = how many times each setting was run.

- `results/RESULT_1_DEADLOCK.md` — **Only a static checker catches a deadlock**: unchecked rules 0/6 trials, 0 messages, ∞ cost; validated 6/6 first try. Plus the authoring-risk measurement (unchecked AI-drafted protocols are safe only 3/10 times; the checker caught all 7 unsafe drafts).
- `results/RESULT_2_TOKEN_EFFICIENCY.md` — **Same task, one-third the tokens**: everyone completes 100%; lean projected contract 8.8k tokens vs 24.1k with no contract (−63%). Mechanism: less deliberation + smaller prompts.
- `results/RESULT_3_PROTOCOL_LADDER.md` — **More protocol support, better outcomes** (8 settings, n=10): no protocol 0% → rejected protocol 10% → validated text 40% → projected contracts 60–100%. Also the best place to see, with real traces, exactly what "a violation" and "success" mean.
- `results/RESULT_4_FULL_STACK.md` — **The latest headline** (pre-registered, 2026-07-02): full STJP stack is simultaneously the safest (100%, 0 disasters) and the cheapest/fastest (13.3k tokens, 32s per delivered report — 9× cheaper than the same protocol as text).
- `results/RESULT_5_SUBAGENT_VALIDATION.md` — **Foundry-free validation of the 2026-07 components** (Critic/Revisor, skill compaction, incremental extension): 211/211 stress checks over generated protocols; subagent-driven trials n=10 — unchecked prose skills 0/10 (all deadlock) vs STJP 10/10 at protocol-minimum cost, extended protocol 10/10, compaction gauntlet 10/10 detect + 10/10 repair.
- `results/RESULT_6_BENCHMARK_HARDENING.md` — **Benchmark Plan v2** (test the testers + mutation testing + adversarial gate + pass^k + translation fidelity + roles/portability): verdict corpus 40/40, checker 95.6% detection/0% FP, gate exfiltration ladder 0→41.7→91.7→100%, pass^10 CI story, equivalence scorer 100%. Design in `reference/BENCHMARK_PLAN_V2.md`.
- `results/RESULT_7_N100_SCALE.md` — **n=100 scale run** (all deterministic benchmarks): Wilson CI narrows from [72,100]% to [96.3,100]%; pass^10@floor jumps 0.039→0.686 (17.6×); integration stress 2105/2110; 100-protocol mutation corpus 95.1%/0% FP; subagent trials 0/100 unchecked vs 100/100 STJP; equivalence scorer 300/300.
- `results/RESULT_8_SKILL_SAFETY.md` — **Real public skills, unvalidated vs STJP** (4 cases from openai-agents/crewAI/autogen/langgraph, cloud run, both compilers live in-sandbox — scribble-java master + coinductive nuscr, `reference/NUSCR_CLOUD_INSTALL.md`). *n=10, Haiku-class subagents:* original skills 0% GCR (40/40 stall or deadlock, ∞ cost); contract-as-text 100% GCR but 50% CGC with 20 duplicate-irreversible-act disasters (double charges/seat-writes); full STJP 100%/100%, 0 disasters, −45% tokens and 3.5 vs 10+ agent calls/trial. **Addendum — n=100, Sonnet subagents, strict per-role isolation, nuscr backend (1,200 trials):** STJP still 100%/100%/0 and 2.4–2.9× cheaper (Wilson CI excludes both other arms); the weak arms fail *differently* under a stronger model (200 disasters for contract-as-text, a booking livelock), so unvalidated skills' runtime success is model-dependent — but the design-time compiler rejection of all four `unchecked` protocols is model-independent.
- [`results/RESULT_9_REAL_SKILLS_TWO_MODELS.md`](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md) — **Real Anthropic + GitHub Copilot skills, the same experiment run on two models** (2 teams built from anthropics/skills and github/awesome-copilot files × 3 settings × n=10, once with Haiku subagents and once with Sonnet subagents; written fully jargon-free, every term explained in place). Headline: with no coordination plan, *which* team fails is model-dependent — Haiku failed the code-change team 0/10, Sonnet failed the announcement team 0/10, on identical skills; with full STJP both models were flawless and indistinguishable (40/40, 0 rule-breaking messages, exactly 4 AI calls/trial, ~1.8k tokens = 3× cheaper than no-plan, 2.4× cheaper than plan-as-text). Evidence: `experiments/subagent_trials/reports/ss2026_new_skills/`.

Earlier run reports, kept here for history (technical, not rewritten):

- `results/RUN_REPORT_2026-06-11.md` — cost anatomy, severity re-scoring, the banking companion run
- `results/RUN_REPORT_2026-06-17.md` — drafting prompt A/B, criticality-gate smoke results
- `results/RESULTS.md` — results from the deleted legacy runner (earliest run)

### `diary/` — the project journal

- `diary/DIARY.md` — newest-first development log; the history of every decision. (The former standalone `SESSION_2026-06-17.md` session index is merged into its 2026-06-17 entry.)

### Archived documents (`archive/` — kept for reference, nothing deleted)

| Document | Why archived |
|---|---|
| `TESTING_STRATEGY.md` | Superseded by `2_TESTING_STRATEGIES.md` (same content, plain English) |
| `BENCHMARK_DESIGN_V3_CRITICALITY.md` | Superseded by `3_BENCHMARK_DESIGN_EXPLAINED.md` for readers; technical original of the C1/C2/C3 design |
| `BENCHMARK_DESIGN.md` | v2 scoring spec — content absorbed into `3_BENCHMARK_DESIGN_EXPLAINED.md` |
| `BENCHMARK_DESIGN_V2_FROZEN.md` | Frozen snapshot behind the grand n=10 run (revert point) |
| `EXPERIMENT_DESIGN.md` | v1 (4-scenario) design |
| `EXPERIMENT_DESIGN_v2.md` | The 8-arm design (superseded by v3 execution design) |
| `EXPERIMENT_DESIGN_V3_EXECUTION.md` | The pre-registered design graded by `results/RESULT_4_FULL_STACK.md` |
| `WHY_B_MATCHES_C_ANALYSIS.md` | The honest confound analysis — its conclusions now live in `2_TESTING_STRATEGIES.md` |
| `RUN_REPORT_2026-07-02.md` | Technical original of the 2026-07-02 run — rewritten in plain English as `results/RESULT_4_FULL_STACK.md` |
| `RESULTS_finance_n10.md` | Technical original of the n=10 finance run — rewritten as `results/RESULT_3_PROTOCOL_LADDER.md` |
| `DEADLOCK_DEMO.md` | Technical original of the deadlock demo — rewritten as `results/RESULT_1_DEADLOCK.md` |
| `TOKEN_EFFICIENCY_DEMO.md` | Technical original of the efficiency demo — rewritten as `results/RESULT_2_TOKEN_EFFICIENCY.md` |
| `STJP_RESEARCH_REPORT.md` | The full technical report through the n=5 gate result |
| `STJP_discussion_13May2025.md` | Meeting notes (the journal itself lives in `diary/`) |
| `DRAFTING_IMPROVEMENTS.md` | Why early drafts failed + the fan-out normalizer fix |
| `EVOLUTION_DEMO_DESIGN.md` | "The demand changed on Tuesday" demo design |
| `GOVERNANCE_TOOLKIT_ASSESSMENT.md` / `RELATED_WORK_DELM.md` | Inputs synthesized into `reference/STJP_V3_PLAN.md` |
| `SKILLS_COMPILER_PROPOSAL.md` / `APPLICATION_SCENE_VIEW_PROPOSAL.md` | Retired/superseded proposals |

---

## 🎯 Reading paths by role

### "I'm new to STJP"
1. `1_TECH_SETUP.md` (understand the foundation)
2. `6_USE_CASE_DEADLOCK_SAFETY.md` (see why it matters)
3. `2_TESTING_STRATEGIES.md` (learn how we measure it)
4. `5_RUN_REPORTS_EXPLAINED.md` (see real results)

### "I want to run STJP"
1. `1_TECH_SETUP.md` section 5 (setup steps)
2. `4_HOW_TO_CREATE_USE_CASES.md` (build a test case)
3. Run locally and view traces in Azure AI Foundry

### "I want to create a new use case"
1. `1_TECH_SETUP.md` sections 1–3 (understand the basics)
2. `2_TESTING_STRATEGIES.md` (understand fairness rules)
3. `4_HOW_TO_CREATE_USE_CASES.md` (step-by-step guide)
4. `3_BENCHMARK_DESIGN_EXPLAINED.md` (understand metrics)

### "I'm reviewing the results"
1. `3_BENCHMARK_DESIGN_EXPLAINED.md` (how we measure)
2. `5_RUN_REPORTS_EXPLAINED.md` (what the numbers mean)
3. `2_TESTING_STRATEGIES.md` (what was controlled/varied)

### "I'm a researcher"
1. `reference/GLOSSARY.md` (terms)
2. `reference/SCRIBBLE_EXTENSIONS.md` (technical deep dive)
3. `reference/STJP_V3_PLAN.md` (latest plan: governance + execution planes)
4. `reference/GAP_CLOSED.md` (what's implemented)
5. `archive/BENCHMARK_DESIGN_V3_CRITICALITY.md` + `archive/RELATED_WORK_DELM.md` (design history, related work)

---

## 🏗️ Document organization philosophy

**As of 2026-07-04, `docs/` has six layers:**

```
docs/
├── 1_...md … 6_...md + README.md   ← the numbered guides (plain English; start here)
├── reference/                       ← current technical deep-dives (glossary, Scribble
│                                      extensions, gate internals, Foundry wiring, v3 plan,
│                                      Benchmark Plan v2)
├── results/                         ← current evidence, plain English: RESULT_1_DEADLOCK …
│                                      RESULT_8_SKILL_SAFETY (latest)
├── predictions/                     ← pre-registered predictions (written BEFORE a run,
│                                      graded after) — e.g. BENCHMARK_V2_PREREGISTRATION
├── diary/                           ← the project journal (DIARY.md, newest-first)
└── archive/                         ← superseded designs, earlier reports, technical
                                       originals of the RESULT_* rewrites
                                       (nothing deleted, nothing here is current)
```

Rules:
- **Pitch is separate** — only presentation assets (demo HTML, slides) go in the repo-root `pitch/` directory (not under `docs/`)
- **Plain language always** — every term explained; no unexplained acronyms
- **A new doc goes into exactly one layer** and gets a one-line entry in this README
- **When a doc is superseded**, move it to `archive/` and note what replaced it

---

## 🔄 Where to get the latest

- **Latest plan:** `reference/STJP_V3_PLAN.md` (governance plane + execution plane; summarized in `1_TECH_SETUP.md` section 7)
- **Latest results:** `results/RESULT_8_SKILL_SAFETY.md` (real public skills, 3 arms — n=10 Haiku **and** an n=100 Sonnet per-role-isolated addendum on the nuscr backend), `results/RESULT_7_N100_SCALE.md` (all deterministic benchmarks at n=100) and `results/RESULT_4_FULL_STACK.md` (finance case, gpt-5.4, n=10 — the pre-registered live-model run)
- **How to run the compiler backends:** `reference/NUSCR_CLOUD_INSTALL.md` (coinductive nuscr / "nuscribble" — Docker or native binary via `STJP_COMPILER_BACKEND=nuscr`; scribble-java is the default backend)
- **How to verify the results from raw traces:** `reference/HOW_TO_USE_TRACES.md` — the RESULT_8 n=100 per-trial traces are committed under `experiments/subagent_trials/reports/ss2026_n100_sonnet/traces/`; re-derive every metric with `engine.py report`
- **Latest code status:** `reference/GAP_CLOSED.md`
- **Latest experiment design:** `archive/EXPERIMENT_DESIGN_V3_EXECUTION.md` (pre-registered; graded by the 2026-07-02 run report)

---

## ❓ Didn't find what you're looking for?

- Need to understand a specific term? → `1_TECH_SETUP.md` section 4 or `reference/GLOSSARY.md`
- Want to know how to debug a protocol? → `4_HOW_TO_CREATE_USE_CASES.md` step 5
- Curious about a specific benchmark arm? → `5_RUN_REPORTS_EXPLAINED.md` section 3
- Want to understand why a particular result? → `5_RUN_REPORTS_EXPLAINED.md` section 6
- Need to view traces? → `1_TECH_SETUP.md` section 5 or `reference/FOUNDRY_VISIBILITY.md`
- Wondering if STJP applies to your use case? → `6_USE_CASE_DEADLOCK_SAFETY.md`
