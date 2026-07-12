# W8 — Real-world skills miner (D5)

Worker report for `SEAM_TRAINING_EXECUTION_PLAN.md` §9 W8: "miner (D5) with
provenance/license ledger", done-when "≥150 `test-real` items or a
measured-yield report." This is the measured-yield report. Package:
`experiments/seam_bench/mining/` (branch `gc/seam-w8-miner`).

Inputs read first, per the task card: §3 (D4 split rules, D5) and §1 of the
execution plan; `docs/reference/reports/seam/scouts/R3_datasets_mining.md`
(ranked shortlist); `docs/reference/SKILL_COMPACTION.md`;
`experiments/cases/skills_safety/` (the existing recipe).

**2026-07-12 pointer:** every source repo named below now has a
live-verified canonical URL, license file URL, and (where a commit SHA and
path are both recorded) an exact-file permalink in
`docs/reference/MINED_SKILLS_SOURCES.md`, with a machine-readable copy at
`experiments/seam_bench/mining/sources.json`. That pass also found and
flagged a license inconsistency on the `crewAIInc/crewAI-examples`-derived
`content_pipeline` item — see the registry's Part A row 2.

---

## 1. Probe results (verbatim)

Run 2026-07-11, from this worker's assigned worktree.

```
$ timeout 15 git ls-remote https://github.com/github/awesome-copilot
30472ecf0fe34cc561df958c08501ecc5ca80ea4	HEAD
...
30472ecf0fe34cc561df958c08501ecc5ca80ea4	refs/heads/main
EXIT:0

$ curl -sS -o /dev/null -w "HTTP:%{http_code}\n" https://raw.githubusercontent.com/github/awesome-copilot/main/LICENSE
HTTP:200

$ curl -sS -o /dev/null -w "HTTP:%{http_code}\n" https://api.github.com/repos/github/awesome-copilot
HTTP:403

$ curl -sS -o /dev/null -w "HTTP:%{http_code}\n" https://codeload.github.com/github/awesome-copilot/tar.gz/refs/heads/main
HTTP:403

$ git ls-remote https://github.com/VoltAgent/awesome-claude-code-subagents   # HEAD 947b44ca0c...
$ git ls-remote https://github.com/anthropics/skills                        # HEAD 9d2f1ae187...

$ git clone --depth 1 https://github.com/github/awesome-copilot.git         # succeeded, 157M, HEAD 30472ecf0f...
$ git clone --depth 1 https://github.com/VoltAgent/awesome-claude-code-subagents.git   # succeeded, HEAD 947b44ca0c...
$ git clone --depth 1 https://github.com/anthropics/skills.git              # succeeded, HEAD 9d2f1ae187...
```

**Verdict: remote reachable.** `api.github.com` and `codeload.github.com`
are blocked (403, same as the pattern recorded in
`experiments/cases/skills_safety/_incoming/*/PROVENANCE.md` from an earlier
session) — but `raw.githubusercontent.com` is reachable AND, unlike that
earlier session, this sandbox's egress also permits the git smart-HTTP
protocol (`https://github.com/<owner>/<repo>.git` — `info/refs` +
`git-upload-pack`) for the three named out-of-scope repos
(`github/awesome-copilot`, `VoltAgent/awesome-claude-code-subagents`,
`anthropics/skills`), which is what `git clone`/`git ls-remote` actually
use. All three were cloned in full (shallow, `--depth 1`) with exact commit
SHAs recorded above. This task's harvest ran against those real,
network-fetched checkouts, not synthetic fixtures — **no GitHub MCP tools
were used against these out-of-scope repos**, per the environment
constraint.

**Unblock procedure (recorded for a future session where this probe fails
differently).** If `git clone`/`git ls-remote` are ever also blocked for a
target repo while `raw.githubusercontent.com` stays reachable: (a) recover
the file tree via a known index file (e.g. a marketplace/registry JSON, as
`_incoming/anthropic_skills/PROVENANCE.md` did for `anthropics/skills`
using `.claude-plugin/marketplace.json`) and fetch individual files over
`raw.githubusercontent.com`, recording "no commit SHA available" honestly
(as that PROVENANCE.md does) rather than fabricating one; or (b) if literal
git access is required, fork the target into the session-owner
(`ginaecho`) account, `add_repo` + clone the fork — mirrors
`docs/reference/NUSCR_CLOUD_INSTALL.md` Route B (built for the nuscr/
scribble-java toolchain under the same egress constraints). Neither was
needed this run.

