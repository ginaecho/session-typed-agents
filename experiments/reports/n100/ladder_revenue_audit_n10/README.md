# revenue_audit ladder — the SAFETY axis (no Foundry, cheap subagents)

See `../LADDER_NOFOUNDRY.md` for the combined write-up. Headline: the observe
arms (A: intent, B: global text) file prematurely — 10/10 disasters, 0% clean
completion — while the projected-contract / gate / scheduler arms are 100% safe.
Disasters are judged causally (round-aware); the fix that surfaced them is
`_causal_sequence_disasters` in `experiments/subagent_trials/engine_ladder.py`.
