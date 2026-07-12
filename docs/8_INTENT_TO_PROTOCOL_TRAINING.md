# Intent → Protocol Training

How the piece of STJP that turns a plain-English request into a
Scribble-checked coordination plan gets machine-learned — and what you can
run today, on this repo, to see it in action.

**Date: 2026-07-11**

---

## 1. The gap this closes

Every STJP guide so far starts from a protocol that already exists. This
section is about where that protocol comes from in the first place.

STJP's front door is a two-step loop:

```
Natural-language intent  ──►  LLM drafts a global protocol (a .scr file)
                                        │
                                        ▼
                          Scribble validator checks it
                                        │
                        rejected + counterexample ──► LLM redrafts
                                        │
                                    accepted
                                        │
                                        ▼
                              human endorses the protocol
```

We call this the **S1→S2 seam**: S1 is the intent (what the user actually
asked for, in plain English), S2 is the validated global protocol (the
formal plan `1_TECH_SETUP.md` describes). Today a person drafts the intent,
an LLM drafts the protocol, Scribble rejects bad drafts, and a human signs
off on the survivor. The live evidence that this loop is real and not just
diagrammed: the repo's own banking case took **four rejected drafts before
the fifth passed** — one recorded trajectory of exactly the repair loop this
document is about training.

### Why this loop is trainable

Most things people want to train a model to do have no automatic scorer —
you need a human to say "yes, that's good." This loop is different, because
the target side is already fully mechanized:

- The **grammar** — Scribble's surface syntax — is small and known.
- The **validator** — the real Scribble compiler — either accepts or
  rejects a draft, and rejection comes with a specific counterexample
  ("Role not bound: R1Undeclared").
- The **equivalence scorer** (built for a different guide's E5 experiment,
  validated 300/300) can check whether two protocols behave *identically*,
  not just whether either one is individually valid.

Stack those three and you get a **verifier hierarchy**: does it parse? is it
safe? is it the same as a known-correct answer? Every level is
deterministic, free to run (no human, no API call needed at that level),
and tells you exactly what's wrong when it says no. That is precisely the
setup machine-learning research calls "verifiable rewards" — you can train a
model by rewarding it for passing a free, automatic checker, the same way
code-generation models are trained against unit tests. STJP's checker is
stronger than a unit test, though: it doesn't sample a few behaviors, it
proves a property over *every* possible path through the protocol.

### Why validity alone is not enough

A protocol can pass every one of those checks and still be **wrong** — safe,
well-formed, deadlock-free, and describing a conversation the user never
asked for. Validity is a property of the protocol by itself; **faithfulness**
is a property of the (intent, protocol) *pair*, and nothing mechanical
checks it today except a human reading both. If you trained a model purely
to maximize "does it pass the validator," it would learn to draft simple,
easy-to-validate protocols — not the ones the user actually meant. This is
the standard failure mode of optimizing an incomplete reward (reward
hacking), and it is why this program needs a second instrument, not just a
faster validator.

---

## 2. The two instruments

### A. The verifier stack — for validity

Three checks, increasingly strict, all deterministic:

1. **Parses** — is the text legal Scribble syntax at all?
2. **Is safe** — does the real Scribble validator accept it (no deadlocks,
   roles consistent, every path terminates)?
3. **Is behaviorally equivalent to gold** — when a known-correct protocol
   exists, does this one allow exactly the same message sequences? ("Gold"
   here means a protocol we already trust is correct — either hand-written
   or a synthetic one built by the data pipeline in §3.)

Level 3 uses the same **EFSM bisimulation** idea `6_RUN_REPORTS_EXPLAINED.md`
covers for the E5 experiment: convert each agent's slice of the protocol
into a small state machine (an EFSM), then check that both protocols' state
machines accept exactly the same conversations. Two protocols that are
"bisimilar" are indistinguishable from the outside — the strictest
practical notion of "these mean the same thing."

### B. The memoryless judge panel — for faithfulness

Because nothing mechanical can read "the user's true intent," faithfulness
is approximated with a **panel of LLM judges voting on intent–protocol
fit** — under a strict rule: **no judge shares memory with any other
judge, or has any memory of its own.** Each judgment is one fresh, isolated
call: fixed question, one specific view of the case, no tools, no session,
no knowledge that other judges even exist.

