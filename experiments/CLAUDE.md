# experiments/ — project policy

How the STJP benchmark is wired together. Read this before answering questions
about the 8-arm matrix, the skills files, or where prompts come from.

## The 8 arms, mechanically

`baselines/registry.py:160-169` is the single source of truth. Each arm is
`(scenario_key, scenario_name, factory)`. The factory builds a `BaselineRunner`
that calls one of four instruction builders in `baselines/instructions.py`:

| arm key | builder | protocol given to agent | monitor projects |
|---|---|---|---|
| `bare` | `build_bare_instructions` | none | canonical `protocols/v1.scr` |
| `maf_native` | `build_bare_instructions` | none | canonical |
| `maf_foundry` | `build_bare_instructions` | none | canonical |
| `maf_groupchat` | `build_bare_instructions` | none | canonical |
| `maf_groupchat_unsafe` | `build_global_spec_instructions(override=unsafe)` | LLM-drafted unsafe global text | unprojectable → **no monitor** |
| `maf_groupchat_llmvalid` | `build_global_spec_instructions(override=valid)` | LLM-drafted valid global text | LLM-drafted valid |
| `spec_llmvalid` | `build_spec_instructions(override=valid)` | projected **local** type (verbose markdown) | LLM-drafted valid |
| `min_llmvalid` | `build_spec_minimal_instructions(override=valid)` | projected **local** type (SEND/RECV table) | LLM-drafted valid |
| `min_llmvalid_gate` | `build_spec_minimal_instructions(override=valid)` | lean projected local type + gate enforcement | LLM-drafted valid |
| `min_llmvalid_sched` | `build_spec_minimal_instructions(override=valid)` | lean projected local type + gate + **EFSM enabled-sender scheduler** | LLM-drafted valid |

Added 2026-07-02 (`docs/archive/EXPERIMENT_DESIGN_V3_EXECUTION.md`, pre-registered):
`min_llmvalid_gate` decomposes enforcement from contract verbosity (same prompt
as `min_llmvalid`, same gate as `spec_llmvalid_gate`). `min_llmvalid_sched` is
the full STJP execution plane — `FoundryRunner(schedule="efsm")` polls only
roles whose projected local state has an enabled SEND (delm_runner Plane B on
real agents; requires `gate=True` so the scheduler's monitor state tracks
committed reality). When adding arms remember all four registration points:
`registry.py` SCENARIOS, `case_runner.py` `_FOUNDRY_INSTALL_KEYS` **and**
`FOUNDRY_KEYS` (wave split), `evaluate_run.py` `VOCABULARY_ARMS`.

**spec vs min** are both WITH-arms — both hand the agent a projected per-role
local type plus refinement guards. They differ only in verbosity of the markdown.
`spec` = full Claude-subagent markdown via `generate_claude_subagent(...)`. `min`
= one line per EFSM transition like `state 26: SEND NotificationBranch(String)
to TaxSpecialist -> state 38`, plus a "Payload guards (HARD)" list. The minimal
form was introduced after a smoke run showed it recovers ~54% of the verbose
arm's token cost without losing protocol-correctness
(`instructions.py:284-289`).

## "Unsafe" means Scribble's deadlock-freedom check rejected it

`experiments/cases/finance/protocols/llm_drafts/unsafe/v1.scr` has a `choice at
RevenueAnalyst { high } or { standard }` followed by an `Approval` from
TaxVerifier that exists in both branches. On the high branch, TaxVerifier was
never notified (no `NotificationBranch` message), so it can't send `Approval`,
so RevenueAnalyst blocks waiting for it. Scribble surfaces this as wait-for
cycles `[Writer, RevenueAnalyst, TaxVerifier]` and
`[Fetcher, Writer, RevenueAnalyst, TaxVerifier]` — see the captured verdict at
`events_maf_groupchat_unsafe.jsonl:1` (marker `protocol_unprojectable`).

Because projection failed, the runtime monitor is **disabled** for that arm —
which is why its `viol_events=0` is not a success signal. Goal achievement is
still measured, and it drops to 20% strict (`summary_eval.json`).

The valid draft fixes this by adding `NotificationBranch` to both branches so
every role learns of the branch decision before anyone has to act on it.

## Skills files — gone from the live path (kept for authoring only)

The legacy `stjp_core/skills/` directory and the per-case
`experiments/cases/<case>/skills/` directories were retired on 2026-05-29.
Skills files were never projected from the protocol — they were LLM-authored
on top of it (see `stjp_core/generation/skills_generator.py`) and tended to
drift (the finance case's pre-deletion skills files had a stale `P1_v2.scr`
header and a `$10,000` threshold while `case.yaml:48-49` already said
`float(x) > 50000`).

**In the 8-arm matrix, skills are never loaded.** `instructions.py:240-244`
only reads `skills_dir/{role}_skills.md` when `protocol_path_override is None`;
every WITH-arm factory in `registry.py` passes `protocol_path_override=path`
(the llm-drafts/valid path). So even before deletion, `spec_llmvalid` and
`min_llmvalid` always skipped skills.

