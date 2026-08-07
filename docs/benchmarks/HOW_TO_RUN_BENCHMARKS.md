# How to run the benchmarks (Azure AI Foundry)

The complete, committed procedure for producing benchmark results — from
launching hosted-agent runs to the files the report tables are written from.
Terms used here are the canonical ones from [`GLOSSARY.md`](../reference/GLOSSARY.md):
**case** (a scenario under `experiments/cases/<case>/`), **setting** (one
configuration of a case — the harness flag is named `--arms` for historical
reasons), **deployment** (a model deployment in the Azure AI Foundry project,
e.g. `gpt-5-mini`), **run folder** (`experiments/cases/<case>/runs/<name>/`).

## 1. What you need first

- `az login` completed (the harness gets Azure credentials from the CLI).
- `JAVA_HOME` pointing at a JDK (Scribble protocol validation runs on Java).
- The deployment names you plan to use existing in the Foundry project
  (see `docs/reference/` Azure notes; the working pair in 2026-07 was
  `gpt-5-mini` and `gpt-5.4`, with `gpt-5.4-2` as a second `gpt-5.4`
  deployment for parallel capacity).

## 2. Run one case on one deployment — `case_runner.py`

This is the single entry point that does everything for one case: it creates
the hosted agents in the Foundry project, runs every requested setting n
times, and writes every log and summary itself. There is no separate
"fetch the logs" step — all data is persisted locally while the run happens.

```powershell
cd stjp\experiments
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-5-mini"     # which deployment (model)
python scripts/case_runner.py skills_safety/gem_dev_team 10 --arms bare,unchecked_skills,global_decentralized,min_llmvalid,spec_llmvalid_gate,min_llmvalid_gate,min_llmvalid_gate_nohint,min_llmvalid_sched
```

- The eight keys above are the canonical comparison settings 1–8 used in the
  run reports (`docs/6_RUN_REPORTS_V2_CLAIMS_AND_EVIDENCE.md`).
- To run the second model, run the same command again with
  `$env:AZURE_OPENAI_DEPLOYMENT = "gpt-5.4"`.
- If a run is interrupted, continue it — completed settings are skipped:

```powershell
python scripts/case_runner.py skills_safety/gem_dev_team 10 --arms ... --resume cases/skills_safety/gem_dev_team/runs/<run folder>
```

- Any wall-clock/speed claim needs `--sequential` (one setting at a time, so
  settings don't wait on each other's rate limit). Token and goal metrics are
  fine in the default parallel mode.

### What lands in the run folder

Run folders are named `<timestamp>-<deployment>-p<pid>-n<N>-dual` — the
deployment and the process id are in the name on purpose, so every folder
states which model produced it and two runs started in the same second can
never collide (both failure modes were real incidents, 2026-07-27/28).

| file | what it is |
|---|---|
| `events_<setting>.jsonl` | the raw log: every message of every trial, with monitor verdicts and per-goal progress |
| `prompts/<setting>/<Role>.system.md` | the exact system prompt each hosted agent was given (plus `index.json` with hashes and truncation flags) |
| `summary.json` | Set A per setting: violations, success rate with 95% CI, tokens, seconds |
| `summary_eval.json` | Set B per setting: goal achievement (strict and role-pair, per goal) |

`summary_eval.json` is produced automatically — `case_runner.py` calls the
committed `scripts/evaluate_run.py` at the end of the run. The tables in the
run-report docs are written from `summary.json` + `summary_eval.json`, and
`docs/reference/HOW_TO_USE_TRACES.md` shows how to re-derive every headline
number from the raw `events_*.jsonl` yourself.

## 3. Re-checking finished runs (no new trials, no cost)

```powershell
# regenerate both summaries from the existing logs (e.g. after metric fixes)
python scripts/case_runner.py <case> --summarize-only cases/<case>/runs/<run folder>

# audit that no goal predicate rejects payloads the anchor message actually
# delivered (the "fragile goal" measurement artifact found 2026-07-27)
python scripts/fragile_goal_audit.py cases/<case>/runs/<run folder>
```

