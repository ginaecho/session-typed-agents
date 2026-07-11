# W3 — D1-D3 data builders + EFSM-signature dedupe/splitter

Worker: W3 (implementation). Branch `gc/seam-w3-data-builders`.
Spec: `docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md` §3 + §9 (W3 row);
`docs/reference/SEAM_AUTOTRAINING_PLAN.md` §2 (A3/A4), §4.1.

Everything below ran against the REAL Scribble-java toolchain
(`tools/setup_scribble_cloud.sh`, shared `/workspace` build, `lib/`
symlink), on a 4-core cloud sandbox. Every builder starts with a
fail-loud preflight (`common.assert_toolchain`): a gold corpus protocol
must validate AND a corrupted copy must be rejected with a parser error —
a missing/mis-wired toolchain aborts the run instead of surfacing as
silent 100% rejection or fake counterexamples.

## What exists

Package `experiments/seam_bench/data/`:

| file | role |
|---|---|
| `common.py` | fixed JSONL schemas (DatasetRecord / RepairRecord), seed discovery (30 corpus + 21 named-case protocols = 51 seeds), `validate_text` (real `ScribbleValidator` on a scratch file), `assert_toolchain` |
| `signature.py` | canonical EFSM-equivalence-class signature (§ below); `SignatureCache` (thread-safe, text-hash keyed, on-disk); `--verify` harness against the repo's E5 checker |
| `d1_expand.py` | D1 — sweep / compose / crossover expansion, validator-gated, signature-deduped, thread-pooled, deterministic per `--seed`, checkpointing |
| `d2_backtranslate.py` | D2 — 3-register intent prompts, forbidden-vocabulary filter, mock + real Anthropic client, pluggable round-trip probe |
| `d3_repair.py` | D3 — repair tuples from the repo's mutation operators; validator-passing mutants split out to `calibration_candidates.jsonl` |
| `splitter.py` | family-level 80/10/10 split, stratified by (role_count, has_recursion, depth_bucket) |
| `leakage_check.py` | done-criterion checker (green run below) |
| `tests/` | 22 pytest tests, all passing (125 s; they hit the real validator) |
| `samples/` | ≤200-record samples of every artifact + stats/curves (full builds are NOT committed) |

## Signature design + verification (task-card requirement)

`protocol_signature(text)` = SHA-256 over the sorted per-role canonical
EFSM forms, where the per-role canonicalization **reuses the repo's own**
`stjp_core/compiler/incremental.py::efsm_signature` (BFS state relabeling
from the initial state, deterministically ordered edges) — the same
function incremental re-projection already trusts to detect changed
roles. This is the task card's "acceptable v1" (canonical minimized form
per role, hashed together), so the mandated cross-check against the
repo's pairwise checker was run:

```
python experiments/seam_bench/data/signature.py --verify --pairs 200 --seed 0
```

Population: 51 seeds + their mutants (via `mutate_protocol.py`) up to 120
texts (97 validated; 23 were validator-rejected mutants, correctly
unsignable). Result (`samples/sig_verify_report.json`):

- pairs tested: **200**, agreement with `efsm_equiv.protocols_equivalent`:
  **200/200 = 100.0%**
- 20-pair spot-check of the fast in-process replica against the
  *unoptimized* `protocols_equivalent` (fresh Scribble runs): **20/20**.

No escalation needed (<100% would have required one).

Signature stability across toolchain builds was also checked: the local
Maven build and the shared `/workspace` build produce byte-identical
`-fsm` DOT output for all roles of `corpus_000`, and
`protocol_signature(corpus_000)` is unchanged after switching to the
shared lib symlink.

## D1 — expansion (bounded run, measured saturation)

```
python experiments/seam_bench/data/d1_expand.py \
  --target 800 --max-candidates 3000 --seed 1 --workers 4 \
  --curve-every 50 -o /tmp/d1_v2/d1_dataset.jsonl
```

Run was time-boxed at 1380 s (`timeout 1380 ...`); it checkpoints every
30 s, so the kill cost nothing. Real output:

```
[d1] candidates=803 uniques=661 rejected=0 dup=109 n/a=33 rate=0.60/s elapsed=1345.4s
```

- **671 unique valid families** kept (last checkpoint) from ~810
  candidates in 22.5 min.
