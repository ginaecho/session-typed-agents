# Change-Request-Driven Protocol Evolution

How STJP absorbs a change request — an email asking to add an interaction, a
policy, or a condition to an already-encoded workflow — into an **updated,
re-validated global type**, by treating the change as a **sub-session (child
protocol)** composed with the retained parts of the current protocol.

Drafted 2026-05-21. Companion: `SCRIBBLE_EXTENSIONS.md` (the layering),
`ROADMAP.md` (Phase 3.1 Hybrid MPST), `RESEARCH.md` (bibliography).

> **Status 2026-06-12** — this concept now has a concrete benchmark/demo
> design: `docs/EVOLUTION_DEMO_DESIGN.md` ("the demand changed on Tuesday",
> banking + new ComplianceScreen role; metrics: disaster rate, half-landing
> rate (trials where the new obligation fired on some but not all triggering
> branches), regression rate, turnaround, blast radius). Not yet built; build
> plan in that doc.

---

## 1. The challenge (`zim_example.png`)

The figure shows an **Agentic Corrector**: a two-phase system.

- **Build (offline)** — SOP / policy documents are ingested and *encoded* into
  a structured per-scenario workflow ("Encoded Logic per Scenario"); an SME
  validates and deploys it.
- **Runtime** — an incoming request email is classified, the matching encoded
  workflow is selected, its steps run (automated checks, manual approvals),
  and a correction is implemented.

The encoded workflow is a **multi-party interaction** — classifier, corrector,
approver(s), auditor — i.e. exactly a **global session type**.

The problem this extension targets: **the encoded workflow is not static.**
Humans email change requests *about the workflow itself* —

> *"From now on, corrections above $10k also need a compliance review before
> the fix is applied."*
> *"Add a second approver for the refund scenario."*
> *"Drop the manual double-check on address corrections."*

Today that means re-running the offline encode + a full SME re-validation. The
goal: turn a change-request email directly into an updated, **provably
well-formed** global type — folding the new interactions/policies/conditions
in, and **keeping the old ones that still apply** — without regenerating the
whole workflow from scratch.

---

## 2. The capability

```
change-request email
      │
      ▼  classify          what does the request keep / add / modify / remove?
  ChangeSet
      │
      ▼  the ADDED interactions become a child sub-protocol
  child  aux global protocol  +  updated parent that `// @use`s and `do`s it
      │
      ▼  compose + Scribble-validate
  evolved global type   (well-formed, deadlock-free, branch-complete)
```

A change is a **composable delta**, not a rewrite. The retained interactions
stay verbatim; the new ones arrive as a nested child protocol; Scribble
re-checks the whole for safety.

---

## 3. Why sub-sessions — the theory

A change request adds *a bounded piece of new interaction* to an existing
protocol. That is precisely what nested / sub-session session types model.

- **Demangeon & Honda — *Nested Protocols in Session Types* (CONCUR'12).**
  An `aux global protocol` can be invoked with `do` from inside a parent. A
  change request → a new `aux` protocol; the evolved parent `do`s it. STJP
  already ships the cross-file form of this in `compiler/composer.py`
  (`// @use` directives — see `SCRIBBLE_EXTENSIONS.md` §3).
