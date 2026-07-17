# seam_results.tex — how to fill the trainable-seam results template

The trainable-seam section (`\S`ref `sec:seam`) and the E5 translation-fidelity
cells (Table `tab:transfid`) consume **only** macros defined in
`seam_results.tex`. Every macro defaults to a visible `\pending` marker. After
the GPU training runs land, drop each number in by editing **one line** in
`seam_results.tex` — never edit a table in `main.tex`. Then `make` (pdflatex
×2) re-typesets; the table structure never changes, so a compiled cell reads
either a real number or an honest `\pending`.

## Two ways to fill a macro (equivalent)

```latex
% direct:
\renewcommand{\seamSftValOne}{87.3\%}
% or the convenience idiom:
\seamfill{\seamSftValOne}{87.3\%}
```

Include the unit in the value (`\%`, `\$`, `pp` for percentage-point deltas,
etc.) so the tables stay unit-consistent. For a delta, include the sign
(`+8.1\,pp`, `$-0.4$`). For an interval, include it (`$-0.02$ [$-0.09$, 0.05]`).

## Where each number comes from

All harness fields below are emitted by the Seam-Bench eval package
(`experiments/seam_bench/eval/`): `metrics.py` computes the standing metric
block, `report_gen.py` writes the per-(system, split) markdown tables with
value + 95% CI + n. The phase-gate reports referenced live under
`docs/reference/reports/seam/`.

### Group A — E5 translation-fidelity cells (v8 Table `tab:transfid`)

Filled from the **T0 prompt-era** run (`reports/seam/T0_baselines.md`), Sonnet
under the production T+R (draft→validate→repair) loop.

| macro | fills | harness field |
|---|---|---|
| `\seamEfiveFirstDraft` | "First draft passes validator" | `metrics.validity@1` (Sonnet, k=1) |
| `\seamEfiveRepairRounds` | "Repair rounds to validity" | `metrics.repair-rounds` (Sonnet, mean, cap 3) |
| `\seamEfiveGuardCoemit` | "Guard sidecar co-emission" | guard-sidecar co-emission rate over guard-implying intents (T0 JSONL, `gen.guard_emitted` tally) |

### Group B — T0 prompt-era baselines, per API tier (Table `tab:seam-baselines`)

Filled from `reports/seam/T0_baselines.md` / the eval metric block, one column
per model (Haiku / Sonnet / Opus), on `test-syn`.

| macro family | fills | harness field |
|---|---|---|
| `\seamTzeroValOne{Haiku,Sonnet,Opus}` | validity@1 row | `metrics.validity@1` |
| `\seamTzeroValK{Haiku,Sonnet,Opus}` | validity@10 row | `metrics.validity@k` (k=10, best-of-n validator filter) |
| `\seamTzeroRepair{Haiku,Sonnet,Opus}` | repair-rounds row | `metrics.repair-rounds` (mean, cap 3) |
| `\seamTzeroDollar{Haiku,Sonnet,Opus}` | \$-to-accepted row | `metrics.$-to-accepted` (posted per-model prices) |

### Group C — T1 SFT (system S4), Table `tab:seam-trained`

Filled from `reports/seam/T1_sft_report.md`, on `test-syn`.

| macro | fills | harness field |
|---|---|---|
| `\seamSftValOne` | SFT-7B validity@1 | `metrics.validity@1` (S4) |
| `\seamSftBisimOne` | SFT-7B bisim@1 | `metrics.bisim@1` (E5 equivalence to gold, S4) |
| `\seamSftDollar` | SFT-7B \$-to-accepted | `metrics.$-to-accepted` (S4; local-GPU amortized) |

### Group D — T2 GRPO deltas (system S6/S7), Table `tab:seam-trained`

Filled from `reports/seam/T2_grpo_report.md`; each is the **delta vs. the T1
SFT checkpoint** (the pre-registered H4 form — paired bootstrap on shared
`test-syn` items, sign included).

| macro | fills | harness field |
|---|---|---|
| `\seamGrpoValDelta` | Δ validity@1 vs. SFT | paired-bootstrap Δ of `metrics.validity@1` (S6 − S4) |
| `\seamGrpoEquivDelta` | Δ graded-equivalence@1 | paired-bootstrap Δ of graded-equivalence proxy (S6 − S4) |
| `\seamGrpoRepairDelta` | Δ repair-rounds | Δ of `metrics.repair-rounds` (S6 − S4; H4 requires strictly down) |

### Group E — Judge-panel calibration gate (§6 of the execution plan)

Filled from `reports/seam/W7_calibration.md` (the panel calibration run).

| macro | fills | harness field |
|---|---|---|
| `\seamPanelAUC` | gold-vs-mutant AUC (non-D2 strata) | `judge/aggregate` calibration-set AUC, non-D2 strata only |
| `\seamPanelHumanLB` | human-agreement Wilson 95% LB (n≥200) | Wilson lower bound of ensemble human-agreement, n≥200 |
| `\seamPanelSwapReject` | swapped-pair rejection | `canaries` swapped-pair rejection rate |
| `\seamPanelEffVotes` | effective independent votes | `canaries.effective_independent_votes` |

### Group F — Transfer (H6), Table `tab:seam-trained`

Filled from the phase-gate report's transfer-gap table.

| macro | fills | harness field |
|---|---|---|
| `\seamTransferGap` | Δ-of-gaps point estimate [95% CI] | unpaired bootstrap on (trained gap − baseline gap) = `metrics.transfer-gap` difference, with CI |

## Discipline

- A macro left at `\pending` compiles to a visible **pending** cell — that is
  the intended honest state until the number exists. Do not delete a row to
  hide a pending cell; the pending-cell honesty is a feature (it matches the
  paper's E3-vendor and E5 discipline).
- Fill from the committed JSONL / `report_gen.py` output, not from memory; the
  report generator's numbers reproduce bit-for-bit from the run directory.
- After filling, re-run the begin/end + brace sanity check (see
  `CHANGELOG_v9.md`) and rebuild with `make`.