Every result that goes into a report must pass the fragile-goal audit first.

## 4. Run a campaign — several cases, several deployments in parallel

`scripts/run_campaign.py` launches `case_runner.py` processes across
deployments. It is only a launcher: it starts runs, watches for stalls, and
decides when the next case starts. It never computes or records any result.

```powershell
cd stjp\experiments
python scripts/run_campaign.py my_campaign.yaml --dry-run   # print plan only
python scripts/run_campaign.py my_campaign.yaml             # run it
```

Campaign file:

```yaml
n: 10
settings: [bare, unchecked_skills, global_decentralized, min_llmvalid,
           spec_llmvalid_gate, min_llmvalid_gate, min_llmvalid_gate_nohint,
           min_llmvalid_sched]
sequential: false      # true when the campaign must support timing claims
stall_minutes: 25      # kill + resume a job whose newest log is this quiet
poll_seconds: 60
deployments:           # each deployment runs its list IN ORDER, one at a time
  gpt-5-mini: [skills_safety/gem_dev_team, agenticpay_settlement]
  gpt-5.4:    [skills_safety/gem_dev_team]
```

Job stdout goes to `experiments/campaign_logs/<timestamp>/` (git-ignored).
A job that keeps failing is skipped after a bounded number of retries and the
campaign exits non-zero, so a broken case can never loop forever.

### The three safety rules (each one is a past incident)

1. **One job per deployment at a time.** Two jobs on one deployment share its
   rate limit and starve each other. Deployments run in parallel with each
   other — that is safe, because rate limits are per deployment.
2. **Exactly one launcher process.** The launcher refuses to start if another
   launcher holds the lock file (`experiments/.run_campaign.lock`) or if
   `case_runner.py` processes from an earlier launcher are still alive.
   Incident (2026-07-28): an old launcher was left running while runs were
   being killed by hand; it treated every kill as a crash and restarted the
   run, so killed jobs kept "coming back" and duplicate runs burned tokens.
3. **Run folders are resolved by pid, never by the `LATEST` file.** Each
   case's `LATEST` file holds only one run-folder name. When the same case
   runs on two deployments at once, both overwrite it, so anything reading
   `LATEST` sees only the later run — the earlier one becomes invisible, and
   a launcher that trusted `LATEST` could resume one deployment's run into
   the other's folder. Incident (2026-07-28): caught before data was
   corrupted; the launcher now finds each run folder by the `-p<pid>-` tag
   that `case_runner.py` puts in the folder name.

So: parallel running is safe **with these rules enforced** — and
`run_campaign.py` enforces all three. Running several `case_runner.py`
processes by hand without them is how the incidents above happened.

## 5. What not to do

- Do not run two campaigns (or a campaign plus hand-launched runs) at the
  same time — rule 2 exists because this happened.
- Do not compare wall-clock seconds from a parallel run; use `--sequential`
  (recorded in `summary.json` as `execution_mode`).
- Do not report a result before `fragile_goal_audit.py` passes on its run
  folder.
- Do not compare settings at different n (see
  `docs/6_RUN_REPORTS_V2_CLAIMS_AND_EVIDENCE.md` — every comparison table
  holds n constant).


---

## 6. Run a case as a HOSTED AGENTS GROUP (the portal "Hosted" surface)

§2–§5 run the 8-setting ladder on the **classic Agent Service** (per-role
agents + threads, previous/classic portal view). This section is the separate,
required surface: each case is also deployed as ONE Azure AI Foundry **hosted
agent group** (portal agent type **"Hosted"**, `stjp-<case>-group`) and invoked
**n=10 per model = 20 traces per case**, visible on the Hosted surface a
reviewer audits. A run not visible here does not count as delivered.

**What a hosted group is (design).** One case = one MAF GroupChat, hosted as a
`WorkflowAgent`: the **orchestrator holds the validated protocol** (it selects
who speaks each round); each **participant holds only its projected local
contract**. This is the hosted twin of the `maf_groupchat_llmvalid_orch` arm.
The gate and the EFSM scheduler cannot be interposed inside a sealed group, so
the hosted row measures the group's own coordination (like the MAF kinds) — the
gate/scheduler settings live on the classic surface (§2). Name both surfaces per
case so no reader conflates them.

