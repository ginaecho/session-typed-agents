# STJP Benchmark — experiments/

A versioned benchmark that compares multi-agent runs **with vs. without** STJP
session-type machinery, across multiple multiparty protocols. Each protocol is
a `cases/<case_id>/` directory; one case-agnostic runner
(`scripts/case_runner.py`) drives the 8-arm matrix for any case.

The runner imports the STJP library from `../stjp_core/`. The arm definitions
live in `baselines/` (see `baselines/README.md`); the metric design is in
`../docs/archive/EXPERIMENT_DESIGN_v2.md`.

## Layout

```
experiments/
  cases/
    <case_id>/                       e.g. finance, code_review, banking, ...
      case.yaml                      case config (schema below)
      protocols/
        v1.scr                       canonical Scribble global protocol
        v1.refn                      refinement contracts (sidecar)
        llm_drafts/                  LLM-drafted protocols (the WITH-llmvalid
          valid/  {v1.scr, goals.yaml}    arms) — produced by draft_llm_protocols.py
          unsafe/ {v1.scr, goals.yaml}
      skills/v1/                     per-role skills .md (auto-generated at run)
      runs/
        <ISO-timestamp>-n<N>-dual/   one benchmark run
          events_<arm>.jsonl         per-event JSONL, one file per arm
          summary.json               Set A (conformance) + process-cost metrics
          summary_eval.json          Set B (goal-achievement) metrics
      LATEST                         text pointer -> newest run dir
  baselines/                         the 8 arm runners (see baselines/README.md)
  scripts/
    case_runner.py                   the benchmark driver
    run_subset.py                    run a chosen subset of arms
    draft_llm_protocols.py           LLM-draft a protocol from a case's intent
    re_anchor_goals.py               re-anchor goals onto an LLM-drafted protocol
    evaluate_run.py                  standalone Set B evaluator (also wired into case_runner)
    index_builder.py                 regenerate INDEX.html
    case_loader.py                   case.yaml -> Case object
  INDEX.html                         cross-case dashboard (run index_builder.py)
  logs/                              run logs (tee'd by _smoke_all.sh / manual)
```

## The 8-arm matrix

Each run drives 8 arms; the variable is what protocol information the agents
get. Full table in `baselines/README.md`. In short:

- **intent-only** — `bare`, `maf_native`, `maf_foundry`, `maf_groupchat`
- **validated global type, no projection** — `maf_groupchat_unsafe` (Scribble
  *rejected* it), `maf_groupchat_llmvalid` (Scribble *accepted* it)
- **projected per-role local type + monitor** — `spec_llmvalid`, `min_llmvalid`

## Two evaluations per run (see EXPERIMENT_DESIGN_v2.md)

- **Set A — global-type conformance** — the local typed monitor walks each
  role's projected EFSM; `summary.json` carries `violations` / `violation_types`.
  Meaningful only for arms given a protocol.
- **Set B — goal achievement** — `summary_eval.json` carries `strict` /
  `role_pair` / `semantic` per arm. `case_runner.py` computes Set B (strict +
  role-pair) at the end of every run; `--semantic` adds the LLM-judged lens.
- **Process cost** — tokens, LLM calls, wall-clock, attempts — in `summary.json`.

## case.yaml schema

```yaml
case_id: finance                       # must match the directory name
description: |                         # one-paragraph human description
  Quarterly finance report with high/standard branching.
version: v1                            # which protocols/v* + skills/v* to use
protocol_name: QuarterlyFinanceReport  # the Scribble `global protocol <NAME>`
roles:                                 # ordered; first role usually starts
  - Fetcher
  - RevenueAnalyst
  # ...
terminal_label: GenerateReport         # session ends when this label is sent
max_steps: 24                          # per-trial safety bound
branch_hints: [high, standard]         # cycled across trials so each branch runs
role_descriptions:                     # prose, held constant across ALL arms
  Fetcher: retrieves raw revenue data on request
  # ... one line per role
intent: |                              # user-facing prose driving the scenario
  We need a Quarterly Finance Report pipeline ...
goals:                                 # outcome predicates checked post-trace
  - id: G1
    description: High-path revenue must exceed $50,000
    metric: revenue_amount
    predicate: float(x) > 50000        # python expression, x = payload
    anchor: {sender: Fetcher, receiver: TaxSpecialist, label: HighRevenue}
    threshold: "> 50000"
    branch: high                       # OPTIONAL — goal applies only on this
                                       # branch; vacuously satisfied elsewhere.
                                       # Omit for goals mandatory on every branch.
```

`protocols/v1.refn` uses the `refinement_checker.py` sidecar format:

```
[Fetcher -> TaxSpecialist : HighRevenue]
type: float
require: x > 50000.0
```

## Adding a new case

1. `mkdir -p cases/<case_id>/protocols cases/<case_id>/skills/v1`
2. Write `cases/<case_id>/case.yaml`, `protocols/v1.scr`, `protocols/v1.refn`.
3. Smoke the intent-only arms: `python scripts/case_runner.py <case_id> 1`.
4. For the WITH-llmvalid arms, draft the protocols first:
   ```
   python scripts/draft_llm_protocols.py <case_id>
   python scripts/re_anchor_goals.py <case_id> valid
   python scripts/re_anchor_goals.py <case_id> unsafe
   ```

`banking`, `travel`, and `rag` are scaffolded (canonical `.scr` + `.refn` +
`case.yaml`); they need the `draft_llm_protocols.py` step before the four
WITH-llmvalid arms will run.

## Running

```powershell
python scripts/case_runner.py finance 1            # 1 trial each (smoke)
python scripts/case_runner.py finance 10           # 10 trials each
python scripts/case_runner.py --all 10             # every case, n=10
python scripts/case_runner.py finance 10 --semantic        # + LLM-judged Set B
python scripts/case_runner.py finance 10 --resume <run_dir># resume a partial run
python scripts/case_runner.py finance --summarize-only <run_dir>  # re-aggregate
python scripts/run_subset.py finance 1 bare spec_llmvalid  # just these arms
python scripts/index_builder.py                    # refresh INDEX.html
```

## Authoring rules

- **Protocols must validate** against Scribble before they enter the benchmark
  (`case_runner` refuses to start on an invalid `.scr`). Author them
  deadlock-free: every role must participate in every branch of a choice.
- **Refinements** should include at least one numerical predicate so the
  comparison surfaces both the structural (EFSM) and value (refinement) gaps.
- **Goals** are evaluated post-trace. Tag a goal with `branch:` if it only
  applies on one branch (otherwise a missing anchor on the other branch fails
  the trial spuriously).
- **Naming**: `case_id` is lowercase snake_case; role names are PascalCase.

## Findings tracked across cases

1. **Refinement-violation finding** — LLM agents handed a structural protocol
   still pick payload values that violate value-dependent constraints. Closed
   at the call site via compiled refinement guards (see `../docs/reference/GAP_CLOSED.md`).
2. **Sequencing-violation finding** — agents handed both protocol and
   refinement still pick the wrong *message label* at the right *state* (e.g.
   skipping the audit step). The benchmark characterises its prevalence across
   protocol shapes.
