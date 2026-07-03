# Benchmark Design v3 — Criticality-Aware Testing

**Drafted 2026-06-17.** Builds on (does not replace) `BENCHMARK_DESIGN.md` and
its frozen snapshot `BENCHMARK_DESIGN_V2_FROZEN.md`. v3 is **additive**: new
post-hoc metrics + optional per-case annotations; no arm or existing metric is
removed.

## 1. The problem v3 fixes

The v2 headline metric (GCR + monitor acceptance) credits agents for **following
the protocol's order**. But the grand n=10 run (gpt-5.4) showed B (global-type-
as-text, no projection, no monitor) reaching **100% GCR** — matching C+. A fair
reviewer objects:

> "On a strong model your protocol order was followed anyway. Following an
> arbitrary total order is not intrinsically valuable. Show me a task where the
> order is *load-bearing* — where getting it wrong is not a style violation but
> a wrong answer — and show me you measure that property directly, not just
> 'did they match my sequence'."

The objection is correct. **Protocol-following is not universally better.** It is
better-and-necessary exactly when the task has a *critical dependency*. v3 makes
criticality the independent variable and tests the critical property directly.

## 2. Criticality classes (the properties that actually matter)

A "critical dependency" is a constraint whose violation makes the outcome wrong
even if a final artifact is produced. Three classes, each with a direct test:

### C1 — Data provenance ("no guessing")
A derived value an agent emits must be **causally downstream of the real data**
it received — not invented. *Example:* RevenueAnalyst's analysis must depend on
the `RawRevenueData` it was given; if it emits an analysis built on a number it
hallucinated, the report is wrong even if well-formed.
- **Direct test (provenance gate):** plant a unique token (or use the exact
  numeric value) in the data-source payload; require it to reappear / be
  numerically derivable in the downstream derived payload. Failure = the agent
  guessed.

### C2 — Context completeness ("read everything first")
Before producing aggregate output O, the actor must have **consumed all required
inputs** I₁…I_k. *Example:* the Writer must incorporate BOTH revenue and expense
analyses; a report written before the expense input arrived is incomplete.
- **Direct test (context gate), two tiers:**
  - *Structural* (EFSM-native, free): did the actor RECV every required input
    before the SEND? The local type already encodes this; the monitor already
    enforces it. This is the part protocol projection gives for free.
  - *Substantive* (the user's `len(context)` idea, hardened): does the output
    payload actually **cover** each input? Proxy = the output references each
    input's planted token / value, OR `len(output) ≥ floor` scaled to #inputs.
    Length alone is a weak proxy (an agent can pad); token-coverage is the
    strong form. We report both and treat coverage as primary.

### C3 — Authorization before irreversible action
An irreversible act must be preceded by its authorizing step. This is exactly the
v2.1 **S4** severity class (`severity_grader.py`) — already implemented. v3 folds
it in as the third criticality class so all three are reported together.

## 3. The fairness design: two variants per case

The decisive move. For each scenario, define two variants that differ ONLY in
whether a critical dependency is load-bearing:

| variant | construction | expected honest result |
|---|---|---|
| **neutral** | inputs independent; any interleaving yields the same correct output | B ≈ C ≈ C+ — protocol overhead does NOT pay; *we say so* |
| **critical** | output is only correct if C1/C2/C3 hold (e.g. analysis must use the real datum; report must cover both inputs; debit needs prior auth) | only the monitored arms (C/C+) can *guarantee* the property; B passes or fails by luck of the model |

This converts the benchmark claim from the indefensible "protocols are always
better" to the defensible:

> **STJP's value is conditional and we identify the condition.** When a task
> carries a critical dependency (C1/C2/C3), projection + monitor turns "happened
> to be right" into "cannot be wrong", and we measure the dependency directly.
> When it doesn't, we report parity honestly.

A benchmark that can show its own method *not* helping on neutral tasks is far
more credible than one that always wins.

## 4. The arm matrix (unchanged set, sharper question)

Same arms as v2 (A intent, B global-text, C local, C-min, **C+ gate**), now run
on both variants of each case. The question each pairwise comparison answers:

- A vs B — does a validated global type (even as text) help at all?
- B vs C — does **projection** (own local contract) beat reading the whole type?
- C vs C+ — does **enforcement** beat observation? (the liveness + guarantee gap)
- **neutral vs critical** (within each arm) — is the help *specific to
  criticality*? The headline v3 chart is GCR-and-critical-property-rate plotted
  against criticality, per arm.

## 5. New metrics (Layer 1b: Critical-Property Achievement)

Computed post-hoc from existing `events.jsonl` by
`experiments/scripts/criticality_gate.py`, driven by a per-case
`protocols/criticality.yaml` (mirrors `severity.yaml`):

- **Provenance rate (C1):** fraction of trials whose derived payload references /
  derives-from the source datum.
- **Context-coverage rate (C2):** fraction whose aggregate output covers all
  required inputs (token-coverage; length proxy reported secondarily).
- **Authorization rate (C3):** 1 − (S4-disaster trials / trials) — reuse the
  severity grader.
- **Critical-Goal Completion (CGC):** GCR **AND** all applicable C1/C2/C3 hold —
  the honest "did they really achieve it" number. This is the v3 headline,
  stricter than GCR.

`criticality.yaml` schema (per case):
```yaml
provenance:                 # C1
  - source:  {sender: Fetcher, label: RawRevenueData}    # carries the datum
    derived: {sender: RevenueAnalyst, label: FinalRevenueAnalysis}
    check: numeric          # the source number must appear / be derivable
context:                    # C2
  - actor: Writer
    requires: [RevenueAnalysis, ExpenseData]   # must all be RECV'd before...
    output: GenerateReport                      # ...this SEND, and output must cover each
authorization:              # C3 — defer to severity.yaml's irreversible block
  use_severity: true
```

## 6. Why this is the right shape (and its limits)

- It tests **the property, not the path** — robust to dialect and to a model that
  reaches the right place by a different route (answers the v2 circularity
  objection at a deeper level than label-alignment did).
- It is **falsifiable in STJP's disfavour**: the neutral variant is designed to
  show no benefit. If C never beats B even on the critical variant, STJP's claim
  is wrong and the benchmark will say so.
- **Limit — coverage proxies are imperfect:** token-coverage can be gamed by an
  agent that echoes inputs without using them; `len()` is weaker still. The
  honest framing is "necessary, not sufficient" evidence of context use; the
  strongest form would be an LLM-judge of *faithfulness*, which we add as the
  semantic tier (versioned judge, sampled audit) — same pattern as Set B's
  semantic rung.
- **Limit — provenance for prose:** numeric provenance is clean; free-text
  provenance needs the planted-token construction in the case design (the
  data-source emits a unique tag the derived message must carry).

## 7. Smoke test (this session)

`criticality_gate.py` was run post-hoc on the existing grand n=10 traces
(`runs/20260612T162803-n10-dual`) with a finance `criticality.yaml`. Results and
interpretation: see `RUN_REPORT_2026-06-17.md` §"Criticality smoke". The point of
the smoke is to verify the metric *computes and discriminates* on real traces,
not to draw a final conclusion (that needs the purpose-built neutral/critical
case variants, which are future work below).

## 8. Future work to fully realize v3

1. Author neutral/critical **variants** for finance and banking (the two-variant
   design in §3) with planted provenance tokens.
2. Add the semantic faithfulness judge (C2 strong form).
3. Re-run the 5-arm matrix on both variants, n≥10, and produce the
   criticality-vs-achievement headline chart.
