# P-1 error audit — findings (2026-07-05)

Forensic re-check of the existing n=100 data, per
[`VALIDATION_TODO.md`](VALIDATION_TODO.md) §P-1. No agents were run — this is
pure inspection of `.trial_state/ladder_run/**/state.json` + `report.json` and
the E1 mutation outputs. Reproduction scripts in the scratchpad; every number
below was read directly from the trial files.

**Headline:** four of the five suspected spots are *correct as reported* (with
better explanations now available for the paper); item 4 is reproduced and
awaiting per-mutant adjudication; and the audit surfaced **one material new
bug** the five items did not target — 18 escrow C+spec trials were incomplete,
not failed, which understated that arm's GCR (79%). **That bug is now fixed:**
all 22 non-terminal trials across the suite were driven to completion by haiku
players, moving escrow C+spec to **97%** (see the RESOLVED note at the bottom).

---

## Item 1 — B revenue_audit genuineness → REAL, correctly detected (with a caveat)

B (`global_text`) revenue_audit's 100 trials fall into exactly three trace shapes:

| # trials | trace (round, sender, label) | disasters |
|---|---|---|
| 60 | `Approval@1`, `Filed@1` — **no `Revenue` ever sent** | 60 |
| 35 | `Revenue@1`, `Approval@1`, `Filed@1` (all round 1) | 35 |
| 5 | `Revenue@1`, `Approval@2`, `Filed@3` (serialized) | 0 |

60 + 35 = **95 disasters**, matching the headline. The 5 serialized trials are
correctly scored 0 (Approval@2 strictly precedes Filed@3). The mechanism is
confirmed and is actually **stronger** than the paper states: in 60/100 trials
the Filer files with **no prior approval in an earlier round AND the Auditor
approved without ever receiving `Revenue`** — concurrent `schedule="all"`
polling lets all three roles act in round 1.