- **Gheri & Yoshida — *Hybrid Multiparty Session Types* (OOPSLA'23).**
  *Projection-preserving* composition: a child protocol verified **once** can
  be composed into many parents without re-projecting the whole. This is the
  Phase-3 target — it makes evolution *pay-once-per-change* instead of
  *re-verify-everything*.
- **Anderson & Rathke — *Dynamically Updatable MPST* (Oxford).**
  Protocol *upgrades* applied to a **live** session — graceful migration of
  in-flight interactions from v1 to v2. This is the runtime half of the story
  (changing a workflow while instances of it are mid-run); STJP's current
  scope is build-time evolution, with this as the documented next step.
- **Subtyping** (Gay-Hole 2005; Chen-Dezani-Padovani-Yoshida LMCS'17) answers
  *"is the evolved v2 a safe drop-in for v1?"* — `ROADMAP.md` §2.2.

So: nested protocols give the *mechanism*, Hybrid MPST gives *cheap* re-use,
dynamic-update MPST gives *live* migration, subtyping gives the *safety check*.

---

## 4. The mechanism

### 4.1 Classify — the change request → a `ChangeSet`

An LLM reads the change-request email **against the current protocol** and
emits a structured delta:

| field | meaning |
|---|---|
| `keep` | existing interactions the request leaves in force (retained verbatim) |
| `add` | new interactions / policy steps / conditions the request introduces |
| `modify` | existing interactions whose shape or payload constraint changes |
| `remove` | interactions the request retires |

Each item is a one-line natural-language description, anchored where possible
to a `(sender, receiver, label)` of the current protocol.

### 4.2 The `add` items → a child sub-protocol

The added interactions are authored as a Scribble **`aux global protocol`** —
a self-contained child. Example, for the "compliance review" request:

```scribble
aux global protocol ComplianceReview(role Corrector, role ComplianceOfficer) {
    ReviewRequest(Double) from Corrector to ComplianceOfficer;
    ReviewVerdict(String) from ComplianceOfficer to Corrector;
}
```

### 4.3 Compose — retain + insert

The evolved parent (`v2`) keeps the original protocol body (the `keep` items
unchanged) and gains a `// @use` directive plus a `do` call at the point the
request specifies:

```scribble
// @use ComplianceReview from "compliance_review.scr";

global protocol EncodingCorrection(role Classifier, role Corrector,
                                    role ComplianceOfficer, role Auditor) {
    ... retained interactions ...
    do ComplianceReview(Corrector, ComplianceOfficer);   // <- the change
    ... retained interactions ...
}
```

`compiler/composer.py` resolves the `// @use`, splices the child's `aux` block
in, and runs the whole through the Scribble compiler. If Scribble accepts it,
the evolved global type is **well-formed, deadlock-free, branch-complete** —
by the same Honda-Yoshida-Carbone theorem the rest of STJP rests on. If
Scribble rejects it, the error is fed back to the LLM and the draft retried
(the `architect`-style fix loop).

### 4.4 Re-project, re-generate

Once the evolved `.scr` validates, the standard STJP pipeline takes over:
project per role (`compiler/efsm_parser.py`), regenerate skills/agents
(`generation/`), regenerate monitors (`monitor/`). The change has propagated
end to end.

---

## 5. What is tractable now vs. Phase 3

### Built — the tractable slice (`stjp_core/authoring/change_request.py`)

- `classify_change_request()` — email → `ChangeSet` (LLM, with a mock mode).
- `evolve_protocol()` — classify → draft the `add` items as a child
  `aux global protocol` → build the evolved parent → `composer.compose_and_
  validate()` → fix loop → validated evolved `.scr`.
- Handles the **common case — a request that ADDS** interactions / policies /
  conditions (with `keep` retained). This is *lexical* sub-session
  composition: the evolved whole is **re-projected and re-validated** each time.
- `modify` / `remove` are surfaced in the `ChangeSet` but fall back to the
  full-regeneration path (`authoring/evolution_loop.py`) — editing or deleting
  an existing interaction is not a pure composition.

### Built 2026-07-04 — the incremental slice (`stjp_core/compiler/incremental.py`)

The deterministic engine under the change-request flow, realizing the
pay-once-per-change discipline in engineering form:

- **Child verified once** — `validate_child_once()` checks the child
  `aux global protocol` standalone (promoted to a scratch global) and caches
  the verdict by content hash (`.stjp_child_cache.json`). Re-adding the same
  child to another parent is a cache hit — the Gheri-Yoshida OOPSLA'23
  verify-once idea, with the full compose+validate kept as the safety net.
- **Deterministic extension** — `extend_parent_text()` inserts the
  `// @use` + `do Child(roles);` at a named anchor (`end` / `start` /
  `after:<Label>` / `before:<Label>`) and declares any NEW roles in the
  parent header (the Deniélou-Yoshida POPL'11 dynamic-role case). No LLM is
  involved when the child already exists.
- **Incremental re-projection** — `incremental_project()` diffs each role's
  new EFSM against the old one by canonical signature; only roles whose
  local type actually changed are re-projected.
- **Regenerate only the blast radius** — changed/new roles get a fresh local
  contract markdown + a STANDALONE monitor script
  (`generation/monitor_codegen.py`: dependency-free Python embedding the
  EFSM + refinements — deterministic code, droppable next to any runtime).
  Unchanged roles keep their artifacts untouched.

```bash
python -m stjp_core.compiler.incremental \
    --parent v1.scr --child compliance_child.scr \
    --roles Corrector,ComplianceOfficer --at after:ClassifiedRequest -o out/
# EXTENDED with ComplianceReview (child verified) — re-projected 2 role(s)
# ['ComplianceOfficer', 'Corrector'], kept 2 unchanged ['Auditor', 'Classifier']
```

Tests: `stjp_core/tests/test_incremental.py` (child cache, unsafe child
rejected standalone, end-to-end extension with projection diff, generated
monitor verdicts on good/bad traces, anchor/arity errors, determinism).

### Phase 3 — designed, not built

- **Projection-preserving composition, formally** (Gheri-Yoshida OOPSLA'23):
  today the composed whole is still re-validated (conservative); adopting the
  compatibility relation itself would let the re-check be skipped with a
  proof rather than a cache.
- **Dynamically-updatable MPST** (Anderson-Rathke): apply the change to a
  **live** workflow instance, migrating in-flight interactions v1 → v2.
- **Subtyping safety gate** (`ROADMAP.md` §2.2): before deploying v2, prove
  `v2 ≤ v1` (or report exactly where it is not) — so a change can be
  classified *safe drop-in* vs *breaking*.

---

## 6. Worked example — the encoding corrector

**Current workflow** `EncodingCorrection` (v1): `Classifier` routes a request
to `Corrector`, who applies the fix and reports to `Auditor`.

**Change-request email:**
> "Corrections of $10,000 or more must get a compliance review before the fix
> is applied. Everything else stays as it is."

**Classify →** `ChangeSet`:
- `keep`: classify the request; corrector applies the fix; auditor logs it.
- `add`: a compliance review (Corrector ↔ ComplianceOfficer) that must happen
  **before** the fix, for high-value corrections.
- `modify`: —  `remove`: —

**Child sub-protocol** `ComplianceReview` — the `add` items (see §4.2).

**Evolved parent** v2 — the v1 body with `do ComplianceReview(...)` inserted
before the fix step, plus the `// @use` (see §4.3).

**Compose + validate →** Scribble accepts it → `EncodingCorrection` v2 is a
well-formed global type. The compliance review is now a first-class,
verified part of the workflow — and the SME validates a *diff* (one child
protocol) instead of re-reading the whole encoded flow.

---

## 7. Honest scope

- The tractable slice covers **additive** change requests via lexical
  composition; it **re-projects and re-validates the whole** evolved protocol
  (it does not yet skip re-checking via Hybrid MPST).
- `modify` / `remove` requests are detected but routed to full regeneration —
  they are edits, not compositions.
- Evolution is **build-time**: it produces a new validated `.scr`. Migrating a
  *running* session to it (dynamic update) is future work.
- As everywhere in STJP, the LLM is in the *cold path*: it drafts the child
  protocol; Scribble is the judge; once validated, the deterministic monitor
  enforces the evolved type with no LLM in the loop.
