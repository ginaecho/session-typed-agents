# ICLR Readiness Report — STJP paper (v10.1, 2026-07-19)

This report scores the current draft (`v10/main.tex`, retitled *"Compile the
Conversation of Multi-Agent Coordination: Provably Safe and More
Token-Efficient"*) against what ICLR reviewers are told to check — whether the
paper is clear, technically correct, experimentally rigorous, reproducible,
and novel, and above all whether it *supports its claims* ([ICLR reviewer
guide](https://iclr.cc/Conferences/2025/ReviewerGuide),
[2026 edition](https://iclr.cc/Conferences/2026/ReviewerGuide)). It then
lists, in priority order, exactly which experiments would close the gaps,
with the commands from this repository and rough costs from
`docs/reference/COST_ESTIMATES.md`.

One term used throughout: an **arm** is one configuration being compared —
like the treatment and control groups of a medical trial. "Bare" is the arm
that gets only the task description; the STJP arm adds the checked protocol,
the message-blocking gate, and the turn scheduler.

## Menu

- [Scorecard against ICLR criteria](#scorecard-against-iclr-criteria)
- [What v10.1 already fixed](#what-v101-already-fixed)
- [The gap list: a prioritized experiment plan](#the-gap-list-a-prioritized-experiment-plan)
- [A non-experimental gap: the page budget](#a-non-experimental-gap-the-page-budget)
- [Venue-fit verdict](#venue-fit-verdict)

## Scorecard against ICLR criteria

| Criterion | Rating | One-line justification |
|---|---|---|
| **Novelty** | **ready** | Type-checking deployed skill files as a protocol language, enforced on free-running untrusted agents, is genuinely new; the concurrent-work boundary (ZipperGen) is argued carefully and honestly. |
| **Evidence** | **weak** | The n=100 suite and nine real-skills cases are strong, but the headline finance tables were scored under the pre-audit strict rule (bare-arm 0% is partly manufactured by the grading) and have not been re-run under the fair per-arm rule. |
| **Baselines** | **weak** | Bare agents and pasted-protocol text are the only live competitors; the realistic alternative — a hand-wired flow graph (LangGraph style) or protocol text plus a cheap checker — is never run, and the cheap-scheduler control exists but has no live numbers. |
| **Ablations** | **weak** | The two ablations a reviewer will ask for first (gate without per-turn hints; protocol-free last-receiver scheduling) are built and pre-registered but pending — the paper currently cannot separate "blocks wrong messages" from "whispers the next move". |
| **Statistical rigor** | **weak** | Wilson 95% intervals are now reported and the n=100 suite is well-powered, but the live frontier-model runs are n≤10 per cell (adjacent arms overlap), and the n=100 trials use cheap subagent role-players rather than frontier models. |
| **Reproducibility** | **ready** | Appendix B now gives layout, commands, what summaries record, the determinism boundary, and costs; traces are the artifact of record and evaluators are bit-reproducible. (Caveat: some early run directories are not committed.) |
| **Clarity** | **weak** | The prose is precise and the honesty devices are excellent, but the abstract is ~600 words, the paper is ~23 pages against ICLR's 9–10-page main-text limit, and several sections carry three papers' worth of content. |

## What v10.1 already fixed

The 2026-07-17 fairness audit (`docs/BENCHMARK_FAIRNESS_REVIEW.md`) found
that the old headline metric graded the bare arm against message labels it
was never shown — like grading an essay by whether it contains the answer
key's exact sentence. The v10.1 edit aligned the paper with the fixes: the
per-arm success rule is now defined in the methodology, every pre-fix table
is labeled with the caveat and its Wilson intervals, wall-clock numbers from
contended parallel runs are marked indicative, the two new ablation arms are
described as pre-registered predictions (no invented numbers), and the
Limitations and Reproducibility sections carry the audit's findings. What
the edit could *not* do is produce the re-run numbers — that is the gap
list below.

## The gap list: a prioritized experiment plan

Ordered by how much reviewer doubt each experiment removes per dollar.
Costs assume the gpt-4o-class deployment (`docs/reference/COST_ESTIMATES.md`;
a mini-tier model costs ~15× less and is fine for shakeout runs). The
`--arms` flag scales cost linearly, so partial runs are cheap.

**1. Fair-rule re-run of the headline finance comparison at n≥30.**
This is the credibility foundation: every table a reviewer reads first is
currently a lower-bound-labeled pre-fix number. Re-run the five core arms
under the per-arm rule, sequentially (so the wall-clock column becomes
usable too), and let the bare arm score whatever it really scores —
"bare succeeds 30%, STJP 100% with disjoint intervals" is *more*
convincing than the old 0%.
`python experiments/scripts/case_runner.py finance 30 --sequential --arms bare,maf_groupchat_llmvalid,min_llmvalid,min_llmvalid_gate,min_llmvalid_sched`
Cost: ~5/15 of a full run × 3 (n=30 vs n=10) ≈ **$20–45**.

**2. The two pre-registered ablation arms, live.**
Without these the paper's causal story ("blocking is what buys safety;
the protocol is what schedules well") is a claim, not a result. Run the
hint-free gate and the last-receiver control side by side with the full
stack, on one linear case (where the control is predicted to tie) and on
the branching/fan-in cases (where it is predicted to lose).
`python experiments/scripts/case_runner.py finance 10 --sequential --arms min_llmvalid_gate,min_llmvalid_gate_nohint,min_llmvalid_gate_lastrecv,min_llmvalid_sched`
then the same for `finance_nested`, `intel_report`, `auction`.
Cost: 4 arms ≈ 4/15 of a full run per case ≈ **$6–12 per case, ~$30–50 total**.

**3. Weak-vs-strong model sweep on one case, bare vs gate.**
The paper's best pitch — "enforcement substitutes for model capability;
the gap closes on strong models but the gate's zero is a guarantee, not an
average" — is currently carried by subagent ladders. Run it with real
hosted models at three tiers (e.g. gpt-4o-mini / gpt-4o / the strongest
available deployment) and plot the closing gap.
Same runner, three `AZURE_OPENAI_DEPLOYMENT` values, 2 arms:
Cost: ≈ 2/15 × 3 models ≈ **$10–25** (the mini tier is nearly free).

**4. The scaling chart, run live (6 → 10 roles, then 20).**
One number ("9×") invites haggling; two diverging lines do not. The
projection saving should *grow* with team size because each agent's slice
stays small while the whole plan grows — showing that trend is structurally
convincing in a way no single ratio is.
`python experiments/scripts/scaling_chart.py run` then `plot`
(6-role `report_pipeline`, 10-role `report_pipeline_large`; a 20-role case
needs authoring first — reuse the case-creation guide in
`docs/4_HOW_TO_CREATE_USE_CASES.md`).
Cost: ≈ 5M tokens ≈ **$15–20** for the existing two sizes; budget ~$20–30
more for a 20-role case.

**5. External-framework baseline (hand-wired DAG, LangGraph style).**
The realistic competitor to STJP is not agents shouting in a circle — it
is an engineer hand-wiring the flow as a graph. The E7 portability adapter
already executes ladder protocols as LangGraph StateGraphs, so the build
cost is modest: run the finance case as a hand-wired graph arm and compare
cost and safety. The honest expected result: the DAG matches STJP on cost
for a fixed linear flow, and loses on branching/authorization cases plus
everything static checking catches at authoring time. Reporting that
honestly is the strongest positioning move available.
Cost: engineering ~1–2 days; runs ≈ **$5–15**.

**6. Authoring-risk rate at scale (a rate, not a demo).**
"The checker caught 4 of 5 LLM drafts" is an anecdote. Generate 100+
LLM-drafted protocols across varied intents, and report the fraction
rejected as unsafe before any token was spent, by defect class. Drafting
is cents per protocol and validation is free, so this is the cheapest
headline number in the whole plan; it also doubles as the T0 baseline row
of the seam program (`experiments/seam_bench/`).
Cost: **$5–20**.

**7. Semantic-judge rung as a cross-check on the headline metric.**
The evaluator already computes a third scoring rung (an LLM judge that
reads the conversation and decides whether the goal was met in spirit).
Run it batched over the existing and new run directories, calibrated
against a small human-labeled sample, and report agreement between the
mechanical per-arm rule and the judge. If they agree, the mechanical rule
gains trust; if they diverge, that is a finding.
`python experiments/scripts/evaluate_run.py <run_dir>` (judge rung);
Cost: judge calls over existing traces ≈ **$5–15**.

Total to close the evidence, baseline, and ablation rows: roughly
**$100–200 of compute** plus a few days of run-shepherding — small against
the cost of a rejection cycle.

## A non-experimental gap: the page budget

ICLR's main text limit is 9–10 pages. The current draft is ~23 pages
because it contains three papers: the compiler + finance/n=100 evaluation
(the ICLR paper), the seam training program (§8, currently all-pending
templates), and the three typed extensions (§9). The submission-shaped move
is to keep paper one in the main text, compress §8 to a half-page "the seam
is trainable and instrumented; program pre-registered" paragraph, and move
§9 and most of the audit detail to appendices. The 600-word abstract needs
to come down to ~200 words; the current one reads as a summary section, and
reviewers read overlong abstracts as a clarity signal.

## Venue-fit verdict

ICLR is a defensible first choice, but not the obviously best one. The case
for ICLR: the contributions are framed as an empirical program about LLM
agents — benchmarks, ablations, capability sweeps, a released suite — and
ICLR now publishes exactly this class of work (the paper itself cites
ST-WebAgentBench at ICLR 2026); the session-type theory is imported, not
invented, so a programming-languages venue would ask "what is new in the
theory?" and the honest answer is nothing. The case against: ICLR reviewers
tend to ask "where is the learning?", and the paper's learning component
(the seam training) is precisely the part that is still pending — if the
GPU runs land in time and fill the template, the ICLR fit improves sharply;
if they do not, the strongest alternative homes are NeurIPS
Datasets & Benchmarks (the released 1,200-trial suite plus the real-skills
corpus is a first-class benchmark contribution and that track rewards the
paper's unusual measurement honesty) or a top software-engineering venue
like ICSE/FSE (where "a compiler and runtime monitor for deployed agent
artifacts, evaluated on real skill files" is a central systems
contribution and n=10 live runs raise fewer eyebrows). Recommendation:
run gap items 1–3 regardless of venue, then decide by whether the seam
numbers exist — with them, ICLR; without them, NeurIPS D&B.

Sources: [ICLR 2025 Reviewer Guide](https://iclr.cc/Conferences/2025/ReviewerGuide),
[ICLR 2026 Reviewer Guide](https://iclr.cc/Conferences/2026/ReviewerGuide),
[ICLR 2024 Reviewer Guide](https://iclr.cc/Conferences/2024/ReviewerGuide).
