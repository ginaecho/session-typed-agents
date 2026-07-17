# Is the STJP Benchmark Fair? — A Review in Plain English

**Date: 2026-07-17.** This review checked whether the benchmark behind the
headline results ("bare agents: 0% success; full STJP: 100% success, 9×
cheaper, 4× faster") is a fair comparison, by reading both the documentation
(`docs/2_TESTING_STRATEGIES.md`, `docs/3_BENCHMARK_DESIGN_EXPLAINED.md`) and
the code that actually produces the numbers (`experiments/scripts/case_runner.py`,
`experiments/baselines/`, `experiments/scripts/evaluate_run.py`).

One term used throughout: an **arm** is one configuration being compared —
like the treatment group and the control group in a medical trial. "Bare" is
the arm where agents get only the task description; the STJP arm adds the
checked protocol, the message-blocking gate, and the turn scheduler.

---

## The short answer

The benchmark design is unusually honest — the docs openly admit things that
weaken the story, which builds trust. Most of the fairness rules the docs
promise are really implemented in the code.

But two real problems were found in how results are **scored**, and they both
lean in STJP's favor. Two more problems affect the cost and speed claims.
The good news: all of them are fixable by changing how we *measure*, not by
changing the STJP system itself. And after fixing them, the story is likely
*more* convincing to a skeptical reader, not less — because the remaining
gap is one nobody can argue with.

---

## What the benchmark already does well

**Every team gets the same briefing.** Each arm's prompt contains the same
task description, the same goal descriptions, the same one-line explanation
of what each role does, and the same "here is how you know you are finished"
hint. The code comments even explain why: without this, the no-protocol team
would lose simply because nobody told it what a "TaxVerifier" is — and then
the benchmark would be measuring briefing quality, not protocols.

**One change at a time.** The three strongest arms differ by exactly one
mechanism each: contract only → contract + gate → contract + gate + scheduler.
The prompts of the last three are identical. So if the scheduler arm is
cheaper than the gate arm, the scheduler is the only possible cause. This is
how a comparison should be built.

**Honest cost bookkeeping.** When the gate blocks a wrong message and the
agent has to try again, the tokens spent on the blocked attempt still count
against the STJP arm. Failed trials count too: the headline cost metric
divides total tokens by the success rate, so an arm that is cheap but rarely
finishes is correctly charged for its failures.

**Everything is auditable.** Every prompt each agent saw is saved to disk
with a fingerprint (a checksum), so a reviewer can verify after the fact
exactly what each arm was told.

**The docs don't oversell.** They admit that on a strong model, simply
pasting the whole protocol as text also reaches 100% success — and that
STJP's advantage is bigger on weaker models and bigger protocols. Admitting
this is rare and it is the right thing to do.

---

## Problem 1 (the big one): the pass/fail rule asks the no-protocol team to guess secret words

**How scoring works today.** A trial "succeeds" if the message log contains
events that match each goal's expected *sender, receiver, and message label*
exactly. A message label is the tag on a message, like `RevenueAuditApproval`.

**Why that is unfair to the bare arm.** Take goal G3 of the finance case.
The bare team's prompt says, in plain words: *"the tax verifier must approve
the audit explicitly."* But the scoring rule actually checks: *did TaxVerifier
send a message labelled exactly `RevenueAuditApproval` to RevenueAnalyst?*
The bare team was never shown that label, and never told the approval must go
to RevenueAnalyst specifically. A bare team that performs a perfect audit
approval — right content, right people, wrong wording — scores **zero**.

A small analogy: it is like grading an essay exam by checking whether the
essay contains the exact sentence from the answer key. The protocol teams
were handed the answer key (the protocol *is* the list of expected labels);
the bare team was not.

**The project already knows this.** The post-run evaluator
(`evaluate_run.py`) computes three scoring rules — strict label match, a
looser "right people, right content" rule, and an LLM judge that reads the
conversation and decides if the goal was met in spirit. Its own comment says
the strict rule is *"unfair to test their ability to match labels they were
never given"* and marks it not-applicable for bare arms. **Yet the headline
success number (`success_rate_pct` in `summary.json`, the "0%" in the README
table) is produced by exactly that strict rule**, inside `case_runner.py`.

There is a second cost: the runner retries each failed trial up to three
times, and "failed" is judged by the strict rule. So the bare arm burns up to
three full runs chasing a target it cannot see — which also inflates its
token bill.

**The fix.** Use the looser rules — which already exist — as the headline
metric for comparisons that include the bare arm. Keep the strict rule as a
secondary metric among the arms that were actually given the vocabulary.
(An alternative: put the expected labels into every arm's prompt, which makes
the strict rule fair — but then the bare arm is no longer truly "bare.")

Expect the bare arm's score to rise from 0% to something real. That is fine.
"Bare teams succeed 30% of the time, STJP 100%" is a *more* believable
result than "0% vs 100%", because the 0% currently invites the question
"did you just rig the grading?" — and today the honest answer is "partly."

---

## Problem 2: different teams are graded against different answer keys

The protocol arms use a protocol that an LLM drafted (and the checker
approved), so their goals were "re-anchored" — re-pointed at that protocol's
message labels. Re-pointing the *labels* is necessary and fair. But comparing
the two goal files shows the rewritten key also got **easier**:

- Goal G3 originally passes only if the approval text contains "approved" or
  "ok". The rewritten key *also* accepts "true". So a protocol-team agent
  that replies `true` passes; a bare-team agent doing the same fails.
- Goal G5 originally requires the expense analysis to be more than 10
  characters, sent from ExpenseAnalyst to Writer. The rewritten key accepts
  *any non-empty text*, sent to a different receiver.

Each difference is small, but they all lean the same way: the protocol teams
sit a slightly easier exam.

**The fix.** Make the re-anchoring step change *only* the labels, never the
pass conditions, and add an automated check that fails loudly if the two goal
files differ in anything but labels. That way this can never drift again.

---

## Problem 3: the stopwatch is shared

All the Foundry arms run **at the same time**, against the **same** Azure
model deployment, which has a shared rate limit. When the service says "too
many requests," the code waits and retries — and that waiting counts in the
trial's clock time.

Picture six runners timed on one narrow track simultaneously: everyone's
time includes shoving. Worse, the arm that makes the fewest calls (the
scheduler arm) gets shoved the least. So "4× faster" mixes two things:
genuinely fewer steps, and suffering less from a traffic jam the benchmark
itself created.

**The fix.** For any speed claim, run the arms one at a time (or on separate
deployments). Or drop the wall-clock claim and report only calls and tokens,
which are unaffected by the traffic jam.

---

## Problem 4: the 9× saving is partly from beating a weak opponent

Where does the scheduler's saving come from? The non-scheduled arms take
turns in a fixed circle ("round-robin"): every agent is asked "your move?"
in rotation, even when it obviously has nothing to do. Each pointless ask is
a full paid LLM call, carrying the whole conversation so far. In a six-agent
pipeline where mostly one agent acts at a time, roughly five of every six
asks are wasted. The scheduler eliminates that waste — hence the big saving.

But there is a much simpler rule that also eliminates most of it, with no
protocol at all: *"next, ask whoever just received a message."* The
benchmark never tests that rule. So today's comparison shows "smart
scheduling beats the dumbest possible scheduling," which is not quite the
claim STJP wants to make.

**The fix.** Add the simple rule as a baseline arm. Then show where it
breaks and the protocol-derived scheduler does not: cases with branching
(the next actor depends on a decision), fan-in (several agents must all
report to one), or two agents legitimately active at once. Those cases exist
in this repo already (`finance_nested`, `intel_report`, `auction`). Winning
*there* is the honest — and stronger — version of the scheduling claim.

---

## Problem 5: the enforced team also gets whispered hints

The gate arm is described as "same prompt, but wrong messages get blocked."
In the code it does a bit more: when an agent is at a point where the
contract says it must send something, the runner adds a line to its turn
like *"you are at state 5; the available action is: SEND AuditReport to
RevenueAnalyst."* That is not enforcement — that is telling the agent the
answer for this turn.

So the comparison "contract vs contract + gate" really measures "contract
vs contract + gate **+ per-turn hints**." The hint may well be a legitimate
product feature (it exists to prevent stalls), but then the docs should say
the gate arm includes it, and ideally one run should test the gate with
hints switched off, so we know how much each part contributes.

---

## Smaller issues, quickly

- **Prompts can be silently cut off.** The Foundry service truncates agent
  instructions at 8,000 characters. The long-form contract arm and the
  paste-the-whole-protocol arm can exceed that on bigger cases. The
  truncation is recorded in a log file, but nothing warns you in the results
  summary. A clipped prompt makes that arm look worse for the wrong reason.
  Fix: make the run fail (or stamp a warning into the summary) if any
  compared arm was clipped.
- **Ending the conversation costs the non-scheduled arms extra.** The
  scheduler arm knows from the contract when everyone is done and stops
  instantly. The other arms stop only after every agent has said "nothing to
  do" enough times in a row — for six agents, that is up to 13 extra paid
  calls just to say goodbye. This is a real STJP advantage, but it should be
  reported as its own line, not silently folded into "9× cheaper."
- **Ten trials, no error bars.** With 10 trials per arm, "100% vs 60%" looks
  decisive but the statistical uncertainty ranges overlap (roughly 72–100%
  vs 31–83%). The repo already contains the code to compute these ranges
  (`experiments/scripts/stats.py`) — it just isn't used in the headline
  tables. Fix: print the ranges everywhere, and use 30+ trials for headline
  claims.
- **The cost of making the protocol is billed to nobody.** An LLM drafts the
  protocol and another step re-anchors the goals; those calls are not
  counted in any arm. It is fair to treat this as a one-time setup cost —
  but it should be disclosed as a line item.
- **The data is made up.** Agents have no files or tools; every number in
  the pipeline is invented by the model on the spot (the docs admit this).
  So the "no guessing — report only real numbers" safety property currently
  tests message formatting, not real data provenance. A variant where a tool
  actually serves the revenue number would make the safety claims solid.

---

## How to make STJP's advantages genuinely convincing

1. **Fix the scoring first** (Problems 1 and 2). This is the credibility
   foundation — every other claim inherits doubt from it.
2. **Show the trend, not one number.** The projection saving (each agent gets
   its own small slice instead of the whole plan) should *grow* with team
   size: the slice stays small while the whole plan grows. Run the same
   comparison at 6, 10, and 20 roles and plot tokens-per-success against
   team size for each arm. Two lines that spread apart as teams grow prove
   the point structurally — far better than any single "9×".
3. **Sweep weak models.** The docs already admit strong models mostly comply
   on their own. Turn that into a result: run bare vs gate on a weak, a
   medium, and a frontier model, and show the gap shrinking. "Enforcement
   substitutes for model capability" is a stronger pitch than "it also helps
   the best model a little."
4. **Lead the safety story with blocked messages.** Even in the arm that
   succeeded 100% of the time, the gate blocked 10–12 wrong send-attempts
   per trial. That is the strongest evidence in the whole repo: the model
   *did* try to stray; enforcement caught it every time. Grade how bad those
   blocked messages would have been (how many were a "file the report before
   the audit" class of mistake) and report it.
5. **For the deadlock claim, report a rate, not a demo.** One hand-built
   deadlocking protocol proves little. Generate many LLM-drafted protocols
   and report what fraction were unsafe and got caught by the checker before
   any tokens were spent. That number *is* the value of static checking.
6. **Add stronger competitors.** The realistic alternative to STJP is not
   agents shouting in a circle — it is a hand-wired flow graph (the
   LangGraph style) or pasted protocol text plus a cheap regex checker.
   Beating those is the comparison practitioners actually care about.

---

## Where each fix lives

| Fix | File(s) |
|---|---|
| Headline metric → looser scoring | `experiments/scripts/case_runner.py` (success rule), `evaluate_run.py` |
| Goal re-anchoring must not change pass conditions | `experiments/scripts/re_anchor_goals.py` + a new invariance check |
| Sequential runs for timing | `case_runner.py` (wave logic in `run_case`) |
| "Ask the last receiver" baseline arm | `experiments/baselines/registry.py`, `foundry_runner.py` |
| Gate-without-hints ablation | `foundry_runner.py` (the "liveness nudge" block) |
| Truncation warning in summary | `case_runner.py` (`_persist_prompts` → `summarize_run`) |
| Error bars in tables | `case_runner.py` `summarize_run` + `stats.py` (already written) |
