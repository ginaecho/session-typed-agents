# How to implement subsessions (child protocols) — modular SOP compilation and incremental adaptation

How STJP factors a large standing policy (an SOP, a handbook, a blueprint)
into reusable **child protocols**, recompiles only what a policy change
touches, and proves what each step does and does not guarantee. This is the
design + implementation document behind
[`HOW_TO_RUN_BENCHMARKS.md`](HOW_TO_RUN_BENCHMARKS.md) §9 (the Level-1 /
cost-of-change rules).

Scope note on the word "subsession": in this document it means **nested
protocol invocation** — an `aux global protocol` child invoked with `do` —
NOT higher-order session delegation (a session carried as a payload), which
is documented separately in
[`SCRIBBLE_EXTENSIONS.md`](SCRIBBLE_EXTENSIONS.md) §4.
[`SCRIBBLE_EXTENSIONS.md`](SCRIBBLE_EXTENSIONS.md) §3 documents the
composition *mechanics* (native `aux`+`do`, cross-file `// @use`); this
document is the *operational design* on top of them: the authoring
convention, the change workflow, the artifact hashing, the verified gaps
that must be fixed first, and the exact theory claims that are and are not
licensed. Drafted 2026-08-03; every "verified" mark below was checked
against the code on that date.

## Menu

