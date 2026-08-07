# MAF token accounting — investigation handoff

**Date: 2026-08-06.** Plain-English handoff for the next agent (or human)
picking up the `sdlc_release_gate` benchmark. It records what was found while
investigating "why is there a huge token gap between the MAF and non-MAF
arms?", why the pooled arm-average table was misleading, and what is still
broken before an `n=30` headline run can start. Every number below was
re-derived from files on disk; the exact paths and commits are given so you
can reproduce each one, not take it on trust.

Read alongside [`BENCHMARK_HANDOFF.md`](BENCHMARK_HANDOFF.md) (the campaign
entry point) and [`BENCHMARK_IMPLEMENTATION_STEPS.md`](BENCHMARK_IMPLEMENTATION_STEPS.md)
(§0a infrastructure traps).

## Menu
- [0. TL;DR](#0-tldr)
- [1. The run this is about](#1-the-run-this-is-about)
- [2. Two open MAF runtime bugs (the real blocker)](#2-two-open-maf-runtime-bugs-the-real-blocker)
- [3. The token-accounting finding](#3-the-token-accounting-finding)
- [4. The pooling trap — why maf_localvalid "looked cheaper"](#4-the-pooling-trap--why-maf_localvalid-looked-cheaper)
- [5. The verified matched-model comparison](#5-the-verified-matched-model-comparison)
- [6. Does Azure AI Foundry count tokens correctly?](#6-does-azure-ai-foundry-count-tokens-correctly)
- [7. Exact pointers to re-derive every number](#7-exact-pointers-to-re-derive-every-number)
- [8. What to do next](#8-what-to-do-next)

---

## 0. TL;DR

1. The huge MAF-vs-non-MAF token gap is **real and correctly measured**. It is
   the honest cost of MAF's LLM orchestrator (speaker selection every round,
   holding the full intent + protocol) plus its broadcast of the growing
   transcript to every participant. Non-MAF round-robin has **zero**
   orchestrator LLM calls and feeds each role only a projected, filtered view.
2. The old local usage counter **undercounted MAF by 2–9×** because it read
   MAF's `workflow.run()` outer stream, which does not surface orchestrator
   replies. Fixed for future runs at commit `b1252fd` (capture at the shared
   chat-client boundary). Historical cells were corrected from Foundry
   OpenTelemetry trace spans via `reconcile_maf_usage.py`.
3. The **pooled arm-average table is invalid** and must not be used: the MAF
   rows contain only DeepSeek successes while the non-MAF rows also include
   expensive GPT trials (one `mini/localvalid` cell alone = 1.16M tokens). The
   only valid view is **matched-model** (same model on both sides).
4. Matched-model, on the projected/STJP arms, **MAF costs 3.2–7.0× more tokens
   per model**. On the verbose baselines (`skills`, `globalvalid`) MAF is
   roughly neutral-to-cheaper — a real nuance, explained in §5.
5. The actual blocker before `n=30`: **two MAF runtime bugs** leave GPT (both
   models) and the MAF scheduler arm with no valid cells to compare (§2).

## 1. The run this is about

```
experiments/cases/skills_safety/sdlc_release_gate/runs/
  20260806T091831-hosted-hardened-localcheck-sol-mini-v4pro-v4flash-n1/
```

This is the **`n=1` "localcheck" pilot gate** — 10 arms × 4 models = 40 cells —
that must pass cleanly before the `n=30` headline campaign (per
`BENCHMARK_HANDOFF.md` §8). It ran **locally** (`endpoint_mode: local`), each
model on its own detached hosted server, real model calls, live telemetry to
Application Insights. Cell state at time of writing (from
`campaign_manifest.json`): **32 valid, 6 invalid, 1 running, 1 pending**.

- Models: `sol` = gpt-5.6-sol, `mini` = gpt-5-mini (the two GPT/closed models);
  `v4pro` = DeepSeek-V4-Pro, `v4flash` = DeepSeek-V4-Flash (the two open-weight
  models).
- The 10 arms and their meaning: `BENCHMARK_PLAN_V3.md` §10.8. Role prompts for
  matched arms are byte-identical (checksum-verified this session); the only
  prompt difference in a MAF arm is the added `__orchestrator__.system.md`.

## 2. Two open MAF runtime bugs (the real blocker)

Every invalid cell in the pilot is a **MAF** arm, failing for one of two
reasons (from each cell's `error` in `campaign_manifest.json`):

**Bug A — empty message list on GPT.**
`ChatClientInvalidRequestException: Messages are required for chat completions`.
Hits **all MAF arms on `sol` and `mini`** (`maf_skills`, `maf_globalvalid`,
`maf_localvalid`, `maf_localvalid_gate`). When MAF's orchestrator selects the
same speaker twice in a row, that participant's `AgentExecutor` cache can be
empty, so the request carries no user message. GPT rejects an empty message
list; DeepSeek tolerates it (which is why the same arms are **valid** on
`v4pro`/`v4flash`). Consequence: **there are currently zero valid GPT MAF
cells**, so no GPT MAF-vs-non-MAF comparison exists at all.
The intended guard is described in `BENCHMARK_IMPLEMENTATION_STEPS.md` §7
("participant requests must always contain a non-empty user message");
`main.py` supplies `_MAF_TURN_INSTRUCTION` as a fallback, but it is not
preventing the empty-list case on GPT in this run.

**Bug B — MAF scheduler never converges.**
`WorkflowConvergenceException: Runner did not converge after 100 iterations`.
Hits `maf_localvalid_sched` on **both `v4pro` and `v4flash`**. The EFSM
`selection_func` keeps selecting speakers but the terminal condition
(`_maf_terminal_condition`, label `Deployed`) never trips before MAF's
100-superstep limit. So `maf_localvalid_sched` has **0 valid cells across all
four models**.

**Net:** the campaign's own rule — "MAF must pass on all four models before
`n=30`" (`BENCHMARK_HANDOFF.md` §8) — is **not met**. These two bugs, not the
token accounting, are what block the headline run.

## 3. The token-accounting finding

### What was wrong
The old local usage counter summed usage from MAF's `workflow.run()` **outer
result stream**. Per MAF's own design (and stated in
`BENCHMARK_IMPLEMENTATION_STEPS.md` §7), `GroupChatBuilder` **does not expose
the orchestrator's internal speaker-selection replies in that outer stream**.
So the orchestrator's per-round LLM calls — which are roughly *half* of all
calls and each carry a large system prompt — were **invisible** to the counter.

### The proof (from the reconciled cell `v4pro/maf_localvalid/0000`)

| source | calls counted | total tokens |
|---|---|---|
| old local method (participant stream) | **8** | 5,022 |
| Foundry OTel `chat` spans, summed | **17** | 45,794 |

The old method saw 8 calls; the trace saw 17. **The 9 missing calls are the
orchestrator's speaker-selection calls.** Same pattern on
`v4flash/maf_skills/0000`: 66 local calls → 129 trace calls. Across all 9 valid
MAF cells the old totals were **2.3×–9.1× too low** (`previous_usage` vs
reconciled, stored in each `result.json`).

### Why the gap is large *and honest*
Two structural causes, both verified in the installed MAF source under
`foundry_hosted_agents/.../sdlc_release_gate/.venv/Lib/site-packages/`:
- **The orchestrator is a real extra LLM, called ~once per round.** For
  `maf_localvalid` its system prompt is ~2,827 tokens (it embeds the full
  9,487-char intent document **and** the whole protocol; for `maf_globalvalid`
  / `maf_skills` it is ~1,791 tokens). That entire system prompt is re-sent on
  every orchestrator call, and the model processes the whole accumulated
  transcript each round. Non-MAF round-robin selects the next speaker with a
  free Python `pop(0)` — no LLM call.

  **Correction (2026-08-07):** an earlier version of this section said the
  orchestrator re-sends the full transcript via `_get_conversation()`. That is
  not what the code does. `AgentBasedGroupChatOrchestrator._invoke_agent`
  (installed `agent_framework_orchestrations/_group_chat.py`) copies only
  `self._cache` — the messages new since last round — clears it, appends its
  instruction block, and passes `session=self._session`; the comment there reads
  *"We only need the last message for context since history is maintained in the
  thread."* History lives server-side in the session thread, so the client sends
  a delta, not the transcript. `_get_conversation()` feeds the `selection_func`
  path (`GroupChatState`) and the termination check, not the LLM orchestrator's
  call. The **billing** conclusion is unchanged — each call still processes the
  accumulated thread, so input grows per round — but the request is append-only,
  which is the shape automatic prompt caching serves best. Caching discounts
  dollars, not tokens; token counts, the benchmark's primary metric, are
  unaffected either way.
- **Participants get broadcast context, not a projected view.** MAF broadcasts
  each reply to all participants and each `AgentExecutor` defaults to
  `context_mode="full"`. Note that `context_mode` is **not** a usable lever here:
  it is consulted only in the `from_response` chaining handler, while group-chat
  broadcasts arrive as an `AgentExecutorRequest` and hit `run()`, which does an
  unfiltered `self._cache.extend(request.messages)`. Projecting MAF's broadcast
  would require a custom orchestrator passing a receiver subset to
  `_broadcast_messages_to_participants`, not a `context_filter`.
  Non-MAF calls `session_view.build_view`, which filters
  history to **only messages where this role is sender or receiver** — the STJP
  projection. (Broadcast growth is linear, not quadratic: `AgentExecutor._cache`
  is cleared after each run and only the newest message is rebroadcast — so
  there is no hidden duplication bug.)

### The fixes (already committed)
- `b1252fd` "Count complete MAF orchestration usage" — **future runs**: usage
  is captured at the shared `RetryingChatClient` boundary in `main.py`
  (`client.captured_usage()`), which sees **every** model call (orchestrator +
  participants). Stamped `capture_scope=all_chat_client_calls`. Applied to all
  arms symmetrically, so it is not a MAF-only inflation.
- `516ffc5` "Add exact MAF usage reconciliation" — **historical cells**:
  `experiments/scripts/reconcile_maf_usage.py` re-derives usage from run-owned
  OTel `chat <model>` spans (sum of per-call spans; rejects missing traces,
  wrong-model spans, duplicate span IDs; fails closed). It overwrites the stale
  local totals and records `usage_source: foundry_trace` +
  `usage_reconciliation.previous_usage` provenance in each `result.json`.
- `beffd45` "Require paired MAF cost comparisons" — the matched-model reporting
  rule (§4–§5).
- `fef7f0e` documents the trace safeguards in the two benchmark docs.

**Reconciliation status in this run:** all **9 valid** MAF cells now carry
`usage_source=foundry_trace` (verified: per-trace sums equal the aggregate; no
duplicate span IDs; model matches). The MAF cells that were **not**
recalculated have **no valid trial** to recalculate — they are the Bug-A /
Bug-B cells and must be **rerun**, not reconciled.

## 4. The pooling trap — why `maf_localvalid` "looked cheaper"

A pooled arm-average table showed `maf_localvalid` at ~61k tokens vs
`localvalid` at ~302k — i.e. MAF looking **cheaper**, which is backwards. That
is a **model-mix artifact**, not reality:

```
localvalid pool     = {sol, mini = 1,159,117 (!), v4pro, v4flash}  ← includes GPT
maf_localvalid pool = {v4pro, v4flash} only                        ← DeepSeek only
```

The GPT MAF cells are all invalid (Bug A), so the MAF pool is DeepSeek-only,
while the non-MAF pool also carries the expensive GPT trials (the single
`mini/localvalid` cell is 1.16M tokens). Comparing them is "GPT+DeepSeek
non-MAF" vs "DeepSeek-only MAF". **Never pool across arms when the valid
model composition differs** (this is the standing rule in
`BENCHMARK_HANDOFF.md` §8 and `BENCHMARK_IMPLEMENTATION_STEPS.md` §7). Report
matched-model ratios first; pooled averages only once every arm has the same
valid model/trial denominator.

## 5. The verified matched-model comparison

Same model on both sides, from the reconciled cells in this run:

| model | pair | non-MAF calls/tok | MAF calls/tok | MAF token ratio |
|---|---|---|---|---|
| v4pro | **localvalid** | 14 / 6,559 | 17 / 45,794 | **6.98×** |
| v4flash | **localvalid** | 42 / 21,699 | 25 / 76,600 | **3.53×** |
| v4pro | **localvalid_gate** | 42 / 20,570 | 27 / 85,728 | **4.17×** |
| v4flash | **localvalid_gate** | 42 / 24,362 | 25 / 77,001 | **3.16×** |
| v4pro | globalvalid | 42 / 128,368 | 27 / 89,455 | 0.70× |
| v4flash | globalvalid | 56 / 97,280 | 48 / 158,797 | 1.63× |
| v4pro | skills | 244 / 978,738 | 113 / 614,016 | 0.63× |
| v4flash | skills | 199 / 772,643 | 129 / 761,662 | 0.99× |

**On the projected/STJP arms (`localvalid`, `localvalid_gate`), MAF costs
3.2–7.0× more tokens per model** — the orchestrator + broadcast overhead.

**Honest nuance to carry into the report:** on the *verbose* baselines
(`skills`, `globalvalid`) MAF is neutral-to-cheaper (0.6–1.6×). Reason: the
non-MAF round-robin blindly polls all 7 roles in a fixed circle, making far
more calls (244 vs MAF's 113 on v4pro `skills`), each re-reading a large
2.3–5k-token role prompt; that call churn outweighs MAF's orchestrator
overhead when role prompts are already big. So "MAF always costs more" is only
true where role prompts are small (the projected arms). Also: `skills` /
`maf_skills` are **0% GCR** here, so their token totals are cost-per-nothing
and must not anchor any claim.

## 6. Does Azure AI Foundry count tokens correctly?

**Yes — Foundry telemetry is the complete/correct source; it does not have the
undercount problem. It is the source used to *fix* it.**

- The undercount was specific to reading MAF's `workflow.run()` **outer
  stream**. Foundry's OpenTelemetry GenAI layer instruments at the **model-SDK
  call boundary**, one level below that stream, and emits **one `chat <model>`
  span per actual model call** with `gen_ai.usage.input_tokens` /
  `output_tokens`. Every orchestrator call and every participant call gets its
  own span. `reconcile_maf_usage.py` sums those spans and that is exactly how
  the 8→17-call, 5,022→45,794-token correction was obtained.
- **The one condition:** the correct Foundry number is the **sum of all
  `chat <model>` child spans under the trial's exact trace IDs** — not a single
  top-level workflow-span figure. If someone reads a top-level rollup off the
  portal that does not sum children, they can undercount again — the same
  "read the wrong level" trap, one layer up. The reconcile tool and the
  `b1252fd` client-boundary capture both do the summation correctly.
- **Future `n=30` runs:** because `b1252fd` captures at the shared chat-client
  boundary (which also sees all calls), the **local** number will match the
  Foundry trace sum — no reconciliation needed. Note: every valid MAF cell in
  *this* pilot ran **before** the `b1252fd` fix landed (all before 12:00 on
  2026-08-06), which is why they all needed trace reconciliation. The n=30
  preflight should cross-check that local `captured_usage` equals the trace-sum
  on at least one MAF cell to confirm the fix end-to-end.
- **Retries/throttles do not inflate tokens:** a throttled (429) attempt fails
  before returning usage, so it carries no token attributes and is skipped by
  the span sum; multiple trace IDs on one cell are separate *attempts* and are
  summed on purpose (honest bookkeeping — every attempt counts).

## 7. Exact pointers to re-derive every number

- **Run dir / manifest:**
  `experiments/cases/skills_safety/sdlc_release_gate/runs/20260806T091831-hosted-hardened-localcheck-sol-mini-v4pro-v4flash-n1/campaign_manifest.json`
  (cell status, usage, `usage_source`, `trace_ids`, and each invalid cell's
  `error`).
- **Per-cell reconciliation provenance:** each valid MAF cell's
  `cells/<model>/<arm>/0000/result.json` → `usage`,
  `usage_reconciliation.previous_usage`, `.per_trace`,
  `.usage_evidence = server_otel_console_export`.
- **Prompts (checksum matched arms):** the run's `prompts/<arm>/*.system.md`.
  Role prompts are byte-identical across matched pairs; MAF arms add
  `__orchestrator__.system.md` (~2,827 tok for `maf_localvalid`, ~1,791 for
  `maf_globalvalid`/`maf_skills`).
- **Hosted workflow code:**
  `foundry_hosted_agents/agent-framework-agent-with-remote-mcp-tools-responses/agents/sdlc_release_gate/main.py`
  — `RetryingChatClient` / `captured_usage()` (~line 156–202, 1003–1006);
  `MafGroupChatLoop` and the three MAF orchestrators (~line 405–784);
  `RoundRobinGateLoop` + `session_view.build_view` (the projected view).
- **Reconcile tool:** `experiments/scripts/reconcile_maf_usage.py`
  (`python experiments/scripts/reconcile_maf_usage.py <run-dir> <server.log>... --write`;
  fails closed on missing/wrong-model/duplicate spans).
- **Commits:** `b1252fd` (client-boundary usage capture), `516ffc5` (reconcile
  tool), `beffd45` (paired-comparison rule), `fef7f0e` (doc safeguards),
  `5150995` (trace export with agent identity).
- **Installed MAF source (mechanism):** under the case's `.venv/Lib/site-packages/`:
  `agent_framework_orchestrations/_group_chat.py` (broadcast + `_get_conversation`),
  `agent_framework_orchestrations/_base_group_chat_orchestrator.py`
  (`_send_request_to_participant`, `_broadcast_messages_to_participants`),
  `agent_framework/_workflows/_agent_executor.py` (`context_mode="full"`,
  cache cleared after each run).

## 8. What to do next

**Status update 2026-08-07: items 1–3 are done; the campaign is running.**

1. ~~**Fix Bug A (empty message list on GPT).**~~ **RESOLVED — no new fix was
   needed.** The guard (`_MAF_TURN_INSTRUCTION`, forced on every
   `_send_request_to_participant` path) landed in commit `5150995` at 16:58 on
   2026-08-06 — *after* the pilot started at 09:18, so every Bug-A failure
   recorded in that run was produced by code that no longer exists. Verified by
   re-running the exact failing combination (`mini` / `maf_localvalid`, the
   Responses API path GPT uses): **valid**, goal achieved, 36 calls, 228,360
   tokens, zero empty-message errors. Lesson for the next reader: the manifest
   stores only an error *string*, never a stack trace, and the run-owned server
   logs are not kept — so a stored failure cannot be re-diagnosed by reading,
   only by re-running.
2. ~~**Fix Bug B (`maf_localvalid_sched` non-convergence).**~~ **FIXED** in
   `main.py`. The cause was not the terminal condition: MAF's workflow runner
   raises `WorkflowConvergenceException` after `DEFAULT_MAX_ITERATIONS` (100)
   **supersteps**, and `GroupChatBuilder.build()` does not expose that knob. One
   group-chat round costs several supersteps, so this case's 52-round budget
   (`max_steps` 48 + 4) exhausted a MAF-internal counter long before the
   benchmark's own turn budget. Two changes, both applied to **all three MAF
   arms identically** so no arm's stopping rule differs:
   - `_lift_maf_superstep_ceiling()` raises the runner ceiling to
     `6 * max_rounds + 20`, making `max_rounds` the only turn budget any arm can
     hit. Supersteps are a MAF implementation detail, not a benchmark quantity,
     so this does not change what is being compared. It must set
     `workflow._runner._max_iterations` as well as the public attribute — the
     runner captures the value in `Workflow.__init__`.
   - the EFSM `selection_func` now records `efsm_end` when no role has an
     enabled SEND, and the termination condition stops on it. This is the MAF
     twin of `RoundRobinGateLoop`'s `terminated_by="efsm_end"`; without it the
     scheduler polled an arbitrary role until the budget drained.

   Verified on the exact failing cell (`v4flash` / `maf_localvalid_sched`):
   **valid**, goal achieved, 12 calls, 9,591 tokens, $0.002, finished in about a
   minute instead of hitting the wall.
3. **Re-run the pilot gate cleanly** so MAF passes on all four models (the
   handoff rule), then confirm the local-vs-trace usage cross-check on a MAF
   cell (proves the `b1252fd` fix end-to-end). **Superseded in practice:** the
   n=10 campaign started 2026-08-07 08:00 local
   (`runs/20260807T080010-hosted-n10-4model-10arm-...-n10`, 10 arms × 4 models ×
   10 trials = 400 cells) is itself the gate — every MAF arm now produces valid
   cells on every model. The usage cross-check still wants doing on one MAF cell.

   Two early observations from that run worth carrying forward: the `skills`
   baseline is **not** the 0%-goal floor the n=1 pilot implied (5 of the first 11
   trials met their goals, 4 of 6 on `v4pro`) — a single trial per cell simply
   could not show that; and per-cell cost of `skills` (136–360 calls, 0.5–2.4M
   tokens) against `localvalid` (14 calls, 6,559 tokens on `v4pro`) is the
   clearest contrast in the data so far.
3b. **Dollar cost is now reported alongside tokens.**
   `experiments/scripts/cost_summary.py` runs automatically at the end of every
   campaign and writes `cost_summary.json` (per model, per arm, grand total,
   with the same `comparable` flag as the token tables and an explicit list of
   unpriced cells). `experiments/config/model_prices.json` now holds **verified
   Azure meter rates**, not analogs — it previously carried placeholders that
   were badly off (DeepSeek-V4-Pro listed at $0.25/1M input against a real
   $1.74), so any dollar figure produced before 2026-08-07 understates spend.
   Rates are UNCACHED input, making every total an upper bound; the runtime does
   not yet record how many prompt tokens were served from cache.
4. **Only report matched-model ratios** (§5) until every arm has the same valid
   model/trial denominator; never show the pooled arm-average table.
5. Then proceed to `n=30` per `BENCHMARK_HANDOFF.md` §8, owner's go required
   (real-money run).
