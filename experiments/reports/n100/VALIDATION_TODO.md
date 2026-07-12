# VALIDATION_TODO — what to run next, what to re-check, and where suspected errors hide

*Written 2026-07-05, after integrating the n=100 suite into paper v4. Ordered by priority. Each item: why, how, effort, and what changes in the paper when done. The "error audit" section lists the places where I suspect the current numbers could be wrong — check those BEFORE running anything new, because they're cheap and they feed the paper's integrity story either way.*

> **Status (2026-07-05) — most of the plan is done:**
> - **P-1: complete.** All 5 suspected spots correct-as-reported; item 4
>   adjudicated (**4 genuine checker gaps** + 7 valid → detection 82.5%→92.9%,
>   a new named limitation); A/B violation-type histograms done. See
>   [`P1_AUDIT_FINDINGS.md`](P1_AUDIT_FINDINGS.md) +
>   [`e1/branch_asymmetry_adjudication.md`](e1/branch_asymmetry_adjudication.md).
> - **Material fix: complete.** 22 non-terminal trials driven to completion →
>   `escrow_trade` (the goods-for-payment case, named for its Escrow role — a
>   neutral third party that holds funds until both sides deliver; "escrow"
>   below is shorthand for this case) C+spec 79→97%, C+min 82→83%, STJP
>   97→98%; revenue A 99→100%, C-min 31→32%. Dataset 100% terminal.
> - **P0b: complete.** B + C+min on revenue_audit re-run with **sonnet**
>   (mid-tier): B 0/30 races (vs haiku 95/100), C+min 10/10 clean. See
>   [`P0B_MIDTIER_SONNET.md`](P0B_MIDTIER_SONNET.md).
> - **E3: done in-environment (3 Claude tiers, both cases).** Capability curve
>   **haiku→sonnet→opus** on revenue_audit and **haiku→sonnet** on escrow_trade
>   (n=10/arm for the new tiers, every trial verified from `state.json`,
>   `malformed=0`): unenforced safety *and* cleanliness are capability-dependent
>   and **plateau at sonnet** (opus confirms); the gate/scheduler arms are
>   capability-independent (0 disasters at every tier) and STJP holds its 4× cost
>   edge. Only the **non-Claude vendor** point remains (external access). See
>   [`E3_CAPABILITY_SWEEP.md`](E3_CAPABILITY_SWEEP.md) +
>   [`e3/opus_revenue.json`](e3/opus_revenue.json),
>   [`e3/sonnet_escrow.json`](e3/sonnet_escrow.json).
> - **E7 three-harness: now done.** A LangGraph adapter
>   (`experiments/harness_adapters/langgraph_ladder.py`) runs every case/arm as
>   a StateGraph; the native STJP monitor agrees **14/14** (clean → 0
>   violations, injected fault → caught). langgraph + langchain-anthropic
>   installed; token metering is connected (real numbers when `ANTHROPIC_API_KEY`
>   is set).
> - **Genuinely blocked (external access), documented not faked:** anything
>   needing a **live/metered LLM** — E3's non-OpenAI-vendor tier, **token-metered
>   E6** and the **live token numbers** (the LangGraph metering is code-complete;
>   only an LLM key is missing — this env's base URL needs an `x-api-key` we
>   don't have, and there's no local model), the **LLM half of E5** (needs the
>   100-intent expert golds), and the **live finance ladder** (Foundry). The
>   n=30-vs-n=100 choice there was a *cost hedge* for a paid metered run, not a
>   hard cap — n=100 is fine given a metered endpoint + budget.

---

## P-1 (do first, ~half a day): ERROR AUDIT of the existing n=100 data

These are the five places where the current results look "off" enough that a careful reviewer — or we ourselves — should poke them. Finding a bug here is not a disaster; it's a paragraph for the integrity log. Not looking is the disaster.

1. **B's 0.4 avg_seconds/trial in revenue_audit (vs 16.4s for A, 3.7s for C+spec).**
   A 3-role trial finishing in 0.4 seconds with 3.3 calls means the subagent answered nearly instantly, every time. Check: are B-arm replies real model calls or did any batch fall back to a cached/scripted path? Verify a random 10 B trials: open `state.json`, confirm each poll has a distinct, non-templated reply and a plausible timestamp gap. The 95-disaster headline depends on these being genuine model decisions. (The `malformed==calls` fraud signature was designed for a different failure mode — it would NOT catch a legitimate-looking auto-responder that answers correctly-formatted sends instantly.)
2. **A-arm revenue_audit: 99% GCR (goal-completion rate — % of trials that reached every goal) with 0 disasters but only 1% CGC (critical-goal completion — reached the goal AND had zero critical-safety violations).**
   99 of 100 trials had some violation, yet ZERO were disasters, while B (which saw MORE structure) had 95 disasters. What are those A-arm violations concretely? Pull the violation-type histogram from the traces. If they're all trivial (e.g., duplicate sends), fine — but confirm the disaster detector was actually armed on the A arm (a detector misconfigured per-arm would produce exactly this pattern). The cross-check: A's Filer must be filing AFTER approval in ~99 trials — verify on 10 sampled traces that Approval genuinely precedes Filed.
