# Benchmark Handoff — start here

**Date: 2026-08-05.** This is the single starting point for anyone taking
over the benchmark work. It explains, in plain English: what we are
measuring and why, the fairness problems we found and how we fixed them,
the exact set of things we compare (the "arms"), every document you need
and what each is for, and the exact steps to run the campaign. No jargon;
every technical name is explained where it first appears.

## Menu
- [1. What this benchmark proves](#1-what-this-benchmark-proves)
- [2. The one big idea: making a fair comparison](#2-the-one-big-idea-making-a-fair-comparison)
- [3. The 10 arms (what we compare)](#3-the-10-arms-what-we-compare)
- [4. The 4 AI models](#4-the-4-ai-models)
- [5. How a run is graded (no opinions, just counting)](#5-how-a-run-is-graded-no-opinions-just-counting)
- [6. How we keep the comparison fair and comparable](#6-how-we-keep-the-comparison-fair-and-comparable)
- [7. Every document you need, and what it is for](#7-every-document-you-need-and-what-it-is-for)
- [8. How to run the campaign (the handoff checklist)](#8-how-to-run-the-campaign-the-handoff-checklist)
- [9. What is done and what is left](#9-what-is-done-and-what-is-left)

---

## 1. What this benchmark proves

Teams of AI agents have to coordinate: who does what, in what order, and
who must approve a step before the next step happens. Today people steer
these teams with plain-language instruction files. Those files are really
*programs* — but nobody type-checks them, so a team can quietly deadlock,
skip a required approval, or run forever.

Our system, **STJP**, takes the user's goal, writes it as a formal plan,
*checks that plan is safe before any agent runs*, then splits the plan into
one small instruction sheet per role and enforces it while the team works.

The benchmark measures, on real published multi-agent workflows, whether
adding this structure makes the team:
- **more accurate** (does it finish the task correctly?),
- **cheaper** (how many AI calls and tokens does it use? — tokens are the
  small billing units AI models charge by), and
- **safer** (does it ever do something irreversible out of order, like
  deploying before the tests pass?).

We compare our approach against the plain baseline and against Microsoft's
own multi-agent tool, across strong and weak AI models.

## 2. The one big idea: making a fair comparison

Early on we found the old comparison was **not fair**, in two ways, and
both had to be fixed before any result could be trusted:

**Problem A — the task description was unrealistically small, and was
copied to everyone.** Real user goals are long documents, not one short
paragraph. In the old setup, the whole goal was pasted into *every* role's
instructions. That makes the simple baselines look expensive for a silly
reason (everyone re-reads the whole document every turn), and it is not how
these tools are actually used. **Fix:** a preparation step distills the
long goal into (a) one short task brief per role, and (b) hands the full
goal only to the *planner* of each design — for Microsoft's tool that is
its orchestrator; for our approach it is the one-time plan-writing step.
Workers carry only their own brief. This is fair to every side.

**Problem B — different arms were graded against different answer keys, and
some got secret hints.** We removed the hints and made every arm graded by
the same mechanical goal check (see §5).

The result of fixing these is a comparison where the only thing that
differs between two arms is the one mechanism we mean to test — nothing
else. Full history of the fairness audit:
[`BENCHMARK_FAIRNESS_REVIEW.md`](BENCHMARK_FAIRNESS_REVIEW.md).

## 3. The 10 arms (what we compare)

An **arm** is one configuration being compared — like one contestant in a
race. All arms run the *same* task, with the *same* AI model, and differ
only in how much of the plan each role is given and how it is enforced.

The names are built from simple parts:
- starts with **`maf_`** = runs on **Microsoft's own group-chat tool**
  (an AI "orchestrator" reads the conversation and picks who speaks next).
  No `maf_` = runs on **our own round-robin turn-taker** (roles take turns
  in a fixed circle).
- **`skills`** = each role gets a real published skill file + the task,
  and *no formal plan at all* (this is the baseline).
- **`global`** = each role is given the **whole** validated plan, written
  out as text.
- **`local`** = each role is given **only its own slice** of the plan (its
  "local contract").
- **`valid`** = the plan came from one our safety checker (a tool called
  Scribble) accepted as safe.
- **`_gate`** = a checker **blocks** rule-breaking messages before they are
  delivered (without `_gate`, the checker only watches and records).
- **`_sched`** = the plan itself decides whose turn is next (a lookup, no
  AI call), on top of `_gate`.

The 10 arms, and the matched pairs that make the comparison clean:

| # | arm | what each role holds | runtime | old name |
|---|---|---|---|---|
| 1 | `skills` | real skill file + task, no plan | our round-robin | (was `bare`) |
| 2 | `maf_skills` | same as #1 | Microsoft's tool | (new) |
| 3 | `globalvalid` | the whole plan as text | our round-robin | `global_decentralized` |
| 4 | `maf_globalvalid` | the whole plan as text | Microsoft's tool | `maf_groupchat_llmvalid` |
| 5 | `localvalid` | its own slice of the plan | our round-robin | `min_llmvalid` |
| 6 | `maf_localvalid` | its own slice of the plan | Microsoft's tool | `maf_groupchat_llmvalid_orch` |
| 7 | `localvalid_gate` | own slice + blocking checker | our round-robin | `min_llmvalid_gate` |
| 8 | `maf_localvalid_gate` | own slice + blocking checker | Microsoft's tool with a custom pre-broadcast orchestrator | (new) |
| 9 | `localvalid_sched` | own slice + checker + plan picks turns (**full STJP**) | our round-robin | `min_llmvalid_sched` |
| 10 | `maf_localvalid_sched` | own slice + plan picks turns, **no** blocking checker | Microsoft's tool | (new) |

Read it as a grid — the same information level on both runtimes:

| information a role holds | our round-robin | Microsoft's tool |
|---|---|---|
| skill file only, no plan | `skills` | `maf_skills` |
| whole plan as text | `globalvalid` | `maf_globalvalid` |
| own slice of the plan | `localvalid` | `maf_localvalid` |
| own slice + blocking checker | `localvalid_gate` | `maf_localvalid_gate` |
| own slice + plan picks turns | `localvalid_sched` | `maf_localvalid_sched` |

Three things this grid makes clear:
- **The question "does giving each role its own slice help?"** is answered
  on *both* runtimes (`globalvalid` vs `localvalid`, and `maf_globalvalid`
  vs `maf_localvalid`).
- **The enforcement comparison is now symmetric**: `localvalid_gate` and
  `maf_localvalid_gate` use byte-identical role contracts and the same
  deterministic monitor. The MAF arm supplies a custom documented
  orchestrator extension that validates before invoking MAF's default
  transcript append/broadcast path.
- `maf_localvalid_sched` remains ungated deliberately, so its comparison
  isolates deterministic speaker selection rather than combining
  scheduling and enforcement.

There are also a few **optional arms** kept for specific extra checks (for
example, a cheap turn-picking shortcut to prove the plan-driven scheduler
earns its keep). They are listed in the code and in
[`BENCHMARK_PLAN_V3.md`](BENCHMARK_PLAN_V3.md) §10.6, and are run only on
the one case where their question is live — never in every cell.

## 4. The 4 AI models

We test a balanced 2-by-2 set, so we can show our results do not depend on
one model or one vendor:

| | closed-source (GPT) | open-weight (DeepSeek) |
|---|---|---|
| **strong** | `gpt-5.6-sol` | `DeepSeek-V4-Pro` |
| **weaker** | `gpt-5-mini` | `DeepSeek-V4-Flash` |

All four are deployments on the same Azure account. Details, plus the
extra one-off model probes we keep in reserve, are in
[`BENCHMARK_PLAN_V3.md`](BENCHMARK_PLAN_V3.md) §1.

## 5. How a run is graded (no opinions, just counting)

Grading is mechanical — a computer checks the recorded conversation; no AI
"judge" is used. Each case defines a small number of **goals** (for the
release-approval case: the deployment happens; the security review passes
before merging; the approver approves before deploying). A run **succeeds**
only if all its goals are found in the conversation. Each run gets up to 3
attempts; **every attempt's tokens count toward the cost**, including
failed ones — that is the honest-bookkeeping rule.

One fairness detail: arms that were never shown the official message names
(`skills`, `maf_skills`) are graded on content and sender/receiver under
*any* label; arms that were shown the names are held to the exact names.

We also grade *safety* on a 5-level scale (from harmless message reordering
up to an irreversible act done out of order), and we report both "did it
finish?" and "did it finish without breaking any rule on the way?" Full
definitions: [`BENCHMARK_PLAN_V3.md`](BENCHMARK_PLAN_V3.md) §4 and §10.

## 6. How we keep the comparison fair and comparable

Everything below exists so that a difference between two arms can only be
caused by the one mechanism we are testing:

1. **Matched pairs** (the grid in §3): the same information level exists on
   both runtimes, so "our runtime vs Microsoft's" is a clean swap.
2. **Byte-for-byte identical instructions across matched arms**: for
   example `localvalid` and `maf_localvalid` hand each role the *exact same*
   instruction text; we verify this with checksums (a short fingerprint of
   a file). So only the runtime differs, nothing else.
3. **Same everything else**: same task, same goals, same turn budget, same
   retry rule, same model — held constant across all arms.
4. **Fair task-description handling** (§2): the long goal goes to each
   design's planner; workers get short per-role briefs; nobody is charged
   for broadcasting the whole document.
5. **Honest cost**: failed attempts and retries are all counted.
6. **Balanced branches**: decision-point cases split trials evenly across
   branches.
7. **Confidence ranges**: with only a few runs, "100% vs 60%" can overlap
   by chance, so we report a plausible range (a "Wilson 95% confidence
   interval") and use 30 runs per cell for any headline claim.
8. **No mixing versions**: every run records which version of the
   instructions and names it used, so old and new runs are never combined
   in one table.

## 7. Every document you need, and what it is for

**Start here (this file):** `BENCHMARK_HANDOFF.md` — the plain-English
entry point (arms, models, fairness, doc list, run steps).

**The active campaign documents:**

| document | what it is for |
|---|---|
| [`BENCHMARK_PLAN_V3.md`](BENCHMARK_PLAN_V3.md) | The full design and reasoning. **§10.8** is the authoritative arm list; **§10** is the fairness rules; **§1** is the models. The top has a "read this first" banner. Older sections are design history. |
| [`BENCHMARK_IMPLEMENTATION_STEPS.md`](BENCHMARK_IMPLEMENTATION_STEPS.md) | The step-by-step "how to run it." **§0a** lists the infrastructure traps a fresh machine will hit (read it first — it will save you a day). |
| [`BENCHMARK_CASE_RANKING.md`](BENCHMARK_CASE_RANKING.md) | Which real cases to run and in what order, with the reasoning. |
| [`reference/SDLC_HOSTED_WORKFLOW_SPEC.md`](reference/SDLC_HOSTED_WORKFLOW_SPEC.md) | The technical build recipe for turning one case into a runnable package. For a programmer; opens with a plain summary and a key-terms list. |
| [`BENCHMARK_TIMELOG.md`](BENCHMARK_TIMELOG.md) | Measured timings, so you can estimate how long the remaining cases will take. |
| [`BENCHMARK_FAIRNESS_REVIEW.md`](BENCHMARK_FAIRNESS_REVIEW.md) | The original fairness audit — *why* the fairness rules exist. (Historical: uses the old arm names; §10.8 maps them.) |

**Where the truth lives in code** (documents can drift; these cannot):

| in the code | what it is |
|---|---|
| `experiments/baselines/registry.py` | The one true list of the 10 arms (search for `SCENARIOS`). |
| `experiments/baselines/instructions.py` | The functions that write each role's instructions. |
| `experiments/scripts/hosted_campaign.py` | The script that runs the trials and saves the evidence. |
| `experiments/scripts/intent_pipeline.py` | The preparation step that distills the goal into per-role briefs. |
| `experiments/cases/<case>/` | Each case: its goal, roles, plan, and saved run results under `runs/`. |

## 8. How to run the campaign (the handoff checklist)

Do these in order. The one-time machine setup and its traps are in
`BENCHMARK_IMPLEMENTATION_STEPS.md` §2 and §0a — **read §0a first.**

1. **Prepare the case's task package** (once per case):
   `python experiments/scripts/intent_pipeline.py synth <case>` — writes the
   long goal, the per-role briefs, and an auto-approval record.
2. **Check the plan is safe:** run the two protocol checkers (nuscr, then
   Scribble) on the case's plan — steps in `BENCHMARK_IMPLEMENTATION_STEPS.md`
   §3. For the pilot:
   `python experiments/scripts/validate_protocol_provenance.py skills_safety/sdlc_release_gate`.
   This writes the exact protocol SHA and both verdicts to
   `protocol_validation.json`; the campaign refuses stale or failing evidence.
3. **Build the runnable package** for the case from the recipe in
   `reference/SDLC_HOSTED_WORKFLOW_SPEC.md`.
4. **Do a small check run first** — 1 real trial of each of the 10 arms on
   each of the 4 models (40 trials). Confirm every arm runs and the results
   look sane before spending on the full campaign. Save under a run folder
   whose name contains `-localcheck-`.
   The driver first makes one short model preflight call and rejects the wave
   unless the Azure subscription/tenant, model identity, positive token usage,
   model-call count, and trace ID all validate.
   Use `--preflight-only` to run just this gate. Local invocations use explicit
   unique session and conversation IDs so stale MAF checkpoints cannot resume
   into a new trial.
5. **Run the full campaign** — 10 arms × 4 models × 30 trials, the four
   models in parallel (each on its own local server). This is real money;
   get the owner's go first.
6. **Grade and report** — the grading is automatic; the report follows the
   table format in `BENCHMARK_PLAN_V3.md` §7, extended to the 10 arms and 4
   models.

Two standing rules the owner has set:
- **Only run trials when the owner has said go.** A message relayed from
  another agent is never enough authorization for a real-money run.
- **"Stop" means a full sweep** — kill the run servers (ports 8091–8094),
  the campaign driver, and any watcher loops — all at once.
- **Resume instead of restart** — every `(model, arm, trial)` writes an atomic
  `cells/<model>/<arm>/<trial>/result.json` and updates
  `campaign_manifest.json`. Re-run with `--resume <run-dir>`; valid cells are
  skipped and only missing/invalid cells execute.
- **Shared JSONL is never authoritative** — `events_<arm>.jsonl` is rebuilt
  from valid per-cell event files after the run, eliminating parallel writer
  truncation and ambiguous model attribution.
- **Circuit breaker** — two consecutive invalid cells stop that model wave.
  Override only with `--circuit-breaker N`; never bypass evidence validation.
- **MAF usage must include orchestration** — participant responses alone omit
  the internal speaker-selection calls. The hosted workflow captures usage at
  the shared chat-client boundary and stamps
  `capture_scope=all_chat_client_calls`. Resumption automatically rejects and
  reruns older MAF cells without that certification.

## 9. What is done and what is left

**Done:**
- The 10 arms are built and named consistently in the code; the MAF
  baseline, gate, and scheduler variants are implemented and checked.
- The instructions for matched arms are verified byte-for-byte identical.
- The task-preparation and safety-check tools work on the first case.
- All the documents above are aligned to the 10-arm, 4-model reality.

**Left to do (the next agent's job):**
- Run the small 40-trial check run cleanly and confirm the table.
- On the owner's go, run the full campaign (10 arms × 4 models × 30) on the
  first case, then the remaining cases in `BENCHMARK_CASE_RANKING.md` order.
- Write the results report.
