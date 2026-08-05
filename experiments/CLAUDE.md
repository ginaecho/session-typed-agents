# experiments/ — project policy

How the STJP benchmark fits together. Read this before answering questions
about the arm matrix (9-arm core + 3 ablation + 17 legacy), the skills files, or where prompts come from.

## Menu

- [The arm matrix: 9 core + 3 ablation + 17 legacy](#the-arm-matrix-9-core--3-ablation--17-legacy)
- ["Unsafe" means Scribble's deadlock-freedom check rejected it](#unsafe-means-scribbles-deadlock-freedom-check-rejected-it)
- [Skills files — gone from the live path](#skills-files--gone-from-the-live-path-kept-for-authoring-only)
- [Payload values are pure LLM output](#payload-values-the-numbers-are-pure-llm-output)
- [Where prompts live — two layers](#where-prompts-live--two-layers)
- [What lives in case.yaml vs. here](#what-lives-in-caseyaml-vs-here)
- [Persistence policy](#persistence-policy--every-prompt-is-checkable-post-hoc-implemented)
- [Skills files — do not regenerate without rechecking](#skills-files--do-not-regenerate-into-the-case-dirs-without-rechecking)
- [Reading a trial trace](#reading-a-trial-trace)
- [Reading a run summary](#reading-a-run-summary)
- [Common pitfalls](#common-pitfalls-dont-repeat)
- [File map you'll need](#file-map-youll-need)

## The arm matrix: 9 core + 3 ablation + 17 legacy

`baselines/registry.py` is the single source of truth and holds THREE
lists (line numbers drift; search for `SCENARIOS`):

- **`SCENARIOS` — the 9-arm CORE matrix** (what `case_runner.py <case>`
  runs). RENAMED 2026-08-05 (project-owner directive, BENCHMARK_PLAN_V3
  §10.8 "Final arm naming") to a uniform `(maf_)?(global|local)valid(_gate|_sched)?`
  vocabulary, plus the two real-skill-file baselines. Full rename table:

  | new name | old name (legacy alias) | meaning |
  |---|---|---|
  | `skills` | (replaces `bare` as baseline; = `unchecked_skills` promoted) | real published skill files (`skills_original`/`unchecked_skills`) + user intent; round-robin; no protocol |
  | `maf_skills` | (new) | same skill files + intent, MAF GroupChat runtime |
  | `globalvalid` | `global_decentralized` | whole validated plan as text, round-robin, observe-only |
  | `maf_globalvalid` | `maf_groupchat_llmvalid` | whole validated plan as text, MAF runtime |
  | `localvalid` | `min_llmvalid` | validated projected per-role local contract, round-robin, observe-only |
  | `maf_localvalid` | `maf_groupchat_llmvalid_orch` | same local contracts, MAF runtime (orchestrator holds intent+plan) |
  | `localvalid_gate` | `min_llmvalid_gate` | local contract + gate blocks rule-breaking messages |
  | `localvalid_sched` | `min_llmvalid_sched` | + EFSM-driven turn selection (full STJP) |
  | `maf_localvalid_sched` | (new — feasibility confirmed same day) | MAF GroupChat + local contracts + EFSM-driven speaker selection (no gate — MAF's sealed GroupChat has no message-interception point) |

  Every OLD key above is still resolvable (`make_runner`, `--arms`,
  `ALL_SCENARIOS`) via an identical-factory alias in `LEGACY_SCENARIOS` — old
  run dirs stay summarizable. `bare` and `maf_groupchat` are NOT renamed;
  they are REPLACED as the no-protocol baseline by `skills`/`maf_skills` and
  demoted to legacy aliases. Selection rationale for the underlying 7
  mechanisms: BENCHMARK_PLAN_V3 §10.6; rename rationale: §10.8.
- **`ABLATION_SCENARIOS` — 3 opt-in mechanism isolations**, run via
  `--arms` only where their question is live: `min_llmvalid_gate_lastrecv`
  (REQUIRED on >=1 branching case per campaign — the scheduling claim must
  beat the cheap heuristic), `min_llmvalid_gate_nohint` (blocking vs
  hinting), `spec_llmvalid_gate` (contract verbosity). NOT covered by the
  2026-08-05 rename (they sit outside the 9-arm canonical table); keys
  unchanged. (`unchecked_skills` and `global_decentralized` used to live
  here too — both were PROMOTED into the core matrix as `skills` and
  `globalvalid` respectively; their old keys survive as legacy aliases,
  not as ablation entries, so they are no longer double-listed.)
- **`LEGACY_SCENARIOS` — 17 archived/aliased arms**, runnable ONLY via
  `--arms`: the 9 pre-2026-08-05-RENAME aliases (`bare`, `maf_groupchat`,
  `global_decentralized`, `maf_groupchat_llmvalid`, `min_llmvalid`,
  `maf_groupchat_llmvalid_orch`, `min_llmvalid_gate`, `min_llmvalid_sched`,
  `unchecked_skills` — identical factories to their new-named core-matrix
  counterparts, just resolvable under the old key), the pre-2026-08-05-REPAIR
  broadcast-intent prompts under `_legacy` keys (`bare_legacy`,
  `global_decentralized_legacy`, `maf_groupchat_legacy`,
  `maf_groupchat_llmvalid_legacy`), the appendix runtime baselines
  (`maf_native`, `maf_foundry`), the deadlock negative control
  (`maf_groupchat_unsafe`), and the superseded verbose observe-only arm
  (`spec_llmvalid`). `ALL_SCENARIOS` = all three tiers; make_runner, --arms
  validation, and every summarize/eval path resolve against it, so
  pre-consolidation run dirs stay fully summarizable.

REPAIR NOTE (2026-08-05): `bare`, `global_decentralized`, `maf_groupchat`,
and `maf_groupchat_llmvalid` (all now legacy-alias keys; see rename table
above) KEPT THEIR KEYS but their prompt policy was repaired (workers carry a
distilled role brief; the intent lives with the architecture's planner).
Runs record the era in `prompts/<arm>/index.json:prompts_schema_version`
(missing = v1 broadcast, 2 = repaired) — NEVER compare v1 and v2 rows of
those four arms (or their new-named twins `globalvalid`/`maf_globalvalid`)
in one column. Pre-repair run dirs recorded the broadcast prompts under the
unsuffixed keys; to rerun the broadcast prompts today use the `_legacy`
arms.

Each arm is `(scenario_key, scenario_name, factory)`. The factory builds a
`BaselineRunner` that calls one of seven instruction builders in
`baselines/instructions.py` (legacy/alias arms marked):

| arm key | builder | protocol given to agent | monitor projects |
|---|---|---|---|
| `skills` (ex `bare`/`unchecked_skills`) | `build_unchecked_skills_instructions` | none; real hand-authored per-role skill file (never Scribble-checked) + user intent | canonical `protocols/v1.scr` |
| `maf_skills` (new) | `build_unchecked_skills_instructions` | none; same skill files, MAF orchestrator holds the intent | canonical |
| `bare` (LEGACY alias, repaired) | `build_bare_fairintent_instructions` | none; worker carries a distilled role brief instead of the full intent (fair intent-carrying policy) | canonical |
| `bare_legacy` (LEGACY) | `build_bare_instructions` | none; full intent broadcast to every worker (pre-repair `bare`) | canonical |
| `maf_native` (LEGACY) | `build_bare_instructions` | none | canonical |
| `maf_foundry` (LEGACY) | `build_bare_instructions` | none | canonical |
| `maf_groupchat` (LEGACY alias, repaired) | `build_bare_fairintent_instructions` | none; orchestrator holds the intent, participants hold briefs (MAF used as designed) | canonical |
| `maf_groupchat_legacy` (LEGACY) | `build_bare_instructions` | none; full intent broadcast to participants AND orchestrator (pre-repair `maf_groupchat`) | canonical |
| `maf_groupchat_unsafe` (LEGACY) | `build_global_spec_instructions(override=unsafe)` | LLM-drafted unsafe global text | unprojectable → **no monitor** |
| `maf_globalvalid` (ex `maf_groupchat_llmvalid`, repaired) | `build_global_spec_fairintent_instructions(override=valid)` | LLM-drafted valid global text + role brief (no full intent in workers; orchestrator holds the intent) | LLM-drafted valid |
| `maf_groupchat_llmvalid_legacy` (LEGACY) | `build_global_spec_instructions(override=valid)` | LLM-drafted valid global text + full intent in every worker (pre-repair `maf_globalvalid`) | LLM-drafted valid |
| `maf_localvalid` (ex `maf_groupchat_llmvalid_orch`) | `build_spec_minimal_instructions(override=valid)` for participants; orchestrator prompt carries intent + the valid global text | projected **local** types for participants; global type with the ORCHESTRATOR (BENCHMARK_PLAN_V3 §5.2 / §10) | LLM-drafted valid |
| `maf_localvalid_sched` (NEW, feasibility confirmed 2026-08-05) | `build_spec_minimal_instructions(override=valid)` for participants; NO orchestrator prompt (`GroupChatBuilder(selection_func=...)`, no LLM speaker-selection call) | projected **local** types for participants; speaker choice is a programmatic EFSM enabled-sender function, not a protocol-text prompt | LLM-drafted valid |
| `unchecked_skills` (LEGACY alias) | `build_unchecked_skills_instructions` | human-written per-role skills, never formally checked (the deadlock demo's no-checker arm) | canonical |
| `globalvalid` (ex `global_decentralized`, repaired) | `build_global_spec_fairintent_instructions(override=valid)` | LLM-drafted valid global text + role brief, on the decentralized round-robin `FoundryRunner` (no LLM orchestrator) — isolates "global text vs local contract" from "orchestrated vs decentralized" | LLM-drafted valid |
| `global_decentralized_legacy` (LEGACY) | `build_global_spec_instructions(override=valid)` | same but with the full intent in every worker (pre-repair `globalvalid`) | LLM-drafted valid |
| `spec_llmvalid` (LEGACY) | `build_spec_instructions(override=valid)` | projected **local** type (verbose markdown) | LLM-drafted valid |
| `localvalid` (ex `min_llmvalid`) | `build_spec_minimal_instructions(override=valid)` | projected **local** type (SEND/RECV table) | LLM-drafted valid |
| `spec_llmvalid_gate` | `build_spec_instructions(override=valid)` | verbose projected local type + gate enforcement (off-contract sends are REJECTED before delivery and the role re-prompted) | LLM-drafted valid |
| `localvalid_gate` (ex `min_llmvalid_gate`) | `build_spec_minimal_instructions(override=valid)` | lean projected local type + gate enforcement | LLM-drafted valid |
| `min_llmvalid_gate_nohint` | `build_spec_minimal_instructions(override=valid)` | same as `localvalid_gate` but WITHOUT the per-turn liveness nudge (hints=False) — isolates pure enforcement from per-turn guidance | LLM-drafted valid |
| `min_llmvalid_gate_lastrecv` | `build_spec_minimal_instructions(override=valid)` | same prompt + gate, scheduled by the protocol-free "ask whoever just received a message" heuristic (round-robin fallback) — the cheap-heuristic control for the EFSM scheduler | LLM-drafted valid |
| `localvalid_sched` (ex `min_llmvalid_sched`) | `build_spec_minimal_instructions(override=valid)` | lean projected local type + gate + **EFSM enabled-sender scheduler** | LLM-drafted valid |

Added 2026-07-02 (`docs/archive/EXPERIMENT_DESIGN_V3_EXECUTION.md`, pre-registered):
`localvalid_gate` decomposes enforcement from contract verbosity (same prompt
as `localvalid`, same gate as `spec_llmvalid_gate`). `localvalid_sched` is
the full STJP execution plane — `FoundryRunner(schedule="efsm")` polls only
roles whose projected local state has an enabled SEND (delm_runner Plane B on
real agents; requires `gate=True` so the scheduler's monitor state tracks
committed reality). `maf_localvalid_sched` is the MAF-runtime twin (no gate;
see `baselines/maf_groupchat.py`'s `MAFGroupChatRunner` docstring for why MAF
cannot gate). When adding arms remember all four registration points:
`registry.py` SCENARIOS, `case_runner.py` `_FOUNDRY_INSTALL_KEYS` **and**
`FOUNDRY_KEYS` (wave split), `evaluate_run.py` `VOCABULARY_ARMS`.

Added 2026-08-05 (BENCHMARK_PLAN_V3 §10, fair intent-carrying): the
repaired arms replace "every worker carries the full user intent" with
"the intent goes to that architecture's planner; workers carry a distilled
role brief." Intent artifacts live under
`experiments/cases/<case>/intent/` (`intent.md` doc-scale intent with git or
llm_authored provenance, `intent_distilled.md`, `role_briefs.yaml`,
`provenance.json` with setup-cost metering) and are produced by
`scripts/intent_pipeline.py` (mechanical label-leak guard so no protocol
vocabulary reaches non-vocabulary arms). The pipeline is a SEPARATE
preprocessing stage: run `intent_pipeline.py synth --all` (unattended:
author → distill → auto LLM coverage check → auto-approve, recorded as
`approved_by: "auto-llm"` = SYNTHESIZED, disclosed in reports) once
BEFORE a campaign; the per-step commands (author / distill / check /
approve) exist for human-gated use, and a human approval supersedes auto.
Repaired brief-carrying arms FAIL-FAST if `role_briefs.yaml` is missing.
Runs execute at `--intent-scale short` (default) or `doc`
(`intent.md` is the intent). Every run persists the exact intent it used to
`runs/<dir>/intent.md` with a provenance header (`_persist_intent` in
`case_runner.py`).

**spec vs min** are both WITH-arms — both hand the agent a projected per-role
local type plus refinement guards. They differ only in verbosity of the markdown.
`spec` = full Claude-subagent markdown via `generate_claude_subagent(...)`. `min`
= one line per EFSM transition like `state 26: SEND NotificationBranch(String)
to TaxSpecialist -> state 38`, plus a "Payload guards (HARD)" list. The minimal
form was introduced after a smoke run showed it reaches the same
protocol-correctness at roughly 46% of the verbose arm's token cost — a ~54%
saving (see the docstring of `build_spec_minimal_instructions` in
`instructions.py`).

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
header and a `$10,000` threshold while the G1 goal predicate in `case.yaml`
already said `float(x) > 50000`).

**In the arm matrix, the legacy `skills/v1` files are never loaded.** (The
`unchecked_skills` arm reads hand-authored files, but from a different
directory — `cases/<case>/unchecked_skills/<role>.md` — on purpose.) The
skills-loading branch inside `build_spec_instructions` in `instructions.py`
only reads `skills_dir/{role}_skills.md` when `protocol_path_override is None`;
every WITH-arm factory in `registry.py` passes `protocol_path_override=path`
(the llm-drafts/valid path). So even before deletion, `spec_llmvalid` and
`min_llmvalid` always skipped skills.

**If you need skills for a new authoring flow**, the `apps/orchestrator.py`
CLI accepts `--case <case_id>` and writes regenerated skills under
`experiments/cases/<case_id>/skills/` using the current
`protocols/v1.scr` + `case.yaml`. That directory does not need to exist on
disk to drive the arm-matrix benchmark; create it only when authoring resumes.

## Payload values (the numbers) are pure LLM output

There is no data source. No tool calling. `case.intent` (prose) and the role
description (prose) are the **only** things the Fetcher ever sees about "the
data" — see the `Fetcher` line in the finance case's `role_descriptions`
(`Fetcher: retrieves raw revenue data on request`).
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
     (the session log so far, from this role's point of view). The module is
     imported near the top of `foundry_runner.py` as `ex`.
   - Posted as a `user` message to that role's thread
   - Then `runs.create_and_process(thread, agent)` is invoked

**Goals** flow through two channels:
- As prose into the system prompt — every builder in `instructions.py`
  interpolates `case.goals_text()` into its template
- As executable predicates into the post-trace verifier
  (`summary_eval.json` lifecycle)

**Violation verdicts** (`off_protocol`, `unexpected_peer`) in
`events_<arm>.jsonl` are emitted by the runtime monitor in
`stjp_core/monitor/monitor.py`, not by the agents.

## What lives in `case.yaml` vs. here

`case.yaml` is the **case** spec: `intent`, `roles`, `goals`, `branch_hints`,
`role_descriptions`, `terminal_label`, `max_steps`. It says nothing about
the arms, about min vs spec, or about why a particular LLM-drafted protocol
is "unsafe" — those are **matrix-level** concerns and belong here, in
`baselines/README.md`, and in the comment block above `SCENARIOS` in
`baselines/registry.py`. Do not bloat
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

Foundry-stack arms (every `FoundryRunner` arm — `skills`, `globalvalid`,
and the `spec`/`local(valid)` family, plus their pre-rename aliases `bare`/
`unchecked_skills`/`global_decentralized`) truncate the
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
the arm matrix (the skills-loading branch in `build_spec_instructions` only
fires without a protocol override). It was deleted on 2026-05-29
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
  `success_rate_pct` is **GOAL-based, not "zero monitor violations"**: it is
  the % of trials where every goal predicate passed, under the per-arm success
  rule recorded in `success_rule`. That rule is `strict` (exact anchor
  sender/receiver/label match) for arms whose prompt contained the protocol
  vocabulary (`evaluate_run.VOCABULARY_ARMS` — `globalvalid`, `maf_globalvalid`,
  `localvalid`, `localvalid_gate`, `localvalid_sched`, `maf_localvalid`,
  `maf_localvalid_sched`, plus their pre-rename aliases), and `role_pair`
  (label-free — right sender, right receiver, predicate-satisfying payload,
  any label) for arms that never saw the protocol (`skills`, `maf_skills`,
  and their pre-rename aliases `bare`/`maf_groupchat`) and so cannot be
  expected to use its labels. Example: a `skills`-arm trial that sends the
  right amount from Fetcher to TaxSpecialist under a made-up label counts as
  a success; a `localvalid`-arm trial doing the same thing fails, because its
  prompt named the label. Rationale + history:
  `docs/BENCHMARK_FAIRNESS_REVIEW.md` Problem 1.
  Each arm also carries:
  - `success_rate_ci95_pct` — a 95% Wilson confidence interval (the plausible
    range for the true rate given the sample size). Quote it, not just the
    point estimate: 10/10 successes at n=10 still means "anywhere from 72% to
    100%".
  - `prompt_truncated_roles` — non-empty = that arm's installed prompt was
    clipped at Foundry's 8000-char limit; treat its numbers as invalid for
    comparison.
  - `execution_mode` — `"sequential"` (arms ran one after another) or
    `"parallel"` (arms shared one rate-limited endpoint at once). Seconds
    from parallel runs include rate-limit contention, so do not compare
    wall-clock across the two modes.
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
- **Don't treat `skills`/`maf_skills` violations as the agents "doing
  something wrong."** These no-protocol arms (formerly `bare`/`maf_groupchat`)
  are monitored against the canonical `v1.scr` whose label vocabulary the
  agents have never seen. They cannot satisfy it. That's the experimental
  point — `off_protocol` on every event is the expected baseline.
- **Don't conflate `spec_llmvalid` with running against the canonical
  protocol.** It projects from `llm_drafts/valid/v1.scr` (the LLM-drafted
  protocol that Scribble accepted), not from `protocols/v1.scr`.

## File map you'll need

| what | where |
|---|---|
| arm registry (9 core + 3 ablation + 17 legacy) | `experiments/baselines/registry.py` |
| 7 instruction builders | `experiments/baselines/instructions.py` |
| Foundry-stack runner (skills/spec/local(valid)/gate/sched) | `experiments/baselines/foundry_runner.py` |
| MAF runners | `experiments/baselines/maf_*.py` |
| Case driver | `experiments/scripts/case_runner.py` |
| Intent pipeline (author/distill/check/approve) | `experiments/scripts/intent_pipeline.py` |
| Case loader | `experiments/scripts/case_loader.py` |
| Per-case spec | `experiments/cases/<case>/case.yaml` |
| Canonical protocol | `experiments/cases/<case>/protocols/v1.scr` |
| Refinement sidecar | `experiments/cases/<case>/protocols/v1.refn` |
| LLM-drafted protocols | `experiments/cases/<case>/protocols/llm_drafts/{valid,unsafe}/v1.scr` |
| Re-anchored goals for LLM drafts | `experiments/cases/<case>/protocols/llm_drafts/{valid,unsafe}/goals.yaml` |
| (Stale) skills files | `experiments/cases/<case>/skills/v1/*_skills.md` — dead in the arm matrix |
| Runtime monitor | `stjp_core/monitor/monitor.py` |
| EFSM projection | `stjp_core/compiler/efsm_parser.py` (`get_all_efsms`) |
| Refinement loader | `stjp_core/compiler/refinement_checker.py` |
| Subagent markdown generator | `stjp_core/generation/agent_generator.py` |
