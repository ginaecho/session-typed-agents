# experiments/apps/live_demo

Flask UI for the STJP arm-matrix benchmark (15 arms — see
`../../baselines/README.md`). Walks an audience through:

1. **Pick a case** (or edit its intent prose).
2. **Draft a global type** — LLM architect drafts a Scribble protocol N times,
   Scribble validates each; the first valid and first unsafe drafts are kept
   and shown side by side with the canonical reference.
3. **Run the arms** — `case_runner` runs in a subprocess; each chosen arm's
   `events_<arm>.jsonl` is tailed and streamed into a per-arm panel via SSE.
4. **Drill in** — open any role's full pre-truncation system prompt straight
   from `runs/<ts>/prompts/<arm>/<Role>.system.md`. Summary tables (Set A
   conformance + Set B goal achievement) render when the run completes.

## Run

```powershell
# from repo root
python experiments/apps/live_demo/app.py
# then visit http://127.0.0.1:5005/
```

Requires the same env as `case_runner.py`: `az login` (Microsoft tenant,
not Siemens), `stjp_core/.env` populated with `AZURE_AI_PROJECT_ENDPOINT`,
`AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_ENDPOINT`.

## Layout

```
live_demo/
  app.py                  Flask routes (cases / draft / run / SSE / prompts)
  runner.py               Background job manager: drafting + subprocess
                          tailing of run_subset.py
  templates/index.html    Single-page UI
  static/
    style.css             Dark theme matched to stjp_comparison.html
    app.js                Client: SSE consumer, panel updates, modal
```

## How it talks to the benchmark

- **Drafting** invokes `ArchitectAgent` + `ScribbleValidator` in a thread,
  writes to `experiments/cases/<case>/protocols/llm_drafts/{valid,unsafe}/v1.scr`
  — exactly what `experiments/scripts/draft_llm_protocols.py` writes from
  the CLI.
- **Run** spawns `python experiments/scripts/run_subset.py <case> <n> <arms…>`
  as a subprocess. The runner waits for the new `runs/<ts>-n<N>-dual/` dir to
  appear, then tails `events_<arm>.jsonl` for each chosen arm on its own
  thread. Every JSONL line becomes one SSE frame.
- **Prompt drill-in** reads `runs/<ts>/prompts/<arm>/<Role>.system.md`
  written by the persistence layer in `experiments/scripts/case_runner.py`.

Nothing about the benchmark itself changes; this is a thin live UI layer.
