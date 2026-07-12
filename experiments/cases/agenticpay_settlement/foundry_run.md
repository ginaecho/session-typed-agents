# Running `agenticpay_settlement` on Azure AI Foundry

This file is the exact, checkable command sequence for reproducing the
`RESULT_1_DEADLOCK.md`-style comparison on this case: an **unchecked**
arm (agents follow their own hand-written rules — expected to deadlock,
0 trades completed) against an **STJP-validated** arm (agents follow a
Scribble-checked protocol — expected to complete every trial), swept
across a matrix of Azure AI Foundry model deployments.

Everything below was verified by reading the harness code, not by running
it — this repo has no Azure credentials. Every command references a script
or flag that exists today (grep pointers given inline). Section 5 lists the
one real gap found in the harness and how this setup works around it
without inventing anything.

## 1. Prerequisites (on the machine that will actually run this)

1. `az login` — the harness authenticates via `AzCliCredential`
   (`stjp_core/foundry/az_credential.py`), not API keys.
2. `stjp_core/.env` with at minimum:

   | key | value |
   |---|---|
   | `AZURE_AI_PROJECT_ENDPOINT` | your Foundry project endpoint |
   | `AZURE_OPENAI_DEPLOYMENT` | one deployment name (see the model-matrix section — this gets overridden per sweep run) |

   See `stjp_core/CLAUDE.md` ("Env vars (in `.env`)") for the full table,
   including the optional `AZURE_OPENAI_ENDPOINT` / `STJP_LLM_BACKEND` keys
   (only needed for the non-default `chat` backend, not used here).
3. In your Foundry project, create **five model deployments** — one per
   entry in your model matrix (Section 4). The *names* you give them in
   Foundry are what you pass to this harness; nothing here hardcodes model
   names beyond the placeholders `opus-4.7`, `opus-4.6`, `sonnet-5`,
   `sonnet-4.6`, `haiku-4.5` used as examples throughout.
4. Python environment for `experiments/` set up per the repo's normal
   instructions (`pip install -r requirements.txt` or equivalent — not
   re-documented here).

All commands below are run from the `experiments/` directory (matches the
usage line in `experiments/scripts/case_runner.py`: `python
scripts/case_runner.py <case_id> [n_trials]`).

## 2. One-time setup for this case: generate the validated protocol draft

The case's own `protocols/v1.scr` is the hand-authored, Scribble-validated
escrow-first fix (see this directory's `README.md`). But the harness's
registered WITH-arms (`spec_llmvalid`, `min_llmvalid` in
`experiments/baselines/registry.py`) do **not** read `protocols/v1.scr`
directly — every WITH-arm factory in that file is built through
`_make_foundry_llm_drafted_factory`, which calls `_require_llm_draft` and
fails fast unless `protocols/llm_drafts/valid/v1.scr` exists
(`registry.py:82-91`). That file does not exist yet for this case (only
`trade_deadlock` and five other cases have it — verified: `find
experiments/cases -path "*llm_drafts*"` does not list
`agenticpay_settlement`). Generating it is a real, existing, generic script
— not something invented for this task:

```bash
cd experiments
python scripts/draft_llm_protocols.py agenticpay_settlement 10
```

This calls the LLM (`stjp_core/authoring/architect.py:ArchitectAgent`,
which itself goes through Foundry per `stjp_core/CLAUDE.md`'s
Foundry-first rule) up to 10 times, keeps the first Scribble-valid draft,
and writes `protocols/llm_drafts/valid/v1.scr`. Because
`case.yaml`'s `intent` already spells out the escrow-first fix in prose,
this is very likely to reproduce essentially the same message sequence as
the hand-authored `protocols/v1.scr` (this is exactly what happened for
the `trade_deadlock` sibling case — its
`protocols/llm_drafts/valid/v1.scr` is structurally identical to its
canonical `protocols/v1.scr`).

Then re-anchor the goals to that draft's labels (also a real, existing,
generic script):

```bash
python scripts/re_anchor_goals.py agenticpay_settlement valid
```

This writes `protocols/llm_drafts/valid/goals.yaml`.

**Optional, not required:** `build_spec_instructions` /
`build_spec_minimal_instructions` auto-discover a sibling `.refn` file
next to whatever `.scr` they're projecting
(`stjp_core/compiler/refinement_checker.py:287-292`). Neither script above
writes `protocols/llm_drafts/valid/v1.refn`. If you want the refinement
guards (funded amount > 0, released payment > 0) enforced on the LLM-drafted
arms too, copy this case's own `protocols/v1.refn` there **only if** the
drafted protocol kept the same message labels (`FundEscrow`,
`ReleasePayment`) — otherwise the guards will look up labels that don't
exist and silently be a no-op. If you skip this, `spec_llmvalid` /
`min_llmvalid` still run correctly; they just inherit an empty refinement
set (documented default behaviour, see `build_spec_instructions`
docstring in `experiments/baselines/instructions.py:260-262`).