**If you need skills for a new authoring flow**, the `apps/orchestrator.py`
CLI accepts `--case <case_id>` and writes regenerated skills under
`experiments/cases/<case_id>/skills/` using the current
`protocols/v1.scr` + `case.yaml`. That directory does not need to exist on
disk to drive the 8-arm benchmark; create it only when authoring resumes.

## Payload values (the numbers) are pure LLM output

There is no data source. No tool calling. `case.intent` (prose) and the role
description (prose) are the **only** things the Fetcher ever sees about "the
data" — see `case.yaml:31` (`Fetcher: retrieves raw revenue data on request`).
When the trace shows `HighRevenue(75000)`, the `75000` was hallucinated by the
LLM in the same call that emitted the message. This is why the **refinement
guards** in `protocols/v1.refn` matter: without them compiled into the prompt
(bare arms), nothing prevents `HighRevenue(10)` on the high branch.

## Where prompts live — two layers

1. **Static system prompt per role** — built once at agent-creation time:
   - Intent: `case.intent` from `experiments/cases/<case>/case.yaml`
   - Wrapped by `experiments/baselines/instructions.py` (one of 4 builders)
   - Installed on the Foundry agent via
     `AgentsClient.create_agent(..., instructions=instr)` in
     `experiments/baselines/foundry_runner.py:setup()`
   - Truncated to 8000 chars at install. The full pre-truncation string is
     saved to `runs/<ts>/prompts/<arm>/<Role>.system.md` so reviewers can
     spot silent over-truncation (see "Persistence policy" below).

