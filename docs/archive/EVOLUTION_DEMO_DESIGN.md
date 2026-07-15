# STJP evolution demo — "the demand changed on Tuesday"

Design for the second demo act: a **new requirement arrives after the system
is live**. The claim to demonstrate: with intent-only agents, absorbing the
change is statistical hope; with STJP, it is a small reviewed diff that is
re-proven before any agent runs, and the change's blast radius is *provable*.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Use case — banking, new compliance demand](#use-case--banking-new-compliance-demand)
- [Act 1 — intent-only team absorbs the change](#act-1--intent-only-team-absorbs-the-change)
- [Act 2 — STJP absorbs the change](#act-2--stjp-absorbs-the-change)
- [What the demo page shows (extends `STJP_Benchmark_Demo.html`)](#what-the-demo-page-shows-extends-stjp_benchmark_demohtml)
- [Build plan (when greenlit)](#build-plan-when-greenlit)
<!-- MENU:END -->

## Use case — banking, new compliance demand

Base: the existing `experiments/cases/banking/` case
(`Initiator, SourceBank, DestBank, Approver, AuditLog`; invariant: large
transfers need approval **before any money moves**; terminal `Settled`).

**The new demand (one paragraph, exactly how it arrives in real life):**

> "Effective immediately: every transfer above $10,000 to a payee the source
> account has never paid before must pass a sanctions/fraud screen by the new
> ComplianceScreen service **before any money moves**. Screen verdicts must be
> logged. Existing approval rules still apply."

Why this demand is the right one:

- It touches an **irreversible action** (`Debit`/`Credit`): doing it in the
  wrong order is an S4 disaster (payment to a sanctioned entity cannot be
  unsent), not a style problem.
- It interacts with an **existing branch** (large vs small) — the classic
  place where a hand-edited prompt change half-lands.
- It adds a **new role**, so the projection/blast-radius story is visible.

## Act 1 — intent-only team absorbs the change

Append the paragraph to the intent, rerun MAF GroupChat. Failure modes to
surface (each is one recorded trial in the demo):

1. **Screen-after-debit**: money moved, then screened — S4, the disaster. The
   trace looks busy and plausible; nothing in the intent-only stack even
   *flags* it.
2. **Half-landed change**: screen happens on the large branch but the
   new-payee small branch (> $10k is not the only trigger condition) is missed.
3. **Regression**: while absorbing the new rule, agents drop an old one
   (debit before approval) — prompts are a global medium; every edit can
   perturb everything.
4. **No completion**: agents over-rotate, screen everything, deadlock waiting
   for ComplianceScreen on branches where it has nothing to say.

The honest framing for the slide: with prompts, change coverage is
**statistical** — you test more and hope; absence of disaster is never proven,
and the system gives you *zero signal* when a trial quietly does #1.

Metric set (Act 1 and Act 2 measured identically):

| metric | meaning |
|---|---|
| **disaster rate** | trials with an irreversible act before its new authorization (S4 under the v2 partial order) |
| **half-landing rate** | trials where the new obligation fired on some but not all triggering branches |
| **regression rate** | trials violating an *old* invariant that v1 trials satisfied |
| **turnaround** | wall-clock from "demand text" to "first safe deployment" |
| **blast radius** | # roles whose instructions changed (prompts: all of them, unprovably; STJP: hash-diff of projected contracts) |

## Act 2 — STJP absorbs the change

1. **Delta-draft**: LLM gets v1 global type + the demand paragraph → drafts v2
   as a diff (new role in signature, `ScreenRequest`/`ScreenVerdict` messages,
   refinement `verdict == "clear"` guarding `Debit`). A few lines.
2. **Scribble re-validates — and catches the realistic pitfall.** Stage the
   first draft to make the natural mistake: screen inserted on the large
   branch only, while SourceBank waits for a screen-ack before *any* debit →
   wait-for cycle `[Initiator, SourceBank, ComplianceScreen]` → **REJECTED
   before any agent ran**. (Mirror of the finance unsafe-draft story — now in
   the change-management setting, where it lands harder: the bug was
   *introduced by the change*.)
3. **Fix, re-validate, re-project.** Per-role local contracts regenerate.
   Show the contract diff table: `Initiator`, `DestBank`, `AuditLog` contracts
   **hash-identical to v1** — the change provably cannot have altered their
   behaviour surface. Only `SourceBank`, `Approver`, `ComplianceScreen`
   changed. That is the blast-radius proof prompts cannot give.
4. **Goals re-anchor mechanically**: new goal `G7: ScreenVerdict(clear) ≺
   Debit` (ordered, branch-conditional); old goals untouched.
5. **Monitors update for free** (same projection), so even if an agent ignores
   its new contract, the first off-contract event is flagged at event-time —
   compare with Act 1 where disaster #1 produces no signal at all.

## What the demo page shows (extends `STJP_Benchmark_Demo.html`)

New section **"06 · When the demand changes"**:

- **The diff panel**: v1→v2 global type as a unified diff; toggle to the
  rejected intermediate draft with Scribble's wait-for-cycle verdict.
- **Blast radius strip**: six role chips; three glow "changed", three show
  `sha256 unchanged` badges.
- **Side-by-side replay** (reuses the existing replay engine): left, an
  intent-only trial hitting failure mode #1 with a red **IRREVERSIBLE —
  UNSCREENED DEBIT** marker the moment `Debit` precedes `ScreenVerdict`;
  right, the typed trial where `Debit` stays disabled until the verdict.
- **The four-number scoreboard**: disaster rate / half-landing rate /
  regression rate / turnaround, Act 1 vs Act 2.

## Build plan (when greenlit)

1. `banking/protocols/v2.scr` + staged `v2_drafts/unsafe/` (the rejected
   delta) + `v2.refn` (screen verdict guard) — author from existing v1.
2. Re-anchored `goals.yaml` for v2 incl. ordered G7 (the ordering predicate
   needs a small extension to the verifier: goal anchored on a *pair* of
   events, `before:`/`after:`).
3. `case_runner` v2 arms: `--arms maf_groupchat,spec_llmvalid` against v2
   protocol with the v1-trained intent +appended paragraph (Act 1) and the
   re-projected contracts (Act 2); n ≥ 10.
4. Severity grader (post-hoc script over events.jsonl implementing the
   S0–S4 ladder from BENCHMARK_DESIGN.md v2.1) — shared with the fairness
   work; the evolution metrics are S4-rate restricted to the new partial
   order.
5. Demo section 06 wired to the new run dirs.

Nothing above requires new infrastructure beyond: ordered-pair goal
predicates, the severity grader, and one new protocol version directory —
the runner, monitor, projection, and demo replay all already exist.
