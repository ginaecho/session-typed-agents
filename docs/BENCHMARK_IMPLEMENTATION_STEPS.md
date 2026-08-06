# Benchmark Implementation Steps — how to set up and run the campaign

**Date: 2026-08-05.** This is the step-by-step guide for running the test
campaign described in [`BENCHMARK_PLAN_V3.md`](BENCHMARK_PLAN_V3.md) (its
section 10 has the corrected rules; [`BENCHMARK_CASE_RANKING.md`](BENCHMARK_CASE_RANKING.md)
has the order to run cases in). Every case is **packaged** as an Azure AI
Foundry Hosted Agent — an AI-role team bundled to run as Microsoft's cloud
"hosted agent" product — and never as the older "classic Agent Service"
style (see step 4 for why; this replaces PLAN_V3 section 2.2). How the
package is **executed** is section 4.5: the main test runs execute the
identical package locally (fast, parallel), and the cloud-hosted copies
run a small verification sample. More detail in:
[`reference/FOUNDRY_VISIBILITY.md`](reference/FOUNDRY_VISIBILITY.md),
[`reference/HOW_TO_IMPLEMENT_SUBSESSIONS.md`](reference/HOW_TO_IMPLEMENT_SUBSESSIONS.md),
[`reference/HOW_TO_USE_TRACES.md`](reference/HOW_TO_USE_TRACES.md),
[`reference/NUSCR_AND_SKILL_SAFETY_PLAN.md`](reference/NUSCR_AND_SKILL_SAFETY_PLAN.md),
[`reference/NUSCR_BACKEND_COMPARISON.md`](reference/NUSCR_BACKEND_COMPARISON.md),
[`reference/NUSCR_CLOUD_INSTALL.md`](reference/NUSCR_CLOUD_INSTALL.md),
[`reference/PROTOCOL_EVOLUTION.md`](reference/PROTOCOL_EVOLUTION.md).

## Menu