2. **Dynamic per-turn user prompt** — one per step:
   - Built by `stjp_core/foundry/session_helpers.py::build_view(role, history)`
     (the session log so far, from this role's POV). Imported by
     `foundry_runner.py:36` as `ex`.
   - Posted as a `user` message to that role's thread
   - Then `runs.create_and_process(thread, agent)` is invoked

**Goals** flow through two channels:
- As prose into the system prompt via `case.goals_text()`
  (`instructions.py:81-84, 184`)
- As executable predicates into the post-trace verifier
  (`summary_eval.json` lifecycle)

**Violation verdicts** (`off_protocol`, `unexpected_peer`) in
`events_<arm>.jsonl` are emitted by the runtime monitor in
`stjp_core/monitor/monitor.py`, not by the agents.

## What lives in `case.yaml` vs. here

`case.yaml` is the **case** spec: `intent`, `roles`, `goals`, `branch_hints`,
`role_descriptions`, `terminal_label`, `max_steps`. It says nothing about
the 8 arms, about min vs spec, or about why a particular LLM-drafted protocol
is "unsafe" — those are **matrix-level** concerns and belong here, in
`baselines/README.md`, and in `baselines/registry.py:150-159`. Do not bloat
`case.yaml` with arm-level prose; if you need to explain something about an
arm, write it here.

## Persistence policy — every prompt is checkable post-hoc (implemented)

Every WITH-arm, MAF arm and global-text arm now persists its full per-role
system prompt to disk immediately after `runner.setup()`. Implemented in
`scripts/case_runner.py::_persist_prompts` and called from `run_scenario`.

Layout:

```
runs/<ISO-timestamp>-n<N>-dual/
  prompts/
    <arm_key>/
      <Role>.system.md       <-- full pre-install string (what the builder produced)
      __orchestrator__.system.md  <-- only for maf_groupchat* arms
      index.json             <-- per-role SHA-256, char count,
                                 install_limit, truncated_on_install
```

Foundry-stack arms (`bare`, `spec_llmvalid`, `min_llmvalid`) truncate the
installed copy at 8000 chars on `client.create_agent(instructions=...)`. The
saved `.system.md` is the **pre-truncation** string; `index.json` records the
character count and a `truncated_on_install` flag so reviewers can spot
prompts that were silently clipped. MAF arms do not truncate; their flag is
always `false`.

How runners cooperate with the persister:
- `BaselineRunner.__init__` declares `self._role_prompts: dict[str, str]`.
- Each runner populates that dict during `setup()` with the same string it
  hands to the agent backend.
- `BaselineRunner.prompts()` returns a copy. `_persist_prompts` consumes it.

**If you add a new arm**, populate `self._role_prompts[role] = instr` before
calling the agent constructor — otherwise the run will print a warning and
emit an `index.json` with `"warning": "no prompts captured for this arm"`,
which means the artefact tree is no longer audit-complete.

**If you change an instruction builder**, the persisted SHA-256 in
`prompts/<arm>/index.json` will change. That's the intended signal — old
runs and new runs are no longer comparable on raw prompt content. Either
bump a logical schema version next to the change or keep the edit additive.

## Skills files — do not regenerate into the case dirs without rechecking

The finance case used to ship a `skills/v1/` directory carried over from the
earlier `stjp_core/apps/stjp_dual_demo.py` flow. It was stale on both the
protocol filename (`P1_v2.scr` vs current `v1.scr`) and on the high-revenue
threshold (`$10,000` vs `case.yaml`'s `> $50000`). It was also dead-coded in
the 8-arm matrix (`instructions.py:240-244`). It was deleted on 2026-05-29
and the `v1.refn` header line that incorrectly referenced `P1_v2.scr` was
corrected at the same time. Do not recreate the folder by accident.

If a future arm legitimately needs business-rule skills on top of the protocol,
regenerate via `stjp_core/generation/skills_generator.py` using the **current**
`protocols/v1.scr` + `case.yaml` and write to both
`stjp_core/skills/` and `experiments/cases/<case>/skills/<version>/`, then
update the matching `prompts_schema_version`.

## Reading a trial trace

```
{"step":3, "sender":"RevenueAnalyst", "receiver":"TaxSpecialist",
 "label":"HighRevenue", "payload":"60000", "goals_pass":1, "violation":null}
```

- `goals_pass` is the running count of goal predicates satisfied so far by
  events in this trial (max = `goals_total`).
- `violation:null` = monitor accepted this event. Otherwise expect
  `{"type":"off_protocol", "role":..., "state":..., "expected":[...]}`.
- `attempt_end` markers carry `all_goals_pass` (Set B success for that attempt).
- `trial_end` markers carry `succeeded` (the trial-level success boolean —
  becomes the numerator of `success_rate_pct` in `summary.json`).

## Reading a run summary

- `summary.json` — Set A (conformance + process cost). `violations`,
  `violation_types`, `success_rate_pct`, token/seconds totals.
  `success_rate_pct` = % of trials where every goal predicate passed, under
  the arm's own `success_rule` (also in the summary): `strict` (exact
  anchor sender/receiver/label match) for arms whose prompt contained the
  protocol vocabulary (`evaluate_run.VOCABULARY_ARMS`), `role_pair`
  (label-free — right sender, right receiver, predicate-satisfying payload,
  any label) for arms that never saw the protocol (bare, maf_*). Rationale
  + history: `docs/BENCHMARK_FAIRNESS_REVIEW.md` Problem 1. Each arm also
  carries `success_rate_ci95_pct` (95% Wilson interval — quote it, not just
  the point estimate) and `prompt_truncated_roles` (non-empty = that arm's
  installed prompt was clipped at Foundry's 8000-char limit; treat its
  numbers as invalid for comparison).
- `summary_eval.json` — Set B (goal achievement). `strict_pct` /
  `role_pair_pct` / per-goal breakdowns. Strict = exact-anchor match; role_pair
  relaxes the label requirement (any message between the expected sender/
  receiver counts). `strict_per_goal` and `role_pair_per_goal` show which goals
  drag the average down.

## Common pitfalls (don't repeat)

- **Don't assume skills files are authoritative.** They're stale on at least
  one finance case (protocol filename + threshold both wrong).
- **Don't read `viol_events=0` as success.** Check `succeeded` /
  `success_rate_pct` and look for a `protocol_unprojectable` marker at the top
  of the events file — that means the monitor was disabled.
- **Don't treat `bare` violations as the agents "doing something wrong."** The
  bare arms are monitored against the canonical `v1.scr` whose label vocabulary
  the agents have never seen. They cannot satisfy it. That's the experimental
  point — `off_protocol` on every event is the expected baseline.
- **Don't conflate `spec_llmvalid` with running against the canonical
  protocol.** It projects from `llm_drafts/valid/v1.scr` (the LLM-drafted
  protocol that Scribble accepted), not from `protocols/v1.scr`.

## File map you'll need

| what | where |
|---|---|
| 8-arm registry | `experiments/baselines/registry.py` |
| 4 instruction builders | `experiments/baselines/instructions.py` |
| Foundry-stack runner (bare/spec/min) | `experiments/baselines/foundry_runner.py` |
| MAF runners | `experiments/baselines/maf_*.py` |
| Case driver | `experiments/scripts/case_runner.py` |
| Case loader | `experiments/scripts/case_loader.py` |
| Per-case spec | `experiments/cases/<case>/case.yaml` |
| Canonical protocol | `experiments/cases/<case>/protocols/v1.scr` |
| Refinement sidecar | `experiments/cases/<case>/protocols/v1.refn` |
| LLM-drafted protocols | `experiments/cases/<case>/protocols/llm_drafts/{valid,unsafe}/v1.scr` |
| Re-anchored goals for LLM drafts | `experiments/cases/<case>/protocols/llm_drafts/{valid,unsafe}/goals.yaml` |
| (Stale) skills files | `experiments/cases/<case>/skills/v1/*_skills.md` — dead in 8-arm matrix |
| Runtime monitor | `stjp_core/monitor/monitor.py` |
| EFSM projection | `stjp_core/compiler/efsm_parser.py` (`get_all_efsms`) |
| Refinement loader | `stjp_core/compiler/refinement_checker.py` |
| Subagent markdown generator | `stjp_core/generation/agent_generator.py` |