- Throughput: **0.60 candidates/s ≈ 0.50 uniques/s** with 4 workers
  (each kept candidate costs 1 validate JVM + one `-fsm` JVM per role;
  text-hash cache dedupes BEFORE validation; `assume_valid=True` avoids
  re-validating inside the signature call).
- Operator mix: sweep 344, crossover 181, compose 146. Role counts
  2:41 / 3:153 / 4:202 / 5:156 / 6:119; depth flat 287 / shallow 356 /
  deep 28; 220 records carry a generated+parse-checked `.refn` sidecar.
- validator_rejected = 0 across the run: all three operators are
  validity-preserving-by-construction on this population (sweep shapes
  are safe by design; compose is internally validated by
  `incremental.add_subprotocol`; crossover splices between causally
  compatible acyclic texts). The validator is nevertheless live in the
  loop — the corrupt-protocol preflight proves it rejects, and D3 below
  exercises the reject path hundreds of times.

Saturation curve (uniques vs candidates; full curve in
`samples/d1_saturation.json`):

| candidates | 101 | 201 | 301 | 401 | 501 | 601 | 701 | 803 |
|---|---|---|---|---|---|---|---|---|
| uniques | 85 | 166 | 255 | 342 | 424 | 496 | 574 | 661 |
| duplicates | 13 | 27 | 35 | 42 | 55 | 78 | 96 | 109 |

The curve is still near-linear (dup rate ~14% at the end, rising
slowly): **5,000 families are plausibly reachable with the current
operators** at roughly 6,500-8,000 candidates ≈ 3-4 h wall-clock on this
4-core box (the workload is JVM-bound and embarrassingly parallel; more
cores scale it directly). One measured exception: the **recursion axis
saturates at ~9 families** — the `retry` shape is the only
recursion-bearing generator and is near-deterministic per grid cell.
Growing the recursion-on stratum needs either a randomized recursive
generator or nuscr-coinductive-backed shapes; flagged as a known
limitation, not silently padded.

To continue the build: rerun the same command with a higher
`--max-candidates` and the same `--cache` file; the signature cache makes
re-processing of already-seen texts free.

Two real bugs were found and fixed by inspecting the first full run's
output (both now have regression tests):

1. the task-interleave pattern (period 9) aliased against the sweep grid
   (stride divisible by 9), silently making every `retry` (recursion)
   grid cell unreachable — the first run produced 0 recursive protocols;
2. `gen_compose` wrote the parent seed under a filename that didn't match
   its `module` line, so Scribble's `-fsm` failed for every composed
   candidate (0 compose yield in the first run); relatedly,
   `protocol_name`/`roles_of` had to skip `aux global protocol` headers
   for composed texts.

## D3 — repair tuples + calibration split-out

```
python experiments/seam_bench/data/d3_repair.py \
  --target 20000 --max-mutations 3200 --seed 1 --workers 4 \
  --gold-jsonl /tmp/d1_v2/d1_dataset.jsonl --n-generated 80 \
  -o /tmp/d3_v2/d3_repair.jsonl \
  --calibration-out /tmp/d3_v2/calibration_candidates.jsonl
```

Real output:

```
[d3] 860 repair records + 1746 calibration candidates from 3200 mutation
     attempts over 802 golds in 636.8s -> /tmp/d3_v2/d3_repair.jsonl
```

- Gold pool: 51 seeds + 671 D1 families + 80 freshly generated
  LocalType-bearing protocols (for the `s2_mutation` operator family).
- Throughput: **5.03 mutations/s** (mutant validation is one JVM; gold
  signatures are cache hits after first touch).
- The ≥20k target was NOT reached in this bounded run — measured yield is
  **0.27 repair tuples per mutation attempt ≈ 1.35 repairs/s**, so 20k ≈
  4.1 h wall-clock with the same command and `--max-mutations` ~74k.
  That is a budget statement, not an operator limitation; per the task
  card the reachable number + yield table is reported instead.
- Counterexamples are the validator's error string verbatim, minus
  exactly one environment artifact (the sandbox JVM's
  `Picked up JAVA_TOOL_OPTIONS` stderr banner, which would otherwise leak
  host proxy config into training data — see
  `d3_repair.clean_counterexample`). Example record:
  operator=`branch_asymmetry`, counterexample=`Source role not enabled: R3`.