- [0a. Learnings from the first case (read this first on a new machine)](#0a-learnings-from-the-first-case--unexpected-problems-a-fresh-clone-will-hit-again)
- [0. Execution model: orchestrator + cheap subagents](#0-execution-model-orchestrator--cheap-subagents)
- [1. Endpoints and hard rules](#1-endpoints-and-hard-rules)
- [2. Tooling install (once)](#2-tooling-install-once)
- [3. Validation policy: nuscr first, scribble authoritative fallback](#3-validation-policy-nuscr-first-scribble-authoritative-fallback)
- [4. Hosted agent groups (how each case is packaged)](#4-hosted-agent-groups-how-each-case-is-packaged)
- [5. Per-case preprocessing](#5-per-case-preprocessing)
- [6. Tracing and evidence](#6-tracing-and-evidence)
- [7. Run matrix and order](#7-run-matrix-and-order)
- [8. Grading and reporting](#8-grading-and-reporting)
- [9. Subagent task breakdown](#9-subagent-task-breakdown)

## 0a. LEARNINGS FROM THE FIRST CASE — unexpected problems a fresh clone WILL hit again

We lost most of a day to infrastructure surprises on the pilot case
(`sdlc_release_gate`, 2026-08-05). The AI test runs themselves were quick
(23 seconds to 9 minutes each); what consumed the day was breakage around
them. Every problem below is now fixed or has a known workaround — read
this FIRST when setting up on a new machine, because a fresh clone will
meet the same landmines:

1. **Cloud deployment is extremely slow — up to ~1 hour per group.** Each
   `azd deploy` uploads the code and builds it in Azure, one group at a
   time. This is why the standard model is now "run locally first, deploy
   in the background" (see §4.5). Do not plan a day around waiting for
   deploys.
2. **The hidden one-hour kill switch.** Long-running processes started as
   background tasks of the AI-helper harness are silently killed at
   exactly 60 minutes (our model server died at 59 min 53 s with no error
   message — same signature as the old memory_race stall in
   archive/CAMPAIGN_STATUS.md). FIX: start servers and campaign drivers as
   **detached processes** (owned by cmd.exe, output redirected to log
   files), never as harness background tasks.
3. **Stale login variables break authentication.** This machine had
   leftover environment variables (`AZURE_CLIENT_ID`,
   `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`)
   from an unrelated app. They silently take priority and make logins
   fail with error AADSTS7000215. FIX: clear those four variables in the
   environment of every `azd` / local-server command. Transient auth
   failures on cloud calls also happen — retry with spacing; they clear.
4. **A missing package blocks the Microsoft-system setups.**
   `agent-framework-orchestrations` is required for the MAF group-chat
   arms and was not installed by default. It is now in the container's
   `requirements.txt` — but a fresh Python environment must install it,
   or the four MAF arms (`maf_skills`, `maf_globalvalid`, `maf_localvalid`,
   `maf_localvalid_gate`, `maf_localvalid_sched`) fail while everything else works.
5. **Package downloads fail on this network.** The standard Python
   package site is TLS-blocked here. FIX: set
   `UV_DEFAULT_INDEX=https://packagefeedproxy.microsoft.io/pypi/simple/`.
6. **A broken JAVA_HOME poisons the protocol tools.** The machine-level
   `JAVA_HOME` pointed at a JDK that does not exist; `stjp_core/config.py`
   now checks the path really exists before trusting it (self-heals), but
   know this if java errors appear elsewhere.
7. **One run at a time per local server, and long timeouts.** Each local
   run server executes ONE trial at a time; a second request gets
   "Workflow is already running" (that is "busy", not an error — wait and
   retry). Client timeouts must be ≥30 minutes: a short timeout makes the
   command-line tool give up and print a misleading connection error
   while the server quietly finishes the trial anyway, creating orphaned
   run records.
8. **Where things appear on the Azure portal — and the required identity.**
   Local benchmark servers must export live telemetry with the same
   per-model Foundry agent name as their deployment and with version
   `local`. This makes the source explicit while allowing the trace to be
   found under the correct agent identity:

   | model | port | `FOUNDRY_AGENT_NAME` | API |
   |---|---:|---|---|
   | `gpt-5.6-sol` | 8091 | `stjp-sdlc-release-gate-group-sol` | responses |
   | `gpt-5-mini` | 8092 | `stjp-sdlc-release-gate-group-mini` | responses |
   | `DeepSeek-V4-Pro` | 8093 | `stjp-sdlc-release-gate-group-v4pro` | chat |
   | `DeepSeek-V4-Flash` | 8094 | `stjp-sdlc-release-gate-group-v4flash` | chat |

   `main.py` derives these names from
   `AZURE_AI_MODEL_DEPLOYMENT_NAME`; local servers also set
   `FOUNDRY_AGENT_VERSION=local`. DeepSeek servers MUST set
   `STJP_CHAT_API=chat`; otherwise the Responses API requests unsupported
   encrypted content and fails with HTTP 400. Local runs are still local
   Python processes, not deployed containers, and must never be reported
   as hosted execution.
9. **Tracing needs an exporter, not only tracing flags.** Before
   `ResponsesHostServer` is imported or started, `main.py` retrieves the
   project's Application Insights connection string and sets
   `APPLICATIONINSIGHTS_CONNECTION_STRING`. Startup is invalid unless its
   log reports both `appinsights_configured=True` and the expected
   `agent_name`. The two GenAI content-recording flags alone do not
   configure export.
10. **Every server/model combination must pass an exact-ID trace check.**
    Run `hosted_campaign.py --preflight-only` before benchmark cells. Read
    the trace ID from `preflight/<model>.json`, wait for ingestion, and
    query Application Insights using only
    `operation_Id == '<that exact trace ID>'`. Require a root/workflow
    span, one `chat <expected-model>` span, positive input/output tokens,
    and the expected `cloud_RoleName`/`gen_ai.agent.name`. Never accept a
    nearby trace by timestamp and never count unrelated historical traces.
9. **First results only appear after all of the above is fixed** — if a
   model shows no conversations on the portal, check (in order): is its
   server process alive? was it killed at the 60-minute mark? did its
   driver hit auth errors? — before suspecting the benchmark code.

## 0. Execution model: orchestrator + cheap subagents

**The most capable available AI model acts as the director,
not the hands-on worker.** It holds the full context of the benchmark plan
— the rules in PLAN_V3, what each setup (this project calls a setup an
"arm" — one configuration being tested, such as with or without the
safety checker) means, which version of the rules applies, and the
fairness rules — and it makes every design and sequencing decision. It
reviews the work of its AI helpers ("subagents") and never spends its own,
more expensive capacity on routine, mechanical work. **The cheaper AI
helpers do the hands-on work**: setting up new `azd` (Azure's
command-line deployment tool) projects, copying the workflow code into
each new case, running installs, calling the hosted groups the required
number of times, collecting recorded conversations (this project's
technical name for these is "traces"), and re-running the grading
scripts. The full hand-off list is in section 9. Rule of thumb: if a task
is "apply this known pattern to case X," it goes to a helper; if a task
would change what any setup actually *means*, the director keeps it.

## 1. Endpoints and hard rules

These are the technical addresses ("endpoints") and settings this project
connects to. They rarely change:

| item | value |
|---|---|
| Foundry project endpoint | `https://foundary-tzuc06.services.ai.azure.com/api/projects/firstProject` |
| API (OpenAI v1) endpoint | `https://foundary-tzuc06.openai.azure.com/openai/v1` |
| Project service name (azure.yaml) | `firstProject` (`host: azure.ai.project`, `infra.provider: microsoft.foundry`) |
| Model pinning | `AZURE_AI_MODEL_DEPLOYMENT_NAME` env per deployment — one per campaign model: gpt-5.6-sol / gpt-5-mini / DeepSeek-V4-Pro / DeepSeek-V4-Flash (PLAN_V3 §1) |

**Hard rules:**

1. **Hosted Agents only.** Every test group in this benchmark is a
   Foundry "hosted agent" — in the Azure web portal it shows up labeled
   "Hosted"; in the config file `agent.yaml` it is set with `kind: hosted`
   and `host: azure.ai.agent`. **Do not create the older-style "classic
   Agent Service" agents** — that older setup does not work for how we
   deploy things now, and this document replaces PLAN_V3 section 2.2,
   which described it. (Microsoft's deploy guide:
   learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent,
   azd pivot.)
2. **Every role in a case lives inside ONE hosted group**
   (named `stjp-<case>-group`), so the recorded conversations in the
   Azure portal show the complete back-and-forth between all the roles.
3. Every test run must leave three separate records of what happened:
   files saved locally, files saved in git (our version-control system),
   and recorded conversations in Foundry. See section 6.
4. **The director runs the `azd deploy` command itself** (either
   directly, or through a helper assigned to deployment) — deploying to
   the cloud is just one more automated step, never something handed to
   the project owner to do by hand. Deploy each case's services **one at
   a time, by name** (`azd deploy stjp-<case>-group-<model>`) — never run
   a plain `azd deploy` that would touch unrelated groups by accident.
   The project owner is only needed for two things: logging in
   (`az login`) and asking Microsoft to raise a quota limit if a deploy
   fails because of a capacity cap. Everything else — including deploying
   and re-deploying for each model's batch of runs — is the director's
   job.

## 2. Tooling install (once)

### 2.1 azd + hosted-agent extension

This is one-time setup on the machine running the benchmark. Install the
Azure Developer CLI extension for hosted agents, and set up how it
authenticates (logs in). Two options are shown below: reuse an existing
`az` command-line login, or use a service account.

```bash
azd ext install azure.ai.agents
azd extension upgrade azure.ai.agents
# Auth, either:
#  (a) interactive az login already done (the repo's Python tooling uses
#      AzCliCredential) -> let azd reuse the az CLI credential:
azd config set auth.useAzCliAuth true
#  (b) or service principal:
# azd auth login --client-id "<client id>" --client-secret "<client secret>" --tenant-id "<tenant id>"
```

Only run the next command if starting a brand-new azd project from
scratch — this repository already has one (see §4.1):

```bash
azd ai agent init      # select: Agent Framework + MCP tools
```

The usual deploy-and-test cycle:

```bash
azd deploy                                   # deploys the hosted group(s)
azd ai agent run                             # local server
azd ai agent invoke --local "<task text>"    # local smoke invoke
```

### 2.2 scribble-java (projection engine — always required)

Scribble-java is the tool that checks a protocol description is safe and
then "projects" it — breaks it down into separate, per-role instructions.
It is always required. Build it with `mvn -DskipTests package` (a Maven
build command), unzip the file
`scribble-dist/target/scribble-dist-*.zip`, then set the `SCRIBBLE_PATH`
environment variable (plus `JAVA_HOME`, for example
`/usr/lib/jvm/java-21-openjdk-amd64`). **Never** use the old 2017 Maven
package `org.scribble:scribble-dist:0.4.x` — its reader silently drops
parts of the protocol and will wrongly approve almost anything (see the
warning in NUSCR_CLOUD_INSTALL).

### 2.3 nuscr (coinductive fork — the preferred validator)

nuscr is our second, independent protocol checker, and the one we prefer
to try first (see §3 for why). We use our own copy ("fork") of it, named
`nuscr_coinduction`, on the branch `coinductive_projection` (kept
privately — use the project owner's copy). Two ways to install it:

- **On a workstation, using Docker** (a tool for packaging software so it
  runs the same way everywhere):
  `docker build -t nuscr-coind:latest -f tools/nuscr/Dockerfile ./nuscr-coinduction`
  (use the wrapper `Dockerfile` we provide in `tools/nuscr/`, NOT the
  fork's own Dockerfile — the fork's own file fails on a missing
  dependency, `opam depexts`). Point to a different image with
  `STJP_NUSCR_IMAGE`.
- **On a cloud machine or a restricted network** (our "Route B," verified
  2026-07-06): build it on a GitHub Actions runner (an automated cloud
  machine that builds software for us) — see
  `.github/workflows/build-nuscr.yml`, branch `ci-build`, using
  **OCaml 5.3** (a programming language; version 5.2 fails on a
  dependency called `ppxlib_jane`). Save the finished program to the
  `ci-artifacts` branch, then run:
  `git fetch origin ci-artifacts && git show FETCH_HEAD:dist/nuscr-linux-x86_64 > /usr/local/bin/nuscr && chmod +x /usr/local/bin/nuscr`
  and set `STJP_NUSCR_BIN=/usr/local/bin/nuscr`.

The code that drives nuscr for us is
`stjp_core/compiler/nuscr_compiler.py` (functions `NuscrCompiler.validate()`
and `.project_efsm()`), with a converter at
`stjp_core/compiler/nuscr_syntax.py` that turns our `.scr` protocol files
into nuscr's own `.nuscr` format — nuscr cannot read Scribble's original
file format directly. Switch between checkers with the setting
`STJP_COMPILER_BACKEND=scribble|nuscr`. Run the tests with
`python stjp_core/tests/test_nuscr_backend.py` (you should see
`ALL PASS`).

### 2.4 Everything else + preflight

Also install: Microsoft's Agent Framework (MAF — a toolkit for building
multi-role AI teams), Python package `agent-framework`, the recording
("tracing") packages `azure-monitor-opentelemetry` and
`opentelemetry-instrumentation-openai-v2`, and Docker. Before any test
run, a startup check called `tool_preflight` (PLAN_V3 §3) confirms
**four** things are working: scribble-java can break down a known
protocol into per-role instructions, nuscr can check one
(`nuscr check`), MAF can build a simple test group, and the `azd`
extension responds. If any of these fail, the whole campaign stops rather
than continuing with something broken.

## 3. Validation policy: nuscr first, scribble authoritative fallback

**The project owner's preference: check the overall protocol (the "global
type" — the full plan describing every role's messages) with nuscr
first.** For each case, before any deployment:

```bash
# 1) adapt syntax        .scr -> .nuscr    (nuscr_syntax.py, automatic in driver)
nuscr check <case>.nuscr                          # well-formedness + balance
nuscr project --mode=coinductive-full <case>.nuscr Role@Proto   # looping cases
# 2) scribble validation + projection (always)
#    get_all_efsms(...)  -> per-role EFSMs -> contracts, monitors, scheduler
```

For every case, we record both results in the run's provenance file (its
record of origin): `nuscr_verdict` (pass / fail / `not-implemented`)
**and** `scribble_verdict`.

Run:

```powershell
python experiments\scripts\validate_protocol_provenance.py <case>
```

The command validates and projects every role, hashes the exact `.scr` bytes,
writes `protocols/llm_drafts/valid/protocol_validation.json`, and links the
verdicts from `intent/provenance.json`. `hosted_campaign.py` verifies the SHA
and verdicts before any preflight or benchmark call and copies the validation
artifact into the run directory.

**Being honest about nuscr's limits** (from our own verified comparison
of the two tools — see NUSCR_BACKEND_COMPARISON.md, based on 30 test
protocols): nuscr cannot check certain kinds of loops (it calls this
"not implemented" — this happened on 19 of 30 protocols, including
`finance`). And on the protocols both tools *can* check, nuscr caught
**zero** extra deliberately-broken test cases that scribble-java missed.
So our rule is:

- Try nuscr **first**, and trust its result wherever it can read the
  protocol — its special ability to check loops properly is a genuine
  advantage on the cases that loop (`retry_loop`, `iterative_polling`,
  `nested_retry`, `pr_review_merge`, `sdlc_release_gate`, `gem_dev_team`,
  `react18_migration`, `rag`);
- where nuscr says `not-implemented`, we record that, and **scribble-java's
  result is the one we trust** for that case;
- the step that breaks a checked protocol down into per-role instructions
  (small state diagrams called EFSMs, then short instructions, generated
  checkers, and a turn-order planner) always uses scribble-java
  (`STJP_COMPILER_BACKEND=scribble` is the default);
- we never count "the tool couldn't check this" as if it were "the tool
  found and caught a real bug" — that exact mistake is what our tool
  comparison caught and fixed.

## 4. Hosted agent groups (how each case is packaged)

### 4.1 Existing azd project — extend, don't re-scaffold

The folder
`foundry_hosted_agents/agent-framework-agent-with-remote-mcp-tools-responses/`
already has a working example to copy from: a top-level `azure.yaml` file
listing all the groups and the `firstProject` name, plus one folder per
case (`agents/<case>/{agent.yaml,Dockerfile,main.py,requirements.txt}`).
The file `azure.yaml` is the up-to-date list of which groups exist
(early demo groups plus the four model-pinned groups for the pilot case,
`stjp-sdlc-release-gate-group-{sol,mini,v4pro,v4flash}`). To add a new case, add a new
`agents/<case>/` folder plus a new entry in `azure.yaml`, then run
`azd deploy`.

Every group's `agent.yaml` file must always set: `kind: hosted`,
`host: azure.ai.agent`, `language: docker` (with `remoteBuild: true`),
`protocols: responses 2.0.0`, `startupCommand: python main.py`,
`uses: firstProject`, and computing resources of 0.5 CPU / 1 GiB memory.

### 4.2 One group per case; the arm is selected per invocation

Group naming rule: **`stjp-<case>-group`**. Each group contains **every
role in that case**, built with the Microsoft Agent Framework, inside one
`WorkflowAgent` (a container that runs the whole team) served by
`ResponsesHostServer` (the code that answers requests). We do not deploy
a separate group per setup — with 10 setups per case, that would be too
many groups to manage. Instead, `main.py` reads which setup to use from
the request itself (field `stjp_arm`, also saved as a label on the
recorded conversation) and builds the matching workflow on the fly. Which
AI model to use is fixed per deployment through the
`AZURE_AI_MODEL_DEPLOYMENT_NAME` setting — one deployment per model
— one deployment per campaign model (the four groups above).

### 4.3 The gate and scheduler move INSIDE the workflow

Since we cannot use the old-style ("classic") agents, and a hosted group
cannot be watched or controlled from the outside, our safety-checking
system has to live **inside the deployed workflow code itself**. That's
fine — we write `main.py`, so we control what happens inside the group.
Here is what each of our 10 core setups ("arms") does inside the group.
**Renamed 2026-08-05** (PLAN_V3 §10.8, "Final arm naming" — a uniform
`(maf_)?(global|local)valid(_gate|_sched)?` vocabulary, plus two real-skill-
file baselines): `bare`→`skills`, `global_decentralized`→`globalvalid`,
`maf_groupchat_llmvalid`→`maf_globalvalid`, `min_llmvalid`→`localvalid`,
`maf_groupchat_llmvalid_orch`→`maf_localvalid`, `min_llmvalid_gate`→`localvalid_gate`,
`min_llmvalid_sched`→`localvalid_sched`, plus three genuinely new setups,
`maf_skills`, `maf_localvalid_gate`, and `maf_localvalid_sched`. See PLAN_V3 §10.8 for
the full old-name/new-name/meaning table; do not use the old names below
this point in the document.

| arm (core 10, PLAN_V3 §10.8) | what happens inside the group |
|---|---|
| `skills` | every role gets its real, hand-authored per-role skill file (never formally checked) as its prompt; the code takes turns role by role in a fixed order ("round-robin") |
| `maf_skills` | same real skill-file prompts, but built with Microsoft's own group-chat tool (`GroupChatBuilder`) plus an orchestrator role holding the task description |
| `globalvalid` | every role gets the whole validated protocol written out as text, round-robin turn order; a checker watches and records what it would have done, but blocks nothing |
| `maf_globalvalid` | same whole-protocol-as-text prompt, group-chat setup with an orchestrator role holding the task description |
| `localvalid` | roles get their own short, projected instructions ("local contract" — each role's own slice of the protocol), round-robin turn order; a checker watches and records what it would have done, but blocks nothing |
| `maf_localvalid` | same local-contract prompts, group-chat setup; the orchestrator holds the task description and full protocol, while other roles get only their own short, projected instructions |
| `localvalid_gate` | same local-contract prompts as `localvalid`, plus a generated safety checker (`SessionMonitor`, plain Python code shipped inside the container) that blocks off-protocol messages before delivery and asks the sender to try again |
| `maf_localvalid_gate` | same local-contract prompts and AI orchestrator as `maf_localvalid`; a custom MAF orchestrator checks before the default transcript append/broadcast path, blocks off-contract output, and re-prompts the same sender |
| `localvalid_sched` | same as `localvalid_gate`, plus a scheduler: instead of a fixed turn order, it only asks roles whose turn is actually valid right now, based on the protocol's state diagram (EFSM) — the full STJP execution plane |
| `maf_localvalid_sched` | same local-contract prompts, group-chat setup, but the next speaker is picked by the SAME state-diagram (EFSM) scheduler instead of an AI orchestrator — confirmed feasible 2026-08-05 (`GroupChatBuilder(selection_func=...)`, a documented, first-class, no-LLM-call alternative to an orchestrator role); deliberately ungated to isolate scheduling |

The checker and state-diagram files are generated ahead of time, when the
protocol is broken down into per-role parts (§3), and copied into the
container image. This means the safety checker is plain, predictable,
generated Python code that makes no AI calls of its own — exactly as it
worked in our earlier, non-hosted setup. This replaces both PLAN_V3
section 2.2 (the older "classic" setup) and our even older approach where
the checker sat outside the group and re-read the recorded conversation
afterward (described in NUSCR_AND_SKILL_SAFETY_PLAN §2.4b). That
after-the-fact re-check still happens too, as an independent double-check,
but the real blocking now happens live, inside the group, as it runs.

### 4.4 Deploy and small-check-run sequence per case

For each case, deploy and test in this order:

```bash
# in foundry_hosted_agents/agent-framework-agent-with-remote-mcp-tools-responses/
azd ai agent run                                  # local server
azd ai agent invoke --local "run stjp_arm=localvalid_sched trial=smoke"
azd deploy                                        # then 1 hosted smoke trial per arm
```

A case is only allowed to join the full campaign once: both checkers'
(nuscr and scribble) results are recorded, a small check run passes
locally for all 10 setups, and at least one small check run's recorded
conversation shows up on the Azure portal's Tracing page.

### 4.5 How we run tests — mainly on local containers, with a small hosted verification sample (2026-08-05, project-owner directive)

> **Note on our pilot case (sdlc_release_gate):** we briefly considered
> running mainly on the hosted (cloud) version instead of locally — two of
> the four deployments were already paid for — but reversed that decision
> the same day. The DeepSeek deployments were still being built, and
> running small check runs on the hosted version takes about 9 minutes per
> test run, one at a time. Running mainly on the hosted version would have
> stalled the whole campaign waiting on exactly the kind of delay this
> section is meant to avoid. So the pilot follows our standard approach:
> **run mainly on local containers, at the full number of test runs**, and
> keep whatever hosted small check runs did complete (all seven of the then-current setups for
> gpt-5-mini, plus one run per setup for the other three models as their
> deployments finish) as the small hosted verification sample.

We learned from the pilot that deploying to the cloud one step at a time
takes hours and slows down the real work. So our standing approach for
every case is:

1. **Our main results come from running the exact same container LOCALLY
   on the workstation, once, at the full number of test runs.** We run one
   local copy per model's batch (`azd ai agent run`), four batches running
   at the same time; every test run makes REAL calls to the AI models. As
   each test runs, a recording system called OpenTelemetry sends the
   recorded conversation live to the project's Application Insights
   (Azure's monitoring tool) — so it shows up on the Foundry Tracing page
   as genuine, honestly-labeled activity:
   `OTEL_RESOURCE_ATTRIBUTES=stjp.execution=local`, with the service name
   `stjp-<case>-local-<model>`. This keeps us to the same honesty standard
   as our earlier, non-hosted benchmarks: every record comes from a real
   run, correctly labeled as such. All of the report's tables come from
   these local runs.
2. **The hosted (cloud) version is a small verification sample, NOT a
   second full run.** Deployments happen in the background; once a hosted
   group is live, we run it 3 to 5 times for each setup and model (about
   10-15% extra cost). The purpose is only to confirm the identical
   container behaves the same way when Foundry hosts it — that its results
   fall within the same confidence range as the local runs, and the safety
   checker and scheduler behave identically. This gets reported as a short
   paragraph confirming consistency; it is never mixed into the main
   results tables.
3. **We are strict about correctly labeling where a result came from.** A
   recorded conversation from a local run is NEVER relabeled as if it came
   from a hosted agent, and recordings are never uploaded in a batch after
   the fact — only sent live, as the run happens. Every role is a separate
   AI agent making its own call on its turn (so each role's part of the
   recorded conversation proves it really is a multi-role run). Our
   anti-fabrication check searches the local logs and compares them
   against the server-recorded conversations to make sure they match.
4. We start analyzing local results as soon as each model's batch of runs
   starts producing them — we don't wait for everything to finish before
   beginning analysis.

## 5. Per-case preprocessing

In this order, all done automatically by AI helpers, without a person
needing to watch:

1. **Build the intent package** (the written task description each case
   runs from — PLAN_V3 §10.3): run
   `python experiments/scripts/intent_pipeline.py synth --all`. This
   produces a computer-generated package; its record of origin says
   `approved_by: auto-llm`, and every report says so openly.
2. **Draft the protocol with an AI model** (only where one doesn't exist
   yet): run `python experiments/scripts/draft_llm_protocols.py <case>`.
3. **Check the protocol**: nuscr first, then always scribble-java too
   (§3); record both results.
4. **Build the per-role files**: the state diagrams (EFSMs), the short
   per-role instructions, the generated safety checkers, and the
   scheduler's lookup tables — all built into the case's `agents/<case>/`
   container image.
5. **If the protocol changes** partway through the campaign, follow the
   rules in PROTOCOL_EVOLUTION: adding something new goes through a small
   "child" addition plus a combine-and-check step
   (`python -m stjp_core.compiler.incremental --parent ... --child ...`);
   changing or removing something means rebuilding everything from
   scratch. Every run's metadata records version fingerprints (hashes),
   and the grading tool `evaluate_run` refuses to grade results that mix
   different protocol versions together.

## 6. Tracing and evidence

- **Turn recording on**: every `main.py` calls `enable_foundry_tracing()`
  once when it starts (safe to call more than once; does nothing if
  `AZURE_AI_PROJECT_ENDPOINT` isn't set). Needed settings:
  `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` and
  `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true`. This requires the
  project's Application Insights connection to be set up (Project
  Settings → Connections). The hosted workflow additionally resolves that
  connection at server startup and sets
  `APPLICATIONINSIGHTS_CONNECTION_STRING` before constructing
  `ResponsesHostServer`; environment flags without this exporter are not
  sufficient.
- **Labeling each recorded conversation**: the service name is
  the per-model `FOUNDRY_AGENT_NAME` from the table in §0a; local execution
  is explicitly versioned `local`. Each test run's recording is tagged with
  `stjp.arm` (which setup), `stjp.case`, `stjp.model`, `stjp.trial`,
  `stjp.prompts_schema_version` (currently 2 — the version number of our
  prompt-writing rules), and the intent file's fingerprint (a short unique
  code identifying the exact file used). Safety-checker decisions are
  logged as events inside the recording.
- **Where to look**: the Tracing tab in the Azure portal (direct link:
  `https://ai.azure.com/resource/tracing?wsid=<ARM-id>`); it takes about
  30–60 seconds for a new recording to show up there. Filter by the exact
  trace ID persisted in the cell result and confirm the per-model agent
  identity. Do not use a broad time-window query as benchmark evidence.
- **Every test run leaves three separate records** (PLAN_V3 §2.3): a
  local one (the event log file `events_*.jsonl`, summary files, the
  prompts used in `prompts/<arm>/`, and the task description in
  `intent.md`, all at the top of the run's folder); a git one (the run's
  folder is saved to version control and pushed to the shared repository,
  even though it would normally be ignored); and a Foundry one (the
  recorded conversation in Application Insights). Our anti-fabrication
  check searches for distinctive sentences the AI model actually wrote in
  the local log, and confirms they also appear in the server-side
  recording.

## 7. Run matrix and order

- **The full test grid**: our 10 core setups (PLAN_V3 §10.8) × **4 AI
  models** (a 2-by-2 grid: **gpt-5.6-sol**, a strong closed model;
  **gpt-5-mini**, a weaker closed model; **DeepSeek-V4-Pro**, a strong
  open-weight model; **DeepSeek-V4-Flash**, a weaker open-weight model —
  see PLAN_V3 §1, revised 2026-08-05) × 30 test runs per setup and model
  (30 is the minimum for a headline claim; a quick n=10 pilot pass is
  allowed for early sanity checks but is never citable). Each model's batch of runs uses one fixed deployment,
  set through `AZURE_AI_MODEL_DEPLOYMENT_NAME`; both DeepSeek models get
  one small check run per setup first. We also plan one appendix test to
  find the point where a model gets too weak to help (using `gpt-5-nano`,
  on one case). Two more models are on standby and used only if needed:
  `qwen3-32b` (a second open-weight AI family, as a check that our
  open-model results aren't specific to DeepSeek) and `Kimi-K2.6` (a third
  open family).
- **Order of cases**: follow BENCHMARK_CASE_RANKING.md — Tier 1 first, then Tier 2
  (running `intel_report` early, since it also covers the required
  `lastrecv` shortcut-comparison check, run with the `--arms` option),
  then Tier 3 only where a report section specifically needs it.
- **One job per model at a time** (PLAN_V3 §9). We can report
  token-usage numbers from any run, but we can only make **speed claims
  from runs done one at a time, with nothing else competing for that
  model's capacity**.
- **Fail-fast preflight and resumability** (implemented in
  `hosted_campaign.py`): before a model wave, make one short real model call
  and require the pinned Microsoft subscription/tenant, exact deployment
  identity, positive prompt/completion tokens, positive call count, and a
  valid trace ID. Persist every `(model, arm, trial)` atomically under
  `cells/`; `campaign_manifest.json` is the state machine. Use
  `--resume <run-dir>` to skip valid cells. Two consecutive infrastructure or
  evidence failures open the model circuit breaker.
  Use `--preflight-only` before a new model/server combination. Every local
  invocation supplies fresh explicit session and conversation UUIDs; do not
  rely on `azd --new-session` alone because it previously restored stale MAF
  checkpoints.
- **Compatibility logs are derived**: parallel waves never write the same
  authoritative file. After all cells validate, the driver deterministically
  rebuilds `events_<arm>.jsonl` from per-cell `events.jsonl` files for existing
  summarizers.
- **Count every MAF model call**: `GroupChatBuilder` does not expose every
  internal orchestrator response in its outer result stream. Usage therefore
  comes from the shared `RetryingChatClient` interceptor, covering participant
  and orchestrator calls, and is accepted only with
  `capture_scope=all_chat_client_calls`. Participant-only historical MAF usage
  is invalid evidence. If its exact run-owned OTel server log remains
  available, use `scripts/reconcile_maf_usage.py <run-dir> <server.log>...
  --write`; it resolves only the cell's persisted trace IDs, rejects missing
  or wrong-model spans, and records both the previous and corrected usage.
- **MAF runtime acceptance checks**: participant requests must always contain
  a non-empty user message because selecting the same speaker twice can leave
  its MAF executor cache empty (GPT rejects an empty message list even when a
  DeepSeek model tolerates it). All MAF orchestrators must also stop on the
  protocol terminal label; otherwise deterministic scheduling can hit the
  workflow runner's 100-superstep convergence limit. The 40-cell pilot must
  exercise `maf_skills`, `maf_localvalid_gate`, and
  `maf_localvalid_sched` on every model before an n=30 campaign starts.
- As always, split test runs evenly across each branch on cases with a
  decision point.

## 8. Grading and reporting

Grading and reporting are unchanged from PLAN_V3 §4 and §10.7: **Set A**
checks whether every message followed the protocol (we replay the
recorded conversation through the same generated safety checker offline,
as an independent double-check); **Set B** checks whether the goals were
reached (using the exact-match rules written in each case's `case.yaml`
file; graded either strictly, or by role-pair† — a looser match —
depending on the setup); every violation is scored on our S0–S4 severity
scale, including the strictest S4 ("disaster") category; results include
Wilson confidence intervals (a way of stating a confidence range around a
percentage result); and our "era rule" still applies — rows tagged
`prompts_schema_version: 2` (the corrected prompts) must never be shown in
the same table column as older, version-1 rows, for the setups that were
corrected. Report tables follow PLAN_V3 §7, plus the new intent-scaling
table.

## 9. Subagent task breakdown

The director hands off the following work packages to AI helpers, one
package per helper, and reviews each result:

| # | work package | notes |
|---|---|---|
| S1 | Install and check every tool: `azd` and its hosted-agent extension, build scribble, get the nuscr program or Docker image, and run the startup check script (including `nuscr check`) | §2; write down version numbers |
| S2 | Run `intent_pipeline.py synth --all` and check the results and records it produced | §5.1 |
| S3 | Write AI-drafted protocols for any case missing one, run the checks from §3 on every case in the campaign, and write up a table of nuscr/scribble results | §3 |
| S4 | Write the `agents/<case>/` files (agent.yaml, Dockerfile, main.py) for each Tier-1 case, copying the existing pattern, with the switch between the 10 setups and the safety checker/scheduler built in | §4.2–4.3; the director designs the workflow template once, then it gets copied ("stamped") onto each case |
| S5 | Run `azd deploy`, then run local and hosted small check runs for every case and setup; confirm they show up on the Azure portal | §4.4 |
| S6 | Run the campaign: call each group the required number of times for each setup and model, collect the recorded conversations, and save each run's folder (events, prompts, intent.md) | §6–7 |
| S7 | Grade the results, verify them, build the report tables, and make sure old and new prompt versions are never mixed in one table | §8 |

The director keeps some tasks for itself and never hands them off:
designing the one shared workflow template (deciding what each setup
means, and building the safety checker/scheduler into it), any change to
what a setup means or how grading works, approving each checkpoint, and
writing the claims that go into the final report.
