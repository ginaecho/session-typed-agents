# Pre-registration — agent_lit_sweep arm comparison

**Registered 2026-07-25, before any arm was run.** Following the same rule as
[`BENCHMARK_V2_PREREGISTRATION.md`](BENCHMARK_V2_PREREGISTRATION.md): the
expected outcome of each measurement is written down first, then graded after.
A prediction that can be edited after the run can never fail.

This document exists because of a methodological error worth recording. An
ad-hoc fan-out of eight search agents was run earlier to do real work (sweep the
2026 related-work literature). It failed in three visible ways — the same paper
was found and paid for repeatedly, a shared search-call budget was drained to
zero without any agent noticing, and an invented citation reached the written
output. Those observations were then presented as *evidence for* the compiler.
They are not. Each of the eight agents had a **different** search assignment, so
configuration was confounded with topic; and the metrics were chosen after
seeing the outcome. This pre-registration is the corrected version.

One term, glossed once: an **arm** is one configuration being compared — like
the treatment and control groups of a medical trial.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [What is already established, and what is not](#what-is-already-established-and-what-is-not)
- [Design](#design)
- [Metrics, defined mechanically and before the run](#metrics-defined-mechanically-and-before-the-run)
- [Predictions](#predictions)
- [Known confounds, stated in advance](#known-confounds-stated-in-advance)
- [Grading](#grading)
<!-- MENU:END -->

## What is already established, and what is not

**Established, and it is a compiler property rather than a benchmark result.**
[`check_case.py`](../../experiments/cases/agent_lit_sweep/check_case.py) passes
in four steps: the protocol is well-formed under the real Scribble compiler; all
three roles project to non-empty local contracts (13, 7, and 6 transitions); the
budget ledger passes its static coherence check against the protocol's labels;
and four spend requests of ten against a budget of thirty leave the budget at
`0` with exactly one overdraw **rejected pre-delivery** — never negative. This
is deterministic, involves no agents, and needs no statistics. It is the same
class of evidence as the offline replay verification of choice guards already
reported in the paper.

Also worth recording: the **first draft of the protocol was rejected** by the
compiler with `Subject not enabled: Scout`, because the loop re-entry left Scout
having to choose with nothing received. That is the authoring-risk mechanism
working on the author of this document, at zero token cost.

**Not established.** Anything at all about how agents behave under the protocol.
Every prediction below is unrun.

## Design

Same case, same roles, same intent, same model, same budget, same step cap.
**One variable: the arm.** This is the design `experiments/baselines/registry.py`
already uses, and the earlier fan-out did not.

| Held constant | Value |
|---|---|
| Case | `agent_lit_sweep` |
| Roles | Coordinator, Scout, Verifier (in **both** arms) |
| Search assignment | one identical research question, given to both arms |
| Role descriptions | the prose block from `case.yaml`, in both arms |
| Search budget | 12 calls (see amendment below) |
| Step cap | 40 |
| Role-players | the same model at the same settings in both arms |
| Driver loop | the same loop drives both arms, so neither gets a human in the loop the other lacks |

| Arm | What each agent is told | Enforcement |
|---|---|---|
| `bare` | the intent as prose only | none |
| `min_llmvalid_sched` | its projected local type | gate + EFSM turn selection + budget ledger |

**Amendment, 2026-07-25, before any trial was run.** The shared search budget
was lowered from 30 calls to 12. Reason: six trials at 30 would need up to 180
real search calls, and this session's search pool has a hard cap that was already
reached once. The change is recorded here, and in a comment in `v1.refn`, because
it was made *before* any arm ran — the same change made after seeing results
would not be legitimate, and the whole point of this document is that the
difference is visible. `check_case.py` was re-run at the new budget and still
passes: three spend requests of five against twelve leave the budget at 2 with
one overdraw rejected pre-delivery.

**The search assignment must be a question whose answer is not already known to
the operator.** The earlier sweep's topic is disqualified: its findings are
known, which would advantage whichever arm ran second. A fresh, unswept question
of comparable shape is required, and it is fixed before either arm runs.

## Metrics, defined mechanically and before the run

No LLM judge. Each is computed from the event trace.

- **M1 — duplicate-claim rate.** Of all candidate findings submitted, the
  fraction whose identifier had already been submitted earlier in the same run.
- **M2 — budget overrun.** The most negative value the search-call budget
  reaches, and whether any search happened after the budget hit zero.
- **M3 — unverified-claim rate.** Of the findings present in the final report,
  the fraction that never received a confirming verdict. An identifier that does
  not resolve counts as unverified whether or not anyone noticed.
- **M4 — tokens per confirmed finding.** Total tokens divided by the number of
  confirmed findings. Reported per arm with the raw token count alongside, since
  the denominator can differ.

**Fair success rule.** The `bare` arm is scored on *what it achieved*, never on
whether it happened to emit the protocol's message labels — it was never shown
them. A `bare` run that returns verified findings within budget succeeds, however
it structured its messages. This is the correction the
[fairness review](../BENCHMARK_FAIRNESS_REVIEW.md) forced on the finance tables.

## Predictions

| # | Prediction, registered before running | Outcome |
|---|---|---|
| P1 | **M1 (duplicates) is higher in `bare` than in the compiled arm.** In the compiled arm a claim must pass the Verifier before it is recorded, and the Coordinator holds the record, so a re-submission is visible. Direction predicted, magnitude not. | PENDING |
| P2 | **M2 (budget overrun) is zero in the compiled arm by construction, and can be non-zero in `bare`.** The compiled half is not an empirical claim — it is the theorem `check_case.py` already checks. The empirical half is whether `bare` actually overruns when nothing stops it. | PENDING |
| P3 | **M3 (unverified claims) is zero in the compiled arm and can be non-zero in `bare`.** Structurally a candidate cannot become a recorded finding without a verdict. **Caveat registered in advance:** this guarantees the claim was *checked*, not that the checker was right — a Verifier that confirms a bad identifier satisfies the protocol and still puts a wrong finding in the report. If that happens it counts as a confirmed prediction about the mechanism and a falsification of any claim that the mechanism delivers truth. | PENDING |
| P4 | **M4 (tokens per confirmed finding) is WORSE in the compiled arm on this case at small scale.** Registered deliberately as a predicted loss. The protocol adds round trips `bare` does not pay — every spend costs three messages, every candidate costs four — and with only three roles there is little projection saving to offset it. The paper's token win comes from projection replacing re-read prose across many roles and from failure avoidance; a 3-role case with a short loop has neither in quantity. If the compiled arm wins here, the prediction is falsified and the reason needs finding rather than celebrating. | PENDING |
| P5 | **`bare` will not reliably produce the deadlock this case can express.** Three roles with a Scout-driven loop is a shallow coordination problem; prose-only agents will probably muddle through. Registered so a null result is not later reported as a win. | PENDING |

## Known confounds, stated in advance

1. **Operator effect.** The compiled arm needs a runtime; if the operator hand-drives
   its turns while `bare` runs unsupervised, the comparison measures supervision,
   not the compiler. Mitigation: one driver loop for both arms, differing only in
   whether the contract, gate, and ledger are switched on.
2. **Experimenter bias.** The protocol author is also the operator. Mitigation:
   metrics and success rule fixed here, computed from the trace mechanically.
3. **Unseeded role-players.** The hosted models expose no seed, so trials are not
   replayable and small-n differences are noise. Any n below about 10 per arm
   supports a direction at best, never a magnitude, and must be reported with
   Wilson intervals via `stats.py`.
4. **This case is not the paper's headline case.** It is 3 roles and shallow. It
   can test the ledger, the verification barrier, and duplicate suppression. It
   cannot test the role-count scaling claim, and no result here should be
   generalized to it.
5. **A single case, chosen by the operator, on a workload the operator picked.**
   Whatever comes out is one case's evidence.

## Grading

After the run, fill the Outcome column with **CONFIRMED**, **FALSIFIED**, or
**INCONCLUSIVE (n too small)**, and do not edit the prediction text. Falsified
predictions are reported in the same table, in the same prominence, as confirmed
ones.
