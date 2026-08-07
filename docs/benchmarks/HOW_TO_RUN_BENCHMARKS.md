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
