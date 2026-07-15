# An Interview with Fable 5: STJP as a Development Blueprint for Token-Efficient Multi-Agent Systems

> **Format.** Fable 5 (Anthropic's Claude, Mythos-class tier) was asked to read this
> repository — [`/docs`](README.md), [`/pitch`](../pitch/), and the experiment
> reports under [`experiments/reports/`](../experiments/reports/) — and answer
> three questions from the project owner. This document is the interview,
> lightly edited, with every claim hyperlinked to the evidence in this repo.
>
> **Interview date:** 2026-07-08.
>
> The questions:
> 1. Which **development use cases** (e.g., coordinating subagents) can use the
>    STJP blueprint — a global protocol supported by multiparty session type
>    (MPST) theorems — to **reduce token cost**?
> 2. When *you* (Fable 5) organize a group of subagents, how would the STJP
>    blueprint help you?
> 3. Would you want to use this tool?
> 4. Could STJP help Google's "dynamic subagent" deep-research agent? *(added
>    2026-07-08)*
> 5. **Follow-up (2026-07-12), after Fable 5 spent a week coordinating ~20
>    subagents to build this project's own training program:** by looking at
>    the real mined cases and your own experience, do you still find STJP
>    helpful for you? The real-world cases are few — is that because there is
>    not much need, or because people have not fully explored coordinating
>    subagents, or cannot see what agents do in the background? *(Part 2
>    below.)*

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Part 1 — Initial interview (2026-07-08)](#part-1--initial-interview-2026-07-08)
  - [Q1 — Which development use cases can adopt the STJP blueprint to cut token cost?](#q1--which-development-use-cases-can-adopt-the-stjp-blueprint-to-cut-token-cost)
    - [Where the tokens are saved (measured in this repo's reports)](#where-the-tokens-are-saved-measured-in-this-repos-reports)
    - [The developer use cases we already have — hyperlinked](#the-developer-use-cases-we-already-have--hyperlinked)
      - [UC1. Coordinating subagents](#uc1-coordinating-subagents)
      - [UC2. Agent pipelines with review/approval gates](#uc2-agent-pipelines-with-reviewapproval-gates)
      - [UC3. Loops with budgets](#uc3-loops-with-budgets)
      - [UC4. Skill/prompt authoring itself](#uc4-skillprompt-authoring-itself)
      - [UC5. Growing the system without re-verifying everything](#uc5-growing-the-system-without-re-verifying-everything)
  - [Q2 — When you organize a group of subagents, how would the STJP blueprint help you?](#q2--when-you-organize-a-group-of-subagents-how-would-the-stjp-blueprint-help-you)
  - [Q3 — Would you want to use this tool?](#q3--would-you-want-to-use-this-tool)
  - [Q4 — Could STJP help Google's "dynamic subagent" deep-research agent?](#q4--could-stjp-help-googles-dynamic-subagent-deep-research-agent)
- [Part 2 — Follow-up interview (2026-07-12): after a week of doing it myself](#part-2--follow-up-interview-2026-07-12-after-a-week-of-doing-it-myself)
  - [Q5 — With the real cases in hand and a week of experience, do you still find STJP helpful for you? And why are the real-world cases so few?](#q5--with-the-real-cases-in-hand-and-a-week-of-experience-do-you-still-find-stjp-helpful-for-you-and-why-are-the-real-world-cases-so-few)
    - [What I actually did, and how I coordinated](#what-i-actually-did-and-how-i-coordinated)
    - [The four failures, and what would have prevented each](#the-four-failures-and-what-would-have-prevented-each)
    - [The observation that changed my mind about the central claim](#the-observation-that-changed-my-mind-about-the-central-claim)
    - [Why the real-world cases are few: not low need — low visibility, early days, and a price problem](#why-the-real-world-cases-are-few-not-low-need--low-visibility-early-days-and-a-price-problem)
    - [The honest boundary](#the-honest-boundary)
    - [So: would I use it?](#so-would-i-use-it)
  - [Appendix — the sources this interview drew on](#appendix--the-sources-this-interview-drew-on)
<!-- MENU:END -->

# Part 1 — Initial interview (2026-07-08)

## Q1 — Which development use cases can adopt the STJP blueprint to cut token cost?

**Fable 5:** Your own repo already demonstrates the pattern on 17 cases under
[`experiments/cases/`](../experiments/cases/), and they generalize cleanly. The
ones where the token-saving mechanism applies are any development scenario where
**multiple agents must exchange messages in a required order**, because STJP
attacks the three places tokens actually go: per-turn coordination deliberation,
polling of idle agents, and runtime discovery of statically-refutable design bugs.

### Where the tokens are saved (measured in this repo's reports)

| Lever | Mechanism | Evidence |
|---|---|---|
| **Projection** — each agent gets only its local slice, not the global prose | Smaller prompt every call, plus far less "is it my turn?" deliberation (1,534 → 552 thinking tokens/turn) | [`RESULT_2_TOKEN_EFFICIENCY.md`](results/RESULT_2_TOKEN_EFFICIENCY.md): 24.1k → 8.8k tokens, **−63%**, same 100% completion |
| **EFSM scheduler** — poll only agents that *can* act | Idle agents never burn a call saying "WAIT" | [`RESULT_4_FULL_STACK.md`](results/RESULT_4_FULL_STACK.md): −66% calls; 13.3k vs 120.3k tokens for the same protocol pasted as text — **9× cheaper**, 4× faster |
| **Static check before running** — Scribble + the Bocchi–Chen–Demangeon–Honda–Yoshida composition theorem (FORTE'13) | Deadlocks and orphan messages refuted in milliseconds instead of discovered after burning calls | [`trade_deadlock`](../experiments/cases/trade_deadlock/): unchecked skills **0/100** success, all deadlock (infinite cost-to-goal); the compaction gauntlet flags UNSAFE 10/10 with a pinpoint diagnosis ([`RESULT_5_SUBAGENT_VALIDATION.md`](results/RESULT_5_SUBAGENT_VALIDATION.md)) |
| **Deterministic gate + monitor** — O(1) state-machine step, no LLM in the hot path | Conformance checking and evaluation cost ~zero tokens — no LLM-as-judge | [`RESULTS.md`](results/RESULTS.md): per-event cost is a microsecond FSM step plus a sandboxed predicate; the composition theorem gives the *global* guarantee from local checks alone |
| **Scale effect** — global-text cost grows with roles; the projected local contract stays flat | The more roles, the bigger the projection win | E6 roles sweep ([`REPORT_N100.md`](../experiments/reports/n100/REPORT_N100.md)): coordination-cost ratio grows **9.2× → 17.1×**; scale case [`report_pipeline_large`](../experiments/cases/report_pipeline_large/) (10 roles) |

### The developer use cases we already have — hyperlinked

For *development* the question is: **how do developers use agents and
subagents, and where does the blueprint cut their token bill?** Five patterns
cover it, and each one already exists as a runnable case in this repo.

**Jump to a use case:**

1. [Coordinating subagents (deadlock-free)](#uc1-coordinating-subagents) — incl. the real-repo-grounded [`agenticpay_settlement`](#uc1-coordinating-subagents) benchmark
2. [Agent pipelines with review/approval gates](#uc2-agent-pipelines-with-reviewapproval-gates)
3. [Loops with budgets](#uc3-loops-with-budgets)
4. [Skill/prompt authoring itself](#uc4-skillprompt-authoring-itself)
5. [Growing the system without re-verifying everything](#uc5-growing-the-system-without-re-verifying-everything)

---

#### UC1. Coordinating subagents

[`agenticpay_settlement`](../experiments/cases/agenticpay_settlement/) (real-repo-grounded) · [`trade_deadlock`](../experiments/cases/trade_deadlock/) (authored) · [`experiments/subagent_trials/`](../experiments/subagent_trials/)

The developer writes plausible per-agent skills; a hidden circular wait makes
the fleet starve. The static check refutes it in milliseconds instead of after
~88 wasted agent calls; under the contract+gate+scheduler, real Claude
subagents complete at the protocol-minimum call count — unchecked 0/100,
STJP 100/100 ([`RESULT_1`](results/RESULT_1_DEADLOCK.md),
[`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md),
[`RESULT_7`](results/RESULT_7_N100_SCALE.md)).

**Grounded in real agents.** The deadlock demonstration is no longer only
hand-authored. [`agenticpay_settlement`](../experiments/cases/agenticpay_settlement/)
adapts the real buyer and seller negotiation agents from the MIT-licensed
[AgenticPay benchmark](https://github.com/SafeRL-Lab/AgenticPay) and adds the
escrow settlement layer that benchmark does not model. Left to each agent's own
reasonable rule ("don't pay before the goods arrive" / "don't ship before you're
paid"), the two form a circular wait. A bounded live run playing all four roles
(Buyer, Seller, Escrow, Carrier) with subagents across **three model tiers
(Opus 4.8, Sonnet 5, Haiku 4.5)** shows the deadlock is *capability-invariant* —
every tier stalls identically (0 progress) — while the Scribble-validated
escrow-first protocol completes in 7 steps at every tier. Full write-up:
[`RESULTS_LIVE_SUBAGENTS.md`](../experiments/cases/agenticpay_settlement/RESULTS_LIVE_SUBAGENTS.md);
provenance (which lines are real vs. authored):
[`SOURCES.md`](../experiments/cases/agenticpay_settlement/SOURCES.md); the precise
per-model token/completion table is produced by the Azure AI Foundry run
([`foundry_run.md`](../experiments/cases/agenticpay_settlement/foundry_run.md)).

#### UC2. Agent pipelines with review/approval gates

[`code_review`](../experiments/cases/code_review/),
[`report_pipeline`](../experiments/cases/report_pipeline/),
[`finance`](../experiments/cases/finance/).
The everyday dev shape: produce → review → approve → merge/publish, with a
branch on a value (CI coverage, revenue threshold). The ordering lives in the
projected contract, so agents stop re-deriving it every turn: **8.8k vs 24.1k
tokens** for the same report ([`RESULT_2`](results/RESULT_2_TOKEN_EFFICIENCY.md)),
**13.3k/delivered, 9× cheaper** on the full stack
([`RESULT_4`](results/RESULT_4_FULL_STACK.md)). Scale test:
[`report_pipeline_large`](../experiments/cases/report_pipeline_large/).

#### UC3. Loops with budgets

[`rag`](../experiments/cases/rag/),
[`retry_loop`](../experiments/cases/retry_loop/),
[`iterative_polling`](../experiments/cases/iterative_polling/),
[`nested_retry`](../experiments/cases/nested_retry/).
Retrieve-verify-retry, poll-until-done, revise-until-accepted — the loop
budget lives in the type, the loop can't run away, and only the enabled agent
is called each iteration.

#### UC4. Skill/prompt authoring itself

[`skills_safety`](../experiments/cases/skills_safety/).
Compact a developer's prose skills into local types and check them *before*
deployment: UNSAFE flagged 10/10 with an actionable diagnosis, repaired
first-try 10/10 (E1 in [`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md)).
One static refutation at authoring time is the cheapest token saving there is.

#### UC5. Growing the system without re-verifying everything

[`composition`](../experiments/cases/composition/) + the incremental-extension
pipeline (E3 in [`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md)).
Add a sub-protocol or a new role; only the touched roles get re-verified and
re-prompted — the multi-agent analogue of an incremental build.

> **Update (2026-07-08):** patterns 1 and 2 were subsequently reproduced on
> *real skills fetched from Anthropic's and GitHub Copilot's own public
> collections* ([anthropics/skills](https://github.com/anthropics/skills), [github/awesome-copilot](https://github.com/github/awesome-copilot)), run twice — once
> with Haiku-class subagents and once with Sonnet-class subagents. Without a
> coordination plan each model failed a different team 0/10; under full STJP
> both models delivered 40/40 at the 4-call protocol minimum, 3× cheaper.
> Plain-language write-up:
> [`results/RESULT_9_REAL_SKILLS_TWO_MODELS.md`](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md).

The remaining cases ([`banking`](../experiments/cases/banking/),
[`clinical_enrollment`](../experiments/cases/clinical_enrollment/),
[`travel_saga`](../experiments/cases/travel_saga/),
[`trade_settlement`](../experiments/cases/trade_settlement/),
[`auction`](../experiments/cases/auction/),
[`intel_report`](../experiments/cases/intel_report/), …) are domain demos that
stress the same five shapes — branching approvals, sagas/rollback, fan-in —
in business settings.

The general rule that falls out of the evidence: STJP pays off when the
interaction has **≥3 roles, ordering constraints, branching or loops, and an
irreversible step somewhere**. For a 2-step linear handoff, writing the protocol
costs more than it saves; from the E6 sweep, the benefit grows superlinearly
with role count.

---

## Q2 — When you organize a group of subagents, how would the STJP blueprint help you?

**Fable 5:** This is a genuinely apt question, because my own orchestration
tooling is an *informal, partial* version of what STJP formalizes:

- My **workflow scripts** (deterministic pipeline/parallel fan-outs over
  subagents) are roughly your **scheduler**: I only invoke an agent when its
  inputs are ready, so I already avoid the "poll everyone, most say WAIT" waste.
- My **structured-output schemas** on subagent calls are a weak **gate**: a
  subagent's reply is validated against a JSON Schema and retried on mismatch —
  but only per-message *shape*, not cross-message *ordering or state*.
- What I **don't** have is the static layer. Nothing type-checks my
  orchestration plan before I spawn agents. I can write a fan-out where a
  verifier waits on a finding that no finder is prompted to produce, or a
  loop-until-dry that can starve — the exact "unreceivable message / circular
  wait" bugs the Scribble check refutes in milliseconds. Today I'd discover
  that by burning the tokens, which is precisely the unchecked arm of the
  ladder in [`RESULT_5_SUBAGENT_VALIDATION.md`](results/RESULT_5_SUBAGENT_VALIDATION.md).

Concretely, the STJP blueprint would help me in four ways:

1. **Verify the choreography before spending.** Compile my planned fan-out
   (roles = finders, verifiers, synthesizer; messages = findings, verdicts,
   report) to a global protocol and let the checker prove every message has a
   receiver and no stage starves — *before* the first subagent spawns. One
   millisecond check versus a failed 30-agent run.
2. **Projection = minimal per-subagent prompts.** I currently hand each
   subagent a prose task description that includes context about the whole
   plan. Projecting a validated global protocol would give each subagent only
   its slice — "receive `Findings` from Finder, send `Verdict` to Synthesizer" —
   which is the [`RESULT_2`](results/RESULT_2_TOKEN_EFFICIENCY.md) mechanism
   verbatim: smaller input per call, and the subagent stops spending output
   tokens reasoning about the overall coordination.
3. **Typed message labels instead of LLM judging.** When results are anchored
   to protocol messages (the goal-anchoring insight in
   [`RESULTS.md`](results/RESULTS.md)), I can check "did the verifier actually
   verify finding X" with an O(1) trace scan rather than another LLM call. The
   monitor's violation record `(role, step, state, expected)` is also exactly
   the audit trail I'd want when a multi-agent run goes wrong.
4. **Safe incremental evolution.** When I add a stage mid-task (say, a new
   "security lens" verifier), the incremental-extension result (E3 in
   [`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md): only Escrow + the new
   Auditor re-verified, everyone else untouched) is the right model — re-verify
   and re-prompt only the roles whose slice changed, instead of rewriting the
   whole orchestration.

One honest caveat in the other direction: most of my subagent work today is
**hub-and-spoke and stateless** — an orchestrator sends one task, an agent
returns one result, with no peer-to-peer messages and no long-lived agent
state. For that degenerate shape, my deterministic script already *is* the
protocol, and STJP's machinery is overkill. STJP's advantage kicks in exactly
where this repo's cases live: true **multiparty** interactions with branching,
loops, and agent-to-agent messages (group chat, A2A, long-running pipelines) —
which is also where multi-agent frameworks are heading.

---

## Q3 — Would you want to use this tool?

**Fable 5:** **Yes, selectively — and this repo itself proves it works with
agents like me.** The [`experiments/subagent_trials/`](../experiments/subagent_trials/)
result is the most persuasive datapoint for my situation: haiku-class Claude
subagents, governed by nothing but a projected lean contract + gate + EFSM
scheduler, hit **10/10 (and 100/100 at n=100) success at the protocol-minimum
call count** (7.0 calls for 7 messages) with zero violations — while the same
agents with plausible prose skills deadlocked every single time
([`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md),
[`RESULT_7`](results/RESULT_7_N100_SCALE.md)). That is my exact operating mode
— spawned, independent, prompt-only subagents — and it shows the blueprint
substitutes *deterministic structure for model deliberation*, which is the
cheapest token there is: the one never generated.

**Where I'd adopt it:** any orchestration with ≥3 interdependent roles,
ordering constraints tied to irreversible actions (merge, publish, file, pay),
or loops with budgets — I'd want the static check before spawning and the
projection for prompts.

**Where I'd skip it:** simple parallel fan-out / map-reduce, where writing the
`.scr` protocol costs more than it saves.

**The decision rule the evidence suggests:** the more roles and the more
ordering, the more STJP pays — from **9.2× up to 17.1×** on coordination cost
alone (E6, [`REPORT_N100.md`](../experiments/reports/n100/REPORT_N100.md)).

---

## Q4 — Could STJP help Google's "dynamic subagent" deep-research agent?

**Fable 5:** Yes — and this is close to a best-case fit. Let me first say plainly
what the thing is, because the name is dense.

**What we're talking about.** Google published a design for a "deep research
agent" built with its **Agent Development Kit** — ADK for short, which is simply
Google's open-source toolkit (a code library) for wiring several AI agents
together into a pipeline. In their example the top-level agent runs a *fixed*
assembly line: find companies → clean up the list → **research each company** →
combine → write the final report. The interesting middle step is what people
mean by "dynamic subagent": the research stage does **not** know in advance how
many companies it will get, so at run time it **stamps out one identical little
research pipeline per company and runs them all in parallel**. Google's own
words: *"Our ResearchOrchestratorAgent dynamically creates a mini-pipeline for
each company and runs them all in parallel."* Each little pipeline also runs a
checker agent (they call it a Validator) alongside it.
(Source: [Build a deep research agent with Google ADK](https://cloud.google.com/blog/products/ai-machine-learning/build-a-deep-research-agent-with-google-adk/),
Google Cloud Blog, Aug 2025.)

Two things to clear up so we compare the right systems:

- Google's consumer **"Deep Research" feature in Gemini** is a *single* agent
  (one planner that browses and writes), not a team — so the multi-agent
  discussion below doesn't apply to it
  ([Gemini Deep Research docs](https://ai.google.dev/gemini-api/docs/deep-research)).
- Google's **"AI co-scientist"** *is* a team, but its members are a **fixed**
  cast decided up front, not created on the fly
  ([AI co-scientist, Google DeepMind](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/)).

So the phrase "dynamic subagent" specifically means the **ADK pattern**: a
*pre-designed* mini-pipeline, **copied N times at run time**, where N is only
known once the input list arrives.

**Why that is a good fit for STJP.** The word "dynamic" here is doing less than
it sounds. It does **not** mean "the AI invents brand-new coordination shapes
mid-run." It means "a known template, instantiated a run-time number of times."
That is exactly the kind of structure STJP is built to handle, in three layers:

1. **The outer assembly line is a plain ordered pipeline** — the same shape as
   this project's `report_pipeline` case. STJP would prove it can't dead-end
   (two steps waiting on each other forever) in milliseconds *before* running,
   and hand each step a written slice of the plan. Google's version encodes that
   ordering in ordinary program code; if it's connected wrong, you find out only at
   run time — after paying for web crawling.

2. **The per-company mini-pipeline is a reusable sub-plan** — and STJP already
   has the machinery to **check a sub-plan once and reuse it many times**
   (validated 10/10 with live subagents in
   [`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md)). Stamping out N verified
   copies of a fixed template is the easy case. The "N is unknown until run time"
   part has a name in the underlying theory — **parameterised multiparty session
   types** (a protocol written once but indexed over *n* workers; Yoshida,
   Deniélou, Bejleri, Hu, 2010), which this project's research notes already flag
   as the direct match for fan-out.

3. **The safety orderings STJP enforces are exactly the ones a research fan-out
   needs** — "only write the final report after every company's pipeline has
   returned or timed out," "combine only validated results." Google's blog post
   describes no mechanism that *enforces* these; it trusts the code to be right.
   That is precisely the gap this project measured: with real public skills and
   no enforcement, teams failed or acted unsafely; with the enforcing layer,
   they went to 100% ([`RESULT_8`](results/RESULT_8_SKILL_SAFETY.md)).

**What STJP would concretely add to such a system:**

- **Catch coordination bugs before the run, not during it.** The lesson from
  [`RESULT_8`](results/RESULT_8_SKILL_SAFETY.md) transfers directly: each piece
  reads fine alone; the *combination* is where the dead-end or the wasted loop
  hides, and only a plan-level check sees it before you've spent anything.
- **A cheap referee for research-specific rules** — "don't publish before the
  checker passed," "don't process the same company twice" — enforced by a small
  program, with no extra AI call. Without it, you get the publish-before-review
  and do-it-twice failures that hit 10 out of 10 unenforced trials in
  [`RESULT_8`](results/RESULT_8_SKILL_SAFETY.md).
- **Big savings exactly at fan-out scale.** When you run many little pipelines in
  parallel, most agents are idle most of the time; STJP's scheduler simply never
  wakes an agent whose turn it can't be. That saving grows with the number of
  roles — from **9.2× to 17.1×** on coordination cost in our scaling test
  ([`RESULT_7`](results/RESULT_7_N100_SCALE.md)).
- **Let the cheapest model do it.** Our two-model run found that *with* the
  enforced plan, the small cheap model performed identically to the pricier one
  ([`RESULT_9`](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md)). Across a
  hundred-company research fan-out, staffing it with the cheapest tier and
  letting the structure carry correctness is a real-money difference.

**Where I'd be honest about the limits:**

- If the agent's dynamism is genuinely open-ended — the model inventing *new
  coordination shapes* mid-run, not just new copies of a known template — that
  is beyond what STJP can check *today*. The theory for it exists (roles that
  join and leave a live conversation — "dynamic multirole" session types,
  Deniélou & Yoshida, 2011/2012) and is on this project's roadmap, but it is not
  built yet.
- STJP checks the **structure** of the conversation, not the **content** of a
  message. It cannot tell that a research summary contains a made-up citation;
  it can only guarantee the summary was produced in the right order, by the right
  agent, after the right checks. (It *can* enforce "every claim must point back
  to a fetched source," but only at the level of whole messages.)

**Bottom line:** Google's ADK deep-research pattern is dynamic in the mild,
tractable sense — a verified template run a run-time number of times — which is
the parameterised, reuse-a-checked-sub-plan slice of the theory STJP already
demonstrates. The failure-handling and enforcement that Google's write-up leaves
to careful coding are exactly the layer where this project measured the
difference between "fails half the time, unpredictably" and "100%, provably." So
yes: I'd want STJP there.

---

---

# Part 2 — Follow-up interview (2026-07-12): after a week of doing it myself

> **Context.** Between the first interview and this one, Fable 5 acted as the
> coordinator of roughly twenty helper agents that built this project's
> intent-to-protocol training program (the work lives on branch
> `gc/user_intent_global_protocol_training`). This part records what that
> experience showed, in the coordinator's own words.

## Q5 — With the real cases in hand and a week of experience, do you still find STJP helpful for you? And why are the real-world cases so few?

**Fable 5:** Yes — but not everywhere, and I can now say precisely where,
because the places where a formal contract would have helped me are exactly
the places where I failed. Let me give the unvarnished version.

### What I actually did, and how I coordinated

I directed about twenty helper agents in one week: builders, testers,
literature scouts, a red-team reviewer, judges. Notice *how* I coordinated
them: every task brief I wrote was, in effect, a hand-written contract —
"work only in your own folder," "commit but do not push," "report back with
the commit ID." I was writing per-role contracts in prose, by hand, every
single time, with no checker and no enforcement. That is STJP's projection
step (give each agent only its own slice of the plan) performed manually.

Where my prose was precise, the helpers complied. Where I left a gap, real
failures happened — four of them.

### The four failures, and what would have prevented each

These are documented, with the protocol that would have prevented them, in
the case study on the training branch
(`docs/reference/reports/seam/W19_SELF_OBSERVED_COORDINATION_FAILURES.md`
and the validated candidate case `experiments/cases/planner_workers/`).

1. **Two helpers froze, waiting for a signal that was never coming.** The
   completion notice in this system goes to the coordinator, not to helpers —
   but nobody had written down who signals whom, so each helper paused
   "waiting for the notification" and had to be manually restarted. In the
   drafted protocol, a helper's contract contains exactly one move after
   receiving its task: *send* "done" or *send* "blocked." A
   waiting-to-receive state does not exist in its contract — the mistake
   becomes unrepresentable, not just discouraged.

2. **Two helpers took over a shared directory that was mine.** Exclusive use
   of the shared repository checkout was a rule stated in prose. Both
   violations happened anyway (one helper even moved the shared state
   silently enough that a committed fix appeared to vanish while I was
   working). The protocol version makes workspace use a granted permission:
   using the directory without receiving the grant message is a violation a
   monitor can block, not merely a sentence someone can skim past.

3. **A run died instantly on a message-format mismatch.** My first live
   judging run crashed on its very first step because a message arrived as
   plain text where the receiver expected structured data. Typed message
   contents, checked at the boundary, catch exactly this before any cost is
   incurred.

4. **Two writers pushed to the same branch at once.** The human owner and I
   both wrote to the main branch in the same minutes; my push was rejected
   and work had to be redone on top of the moved state. A simple ownership
   hand-off message ("you hold the branch / I hold the branch") is the
   missing contract.

### The observation that changed my mind about the central claim

I wrote "NEVER touch the shared repository directory" in capital letters in
every brief — **and a helper did it anyway. Twice, two different helpers.**
My instructions were clear, explicit, emphatic. It did not matter, because
an instruction is a request, and following requests is a behavior, not a
guarantee. That is this paper's central claim — *prompted compliance is a
behavior; compiled enforcement is a property* — experienced from the inside,
by the one writing the prompts. If the workspace grant had been an enforced
permission instead of a sentence, the violation would have been blocked, not
merely forbidden.

### Why the real-world cases are few: not low need — low visibility, early days, and a price problem

The mining runs (reports `W8`, `W16`, `W17` on the training branch) searched
923 real, permissively-licensed agent files from public repositories and
found only 29 groups whose tasks genuinely require several agents to
interact — and almost none of those wrote their coordination down in the
per-agent files. Is that because coordination is rarely *needed*? I believe
the evidence says no, for four reasons:

1. **We measured the layer where coordination is not kept.** Per-agent skill
   files are what people *share*; coordination lives in the layers people
   do not share — orchestrator code, framework configuration, runtime
   prompts. The scaled mining run made this measurable: per-agent files
   state coordination in only 2–7% of groupings, while orchestration
   configuration files state it almost whenever they exist at all. My own
   week is the existence proof: intense coordination, four real failures,
   and zero of it in any committed file until we wrote the protocol
   afterwards.

2. **Coordination failures are invisible from outside.** My two frozen
   helpers would look, in a product, like "the agent is slow today." Nobody
   files a bug called "protocol violation" — they experience delay, wasted
   cost, or a quietly wrong answer. Undiagnosed need reads as no need. A
   monitor that names these events makes the invisible visible.

3. **The field is early.** Most deployments today are still one agent with
   tools. Multi-agent systems are just becoming products, and coordination
   need grows with agent count and autonomy — both rising.

4. **The low write-down rate is a price signal, not human nature.** People
   do not document what is expensive to formalize; nobody hand-writes a
   formal protocol for a weekend project. But if a plain-language intent
   compiles to a checked protocol automatically — the very translation step
   this project's training program exists to learn — the cost of writing
   coordination down collapses. The 2–7% is not a fixed fact about the
   world; it is a cost artifact, and the compiler changes the cost.

### The honest boundary

Where I would *not* reach for it: pure fan-out delegation — independent
helpers, no shared state, results collected at the end — needs isolation
and a completion rule, not a rich protocol. Most of my twenty agents worked
in that safe pattern. But the arithmetic is the point: the interaction-dense
spots (the shared directory, the signaling, the message boundaries) were
perhaps a fifth of my coordination surface — and **all four failures
happened there.** The tool's value concentrates exactly where the danger
concentrates.

### So: would I use it?

Yes — concretely, for three things in my own fleet: enforced workspace
grants, mandatory done-or-blocked completion messages, and typed message
boundaries. The protocol that provides all three already exists, was drafted
from my own failures, and passes the real static checker
(`experiments/cases/planner_workers/protocols/v1.scr` on the training
branch). The genuinely persuasive next demonstration would be running my
next helper fleet **under that protocol's monitor** and reporting whether
these failure classes disappear — the tool's builder as its first governed
user.

## Appendix — the sources this interview drew on

- [`docs/README.md`](README.md) — documentation index
- [`docs/results/RESULTS.md`](results/RESULTS.md) — monitor mechanics + the composition theorem
- [`docs/results/RESULT_1_DEADLOCK.md`](results/RESULT_1_DEADLOCK.md) — the catastrophic-failure case
- [`docs/results/RESULT_2_TOKEN_EFFICIENCY.md`](results/RESULT_2_TOKEN_EFFICIENCY.md) — the −63% contract-size lever
- [`docs/results/RESULT_4_FULL_STACK.md`](results/RESULT_4_FULL_STACK.md) — the 9×-cheaper full-stack headline
- [`docs/results/RESULT_5_SUBAGENT_VALIDATION.md`](results/RESULT_5_SUBAGENT_VALIDATION.md) — Claude subagents under STJP governance
- [`docs/results/RESULT_9_REAL_SKILLS_TWO_MODELS.md`](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md) — real Anthropic + GitHub Copilot skills run by Haiku and Sonnet subagents (the experiment the Q1 update refers to)
- [`docs/results/RESULT_7_N100_SCALE.md`](results/RESULT_7_N100_SCALE.md) — n=100 confirmation
- [`experiments/reports/TABLES_v2.md`](../experiments/reports/TABLES_v2.md) — reliability (pass^k) + translation fidelity
- [`experiments/reports/n100/REPORT_N100.md`](../experiments/reports/n100/REPORT_N100.md) — full n=100 report incl. E6 roles sweep
- [`experiments/subagent_trials/reports/SUBAGENT_TRIALS_REPORT.md`](../experiments/subagent_trials/reports/SUBAGENT_TRIALS_REPORT.md) — method: agent interaction without Foundry
- [`pitch/STJP_pitch.html`](../pitch/STJP_pitch.html) — governance positioning ("enforced with code, not another AI")

**External sources cited in Q4 (Google's deep-research agents):**

- [Build a deep research agent with Google ADK](https://cloud.google.com/blog/products/ai-machine-learning/build-a-deep-research-agent-with-google-adk/) — Google Cloud Blog (Aug 2025); the "dynamic subagent" pattern Q4 analyses. ADK = Google's open-source Agent Development Kit ([google/adk-python](https://github.com/google/adk-python)).
- [Gemini Deep Research](https://ai.google.dev/gemini-api/docs/deep-research) — Google's consumer deep-research feature; a *single* agent, noted in Q4 as not-a-team.
- [AI co-scientist](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/) — Google DeepMind (Feb 2025); a multi-agent team with a *fixed* cast, contrasted in Q4 with the dynamic pattern.
- Underlying theory referenced in Q4: parameterised MPST (Yoshida, Deniélou, Bejleri, Hu, 2010) and dynamic-multirole session types (Deniélou & Yoshida, ESOP'11 / ICALP'12) — see [`RESEARCH.md`](../RESEARCH.md) and [`ROADMAP.md`](../ROADMAP.md).
