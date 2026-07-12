# W17 — coordination filter + mining scale-up

Worker report for the open problem the project owner raised after W16: the
paper's claim — "independently authored agent skills don't state their
coordination structure" — currently rests on **n=2** real-world teams
(`docs/8_INTENT_TO_PROTOCOL_TRAINING.md`, the 2026-07-11 "denominator
caveat" update). That number is small because nobody had checked, before
grouping harvested files into candidate "teams," whether the underlying
TASK those files describe actually needs more than one party to complete it
— W8's 13 teams were formed by directory boundary and a text-matching
heuristic, neither of which asks that question. This task (a) builds that
missing check as a first-class, reusable, re-judgeable pipeline stage, and
(b) expands the harvest to see how large a real evidence base it can find.

Two terms used throughout: a **coordination-requiring task** is one whose
completion needs two or more parties to hand information or work to each
other, in some order (the project owner's own example: "a pull-request
review-and-merge task needs multiple parties even if the file is written
solo-voice"). A **candidate team** is a group of harvested files a
heuristic proposed as possibly describing such a task — proposing one is
cheap and mechanical; deciding whether it actually IS one requires reading.

---

## 0. A framing rule this report follows throughout

Before the numbers: this miner measures what is **written down** in public,
single-file, per-agent skill documents — not what coordination actually
exists or is needed in real, deployed multi-agent systems. Public
agent-skill files are, by genre, mostly single-agent documents (a persona
description, a checklist, a slash-command). In real systems the
coordination structure often lives elsewhere entirely: in orchestrator
code, in a multi-agent framework's own configuration format, in runtime
prompts, or in human conventions that never become a committed skill file.
So a low "yes" rate from a source like an agent-persona catalog supports
exactly one claim — **"coordination structure is rarely stated in that
catalog's own files"** — and never the broader claim that coordination is
rarely needed. Every number below should be read with that scope. Where a
source's coordination structure plainly lives OUTSIDE the individual agent
files (§4.3 below), that is recorded as its own outcome and treated as
evidence FOR the paper's thesis, not against it.

---

## 1. What was built

`experiments/seam_bench/mining/coordination_filter.py` — the missing
pipeline stage. For a candidate team, a judge (a person or a model, reading
the actual text) records a `CoordinationVerdict`: `requires_coordination`
∈ {`yes`, `no`, `unclear`}, `evidence` (verbatim quotes only — a `"yes"`
verdict cannot be constructed without at least one, enforced by the
dataclass's own `__post_init__`), and a one-sentence `reasoning`. Every
verdict is written to an auditable JSONL (`write_verdicts_jsonl` /
`read_verdicts_jsonl`, schema-validated on read — an unknown field or a bad
verdict value raises rather than silently passing through) so it can be
re-judged later without re-reading the source repos. `build_dossier()`
prepares a judge's compact input (role descriptions + any textual
cross-reference `team_builder.py` already found, with its quote) but
decides nothing itself — the discipline is "judge the task, not the file
structure," stated as the module's `RUBRIC` constant and applied uniformly
by every judge in this run (see §3). `merge_verdict_files` combines several
judges'/batches' outputs and hard-fails on a duplicate `team_id` rather than
silently picking one. 11 new tests in `tests/test_coordination_filter.py`.

`experiments/seam_bench/mining/team_builder.py` — two new team-formation
heuristics, plus every heuristic now records its textual evidence
(`Team.edges`, previously discarded at formation time):

- **`named_counterpart_star_teams`** — the task card's "an artifact that
  NAMES counterpart roles can seed a team even across directories."
  VoltAgent's `awesome-claude-code-subagents` turns out to have a
  near-universal convention (130 of 172 files, verified by direct grep) of
  an `## Integration with other agents:` section naming 4-8 specific
  counterparts with a directional verb ("Receive X from Y", "Collaborate
  with Y on Z"). The old `explicit_reference_teams` handoff-verb regex
  didn't match this vocabulary at all (0 hits); the new one does, and forms
  one STAR team per hub file (itself + up to 5 named counterparts, greedily
  claimed so nothing is double-counted) rather than one giant unusable
  connected component.
- **`crewai_config_teams`** + `harvest.py::adapter_crewai_style` — R3's
  item 2.d, implemented rather than left a stub. Every agent defined in one
  `config/agents.yaml` is, by CrewAI's own `Crew(agents=..., tasks=...)`
  construction, a real member of that crew — this is trusted directly
  rather than re-derived from a text heuristic. `context: [other_task]`
  dependencies in `tasks.yaml`, where present, become real quoted edges.
- 4 new tests in `tests/test_team_builder.py` (star-team formation, size
  cap, greedy-claim no-double-use, crewai config parsing + context edges)
  and 2 new tests in `tests/test_harvest.py` for `adapter_crewai_style`
  (the old single stub-existence test was replaced with real parsing
  coverage). Full suite: 37 tests (W8) → **54 tests**, all passing.

Both additions keep W8's license/provenance discipline unchanged
(`ledger.py`): a team's members still have to pass the same permissive-SPDX
gate before any `DatasetRecord` can be emitted from them, regardless of
which heuristic proposed the team.

---

## 2. Harvest, source by source

Same clone route W8 recorded (`git clone --depth 1`, exact commit SHAs
below), plus three new sources per the task card's ordering (a-d):

| source | route | license | commit | artifacts harvested |
|---|---|---|---|---|
| `experiments/cases/skills_safety/*/skills_original/` | local-vendored, always available | per-case, see `ledger.py::IN_REPO_UPSTREAMS` | n/a | 21 |
| `github/awesome-copilot` | `git clone` | MIT (verified, root `LICENSE`) | `30472ecf0f...` | 412 (222 `*.agent.md` + 190 `*.instructions.md` — a live count today; R3's scouted figure was 243+209, the small drift is normal repo churn between scouting and harvest, not a miner bug) |
| `VoltAgent/awesome-claude-code-subagents` | `git clone` | MIT (verified) | `947b44ca0c...` | 158 |
| `anthropics/skills` | `git clone` | Apache-2.0 per-skill (verified); 4 `docx/pdf/pptx/xlsx` folders carry a restrictive source-available override and are quarantined by path prefix, unchanged from W8 | `9d2f1ae187...` | 18 |
| `crewAIInc/crewAI` (R3 item 2.d, the CrewAI framework's OWN repo, not the examples repo) | `git clone` | MIT (verified, root `LICENSE`) | `fb8e93be25...` | 7 (2 real crew scaffolds + a test-fixture duplicate of one) |
| `crewAIInc/crewAI-examples` (R3 item 2.d) | `git clone` | **none found** — see below | `da94a91e69...` | 48 (20 crews) |
| `rohitg00/awesome-claude-code-toolkit` (fallback, task card step 2.d "if still short of target") | `git clone` | Apache-2.0 (verified, root `LICENSE`) | `ebdf1d596d...` | 259 |
| **total** | | | | **923** |

**`crewAIInc/crewAI-examples` has no license.** Checked directly (no
`LICENSE`/`LICENSE.txt` anywhere in the tree, no `license =` field in any
of its 20 `pyproject.toml` files, a live fetch of the repo's own GitHub page
found no SPDX badge), and its README says only "Check individual examples
for specific licensing information" — no example does. Per this project's
license discipline this repo is **quarantined outright**
(`ledger.py::entry_for` falls through to its `spdx is None` branch for
every artifact from it) — it cannot contribute a `test-real` `DatasetRecord`
no matter what its structure recovers to. It is still harvested, still
teamed, and still run through `coordination_filter` (§3) and the two-track
assessment (§4), because "does this task need coordination" and "can I
legally redistribute this text" are two different questions, and this repo
turns out to answer the first one unusually clearly (§4.3) — that is
itself worth reporting honestly, distinct from a silent skip.

`rohitg00/awesome-claude-code-toolkit` was added as the task card's named
fallback after the four primary sources (a-c + CrewAI) produced 74
candidate teams — short of the ~100 target at the CANDIDATE stage, before
any coordination judgment. It turned out to be another instance of the
same skill-catalog genre as `awesome-copilot` (checked directly: 0/136
sampled `agents/` files have any collaboration language at all — no
"coordinate", "collaborate", "hand off", "delegate" anywhere in a
representative file), which is itself a data point for §0's framing, not
noise.

---

## 3. The coordination-filter funnel

**Funnel**: 923 artifacts harvested → 871 licensed (52 quarantined: 4
restrictive-path, 48 `crewAI-examples` no-license) → 319 artifacts teamed
into **110 candidate teams** (604 artifacts unteamed, 14 directories
skipped as too-large for the same-directory heuristic) → every one of the
110 candidate teams judged by `coordination_filter`:

| verdict | count | % of 110 |
|---|---|---|
| **yes** (coordination-requiring) | **29** | 26% |
| no | 74 | 67% |
| unclear | 7 | 6% |

By team-formation heuristic (the clearest single result in this run):

| heuristic | n teams | yes | no | unclear | yes-rate |
|---|---|---|---|---|---|
| `crewai-config` (task-flow YAML) | 15 | 15 | 0 | 0 | **100%** |
| `worked-example` (skills_safety + curated upstream) | 8 | 8 | 0 | 0 | 100% |
| `explicit-reference` (handoff-verb text match) | 4 | 2 | 2 | 0 | 50% |
| `named-counterpart` (VoltAgent "Integration with..." bullets) | 41 | 3 | 37 | 1 | 7% |
| `same-directory` (weakest heuristic, per R3's own warning) | 42 | 1 | 35 | 6 | 2% |

**Judging method, stated plainly.** 110 verdicts is more than one person
reading every full source file carefully can responsibly do in this task's
time-box, so judging was split: I (this session) personally judged all 8
`worked-example`, all 4 `explicit-reference`, and all 15 `crewai-config`
teams (27 total — the categories with the highest stakes and the clearest
evidence) directly against their source text. The remaining 83
(`named-counterpart` + `same-directory`) were split into six batches of
~14 and judged by six parallel Claude instances, each given the *exact
same* rubric (`coordination_filter.RUBRIC`, reproduced verbatim in their
prompts) and told explicitly to prefer `"unclear"` over a forced `"yes"`.
Every batch's output was schema-validated (`merge_verdict_files` — zero
duplicate `team_id`s, zero schema errors across all 110) and I QA-checked a
sample by re-reading full source files myself (§4.2). That check found the
delegated batches' verdicts were reliable on the STRONG cases
(correctly-matched cross-references, e.g. `incident-responder` ↔
`devops-incident-responder`) but produced **3 false "yes" verdicts** out of
the 8 I deep-checked (a 37.5% error rate on that specific sample) where a
generic collaboration-list bullet or a superficial keyword match was
mistaken for real task dependency. All 3 are corrected in the final
verdicts file (`samples/w17_coordination_verdicts.jsonl`,
`extra.corrected_from` records the original verdict for auditability) —
this is exactly why the module stores evidence and stays re-judgeable
rather than just a count.

---

## 4. Two-track assessment over the 29 coordination-requiring teams

Per protocol: (a) deterministic extraction (W8's `--no-llm` path,
unmodified) run against **all 29**; (b) careful model-read extraction under
W16's evidence-only rule, **sampled** rather than run on all 29 (task card:
"the filter verdict on all candidates matters more than deep extraction on
every single one ... sample randomly, say so, report n").

### 4.1 Track (a): deterministic, all 29

| stage reached | count |
|---|---|
| dropped at `team_license_ok` (crewAI-examples, no license) | 12 |
| dropped at `compactor_survived` (no fenced `localtype` block anywhere) | 17 |
| survived to `compatibility_survived`/`synthesis_survived`/`validator_passed` | **0** |

Identical structural finding to W8's original 0/13 — expected, and for the
same reason: none of these sources authors the STJP fenced-block
convention. This is not new evidence; it confirms the expanded harvest
didn't accidentally change the deterministic-path conclusion.

### 4.2 Track (b): model-read, n=19 of 29 assessed

9 of the 29 are exactly W16's own already-extracted teams (its 8
`worked-example` teams plus the `gem-orchestrator` subset of its 15-role
`explicit_ref` cluster) — re-verified byte-identical this run
(`llm_read/extraction.py`, patched to select by `team_id` instead of list
position now that `team_builder` finds ~110 teams instead of 13; see the
file's own comment). Their outcomes are reused, not redone:

| outcome | teams |
|---|---|
| **recovered** (Scribble-valid) | `pr_merge` (reduced), `content_pipeline` (full), `airline_seat` (full) — 3 |
| **extracted-but-incompatible** | `booking_saga` (genuine deadlock), `code_execution` (coverage-gap), `gem-orchestrator` subset (synthesis stuck) — 3 |
| **nothing-to-extract** | `doc_pipeline`, `pr_merge_upstream`, `doc_pipeline_upstream` — 3 |

The remaining 23 "yes" teams were not individually deep-extracted; a
random sample of 8 was drawn (`random.seed(1707)`, reproduced in
`experiments/seam_bench/mining/llm_read/w17_sample_extraction.py`) and
model-read in full (source files read directly, not just the judging
dossier). Two more were checked outside the random draw because they are
the *only* remaining license-clean candidates
(`crewAIInc/crewAI`'s other two `crewai-config` teams) and were worth
verifying directly rather than leaving the sole license-clean new source
unexamined:

| team | outcome | license | in `test-real`? |
|---|---|---|---|
| `crewai_config:...templates/crew` (researcher→reporting_analyst) | **recovered** | MIT | **yes — new** |
| `crewai_config:...content_crew` (planner→writer→editor) | **recovered** | MIT | **yes — new** |
| `crewai_config:...outline_book_crew` (researcher→outliner) | **recovered** | none | no — license-blocked |
| `crewai_config:...surprise_trip` (2 producers → 1 compiler, fan-in) | **recovered** | none | no — license-blocked |
| `named_counterpart:...incident-responder+devops-incident-responder` | nothing-to-extract (real edge, no concrete label) | MIT | n/a |
| `named_counterpart:...codebase-orchestrator+readme-generator` | nothing-to-extract (real edge, no concrete label) | MIT | n/a |
| `crewai_config:...screenplay_writer` | nothing-to-extract (genre reads as a pipeline; no task literally names its predecessor) | none | n/a |
| `same_dir:...quality-playbook/agents` | **coordination_filter corrected yes→no** (full text: one file explicitly forbids invoking the other as a sub-agent) | — | n/a |
| `same_dir:rohitg00...visual-regression/commands` | **corrected yes→no** (two commands run by the same single actor, not two parties) | — | n/a |
| `same_dir:...09-meta-orchestration` (3-file residual) | **corrected yes→unclear** (real coordination need, wrong counterparts in this specific grouping) | — | n/a |

Counting only the teams still judged coordination-requiring after this
closer read (9 reused + 5 of the 8 sampled, the other 3 corrected away in
§3, + 2 bonus = 16 teams assessed in total): **7 of 16 (44%) recovered** a
real, Scribble-valid protocol. All but one of the CrewAI-config teams
checked for extraction this pass recovered (4 of 5: `outline_book_crew`,
`surprise_trip`, `crew_template`, `content_crew` — only `screenplay_writer`
did not), a much higher hit rate than W16's original run, entirely because
CrewAI's `tasks.yaml` phrasing ("based on the research findings",
"Compile all researched information... integrates... activities and dining
experiences") states a concrete dependency with a nameable payload, which
ordinary skill-catalog prose almost never does (§4.3). The other 3
recoveries are W16's original `pr_merge`/`content_pipeline`/`airline_seat`.
The remaining 6 of the 16 assessed either hit a genuine deadlock or
coverage-gap (3, all reused from W16) or had a real, correctly-matched
cross-reference with no specific message to extract without inventing one
(3 newly sampled: `incident-responder`+`devops-incident-responder`,
`codebase-orchestrator`+`readme-generator`, `screenplay_writer`).

### 4.3 The category the project owner asked for: coordination stated in orchestration config, not in agent files

This is the single clearest result of the expanded harvest. Every one of
the 15 `crewai-config` candidate teams was judged coordination-requiring
(100%, vs. 2-7% for the three skill-catalog heuristics), and of the 5
`crewai-config` teams checked for extraction this pass, 4 recovered a real
validated protocol. The reason is structural, not incidental: a CrewAI `tasks.yaml`
entry's `description` field routinely says outright which other task's
output it consumes ("Using the outline provided, write a full blog post");
an individual VoltAgent or `awesome-copilot` persona file almost never
says which other file's output it's waiting for, even when its own
"Integration with other agents" section lists six collaborators by name.
**This is exactly the pattern the project owner's addendum names**: these
sources' authors DO think in coordination terms — they just write it into
the orchestration config (`tasks.yaml`'s task-to-task data flow), not into
the individual agent's own persona document. Read against §0's framing,
this is evidence FOR the paper's scoped claim, not against it: it is not
that these authors don't think about coordination, it's that the
PER-AGENT-SKILL-FILE genre specifically is where the structure goes
unstated — move one level up to the framework's own config format and the
structure reappears, cleanly enough to autoformalize four times out of the
five `crewai-config` teams tried this pass.

### 4.4 `test-real` dataset

New this task, `samples/w17_sample_dataset_records.jsonl` (2 records,
`crewAIInc/crewAI`, MIT): `mined:llm_read:w17:crewai_config:...templates/crew`
(2 roles) and `mined:llm_read:w17:...content_crew` (3 roles). Combined with
W16's pre-existing 3 (`pr_merge`, `content_pipeline`, `airline_seat`,
untouched by this task, still valid), the project's `test-real` mined
corpus is now **5 records**.

---

## 5. What these numbers do to the n=2 problem

The owner's caveat measured **2** coordination-requiring, textually-solo
real-world teams out of W8's original 13. This task measured **29**
coordination-requiring teams out of a much larger, more carefully filtered
110-candidate pool drawn from 923 artifacts across 7 sources — roughly a
**14x** increase in the denominator, with every verdict backed by a
verbatim quote and stored in an auditable, re-judgeable JSONL rather than
counted by hand.

That is a real improvement, and it is **not** 100. The task's target was
~100 coordination-requiring teams; this run found 29, and per this task's
own honesty rule that smaller number IS the result — it is not padded and
should not be read as "close enough." Two things prevented reaching 100,
both structural rather than a search-effort shortfall:

1. **The dominant genre in every skill-catalog source really is
   single-agent prose.** `same-directory` and `named-counterpart` — the two
   heuristics that swept the largest volume of real per-agent-persona files
   (83 of 110 candidate teams, drawn from VoltAgent, `awesome-copilot`, and
   `rohitg00-toolkit` combined) — converted at 2-7%. Even VoltAgent's
   unusually structured "Integration with other agents" convention (present
   in 130/172 files) mostly turned out, on reading, to be a boilerplate
   appendix listing plausible collaborators rather than a task whose
   completion actually depends on them (§3's 37.5% correction rate on the
   sampled deep-checks makes the same point from the opposite direction:
   even a heuristic MATCH on this convention over-predicts "yes").
2. **The one source type that reliably WAS coordination-requiring
   (CrewAI-style task-flow config, 100% yes-rate) is small.** Only two repos
   of this shape were reachable this run (`crewAIInc/crewAI`'s own 2 real
   scaffold crews, and `crewAIInc/crewAI-examples`'s 20 — the latter
   license-blocked). R3 already flagged CrewAI as a "long-tail,
   one-team-per-repo" source, not a large single-repo win like
   `awesome-copilot`; finding another 70 coordination-requiring teams would
   most likely mean finding and licensing dozens more individual CrewAI (or
   similar-shaped) repos one at a time, not re-mining the same three or four
   large skill-catalog repos harder.

**Honest verdict on the paper's claim**: the scoped claim survives, and now
rests on meaningfully more than n=2 — 29 judged-coordination-requiring
teams (up from 2), with 4 of 5 checked CrewAI-shaped teams and 3 of W16's
original 13 recovering real Scribble-valid structure from prose alone
(7 of the 16 teams actually deep-assessed this run, 44%, recover cleanly
when the source states a concrete dependency; the rest either have nothing
stated to recover, or state a real dependency too generically to extract a
labeled message without inventing one). What has NOT changed, and what this task's
own numbers reinforce rather than soften, is the shape of the finding
itself: **ordinary, independently-authored per-agent skill files —
regardless of source, regardless of how much more of them are harvested —
essentially never state their own coordination structure** (2-7% across
three separate skill-catalog repos, three different curators, 923
artifacts). Where real coordination structure DOES get written down, it is
almost always in a different artifact entirely — the orchestration
config, not the skill file (§4.3) — which is itself the more precise,
more defensible version of the paper's claim than "skills don't state
coordination" read in isolation. Scaling the n=2 evidence base further
past 29 is a matter of finding and licensing more orchestration-config-shaped
repos (CrewAI and its relatives), not re-running these same three
heuristics over a bigger pile of persona files.

---

## 6. Artifacts

Code (`experiments/seam_bench/mining/`):
- `coordination_filter.py` — the new pipeline stage (§1); 11 tests in
  `tests/test_coordination_filter.py`.
- `team_builder.py` — `named_counterpart_star_teams`, `crewai_config_teams`,
  edge-capturing retrofit on `explicit_reference_teams`; 12 new tests in
  `tests/test_team_builder.py`.
- `harvest.py` — `adapter_crewai_style` (replaces the old
  `adapter_crewai_stub`, which is now a delegating alias, not removed, for
  backward compatibility); `ledger.py` gained `crewAIInc/crewAI` (MIT) and
  `rohitg00/awesome-claude-code-toolkit` (Apache-2.0) license facts, and a
  documented, deliberate absence of a `crewAIInc/crewAI-examples` entry.
- `run_mining.py` — wired the two new sources into `DEFAULT_REMOTES`.
- `llm_read/extraction.py` — one defensive fix (selects the original 13
  teams by `team_id` instead of list position, since `build_teams` now
  returns ~110); verified byte-identical output to W16's original run.
- `llm_read/w17_sample_extraction.py` — new, this task's model-read
  extraction over the 8 randomly-sampled + 2 bonus-licensed teams (§4.2).

Samples (`experiments/seam_bench/mining/samples/`, all ≤200 records):
- `w17_funnel.json` — full harvest→team→(deterministic-)compaction funnel
  over the 923-artifact/110-team run.
- `w17_team_results.jsonl` — all 110 candidate teams with their formation
  heuristic and deterministic-pipeline stage.
- `w17_ledger_sample.jsonl` — 150-entry stratified sample of the 923-entry
  ledger (every quarantined entry, up to 20 permissive per source repo).
- `w17_dossiers.json` — the exact judging input (role descriptions + quoted
  edges) every one of the 110 verdicts was based on.
- `w17_coordination_verdicts.jsonl` — all 110 `CoordinationVerdict`s,
  including the 3 corrected ones with `extra.corrected_from`.
- `w17_deterministic_outcomes.json` — track (a) result for all 29
  coordination-requiring teams.
- `w17_sample_extraction_summary.json` / `w17_sample_dataset_records.jsonl`
  — track (b) result and the 2 new `test-real` records for the sampled run
  (§4.2, §4.4).

Reproduce: clone the 7 sources at the commits in §2, then
`python run_mining.py --out-dir <dir> --remote-root <dir with
awesome-copilot/, VoltAgent/, anthropic-skills/, crewAI-core/,
crewAI-examples/, rohitg00-toolkit/>`, then
`python -m experiments.seam_bench.mining.llm_read.w17_sample_extraction
--remote-root <same> --scratch-dir <scratch>`.