3. **C-min revenue_audit 31% GCR vs C-min escrow 100% GCR.**
   Same arm, wildly different liveness. The stall mechanism (agent resending Revenue into silence) should apply to escrow too unless the escrow protocol shape prevents it. Confirm the 31% is protocol-shape-dependent (3-role pipeline with a strict wait) and not an engine bug in the revenue config (e.g., a role's poll never being delivered). One failing trace was manually inspected — inspect five more, from different batches.
4. **The 11 surviving branch_asymmetry mutants (E1's 82.5%).**
   Classify each survivor: (a) genuine checker gap (mutant is truly ill-formed and Scribble accepted it) → report as a real limitation with the defect pattern; (b) mutant accidentally semantically valid (the "asymmetry" landed on a branch where the role's behavior legitimately coincides) → move to the correctly-accepted bucket and the detection rate rises. Either answer improves the paper; the current silent 82.5% invites the question.
5. **The 3 escrow STJP failures (97%, not 100%).**
   Pull the 3 failing `state.json`s. Expected cause: retry-budget exhaustion after repeated gate rejections (a liveness stall, not a safety event — CGC=GCR=97 confirms zero violations). Name the cause in the paper ("3 stalls under retry budget k=…; no violations") instead of leaving a bare 97%.

Also re-verify two computed numbers I derived for Table tab:ctcg: cost-to-clean-goal = total_calls / clean_count (e.g., revenue B: 330 calls / 5 clean = 66; C-min: 2319/1 = 2319). Recompute from ladder_summary.json directly and confirm the table.

## P0 (the keystone, ~2–4 days incl. API access): E3 capability sweep

Why it's now non-optional: the paper's reconciliation claim ("which unenforced arm fails depends on model/task/scheduling") rests on two model anchors. E3 turns it into a curve.
- Arms A, B, C+min at n=30 each; four model tiers (small open-weights, gpt-4o, gpt-5.4, one non-OpenAI frontier — the non-OpenAI point also kills the "one vendor" limitation).
- Task: finance (for continuity with the measured anchors).
- Report: A-arm disasters vs tier (expect rising), enforcement gain (C+min − B on CGC, not GCR) vs tier, and B's disaster count vs tier under BOTH schedulers (poll-all and turn-based) — because the ladder showed B's danger is scheduler-dependent.
- Paper change: Fig. 3c loses its "PENDING/synthetic" tag; the limitations bullet shrinks; the reconciliation paragraph gains its curve.

## P0b (protects the headline, ~1 day): mid-tier replication of revenue_audit ladder

The 95% B disaster rate is the paper's most quotable number and it currently comes from cheap haiku subagents. Rerun JUST arms B and C+min on revenue_audit at n=30 with a mid-tier model (gpt-4o class). Two outcomes: (a) B's Filer still files at round 1 under poll-all → headline is model-independent, say so; (b) the stronger model waits → the finding becomes "B's safety is model-dependent; enforcement's is not," which is STILL the paper's thesis. Either way add the **filed-at-round histogram** for B (one plot from existing traces — do this part today, zero new runs: it visually proves the concurrency mechanism).

## P1 (forensics already listed in P-1 items 4–5 feed these paper edits, ~1 day)
- branch_asymmetry survivor classification → updated E1 paragraph (and possibly a raised detection number).
- escrow STJP 3-stall explanation → one sentence in the ladder discussion.
- filed-at-round histogram → small inset or appendix figure.
- A/B violation-type histograms for both tasks → one appendix table; converts "violations" from a count into named behaviors (duplicate send, out-of-order, premature file), which reviewers trust more.

## P2 (nice-to-have, post-submission or rebuttal ammunition)
- Token-metered E6 (rerun roles sweep with a metered endpoint; replaces the structural proxy caveat).
- Three-harness E7 (LangGraph + skill-runtime adapters; currently 59/59 is in-process vs standalone monitor agreement only).
- LLM half of E5 (first-draft validity, repair rounds, guard co-emission over the 100-intent set with expert golds — known-correct reference answers written by a person) — the scorer is validated, so these numbers become trustworthy the day they're run.
- n=30 live-LLM rerun of the original finance ladder (the live-model evidence is still n≤10 there).

## What NOT to redo
E0 (40/40), E1 well-formedness (deterministic, stable across 30→100), E2 (deterministic; rerunning adds zero information), E4's infrastructure certification, the deadlock replication (0/100 vs 100/100). These are done; spend nothing further on them.

## Order of operations
Day 1: P-1 audit + filed-at-round histogram. Day 2: P0b replication. Days 3–5: E3. Then paper v5: swap Fig 3c to measured, fold forensics sentences, update limitations. Everything else is P2/rebuttal.