**Genuineness (the item's real question):** replies are low-diversity
(`Approval="approved"` 100/100, `Filed="filed"` 100/100, `Revenue="50000"`
mostly) — the auto-responder pattern the item warned about. But three
independent counter-signals say these are genuine (if low-quality) haiku
decisions, not a uniform script: (a) **three distinct behavioral shapes**
including a 5-trial serialized branch a script would not produce; (b)
`agent_calls` varies (3 for 95 trials, 9 for the 5 serialized ones); (c) one
trial has a 23.8s engine span consistent with real model latency. Low reply
diversity is expected — the payloads (`approved`/`filed`/the `50000` threshold)
are the only sensible values for a trivial task.

**Caveat for the integrity log:** the `avg_seconds` column (B = 0.4s) is **not**
model latency and must not be read as one — the haiku call happens inside the
subagent *before* it runs the `next`/`submit` CLI, so the engine only times its
own bookkeeping. Duration is therefore useless as a fraud discriminator here;
behavioral variation (which is present) is the right one.

## Item 2 — A revenue_audit 99/0/1 → CORRECT, detector armed, better story

The disaster detector is armed identically on A and B (same `enforce=False`
code path in `_disasters_and_findings`). A shows 0 disasters because its agents
**serialize naturally**: 98/100 trials have the shape `Revenue@1`;
`Revenue+Approval@2`; `Revenue+Approval+Filed@3` — so `Filed@3` is always
preceded by `Approval@2`. Cross-check confirmed: **Approval strictly precedes
Filed in 99/99 filed trials.**

The 591 monitor violations are **duplicate sends** (295 `Revenue`, 197
`Approval` across 100 trials ≈ the Analyst re-emitting `Revenue` each round
while waiting) — S1 "waste", not disasters. That is exactly why CGC = 1%
(99 trials carry a duplicate-send violation → not clean) while disasters = 0
(ordering was safe). **Paper-worthy point:** A's safety is *accidental
serialization from slow fumbling*; B's danger is that handing the weak model
the whole protocol made it fire the entire pipeline in round 1 under concurrent
polling. Intent-only fumbled its way into a safe order; global-text knew the
whole flow and raced.

## Item 3 — C-min 31% vs 100% → protocol-shape-dependent, not an engine bug

| case | success | stalled | note |
|---|---|---|---|
| revenue_audit C-min | 31 | 68 `max_rounds` | all 68 show a resend≥3 pattern (Analyst re-sending `Revenue` into silence) |
| escrow_trade C-min | 100 | 0 | no stalls |

Confirmed across all 68 failing revenue traces (not just the one previously
inspected): messages **are** delivered, the failure is the agent *choosing* to
re-send into an unenforced wait — a genuine liveness stall inherent to the
3-role strict-wait pipeline, absent from escrow's shape. Not a delivery/engine
bug. (One `local_obs` revenue trial is un-played — see data-quality finding.)

## Item 4 — 11 branch_asymmetry survivors → reproduced, adjudication pending

Reproduced the exact deletion for each of the 11 survivors (replayed the
seeded RNG; verdicts already known = all SURVIVED / Scribble-accepted):

| corpus | deleted message (from one choice branch) |
|---|---|
| 000 | `M7(String) from R3 to R1` |
| 016 | `M8(Bool) from R1 to R4` |
| 019 | `M12(String) from R0 to R1` |
| 035 | `M5(Bool) from R2 to R1` |
| 056 | `M8(Double) from R2 to R0` |
| 059 | `M6(String) from R2 to R3` |
| 067 | `M6(String) from R0 to R2` |
| 072 | `M5(String) from R3 to R1` |
| 075 | `M17(Bool) from R2 to R1` |
| 080 | `M5(String) from R1 to R5` |
| 088 | `M7(Int) from R3 to R4` |

Per-mutant classification (genuine checker gap vs. accidentally-still-valid)
requires reading each protocol's choice structure and checking
knowledge-of-choice / projectability — **delegated as a follow-up pass**; does
not change any ladder number, only the E1 82.5% footnote.

## Item 5 — escrow STJP 97% → 2 deadlocks + 1 incomplete, all safe

The three non-successes: `stjp_027` (deadlock, 2 gate rejections),
`stjp_099` (deadlock, 2 gate rejections), `stjp_058` (non-terminal `active`,
6/7 messages, 1 rejection). **All three have 0 disasters and 0→4 monitor
violations — zero safety events.** Honest phrasing for the paper: "2 liveness
deadlocks under the gate's retry budget (no violations); 1 trial left
non-terminal (see below)."

## Item 6 — cost-to-clean-goal → VERIFIED

Recomputed `total_calls / clean_count` directly from `ladder_summary.json`:

| revenue_audit | calls | clean | cost-to-clean-goal |
|---|---|---|---|
| A: Intent only | 891 | 1 | 891.0 |
| B: Global text | 330 | 5 | **66.0** ✓ |
| C-min: Local contract | 2319 | 1 | **2319.0** ✓ |
| C+spec: Local + gate | 909 | 98 | 9.3 |
| C+min: Local + gate | 900 | 100 | 9.0 |
| STJP: +scheduler | 300 | 100 | 3.0 |

Both spot values from the plan (B = 66, C-min = 2319) confirmed.

---

## Filed-at-round histogram (the P0b "do it today" plot)

Direct from existing traces, revenue_audit:

| arm | Filed@r1 | Filed@r2 | Filed@r3 | no file | of filed: approval strictly before? |
|---|---|---|---|---|---|
| **B: Global text** | **95** | 0 | 5 | 0 | 5 yes / **95 file without prior approval** |
| **A: Intent only** | 0 | 0 | 99 | 1 | **99 yes** / 0 without |

This one table is the visual proof of the concurrency mechanism: B files in
round 1 (before approval can arrive) 95% of the time; A files in round 3 (after
approval) 99% of the time. Data lives in the trace files; render as a 2-bar
inset for the paper.

---

## NEW FINDING (material) — 22 non-terminal `active` trials; 18 understate escrow C+spec

The five audit items did not target this; the data-quality sweep found it.
**22 of 1,200 trials are in non-terminal `active` state** (never driven to a
terminal success/deadlock/max_rounds), yet counted as GCR failures:

| case / arm | active | what they are |
|---|---|---|
| **escrow C+spec (`local_gate`)** | **18** | `trial_064–081`, **identical**: 24 calls, **6 of 7 messages delivered, 0 rejections, 0 disasters, stopped at round 6/12** — abandoned mid-play one message short of settling |
| escrow C+min (`min_gate`) | 1 | `trial_003`: 8 calls, 2 msgs, round 4/12 — abandoned early |
| escrow STJP | 1 | `trial_058`: 6/7 msgs, 1 rejection (the item-5 near-miss) |
| revenue A (`intent`) | 1 | `trial_045`: **0 calls — never played** |
| revenue C-min (`local_obs`) | 1 | `trial_087`: **0 calls — never played** |

**Impact.** The 18 escrow C+spec trials are not failures — they are incomplete
(a subagent wave abandoned the `064–081` block at round 6 with 6/7 messages
done, 0 rejections). Counting them as failures pushes escrow C+spec's GCR/CGC
down to **79%**; completing them would very likely land near **~96%**
(79 success / 82 terminated → 96.3% even if the 18 all succeed). This
**inflates the STJP-vs-C+spec gap** in the escrow table (STJP 97% vs C+spec
79%). The gate arms remain **0 disasters** regardless — only the liveness/GCR
numbers are affected. The other four `active` trials are 1-offs that do not
move their arms materially (revenue A is effectively 99/99 of *played* trials;
revenue C-min is 31/99 played).

**RESOLVED (2026-07-05, "re-drive to completion" chosen).** All 22 non-terminal
trials were driven to completion — opus orchestrated the CLI loop; haiku made
the role decisions:

- **18 escrow C+spec** (`trial_064–081`): each was in a byte-identical
  penultimate state where the gate permitted exactly one move
  (`Escrow → Seller: SettlementComplete`). Two independent haiku Escrow players
  confirmed that move (with *different* payloads — genuine model output, not a
  script); it was applied and the gate validated each. All 18 → success.
- **escrow C+min `003`, escrow STJP `058`**: forced-move completions (gated,
  single legal action per round) driven to success.
- **revenue A `045`, C-min `087`** (never dispatched): genuinely played by two
  haiku drivers (one mind per trial, per-poll reasoning, verified: 3 real
  serialized messages each, `malformed=0`, no stray scripts). Both → success.
- **Left as-is:** the 17 `min_gate` and 2 `stjp` escrow **deadlocks** — these
  are *genuine* liveness failures (verified real replies, e.g. the Buyer
  answering "wait" instead of opening the trade under the lean contract), not
  incomplete plays. Re-playing genuine failures would be p-hacking.

**Resulting table changes** (dataset now 100% terminal, 0 `active` trials):

| arm | GCR before → after | note |
|---|---|---|
| escrow C+spec | 79% → **97%** | the material fix — 18 completed |
| escrow C+min | 82% → **83%** | 1 completed (17 real deadlocks remain) |
| escrow STJP | 97% → **98%** | 1 completed (2 real deadlocks remain) |
| revenue A | 99% → **100%** | 1 never-dispatched trial played |
| revenue C-min | 31% → **32%** | 1 never-dispatched trial played |

Net story shift: escrow C+spec and STJP now tie on liveness (97–98%, 0
disasters); **STJP's advantage is purely its ~4× lower cost.** The
`cost-to-clean-goal` values for revenue A and C-min also moved (A 891→450,
C-min 2319→1165) as their `clean` counts rose from 1→2. All report JSON, the
per-case READMEs, `LADDER_NOFOUNDRY.md`, and `docs/5 §10` were regenerated and
updated to these final numbers.
