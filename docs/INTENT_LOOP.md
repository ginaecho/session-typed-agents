# The Intent Loop — training an LLM to write Scribble that means what the user meant

**Branch:** `gc/user_intent_validation_loop` · **Code:** `experiments/intent_loop/`
· **Date:** 2026-08-05

This is a handover document. It states what exists, what is verified, what is
known to be wrong, and what I would do next. Read §1 and §9 first.

---

## 1. The point, in one paragraph

An LLM turning a natural-language intent into a Scribble global protocol can
produce something the checker **accepts** while it says something the user
never asked for. Validity is cheap; faithfulness is the hard part. This app
closes a loop around that gap: interrogate the stakeholder one question at a
time, distil what was learned into typed requirements, endorse that
understanding, *then* draft a protocol and let the real Scribble checker
judge it, grade how faithfully it carries the intent, and record everything
so the next run starts having learned. The unit of work is an **episode**;
episodes accumulate into a corpus that trains the drafter — first at the
prompt level, and later as SFT data.

**Verified live on the author's 64,166-character skill document** (gpt-5.4
learner + gpt-5.6-sol expert, real scribble-java): a protocol Scribble
accepted, reached in 3 attempts, from an interrogation that recovered 17 of
25 requirements from the conversation rather than the document.

---

## 2. The two phases, and why they are separate

```
      ┌─ PHASE 1: UNDERSTAND ─────────────────────────────┐
      │  interrogate (1 question per turn)                │
      │      answered by: human | expert model | document │
      │  → roles, interactions, goals, requirements       │
      │  → force graph + message chart, drawn NOW         │
      └───────────────────────────────────────────────────┘
                          ↓  YOU ENDORSE IT
      ┌─ PHASE 2: FORMALISE ──────────────────────────────┐
      │  draft → REAL Scribble → repair (≤12) → re-draft  │
      │  → faithfulness: coverage · back-translation · E5 │
      │  → SKILL.md + corpus row + lessons                │
      └───────────────────────────────────────────────────┘
```

Phase 1 stops before any Scribble runs. That is deliberate and was the
user's decisive argument: **the checker cannot tell a faithful protocol from
a plausible misreading**, so a validity verdict on an unreviewed
understanding is a claim about grammar dressed up as a claim about intent.
Formalising an understanding nobody agreed to is the expensive way to be
precisely wrong.

---

## 3. Four model roles, deliberately different deployments

| Role | Default | Job |
|---|---|---|
| **learner** | `gpt-5.4` | reads the intent, asks, drafts the Scribble — the model being trained |
| **expert** | `gpt-5.6-sol` | stands in for the stakeholder; **drafts** answers the human approves |
| **judge** | `gpt-5.6-sol` | reads the protocol **alone**, reconstructs the intent, grades it |
| **evaluator** | `gpt-4o` | Microsoft `SimilarityEvaluator` scores that reconstruction |

Two separations matter and both were bugs first:

* **the judge must not be the drafter.** Back-translation ran on the model
  that wrote the protocol — it reconstructs the intent it *had in mind*, not
  the one a reader would take from the text. `back_translate()` has no intent
  parameter; the signature is the isolation mechanism.
* **the expert must not decide unreviewed.** Asked who the participants were,
  gpt-5.6-sol produced five `(decision)` claims — a role taxonomy, a verdict
  enum, a terminal message — none in the document, none agreed. Fluent and
  wrong. So the default mode is **propose-then-approve**.

The evaluator needs its own deployment because `azure-ai-evaluation` still
sends `max_tokens`, which every gpt-5/o-series deployment rejects. A
non-reasoning model is also what those evaluators were calibrated on.

---

## 4. What the understanding contains

`schema.DistilledIntent` — the drafter's input and the unit the grader checks:

