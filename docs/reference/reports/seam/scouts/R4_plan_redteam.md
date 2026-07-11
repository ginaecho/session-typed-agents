# R4 — Adversarial red-team of the Seam-Training plan

Scope: `SEAM_TRAINING_EXECUTION_PLAN.md` (exec) + `SEAM_AUTOTRAINING_PLAN.md`
(strategy), checked against repo reality (`stjp_core/compiler/`,
`experiments/scripts/{gen_corpus,integration_stress,mutate_protocol,efsm_equiv}.py`,
`experiments/cases/_corpus/`, RESULT_5/7/9, `paper-writing/v8/CHANGELOG_v8.md`).
Read-only. Verified 2026-07-11.

**Tally: 2 blockers, 7 majors, 5 minors.**
Worst hole: **B1** — the entire dedup / diversity / leakage-hygiene mechanism
rests on a "canonical bisimulation-quotient signature" that (a) does not exist
in the repo, (b) is O(n²)×JVM if built the only way the repo currently supports,
and (c) even when built measures **non-bisimilarity, not structural diversity**,
so the "5,000 diverse families" target and every downstream generalization claim
are unfounded.

---

## BLOCKERS

### B1 — "5k diverse families" is 5k non-bisimilar clones of ~5 topologies, deduped by a signature that isn't implemented
**Hits:** §3 D1 ("uniqueness is by EFSM-equivalence class… canonical bisimulation-quotient signature"), §3 D4 (split by "EFSM signature of the seed"), and by inheritance H3/H6.
**Failure scenario (one sentence):** D1 sweeps role-count/branch-width/recursion over the 4–5 seed topologies, the EFSM signature dutifully reports 5,000 *non-bisimilar* protocols, and SFT trains on 5,000 pipelines-of-different-lengths that generalize to nothing off the topology manifold.

Evidence:
- The 30 `_corpus` skeletons come from exactly **five shape families**: `grep "global protocol"` → Pipe(4), Star(4), Fan(3), Nego(11), Gen(8). `gen_corpus.py::SHAPES` defines four primitives (`pipeline/star/fan/negotiation`) plus one generic generator. That is the entire structural vocabulary; the 19 named cases add a handful more but not orders of magnitude.
- A 3-role pipeline and a 5-role pipeline are **not bisimilar** (different state counts), so the proposed dedup counts them as two "unique families." Bisimulation-inequivalence is trivially satisfied by scaling one knob; it is *not* a diversity metric. 5,000 non-bisimilar EFSMs can all be the same shape.
- **The canonical signature does not exist.** `efsm_equiv.py` provides `efsm_bisimilar(e1,e2)` and `protocols_equivalent(text_a,text_b)` — a **pairwise** product-BFS decision procedure. There is no canonicalization/hash (`grep` for `quotient|canonical_sig|signature` → nothing). Deduping N candidates pairwise is O(N²) bisim checks, each of which **projects all roles through Scribble/nuscr = JVM spawns**. At N=5k that is ~12.5M pairwise checks × multiple JVM launches each. Infeasible. The plan invokes this signature as if it were existing tooling; building a true canonical bisimulation normal form (partition-refinement to a canonical labeling) is real, unscheduled work — and it also silently gates D4 leakage hygiene.

**Fix:** (1) Add a *structural* diversity axis orthogonal to bisim: e.g. topology class (pipeline/star/fan/nego/composed) × interaction-DAG isomorphism class × {branch-count, max-recursion-depth, role-count, guard-count} feature vector; set a **floor** (no single topology class > 25% of train; ≥ K distinct isomorphism classes; report a diversity index such as normalized entropy over topology×feature buckets ≥ 0.7). (2) Implement a real canonical signature (partition-refinement quotient → sorted edge-label string → hash) as a *pure-Python* pass over already-projected EFSMs, computed once per protocol, so dedup is O(N) hashing, not O(N²) JVM; add it as an explicit W3 sub-deliverable with a done-when. (3) State the diversity floor as a preregistered gate before SFT.

### B2 — Post-SFT the GRPO reward has near-zero within-group variance; the brevity term becomes the objective → mode-collapse to shortest-valid, drifting off gold
**Hits:** §2 reward block, §4 T2, §8 H4. (This is the "if real it breaks T2" case.)
**Failure scenario (one sentence):** After a good SFT init, in a group of 8 rollouts under GCD nearly all pass the validator (+1 each) and none/most-or-all match gold under the **binary** bisim term, so the only quantity that varies across the group is `−0.1·len/1024`, and GRPO's group-relative advantage optimizes purely for *shorter valid protocols regardless of intent*.

Why it holds in every regime: bisim-to-gold is exact behavioral equality — all-or-nothing, no partial-credit gradient. If the SFT model rarely hits it, the +2 fires ~0× across the group (no variance from bisim). If it usually hits it, +2 fires ~everywhere (again no variance). The healthy intermediate band where bisim provides gradient is narrow *because the term is binary*. Meanwhile GCD guarantees parse (not rewarded) and validator pass saturates post-SFT. Net: the dense, always-varying term is brevity, pointing at the degenerate minimum (smallest validating protocol — a 2-role single-message `.scr` validates and is short). The faithfulness term that would anchor to intent is **0.0 until the §6 gate passes** and only applies to mined prompts, so in T2 nothing opposes the brevity pull. This is the exact reward-hacking signature the plan itself names (validity flat/up, faithfulness down) but the guard against it (§4 divergence guard) is defeasible — see M1.

