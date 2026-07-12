# ss2026_n100_sonnet — real-skills safety benchmark, n=100, Sonnet roles

Committed evidence for the n=100 run described in
[`docs/6_RUN_REPORTS_EXPLAINED.md`](../../../../docs/6_RUN_REPORTS_EXPLAINED.md)
§2 and [`docs/results/RESULT_8_SKILL_SAFETY.md`](../../../../docs/results/RESULT_8_SKILL_SAFETY.md).

- **Cases:** the four `experiments/cases/skills_safety/*` cases (real,
  MIT-licensed public skills: openai-agents / langgraph / autogen / crewAI).
- **Arms:** `unchecked` (original skills, compiler-rejected), `bare` (revised
  skills with the projected local contract as prompt text, no enforcement),
  `stjp` (revised skills + gate + EFSM scheduler).
- **n:** 100 trials per (case, arm) = 1,200 trials.
- **Roles:** each played by a Claude **Sonnet** subagent, deciding in strict
  per-role isolation (one subagent sees only its own role's view — skill/
  contract + own inbox — never other roles' prompts or the global protocol).
- **Compiler backend:** the coinductive **nuscr** fork
  (`STJP_COMPILER_BACKEND=nuscr`, native binary), verified to produce EFSMs
  identical to Scribble's for all four protocols.

## Files

- `AGGREGATE.json` — arm-level rollup with Wilson 95% CIs + per-case grid.
- `<case>_<arm>.report.json` — per-run metrics (GCR, CGC, disasters, token
  estimates, agent calls, monitor/gate verdicts).

Full per-trial traces are committed under `traces/` — one `state.json` per
(case, arm) (every trial's ordered message log + terminal status) plus the
`replies_round*.json` decision ledger and the `.scr` protocol. `traces/VERIFY.md`
shows how to re-derive every metric straight from `state.json` with
`engine.py report` (no network, no round-prompt files needed). The bulky
per-round prompt files and the transient scratch buffers were deliberately
left out — see `traces/VERIFY.md` for exactly what and why.

## Headline (arm-level, n=400 each)

**GCR** = goal-completion rate (% of trials that reached the goal). **CGC** =
critical-goal completion (reached the goal AND had zero critical-safety
violations).

| arm | GCR (Wilson 95%) | CGC | Disasters | Cost-to-goal | Agent calls/trial |
|---|---|---|---|---|---|
| unchecked | 75% [70.5–79.0] | 50% | 100 | 3,941 | 10.8 |
| bare | 75% [70.5–79.0] | 50% | 200 | 4,894 | 14.5 |
| **stjp** | **100% [99.0–100]** | **100%** | **0** | **1,674** | **4.0** |

STJP is the only arm at 100%/100%/0-disasters and is 2.4–2.9× cheaper. See the
docs for the per-case breakdown and the honest model-dependence / harness
caveats.