- [1. What exists today (verified)](#1-what-exists-today-verified)
- [2. What the theory licenses — and the claims never to make](#2-what-the-theory-licenses--and-the-claims-never-to-make)
- [3. Phase 0 — the verified gaps that block benchmark use](#3-phase-0--the-verified-gaps-that-block-benchmark-use)
- [4. Authoring convention — SOP to module tree](#4-authoring-convention--sop-to-module-tree)
- [5. The change workflow](#5-the-change-workflow)
- [6. The complete per-role artifact hash H_r](#6-the-complete-per-role-artifact-hash-h_r)
- [7. Goal provenance records](#7-goal-provenance-records)
- [8. Benchmark integration](#8-benchmark-integration)
- [9. Phasing](#9-phasing)

---

## 1. What exists today (verified)

| Capability | Status | Where | Verified how |
|---|---|---|---|
| Native `aux global protocol` + `do` (role substitution at projection) | shipped (stock Scribble) | vendored `scribble-java/` (`STypeInliner`) | grammar + own test corpus use `do` |
| Projection of a composed protocol | shipped | `stjp_core/compiler/efsm_parser.py` — `get_all_efsms` shells out to the scribble-java CLI per role, so `do` is inlined by stock Scribble **before** the EFSM reaches Python | read `get_efsm_from_scribble` |
| Cross-file `// @use` composition (splice + revalidate) | shipped | `stjp_core/compiler/composer.py` (`compose_and_validate`; error classes `ResolutionError` / `RoleMappingError` / `CompositionError`) | read in full |
| Incremental extension pipeline (child cached by hash → deterministic parent extension → compose+validate whole → per-role EFSM diff → regenerate changed roles only) | prototype | `stjp_core/compiler/incremental.py` (`add_subprotocol`; `timings_ms` recorded per step) | read in full |
| Tests: child cache, invalid child rejected standalone, new/changed/unchanged role diff, artifacts only for affected roles, generated monitor verdicts | present | `stjp_core/tests/test_incremental.py` | read |
| Subtype checker (paper's E9a; supersedes the "not built" note in `SCRIBBLE_EXTENSIONS.md` §5, dated 2026-05-20). Implemented relation: **synchronous** subtyping by coinductive simulation, payload sorts exact-match only (flat lattice v1), plus ONE bounded asynchronous fragment (independent-receive output anticipation). NOT the full precise asynchronous relation — its own docstring says so. | shipped (scoped) | `stjp_core/compiler/check_subtype.py` | read |
| Worked example (banking + audit children composed into a pipeline root) | present | `experiments/cases/composition/pipeline/FinancePipeline.scr` (+ `_composed.scr`) | read |

Two facts worth stating because they decide the design:

- **Projection needs no preprocessing for `do`.** The projection path goes
  through stock scribble-java, which inlines child protocols itself. Only the
  *Python-side message-level consumers* are blind to `do` — see Gap 4.
- **The incremental pipeline's conservatism is correct.** It validates the
  composed whole every time (step 3) rather than trusting per-child
  verification to compose. Keep that; projection-preserving composition
  without whole-root revalidation is Hybrid MPST (Gheri–Yoshida OOPSLA'23)
  and remains roadmap, not implemented.

## 2. What the theory licenses — and the claims never to make

Each mechanism below is licensed by a specific result. State only what the
result states.

**Global-to-local projection (standard MPST).** For a well-formed composed
global protocol G, projection yields per-role local types with communication
safety, session fidelity, and progress under the standard assumptions. The
update rule this licenses: *after the composed root changes and passes
validation, regenerate its affected projections — never hand-patch a local
contract.*

**Subprotocol invocation (nested protocols, Demangeon–Honda CONCUR'12;
Scribble `aux` + `do`).** A validated child is reusable under different role
mappings. What it does NOT license: a child valid alone does not make every
parent composition valid. That is why step 3 (compose + validate the whole)
is the permanent safety net, and why the child-hash cache is an
*engineering* optimization (skip re-checking an unchanged child standalone),
not a compositional-soundness theorem.

**Local↔global correspondence (Deniélou–Yoshida ESOP'12; paper §3.2 [27]).**
Under well-formedness, composing the projected EFSMs recovers the behaviors
of G. Downward, this licenses change-impact analysis by EFSM diff. Upward
(local-to-global synthesis), it holds only under multiparty-compatibility /
realizability conditions: use synthesis as a *compatibility check or
recovery tool* (e.g. an amendment arriving as one team's role-local practice
change; the mining pipeline), never as the normal SOP-authoring path.
Arbitrary independently edited locals may disagree on labels or direction,
orphan messages, introduce circular waits, or hide choices from affected
roles — no global type exists for them, and the tool must say so by name.

**Subtyping (paper E9, `check_subtype.py`).** Two DIFFERENT questions — do
not conflate them:

- (a) *Protocol fixed, implementation changed:* a new implementation whose
  type is a subtype of the role's projection is safe (substitutability).
- (b) *Protocol changed, deployed agent kept:* the deployed contract must be
  checked against the NEW projection (deployed ≤ new projection). This is
  the SOP-update question, and the shipped lean ≤ projection check is this
  shape.

Getting the direction backwards approves unsafe keeps. Every use of the
checker in the change workflow must name which question it is answering —
AND which relation is deciding it. The implemented relation is scoped:
synchronous simulation with exact-match payload sorts, plus the one bounded
anticipation fragment (full asynchronous subtyping is undecidable; the
theory is Chen–Dezani–Scalas–Yoshida LMCS'17 / PPDP'24, but the code
implements a sound fragment of it, not the full precise relation). Any
change outside that fragment gets NO subtype exemption: full whole-root
revalidation plus contract/monitor regeneration, no shortcut.

**Claims never to make** (each has tempted someone already):

- "Every valid child composes safely with every parent." (False — whole-root
  revalidation exists because of this.)
- "Local contracts can always be recomposed into a global type." (Only under
  compatibility conditions.)
- "An unchanged EFSM means an unchanged policy." (False TODAY in code — see
  Gap 1. A threshold-only guard change leaves the EFSM identical.)
- "Scribble itself provides incremental validation." (It does not; the
  incremental behavior is this project's layer.)
- "Adding a compile-time role is justified by dynamic-role-join theory."
  (Dynamic multirole [POPL'11] is about runtime join/leave; adding a role to
  the source and revalidating is ordinary recompilation.)
- "SOP updates are fast." (A timing claim: measure dependency-scoped vs
  full-build on the same machine, and report the LLM re-drafting cost —
  which dominates — separately from the deterministic recheck cost.
  `incremental.py` already records `timings_ms` per step.)

## 3. Phase 0 — the verified gaps that block benchmark use

Each gap below was verified in code on 2026-08-03. **No Level-1 or
cost-of-change benchmark run may launch before all four are closed**,
because each one silently corrupts results in the treatment arm's favor —
the worst direction.

### Gap 1 — the change signature is structural-only (stale-guard misclassification)

`efsm_signature` (`incremental.py:207-226`) hashes only
`(state, direction, peer, label, payload_type, target)`. Refinement
predicates, choice guards, ledger invariants, `.fail` handlers, and goal
mappings are invisible to it. Consequence: a threshold-only policy change
(`$50K → $75K`) leaves every EFSM identical, every role is classified
"unchanged", and **no monitor is regenerated — the gate keeps enforcing the
old policy while reporting zero violations.** For the benchmark this is a
false-safe result. (This failure class already burned us once: the
memory_race `.refn` file that parsed to empty, runbook §8.6.)

Fix: a role's change status is decided by the complete RUNTIME artifact
hash H_r^runtime (§6), never by the EFSM signature alone.

### Gap 2 — sidecars are invisible to composition

Two halves, same root cause:

- `child_fingerprint` (`incremental.py:79-82`) hashes only the child's
  whitespace-canonicalized `.scr` text. A child whose `.refn` or `.fail`
  sidecar changed is a cache hit.
- Step 5 loads refinements from the **original parent path**
  (`incremental.py:408`) — a child's own sidecars are silently dropped from
  every regenerated monitor.

Fix: a **sidecar composer** alongside `composer.py` — resolve the same
`@use` graph, remap each child sidecar's `(sender, receiver, label)` keys
through the `do`-call's role binding, emit `composed.refn` /
`composed.fail` next to the composed `.scr`, and load monitors from the
composed sidecars. The child fingerprint becomes
`H(child.scr + child.refn + child.fail)`. Remapping alone is NOT enough:
sidecar entries need a call-site namespace. The same child instantiated
twice under different bindings yields two distinct remapped guard sets; two
instantiations under the SAME binding — or two different children that
happen to use the same `(sender, receiver, label)` triple after remapping —
would collide on the bare key. Every composed sidecar entry therefore
carries a call-site id (root + `do`-call ordinal), and the monitor evaluates
guards per call site, not per bare triple.

### Gap 3 — two lean-contract generators exist

`incremental.py::_contract_markdown` (lines 264-292) emits states + actions
only — **no "Payload guards (HARD)" list, no DECISION RULE lines** — while
the benchmark arm's actual prompt comes from
`experiments/baselines/instructions.py::build_spec_minimal_instructions`,
which includes both. If incremental regeneration ever feeds a benchmark run,
post-change trials would silently use a different prompt format than
pre-change trials — a confound that invalidates every before/after
comparison, and a safety regression (the regenerated contract omits the
guards).

Fix: one lean-contract builder, single source of truth. Either
`incremental.py` imports and calls the instructions builder, or the shared
core moves into `stjp_core/` and `instructions.py` consumes it. The
persisted-prompt SHA discipline (experiments policy: changed builder ⇒
changed SHA ⇒ runs no longer comparable) then applies automatically.

### Gap 4 — message-level consumers cannot see through `do`

`stjp_core/compiler/protocol_parser.py` has no `do` handling. Projection is
unaffected (scribble-java inlines), but every consumer of
`parse_protocol_file(...).messages` sees only the root's top-level messages
on a composed protocol: the setting-3 paraphrase
(`_paraphrase_global_protocol` in `instructions.py`), and
`re_anchor_goals.py::_valid_edges` (which would then reject valid anchors
into child interactions). Silent incompleteness in both.

Fix: a message-level expansion pass — expand `do` calls using the `aux`
blocks present in the composed file (they are all in one file after
`composer.py` runs) — applied for these consumers only. Non-recursive
subprotocol expansion is deterministic and semantics-preserving.

### Phase-0 exit tests (add before anything else)

1. **Stale-guard canary:** compose, change ONLY a `.refn` threshold in a
   child, re-run the incremental pipeline, and assert the affected role is
   classified CHANGED and its regenerated monitor rejects a payload value
   between the old and new thresholds.
2. **Sidecar-drop canary:** a child with its own `.refn` composed into a
   parent; assert the composed monitor enforces the child's guard under the
   remapped role names, twice under two different bindings.
3. **Single-builder check:** assert the incremental path's regenerated
   contract is byte-identical to `build_spec_minimal_instructions` output
   for the same EFSM + refinements.
4. **See-through-`do` check:** assert `_valid_edges` and the paraphrase on
   `FinancePipeline_composed.scr` contain the banking/audit child messages.

## 4. Authoring convention — SOP to module tree

- **Source-visible sections are the DEFAULT decomposition evidence — the
  mapping is many-to-many, not one-to-one.** Real SOP workflows cross-cut
  sections: one procedure hinges on authorities defined in one section,
  channels in another, templates in a third (the HANDBOOK.md anatomy). So a
  clause may feed several modules, a module may draw on several sections,
  and a workflow root composes whichever modules it needs. The fairness
  rule stands unchanged (runbook §9.6): the section structure is free
  because every setting sees it in the document itself; any merge or split
  BEYOND that visible structure is compile work — LLM-done, logged in the
  manifest, charged to the compile bill. The clause ledger (§7) records the
  actual clause↔module↔goal mapping either way, so auditability does not
  depend on the mapping being simple.
- **One root per use-case** (per immediate-request family), composing
  children with `do`. Small cases may keep children as same-file `aux`
  blocks; SOP-scale cases use cross-file `// @use` so sections are owned and
  versioned independently.
- **A module manifest** (JSON, content-addressed) records per module:
  protocol source hash, sidecar hashes (`.refn`, `.fail`), semantic-goal
  hash, role-interface hash, child dependency hashes, per-role artifact
  hashes H_r, and the caller list (which roots `do` this module). The
  manifest is what makes "find every transitive caller" (§5 step 3) a
  lookup instead of a search, and what feeds the policy-version provenance
  line (runbook §7.8).
- **The clause ledger lives in the goal provenance records** (§7): each goal
  names its source section, and each section maps to its child protocol —
  section ↔ child ↔ goals, auditable in both directions.

## 5. The change workflow

When a policy module changes:

1. **Classify the change** (table below).
2. **Validate the changed child standalone** where meaningful
   (`validate_child_once` — cache keyed by the Gap-2-fixed fingerprint).
3. **Find every transitive caller** from the module manifest.
4. **Instantiate the child under each caller's role mapping** (including
   sidecar key remapping).
5. **Compose and Scribble-validate each affected root** (the permanent
   safety net — never skipped).
6. **Re-project the affected roots** (`get_all_efsms`).
7. **Compare complete per-role RUNTIME artifact hashes H_r^runtime** (§6) —
   never the EFSM signature alone, and never the evaluation hash (goal
   re-anchoring must not regenerate prompts).
8. **Regenerate contracts and monitors only for roles whose H_r^runtime
   changed**, using the single lean-contract builder (Gap 3).
9. **Re-run goal-to-protocol traceability** (§7): every provenance-carrying
   goal must re-anchor onto the new composed root under the invariance guard
   (relabeling free; predicate changes are errors unless a payload-type
   change forced a translation, which requires human sign-off). This updates
   H^evaluation only — it never touches a contract or monitor.
10. **Delta re-endorsement + effective-time rule:** the human endorses the
    changed module and the change-impact report (which roles changed, which
    kept their contracts by H_r^runtime, which kept them by an explicit
    subtype check — question (b) of §2, scoped to the implemented relation),
    not the whole G — AND declares the amendment's effective-time rule for
    in-flight sessions: *grandfather* (running sessions finish under the old
    version, version-stamped), *next safe boundary* (apply at a subprotocol
    call boundary), or *immediate typed abort* (E10) plus recompile.
    Immediate in-flight migration is not currently supported — never claim
    it. An authoritative emergency amendment may make continuing under the
    old policy unsafe; that is exactly what the abort option is for, and the
    choice is per-amendment, pre-registered in benchmark runs (runbook
    §9.9). Record all new hashes in the manifest.

"Quickly" means **dependency-scoped recompilation** — steps 2–8 touch only
the changed module's transitive callers — never skipped validation.

### Change classes

| SOP change | Required action |
|---|---|
| Wording only, semantics unchanged | No semantic-hash oracle exists for prose: route through the clause ledger / equivalence instruments; anything they cannot decide escalates to the human gate. Never let a "normalizer" become an unaudited judge. |
| Threshold change (e.g. `$50K → $75K`) | Sidecar + monitor + contract + goal-oracle regeneration for the guard-owning role(s); EFSM unchanged is EXPECTED and irrelevant (Gap 1). Stale-guard canary mandatory. |
| Authorized role changes | Revalidate role mapping, affected roots, projections, capability grants. |
| New approval step | Compose child, validate affected roots, re-project, regenerate changed roles. |
| Message reordering | Full affected-root Scribble validation. |
| New branch | Validate projectability + informed-choice (merge) requirements. |
| Remove obligation | Revalidate goals; a "still compatible" claim requires the explicit subtype check (question (b)) INSIDE the implemented relation (§2 — synchronous + exact sorts + anticipation fragment); outside it, full revalidation + regeneration. |
| Add optional safe behavior | Prove it within the implemented subtype relation or revalidate the composed roots — no exemption from a relation the code does not implement. |
| Payload-type change | Forces goal-predicate translation → human sign-off path (answer-key invariance guard). |
| Terminal-label change | Also update `case.yaml` `terminal_label` and re-derive everything that consumes it (runbook §8.8: derive, never hardcode). |
| Add role (compile time) | Update root role interface, revalidate; this is ordinary recompilation, NOT runtime dynamic join. |
| Change failure handling | Revalidate `.fail` handlers as mini global types (E10 pipeline) and every affected recovery path. |

## 6. The per-role artifact hashes — runtime vs evaluation, kept apart

Two hashes, two jobs. Mixing them was an error in an earlier draft of this
document: goals are HIDDEN evaluation artifacts (runbook §9.3), so
re-anchoring the rubric must never regenerate a participant prompt or a
monitor — otherwise evaluation maintenance leaks into runtime behavior and
the identical-prompt controls break.

**Runtime hash — the only thing that drives regeneration.** A role's
contract and monitor regenerate iff this changes:

```
H_r^runtime = H( efsm_signature(M_r),
                 refinements_r,        # remapped, composed .refn slice for r (per call site)
                 choice_guards_r,
                 ledger_invariants_r,  # stateful session-ledger clauses touching r
                 fail_handlers_r,      # composed .fail slice for r
                 capabilities_r )      # derived tool/permission list
```

**Evaluation hash — version-stamps the exam, regenerates nothing at
runtime:**

```
H^evaluation = H( goals + provenance records,
                  protocol mappings (re-anchoring output),
                  safety policies,
                  world-state oracles )
```

The EFSM signature is one component of H_r^runtime, never the decision.
Consequences:

- A threshold-only change flips `refinements_r` → role CHANGED → monitor and
  contract regenerate (closes Gap 1).
- Re-anchoring goals after a relabeling flips H^evaluation only → zero
  contracts touched, zero monitors touched, prompts byte-stable.
- The exception that proves the split: if a goal obligation is compiled INTO
  the runtime (a guard, a goal marker appearing in a contract), that
  compiled form lives in `refinements_r`/`choice_guards_r` and is already
  covered by H_r^runtime — as a runtime artifact, not as a rubric entry.
- Both hashes live in the module manifest, which also computes one
  **manifest root hash** committing to everything (protocol, sidecars,
  contracts, monitors, policies, oracles — i.e., all `H_r^runtime` plus
  `H^evaluation`). The cross-layer consistency check (§8) requires both to
  derive from one module version before grading; the policy-version
  provenance line (runbook §7.8) prints the root hash, with components in
  run metadata.

## 7. Goal provenance records — integrating the goal-quality framework

Goals are hidden evaluation artifacts distilled from the SOURCE (standing
policy P + immediate request R), never from the protocol — runbook §9 rules
3–4. This section does NOT invent a new goal model: it extends the one the
repo already audited into shape in
[`GOAL_QUALITY_AUDIT.md`](GOAL_QUALITY_AUDIT.md), whose findings are binding
here — existential goals cannot express safety (its B2), message-shape
predicates prove conversations not accomplishments (its A1), and a goal
every arm passes measures nothing (its A2 discrimination gate,
`goal_quality.py`). A Level-1 case therefore carries the full instrument
stack: **achievement goals** + **safety policies** (ordering / at-most-once
/ prohibited-action, scored by `policy_eval.py` over the Critic) +
**world-state oracles** where an environment E exists (the
`memory_race/environment.py` precedent — replay the trace against a real
store, assert final state no payload can fake).

Each criterion records where it came from and how, so two different claims
stay auditable: **compilation fidelity** (did the protocol preserve the
source policy?) and **execution compliance** (did the runtime follow the
endorsed protocol?). The PRIMARY check is the arm-independent verifier;
the protocol mapping is SECONDARY, used for conformance scoring and
compiled guards only — an intent-only condition can never be required to
guess private labels (the strict-vs-role_pair discipline, generalized).

```yaml
goal_id: G2
semantic_obligation: "Deployment requires approved review and green tests."
kind: achievement            # achievement | safety_policy | world_state
prohibited: false            # true = asserts the forbidden outcome did NOT occur
source:
  artifact: standing_policy.md
  section: "Release authorization"      # ties into the module tree (§4)
  quote: "..."
  content_hash: "..."
extraction:
  method: llm                # or "human"
  model: "..."
  prompt_hash: "..."
  raw_response_hash: "..."
human_status: approved       # pending | approved | rejected
verifier:                    # PRIMARY — label-independent, never meaning-independent
  semantic_event: review_approved      # entry in the case's arm-independent event ontology
  actors: {from_role: Reviewer, to_role: Orchestrator}   # roles + direction
  evidence:                  # structured proof this WAS that semantic event —
    action_type: approval    # a random Reviewer->Orchestrator message never counts
    decision: approved
  ordering: "approval precedes tests_passed precedes deployed"
  authorization:             # when the clause is an authority rule
    issuer: "HR Director | Employee Relations Specialist"
    subject: "employee under offboarding"
    action: involuntary_termination
    scope: "..."
    valid_within: "..."      # validity window for the authorizing evidence
  data:                      # when the clause pins data correctness
    evidence: trusted_tool_read        # oracle evidence, never the agent's claim
    cardinality: {expected: 3}
    schema: {columns: [...], types: [...], nullable: [...]}
    hashes: {source: "...", version: "...", query: "...", result: "..."}
  world_state:               # final-state assertions (requires environment E)
    assert: "calendar.event_count == 286"
    no_extra_side_effects: true        # exact-count / untouched-rows invariants
  conditional: "revenue > 50000 => audit branch obligations apply"
protocol_mapping:            # SECONDARY — conformance + compiled guards only
  protocol_hash: "..."       # the composed root this anchors onto
  events:
    - Reviewer -> Orchestrator : PlanApproved
    - BrowserTester -> Orchestrator : TestsPassed
    - DevOps -> Orchestrator : Deployed
predicate: "..."             # legacy payload predicate, where still applicable
```

Rules:

- **The verifier grades every condition through the case's semantic-event
  ontology; exact labels grade only protocol-aware conditions.** The rule is
  label-independent, never meaning-independent: a bare role-pair match is
  too permissive when the same pair exchanges several kinds of messages, so
  each criterion names a `semantic_event` and the structured `evidence` that
  identifies it. Each runtime maps its observable actions onto the ontology:
  intent-only conditions via structured action/tool/world-state evidence,
  protocol-aware conditions via the canonical message mapping
  (`protocol_mapping`), and ALL conditions via final-state evidence where an
  environment exists. Sender/receiver roles, authorization direction,
  ordering, values, and world state stay invariant wherever the source
  clause semantically requires them; labels do not.
- `protocol_mapping` is the only part that changes on re-anchoring; the
  invariance guard (`re_anchor_goals.py --check` discipline) refuses any
  `verifier`/`predicate` change without a forced payload-type translation
  plus human sign-off. Re-anchoring updates H^evaluation only (§6).
- A criterion whose `source` clause the compiler failed to capture still
  grades every setting — including full STJP, which then fails it. That
  asymmetry is the point (runbook §9.4).
- Every case's criterion set must pass the discrimination gate
  (`goal_quality.py`): a criterion every condition passes, or none passes,
  is flagged non-informative.
- Scope note, stated honestly: `world_state` assertions require a real
  environment E. The current Level-2 cases are toolless (payloads are pure
  LLM output — GOAL_QUALITY_AUDIT A1), so world-state oracles arrive with
  the Level-1 environments; `memory_race` is the shipped precedent, not the
  exception.

## 8. Benchmark integration

Everything here restates runbook §9 obligations in implementation terms:

- **Version stamping:** every run's metadata records
  `(protocol_hash, refn_hash, fail_hash, goals_hash, per-role contract
  hashes, monitor hashes)` plus the **manifest root hash** over all of them.
  `evaluate_run` refuses to grade when they do not all derive from one
  module version (the cross-layer consistency check). Report tables carry
  the root hash in the provenance line (runbook §7.8) and never mix
  versions.
- **Stale-guard canary:** every cost-of-change experiment includes a seeded
  trial whose payload value lies between the old and new thresholds; the
  graded outcome proves which policy version judged the run.
- **Amendment kinds (i)/(ii)/(iii)** and their reporting obligations:
  runbook §9.9. Kind (ii) — the conflicting amendment rejected at
  revalidation with a named counterexample — is this machinery's headline
  safety claim; kind (iii) — mid-horizon amendments where in-context
  baselines may adapt and compiled systems must abort-and-recompile — is
  the honest-loss case, reported, not designed out.
- **Timing claims:** dependency-scoped vs full-build recompile measured on
  the same machine (`timings_ms` already exists per step); LLM re-drafting
  cost reported separately from deterministic recheck cost.
- **Contracts feed the benchmark through the one builder** (Gap 3), so
  pre-change and post-change prompts differ only where the policy differs,
  and the persisted-prompt SHA discipline detects everything else.

## 9. Phasing

| Phase | Content | Touches |
|---|---|---|
| **0** | Close Gaps 1–4 (+ the four exit tests). H_r^runtime / H^evaluation split; sidecar composer (call-site namespaced); single contract builder; `do`-expansion for message-level consumers. | Primarily `stjp_core/compiler/`; plus the shared-builder touch point in `experiments/baselines/instructions.py` (Gap 3) and the `do`-aware consumers `instructions.py` paraphrase + `re_anchor_goals.py` (Gap 4). No cases, no runs. |
| **1** | Big-intent case schema: P/R/E artifacts with hashes, module manifest, goal provenance records, two-sided goal sets. New `case.yaml` schema version; new case directories only. | `experiments/` schema + `case_loader.py` |
| **2** | Level-1 end-to-end experiment: one delivery channel for P, retrieval-equipped baseline (pre-registered budget), compile cost + amortization reporting. | new cases + runbook §9 rules |
| **3** | Cost-of-change experiment: amendment kinds (i)/(ii)/(iii), canary trials, version-stamped tables. | after 0–2 |

Nothing in any phase modifies existing Level-2 cases, their runs, or their
reports; those stay frozen and citable under the runbook §9 scope statement.
The running campaign is untouched.
