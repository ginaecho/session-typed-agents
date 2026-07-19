# Benchmark Plan v2 — hardening the STJP evaluation

Implemented 2026-07-04. Closes the six honesty gaps in the original benchmark
(too few repeats; one model family; we grade our own homework; only friendly
agents; the translator is unmeasured; one task size). Design rule: **each
experiment measures ONE component**, so a good/bad number is attributable.

Everything deterministic was run for real with the vendored Scribble compiler;
everything needing multiple model families, a live LLM draft loop, or extra
runtime adapters is a connected harness marked **MEASUREMENT PENDING** with real
anchor points and clearly-tagged synthetic placeholders (so the paper renders
now and real numbers swap in per §10).

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Status at a glance](#status-at-a-glance)
- [§9 Verdict corpus — testing the testers (do first, cheapest)](#9-verdict-corpus--testing-the-testers-do-first-cheapest)
- [E1 — does the checker catch bad protocols? (mutation testing)](#e1--does-the-checker-catch-bad-protocols-mutation-testing)
- [E2 — does the gate stop a hostile agent? (adversarial exfiltration)](#e2--does-the-gate-stop-a-hostile-agent-adversarial-exfiltration)
- [E4 — reliability operators actually need (pass^k)](#e4--reliability-operators-actually-need-passk)
- [E5 — how good is English→protocol? (translation fidelity)](#e5--how-good-is-englishprotocol-translation-fidelity)
- [E6 — does it scale? (roles sweep)](#e6--does-it-scale-roles-sweep)
- [E7 — is it portable? (cross-runtime)](#e7--is-it-portable-cross-runtime)
- [E3 — story vs model strength (capability sweep)](#e3--story-vs-model-strength-capability-sweep)
- [§10 — swapping real numbers in](#10--swapping-real-numbers-in)
<!-- MENU:END -->

## Status at a glance

| # | Experiment | Component tested | Status | Headline (real) |
|---|---|---|---|---|
| §9 | Verdict corpus | monitor + severity grader | **REAL** | 40/40 traces verdicted correctly |
| E1 | Mutation testing | the checker (soundness/completeness) | **REAL** | well-formedness defects 95.6% detected, 0% false positives |
| E2 | Adversarial exfiltration | the gate | **REAL** | none 0% → rules 41.7% → gate 91.7% → gate+refn 100% blocked |
| E4 | pass^k reliability | (stats over runs) | **REAL (n=10)** | 100%/10 → Wilson [72,100], pass^10@CIlo 0.039 |
| E5 | Translation fidelity | English→protocol | **REAL scorer / LLM pending** | equivalence scorer 100% over 90 pairs |
| E6 | Roles sweep | the scheduler/projection cost | **REAL proxy / tokens pending** | global-text 9→17× STJP cost, 2→10 roles |
| E7 | Cross-runtime | boundary portability | **REAL / 3-harness pending** | standalone == in-process monitor 100% |
| E3 | Capability sweep | the story vs model strength | **PENDING** | 2 real anchors (gpt-4o +60/4, gpt-5.4 0/22) |

Reports: `experiments/reports/{e1..e7,figs}/`, `experiments/reports/TABLES_v2.md`;
pre-registration in `docs/predictions/BENCHMARK_V2_PREREGISTRATION.md`.

---

## §9 Verdict corpus — testing the testers (do first, cheapest)

`experiments/tests/verdict_corpus/` — 40 hand-derived traces run against the
`SessionMonitor` (24, incl. async-commuting and value-dependent choice guards)
and the `severity_grader.AttemptGrader` (16, S0–S4 — severity levels running
from benign to irreversible disaster, incl. the payload-blind
`Approval(False)` case). **40/40.** Building it surfaced two real semantics a
naive reviewer gets wrong (both endpoints flag a bad message; a role's
send/receive to the same peer commute), and forced three of my own
hand-derivations to be corrected to the semantically-correct value — the
instruments were right. `run_verdict_corpus.py` (exit 0 iff 40/40) is CI-ready.

## E1 — does the checker catch bad protocols? (mutation testing)

`gen_corpus.py` builds a 30-protocol valid corpus across shapes; `mutate_
protocol.py` injects one defect at a time; `mutation_bench.py` measures
detection + false positives.

- **Well-formedness defects (the soundness claim): 95.6% detected** —
  undeclare_role 100%, flip_branch_subject (inconsistent choice subject) 100%,
  branch_asymmetry 84%. **False positives 0/30.**
- **Reordering ops** (reverse/swap/drop/rewire) detect ~0% — reported
  separately and honestly: on an *acyclic* protocol a local reorder yields
  *another well-formed* protocol, which Scribble correctly accepts. Catching
  *intent* drift (as opposed to well-formedness) is the job of goals /
  refinements / the equivalence check (E5), not the safety checker. This is a
  more honest result than a uniform synthetic 100%.

## E2 — does the gate stop a hostile agent? (adversarial exfiltration)

`adversarial_bench.py` — a prompt-injected Writer tries to exfiltrate a
confidential payload to `ExternalAuditor` (who may legally receive only the
public summary), over 12 injection templates, under four protections:

| guard | blocked | what it is |
|---|---|---|
| none | 0.0% | no protection |
| rules | 41.7% | honest keyword+role blocklist — 7 evasions (base64, hex, synonyms, split payloads, typos) |
| gate | 91.7% | STJP structural gate — blocks every ILLEGAL-route attempt, disguise-proof (checks the (label,recipient), not the wording) |
| gate+refn | 100% | + a value guard on the one legal outbound channel |

The gate's 91.7% (not 100%) is the honest, load-bearing finding: the ONE
attack that got through used a *legitimately-labelled* `PublicSummary` message
to smuggle raw figures — a payload-content attack the structural gate
deliberately does not inspect. The value-refinement layer (the same mechanism
as the `.refn` guards and the Critic's `[flow]` policy) closes it → 100%. The
layered story is stronger than a bare "gate 100%".

## E4 — reliability operators actually need (pass^k)

`stats.py` — Wilson score interval (a confidence-interval formula for
percentages that stays honest at small sample sizes) + pass^k (the probability that all of the
next k runs succeed), no scipy. On the **real** n=10
subagent-trial data, a 10/10 arm (an *arm* is one configuration being
compared — like a clinical trial's treatment and control groups) still has a Wilson lower bound of 72.2%, so
`pass^10` at the CI floor is 0.039 — **this is the concrete "n=10 is too few"
argument**, computed rather than asserted. The n=30 ladder in Table 5 is a
tagged SYNTH placeholder to be replaced by real n=30 runs.

## E5 — how good is English→protocol? (translation fidelity)

`efsm_equiv.py` compares two protocols by MEANING (per-role EFSM
bisimulation — an EFSM is a role's contract compiled to a state machine,
and *bisimulation* is the formal check that two state machines behave
identically no matter what happens — plus
identical conversation language), validated by `test_efsm_equiv.py` (equivalent
to itself/reformat; different under relabel/reorder/role-rename) and a `--demo`
that scores 90 real (gold, draft) pairs — gold being a known-correct reference
answer, paired with the model's draft translation — at **100% classification
accuracy**. The
four fidelity measures over 100 intents (first-draft-valid, ≤3-round repair,
equivalence rate, guard-sidecar) need the LLM draft loop and are pending; the
hard deterministic part — comparing meaning — is done and reusable.

## E6 — does it scale? (roles sweep)

`roles_sweep.py` — a deterministic structural proxy for coordination cost as a
pipeline grows 2→10 roles: global-text (every role re-reads the whole protocol
each turn) vs STJP (scheduler polls one enabled sender; each reads only its
projected contract). The ratio climbs **9.2× → 17.1×**, confirming the SHAPE
(global-text super-linear, STJP ~linear). Token-per-delivered-goal needs live
runs and is pending.

## E7 — is it portable? (cross-runtime)

`cross_runtime.py` — the standalone dependency-free monitor emitted by
`monitor_codegen.py` (a separate "runtime") agrees with the in-process
`SessionMonitor` on **100%** of role-checks over canonical conformant traces.
(Async-reordered traces diverge by the documented strict-sequential codegen
limitation, out of scope.) The three-harness live comparison (MAF, i.e.
Microsoft Agent Framework / LangGraph / skills+hooks; conformance + GCR, the
goal-completion rate) needs those adapters and is pending.

## E3 — story vs model strength (capability sweep)

`capability_sweep.py` — MEASUREMENT PENDING (needs multiple model families +
Azure). Holds the run plan, the two real anchor points (gpt-4o: 4 disasters,
+60 enforcement gain; gpt-5.4: 22 disasters, 0 gain), and clearly-tagged SYNTH
targets so Fig 3c renders now. This is the honest home of the "B ties C+"
finding: it converts an awkward tie into a *predicted curve*, paired in the
text with the criticality axis (for tasks where one disaster is unacceptable,
"cannot misbehave" beats "happened not to misbehave" at any capability level).

## §10 — swapping real numbers in

- Figures: `make_figs_v2.py` reads REAL panels from the E* report JSONs and
  inline SYNTH arrays for pending panels; SYNTH panels carry a "projected
  (synthetic)" corner tag. Set `SYNTH_TAGS = False` to drop them once real.
- Tables: `experiments/reports/TABLES_v2.md`; every synthetic cell ends with
  "synthesized target; measurement pending" — grep that string to find them
  all. **Do not submit while that sentence exists.**