Per-operator yield (full table in `samples/d3_yields.json`):

| operator | applied | → repair (rejected) | → calibration (passed) | synth-rejected | n/a |
|---|---|---|---|---|---|
| undeclare_role | 429 | 429 (100%) | 0 | – | 0 |
| flip_branch_subject | 272 | 272 (100%) | 0 | – | 193 |
| branch_asymmetry | 251 | 154 (61%) | 97 | – | 170 |
| rewire_peer | 341 | 4 | 337 | – | 104 |
| drop_message | 425 | 1 | 424 | – | 0 |
| circular_wait | 402 | 0 | 402 | – | 0 |
| swap_order | 485 | 0 | 485 | – | 2 |
| drop_receive (local) | 0 | 0 | 0 | 22 | 0 |
| retype_payload (local) | 0 | 0 | 0 | 27 | 0 |
| swap_fifo (local) | 1 | 0 | 1 | 19 | 0 |
| reroute_peer (local) | 0 | 0 | 0 | 24 | 0 |
| rename_label (local) | 0 | 0 | 0 | 33 | 0 |

Two findings worth the planner's attention:

1. **The `s2_mutation` (LocalType-level) family contributes ~no textual
   repair tuples**: 120/125 of its mutants are caught by
   `global_synthesizer` BEFORE any global text exists (the
   `caught_by=synthesis` layer of integration_stress), so there is no
   `broken` protocol text to train on. Those five operators are imported
   and exercised as the task card asked (via the extracted
   `apply_local_mutation` — `integration_stress.py` itself is unchanged
   in behaviour and its suite still passes 63/63), but the *repair-data*
   surface is effectively the 7 text-level operators.
2. The reorder-style text operators (`circular_wait`, `swap_order`,
   `drop_message`, `rewire_peer`) almost always yield validator-PASSING
   mutants on this population — consistent with `mutate_protocol.py`'s
   own documentation (acyclic reorders are usually still well-formed).
   They are the dominant source of calibration candidates (semantic
   near-misses), which is exactly what §6 judge calibration needs.

`calibration_candidates.jsonl` rows carry
`{id, family, seed_case, operator, gold, mutant, intent, intent_source}`
— (intent, gold) vs (intent, mutant) pairs ready for W6/W7.

## D2 — back-translation (module + mocked run; NO API spend)

**No `ANTHROPIC_API_KEY` exists in this environment, so the API smoke
did not run and $0.00 was spent.** The module is complete and the whole
pipeline ran end-to-end with the deterministic `MockIntentClient`
(stated loudly in its own output: `[d2] MOCKED — no ANTHROPIC_API_KEY ...`):

```
python experiments/seam_bench/data/d2_backtranslate.py --mock \
  --gold-jsonl /tmp/d1_v2/d1_dataset.jsonl \
  -o /tmp/d2_full/d2_backtranslate.jsonl
# [d2] 2013 (intent, protocol) pairs from 671 protocols (0 quarantined)
```

- 3 registers per protocol (terse ticket / conversational / spec
  paragraph); prompts show the model a Scribble-vocabulary-free
  "participants + numbered exchanges" rendering, and every output is
  post-filtered against a forbidden-terms list (violations are dropped,
  not trained on).
- Example mocked pairs (real API pairs pending a key; mock output is
  intentionally template-shaped, NOT training-grade — the module exists
  so W9 can re-run with `AnthropicIntentClient` and a `--budget-usd` cap,
  default $5):
  - `[terse_ticket] Coordinate R0, R1 to complete the task; R0 kicks things off with R1.`
  - `[conversational] hey can you get R0, R1 to sort this out? R0 kicks things off with R1`
  - `[spec_paragraph] This task involves R0, R1 working together. R0 kicks things off with r1, and the exchange proceeds until ...`
- Round-trip acceptance is implemented as `round_trip_probe(intent,
  gold, translate_fn, best_of=5)` — validator + E5
  `protocols_equivalent`, with `translate_fn` pluggable so W9 drops the
  trained translator in without redesign; failures are quarantined to a
  `hard` list per the plan. Tested with identity and always-None
  translators.

## D4 — splits + leakage check (done-criterion: GREEN)