**Fix:** (1) Replace binary bisim with a **graded** equivalence distance that yields a continuous gradient toward gold: trace-set F-score, simulation-preorder distance, or EFSM edit distance on the bisim quotient (repo already computes per-role EFSMs; `protocol_language()` already yields a trace frozenset for a Jaccard). (2) Drop or cap the brevity term to a tiny tie-breaker (e.g. `−0.02·max(0,len−len_gold)/1024`, one-sided, only penalizing *bloat past gold*, never rewarding sub-gold brevity). (3) Add a hard floor: any rollout shorter than gold's role/message count gets no brevity credit. (4) Verify non-degenerate group reward variance on a dev batch *before* committing GRPO compute (make it a T2 pre-flight check).

---

## MAJORS

### M1 — The T2 divergence guard is defanged exactly when it is most needed
**Hits:** §4 T2 ("dev *panel score* … halts the run automatically") vs §6 ("Below gate → the panel remains advisory … never a deployment gate").
**Scenario:** §6 calibration misses (a real possibility the plan plans for), the panel goes advisory, and the T2 divergence guard — whose halt signal *is* the dev panel score — either can't fire (advisory) or fires on an uncalibrated signal, leaving B2's brevity drift with no faithfulness backstop in the one phase that has no in-reward faithfulness term.
**Fix:** Specify that an advisory panel still powers the *halt-only* divergence guard (halting ≠ rewarding ≠ deployment-gating), OR add a gold-anchored non-panel divergence guard for T2 (dev bisim@1 and dev mean length must not move monotonically against dev validity). Make the guard's authority explicit under both §6 outcomes.

### M2 — Judge calibration is circular; the AUC/agreement gates are optimistically biased
**Hits:** §5.3 (J-fwd sees paraphrases of the D2 intent; default panel is Sonnet/Haiku), §6 ("gold (intent,G) from D2 round-trip winners").
**Scenario:** The calibration "gold" set is precisely the pairs that already survived a Sonnet best-of-5 round-trip probe (the same mechanism J-back implements), and the judges share the D2 back-translator's family/style priors, so the ≥0.85 AUC and ≥0.90 ensemble are measured on panel-friendly pairs and overstate real-world separation.
**Fix:** (1) Draw calibration gold from a source the panel/back-translator did **not** filter — the mined `test-real` human intents and/or Gina's 100 human labels — not from D2 round-trip winners. (2) Require at least one **non-Anthropic** seat to be *present* (not just "if available") for the reported ensemble AUC, or explicitly caption the number as within-family. (3) Report J-fwd-only vs full-panel AUC gap as the circularity estimate (already an ablation — promote it to a gate diagnostic).

### M3 — 100-item human audit is underpowered to *certify* the ≥85% agreement gate
**Hits:** §6 ("≥85% agreement with the human-audited 100").
**Scenario:** The ensemble lands 85/100, the gate reads "pass," but the Wilson 95% CI is **[75.8%, 89.8%]** — true agreement could be ~76% and T3 proceeds to spend faithfulness reward on a panel that is not actually ≥85%.
Math: p̂=0.85, n=100 → Wilson 95% CI ≈ [0.758, 0.898]. To make the CI *lower bound* ≥0.85 you need ≈ **370** audited items at p̂=0.90 (or a near-perfect ~95/100 at n=100).
**Fix:** Rewrite the gate as "Wilson 95% lower bound ≥ 0.85," and either raise the audit to ~300–400 items or lower the gate to "point estimate ≥ 0.90 on 100 with LB ≥ 0.83." Budget the extra human labor (still small) or accept the weaker, honestly-stated bar.

### M4 — JVM-per-validation throughput will bottleneck GRPO on-policy rollouts
**Hits:** §2 throughput note + reward block, §9 W5 ("<200ms cached").
**Scenario:** Each GRPO epoch is group-8 × 1–2k prompts = up to **16,000 rollouts**, each needing a real Scribble validation whose cost is dominated by JVM boot (~0.5–1 s); at ~1 s serial that is ~4.4 h of validation per epoch, and because GRPO reward is on-policy the A100 stalls waiting on the JVM farm. The "<200ms cached" done-when is the *cache-hit* path, but under temp-0.8 GCD sampling early-epoch outputs are mostly distinct → low hit rate → the uncached ~1 s path dominates exactly when it hurts.
**Fix:** Replace per-call `java` spawns with a **persistent JVM validation service** (Nailgun, or a long-lived JVM exposing a socket/HTTP validate endpoint, or GraalVM native-image of the Scribble CLI) so per-check cost is the parse+check (~ms), not JVM boot. Pre-warm a worker pool sized to sustain rollout throughput; make W5's done-when include a *sustained uncached* throughput target (e.g. ≥ 500 validations/s aggregate), not just the cached latency.

