# Hosted-group workflow spec — stjp-sdlc-release-gate-group (10 arms in one WorkflowAgent)

**In plain terms:** this document tells a programmer exactly how to build
the cloud-hosted version of one of our benchmark cases —
`sdlc_release_gate`, a 7-role code-release approval workflow. It lists
which files to write, the exact format of requests and responses, and the
safety rules the code must follow. It assumes the reader is a programmer
and keeps this project's technical names, but explains each one the first
time it appears.

**Arm rename, 2026-08-05** (PLAN_V3 §10.8, "Final arm naming"): the 7-arm
matrix this spec originally described (+ `global_decentralized`, added the
same day) was renamed to a uniform `(maf_)?(global|local)valid(_gate|_sched)?`
vocabulary, plus two real-skill-file baselines and one genuinely new arm:

| new name | old name | meaning |
|---|---|---|
| `skills` | `bare` | real published skill files + user intent; round-robin; no protocol |
| `maf_skills` | (new) | same skill files + intent, MAF GroupChat runtime |
| `globalvalid` | `global_decentralized` | whole validated plan as text, round-robin, observe-only |
| `maf_globalvalid` | `maf_groupchat_llmvalid` | whole validated plan as text, MAF runtime |
| `localvalid` | `min_llmvalid` | validated projected per-role local contract, round-robin, observe-only |
| `maf_localvalid` | `maf_groupchat_llmvalid_orch` | same local contracts, MAF runtime (orchestrator holds intent+plan) |
| `localvalid_gate` | `min_llmvalid_gate` | local contract + gate blocks rule-breaking messages |
| `maf_localvalid_gate` | (new) | same local contracts and MAF AI orchestrator + custom pre-broadcast gate |
| `localvalid_sched` | `min_llmvalid_sched` | + EFSM-driven turn selection (full STJP) |
| `maf_localvalid_sched` | (new — feasibility confirmed same day) | MAF GroupChat + local contracts + EFSM-driven speaker selection; deliberately ungated to isolate scheduling |

The rest of this document uses the NEW names exclusively; this container
has no legacy-key aliasing (it is rebuilt fresh from
`build_hosted_artifacts.py` on every deploy, so there is no old run dir
that depends on the container resolving an old key).

**Key terms used throughout this document:**
- **arm** — one configuration being tested (for example, with or without
  the safety checker). This project tests 10 "core arms."
- **orchestrator / subagent** — the "orchestrator" is the lead AI
  directing this project's work; a "subagent" is an AI helper it assigns
  a specific task to.
- **WorkflowAgent** — the Microsoft Agent Framework (MAF) class that runs
  a whole multi-role team as one deployable unit.
- **EFSM** (Extended Finite State Machine) — a diagram of which messages
  a role is allowed to send or receive at each stage of the protocol.
- **gate** — the safety checker that blocks a role from sending a
  message that breaks the protocol. (Section 5 below also uses "gate" in
  its everyday sense of "checkpoint" — that is flagged where it occurs.)
- **scheduler** — the part of the system that decides whose turn is next,
  based on the EFSM diagram, instead of a fixed order.
- **round-robin** — taking turns in a fixed order, role by role.
- **azd** — the Azure Developer CLI, Microsoft's command-line tool for
  deploying cloud resources.
- **span** — this project's technical name for one recorded segment of a
  conversation, viewable in Azure's Tracing tool. Below, "recorded
  conversation" is used in prose, with "span" noted once alongside it.