| Field | Why it exists |
|---|---|
| `roles[]` with `kind` + `must_not` | the **role test**: something is a role only if a message crosses into or out of it. Tools count; files do not. `must_not` makes a prohibition an absent capability rather than prose in bold. |
| `interactions[]` with `carries[]`, `cardinality`, `waits_for` | who hands what to whom. `carries[].constraint` compiles to refinement guards; `waits_for` marks a **join**, where informal documents deadlock. |
| `goals[]` with `marker`, `predicate`, `final` | outcomes, anchored to the message that signals them. A goal is *what must be true*; a requirement constrains *how you get there*. |
| `requirements[]` typed + **prioritised** | `must` / `should` / `nice`. See §6. |
| `resources[]` | what fails the role test but still constrains (shared-write files, clusters, ledgers). |
| `invariants[]` | budgets and counters over the whole session ("at most 3 repair rounds"). |
| `non_goals[]` | what must NOT be built — how a reader tells an invented step from a required one. |

Three requirement kinds are **reported but never graded**, each for its own
reason: `policy` (no session type can express "the approver and payer must be
different people"), `interior` (intra-role work — the untyped interior of an
agent), and anything the checker declines to judge.

---

## 5. Faithfulness: three instruments, and what the verdict means

1. **Requirement coverage** (primary). Per requirement: covered / partial /
   missing, with cited evidence, plus a list of protocol structure that *no*
   requirement grounds. The checker is shown the **structure and the guard
   sidecar separately**, because a value requirement can only be satisfied by
   a guard — demanding it of message order is a category error.
2. **Back-translation.** The judge reconstructs the intent from the protocol
   alone; Microsoft's `SimilarityEvaluator` scores it 1–5, mapped to 0–100.
3. **Gold E5 equivalence** (optional, exact) when a reference protocol exists.

Plus two mechanical checks that need no LLM (`protocol_checks.py`):
**deadlock precursors** (uninformed branch, loop with no exit, self-send) and
**label quality / grounding** (identifier labels like `I1` are a blocker: they
type-check and communicate nothing).

**The verdict turns on MUST alone** — see §6.

---

## 6. Priority scoring (the newest change)

Demanding 100% of a 20-item checklist is the wrong bar. A real document mixes
obligations with detail, and scoring them equally produced "3 of 19" — a
number that cannot distinguish *"every obligation holds, some fields are
opaque"* from *"an authorization guard is missing"*. So:

* the interrogator assigns `must` / `should` / `nice`, and is told to be
  strict: `must` = an act that may not happen without approval, evidence a
  verdict may not be issued without, the message that ends the session;
* **`faithful` iff every MUST is covered**, no ungrounded structure, and
  back-translation ≥ 70;
* the report carries `must_recall_pct`, `all_recall_pct`, `by_priority`, and
  `dimensions` (structure vs value-guard recall) so the *shape* of the failure
  is visible;
* if no priorities were assigned at all, everything is held to the obligation
  bar rather than certifying against an empty set.

---

## 7. Learning — two timescales