Scribble toolchain: `bash tools/setup_scribble_cloud.sh` ran clean in this
worktree — "scribble-java smoke: gold PASS, corrupt REJECTED [real
toolchain OK]". Every `formalize.py` call in this report ran the real
`org.scribble.cli.CommandLine`, never a Python approximation
(`formalize.py::assert_toolchain` fails loudly otherwise, and does at
process start in `run_mining.py`).

---

## 2. What was built

`experiments/seam_bench/mining/`:

| file | role |
|---|---|
| `harvest.py` | adapters: `copilot_style` (`*.agent.md`/`*.instructions.md`), `skill_dir_style` (`SKILL.md` + frontmatter agent `.md`), `local_vendored` (`skills_safety/*/skills_original/`); `crewai_stub`/`langgraph_stub` interface stubs (R3: no static protocol to extract in the common case) |
| `ledger.py` | per-artifact `LedgerEntry`: source repo, SPDX + verbatim license quote, commit SHA, retrieval route, quarantine verdict |
| `intent_extract.py` | gold (a known-correct reference answer) intent recovery (frontmatter `description`, "when to use" section, opening prose paragraph); silver reverse-engineering path is a documented, unimplemented stub (no API spend) |
| `team_builder.py` | 3 heuristics in priority order: worked-example (skills_safety case boundaries + a curated real-file team mirroring `pr_merge`/`doc_pipeline`), explicit textual cross-reference (handoff-verb + role-name match), same-directory (capped at 6 roles) |
| `formalize.py` | team → `skill_compactor.compact_and_synthesize(..., llm_client=None)` → real `ScribbleValidator` → `DatasetRecord`; `FunnelStats` tallies every stage with drop reasons |
| `schema.py` | local `DatasetRecord` copy, field-identical to W1's `eval/schema.py` and W3's `data/common.py` (both unmerged as of this writing) — see the TODO in that file for consolidation |
| `run_mining.py` | CLI driver: harvest all sources → ledger → teams → formalize → write `ledger.jsonl`/`dataset_records.jsonl`/`team_results.jsonl`/`funnel.json` |
| `tests/` | 37 pytest tests, all passing (see §5) |
| `samples/` | this run's `funnel.json`, `team_results.jsonl` (13 lines), `dataset_records.jsonl` (0 records — see §3), `ledger_sample.jsonl` (115-entry stratified sample of the 609-entry ledger) |

---

## 3. The funnel (real counts, full run: 6 vendored teams + 3 remote repos)

Harvested from `experiments/cases/skills_safety/*/skills_original/` (local,
always available) plus the three cloned repos above.

| stage | granularity | count | of |
|---|---|---|---|
| harvested | artifact | 609 | — |
| licensed (not quarantined) | artifact | 605 | 609 |
| intent-recovered (gold) | artifact | 594 | 609 |
| teamed | artifact | 53 | 609 (556 unteamed) |
| team_license_ok | team | 13 | 13 teams formed |
| compactor_survived | team | **0** | 13 |
| compatibility_survived | team | 0 | 13 |
| synthesis_survived | team | 0 | 13 |
| validator_passed | team | 0 | 13 |
| **DatasetRecords emitted (test-real)** | — | **0** | — |

Harvest by source (adapter used): `github/awesome-copilot` 416 (copilot_style),
`VoltAgent/awesome-claude-code-subagents` 158 (skill_dir_style),
`anthropics/skills` 22 (skill_dir_style, incl. the 4 `doc_pipeline`
local-vendored artifacts re-attributed to their true upstream — see §4),
`crewAIInc/crewAI-examples` 4, `openai/openai-agents-python` 3,
`langchain-ai/langgraph` 3, `microsoft/autogen` 3 (these last 4 are the
local-vendored `skills_safety` artifacts, re-attributed by `ledger.py` to
their real upstream repo rather than credited to this repo).

**Teams formed (13):** 6 worked-example (the skills_safety case boundaries)
+ 2 worked-example (curated selections of the literal upstream files for
`pr_merge`/`doc_pipeline`, mirroring the same human curation but on raw
GitHub text instead of the paraphrased `skills_original/` copies) + 3
explicit-textual-reference teams found automatically in `awesome-copilot`
(e.g. two agents that each say "hand off to"/"invoke the" the other's
name) + 2 same-directory teams (`VoltAgent/tools/subagent-catalog`,
`awesome-copilot/skills/quality-playbook/agents`). 12 directories were
skipped as too-large for the same-directory heuristic (>6 files — mostly
`awesome-copilot/agents/`, `.../instructions/`, and 9 of VoltAgent's 10
category folders), their artifacts falling through to `unteamed`.