Both scripts above are one-time per case, independent of the model matrix
in Section 4 — the deployment you have set in `.env` while running them
only affects which model *authors* the draft, not which model the
benchmark later measures.

## 3. The two arms

Both commands use `--arms`, a real, existing flag
(`experiments/scripts/case_runner.py:629-644`) that restricts a run to a
comma-separated subset of the registered scenario keys in
`experiments/baselines/registry.py`.

**Unchecked arm — expected: deadlock (0/N trials complete):**

```bash
cd experiments
python scripts/case_runner.py agenticpay_settlement 6 --arms unchecked_skills
```

`unchecked_skills` (`registry.py:184-190`) gives each agent only its own
hand-written skill file from `unchecked_skills/<Role>.md` — no protocol —
and monitors the resulting trace against the case's canonical
`protocols/v1.scr`. The Buyer/Seller pair's rules form the circular wait
described in this directory's `README.md`; expect `events_unchecked_skills.jsonl`
to show `WAIT` on every turn and `summary.json`'s
`scenarios.unchecked_skills.succeeded` to be `0`.

**STJP arm(s) — expected: complete (N/N trials):**

```bash
cd experiments
python scripts/case_runner.py agenticpay_settlement 6 --arms spec_llmvalid,min_llmvalid
```

`spec_llmvalid` gives each agent the full projected local type (verbose
markdown); `min_llmvalid` gives the terse SEND/RECV-per-state table. Both
project from `protocols/llm_drafts/valid/v1.scr` (Section 2) and are
monitored against that same file, so this is an apples-to-apples
comparison of "checked contract" vs "no contract," exactly the
`trade_deadlock` pattern in `docs/results/RESULT_1_DEADLOCK.md`.

You can also combine both commands into one invocation — Foundry-stack
arms run in parallel within a single `case_runner.py` call ("WAVE 1" in
`case_runner.py:567-578`):

```bash
cd experiments
python scripts/case_runner.py agenticpay_settlement 6 \
  --arms unchecked_skills,spec_llmvalid,min_llmvalid
```

`6` is the trial count `trade_deadlock` used for `RESULT_1_DEADLOCK.md`;
raise it for tighter confidence intervals, at proportional token cost.

## 4. Model-matrix sweep — mechanism and how to run it

**Existing mechanism, not new:** `experiments/baselines/foundry_runner.py:45`
reads the deployment name **once, at module import time**:

```python
DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
```

That single env var is what every `unchecked_skills` / `spec_llmvalid` /
`min_llmvalid` agent gets created/updated with
(`foundry_runner.py:151-199`, the `model=DEPLOYMENT` arguments). Because it
is read once at import, **one `case_runner.py` process only ever exercises
one deployment** — sweeping the matrix means invoking `case_runner.py` as
a separate process per deployment name, with `AZURE_OPENAI_DEPLOYMENT` set
differently each time. There is no existing flag or harness feature that
loops this internally, so a thin wrapper script is genuinely needed for
the loop itself (not for any new run logic — it only shells the existing
`case_runner.py` invocation from Section 3, once per name).

### `run_foundry_matrix.sh`

Added alongside this file. Usage:

```bash
cd experiments/cases/agenticpay_settlement
./run_foundry_matrix.sh opus-4.7 opus-4.6 sonnet-5 sonnet-4.6 haiku-4.5
```

Pass your **actual Foundry deployment names** as positional arguments (the
five example names above are placeholders — substitute the names you gave
your deployments in Section 1, step 3). If you call it with no arguments it
defaults to that same example list, purely so the script is runnable
as-written for a dry read; it still requires real deployments to succeed.

Environment overrides:

| var | default | meaning |
|---|---|---|
| `N_TRIALS` | `6` | trials per arm per deployment |
| `ARMS` | `unchecked_skills,spec_llmvalid,min_llmvalid` | which arms to run per deployment |