**Files (already built, under `foundry_hosted_agents/agent-framework-agent-with-remote-mcp-tools-responses/`):**
- `group_main.py` — generic entrypoint: reads a `group_spec.json`, builds
  GroupChat -> WorkflowAgent -> `ResponsesHostServer`. Model from
  `AZURE_AI_MODEL_DEPLOYMENT_NAME`; spec path from `STJP_GROUP_SPEC`.
- `gen_group_specs.py` — renders each role's projected local contract
  (scribble-java runs on YOUR machine) + the orchestrator protocol prompt, and
  bakes them into `agents/<case>/group_spec.json`. The container needs no Java.
- `agents/<case>/group_spec.json` — one per case (all 13 present, each
  validated to build a real MAF GroupChat).

### 6.1 Regenerate the specs (only after a protocol/prompt change)

```powershell
cd stjp
python foundry_hosted_agents/agent-framework-agent-with-remote-mcp-tools-responses/gen_group_specs.py
```
Every spec must build a GroupChat locally before deploy (this is the smoke
test; `ResponsesHostServer` itself only exists in the container): for each
`agents/<case>/group_spec.json`, constructing an `Agent(...)` per role plus the
orchestrator and calling
`GroupChatBuilder(participants, orchestrator_agent=orch).with_max_rounds(...).build()`
must succeed. **13/13 required before any azd deploy.**

### 6.2 Deploy one case on one model — `azd`

The deployed entrypoint is `src/<name>/main.py` (see `Dockerfile`). Deploying a
case = point that entrypoint at `group_main.py`, ship the case's spec, and set
the two env vars, then `azd up`. **Model is an env var — redeploy per model,
never bake it into code.**

```powershell
cd stjp\foundry_hosted_agents\agent-framework-agent-with-remote-mcp-tools-responses
# 1. stage this case + model
Copy-Item group_main.py "src\<name>\main.py" -Force
Copy-Item "agents\<case>\group_spec.json" "src\<name>\group_spec.json" -Force
#    agent.yaml: name = stjp-<case>-group   (hyphens; matches group_spec.group_name)
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "gpt-5-mini"   # then re-run for gpt-5.4
$env:STJP_GROUP_SPEC = "group_spec.json"
# 2. deploy (provisions + remote-builds the container + publishes the group)
azd auth login      # once
azd up              # reads azure.yaml (host: azure.ai.agent, remoteBuild: true)
```
Deploy each of the 13 cases twice (once per model). Confirm each appears in the
portal Agents page as type **Hosted**, status **Running**.

> **Verification status of this section:** the spec build, the `azd` config
> (`azure.yaml` / `Dockerfile`), the env keys, and `azd` version (1.28.1) are
> verified. The `azd up` deploy + the invocation below were authored from that
> config and are the procedure to follow — mark a case "delivered" only after
> its 20 traces are actually visible on the Hosted surface, per §8 rule 7.

### 6.3 Invoke n=10 per model and grade

Invoke the deployed group through the Responses/Agents API (one session per
trial, n=10), capture each transcript, and grade it with the SAME Set A/B goal
predicates as the ladder (a transcript-to-events parser feeds `evaluate_run` /
`policy_eval`). Persist under `experiments/cases/<case>/runs/<dir>` exactly like
a ladder run, with a `surface: hosted_group` marker in the run metadata so the
report row is labeled. Then verify per §8 before it enters a table.

### 6.4 Do all 13 cases

Drive 6.2–6.3 case-by-case, **one deploy per model deployment at a time** (§4
rule 1). A case is done only when both models show 10 completed, graded,
portal-visible sessions.

---

## 7. Clean benchmark report format (every table, every case)

The reports drifted before (three arm vocabularies, mixed metric names,
14-row tables). The canonical format, enforced from now on:

1. **One combined table per case, both models side by side.** Columns in this
   fixed order: `# | Setting | GCR mini | GCR 5.4 | Violations mini/5.4 |
   Disasters mini/5.4 | Calls mini/5.4 | Tokens mini/5.4`. MAF kinds and the
   hosted-group row are appended as clearly labeled extra rows, never mixed
   into the numbered 1–8 ladder.
2. **The eight settings in the same order in every table**, by their canonical
   names/numbers (legend once, at the top). Never the internal keys, nor the
   old A/B/C or `Nr`/`gate-v` shorthands in prose.
3. **One provenance line above each table:** "Same case, same protocol, same
   turn limit, n=X per setting per model. Runs: `<mini dir>` · `<5.4 dir>`."
4. **† only on settings graded role-pair** (1–2 and the no-protocol MAF kind),
   with the one-line legend. **Disasters** = the S4 catastrophe (policy-scored,
   or a stated manual trace); "—" only when genuinely unscoreable, with a
   footnote saying why and the verified count.
5. **Wilson 95% CI** on headline goal rates; **Fisher exact** p on key deltas.
   Tokens are the efficiency metric; wall-clock only from `--sequential` runs.
6. **No narrative of what was fixed or what went wrong in the report.** The
   report presents the latest verified results cleanly. Fix-history lives in
   git, not in the tables.
7. **Cost claims compare only completing settings.** The PRIMARY reported
   numbers are always the actual end-to-end totals — every participant,
   orchestrator, retrieval, summarization, retry, and (Level 1) compilation
   token. The FAIR COMPARISON normalization (subtracting the shared
   intent/goals prose) is a SECONDARY robustness check printed beside the
   raw numbers, never in place of them; and never subtract a treatment
   (setting-3 protocol text, setting-2 skills, the contract table). The
   prose subtraction is valid at paragraph-scale intents only — see §9.
8. **Policy-version provenance.** For any run on a composed or amended
   protocol, the provenance line (rule 3) additionally carries the
   **manifest root hash** — one hash committing to the full version:
   protocol, sidecars (`.refn`/`.fail`), per-role contracts, monitors,
   safety policies, and oracles (i.e., over both `H_r^runtime` and
   `H^evaluation` of `HOW_TO_IMPLEMENT_SUBSESSIONS.md` §6) — printed as
   "policy-version `<root8>`", with the component hashes recorded in run
   metadata. A table never mixes rows produced under different policy
   versions — the hold-n-constant rule extended to
   hold-policy-version-constant (§9 rule 7).

---

## 8. Error-avoidance checklist — the operational mistakes to never repeat

Each item is a real incident from building this campaign. Check every one
before and after a run; none is about STJP itself — they are harness/operator
errors that silently corrupt otherwise-good science.

1. **`--arms` is COMMA-separated.** `--arms bare,unchecked_skills,...` runs all
   listed; `--arms bare unchecked_skills ...` (spaces) runs ONLY `bare` and the
   rest are ignored. A run that quietly did one setting still looks "done"
   (exit 0). Always confirm the log's `scenarios: [...]` line lists every
   requested arm.
2. **Per-arm completeness check on EVERY run.** A transient Azure error
   (`HttpResponseError` on `list_agents` during setup) can leave some arms at
   0/N trials while others finish — and a `summary.json` can be written anyway.
   Count `trial_end` markers per arm from the raw `events_<arm>.jsonl`; require
   exactly N for every arm. "arms present" in the summary is not enough.
3. **A partial or in-flight run is NEVER citable.** Wait for the FINAL N, then
   verify. (sdlc: a 65/80 partial said "only setting 8 finishes"; the 80/80
   final refuted it.) Peeked mid-run numbers can and do reverse.