This matters because votes are only meaningful if the voters' mistakes are
independent. If every judge sees the same context (the drafting trace, each
other's opinions, prior verdicts), their errors become correlated — a
7-judge panel quietly turns into one judge with seven rubber stamps. Strict
isolation is what keeps a "panel" from being theater.

Three judge classes sit on one panel, each seeing a **different, deliberately
restricted** view:

| class | sees | catches |
|---|---|---|
| **J-fwd** (forward checklist) | the intent + the protocol | gross mistranslation — missing roles, wrong order, forbidden interactions. Cheapest, but most exposed to confirmation bias (it can rationalize a protocol because it's holding the intent while reading it). |
| **J-back** (blind back-translation) | **the protocol only** — never the intent | confirmation bias directly: it writes down what intent it thinks the protocol encodes, and a separate score compares that reconstruction to the real intent. It literally cannot be led, because it never sees the thing it might be led toward. |
| **J-probe** (compiled behavioral probes) | intent fragments turned into concrete yes/no questions ("can Auditor receive the report before Approver signs?") | these questions are answered **by a deterministic state-machine check** over the protocol, not by an LLM's opinion — the LLM's only job is translating the question into a checkable query. A failed probe is a veto, not a vote. |

### The live smoke test — a faithfulness catch, in plain language

On 2026-07-11 this panel ran for real (`docs/reference/reports/seam/PANEL_SMOKE_2026-07-11.md`)
over three known-good (intent, protocol) pairs plus one deliberately swapped
pair, using 14 isolated judge calls.

- **The swapped pair (canary — a planted check item with a known correct
  answer):** intent from the banking case paired with
  the protocol from the travel case. Both forward judges correctly said "no
  match" at 0.99 confidence — proof the panel isn't a rubber stamp.
- **The interesting catch — `trade_deadlock`:** this case's intent literally
  describes a deadlock ("Buyer releases payment only after goods received;
  Seller releases goods only after payment" — each side waiting on the
  other, forever). The protocol on file doesn't implement that deadlock; it
  implements a working escrow (a neutral third party that holds funds until
  both sides deliver) sequence that avoids it. Both forward judges,
  seeing the intent and the protocol side by side, rated this **faithful**
  (0.88 and 0.82) — reading the escrow protocol as a reasonable way to
  satisfy the intent's spirit. The blind J-back judge, seeing **only the
  protocol**, wrote down what it looked like on its own terms: "a strictly
  linear escrow happy-path." Compared against the actual original intent,
  that reconstruction scored only **0.25** — because the original intent,
  read literally, describes something the protocol does *not* do (it
  describes a deadlock, and the protocol is deadlock-free by design). The
  panel escalated the case rather than voting it through.
- **What this demonstrates:** the protocol is arguably a *repair* of a
  broken intent, not a literal translation of it — and whether "silently
  fixing the user's deadlock" counts as faithful is a policy question for a
  human, not something a vote should quietly decide. That is exactly the
  failure mode J-back exists to surface, caught on the very first live run.

---

## 3. What exists today

Everything below is built, tested, and has a one-command way to run it in
this repo. Component order follows the pipeline: get the real toolchain
working, constrain what the model can even output, generate training data,
measure things, judge faithfulness, then go looking for real-world intents
in the wild.

| component | what it does | one-command usage | evidence |
|---|---|---|---|
| **Toolchain setup** | Installs and connects the *real* Scribble-java compiler (never a Python approximation) plus the optional nuscr backend, and self-tests that it accepts a known-good protocol and rejects a corrupted one. | `bash tools/setup_scribble_cloud.sh` | 30/30 corpus protocols pass real validation; a corrupted control is rejected with a genuine parser error (`docs/reference/reports/seam/W1_eval_harness.md` §3) |
| **Grammar / grammar-constrained decoding (GCD)** | A formal grammar for Scribble's syntax (`stjp_core/compiler/scribble_grammar.lark`), plus an adapter that turns it into the format vLLM/xgrammar need to force a model's output to *always* be syntactically legal Scribble — deleting the "my draft didn't even parse" failure mode outright. | `python -m pytest stjp_core/tests/test_scribble_grammar.py` | 113/113 real corpus files round-trip; 1000/1000 randomly sampled protocols parse under both the grammar and the production parser; 15/15 corrupted negatives correctly rejected (`docs/reference/reports/seam/W2_grammar_gcd.md`) |
| **Data builders** | Turns the ~50 hand-written seed protocols into thousands more (by sweeping parameters, composing sub-protocols, and crossing over fragments — every candidate re-validated, never hand-approved), writes plausible-sounding intents *for* those protocols so training pairs exist without a human writing either side, and builds "broken protocol + validator's own error message → fixed protocol" repair pairs from the mutation testing already used elsewhere in STJP. Splits everything by protocol family so no near-duplicate leaks across train/dev/test. | `python experiments/seam_bench/data/d1_expand.py --target 800 ...` (families) · `python experiments/seam_bench/data/d3_repair.py ...` (repair pairs) · `python experiments/seam_bench/data/splitter.py ...` + `leakage_check.py` (splits) | 671 unique valid families from one 22-minute bounded run; the family-equivalence signature agrees with the repo's real equivalence checker on 200/200 pairs; leakage check reports **GREEN** on a 599/76/76 train/dev/test-syn split (`docs/reference/reports/seam/W3_data_builders.md`) |
| **Eval harness + metrics** | The standing scoreboard: validity, validity-under-GCD, equivalence-to-gold, repair rounds needed, tokens/dollars spent per accepted protocol, and the transfer gap between synthetic and real-world test items — all with proper statistics (bootstrap confidence intervals, not bare averages), plus a guard that logs every time a held-out test split is opened. | `python -m experiments.seam_bench.eval.smoke` | 86/86 tests pass; the smoke run validates all 30 real corpus protocols and correctly rejects all 60 corrupted copies of them (`docs/reference/reports/seam/W1_eval_harness.md`) |
| **Judge panel** | The §2 faithfulness panel as deterministic Python: strips anything from a protocol that could bias or persuade a judge (all comments removed before a judge ever sees it), runs the isolated J-fwd/J-back/J-probe calls, verifies every judge's cited evidence actually appears in what it was shown (discarding fabricated citations), and combines verdicts with an outlier-resistant aggregation method rather than a plain vote average. | `python -m pytest experiments/seam_bench/judge/tests/` (offline) · `python -m experiments.seam_bench.judge.run_panel --protocol <path> --intent "<text>"` (a real live run, once an API key or subagent transport is available) | 62/62 tests pass offline; the live run described in §2 (`docs/reference/reports/seam/W6_judge_panel.md`, `docs/reference/reports/seam/PANEL_SMOKE_2026-07-11.md`) |
| **Real-skills miner** | Goes looking for real, human-written coordination intent in the wild — public repos of AI agent "skill" files — recovers the human-written description as the intent (nobody had to write it for training purposes), and tries to turn the skill files themselves into a validated protocol, to see whether real-world intents and real-world skill definitions actually agree with each other. | `python experiments/seam_bench/mining/run_mining.py --out-dir <dir> --remote-root <dir>` | see below — a genuinely negative, well-diagnosed result (`docs/reference/reports/seam/W8_miner.md`) |

### The miner's honest finding: 609 → 0

The real-skills miner is worth calling out on its own, because its result
is a **negative finding, reported honestly rather than smoothed over** — and
it's exactly the kind of evidence this training program is supposed to
surface. Run against three real public repositories (`github/awesome-copilot`,
`VoltAgent/awesome-claude-code-subagents`, `anthropics/skills`, cloned live,
commit SHAs recorded):

```
609 files harvested
 → 605 pass license filtering
 → 594 have a recoverable, human-written intent
 → 53 get grouped into 13 candidate multi-agent "teams"
 → 0 of those 13 teams survive automatic conversion into a protocol
```

The funnel doesn't die from a bug — it dies at one specific, well-understood
step: STJP's protocol builder expects skill files written in one of two
specific STJP-internal formats, and (unsurprisingly) **no file harvested
from a public GitHub repo was ever written in either format**, because
nobody outside this project has a reason to write one that way.

Two controls locate the failure in the inputs rather than in the pipeline:
a synthetic team built *with* the expected format sails through the
identical code path to a validated protocol, and for the four mined
`skills_safety` teams where an earlier, LLM-assisted compaction had already
produced per-role types, the originals still fail multiparty compatibility.
The useful takeaway isn't "the miner is broken" — it's a measured data
point that independently authored skills do not state their coordination
structure in any machine-recoverable convention. To separate *structure
absent* from *structure implicit in prose*, we ran the follow-up: a careful
model-read extraction over the same 13 teams, under a rule that every
recovered interaction must quote the skill text (no invented coordination).
Reading harder recovers a little structure but not much — 3 of 13 teams
yield a valid protocol and a 4th surfaces a real deadlock — and, decisively,
those recoveries all come from this project's own worked examples; the teams
built from unmodified upstream GitHub files recover zero. So the finding
holds: ordinary skill authors do not write down interaction structure even
when a disciplined reader looks hard for it. One caveat the follow-up
itself exposed: the harvester groups files into "teams" without first
checking the task actually needs multi-party coordination — and 6 of the
13 turned out not to (4 single-agent tool documents, 2 grouping mistakes).
So the strongest real-world evidence is just two teams whose tasks clearly
do involve several interacting parties (pull-request review-and-merge, a
document pipeline) but whose texts contain no cross-role language; a
"does this task need coordination?" filter is the next miner improvement.
The human-read baseline is
packaged (`experiments/seam_bench/mining/human_read/PACKET.md`) and pending.
See `docs/reference/reports/seam/W8_miner.md` and `W16_llm_read_extraction.md`
for the full funnels.

---

## 4. What is pending

Two things are not built yet — deliberately, they're next:

- **T0 — real drafting baselines.** Nothing above has spent real API money
  drafting protocols from scratch with Sonnet/Opus/Haiku and measuring
  best-of-n validity, few-shot performance, or the repair loop live. This
  is meant to run first and cheaply, and it's what fills in the actual
  numbers behind everything the verifier stack in §2A can measure.
- **GPU training (SFT and GRPO).** Actually fine-tuning a small open-weights
  model on the data from §3, then reinforcement-learning it against the
  verifier stack (and, once calibrated, the faithfulness panel) is not
  something this document covers — it needs rented GPU time, a training
  stack, and its own runbook. That's `docs/reference/GPU_TRAINING_RUNBOOK.md`
  For a one-page picture of the whole pipeline — what is done, what you
  do, what the GPU does, in what order — see
  `docs/reference/TRAINING_ROADMAP.md`.
  (being written alongside this guide).

Every number this training program is allowed to call a "win" — how much
training helps, how much grammar-constraining costs in output quality,
whether reinforcement learning clears the bar SFT alone sets — is
**pre-registered before any run**, exactly like the benchmark predictions
`3_BENCHMARK_DESIGN_EXPLAINED.md` teaches you to read. The full set of
committed go/no-go thresholds (what counts as GCD paying for itself, what
counts as fine-tuning working, when the faithfulness panel is allowed to
influence training instead of just observing it) lives in
`docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md` §8 — read that document,
not this one, for the exact numbers and what happens if a threshold is
missed.

---

## 5. What to read next

- **The strategy behind this program** (why each piece is shaped the way it
  is, the research lineage it's drawing on): `docs/reference/SEAM_AUTOTRAINING_PLAN.md`
- **The executable plan** (exact stacks, hyperparameters, data formats,
  worker task cards, and every pre-registered pass/fail threshold):
  `docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md`
- **The GPU training runbook** (once T1/T2 fine-tuning actually runs):
  `docs/reference/GPU_TRAINING_RUNBOOK.md`
- **The worker reports behind every number in §3**:
  `docs/reference/reports/seam/W1_eval_harness.md`,
  `W2_grammar_gcd.md`, `W3_data_builders.md`, `W6_judge_panel.md`,
  `W8_miner.md`, and the live judge run `PANEL_SMOKE_2026-07-11.md`
- **The idea this program extends** — how STJP's core loop already works
  end-to-end, and the vocabulary this guide assumes (protocol, projection,
  validator, EFSM): `1_TECH_SETUP.md`
- **How to read any benchmark table like the ones this program will
  eventually produce** (GCR, confidence intervals, what makes a comparison
  fair): `3_BENCHMARK_DESIGN_EXPLAINED.md`
