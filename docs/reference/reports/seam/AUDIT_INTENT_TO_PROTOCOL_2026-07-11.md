# Audit — user intent -> global protocol implementation, verification evidence (2026-07-11)

**Purpose.** This document lets anyone independently verify that the
"natural-language intent -> Scribble-validated global protocol" (S1->S2 seam)
implementation described in `SEAM_AUTOTRAINING_PLAN.md` and
`SEAM_TRAINING_EXECUTION_PLAN.md` is actually present in this branch and
actually works, rather than trusting the worker reports' prose. Every command
below was re-run in a fresh worktree by an independent auditor (not the
implementing workers) against the real Scribble/nuscr toolchain, and the
outputs recorded verbatim. Where a number in this document restates a worker
report's claim (e.g. D1 family counts, D3 yield), that is called out as
"reported, not re-run in full" — the bounded builds take 20+ minutes and are
not part of this audit's fast-verification pass; everything markable PASS/FAIL
by test suite or corpus sweep was re-executed live.

**Branch audited:** `gc/user_intent_global_protocol_training`
**Commit SHA (this worktree's `HEAD`, detached):**

```
958720f1e9e1cec4296c6353196630226dde7976
```

**Environment:** isolated git worktree, real toolchain wired via
`bash tools/setup_scribble_cloud.sh`:

```
scribble-java smoke: gold PASS, corrupt REJECTED  [real toolchain OK]
nuscr smoke: binary runs  [OK]
export STJP_NUSCR_BIN=/workspace/bin/nuscr   # for the opt-in nuscr backend
```

---

## 1. Component inventory

| component | path(s) | purpose | test count | evidence report |
|---|---|---|---|---|
| GBNF/Lark grammar + guided-decoding adapter | `stjp_core/compiler/scribble_grammar.lark`, `stjp_core/compiler/gcd_adapter.py`; tests `stjp_core/tests/test_scribble_grammar.py` | Formal Lark grammar for the Scribble surface this repo emits/accepts; hand-maintained GBNF mirror for vLLM/xgrammar guided decoding at sample time | 23 passed, 1 skipped (xgrammar not installed, no GPU) | `docs/reference/reports/seam/W2_grammar_gcd.md` |
| Eval harness | `experiments/seam_bench/eval/` (`schema.py`, `metrics.py`, `validity.py`, `_worker.py`, `report_gen.py`, `smoke.py`, `test_access_log.py`) | JSONL schema, real-toolchain validity/bisim adapters, the §7 metric block (validity@k, semantic-validity, bisim, repair-rounds, tokens/$-to-accepted, transfer gap), report generator, opened-test-log gate discipline | 86 passed | `docs/reference/reports/seam/W1_eval_harness.md` |
| Data builders D1/D2/D3 + signature + splitter | `experiments/seam_bench/data/` (`signature.py`, `d1_expand.py`, `d2_backtranslate.py`, `d3_repair.py`, `splitter.py`, `leakage_check.py`, `common.py`) | EFSM-equivalence-class signature (dedupe key), D1 sweep/compose/crossover expansion, D2 back-translation (intent generation), D3 repair-tuple mining from mutation operators, family-stratified 80/10/10 splitter, leakage checker | 22 passed | `docs/reference/reports/seam/W3_data_builders.md` |
| Faithfulness judge panel | `experiments/seam_bench/judge/` (`payloads.py`, `seats.py`, `classes.py`, `aggregate.py`, `canaries.py`, `cache.py`, `run_panel.py`) | 5-layer isolated judge panel (process isolation, payload sanitization, view decorrelation J-fwd/J-back/J-probe, structured verdicts + evidence verification, collusion/degeneration canaries), geometric-median aggregation, escalation gate | 62 passed | `docs/reference/reports/seam/W6_judge_panel.md` + `docs/reference/reports/seam/PANEL_SMOKE_2026-07-11.md` (live 14-seat run) |
| Real-skills miner (D5) | `experiments/seam_bench/mining/` (`harvest.py`, `ledger.py`, `intent_extract.py`, `team_builder.py`, `formalize.py`, `run_mining.py`, `schema.py`) | Harvests real GitHub agent/skill artifacts, license/provenance ledger, team-builder heuristics, compaction -> real-Scribble-validated `DatasetRecord` funnel for `test-real` | 37 passed | `docs/reference/reports/seam/W8_miner.md` |
| Real toolchain | `tools/setup_scribble_cloud.sh`; `docs/reference/NUSCR_CLOUD_INSTALL.md` | Wires the real `scribble-java` CLI + optional `nuscr` coinductive backend into the worktree; gold-pass/corrupt-reject self-test on every invocation | smoke test PASS (see above) | n/a (setup script, not a test suite) |
| Plans | `docs/reference/SEAM_AUTOTRAINING_PLAN.md`, `docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md` (incl. §9 worker task cards, §11 scout & red-team adjudication log) | Strategy proposal + executable training plan: stacks, judge-isolation mechanics, preregistered go/no-go gates, dispatch order, and the v2 adjudication of every red-team finding | n/a (design docs) | n/a |

Corpus fixture used by the sweep below: `experiments/cases/_corpus/*.scr`
(30 files, confirmed by directory listing).

---

## 2. Suite runs — exact commands + verbatim tails

All commands run from the worktree root
(`/home/user/session-typed-agents/.claude/worktrees/agent-a64ef4630a9fc4adb`)
after `bash tools/setup_scribble_cloud.sh`.

### 2.1 Grammar suite

```
$ python -m pytest stjp_core/tests/test_scribble_grammar.py -q
.......................s                                                 [100%]
23 passed, 1 skipped in 0.84s
```

Result: **PASS — 23/23 (1 skip: xgrammar-compile check, dependency not
installed in this environment — expected, matches W2's own report).**

### 2.2 Eval harness suite

```
$ python -m pytest experiments/seam_bench/eval/tests/ -q
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 21.84s
```

Result: **PASS — 86/86**, matching W1's reported count exactly.

### 2.3 Data builders suite

```
$ python -m pytest experiments/seam_bench/data/tests/ -q
......................                                                   [100%]
22 passed in 210.11s (0:03:30)
```

Result: **PASS — 22/22**, matching W3's reported count. (This suite hits the
real validator per-test, hence the ~3.5 min wall time; W3's report recorded
125.64s on its own hardware — the difference is expected sandbox-to-sandbox
JVM-contention variance, not a discrepancy in test count or outcome.)

### 2.4 Judge panel suite

```
$ python -m pytest experiments/seam_bench/judge/tests/ -q
..............................................................           [100%]
62 passed in 5.74s
```

Result: **PASS — 62/62**, matching W6's reported count exactly.

### 2.5 Mining suite

```
$ python -m pytest experiments/seam_bench/mining/tests/ -q
.....................................                                    [100%]
37 passed in 1.82s
```

Result: **PASS — 37/37**, matching W8's reported count exactly.

### 2.6 Package import check

```
$ python -c "import experiments.seam_bench.eval.metrics, experiments.seam_bench.judge.aggregate, experiments.seam_bench.data.signature, experiments.seam_bench.mining.harvest; print('package imports OK')"
package imports OK
```

Result: **PASS** — all four cross-worker packages import cleanly from a
fresh interpreter with no side effects (no LLM/API calls at import time).

### 2.7 Real-Scribble corpus sweep + negative control

Ad hoc script driving `stjp_core.compiler.validator.ScribbleValidator`
directly against all 30 `experiments/cases/_corpus/*.scr` files, plus one
corrupted negative control (final closing brace of `corpus_000.scr` deleted,
producing an unbalanced-brace protocol that must be rejected):

```
$ python sweep_corpus.py
found 30 corpus files under .../experiments/cases/_corpus
  PASS  corpus_000.scr
  PASS  corpus_001.scr
  PASS  corpus_002.scr
  PASS  corpus_003.scr
  PASS  corpus_004.scr
  PASS  corpus_005.scr
  PASS  corpus_006.scr
  PASS  corpus_007.scr
  PASS  corpus_008.scr
  PASS  corpus_009.scr
  PASS  corpus_010.scr
  PASS  corpus_011.scr
  PASS  corpus_012.scr
  PASS  corpus_013.scr
  PASS  corpus_014.scr
  PASS  corpus_015.scr
  PASS  corpus_016.scr
  PASS  corpus_017.scr
  PASS  corpus_018.scr
  PASS  corpus_019.scr
  PASS  corpus_020.scr
  PASS  corpus_021.scr
  PASS  corpus_022.scr
  PASS  corpus_023.scr
  PASS  corpus_024.scr
  PASS  corpus_025.scr
  PASS  corpus_026.scr
  PASS  corpus_027.scr
  PASS  corpus_028.scr
  PASS  corpus_029.scr

corpus result: 30/30 passed

negative control (corrupt_000, missing closing brace): REJECTED (correct)
  validator_msg: line 26:0 mismatched input '<EOF>' expecting '}'

SUMMARY: corpus 30/30 PASS; negative control REJECTED
```

(The one-line `validator_msg` above has the JVM's
`Picked up JAVA_TOOL_OPTIONS: ...` proxy-config banner stripped for
readability, consistent with W1's documented convention that the banner
never affects the pass/fail verdict — pass rule is returncode 0 AND empty
stdout, which the harness's own `validate()` adapter implements identically.)

Result: **PASS — 30/30 corpus protocols validated; negative control correctly
rejected with a genuine Scribble parser error.**

---

## 3. Measured-results summary (pulled from the underlying reports; not
   re-run in full by this audit — the full builds are 20 min to several
   hours)

| measurement | value | source |
|---|---|---|
| Corpus round-trip (Lark grammar) | 100% (113/113 non-skip; 5 legitimately-rejected malformed LLM drafts skip-listed) | W2 |
| Grammar sampled-string parse | 1000/1000 samples parse under both Lark grammar and `protocol_parser` | W2 |
| Signature/EFSM-equivalence agreement | 200/200 = 100.0% vs the repo's own E5 `protocols_equivalent` checker (+ 20/20 spot-check vs the unoptimized checker) | W3 |
| D1 expansion (bounded 22.5 min run) | 671 unique valid families kept from ~810 candidates (saturation curve still near-linear; ~5,000 families projected reachable in 3-4h; recursion axis saturates at ~9 families with current generators) | W3 |
| D3 repair tuples (bounded 10.6 min run) | 860 repair records + 1,746 calibration candidates from 3,200 mutation attempts over 802 golds (0.27 repairs/attempt yield; ~4h projected for 20k target) | W3 |
| D4 splitter + leakage check | 751 families -> train 599 / dev 76 / test-syn 76 (79.8/10.1/10.1%); leakage checker GREEN (0 offending families, 0 offending seeds) | W3 |
| Judge panel test suite | 62 tests (13 payload-sanitization incl. 7 adversarial-comment cases, 4 cache, 12 aggregate, 4 seats, 17 classes incl. real-toolchain worked example, 9 canaries, 1 run_panel end-to-end) | W6 |
| Judge panel live run (PANEL_SMOKE) | 14 stateless subagent seats, 3 gold (intent,G) pairs + 1 swapped-pair canary; canary correctly rejected at no(0.99)/no(0.99) both fwd seats; `trade_deadlock` case escalated (fwd seats yes 0.88/0.82, J-back blind reconstruction scored 0.25 — protocol implements a *repair* of the intent's deadlock, not the intent as literally stated — confirmation-bias catch working live) | PANEL_SMOKE_2026-07-11.md |
| Miner (D5) funnel | 609 harvested artifacts -> 605 licensed -> 594 intent-recovered -> 53 teamed -> 13 teams formed -> 0 survive `--no-llm` compaction (structural: no harvested source authors STJP-format fenced `localtype` blocks; the downstream pipeline half is independently proven sound via a synthetic fixture that DOES survive end-to-end against real Scribble) | W8 |

All of the above are the workers' own measured, reported numbers; this audit
verified them by reading the reports and cross-checking the reports' own
test-count claims against a live re-run (§2), not by re-executing the
multi-hour bounded builds. Anyone wanting to re-verify the D1/D3/mining
numbers themselves should use the reproduction commands in §4.

---

## 4. What is NOT yet done (explicitly out of scope / blocked, per the plan
   and the workers' own reports)

- **GPU-dependent training runs are not done.** W9 (T1 SFT run), W10 (T2
  GRPO run + divergence guard), W12 (persistent validator throughput
  service), and W13 (GRPO structured-outputs plumbing smoke) all require a
  GPU box this audit's sandbox does not have; per `SEAM_TRAINING_EXECUTION_PLAN.md`
  §9 they are listed but not marked done.
- **No real T0 drafting has been run.** W4 (T0 baselines + E5 cell fill) is
  not evidenced in this branch's reports; the eval harness (W1) and D1/D3
  data (W3) exist to feed it, but the baseline LLM-drafting sweep itself has
  not been executed.
- **Full-size D1/D3 builds were not run to their targets.** D1 reached 671/5,000
  families and D3 reached 860/20,000 repair tuples in time-boxed runs (see
  §3); both report exact continuation commands and projected wall-clock to
  hit the task-card targets, but neither full build has actually been run.
- **The recursion axis of D1 is a known, unresolved gap.** The `retry` shape
  is the only recursion-bearing generator in the current operator set and
  saturates at ~9 families; growing it needs either a randomized recursive
  generator or a nuscr-coinductive-backed shape generator — flagged by W3,
  not yet built.
- **D2 back-translation has not been run against a real Anthropic API key.**
  No `ANTHROPIC_API_KEY` exists in any of the worker environments to date; D2
  was validated end-to-end only against the deterministic `MockIntentClient`
  ($0 spent, template-shaped mock output explicitly not training-grade).
- **The judge panel's real-API-key smoke (`run_panel.py` against
  `claude.messages.create`) has not been run** — W6 confirmed only that the
  no-key skip path works cleanly; the one live faithfulness run that DID
  happen (PANEL_SMOKE) used session subagents as panel seats, not the
  API-key transport, which the plan itself notes is fine for in-session
  judging but is required for the headless T2/T3 GPU reward path.
- **D5 (real-skills mining) yielded 0 `test-real` DatasetRecords** under the
  task's `--no-llm` constraint — this is a measured, structural finding (no
  harvested source authors STJP's fenced-`localtype`/heading format), not a
  bug, but it means the miner does not yet supply any of the plan's 150-300
  `test-real` target; W8's own honest projection with LLM compaction enabled
  is still well below that target and recommends either revising the D5-share
  target down or adding a repair step, neither of which has been built.
- **W7 (calibration set + 100-item human-audit packet), W11 (Seam-Bench
  packaging/model card), and W14 (artifact persistence to HF Hub/release
  storage)** are listed in the plan's §9 dispatch table but have no
  corresponding evidence report in this branch as of this audit.

---

## 5. How to re-run everything

```bash
# 1. Wire the real toolchain (once per checkout/worktree)
bash tools/setup_scribble_cloud.sh

# 2. The five component test suites
python -m pytest stjp_core/tests/test_scribble_grammar.py -q
python -m pytest experiments/seam_bench/eval/tests/ -q
python -m pytest experiments/seam_bench/data/tests/ -q
python -m pytest experiments/seam_bench/judge/tests/ -q
python -m pytest experiments/seam_bench/mining/tests/ -q

# 3. Cross-worker package import check
python -c "import experiments.seam_bench.eval.metrics, experiments.seam_bench.judge.aggregate, experiments.seam_bench.data.signature, experiments.seam_bench.mining.harvest; print('package imports OK')"

# 4. Real-Scribble corpus sweep (30 files) + a corrupted negative control
python3 - <<'PY'
from pathlib import Path
from stjp_core.compiler.validator import ScribbleValidator

corpus_dir = Path("experiments/cases/_corpus")
files = sorted(corpus_dir.glob("*.scr"))
validator = ScribbleValidator()
passed = sum(1 for f in files if validator.validate_protocol(f)[0])
print(f"corpus: {passed}/{len(files)} passed")

gold = (corpus_dir / "corpus_000.scr").read_text()
corrupt = gold.rsplit("}", 1)[0]
tmp = corpus_dir.parent / "_audit_corrupt.scr"
tmp.write_text(corrupt)
ok, msg = validator.validate_protocol(tmp)
tmp.unlink()
print(f"negative control: {'REJECTED (correct)' if not ok else 'ACCEPTED (WRONG)'}")
PY

# 5. Optional: the workers' own bounded/full-size builds (20 min - several
#    hours; see W3's report §"Reproduction commands (full-size builds)" for
#    the exact D1/D3/splitter/leakage_check invocations, and W8's report
#    §7 for the miner's --remote-root invocation).
```

Expected results: all five suites green (23/86/22/62/37, one grammar test
skipped for a missing optional dependency), the import check prints
`package imports OK`, and the corpus sweep prints `30/30 passed` with the
negative control `REJECTED`.

---

## 6. Audit verdict

Every suite this audit ran came back green and matched the counts each
worker's own report claimed; the live corpus sweep and negative control
confirm the real Scribble toolchain — not a mock — is doing the validation.
No failures were found in this pass. The gaps in §4 are the honest,
already-self-reported boundary of the implemented work (data-scale targets
not yet reached, GPU-dependent training stages not yet started) rather than
anything contradicting the components' correctness.

---

## Addendum — post-audit integrations (same day, planner-verified)

Commits landed on `gc/user_intent_global_protocol_training` after the audit
above, each independently verified by the planner before integration:

| commit | addition | verification evidence |
|---|---|---|
| 5f3e2fa | docs guide 8 (`docs/8_INTENT_TO_PROTOCOL_TRAINING.md`) + README index | every documented entry-point file confirmed present on the branch |
| adbd7b4 | `docs/reference/GPU_TRAINING_RUNBOOK.md` (710 lines) | spot-checks: R2 pin block verbatim (vllm==0.23.0 cap), generation_kwargs grammar pass-through, az-login owner-machine rule |
| 8d3bec7 | this audit report | — |
| 4dc329b | T0 baseline runner (`experiments/seam_bench/t0/`) | independent re-run: 47/47 tests; 23/23 gold pairs validate under real Scribble (`smoke_gold`) |
| 0e24881 | paper v9 (`paper-writing/v9/`): §8 "The Trainable Seam, Realized" + 26-macro results template | independent structural check: 39/39 begin/end, all seam macros resolve, seam_results.tex included |
| 17e3da3 | human fit/no-fit labeling tool (`experiments/seam_bench/judge/human_audit/`) | independent re-run: 98/98 judge tests; committed 220-item packet verified blind (fields = intent/item_id/order_index/protocol_text only; strata in separate key file) |
| 3463b70 | recursion generator (W15): 200 recursive families, d1_expand race fix | independent re-run: 34/34 data tests; recursion signature report 150/150 + 20/20 vs unoptimized checker |

Updated component totals on this branch: 265 passing tests across
seam_bench (eval 86, data 34, judge 98, mining 37, t0 47 — note judge
includes human_audit's 36) + grammar 23+1skip; 671 non-recursive + 200
recursive = 871 EFSM-deduped protocol families; the 220-item blind human
audit packet ready for labeling.

Remaining GPU-dependent work is unchanged from the section above; the
full re-run commands for the new packages:
`python -m pytest experiments/seam_bench/t0/tests/ -q`,
`python -m pytest experiments/seam_bench/judge/human_audit/tests/ -q`,
`python -m pytest experiments/seam_bench/data/tests/ -q`,
`python -m experiments.seam_bench.t0.smoke_gold`.