```
python experiments/seam_bench/data/splitter.py \
  --in d1_dataset.jsonl d2_backtranslate.jsonl d3_repair.jsonl \
  --out-dir /tmp/splits --seed 1
python experiments/seam_bench/data/leakage_check.py \
  --split-dir /tmp/splits --files d1_dataset.jsonl d2_backtranslate.jsonl d3_repair.jsonl
```

751 families total across the three files → train 599 / dev 76 /
test-syn 76 (79.8 / 10.1 / 10.1 %), assigned per-FAMILY within each
(role_count, has_recursion, depth_bucket) stratum. Real checker output:

```
[1] no family in two splits: PASS (0 offending families)
[2] no seed family straddles: PASS (0 offending seeds)
[3] strat table matches splitter.py's cached table: PASS
VERDICT: GREEN — all leakage checks pass
```

Full strat table committed at `samples/splits/leakage_check_output.txt`;
`samples/splits/family_registry_summary.json` has the split counts (the
full registry maps every family hash → split and ships with the full
build, not the repo). Recursion-bearing strata are thin (see the D1
finding); strata with <3 families stay train-only by design rather than
placing a lone family in dev/test.

## Tests

```
python -m pytest experiments/seam_bench/data/tests/ -q
# 22 passed in 125.64s
```

Coverage: signature determinism / whitespace-insensitivity / negative
protocol; D1 tiny-budget build validity+dedupe+determinism, compose
regression, sweep-grid reachability regression, retry-shape validation,
refn parsing; D3 tiny-budget build (both operator families, verbatim
counterexamples, calibration split-out), stub-intent vocabulary; D2
mocked end-to-end, vocab filter, round-trip probe accept/reject; splitter
family-cohesion + 80/10/10 + leakage green/red detection.

`experiments/scripts/integration_stress.py` (touched only to extract
`apply_local_mutation`, same RNG consumption order) re-run: **63/63
checks pass over 3 seeded iterations**.

## Reproduction commands (full-size builds)

```
bash tools/setup_scribble_cloud.sh                       # once per checkout
D=experiments/seam_bench/data
python $D/signature.py --verify --pairs 200 --seed 0     # agreement report
python $D/d1_expand.py --target 5000 --max-candidates 20000 --seed 1 --workers 4 -o out/d1.jsonl
python $D/d3_repair.py --target 20000 --max-mutations 74000 --seed 1 --workers 4 \
    --gold-jsonl out/d1.jsonl -o out/d3.jsonl --calibration-out out/cal.jsonl
python $D/d2_backtranslate.py --gold-jsonl out/d1.jsonl -o out/d2.jsonl   # add ANTHROPIC_API_KEY for live
python $D/splitter.py --in out/d1.jsonl out/d2.jsonl out/d3.jsonl --out-dir out/splits --seed 1
python $D/leakage_check.py --split-dir out/splits --files d1.jsonl d2.jsonl d3.jsonl
```

## Done-criteria vs task card

| criterion | status |
|---|---|
| signature: equivalent ⇒ same, non-equivalent ⇒ different, verified ≥200 pairs | PASS — 100% agreement on 200 pairs + 20-pair spot-check vs the unoptimized checker |
| D1 ≥5,000 unique families | PARTIAL — 671 in a 22.5-min bounded run; saturation curve still near-linear, ~3-4 h projected for 5k with the same operators (recursion axis saturates at ~9 and needs a new generator); exact continue-command documented |
| every candidate through the repo validator | PASS — `validate_text` → real ScribbleValidator; fail-loud preflight; dedupe by signature (never text) |
| D3 ≥20k repair tuples or reachable number + yield table | PARTIAL — 860 in a 10.6-min bounded run at 0.27 repairs/attempt; per-operator table above; ~4 h projected for 20k |
| calibration_candidates.jsonl split out | PASS — 1,746 validator-passing mutants |
| D2 module + mocked tests; API smoke ≤$5 | PASS (mocked) — no API key in environment, $0 spent, stated plainly; live client + budget cap implemented for W9 |
| splitter by family, stratified 80/10/10 | PASS — 599/76/76 families |
| leakage_check green | PASS — GREEN, output above |
| samples ≤200 records/file, no multi-MB data committed | PASS |
| pytest suite | PASS — 22/22 |