4. **Kill hung supervisors before relaunching; check for zombies AND file
   handles.** A `case_runner.py` process can hang for days on a slow
   no-protocol arm, holding `events_*.jsonl` open — which blocks the final
   `summary.json` write and makes the run-dir rename fail "Access denied".
   Before relaunch: list `python%` processes and kill only the specific
   `case_runner.py <case>` PIDs (leave other projects' python alone).
   "Access denied" on a rename means a live handle inside, not a permission
   problem.
5. **Trace analysis is EXACT, never fuzzy.** A substring heuristic once reported
   4/10 publish-before-review disasters; the ordered, per-trial, per-attempt
   walk showed 0/10. Build the label matcher from the ACTUALLY-OBSERVED labels
   (enumerate per sender first), respect event ORDER, and spot-read full traces
   where it fires and where it does not. A quick heuristic decides where to
   look next — it is never evidence.
6. **Verify payload VALUES, not just message shape.** memory_race graded 10/10
   on shape while agents wrote the delta (50) instead of the new balance (150)
   and `Done` carried no value — because the protocol never pinned the payload
   semantics and the `.refn` guard file was in a format the parser silently
   ignored (parsed to empty). Check the actual numbers in the events, and
   confirm every guard file parses to non-empty refinements.
7. **"Hosted" means the deployed group agents (§6), never the classic per-role
   Agent Service agents (§2).** Calling the ladder path "hosted" made a portal
   audit look like the benchmark never ran. Name the surface precisely in
   every doc and table.
8. **Derive names/dirs; never hardcode.** Terminal labels come from
   `case.yaml`, not memory (a hardcoded label was wrong). Resolve run folders by
   the `-p<pid>-` tag, never `LATEST` (two deployments overwrite it). Confirm a
   run dir is the intended one (a MAF-appendix-only dir once gave a vacuous
   "ALL MATCH").
9. **Do not assume replication is mechanical — check structure first.** The
   hosted `add_chain` template fit only the 3 single-pass-linear cases; the
   other 10 (recurring senders, branches, loops) needed the GroupChat design.
   A role named `Orchestrator` (gem_dev_team) collides with the orchestrator
   agent's executor id — use a collision-proof name.
10. **PowerShell gotchas:** `$PID` is read-only (use another loop variable);
    a `Rename-Item` that fails "Access denied" means an open handle; prefer
    killing only the exact target PIDs, never a blanket `python` kill (other
    projects run python too).
11. **One job per deployment, exactly one launcher** (§4). Two jobs on one
    deployment starve each other; a stray second launcher treats hand-kills as
    crashes and resurrects them, burning tokens.

---

## 9. Scope of this ladder, and the fairness rules for big-intent (Level 1) benchmarks

Everything in §2–§8 is the **runtime-artifact benchmark** ("Level 2"): every
WITH setting starts from the same validated, endorsed drafted protocol, and the
compile step (drafting + validation + goal anchoring) sits outside the measured
cost, disclosed separately. Those results are valid **for paragraph-scale
intents only**. The FAIR COMPARISON subtraction of shared intent/goals prose
(§7 rule 7) is legitimate only because that prose is ~63–115 tokens/call; a
standing policy of realistic size (HANDBOOK.md scale: 8K–79K tokens) breaks
both the accounting (the policy would dominate every intent-carrying setting's
bill, and it is a *treatment*, not background) and the harness itself (the
classic Agent Service truncates installed prompts at 8,000 chars — settings
1/3/5 could not even install). Never extend a Level-2 number to a big-intent
claim; run the Level-1 suite under the rules below.

**Level 1 — the end-to-end compilation benchmark.** Question: starting from
the same source artifacts, which complete system produces safe, successful
executions most efficiently? The fairness rule is **equal source information
and honest accounting of transformations** — never nominal equality
manufactured by copying the same giant text into every prompt. Each rule below
is a requirement, not a style preference:

1. **Three recorded objects, never one intent string.** Standing policy P
   (the long-lived handbook/policy document), immediate request R (this run's
   task), environment E (files, messages, records, facts discovered during
   execution). P and R are immutable artifacts stored once with content
   hashes. E is runtime data — it is never compiled into the protocol.
2. **Two stages of information ownership — never one shared channel at
   runtime.** *Compilation stage:* every system starts from the same
   immutable P+R artifacts (equal source information). *Runtime stage:* each
   condition receives ONLY the artifact its row in the five-condition matrix
   (below) specifies — runtime retrieval from P is a treatment feature of
   the source condition (L1) alone, with a pre-registered budget and
   strategy and every retrieval/summarization call counted. Conditions that
   execute from compiled artifacts (L2–L5) must NOT also read P at runtime;
   letting them would un-isolate the treatment. P is never pasted per-role
   into system prompts in any condition. The immediate request R is
   delivered uniformly at session start to every condition.
3. **Goals never appear in any prompt, and protocol labels never define the
   shared exam.** Each frozen criterion carries an ARM-INDEPENDENT
   semantic/world-state verifier as its primary check (right actors, right
   direction, right ordering, right values, right final world state — under
   ANY label), plus a secondary protocol mapping used for conformance
   scoring and compiled runtime guards; exact-label matching applies only to
   protocol-aware conditions (the existing strict-vs-role_pair discipline,
   extended). Criteria are distilled from P+R by a recorded step with full
   provenance — record format in
   [`HOW_TO_IMPLEMENT_SUBSESSIONS.md`](HOW_TO_IMPLEMENT_SUBSESSIONS.md) §7.
4. **The grading instruments are the three-part stack of
   [`GOAL_QUALITY_AUDIT.md`](GOAL_QUALITY_AUDIT.md), never goals alone.**
   Existential goals cannot express safety (its finding B2): every Level-1
   case carries (a) achievement goals, (b) safety policies (ordering /
   at-most-once / prohibited-action, scored by `policy_eval.py`), and (c)
   world-state oracles where an environment E exists (the `memory_race`
   `environment.py` precedent), plus the per-goal discrimination gate
   (`goal_quality.py`). All of it is distilled from the SOURCE, never from
   the protocol: every condition — including full STJP — is graded against
   it, so a clause the compiler dropped is a *failed criterion for STJP*,
   not a vanished one. This is what prevents a system from omitting a hard
   clause from both its protocol and its goals and then scoring perfectly
   against its own incomplete interpretation.
5. **Charge the compile to the right party; show the amortization.** Three
   ledgers, never merged: (a) *common benchmark cost* — semantic-criterion
   extraction from P+R, human approval, oracle/verifier authoring: this
   builds the exam that grades EVERY condition and is charged to no
   condition; (b) *protocol-compilation cost* — reading P, LLM protocol
   drafting, validation/repair rounds, endorsement (if measured), projection,
   guard generation, and mapping the frozen criteria onto protocol events:
   charged EQUALLY to every condition that consumes the compiled artifacts
   (L2–L5), never to L5 alone — L2–L4 are MAF conditions, but they run on
   this pipeline's output; (c)
   *runtime cost* — execution under each condition. Report (b)+(c) total and
   the per-run amortized cost at N = 1, 10, 100 plus the break-even N. A
   standing policy often governs thousands of runs — show it, never assume
   it.
6. **Source-visible sections are the DEFAULT decomposition evidence, not a
   straitjacket.** Real SOP workflows cross-cut sections (a §12 procedure
   hinging on §4 authorities, §5 channels, §18 templates — the HANDBOOK.md
   anatomy), so clause↔module↔workflow mappings are many-to-many. The
   fairness rule: the section structure of P is visible to every setting for
   free; any merge or split BEYOND that visible structure is compile work —
   LLM-done, logged in the manifest, and charged to the compile bill (rule
   5b).
7. **Version-stamp everything.** Run metadata and every table's provenance
   line carry the policy version (protocol hash, guard-sidecar hash, goals
   hash — §7 rule 8). A table never mixes policy versions.
8. **Cost-of-change runs require the stale-guard canary.** After any policy
   amendment, include a seeded trial whose payload value falls BETWEEN the
   old and new thresholds, and refuse to grade unless every layer hash
   (protocol, sidecars, goals, contracts, monitors) derives from the same
   module version. An incomplete update must fail loudly — a stale monitor
   scoring zero violations against the OLD rule is a false-safe result for
   the treatment arm, the worst corruption this benchmark can produce.
9. **Three amendment kinds, pre-registered:** (i) *consistent* amendment —
   measures dependency-scoped recompile cost against the baseline's zero
   update cost but unchanged full-document per-run cost. (ii) *conflicting*
   amendment — claim rejection only per detector class: a STRUCTURAL
   conflict (deadlock, projectability, choice coherence) is rejected by
   Scribble with a named counterexample at zero run cost; a GUARD/REFINEMENT
   conflict is rejected only where a specific implemented checker detects it
   (static SMT discharge is NOT implemented — do not claim it); a SEMANTIC
   prose conflict escalates to human / equivalence-instrument review. The
   in-context settings execute on the inconsistent document in all three
   classes and their violation rates are measured. (iii) *mid-horizon*
   amendment (an authoritative update arriving during execution) — every
   amendment declares its pre-registered EFFECTIVE-TIME rule: grandfather
   running sessions, apply at the next safe boundary (a subprotocol call
   boundary), or immediate typed abort (E10) plus recompile; immediate
   in-flight migration is NOT currently supported and must not be claimed.
   In-context settings may genuinely adapt mid-horizon. Report kind-(iii)
   losses honestly; do not design them out.
10. **Additive, never a retrofit.** Level-1 cases live in new case
    directories with a new `case.yaml` schema version. Existing Level-2
    cases, runs, and reports are frozen and stay citable with the scope
    statement above. Nothing in this section changes a case mid-campaign.

### The five-condition matrix (Level 1) — one knob per step

The Level-1 comparison is THIS ladder. L2→L3→L4→L5 are the strict
single-component ablations (representation → projection → enforcement →
scheduling); L1→L2 is NOT single-knob — it compares source-policy
orchestration with compiled-protocol orchestration, changing both the
representation and when the transformation cost is paid, so it is a valid
end-to-end treatment comparison but is never cited with the same
attributional strength as L2→L5. Implementations must not blur adjacent
rows; every condition is graded by the same frozen source-derived
instruments (rules 3–4) and gets R at session start (rule 2).

| # | Condition | Controller (orchestrator) input | Participant input | Enforcement / scheduling | Nearest existing arm |
|---|---|---|---|---|---|
| L1 | MAF intent (source) | R + retrieval access to P (counted, pre-registered budget) | neutral role prompt (role description only) | MAF LLM orchestrator | `maf_groupchat` |
| L2 | MAF global | R + validated global protocol G | neutral role prompt | MAF LLM orchestrator | — (new: G moves to the controller, participants stay neutral) |
| L3 | MAF projected | R + G | projected local contracts | MAF LLM orchestrator | `maf_groupchat_llmvalid_orch` |
| L4 | MAF projected + gate | R + G | IDENTICAL local contracts as L3 | MAF LLM orchestrator + gate | — (new; local MAF runner only — the gate cannot be interposed in a sealed hosted group, §6) |
| L5 | Full STJP | — (deterministic) | IDENTICAL local contracts as L3/L4 | gate + EFSM scheduler | `min_llmvalid_sched` |

Deltas: L1→L2 = source-policy orchestration vs compiled-protocol
orchestration (end-to-end treatment comparison, see above); L2→L3 =
projection to participants; L3→L4 = enforcement; L4→L5 = LLM orchestrator
replaced by the deterministic EFSM scheduler — the last three are the
single-component ablations. Only L1 touches P at runtime (rule 2); L2–L5
consume compiled artifacts and share the protocol-compilation bill equally
(rule 5b). The Level-2 everyone-carries-G configuration
(`maf_groupchat_llmvalid`) is kept only as a comparability row, never mixed
into this ladder. Prompts must be byte-identical where the matrix says
IDENTICAL — that is the control that makes L3→L4→L5 attributable to the
runtime alone.

The compiler machinery Level 1 depends on — modular child protocols,
incremental recompilation, complete per-role artifact hashing — is specified
in [`HOW_TO_IMPLEMENT_SUBSESSIONS.md`](HOW_TO_IMPLEMENT_SUBSESSIONS.md). Its
**Phase 0 gaps must be closed before any Level-1 or cost-of-change run is
launched** — four of them, verified in code, each capable of silently
corrupting a result.