**Within an episode.** `ChatDrafter` accumulates every rejection it has seen
and replays them into each later repair ("you already tried these; do not
merely swap one error for another"), with a **structural diagnosis** naming
the role and branch at fault — Scribble says *"Source role not enabled:
Inspector"* but not which branch left it uninformed.

**Across episodes.** Every real rejection folds into `lessons.json`, loaded by
default on the next run. Only the validator's own verdicts become lessons,
deduplicated by error family and bounded. Faithfulness failures produce
lessons too ("name messages after what they carry, never the interaction id").

**Then:** `optimize.py` mines the corpus into a versioned prompt pack (BM25
few-shot exemplars from episodes that were valid **and** faithful, plus the
rulebook); `export.py` emits chat-format JSONL for real fine-tuning, split by
**intent hash** so two episodes of one document cannot straddle
train/validation. Drafting examples come only from valid **and** faithful
episodes — a valid-but-wrong protocol would teach the exact failure this
project exists to prevent.

---

## 8. Running it

```bash
python -m experiments.intent_loop web          # http://127.0.0.1:8765
python -m experiments.intent_loop run --mock   # offline scripted smoke test
python -m pytest experiments/intent_loop/tests -q   # 66 tests, all offline
```

Settings (endpoint, key, four deployments, prices, repair rounds) are in the
UI or `POST /api/settings`. Azure with an **empty key** uses `az login`, so no
secret need touch disk; a stored key is never returned by the API, only a
last-four fingerprint.

**The API is the same surface the UI uses** — no private routes, so an agent
can do anything a human can. Start at `GET /api/manifest`.

| Endpoint | Purpose |
|---|---|
| `POST /api/runs` → `{job_id}` | phase 1 (async). `answered_by`: `expert_reviewed` (default) / `human` / `expert` / `document` |
| `GET /api/runs/<id>` | state, stage events, **the open question** |
| `POST /api/runs/<id>/answer` · `/cancel` | answer it · abandon it |
| `POST /api/episodes/<s>/formalize` | **phase 2**: draft, real Scribble, repair, grade |
| `GET /api/episodes/<s>/graph` | force graph + message chart (falls back to declared interactions pre-protocol) |
| `GET /api/episodes/<s>/checks` | deadlock precursors + turn order |
| `POST /api/episodes/<s>/explain` · `questions` · `repair-questions` · `refine` | per-message rationale · gap questions · **turn a Scribble rejection into a business question** · redraft with answers |
| `GET /api/episodes/<s>/skill` | the episode as a reusable `SKILL.md` |
| `POST /api/packs` · `/api/training/export` | prompt-level · weight-level training data |

**Scribble toolchain.** This box had Docker and Java but no Maven, so it was
built in a container: `docker run --rm -v "$PWD/scribble-java:/out" -v
"<dir>:/work" maven:3.9-eclipse-temurin-17 bash /work/build_scribble.sh`.
A Windows path bug also had to be fixed in `seam_bench/eval/_worker.py`: the
scratch `.scr` went to the system temp dir while the CLI runs with a
*relative* path, so every validation failed with `Bad module arg`.

**Cost.** Token counts are **real API usage**; cost is computed only from
`prices` you configure (USD per 1M tokens per deployment) and otherwise
reported as unknown. Model list prices change by region and agreement, so
guessing them would produce a confident wrong number.

---

## 9. Known problems, in the order I would fix them

1. **Faithfulness is the open research problem.** Best live result:
   `valid: true`, recall ~9–16%. Getting Scribble that *validates* is solved;
   getting Scribble that validates **and** says what the user meant is not.
2. **The drafter does not emit guard sidecars,** which is why every value
   requirement fails. `_GUARDS_BLOCK` fires only when the spec contains value
   constraints, which requires the interrogation to have populated
   `carries[].constraint`. Make the sidecar mandatory whenever a value
   requirement exists, and check it.
3. **`interior` is under-applied.** One live run classified 1 of 40
   requirements as intra-role; a careful human reading of the same document
   put it nearer 60%. Until that is right, recall's denominator is wrong and
   the drafter keeps trying to encode procedure as messages (visible as
   self-sends in the protocol).
4. **No role parameterisation.** A 12-pair DAG has nowhere to go: the model
   is one flat session. The honest encoding is session-per-pair with a
   meta-scheduler; that maps to parameterised MPST, which the paper lists as
   roadmap.
5. **Jobs are in-memory.** A restart loses job state (sessions survive on
   disk, and the UI now recovers from them). Do not restart the server while a
   run is in flight — that mistake killed a user's 64k run.

---

## 10. Things that are true and easy to get wrong

* **A mock run must never touch the network.** The offline suite's value
  depends on it; an evaluator briefly broke this.
* **`valid: false` is normal and is the training signal**, not a failure.
* **Never fabricate a score.** A failed scorer reports the failure; every
  report names the scorer and the judge deployment that produced its number.
* **The graph reader is tolerant on purpose** — it draws drafts the strict
  grammar rejects, because seeing a rejected draft is how you learn why. It
  never decides validity, and lists any line it could not parse.
* **Absence of evidence is not agreement.** A requirement the checker skipped
  is a miss, not a free pass; `partial` counts as a miss with the evidence
  retained so a human can overrule.