### M5 — Ephemeral container loses the expensive, non-git-reconstructible state
**Hits:** §1 (worktree/handoff model), §2 (rented GPU), §9 (deliverables).
**Scenario:** A mid-run eviction of the rented GPU host destroys LoRA adapters, GRPO checkpoints, the verdict cache, and per-rollout JSONL — none of which are in git — and the $100–350 GRPO run must restart from scratch because "reconstructible from git" only covers code, not weights.
**Fix:** Mandate a durable object store (S3/GCS/Modal volume) with per-epoch checkpoint push, resumable-from-last-checkpoint GRPO, and cache/JSONL flushed to durable storage; state explicitly which artifacts are git-tracked vs object-store-tracked. `tools/setup_scribble_cloud.sh` rebuilds the toolchain, but nothing rebuilds a trained adapter.

### M6 — `test-real` (150–300) is underpowered for the H6 transfer-gap claim, and its yield is admitted-unknown
**Hits:** §3 D5 ("yield honestly unknown"), §7 (transfer gap = metric(test-syn) − metric(test-real)), §8 H6.
**Scenario:** Mining yields ~150 items, transfer gap is a *difference of two rates* whose combined Wilson CI is ≈ ±10–11 pts at n≈200/p≈0.7, so "trained gap ≤ baseline gap" (H6) cannot be resolved unless the effect is huge — and if yield falls below 150, H6 is simply unfalsifiable.
**Fix:** Preregister a minimum `test-real` n with a power calculation for the H6 effect you expect to detect (state the minimum detectable difference); if mining under-yields, downgrade H6 to descriptive ("we report the gap with its CI") rather than a go/no-go, and say so now rather than post-hoc.

### M7 — "No public NL→MPST benchmark" is asserted, not verified, and concurrent-work collision is already demonstrated
**Hits:** §7, §10 ("release ours as the reference benchmark"), and the novelty framing generally.
**Scenario:** A concurrent NL→session-type / NL→protocol paper drops before submission (v8's own CHANGELOG shows the team was *already* surprised by ZipperGen, arXiv:2604.17612, an MSC-codegen neighbor), and the "first/reference benchmark" framing collapses because the "no benchmark exists" premise was never literature-verified with a dated search.
**Fix:** Run and log a dated literature search behind the claim; hedge to "first verifier-scored NL→MPST benchmark to our knowledge as of <date>"; pre-write the fallback positioning that survives a competitor — the durable edge is the **total, counterexample-producing** checker and the **mechanized** J-probe faithfulness fraction, not primacy.

---

## MINORS

- **m1 (factual drift).** Strategy doc says "100-protocol corpus" (`SEAM_AUTOTRAINING_PLAN.md:86,188`); disk has **30** `_corpus` skeletons. Exec plan correctly says 30+19. RESULT_7's "n=100" is 100 *freshly generated* protocols, not a stored corpus. Reconcile the strategy doc.
- **m2 (repair generalization).** The validator error space the repairer trains on is only **5–7 mutation classes** (`integration_stress.MUTATIONS` = 5; `mutate_protocol.OPERATORS` = 7). R may not generalize to validator errors outside this hand-authored set; report R's fix-rate on *held-out error types*, not just held-out protocols.
- **m3 (eval fairness).** best-of-k (S2) vs 3-round repair (S3) spend different token budgets; the plan *does* carry tokens/$-to-accepted columns, so it's not fatal, but never present validity@k next to repair@3 as a headline without the cost columns in the same table.
- **m4 (hypothesis lawyering).** H1 "semantic validity within ±2 pts of unconstrained" is ill-defined when the *unconstrained* 7B emits non-parsing output (is a syntax-fail counted as semantic-invalid? then GCD "wins" by construction) and its split is unstated. H3's "−10 pts" slack lets an SFT model that is *worse* than zero-shot Sonnet be reported as a pass. H4's "+10 pts validity@1" collides with the validity ceiling implied by a successful H3 — if SFT reaches ~90%, +10 is near-impossible, so a good SFT makes GRPO look like a failure by arithmetic. Tighten each to name split, measurement, and ceiling handling.
- **m5 (doc hygiene).** Acronym drift: RESULT_9 expands STJP as "Session-Typed Judge Panel." Cosmetic but confusing in a benchmark release.

---

## Findings the planner can fairly rebut (noted for completeness)
- Pure T2 mode-collapse "regardless of intent" is partially blunted because T2 GRPO prompts come from the synthetic `train` split which *has* gold, so the bisim term does tie to intent — but B2 stands because that term is binary/sparse and brevity still wins the gradient.
- Payload sanitization (§5.2, stripping comments/canonicalizing) is a genuinely strong anti-smuggling control; the collusion/canary battery (§5.5) is well-designed. The judge *isolation* story is solid — the weakness is *circularity of the calibration data* (M2), not the isolation mechanics.
- Cost envelope (<$1k) is plausible for API+SFT; the risk is wall-clock/throughput (M4) and lost-state (M5), not dollars.
