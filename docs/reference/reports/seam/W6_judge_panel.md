# W6 — Faithfulness Judge Panel

Worker: W6 (Sonnet implementation). Plan: `docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md` §5 (isolation layers) + §6
(calibration gate binds later, at W7), plan v2.1. Background: `SEAM_AUTOTRAINING_PLAN.md` §3.

Deliverable: `experiments/seam_bench/judge/` — `judge_panel.py`'s responsibilities per §5, split into
`payloads.py`, `seats.py`, `classes.py`, `aggregate.py`, `canaries.py`, `cache.py`, `run_panel.py` (orchestration
glue), plus `tests/`.

## Architecture

```
payloads.py   sanitize_protocol(source) -> SanitizedPayload   (§5.2)
seats.py      SeatConfig, default_panel(), call_structured/call_text, Verdict  (§5.1, §5.3, §5.4)
classes.py    run_j_fwd, run_j_back (+reconstruct_intent/compare_intents), run_j_probe (+ProbeSpec/evaluate_probe)
aggregate.py  verify_evidence, weiszfeld/geometric_median_score, aggregate_panel, write_escalation_record  (§5.3, §5.5)
canaries.py   swapped-pair / gold-vs-mutant / duplicate-self-consistency / rationale-overlap / effective-votes  (§5.5)
cache.py      VerdictCache: disk-backed (class, model, temp, prompt_hash, payload_hash) -> JSON  (§5.1)
run_panel.py  judge_case(): wires one (intent, G) case through the full panel + aggregation; CLI entry for the
              conditional real-API smoke test
```

All five layers of §5 are implemented as deterministic Python in the orchestrator, not by convention, matching the
plan's framing:

**5.1 Process isolation.** A verdict is exactly one `client.messages.create(...)` call — no `tools`, no session
object, bounded `max_tokens`, JSON-schema-forced output (`output_config.format`). There is no judge "agent" class;
`seats.call_structured`/`call_text` are free functions closed only over their arguments, so nothing can accumulate
state between calls. Verified directly in `tests/test_seats.py::test_call_structured_is_one_stateless_call_no_tools_no_session`.

**5.2 Payload sanitization.** `payloads.sanitize_protocol` strips comments *before* any parsing (not via a regex
pass over raw text at the end), then re-emits the canonical text by walking the recursive AST that
`stjp_core.critic.protocol_paths.parse_global_ast` produces (`GMessage`/`GChoice`/unrolled-`rec` nodes) — never by
taking a substring of the original source. Comments therefore cannot survive by construction, not by a stripping
heuristic that could be fooled. Verified with seven adversarial fixtures in `tests/test_payloads.py` that plant
`IGNORE PREVIOUS INSTRUCTIONS`-style text inside line comments, block comments, the role-declaration parens
(the specific hole in `stjp_core.compiler.protocol_parser`'s raw-text regexes, which this module deliberately does
**not** reuse), payload-type parens, choice branches, and trailing/EOF comments — all seven pass. Two extra tests
confirm two syntactically different sources that differ only in comments/whitespace produce byte-identical
sanitized text and hash, and that case-provenance-style comments (`case: skills_safety/pr_merge, provenance:
github/...`) are stripped.

**5.3 View decorrelation.** J-fwd seats each get an independently generated, cached paraphrase (`paraphrase_slot`
0 and 1). J-back's `reconstruct_intent(client, cache, seat, payload)` has **no `intent` parameter in its
signature** — that is the isolation mechanism, not a docstring promise; `tests/test_classes.py::test_j_back_reconstruction_step_never_receives_the_original_intent`
plants a secret marker in the intent and asserts it never appears in any prompt sent for reconstruction. A
separate stateless `compare_intents` call scores the reconstruction against the original. J-probe's one LLM call
(`compile_probes_from_intent`) never receives G at all — only the intent and the protocol's role/label vocabulary —
verified the same way (`test_compile_probes_from_intent_never_receives_the_protocol_text`). The default panel
(`seats.default_panel()`) matches §5.3 v2.1 exactly: 2×J-fwd (`claude-opus-4-8` + `claude-sonnet-5`, distinct
paraphrase slots), 2×J-back (`claude-sonnet-5` + a config-swappable seat defaulting to `claude-opus-4-8`), 1×J-probe
(deterministic). Temperatures drawn from {0.3, 0.7}; `rubric_emphasis` rotated across roles/ordering/prohibitions/termination.

**5.4 Structured verdicts + evidence verification.** Schema forced via `output_config.format` (json_schema,
`additionalProperties: false`, matches the current Structured Outputs API — see `Verdict`/`VERDICT_SCHEMA` in
`seats.py`). `aggregate.verify_evidence` string-matches every evidence quote against its claimed source
(protocol/intent text) after whitespace/case normalization. `classes.run_j_fwd`/`run_j_back` resample once at the
other pool temperature on fabrication and discard (flagging `discarded=True`) if the resample also fabricates —
covered by `test_j_fwd_fabricated_evidence_is_resampled_then_recovers` and `test_j_fwd_double_fabrication_is_discarded`.
J-back's comparator is additionally checked for a subtler failure mode: since it never sees G, *any* evidence quote
it labels `source="protocol"` is fabricated by construction — `test_j_back_protocol_sourced_evidence_is_always_fabricated`
confirms the discard path catches this even though the comparator's own free text never says anything obviously wrong.