- **model batch** — a full round of test runs made against one AI model
  deployment (this project's shorthand for this is a "wave").

**Orchestrator-authored spec, 2026-08-05.** This is what the S4 subagent
(the AI helper assigned to build the workflow — "S4" is the build stage
defined in `docs/benchmarks/BENCHMARK_IMPLEMENTATION_STEPS.md`) must implement. Any
deviation from this spec requires the orchestrator's sign-off. Pattern to
follow:
`foundry_hosted_agents/agent-framework-agent-with-remote-mcp-tools-responses/agents/airline_seat/`
(agent.yaml / Dockerfile / main.py / requirements.txt + `azure.yaml`
entry). Rules source: `docs/benchmarks/BENCHMARK_IMPLEMENTATION_STEPS.md` §4,
PLAN_V3 §10.6.

## 1. Two components

**(A) Host-side artifact builder** —
`experiments/scripts/build_hosted_artifacts.py <case_id>`: runs on the
workstation (needs scribble-java — our tool that checks a protocol and
breaks it down into per-role instructions), writes
`foundry_hosted_agents/.../agents/sdlc_release_gate/artifacts/`:

- `case_meta.json` — case_id, roles (ordered), terminal_label (the
  message that signals the workflow is finished), max_steps (the turn
  limit), branch_hints (hints telling a trial which decision branch to
  take), intent sha256 (a short fingerprint identifying the exact task
  description used — "sha256" is a standard way to fingerprint a file),
  prompts_schema_version: 2 (the version tag for our current
  prompt-writing rules).
- `efsm.json` — per-role EFSM from
  `get_all_efsms(llm_drafts/valid/v1.scr, "SdlcReleaseGate", roles)`:
  states, initial state, accepting states (the states where a role has
  finished its part), transitions
  [{source,target,direction,label,peer,payload_type}].
- `refinements.json` — from `load_refinements_for_protocol` (llm-valid
  path), serialized predicates as source strings (extra conditions
  checked on a message's actual content — for example "amount must be
  positive" — beyond just checking that the message type itself is
  allowed).
- `prompts.json` — `{arm: {role_or_special: system_prompt}}` for the 10
  core arms, built with the EXISTING repaired builders (import from
  `experiments/baselines/instructions.py`; never re-implement):
  skills / maf_skills→build_unchecked_skills_instructions (real published
  per-role skill file; maf_skills additionally gets `__orchestrator__`
  from maf_groupchat._build_orchestrator_instructions(case), no protocol);
  globalvalid / maf_globalvalid→
  build_global_spec_fairintent_instructions(override=llm-valid)
  (maf_globalvalid additionally gets `__orchestrator__`, no protocol);
  localvalid / localvalid_gate / maf_localvalid_gate /
  localvalid_sched / maf_localvalid_sched→
  build_spec_minimal_instructions(override=llm-valid) (identical string,
  one entry reused; maf_localvalid_sched gets NO `__orchestrator__` entry
  — speaker selection is the programmatic EFSM selection_func, not an LLM
  orchestrator call);
  maf_localvalid / maf_localvalid_gate→build_spec_minimal_instructions(override)
  + `__orchestrator__` with protocol_text (reuse the runner's setup logic).
  Case loaded at intent_scale="doc" (the full-length task description,
  not the short paragraph version). Also write per-prompt sha256 index.
- `goals.json` — goals from llm_drafts/valid/goals.yaml AND canonical
  case.yaml goals (both kept; grading is driver-side, this is for
  reference only).

**(B) Container** — `main.py` served by `ResponsesHostServer`
(ResponsesHostServer is the MAF class that answers incoming requests),
one `WorkflowAgent`-compatible group `stjp-sdlc-release-gate-group`
(agent.yaml: kind hosted, host azure.ai.agent, docker remoteBuild,
protocols responses 2.0.0, uses firstProject, cpu 0.5/mem 1Gi). Model:
`FoundryChatClient(model=env AZURE_AI_MODEL_DEPLOYMENT_NAME)`
(FoundryChatClient is the MAF class that connects to an Azure AI Foundry
model deployment) — model pinned per deployed instance; NO model logic
in-container. **Parallel-model deployment (2026-08-05):** azure.yaml
declares FOUR instances of this same container, one per matrix model,
named `stjp-sdlc-release-gate-group-{sol,mini,v4pro,v4flash}` with
AZURE_AI_MODEL_DEPLOYMENT_NAME set to gpt-5.6-sol / gpt-5-mini /
DeepSeek-V4-Pro / DeepSeek-V4-Flash respectively. The four model batches
run CONCURRENTLY (separate deployments = separate quotas; no
cross-batch contention on token metrics). Within a batch, arms share
that model's deployment: wall-clock time (real elapsed time) is
*indicative only*; a citable speed claim needs the dedicated sequential
pass (driver `--sequential`, one model, one arm at a time) run after the
main campaign.

## 2. Request/response contract

Request text = JSON: `{"stjp_arm": <one of 10 core keys>, "trial": int,
"branch_hint": str|null, "max_steps": int|null (default case_meta)}`.
Response text = JSON trial record:

```json
{"arm":..., "model":..., "trial":..., "case":"sdlc_release_gate",
 "prompts_schema_version":2, "intent_sha":...,
 "events":[{"step":n,"sender":..,"receiver":..,"label":..,"payload":..,
            "gate_verdict":"delivered|rejected", "reject_reason":null|...}],
 "blocked_attempts":[...same shape...],
 "usage":{"prompt_tokens":n,"completion_tokens":n,"calls":n},
 "terminated_by":"terminal_label|max_steps|efsm_end|error",
 "error":null|str}
```

`gate_verdict` records the safety checker's decision on that message
("delivered" = allowed through; "rejected" = blocked). All numbers come
from real response usage. The DRIVER (the campaign script described in
§4) persists evidence; the container returns it. Every trial also sets
attributes on its recorded conversation (span): stjp.arm, stjp.case,
stjp.trial, stjp.model, stjp.schema=2 (enable_foundry_tracing once at
startup; gate rejections are logged as events inside the recording).

## 3. Arm semantics in-container (the treatment — byte-exact)

Role agents: one Agent per role, instructions from prompts.json[arm].
Per-turn user message: the session view (reuse the format of
`stjp_core/foundry/session_helpers.py::build_view` — copy the exact
format string into the container or import if dependency-light). Replies
parsed as the one-JSON action schema ({"send_to","label","payload",
"rationale"}); unparseable → treated as WAIT, counted in usage.

| arm | loop |
|---|---|
| skills | fixed round-robin over roles, real published per-role skill file as the prompt; stop on terminal_label or max_steps |
| maf_skills | same skill-file prompts, agent_framework `GroupChatBuilder(participants, orchestrator_agent)` (MAF's group-chat orchestration class) exactly as experiments/baselines/maf_groupchat.py does; orchestrator prompt from prompts.json |
| globalvalid | round-robin, whole validated plan as text; the monitor (the safety-checking component) OBSERVES only: the EFSM walker (the code that steps through the EFSM diagram) records would-be verdict per event but always delivers |
| maf_globalvalid | same whole-plan-as-text prompts, MAF GroupChat with an orchestrator agent |
| localvalid | round-robin, projected local contract; the monitor OBSERVES only, same as globalvalid |
| maf_localvalid | same local-contract prompts, MAF GroupChat; orchestrator carries the protocol |
| localvalid_gate | round-robin + GATE: EFSM walker (from efsm.json + refinements.json; evaluate refinement predicates with eval on payload string exactly as stjp_core/monitor does) REJECTS off-contract sends pre-delivery; re-prompt sender once per turn with rejection reason + its enabled actions (the liveness-hint variant, hints=True) |
| maf_localvalid_gate | same local contracts and LLM orchestrator as maf_localvalid; a custom `AgentBasedGroupChatOrchestrator` validates before MAF's default transcript append/broadcast path, records rejected output only in `blocked_attempts`, and re-prompts the same participant |
| localvalid_sched | gate + EFSM SCHEDULER: poll only roles whose current EFSM state has an enabled SEND; stop when all roles reach accepting states |
| maf_localvalid_sched | same local-contract prompts, MAF GroupChat, but NO orchestrator agent: `GroupChatBuilder(selection_func=...)` — confirmed feasible 2026-08-05, a documented first-class alternative to `orchestrator_agent` — picks the next speaker with the SAME EFSM enabled-SEND rule as localvalid_sched. Deliberately ungated to isolate scheduling |

Monitor state advances ONLY on delivered events (committed reality), same
as the classic gate. Payload-guard evaluation failures (unevaluable) =
allow + flag, matching stjp_core monitor behavior.

## 4. Driver — `experiments/scripts/hosted_campaign.py`

`python hosted_campaign.py sdlc_release_gate --arms <10> --n 30
[--models gpt-5.6-sol,...] [--endpoint-mode local|hosted]`

- Invokes the group (local: `azd ai agent run` server; hosted: the
  project's responses endpoint for the deployed agent) once per
  trial×arm; retry-to-success ≤3 attempts per trial using the SAME
  per-arm success rule as case_runner (strict vs role_pair — "strict"
  requires an exact match against the protocol's own vocabulary;
  "role_pair" is a looser match used for arms that never saw that
  vocabulary — via evaluate_run.VOCABULARY_ARMS; goal predicates from
  llm-valid goals.yaml / canonical as per arm — reuse case_loader +
  goal_elicitor.verify_goals_against_trace, do not re-implement).
- Persists a STANDARD run dir under
  experiments/cases/skills_safety/sdlc_release_gate/runs/<ts>-hosted-<model>-n30/:
  events_<arm>.jsonl in the existing schema (message events + attempt_end
  / trial_end markers with the same field names case_runner emits —
  study `_persist`/emitter usage in experiments/scripts/case_runner.py
  and match it so summarize_run + evaluate_run work UNCHANGED), plus
  prompts/<arm>/<Role>.system.md from prompts.json, intent.md via
  case_runner._persist_intent, and hosted_meta.json (agent id, sampled
  recorded-conversation ids, endpoint, model batch).
- Set A verdicts (the protocol-conformance check, as opposed to Set B's
  goal-completion check): driver replays each trial's delivered events
  through the LOCAL stjp_core SessionMonitor against llm_drafts/valid
  (the independent re-derivation) — container verdicts are cross-checked
  against this replay and any mismatch is a hard error in the report.
- Branch balance: alternate branch_hint per trial from case branch_hints.

## 5. Acceptance gates (implementer must demonstrate, in order)

(These "gates" are checkpoints to clear, in the everyday sense of the
word — not the in-container safety checker defined at the top of this
document.)

1. `build_hosted_artifacts.py` output: prompts.json sha-indexed; skills
   prompt for Author == build_unchecked_skills_instructions output
   byte-for-byte (assert in a test snippet).
2. Container logic small check run without a real AI model: a
   `FakeChatClient` (a stand-in that returns pre-written replies instead
   of calling a real AI model, so this check costs nothing and needs no
   network) drives one trial of localvalid_gate and localvalid_sched
   through main.py's loop classes; gate rejects a scripted off-contract
   send; sched makes only enabled-role calls. Also drive one trial of
   maf_localvalid_sched the same way, confirming the EFSM selection_func
   picks only enabled-SEND roles with zero orchestrator LLM calls.
   Drive maf_localvalid_gate with a WrongLabel followed by Submit and assert
   WrongLabel is blocked before broadcast while Submit is delivered.
   (Structure main.py so the loop is importable/testable without
   ResponsesHostServer.)
3. `azd ai agent run` + `azd ai agent invoke --local` one skills trial on
   gpt-5-mini: valid trial-record JSON returned.
4. STOP for orchestrator review before `azd deploy`. Do NOT deploy.

Out of scope for the implementer: any change to arm meaning, grading,
prompt builders, or registry; any deploy; any n>1 runs.

## 7. Parallel-safety requirements (must-hold, or parallelism corrupts data)

1. **429s are noise, never data.** (A "429" is the standard error code a
   server sends back to mean "you're calling me too fast, slow down.")
   Rate-limit responses (429 / throttling errors) are retried with
   exponential backoff (waiting progressively longer between retries:
   base 2s, cap 60s, max 8 tries) INSIDE the call layer; a 429-retry
   never counts as an LLM call, an attempt, a WAIT, or a violation. This
   matters because MAF surfaces 429s as errors that look like
   no-progress → fake "deadlock" verdicts (known issue, see
   case_runner batch comments). Every retry is logged with a `throttled`
   marker so batches can be audited for contention.
2. **Within-batch concurrency is capped:** driver default = 1 trial in
   flight per group (4 total across the 4 groups). V4-Flash (cap 125)
   stays at 1; raising others to 2 requires observing zero 429-storms in
   the small check run. Arms run sequentially inside a batch.
3. **DeepSeek API-surface risk:** the role-agent client must be
   selectable via env `STJP_CHAT_API=chat|responses`. DeepSeek Foundry
   deployments are served via the chat-completions-compatible surface;
   the OpenAI *responses* API may not accept non-OpenAI models. Default:
   `chat` for the two DeepSeek groups, whatever the airline_seat pattern
   uses for GPT groups. The per-arm DeepSeek small check run is the
   checkpoint — a DeepSeek group that cannot complete one skills trial
   blocks that model's batch, not the whole campaign.
4. **Credentials are environment-aware:** `AzCliCredential` (an Azure
   authentication method that reuses your local `az login`) ONLY for
   local runs; inside the hosted container use the ambient managed
   identity (an automatic cloud identity with no stored secret — follow
   the airline_seat pattern exactly; do not import az_credential in
   container code paths).
5. **Gateway/long-trial timeouts:** a trial is one long request (up to
   max_steps × 7 roles calls). The deploy small check run MUST include
   the longest-running arm (skills) on the slowest model (V4-Flash) to
   measure end-to-end duration; driver client timeout ≥ 30 min. If the
   hosted responses endpoint enforces a shorter gateway limit, escalate
   to the orchestrator (fallback design: chunked trial requests) — do
   not silently shrink max_steps.
6. **Per-batch isolation of evidence:** each model batch writes its own
   run dir (`<ts>-hosted-<model>-n30`); no shared mutable files across
   batches except the append-only campaign log.

## 6. REAL-API rule (project owner mandate)

Every benchmark trial — the local small check run and all campaign
trials — uses REAL LLM calls to the Foundry deployments via
FoundryChatClient (AZURE_AI_MODEL_DEPLOYMENT_NAME, endpoints from
stjp_core/.env). Token numbers come only from real API usage objects;
recorded conversations land in the project's Application Insights
(Azure's monitoring and logging tool). The FakeChatClient of checkpoint 2
above is a unit test of the ENFORCEMENT CODE only (deterministic EFSM
walker behavior); its output must NEVER be written into any runs/
directory or counted in any table. A trial record without real usage
numbers and a real recorded conversation is not evidence.
