# Human audit — §6 judge-calibration gate

A small Streamlit tool so Gina can produce the ~200 human fit/no-fit
judgments the §6 calibration gate needs
(`docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md` §5.2, §6), and see her
judgments feed straight back into the training report.

## Quickstart (5 steps)

**1. Install the one extra dependency** (kept out of `stjp_core`'s own
requirements — this is a standalone labeling UI, not part of the trained
system):

```
pip install -r experiments/seam_bench/judge/human_audit/requirements.txt
```

**2. Build the packet** (already done once and committed — `audit_packet.jsonl`
+ `packet_key.jsonl` in this directory, seed 13, 220 items. Re-run only if
you want a different sample):

```
python -m experiments.seam_bench.judge.human_audit.packet_builder
```

This writes three files here:
- `audit_packet.jsonl` — what you'll see: 220 cards, each `{item_id,
  order_index, intent, protocol_text}`. `protocol_text` is the SAME
  comment-free canonical form the LLM judge panel sees
  (`judge/payloads.py::sanitize_protocol`) — no case names, no file paths,
  no "this one's a mutant" hints anywhere in this file.
- `packet_key.jsonl` — the ground-truth stratum (gold / easy_negative /
  hard_negative / repeat) for each item. **The Streamlit app never opens
  this file.** Don't peek at it before you're done labeling — it exists
  for `analysis.py` to join against afterward.
- `packet_build_stats.json` — composition counts + the hard-negative
  intent-resolution stats (see packet_builder.py's module docstring for
  exactly how intents are resolved from
  `data/samples/calibration_candidates.jsonl`).

**3. Label** (resumable — split across two sittings is fine, that's what
the plan calls for, not a shortcut):

```
streamlit run experiments/seam_bench/judge/human_audit/audit_app.py
```

One card at a time: intent prose on top, syntax-highlighted protocol below,
a progress bar, and three buttons — **Fit** / **No fit** / **Unsure**
(keyboard shortcuts 1/2/3 also work), plus an optional note. Every click
appends one line to `labels.jsonl` (append-only, never rewritten) and
auto-advances. Close the tab whenever you like — restarting the app
re-reads `labels.jsonl` and resumes exactly where you left off. The
sidebar shows only your own progress (count labeled, mean seconds/item) —
nothing about what kind of item is on screen, so you stay blind while you
work.

**4. Run the analysis** (any time — partial or complete):

```
python -m experiments.seam_bench.judge.human_audit.analysis
```

Joins `labels.jsonl` with `packet_key.jsonl` and prints:
- per-stratum agreement (your fit/no-fit vs. the packet's design
  expectation, for gold / easy_negative / hard_negative separately),
- intra-rater consistency on the ~20 repeat items (the §6 "per-seat
  self-consistency ≥ 0.8 on duplicate canaries" check, applied to you),
- the §6 Wilson 95% lower-bound gate over the 200 non-repeat items, with a
  PASS/FAIL line against the 0.80 threshold,
- the full §6 gate checklist, with `N/A (panel-side)` for the two lines
  this tool can't compute alone (AUC, effective independent votes — those
  need actual panel runs).

By default the Wilson-bound gate compares your label against the packet's
*design* `expected_label` (clearly printed as `PLACEHOLDER`) — a stand-in
until the judge panel has real per-item verdicts. Once the panel
(`experiments/seam_bench/judge/aggregate.py`'s `PanelResult`, or the
orchestrator SEAM_TRAINING_EXECUTION_PLAN.md §5 describes — not yet built
at this commit) produces per-item aggregated verdicts, map its
`accept`/`reject` to `fit`/`no_fit`, write that as a JSONL of `{item_id,
verdict}`, and point `analysis.py --panel-verdicts PATH_TO_VERDICTS.jsonl`
at it — the same report becomes the real §6 gate number (mode flips to
`REAL`). This tool's join logic is already structured for that swap; only
the verdicts file needs to exist.

**5. Where this feeds** into the training program:
- The Wilson-bound PASS/FAIL line is one of the five §6 gate conditions
  (`SEAM_TRAINING_EXECUTION_PLAN.md` §6) that decide whether the judge
  panel may reward or gate anything, or stays advisory-only.
- The per-stratum breakdown (gold vs. easy_negative vs. hard_negative
  agreement) is exactly the split §6(i) requires for the circularity fix —
  it separates "the panel agrees with itself" (D2-style strata) from real
  independent signal.
- The intra-rater consistency number calibrates how much noise to expect
  from a single human rater — useful context when interpreting any
  judge-seat vs. human disagreement during calibration-weight tuning
  (§5.3's per-seat calibration curves).

## Files

| file | written by | read by |
|---|---|---|
| `audit_packet.jsonl` | packet_builder.py | audit_app.py, analysis.py (via packet_key join) |
| `packet_key.jsonl` | packet_builder.py | analysis.py ONLY — never audit_app.py |
| `packet_build_stats.json` | packet_builder.py | (informational) |
| `labels.jsonl` | audit_app.py (append-only) | analysis.py |

## Rebuilding with different parameters

```
python -m experiments.seam_bench.judge.human_audit.packet_builder \
    --seed 13 --target 220 --repeats 20 \
    --easy-negatives 23 --hard-negatives 154
```

All defaults are deterministic given `--seed`; re-running with the same
seed reproduces byte-identical `audit_packet.jsonl` / `packet_key.jsonl`
(see `tests/test_packet_builder.py::test_determinism_full_packet`).
Rebuilding **deletes and replaces** `labels.jsonl`'s meaning if the item
set changes — do not rebuild mid-audit with a different seed/target once
you've started labeling, or `labels.jsonl`'s item_ids will stop lining up
with the new packet.