**5.5 Collusion/degeneration audits.** `canaries.py` implements the full battery against an injected (mockable)
judge function, so it runs in CI with zero network calls: swapped pairs, gold-vs-mutant separation
(`naive_behavior_changing_mutation` — a light textual sender/receiver swap for canary purposes only, explicitly
**not** a substitute for D3's real mutation operators), duplicate-probe self-consistency, and the pairwise 5-gram
Jaccard rationale-overlap alarm (`ngram_jaccard`/`rationale_overlap_alarm` — checks free-text *rationale*
verbatim-overlap, not vote agreement, matching the plan's "honest judges may agree; they should not agree
verbatim"). Aggregation lives entirely in `aggregate.py`: `weiszfeld` (Weiszfeld's algorithm, dependency-free,
generalized to arbitrary dimension though used at D=1 here) computes the geometric median of per-seat calibrated
scores; J-probe failures veto the panel outright regardless of vote share (`aggregate_panel`); abstentions route to
`escalation_reasons` with dissent attached rather than being silently dropped; the escalation rule fires on
aggregate ∈ [0.4, 0.6], a probe-vote conflict (probe fails while the panel's score says accept, or vice versa), or
any abstention, and `write_escalation_record` appends a JSONL record for the human gate.

## J-probe status: implemented against the REAL toolchain, not interface+gap

The task card allowed shipping an interface-only stub if the critic machinery didn't expose what J-probe needs
within reasonable effort. It did: `stjp_core.compiler.efsm_parser.get_efsm_from_scribble` cleanly builds a real
per-role EFSM by shelling into the actual Scribble CLI, and this worktree already has the real toolchain wired
(`bash tools/setup_scribble_cloud.sh`, gold-pass/corrupt-reject smoke both green here). So J-probe is **fully
implemented**, not stubbed:

- **Interface** (`classes.py`): `Probe = {query_text: str, compiled_check: ProbeSpec}`. `ProbeSpec` is a plain
  dataclass — `kind: reachable|never|response`, `role`, `label`, `direction`, `peer`, and (for `response`) the
  matching `response_*` fields — never an LLM at verdict time.
- **Compiler** (the one LLM call): `compile_probes_from_intent` translates intent clauses into `ProbeSpec`s,
  grounded against the protocol's actual role/message vocabulary (never against G's text); any hallucinated
  role/label is dropped post-hoc rather than trusted (`test_compile_probes_from_intent_drops_ungrounded_probes`).
- **Checker** (deterministic, no sampling): `evaluate_probe` does BFS reachability for `reachable`/`never`, and
  bounded DFS path enumeration (depth cap + per-state revisit cap, so recursive/looping EFSMs terminate) for
  `response` queries, returning a genuine counterexample trace on failure
  (`test_evaluate_probe_response_fails_with_counterexample_when_notification_missing`).
- **Design note — intentional exemption from §5.2 sanitization**: J-probe's verdict never puts an LLM in front of
  G, so a comment hidden in G cannot persuade a deterministic BFS/DFS. `build_efsms_from_source` therefore compiles
  the *original* G (with its `data <java> ...` header, which `payloads.py` intentionally strips and which the real
  Scribble CLI requires to type-check), not the sanitized payload. Sanitization still applies everywhere an LLM
  reads G (J-fwd) or reads anything derived from it in prose (J-back).
- **Documented scope gap**: `response` probes are checked against a *single role's own* trace ordering only —
  cross-role response probes ("does every Reject on role A eventually cause a Notify on role B") would need a
  product automaton across roles' EFSMs, which this implementation does not build. This is a real, bounded gap
  (not a stub), noted for whoever picks up J-probe next (W7/W9 territory) rather than silently faked.
- **One worked example against the real toolchain**, not a mock:
  `tests/test_classes.py::test_build_efsms_from_source_real_toolchain_worked_example` runs the actual Scribble CLI
  against `experiments/cases/_corpus/corpus_000.scr`, builds all four roles' real EFSMs, and evaluates a genuine
  `reachable` probe against the real transitions. It passed in this environment (see test output below). It is
  `pytest.skip`-guarded on `SCRIBBLE_PATH.exists()` so CI environments without the toolchain wired skip it cleanly
  rather than failing; `run_panel.py::judge_case` also exercises the real toolchain end-to-end via
  `tests/test_run_panel.py` (mocked LLM client, real EFSM build).

## Effective-votes estimate

`canaries.effective_independent_votes` implements the standard design-effect correction
`k / (1 + (k-1)*avg_pairwise_r)` over a canary vote matrix — the same quantity the plan cites for R1's "a 9-judge
panel can carry ~2 effective votes" finding. Three runs, all reproducible from the test suite / a throwaway script
(no real API calls — no key was available, see below):

| scenario | seats | avg pairwise r (approx) | effective votes |
|---|---|---|---|
| near-independent 4-seat matrix (`test_effective_votes_near_k_for_independent_seats`) | 4 | ~0 | **4.00** |
| perfectly-correlated 9-seat matrix (`test_effective_votes_near_one_for_identical_seats`) | 9 | 1.0 | **1.00** |
| synthetic 5-seat default-panel simulation (fwd/back share class-correlated noise, probe deterministic on the same underlying signal) | 5 | high (shared "true signal" term dominates) | **1.21** |

The third row is an illustrative simulation only (Python `random`, seeded), not a real-model calibration number —
it demonstrates that the ≥3 effective-votes gate (§5.5/§6) is a real risk even with class-mixed seats if the
per-item "how hard is this case" variance dominates over independent per-seat noise, exactly the monoculture
caveat the plan calls out ("mixed Anthropic versions buy ACCURACY, not independence — the class structure
(fwd/back/probe) carries decorrelation"). A trustworthy effective-votes number needs real API calls across a
canary battery, which is W7's calibration-set job, not W6's.

## Deviations from the task card

1. **`STJP_JUDGE_BACK2_MODEL_ID`** — per the plan's owner directive ("Opus 4.6 id slotted when confirmed"), the
   second J-back seat defaults to `claude-opus-4-8` and reads `STJP_JUDGE_BACK2_MODEL_ID` from the environment, so
   swapping in the exact Opus 4.6 id later is a one-line env change, not a code change.
2. **J-probe `response` probes are single-role only** (see above) — a documented, bounded gap, not silently faked
   with an LLM.
3. **`.refn` value-guard sidecars are not sanitized** — `payloads.py` only handles `.scr` global-protocol text.
   Guard sidecars carry value-level refinement constraints the plan mentions (§2) but §5's payload description
   doesn't call them out explicitly; scoped out given the effort budget. Flagging so W7/W9 know it's untouched.
4. **`judge_panel.py` as a single file vs. a package** — §5's prose names one file
   (`experiments/scripts/judge_panel.py`); the task card explicitly asks for a *package* at
   `experiments/seam_bench/judge/` with the seven listed modules, which is what's delivered. No `experiments/scripts/judge_panel.py`
   was created — worth a one-line pointer/shim later if something imports that exact path.

## Real smoke (conditional) — not run

`ANTHROPIC_API_KEY` was not present in the environment (`env | grep -i anthropic` shows only `ANTHROPIC_BASE_URL`;
the `ant` CLI is also not installed, so no OAuth profile exists either). Per the task card, the real single-panel
smoke run against a corpus case is **skipped**, plainly: no real Opus/Sonnet verdicts are pasted below because none
were produced. `experiments/seam_bench/judge/run_panel.py` is ready to run the moment a key is available:

```
python3 -m experiments.seam_bench.judge.run_panel \
  --protocol experiments/cases/_corpus/corpus_000.scr \
  --intent "<3-sentence hand-written intent for corpus_000>"
```

It prints the aggregated `PanelResult` as JSON and appends an escalation record if the gray-zone/probe-conflict/
abstention rule fires. Confirmed the skip path itself works cleanly in this environment (prints
`ANTHROPIC_API_KEY not set — skipping real panel smoke run.` and exits 0).

## Test output

```
$ python3 -m pytest experiments/seam_bench/judge/tests/ -q
..............................................................
62 passed in 6.25s
```

Breakdown: `test_payloads.py` 13 (7 adversarial-comment parametrized + 6 structural), `test_cache.py` 4,
`test_aggregate.py` 12 (includes the geometric-median-beats-arithmetic-mean-under-one-poisoned-seat fixture),
`test_seats.py` 4, `test_classes.py` 17 (includes the real-toolchain worked example), `test_canaries.py` 9,
`test_run_panel.py` 1 (full mocked panel + real EFSM build, end to end).

All classes are testable fully offline with a mocked `anthropic.Anthropic`-shaped client
(`tests/conftest.py::MockAnthropic`), per the task card's "every layer testable offline" requirement — the only
test gated on the real toolchain (`SCRIBBLE_PATH.exists()`) is the one that is explicitly supposed to exercise it.

## Files

- `experiments/seam_bench/judge/payloads.py`
- `experiments/seam_bench/judge/seats.py`
- `experiments/seam_bench/judge/classes.py`
- `experiments/seam_bench/judge/aggregate.py`
- `experiments/seam_bench/judge/canaries.py`
- `experiments/seam_bench/judge/cache.py`
- `experiments/seam_bench/judge/run_panel.py`
- `experiments/seam_bench/judge/tests/` (conftest.py + 7 test modules, 62 tests)
