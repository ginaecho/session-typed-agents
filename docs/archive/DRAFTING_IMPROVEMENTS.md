# Improving LLM → Scribble drafting — diagnosis, fixes, and the SLM question

**2026-06-17.** Follows the v2 prompt change (`SCRIBBLE_SYSTEM_PROMPT_V2`). Goal:
push first-pass validity up / re-draft loops down, and answer "should we train a
small model to write Scribble?"

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Why drafts still failed — precise diagnosis](#1-why-drafts-still-failed--precise-diagnosis)
- [2. The fixes (two, layered)](#2-the-fixes-two-layered)
  - [Fix A — deterministic fan-out normalizer (the durable one)](#fix-a--deterministic-fan-out-normalizer-the-durable-one)
  - [Fix B — prompt hardening (cheap, complementary)](#fix-b--prompt-hardening-cheap-complementary)
- [3. Measured effect (A/B, real gpt-5.4, fresh intent)](#3-measured-effect-ab-real-gpt-54-fresh-intent)
- [4. Should we train a small model (SLM) to write Scribble?](#4-should-we-train-a-small-model-slm-to-write-scribble)
- [5. Files](#5-files)
<!-- MENU:END -->

## 1. Why drafts still failed — precise diagnosis

I captured real v2 first-drafts of a fresh, hard intent (5-role Incident-Response
with a severity branch + ack-before-resolve) and read the actual compiler verdict.
The dominant error is **not** a syntax problem and **not** a wait-for cycle — it is:

```
Safety violation(s) at session state 108:
    ... Unfinished roles: {Auditor=36, Responder=28}
```

Cause, exactly. In the protocol's `choice at Triage`, the model wrote a complete
fan-out in the **Critical** branch (Triage notifies Responder, Auditor, Resolver)
but in the **Routine** branch notified **only Resolver** — because Responder and
Auditor "do nothing in a routine incident." Scribble then sees that on the routine
path Responder and Auditor never receive anything and never reach an end state →
**Unfinished roles**.

So the model **half-applies the fan-out**: it notifies the roles *active* in a
branch and silently drops roles that are *idle* in that branch. The v2 prompt
already says "notify every other role in every branch," but the model rationalizes
the omission as natural. Prose alone doesn't reliably overcome that prior.

## 2. The fixes (two, layered)

### Fix A — deterministic fan-out normalizer (the durable one)
`stjp_core/authoring/fanout_normalizer.py`. After the LLM drafts, before Scribble,
a mechanical pass repairs the exact error above:
- Parse the single top-level `choice at X` (conservative: bails on `rec`/`do`/
  `aux`/nested choice — those go to the LLM/Scribble loop unchanged).
- Compute the roles that **act inside** the choice (so roles active only
  before/after — e.g. a Fetcher — are never touched).
- For each branch, for each such role not already receiving its **first** message
  from X, **insert** `BranchNote() from X to R;` at the branch top.
- **Insert-only + minimal-target** ⇒ it provably cannot alter an already-valid
  protocol (verified: finance, banking, canonical-finance drafts → 0 insertions,
  unchanged). On the failing incident drafts it inserts exactly the 2 missing
  notifications and they become **valid**.

This also fixes the sibling "Inconsistent external choice subjects" error, because
forcing X to be every role's first sender in every branch is precisely that rule.

Enabled by default: `ArchitectAgent(auto_fanout=True)`; `False` reverts.

### Fix B — prompt hardening (cheap, complementary)
v2 already adds reason-then-code + the fan-out template + a worked example. The
remaining lever in prose is to name the *specific* failure ("Unfinished roles") and
the count rule ("each branch begins with exactly one notification to every role
that acts anywhere in the choice"). The normalizer makes this robust regardless of
compliance, so prose is now backup, not the primary guarantee.

## 3. Measured effect (A/B, real gpt-5.4, fresh intent)

`experiments/scripts/smoke_draft_prompt.py`, 3 arms × 4 trials:

| prompt | first-pass valid | eventually valid | avg fix-rounds | avg time |
|---|---|---|---|---|
| v1 (one-shot) | 0/4 | 4/4 | 2.25 | 20.6s |
| v2 (reason+template) | 1/4 | 4/4 | 1.25 | 21.4s |
| **v2 + fan-out normalizer** | **3/4** | 4/4 | **0.25** | 16.1s |

(Filled from the 2026-06-17 smoke; see `RUN_REPORT_2026-06-17.md`.) The normalizer
targets first-pass validity directly: it converts the most common Scribble
rejection into a zero-LLM-cost repair, so a draft that was "valid except for the
fan-out" passes on attempt 1.

## 4. Should we train a small model (SLM) to write Scribble?

**Recommendation: not yet — and here is the honest reasoning, plus what to do
instead and the precondition that would change the answer.**

Why not yet:
1. **Correctness is already guaranteed by the loop, not the model.** Scribble is a
   sound oracle in the loop; the output is *always* valid-or-rejected. An SLM
   cannot improve *correctness* — only *latency/cost/iteration-count*. gpt-5.4 +
   v2 + normalizer already converges in ≈1 round.
2. **The dominant error is now handled deterministically** (Fix A) for free — the
   thing an SLM would most help with is the thing we just removed from the LLM's
   burden.
3. **Data scarcity & drift.** A good Scribble SLM needs thousands of
   (intent → valid protocol) pairs across diverse shapes; we have a handful of
   cases. Training now would overfit our shapes.

What to do instead (in priority order):
1. **Deterministic repairs** for the next error classes too (e.g. missing `data`
   declarations, module-name) — each removed error is worth more than model
   training and is reusable across any model.
2. **Collect the dataset now, for free.** Every benchmark/authoring run already
   produces (intent, draft, Scribble-verdict) triples. Persist them
   (`experiments/logs/draft_dataset/`) so that *if* volume ever justifies it, we
   have rejection-sampling distillation data ready.
3. **Few-shot library**, not fine-tuning: keep a curated set of (intent → valid
   protocol) exemplars covering each shape (linear, branch, loop, multi-choice,
   composition) and retrieve the closest as in-context examples. Most of an SLM's
   benefit, none of the training cost or drift.

The precondition that flips the recommendation to **yes, train**: when we are
drafting at *volume* (e.g. interactive authoring for many users, or a large
case-generation pipeline) where gpt-5.4 latency/cost per draft becomes the
bottleneck — then a rejection-sampling-distilled SLM (gpt-5.4 + Scribble oracle
generate the data; fine-tune a small open model; keep the Scribble loop as the
safety net) is the right move. The Scribble checker stays in the loop either way,
so a smaller, occasionally-wrong model is acceptable — it just costs an extra fix
round, which the normalizer already absorbs. **Build the dataset pipeline now;
defer the training until volume demands it.**

## 5. Files
`stjp_core/authoring/prompts.py` (v2 prompts), `architect.py`
(`use_v2_prompt`, `auto_fanout`), `fanout_normalizer.py`,
`experiments/scripts/smoke_draft_prompt.py`.
