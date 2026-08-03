# STJP Documentation

STJP (Session-Typed Judge Panel) machine-checks a team of AI agents'
coordination plan — who talks to whom, in what order — before they run, and
enforces it while they run. This page is the index; every document below is
self-contained.

## Benchmark campaign — the current results (read in this order)

> **The plan:** [BENCHMARK_PLAN_V3.md](BENCHMARK_PLAN_V3.md) — what runs, where
> (Foundry hosted groups + classic Agent Service), which toolchains
> (scribble-java, nuscr, MAF), the 8 settings + MAF kinds, and the evaluation
> methodology. Read this first if you want the design; the documents below are
> the results.


| Document | What it is |
|---|---|
| [6_RUN_REPORTS_V2_CLAIMS_AND_EVIDENCE.md](6_RUN_REPORTS_V2_CLAIMS_AND_EVIDENCE.md) | The claims the benchmark exists to prove, and where the evidence for each stands |
| [7_RUN_REPORTS_FOUNDRY_REAL_CASES.md](7_RUN_REPORTS_FOUNDRY_REAL_CASES.md) | The evidence tables: 12 real cases × 8 settings × 2 models on Azure AI Foundry, with verification, fair-comparison, and failure-anatomy sections |
| [8_ANALYSIS_FINDINGS.md](8_ANALYSIS_FINDINGS.md) | Six numbered findings derived from the tables (scheduling dividend, model-invariance, cost mechanisms, …) |
| [9_EVALUATION_REPORT.md](9_EVALUATION_REPORT.md) | The paper-style evaluation report (methodology + results) |
| [BENCHMARK_FAIRNESS_REVIEW.md](BENCHMARK_FAIRNESS_REVIEW.md) | The plain-English fairness review; the FAIR COMPARISON sections in 6_ and 7_ implement its standard |

These four campaign documents keep their historical numbers (6–9); the
guide series below has its own 1–8 numbering.

## Guides — how the system works ([guides/](guides/))

| Guide | One line |
|---|---|
| [1_TECH_SETUP.md](guides/1_TECH_SETUP.md) | Install and run STJP, including on Azure AI Foundry |
| [2_TESTING_STRATEGIES.md](guides/2_TESTING_STRATEGIES.md) | How STJP is tested, layer by layer |
| [3_BENCHMARK_DESIGN_EXPLAINED.md](guides/3_BENCHMARK_DESIGN_EXPLAINED.md) | Why the benchmark is built the way it is |
| [4_HOW_TO_CREATE_USE_CASES.md](guides/4_HOW_TO_CREATE_USE_CASES.md) | Step-by-step: add your own case |
| [5_ARMS_EXPLAINED.md](guides/5_ARMS_EXPLAINED.md) | Every setting drawn as one flow line |
| [6_RUN_REPORTS_EXPLAINED.md](guides/6_RUN_REPORTS_EXPLAINED.md) | The first campaign's full report (2026-07-02…08, Claude-family models) |
| [7_USE_CASE_DEADLOCK_SAFETY.md](guides/7_USE_CASE_DEADLOCK_SAFETY.md) | Why interaction safety matters — the deadlock use case |
| [8_INTENT_TO_PROTOCOL_TRAINING.md](guides/8_INTENT_TO_PROTOCOL_TRAINING.md) | Machine-learning the intent → protocol drafting step |

## Folders

- [reference/](reference/) — technical deep-dives: [GLOSSARY.md](reference/GLOSSARY.md)
  (the canonical vocabulary), how-to-run and trace guides, audits, the
  paper-style section template ([sections_eval_results.html](reference/sections_eval_results.html)).
- [results/](results/) — the numbered evidence series RESULT_00…13, each a
  self-contained plain-English report with its runnable demo.
- [predictions/](predictions/) — pre-registered predictions, written before
  the runs they predict.
- [diary/](diary/) — the project journal.
- [archive/](archive/) — historical documents, kept unchanged (including the
  previous version of this index).

## Reading paths

- **New to STJP** → [guides/1_TECH_SETUP.md](guides/1_TECH_SETUP.md), then
  [guides/3_BENCHMARK_DESIGN_EXPLAINED.md](guides/3_BENCHMARK_DESIGN_EXPLAINED.md).
- **Reviewing the current results** → the four campaign documents, in order.
- **Why STJP at all, with demos** → [results/README.md](results/README.md).
- **Looking up a term** → [reference/GLOSSARY.md](reference/GLOSSARY.md).