### Drop reasons

- **`licensed` (4 drops):** `anthropics/skills` ships 4 *document* skills
  (`docx`, `pdf`, `pptx`, `xlsx`) under a restrictive, source-available
  per-folder `LICENSE.txt` ("users may not: ... Reproduce or copy these
  materials ... Create derivative works") layered under the repo's
  Apache-2.0 default — `ledger.py::RESTRICTIVE_PATH_PREFIXES` catches these
  by path prefix and quarantines them regardless of the repo-level
  verdict. Same finding the in-repo `doc_pipeline` case's own PROVENANCE.md
  already made by hand; this run reproduces it mechanically.
- **`compactor_survived` (13/13 drops, 100%):** every team failed with the
  same class of error: *"free-form prose has no fenced ```localtype block
  or STJP heading format; deterministic (--no-llm) compaction cannot
  proceed"*. This is `skill_compactor.py`'s own, by-design behavior — see
  §4.

No team reached `compatibility_survived`, `synthesis_survived`, or
`validator_passed`; the DatasetRecord count for `test-real` from this
task's own mined harvest is **0**.

---

## 4. Why the yield is 0% under `--no-llm`, and why that is expected

`skill_compactor.compact_skill_file` tries three sources per file, in
order: (1) a fenced ` ```localtype ` block, (2) the strict STJP
`## Receives` / `## Sends` / `## Execution Flow` heading format
(`generation/skills_parser.py`), (3) the LLM. Both (1) and (2) are
**STJP-internal authoring conventions** — no file harvested from GitHub
uses either, by construction (they aren't something a `awesome-copilot`
agent author or a `VoltAgent` subagent author would ever write). Verified
directly before building the pipeline:

```
$ for f in experiments/cases/skills_safety/*/skills_original/*.md; do
    grep -c '```localtype' "$f"; grep -cE '^## (Receives|Sends|Role Purpose)' "$f"
  done
# 21/21 files: fence=0 stjp=0
```

This task's constraint (task card: "use --no-llm deterministic mode; the
LLM-fallback path is recorded as skipped, no API spend") means (3) is
never tried. The result is not a bug in `formalize.py` — it is the
compactor doing exactly what it says on the tin. Confirmed by two
cross-checks:

1. **The pipeline's downstream half is provably sound.** A synthetic
   4-role escrow-trade team (escrow: a neutral third party that holds funds
   until both sides deliver) WITH fenced `localtype` blocks (the same
   fixture `stjp_core/tests/test_skill_compactor.py` uses) runs the
   identical `formalize_team` code path end-to-end to a REAL-Scribble-
   validated `DatasetRecord`
   (`tests/test_formalize.py::test_synthetic_escrow_team_survives_end_to_end_with_real_scribble`).
2. **The in-repo precedent already shows the same shape.** Every
   `skills_safety` case's `skills_original/` (the mined, unsafe-by-design
   originals) has **no** fenced block and was previously compacted only
   via the LLM path (`_before/local_types/*.json` note: `"compacted by
   LLM"`) — and even then, `content_pipeline`'s original skills FAILED
   multiparty-compatibility (`_before/verdict.txt`: 9 `[ERROR]` findings,
   e.g. "Editor sends Feedback(String) to Writer, but Writer's local type
   never receives Feedback from Editor"). Only the hand-authored
   `skills_revised/` (fenced blocks, written by an STJP author fixing the
   case, not mined) synthesize and validate. That is the entire point of
   the `skills_safety` case family: **real, independently-written skills
   under-determine safe coordination even after LLM compaction** — exactly
   the plan's own framing ("a low yield is itself a paper finding").

---

## 5. Tests

`experiments/seam_bench/mining/tests/`, 37 tests, all passing:

```
test_formalize.py ....       (4  — real Scribble toolchain, no mocking)
test_harvest.py .........    (9  — adapters over tests/fixtures/)
test_intent_extract.py ..... (5)
test_ledger.py .......       (7  — incl. license quarantine)
test_schema.py ......        (6  — incl. schema validity / unknown-field rejection)
test_team_builder.py ......  (6  — incl. heuristic priority / no double-claiming)
====================== 37 passed in ~1.7s ======================
```

`test_formalize.py` is the load-bearing one: it (a) reproduces the real
`pr_merge` compaction failure against the actual vendored files, (b) proves
the success path end-to-end against the real Scribble CLI, (c) checks
license quarantine actually blocks a team before compaction is attempted,
and (d) runs the full 6-team vendored driver and asserts the empirically
measured 0/6 survival — so a future change that silently makes compaction
"succeed" without an LLM would fail this test loudly, and a regression that
breaks the (currently working) success path would too.

---

## 6. Honest projection: R3's 120–260 candidates → test-real yield

R3's shortlist (`R3_datasets_mining.md`) estimated **120–260 candidate
(intent, skills-team) items** across `awesome-copilot` + `VoltAgent` +
`anthropics/skills`, "before the compactor/validator/round-trip filters."
This run measured the actual filter: **0/13 real candidate teams (0%)**
survive the `--no-llm` compactor, and the two independent cross-checks in
§4 show this isn't a fluke of team selection — it's structural (no
harvested source authors STJP-format contracts, by construction).

**Projected test-real yield under this task's exact constraints (no LLM,
no API spend): ~0 of R3's 120–260 candidates.** Scaling up the same team-
building heuristics against the full `awesome-copilot`/`VoltAgent` corpora
(556 unteamed artifacts, 12 skipped oversized directories in this run
alone) would very likely find more *candidate* teams than the 13 found
here — but every one of them would hit the identical `compactor_survived`
wall, because that wall is about file **format**, not team **selection**.
More candidates does not change a 0% conversion rate that has nothing to
do with sample size.

**With an LLM compaction step enabled** (explicitly out of scope for this
task — "no API spend"), the honest projection is still well below R3's
120–260 raw-candidate figure, not close to it, for a structural reason
independent of the LLM. Checked directly in-repo: of the 6 `skills_safety`
cases, 4 (`airline_seat`, `booking_saga`, `code_execution`,
`content_pipeline`) have a preserved `_before/verdict.txt` recording what
happened when their **original** (mined) skills were LLM-compacted and
compatibility-checked, prior to any human fix. **All 4 of 4 FAILED
multiparty-compatibility** — e.g. `booking_saga`: "Hotel sends
BookingConfirmed() to Traveler, but Traveler's local type never receives
BookingConfirmed from Hotel" plus two more findings; `code_execution` and
`airline_seat` similarly, each with 4-5 independent ERROR findings. The
remaining 2 cases (`pr_merge`, `doc_pipeline`) have no `_before` record at
all — they were never independently LLM-compacted-and-verified in this
repo, so this sample cannot claim anything about them either way. Reading
the honest sample as given (0/4 measured, 2/6 unmeasured): **LLM
compaction alone converts on the order of 0-in-4 to maybe 1-in-6 real
teams to a compatible protocol**, before the validator even runs. Applying
that rate to R3's 120–260-candidate estimate (roughly 20-45 curated teams
at ~5-6 candidates per team) projects on the order of **0-10 validated
`test-real` items**, not the plan's 150–300 target — meaning D5 alone,
even with the LLM step funded, is very unlikely to hit that target on
harvest-and-validate alone. Either (a) the 150-300 target needs revising
down for D5's share specifically, or (b) D5 needs a *repair* step (LLM
proposes an ordering fix when compatibility fails, mirroring what a human
did by hand for all 4 of the measured `skills_safety` cases) rather than a
pure harvest-and-validate pipeline. This is exactly the "low yield is
itself a paper finding" the plan anticipated (§3 D5) — the finding is now
measured, not merely predicted.

---

## 7. Artifacts

- Package: `experiments/seam_bench/mining/` (this branch).
- Sample outputs: `experiments/seam_bench/mining/samples/` — `funnel.json`
  (full run), `team_results.jsonl` (13/13 teams, all with their exact drop
  stage), `dataset_records.jsonl` (0 records — honest), `ledger_sample.jsonl`
  (115-entry stratified sample of the 609-entry ledger; every quarantined
  entry is included, plus up to 40 permissive entries per source repo).
- The three remote checkouts used for this run were not committed (git
  clones, ~200MB+ combined); reproduce via the commands in §1, then:
  `python experiments/seam_bench/mining/run_mining.py --out-dir <dir>
  --remote-root <dir containing awesome-copilot/, VoltAgent/,
  anthropic-skills/>`.