What it does, per deployment name:
1. `export AZURE_OPENAI_DEPLOYMENT=<name>`
2. Runs the Section 3 combined command as its own process (so the env var
   from step 1 is what that process's `foundry_runner.py` import sees).
3. Reads `experiments/cases/agenticpay_settlement/LATEST` — a file
   `case_runner.py` itself writes on every run
   (`case_runner.py:540`, `(case.case_dir / "LATEST").write_text(run_dir.name, ...)`)
   — to find the run directory that invocation just created.
4. Writes a `deployment.txt` marker (just the deployment name) into that
   run directory, and appends a `deployment,run_dir,started_at_utc` row to
   `experiments/cases/agenticpay_settlement/runs/model_matrix_index.csv`.

Steps 3-4 are bookkeeping the wrapper does itself — **not** a harness
feature. `summary.json` / `events_<arm>.jsonl` / `summary_eval.json`, as
produced by `case_runner.py`, do not record which deployment produced them
(see Section 5, gap 2). The `deployment.txt` marker and the index CSV are
how this setup makes the per-deployment run directories identifiable
without touching harness internals.

## 5. Where results land, and how to read them

Each `case_runner.py` invocation writes to
`experiments/cases/agenticpay_settlement/runs/<ISO-timestamp>-n<N>-dual/`:

- `events_<arm_key>.jsonl` — one line per protocol event/marker; see
  `experiments/CLAUDE.md` "Reading a trial trace" for the exact schema.
- `summary.json` — Set A (conformance + cost): `success_rate_pct`,
  `avg_tokens_per_trial`, `avg_calls_per_trial`, `avg_seconds_per_trial`,
  `violations`, per scenario key.
- `summary_eval.json` — Set B (goal achievement): `strict_pct` /
  `role_pair_pct` per arm.
- `prompts/<arm_key>/<Role>.system.md` + `index.json` — the exact prompt
  installed on each Foundry agent (for the WITH-arms and
  `unchecked_skills`; see "Persistence policy" in `experiments/CLAUDE.md`).

After a run (or the whole matrix) completes, assemble a
`RESULT_1_DEADLOCK.md`-style table per deployment by reading each
`summary.json`:

| Measure | `unchecked_skills` | `spec_llmvalid` | `min_llmvalid` |
|---|---|---|---|
| Trades completed | `scenarios.unchecked_skills.succeeded` / `n_trials` | `scenarios.spec_llmvalid.succeeded` / `n_trials` | `scenarios.min_llmvalid.succeeded` / `n_trials` |
| Messages ever sent | `scenarios.<key>.events` | | |
| Tokens per trial | `scenarios.<key>.avg_tokens_per_trial` | | |
| Calls per trial | `scenarios.<key>.avg_calls_per_trial` | | |

Expected qualitative outcome (per this case's `README.md`): `unchecked_skills`
at 0/N with zero real progress messages; `spec_llmvalid` and `min_llmvalid`
at N/N, `min_llmvalid` at meaningfully fewer tokens/trial than
`spec_llmvalid` (mirrors `trade_deadlock`'s ~half-cost result in
`docs/results/RESULT_1_DEADLOCK.md` Section 4).

For the full 5-model matrix, repeat this table once per deployment and
compare rows across deployments — that comparison itself is not computed
by any harness script; assemble it by hand or have
`.claude/agents/foundry-benchmark-runner.md` do it (see that file).

## 6. Harness gaps found during this setup (documented, not faked)

1. **No registered scenario projects directly from this case's own
   `protocols/v1.scr`.** `build_spec_instructions` /
   `build_spec_minimal_instructions` in `experiments/baselines/instructions.py`
   both default to `case.protocol_path` (the canonical file) when
   `protocol_path_override` is `None` — but every WITH-arm entry in
   `experiments/baselines/registry.py`'s `SCENARIOS` list is built through
   `_make_foundry_llm_drafted_factory`, which always passes an explicit
   override and fails fast if the `llm_drafts/valid/v1.scr` file is
   missing. There is no registered scenario key that would let you skip
   Section 2 and benchmark directly against the hand-authored
   `protocols/v1.scr`. Section 2's workaround (run
   `draft_llm_protocols.py`, which is very likely to reproduce the same
   escrow-first structure from the same intent) uses the harness exactly
   as it exists today rather than adding a new scenario key. If a direct
   "project from case's own canonical protocol" arm is wanted, that is a
   `registry.py` change out of scope for this author-time setup.
2. **No run artefact records which model deployment produced it.**
   `summary.json`, `summary_eval.json`, and `events_<arm>.jsonl` contain no
   deployment/model field. `run_foundry_matrix.sh`'s `deployment.txt`
   marker and `model_matrix_index.csv` are an external workaround, not a
   harness feature — if the harness itself should tag runs with the active
   `AZURE_OPENAI_DEPLOYMENT`, that is also a `case_runner.py`/`foundry_runner.py`
   change out of scope here.
