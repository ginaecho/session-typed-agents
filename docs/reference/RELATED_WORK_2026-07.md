# Related-work sweep, July 2026 — what changed, and what the paper must answer

**Swept 2026-07-25.** This updates the last literature pass
([`reports/seam/scouts/R1_literature.md`](reports/seam/scouts/R1_literature.md),
2026-07-11), which looked only at the training program. This sweep covers the
whole paper: the compiler framing, the safety claims, the cost claims, and the
judge-free evaluation.

One term used throughout: an **arm** is one configuration being compared — like
the treatment and control groups of a medical trial. Two more, glossed once
here and used freely after: **projection** is the step that takes one whole-team
protocol and cuts it into one contract per role, so each agent is handed only
its own slice; the **seam** is the translation step where a plain-language
request becomes a Scribble-validated protocol.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [How this sweep was run, and how much to trust it](#how-this-sweep-was-run-and-how-much-to-trust-it)
- [The verdict in one paragraph](#the-verdict-in-one-paragraph)
- [Tier 1 — the six findings that change what the paper may claim](#tier-1--the-six-findings-that-change-what-the-paper-may-claim)
  - [1. TraceFix — our pipeline shape, peer-reviewed, three months earlier](#1-tracefix--our-pipeline-shape-peer-reviewed-three-months-earlier)
  - [2. llmcontract — session types for LLM agents already exist](#2-llmcontract--session-types-for-llm-agents-already-exist)
  - [3. Skill compilers exist, so "ships without a compiler" is now false](#3-skill-compilers-exist-so-ships-without-a-compiler-is-now-false)
  - [4. Someone already published the token-efficiency diagnosis](#4-someone-already-published-the-token-efficiency-diagnosis)
  - [5. MCP deleted its session layer, and a reviewer will notice](#5-mcp-deleted-its-session-layer-and-a-reviewer-will-notice)
  - [6. Judge-free evaluation is not novel any more — only its provenance is](#6-judge-free-evaluation-is-not-novel-any-more--only-its-provenance-is)
- [Tier 2 — evidence we should be citing and are not](#tier-2--evidence-we-should-be-citing-and-are-not)
  - [Third-party numbers for the failures we claim to prevent](#third-party-numbers-for-the-failures-we-claim-to-prevent)
  - [The declarative-protocol-for-agents research line](#the-declarative-protocol-for-agents-research-line)
  - [Session-type theory we cite thinly](#session-type-theory-we-cite-thinly)
- [What is still genuinely unoccupied](#what-is-still-genuinely-unoccupied)
- [ZipperGen, reconsidered — threat, no; useful, yes](#zippergen-reconsidered--threat-no-useful-yes)
- [Where STJP would have helped this very sweep](#where-stjp-would-have-helped-this-very-sweep)
- [The edit list for the paper](#the-edit-list-for-the-paper)
- [Sources](#sources)
<!-- MENU:END -->

## How this sweep was run, and how much to trust it

Eight search agents in two rounds: six broad sweeps with deliberately disjoint
search assignments (formal coordination; agent artifacts and standards; failure modes and
token cost; runtime enforcement; plain-language-to-specification translation and
judge-free evaluation; industry and standards landscape), then two verification
agents aimed only at the items that came back contested.

**A caveat that has to come first, because it bounds every number below.**
`arxiv.org`, `dl.acm.org`, and every paper mirror the agents tried are blocked
by this session's outbound network policy — the gateway answers `403` to the
connection attempt. Nothing was routed around it. So no abstract in this
document was read by fetching the paper directly. Abstracts came from web search,
which returns text extracted from the target page, so the quoted content is a
second-hand rendering of the real page rather than an agent's guess from a title
— but author lists, version dates, and any number that will appear in the
manuscript still need one confirming read from an unblocked network.

Three things *were* verified by direct fetch, because GitHub is reachable: the
`llmcontract` repositories, the `agenticraft-foundation` repository, and their
reported measurements. Those are marked **verified by fetch** below. Items
confirmed by a targeted search that returned the paper's own abstract text are
marked **verified by search**. Anything still resting on a title is marked
**unverified** and must not enter `main.tex` in that state.

Where the agents disagreed, that is reported rather than smoothed over. The
clearest case: one agent ranked TraceFix the single most dangerous paper in the
sweep; another marked the same paper title-only and unverified. It was checked
by hand afterwards, and the first agent was right.

**One finding about the sweep itself matters more than any paper in it.** The
verification round established that a first-round agent reported an arXiv
identifier — `2605.23951`, attached to a title *"Methods for Formal Verification
of Agent Skills"* — that **does not resolve to any paper**. Direct identifier
queries return unrelated work. The real paper behind it is probably
arXiv:2605.11770, *Behavioral Integrity Verification for AI Agent Skills*, which
remains unexamined. Nothing else in that agent's report failed to resolve, and
the eight identifiers checked against their titles in round two all matched. But
one fabricated identifier in a literature sweep is one too many: **treat every
identifier in this document as unconfirmed until it has been resolved against
the live listing**, and never paste one into `main.tex` on the strength of this
document alone. That is also a small, sharp illustration of the paper's own
thesis — an unverified claim from a language model looks exactly like a verified
one until something mechanical checks it.

## The verdict in one paragraph

The niche the paper occupies — multiparty session types applied to agent
markdown — is still unoccupied, and thirteen independent negative searches
support that. But the *pipeline shape* is no longer unclaimed, and the framing
sentences are now falsifiable in three places. A peer-reviewed paper
(TraceFix, ACM CAIS 2026) already does intent → formal protocol → static check →
per-agent prompts → runtime monitor, with a model checker where we have a type
checker — and reading its source shows it also has mechanically generated
per-role state-machine monitors policing free-running agents, so four of our
claims to novelty do not survive contact with it. A session-types runtime monitor for LLM agents already exists as
working code by a session-types researcher (`llmcontract`, April 2026). Skill
compilers with typed intermediate representations already exist, so "these
artifacts ship without a compiler" is wrong as written. And the token-efficiency
diagnosis we treat as a discovery — idle agents re-reading context they do not
act on — was published in April 2026 with numbers. None of this sinks the paper.
All of it changes what the paper is allowed to say, and the fixes make the
claims narrower, sharper, and true.

## Tier 1 — the six findings that change what the paper may claim

### 1. TraceFix — our pipeline shape, peer-reviewed, three months earlier

**TraceFix: Repairing Agent Coordination Protocols with TLA+ Counterexamples.**
arXiv:2605.07935, May 2026. Published at the ACM Conference on AI and Agentic
Systems 2026, DOI `10.1145/3786335.3813159`. Code at
`github.com/Sensing-And-Reasoning/TraceFix`. **Verified by search**, including
the venue and DOI.

An agent turns a task description into a protocol topology, generates PlusCal
(the modelling language of the TLA+ toolchain), and repairs the protocol from
model-checker counterexamples until it verifies. Then — and this is the part
that matters to us — "verified process bodies are compiled into per-agent
system prompts and executed under a runtime monitor that rejects
out-of-topology coordination operations." Forty-eight tasks over sixteen
scenario families; every task eventually verifies; 62.5% verify on the first
attempt; never more than four repair rounds.

That is our architecture with a model checker substituted for a type checker,
at a peer-reviewed venue, with public code. It is the paper a reviewer is most
likely to have read, and its related-work section discusses multiparty session
types explicitly — its stated difference from us is *authoring* (LLM-synthesised
rather than hand-written protocols) plus the *repair* loop — so we cannot claim
the connection is unnoticed.

**A correction, because the first pass of this sweep got it wrong.** The
abstract says "topology monitor," and the obvious differentiation to reach for
is that TraceFix only polices who may talk to whom while we police the typed
order. A verification agent cloned the repository and read the architecture
document and source. **That differentiation is false, and writing it would be
the single most damaging error we could put in the paper.** TraceFix has two
stacked checkers: a topology whitelist, and — in
`runtime/monitoring/state_tracker.py` — a **per-agent finite-state machine
extracted mechanically from the TLC-checked specification by a tree-sitter
parser**, enforcing ordering, compound actions, nondeterministic branch
candidates, and integer-counter guards. It blocks before any effect is applied
and hands the agent back its legal next actions. If a reviewer knows this
repository, that one sentence would discredit the section it sits in.

So the differentiation has to move, and here is where the repository says it can
safely stand:

- **Projection with a soundness relation.** This is the strongest axis, and it
  is stronger than expected. TraceFix's per-agent *monitors* are compiled
  deterministically, but its per-agent *prompts* are written by an LLM agent
  loop against an LLM-run checklist ("all states covered", "labels exact", "no
  phantom ops"), with sixteen hand-written anti-patterns the generator must
  avoid. The paper's phrase "compiled into per-agent system prompts" reads as
  deterministic compilation; it is not. Ours is projection from a global type.
  The anti-pattern list is the evidence for us: the LLM route needed sixteen
  guardrails.
- **A decidable, unbounded check.** TraceFix caps channel length with a
  `ChannelBound` constraint, and the architecture document says plainly that it
  exists to stop the state space exploding. "100% verified" means verified
  within a bound, re-earned per protocol. Scribble well-formedness is
  polynomial and holds for every instantiation.
- **Payload-dependent choice.** TraceFix forbids this by design: its
  "sole-mediation" rule says business content can never cause a coordination
  transition, channels carry a label only, and content rides an unverified side
  plane as an opaque reference. Its guards are over PlusCal loop counters, not
  message payloads. Genuine capability difference.
- **Goal reachability.** TraceFix checks **safety only** — no liveness, no
  fairness — and says so unusually candidly, noting that its "termination"
  property means no reachable deadlock rather than a proof that executions
  finish. This is uncontested territory, *provided* our reachability claim is
  really a reachability property and not deadlock-freedom under another name.
  They flag that exact conflation against themselves; we will be held to the
  same standard.
- **Cost.** Three targeted searches found no token or cost numbers in the
  paper. Our "safest and cheapest" framing stands today — but their repository
  ships a `cost.py` with a per-model price table and writes `cost_usd` into
  every result record, so they could produce a cost table in an afternoon. Land
  the claim on measured head-to-head numbers, not on an assumed gap.

**And here is what we must stop claiming.** Static validation before any agent
runs is not a differentiator — same posture, earlier, peer-reviewed. Statically
guaranteed deadlock-freedom is not one either; they also get mutual exclusion,
no orphan locks, and channel drainage. **Generated per-role FSM monitors are
not novel** — `state_tracker.py` is exactly that, mechanically derived, and it
won a best-paper award. And enforcement on free-running untrusted agents at the
message boundary is not novel: their monitored runtime is precisely that, and it
is the *only* arm they ship (the trusted-mediator variant was retired). Our
gradual-session-types and monitorability framing is theory they lack, but the
mechanism is the same, and we must not imply they execute coordination in
trusted code.

Two places they are simply stronger, which the paper should concede rather than
have pointed out. They close the loop from counterexample to repair, with
repair-iteration statistics, and they feed the error classes back into the
generated prompts; if our checker just fails and hands the message back to the
drafting model, that is their clearest advantage, and adding repair-iteration
counts to our own pipeline is cheap. And their evaluation is broader: 48 tasks
over 16 families in three difficulty tiers, a 3,456-run runtime comparison, a
270-run paired ablation, a model-capability degradation curve, and fault
injection at 0/30/60/90%.

*[Status note, added in a follow-up session after checking the codebase: the
"if our checker just fails" conditional does not hold.
`experiments/seam_bench/t0/repair_loop.py` already implements the
instrumented loop — draft → validate through the real Scribble CLI → on
reject, repair on the validator's own counterexample text → revalidate,
capped at 3 rounds — with one record per attempt, a `repair_rounds` metric,
and first-attempt validity (the direct analogue of TraceFix's 62.5%
statistic). Verified in a fresh container: its test suite passes 10/10
against a from-source Scribble build, and `validity.py` raises rather than
fall back to any weaker checker. The D3 mutation-based repair tuples go a
step further than TraceFix's sixteen hand-written anti-patterns: they are a
*training corpus* for the repairer, classed per mutation operator. What
TraceFix has and this program does not yet have is numbers from a real
drafting model — T0 has only run with mock/replay drafters, so the
comparison cell stays pending until one metered run (ICLR_READINESS prices
it at $5–20, needing only an LLM key). The concession to keep is
evaluation breadth; the loop itself is built.]*

One line in their README is aimed squarely at our design: centralized
orchestration "avoids concurrency — but also limits scalability," and they
target independent concurrent agents with shared resources. **An EFSM scheduler
that drives turn-taking is a centralized serializer.** We should expect exactly
that criticism and have an answer ready.

Where we are equally exposed, and should say so: both systems leak off-protocol
side channels. Their agents share a filesystem and have shell access, and their
content plane bypasses the monitor by design. Unless we sandbox the domain
plane, we must not claim to close a hole they leave open.

### 2. llmcontract — session types for LLM agents already exist

**`llmcontract`**, Christian Bartolo Burlò. `github.com/chrisbartoloburlo/llmcontract`,
created 2026-04-23, actively pushed through 2026-07-03. MIT licensed.
**Verified by fetch.**

A runtime monitor for LLM agent interaction protocols built on session-type
theory, grounded in the author's own ECOOP 2021 work on when session types can
be monitored at all. Protocols are written in a session-type-flavoured
notation — `!SearchFlights.?FlightResults.!BookFlight.?BookingConfirmation.end`
— with choice, recursion, and data-dependent guards. It compiles that string
through a parser and an automaton, then checks a live event stream, and
`peek_send`/`peek_receive` let it block an illegal tool call rather than merely
record it. It integrates with LangChain, Claude Managed Agents, and Langfuse.

This is the closest existing work to ours in both theory family and application
domain, it appeared in the same quarter, and its author is exactly the kind of
person who will be asked to review this paper. Three facts keep our
contribution intact, and all three were confirmed from the repository rather
than assumed: it is **two-party**, agent against environment, so there is no
global protocol and no notion of several roles being mutually consistent; there
is **no projection**, because protocols are written directly for the one party
being watched; and it does **no static verification** — the README says so in
as many words, "runtime monitoring only … no static pre-execution verification
of protocols."

So our defensible claim narrows to four load-bearing words: **multiparty,
static, projected, scheduling**. Every one of them now has to do real work in
the sentence.

The satellite repositories are, separately, the best third-party motivation
available to us, and they are ours for free:

- **`llmcontract-playwright-mcp`** (**verified by fetch**): encodes Playwright
  MCP's documented "take a snapshot before you interact" rule as a session
  type and replays 90 trajectories across three frontier models for \$7.97.
  Result: 8/90 (9%) violate snapshot-before-interact, and 26/90 (29%) act on
  stale references from an old snapshot — and the two failure rates move in
  *opposite* directions as the model gets stronger.
- **`llmcontract-tau2`** (**verified by fetch**): replays τ²-bench
  trajectories against the benchmark's own documented rule that the agent must
  get user confirmation before changing the database. Result: 0.6% of
  trajectories that **τ²-bench scored as passing** violate that rule — the
  agent acted first, or never asked. Filed upstream as
  `sierra-research/tau2-bench#298`.

That second finding is worth more to us than any number we generated
ourselves. An independent benchmark, an independent researcher, no stake in our
thesis: agents pass the evaluation while breaking the written rule. That is the
argument for enforcement rather than measurement, made by someone else.

A second, weaker instance: **`agenticraft-foundation`**
(`github.com/agenticraft/agenticraft-foundation`, **verified by fetch**) claims
CSP, multiparty session types with global-to-local projection, and deadlock
detection connected into a deployment gate. Its `verify()` runs five checks on an
application manifest, including per-workflow deadlock-freedom. But it verifies
an abstract manifest, generates no per-role prompts or skills, and is at
version 0.1.0 with 31 commits and one star. Cite it for completeness; the
maturity is a footnote, never the argument.

### 3. Skill compilers exist, so "ships without a compiler" is now false

Three 2026 papers compile agent skill markdown through a typed intermediate
representation. **Verified by search.**

- **SkCC** (arXiv:2605.03353): "introduces classical compiler design into agent
  skill development" via **SkIR**, "a strongly-typed intermediate
  representation that decouples skill semantics from framework-specific
  formatting," explicitly analogised to LLVM. Motivated by up to 40%
  performance variation across frameworks from formatting alone.
- **SkillSmith** (arXiv:2605.15215) compiles skill packages offline into
  "runtime boundary contracts" — contribution boundary, invocation interface,
  execution conditions, fallback obligations. Verified numbers: **−57.44%
  solve-stage tokens, −42.99% thinking iterations, −50.57% solve time (2.02×
  faster), −57.44% cost**. (A different paper at arXiv:2606.01314 shares the
  name — do not conflate them.)
- **Skill-as-Pseudocode** (arXiv:2605.27955) converts markdown skill libraries
  into typed pseudocode, extracting a typed contract per cluster of similar
  passages — trigger, input schema, output schema, and pre/post-conditions,
  analogised in the paper to what OpenAPI gives typed-routing agents — filtered
  through a four-check deterministic verifier.
- **SkillFortify** (arXiv:2603.00195, *Formal Analysis and Supply Chain
  Security for Agentic AI Skills*) goes further than the others: a **sound**
  static analysis with a stated no-false-negatives theorem — if it reports no
  capability violations, the skill provably does not exceed its declared
  capabilities — at 96.95% F1 and 100% precision over 540 skills.

The introduction currently says there is "no parser that rejects an incoherent
skill, no type checker that proves two skills cannot mutually block, no
compiler that guarantees the declared goal is reachable." The middle clause
survives. The first and third do not.

The honest and stronger reframing is that these compilers are **intra-role**.
Every one of them types a single artifact in isolation — a skill's interface, its
rendering into a framework's format, its pre- and post-conditions, or its
capability envelope. None of them types the interaction: which role may send
what, to whom, in what order. SkIR cannot express, let alone check, that the
planner waits for a result the worker will never send, and a set of individually
well-typed skills is exactly where deadlock is born. So the gap is not "no
compiler" — it is "no compiler for the part *between* the skills." That is a
narrower claim and a much harder one to knock down.

Two consequences follow, and both cost us something. We cannot claim to
introduce typed contracts over skill markdown, because Skill-as-Pseudocode
already has trigger, input, output, and pre/post-conditions. And we cannot
attribute token savings to projection without separating them from savings that
compilation alone already buys: SkillSmith reports −57.44% solve-stage tokens
with **no protocol content whatsoever**. If we report savings in that range
without naming SkillSmith as prior art, the result reads as a re-discovery of
progressive disclosure. Either state what our savings are *on top of* a
compiled-skill baseline, or say plainly that we do not separate the two.

The same correction applies at the shallow end of the market: there are
seventeen-plus skill and agent-markdown linters on GitHub created in the first
half of 2026, the largest being `agnix` at 365 stars with 437 rules
(**verified by fetch of repository metadata**). Every one of them stops at
frontmatter, token budgets, broken links, and leaked secrets. That is a good
line for the paper: 437 rules, and not one of them can tell you the
conversation deadlocks.

### 4. Someone already published the token-efficiency diagnosis

**Phase-Scheduled Multi-Agent Systems for Token-Efficient Coordination
(PSMAS).** arXiv:2604.17400, April 2026. **Verified by search**, by hand, twice.

Its diagnosis is ours, almost word for word: token waste comes from
"unstructured parallel execution, where all agents activate simultaneously
irrespective of input readiness" and "unrestricted context sharing, where every
agent receives the full accumulated context regardless of relevance." It
measures production five-agent pipelines at 42,000–71,000 tokens per
invocation, of which 29–38% is context consumed by agents that do not act on
it. Its fix schedules activation around a circular manifold and compresses idle
agents' context, reporting a 27.3% mean token reduction at a 2.1-point accuracy
cost.

We should stop presenting the diagnosis as a discovery and start presenting our
result as the **stronger form of a known effect**. PSMAS restricts context by
*learned scheduling plus lossy compression*, and pays accuracy for it. STJP
restricts context by *projection*, so a role never receives another role's
slice at all — there is nothing to compress and no accuracy tax. Their
measurement of how much context is wasted is excellent independent support for
our motivation.

Two related items in the same direction, both **verified by search**:
*In-Context Prompting Obsoletes Agent Orchestration for Procedural Tasks*
(arXiv:2604.27891) argues an orchestrator is pure overhead — 200 conversations
per condition, in-context scoring 4.53–5.00 against LangGraph's 4.17–4.84. The
rebuttal is clean and should be in the paper: their tasks are single-thread
procedures run by one model following a script, with no two principals, no
mutual waiting, and no authorization boundary — the failure classes we target
are definitionally absent, and their own finding that the *orchestrator* was
the failure source is an argument for a typed one, not for none. (Worth noting
without leaning on it: they score with an LLM judge.) And *Compiling Agentic
Workflows into LLM Weights* (arXiv:2605.22502) claims two orders of magnitude
cost improvement by compiling the workflow into weights — a louder cost claim
than ours, which buys cost by destroying the auditable protocol entirely.

### 5. MCP deleted its session layer, and a reviewer will notice

The Model Context Protocol revision dated **2026-07-28** removes the session
layer: the `initialize`/`initialized` handshake and the `Mcp-Session-Id` header
are gone, every request is self-contained, and state moves into
application-level handles the model passes between calls — "state visible to
the model rather than hidden in transport metadata." (**Verified by fetch**;
`blog.modelcontextprotocol.io` is reachable even though the spec site is not.)
We currently cite the 2025-11-25 spec.

A reviewer will ask the obvious question: you are proposing *session* types for
agent protocols, and the flagship agent protocol just deleted sessions — is the
abstraction obsolete? The answer is that it cuts the other way, and it is a
better motivating paragraph than the one we have. Session types are a static
discipline on the *interaction*; they are orthogonal to whether the *transport*
keeps state. Pushing sequencing out of the transport and into model-visible
handles makes correct ordering entirely the artifact author's problem, with no
protocol-level scaffolding at all. A hand-rolled continuation passed through a
tool handle is precisely the thing a session type describes and a checker can
reject.

### 6. Judge-free evaluation is not novel any more — only its provenance is

**GroundEval: A Deterministic Replacement for LLM-as-Judge in Stateful Agent
Evaluation.** arXiv:2606.22737, June 2026 (v2 July). **Verified by search.**

This is the finding that most directly hits our own contribution, and it hits
the second one, not the first. GroundEval scores an agent's final answer *and*
its recorded trajectory against what it calls "a machine-checkable contract over
state, access, time, and evidence" — its framing sentence is ours. It also
already published the motivating anecdote we would want to open with: two
frontier LLM judges scored a plausible answer at 0.85 and above, while the trace
showed the agent never retrieved the artifact the answer depended on; the
mechanical score was **0.000**.

So we must stop presenting judge-free mechanical evaluation as new. What
survives is narrower and specific: **where the contract comes from.**
GroundEval's contracts are drafted *post hoc* — an adapter runs the agent, an
observed run is turned into a candidate contract, the draft is machine-validated
for structural defects, and then **a human reviews and corrects it, per task**.
Ours would be projected *ex ante* from a single validated global protocol, with
no per-task authoring and no human in the loop. The one sentence to write is
that one: prior judge-free evaluators derive their per-task contracts from
observed runs with human review; ours are projections of one validated global
protocol, so adding a task adds no specification.

Note the honest weak point. GroundEval argues explicitly that its authoring
burden does *not* grow with agent complexity, because drafting is by
observation. So "we avoid hand-authoring" is not by itself a difference — only
"we avoid it *and* our contract existed before the agent ran" is.

The same narrowing applies to **AgentLTL** (arXiv:2607.02599): it defines
procedural compliance mechanically in first-order linear temporal logic, uses
one formalism for evaluation, runtime enforcement, and fine-tuning, and already
reports that violations concentrate in tool ordering and pairwise sequencing —
which is close to a headline finding of ours. It is single-agent and over one
agent's tool calls rather than between agents, and whether its specifications
are hand-authored per workflow could not be confirmed. If our gate admits or
refuses a message *before* it is emitted, that difference from trace-based
enforcement has to be named explicitly, or a reviewer reads the two mechanisms
as the same thing.

## Tier 2 — evidence we should be citing and are not

### Third-party numbers for the failures we claim to prevent

Every one of these replaces a self-reported number with someone else's. All
**verified by search** unless noted; each needs one confirming read before it
is quoted in the manuscript.

| Failure class we claim to prevent | Third-party evidence | Number |
|---|---|---|
| Deadlock | **DPBench**, arXiv:2602.13255 | Deadlock 25.0% (GPT-5.2) to 90.0% (Gemini 2.5 Flash) at five agents; its own conclusion is that "whether the same model coordinates or deadlocks is determined by the protocol, not by the model's capability" |
| Confidential payload to the wrong recipient | **AgentLeak**, arXiv:2602.11510 | Messages between agents leak at 68.8% against 27.2% for final outputs — output-only auditing misses 41.7% of violations |
| Roles cannot be told what they each need to know | **PerspectiveGap**, arXiv:2606.08878 | 27 commercial models; 14.9% average pass rate on assigning the right information to each role |
| Livelock / burning the budget | **IAL-Scan**, arXiv:2607.01641 | 6,549 agent repositories scanned; 68 confirmed infinite-loop failures across 47 projects at 91.9% precision |
| Failure is the expensive token class | arXiv:2606.01365 | Among failed runs that were warned, 58.1% of tokens were spent *after* the first warning |
| Coordination, not capability, is what breaks | arXiv:2605.03310 | Production multi-agent LLM systems fail at 41–87%, "mostly due to coordination defects rather than base-model capability" |
| Acting before authorization | arXiv:2512.20798 | Constraint violations 0.0–62.8% across 12 models, most at or above 25% |

DPBench deserves particular attention: it is a controlled dining-philosophers
testbed, its headline sentence is our thesis in someone else's words, and
running it as an arm would let us write "unenforced: 25–90% deadlock;
compiled: zero, by construction" using an existing external benchmark.

One finding is the sharpest framing available to us, and the verification round
pinned it down. **arXiv:2606.17182** formalises four ways multi-agent LLM
systems corrupt shared state — a stale result generated from data that has since
changed, a tool that has vanished, a cascade of decisions built on one bad read,
and tool effects landing out of order — proves a chain of consistency levels in
TLA+, and reports that *preventing* them costs tokens: **about +8% for snapshot
isolation and 1.6–2.3× for pessimistic locking**. Both numbers confirmed.

Two things must be said precisely about it. It is **runtime** concurrency
control — transactional isolation enforced by a runtime, with the runtime's
design verified offline — not a static analysis of anyone's workflow, so it does
not threaten our static deadlock claim, and implying that it does would
misrepresent a machine-checked paper. But it does mean the "safety that saves
tokens" line has to be stated against this specific baseline with these
specific numbers, because the paper explicitly pre-empts the
order-of-magnitude-penalty strawman. The honest sentence: verified runtime
concurrency control costs roughly +8% to 2.3× in tokens; our checks run
statically over a protocol and add no runtime coordination, so the token effect
is negative rather than positive. It also means we cannot claim the first
machine-checked treatment of multi-agent interference.

### The declarative-protocol-for-agents research line

An entire community arrived at "LLM agents driven by declarative protocols"
from the multi-agent-systems side, and we cite none of it. **Verified by
search**; Ahoy independently by hand.

- **Ahoy** (arXiv:2606.05390, Joshi, Singh, Chopra) builds LLM agents that
  "dynamically select and enact declarative protocols to achieve user goals,"
  concurrently where the goal requires it, without specialised training. The
  distinction to draw is enactment against enforcement: Ahoy shows an LLM can
  *follow* a protocol; it does not statically verify the protocol is
  deadlock-free, nor reject a non-conforming message.
- **Strabo** (arXiv:2606.05043, same group) models the checkout part of
  Google's Universal Commerce Protocol as a declarative protocol and
  interoperates with Google's own implementations. If we ever need to show
  Scribble handles an industrially standardised protocol, that is the case
  study to copy.
- **Pact** (arXiv:2605.03143, workshop on Choreographic Programming 2026)
  identifies the *same hole we do* — choreographic programming "assumes
  cooperative participants … it has no notion of agent self-interest" — and
  fills it with game theory instead of enforcement. Two independent 2026 papers
  agreeing the hole exists is help, not competition. It makes a clean framing
  foil: Pact answers why a self-interested agent would follow the protocol;
  STJP answers what happens when it does not.

### Session-type theory we cite thinly

- **Stutz & D'Osualdo, ESOP 2025** (arXiv:2501.16977), the automata-theoretic
  framework with sound and complete projection for a large class of protocols.
  We cite the Li/Stutz/Wies/Zufferey line but not this one, and a
  programming-languages reviewer will notice the omission. The trade-off to
  state plainly is that complete automata-theoretic projection buys
  expressiveness but its output is a communicating state machine; syntactic
  Scribble projection is what lets us emit human-readable markdown.
- **Formally Verified Liveness with Multiparty Session Types in Rocq**
  (arXiv:2605.23633) and **Mixed Choice in Asynchronous Multiparty Session
  Types** (arXiv:2602.23927) are both live 2026 theory, useful for showing this
  is not a 2008 line of work. Both **unverified**.

## What is still genuinely unoccupied

This is the load-bearing negative evidence, and it held up under roughly
thirty distinct queries across five agents plus a full-text journal-corpus
sweep that returned zero hits.

**Nobody has applied multiparty session types, Scribble, or endpoint projection
to agent markdown artifacts.** Searches crossing the vocabulary of the field
(multiparty session types, Scribble, choreography, behavioural types, gradual
session types, monitorability, communicating finite-state machines) against
every plausible phrasing of LLM agents returned only ZipperGen — which merely
cites multiparty session types — plus classical theory. One search backend
stated outright that its results "don't contain specific information about
applying multiparty session types to natural language protocols or LLM agents in
a combined framework."

**Nobody translates plain language into a multiparty session type.** This
survives, but it must be stated more narrowly than it is now, because
"no prior system translates natural-language intent into a formal multiparty
protocol" is simply false: TraceFix does it with TLA+, and ZipperGen's
runtime-planning mode does it with message sequence charts. The claim that
survives is about the *target formalism and the training*: no prior work
targets a multiparty session type, and no prior work treats that translation as
a trained, verifier-in-the-loop learning problem rather than
prompt-and-repair at inference time.

**Two more specifics are unclaimed**, and both are more valuable than the broad
claim because they are checkable: nobody statically verifies that an
authorization message *precedes* an irreversible one in a protocol (everything
in that crowded space gates at the tool-call boundary, once the agent has
already decided to act), and nobody statically checks declared-goal
reachability. Liveness at scale is explicitly documented as open in the
model-checking work.

**But "we check statically" is no longer a claim on its own.** Agentproof
(arXiv:2603.20356) does pre-deployment static checking across four agent
frameworks with no manual modelling, including a human-approval-gate policy, and
AgentFlow (arXiv:2607.01640) owns the typed-node dependency-graph layer for
agent programs. The verification round found that neither reasons about message
ordering or blocked progress — Agentproof scopes itself to "properties
expressible over the workflow graph," and its named defects (dead ends,
unreachable exits) are reachability-flavoured, while AgentFlow recovers handoffs
as dependency edges rather than typed message sequences. So the surviving delta
is specifically **deadlock-freedom under asynchronous message passing, and
multi-party session fidelity** — and it has to be stated that specifically
rather than as static checking in general. One gap remains open and is the
single highest-value thing left to check: Agentproof's six structural checks are
never individually enumerated in any retrievable text, and if even one of them
is a progress or deadlock check, this delta narrows again.

Two pieces of supporting empirical evidence for why the seam needs a checker in
the loop rather than better prompting, both **verified by search** and both new
to us: LLMs asked to write TLA+ from plain language reach 26.6% syntactic and
only 8.6% semantic correctness across 30 models (arXiv:2606.05792), and LLMs
asked to reason about high-level message sequence charts — the formalism family
nearest to ours — score 52% overall and 36% on abstraction and composition
(arXiv:2605.13773).

## ZipperGen, reconsidered — threat, no; useful, yes

The standing assessment in this project has been that ZipperGen
(arXiv:2604.17612, Bollig/Függer/Nowak) is not a threat: another multiparty
session-type-shaped job, another protocol language, not a portable framework
that checks skill and spec markdown for interaction safety at compile time.
That assessment survives the sweep. Three details in it are now out of date,
and one of them is currently a wrong sentence in the paper.

**What changed.** ZipperGen has a public implementation at `zippergen.io`, and
the architecture is now known: workflows are ordinary Python functions under a
decorator, the decorator rewrites the body into an immutable intermediate
representation mirroring the formal grammar, and projection spawns one thread
per lifeline connected by first-in-first-out queues. It also has a
runtime-planning mode in which an LLM generates the coordination workflow and
the structural guarantees still hold. And it has a follow-up paper.

**The follow-up is the actionable part.** *Causal Past Logic for Runtime
Verification of Distributed LLM Agent Workflows* (arXiv:2605.20923) extends
ZipperGen with a past-time logic for guards in conditionals and loops, with a
vector-clock monitor proved to agree with the guard's semantics. Two agents
verified it independently. The paper currently differentiates against ZipperGen
partly on the grounds that "payload refinements … are absent (data-level
verification is explicitly deferred)." The follow-up closes exactly that gap.
That sentence in `main.tex` must change, and a reviewer who knows this line of
work will find the follow-up in one click from the paper we already cite. The
`min_llmvalid_sched` differentiator is still real, but it is now *statically
checked* guards against *runtime-evaluated* ones, not guards against no guards.

**Is ZipperGen useful to us? Yes, in three concrete ways.**

First, it is the cleanest available statement of the alternative we are defined
against, and now we can cite the mechanism rather than paraphrase it: threads
and first-in-first-out queues owned by the framework, agents that cannot
address a message at all. "The untrusted component is structurally incapable of
sending a message" is a much stronger sentence when you can point at the
thread-per-lifeline implementation that makes it true.

Second, its Lean 4 mechanisation is the right answer to "why should I believe
your projection is correct?" — not because we match it, but because pointing at
the mechanised neighbour and saying plainly that we inherit peer-reviewed
theory instead is more credible than claiming rigour we did not do.

Third, the follow-up's central argument — that a distributed agent workflow
**must not be monitored as a single sequential log**, because a decision may
only depend on events causally visible to the role making it — needs a stated
answer in the paper, but it is not a defect in ours. It is a constraint in
*their* model and a non-issue in a session-typed one, for two reasons that come
straight from the theory. Asynchronous MPST permits permutation of causally
independent actions, and session fidelity holds up to that independence rather
than against any one sequence. And projection gives **one monitor per role**,
each checking only its own local type — the monitorability result we already
cite — so no component ever consults a global order, and a role is never asked
about another role's events. CPL needs causal-visibility machinery precisely
because its guards read other lifelines' latest values; a projected local type
has no such dependency by construction.

What remains is presentation, not semantics: the events file is one
linearization, used for reading traces and computing metrics. That is sound for
every ordering the global type imposes, because those orderings are causally
enforced; metrics must simply not assert order over actions the type leaves
independent. One explicit sentence in the methodology closes this — a reviewer
who has just read CPL will ask, and the answer is that conformance is per-role
and a linearization is a reporting choice.

**The useful consequence runs the other way, and it is an opportunity we are
currently not taking.** `enabled_senders()` in
[`stjp_core/runtime/delm_runner.py`](../../stjp_core/runtime/delm_runner.py)
returns a *list* of roles — every role whose projected local state has an
enabled send. Both runtimes then serialize that set: the decentralized runner
loops over it one role at a time, and the benchmark runner
([`experiments/baselines/foundry_runner.py`](../../experiments/baselines/foundry_runner.py))
builds the enabled list and takes `enabled[0]`. Because the global type proves
those actions independent, dispatching them concurrently is sound by the same
theorem that licenses picking one — so we are serializing by policy and leaving
provable parallelism unused.

Three things follow. It answers the "centralized orchestration limits
scalability" criticism directly: the enabled-set is the set of roles the type
*proves* may act now, so the scheduler can be parallel with a guarantee, where
a hand-built flow graph gets concurrency only where an engineer drew it. It
upgrades the scheduler claim from "fewer calls than taking turns in a fixed
circle" to "the validated type computes the safe parallel schedule" — a
projection artifact no competing system can derive. And it is cheap to measure,
because `delm_runner` already counts actual polls against the round-robin
baseline: a `min_llmvalid_sched_parallel` arm that dispatches the whole enabled
set is a small addition to the registry, and it is the arm where sequential
wall-clock timing finally carries meaning.

**The thing to worry about is not ZipperGen.** It is TraceFix, which is
peer-reviewed and has our whole pipeline shape, and `llmcontract`, which has
our theory family and our application domain and is written by a session-types
researcher. Neither was on the radar before this sweep.

## Where STJP would have helped this very sweep

Running eight agents produced an unplanned piece of evidence: a coordination
failure of exactly the kind the compiler is built to prevent, in first person,
with a token bill.

**What went wrong.** I wrote six lenses — each a role's task assignment — in English and hoped they were
disjoint. They were not. All six agents independently found ZipperGen; four
independently found TraceFix; three found Agentproof; several separately found
DPBench, AgentLTL, *Before the Tool Call*, and *Oversight Has a Capacity*. That
duplicated work was paid for in full, six times over in the worst case.

**What went worse.** The web-search budget turned out to be a single pool of
200 calls shared across the whole session. Two agents consumed it to
exhaustion. The agents launched alongside them then reported, in their own
words, that the budget hit 200/200 and named the queries they never got to run
— one of them the query that would have closed the biggest remaining gap. No
agent knew the budget was shared, none could see the others' consumption, and
nothing stopped the first two from spending all of it. That is resource
starvation under contention: the dining-philosophers shape that DPBench
measures at 25–90% failure, reproduced here at full scale.

**And the failure that cost me the most.** Because no agent could see what
another had already established, the same paper came back ranked Tier-1 by one
agent and unverified by another. I had to re-verify TraceFix, VIGIL, PSMAS and
two others by hand. Two separate agents independently handed me the same
to-do — "verify TraceFix and arXiv:2606.17182 before submission" — discovered
twice, assigned to no one.

**What the compiler would have done about it**, mechanism by mechanism, all of
which exist in this repository today:

- **Projection** turns "six disjoint lenses" from a paragraph I wrote by hand
  into a checked artifact. Each agent receives only its own slice; overlap
  becomes a property of the protocol that a checker can reject, not a hope.
- **The stateful session invariant** — the `__ledger__` sidecar, a running
  value constrained across a whole conversation, such as a budget that must
  never go negative — is an exact fit for a shared 200-call search pool. This
  is the one that stings: the mechanism that would have prevented the worst
  failure of the session is already built, documented in the README as an
  opt-in extension, and I did not have it connected into the thing I was running.
- **The EFSM enabled-set as a claim predicate** (the v3 plan's plane B) stops
  two agents claiming the same lens, because only a role with an enabled move
  may claim.
- **The monitor as a write-admission check on shared context** would have made
  the double-verification impossible: a claim already verified by one agent
  cannot be re-verified by another, because the shared store would have it.

None of this would have fixed the two things that were genuinely outside the
protocol's reach: the arXiv block is an external policy denial, and no amount
of coordination makes search results better. The honest scope of the win is
duplicate spend and starvation — which is exactly what the paper claims, and
about two-thirds of what went wrong here.

This is worth writing up as a case in `experiments/cases/`. It has the
properties the existing real-skills cases have — an unmodified real workload, a
failure that occurred without being seeded, and a protocol that would have
caught it — and it has one they do not: the transcript is ours, so the
counterfactual can actually be run.

## The edit list for the paper

Ordered by how much reviewer damage each prevents.

1. **Soften the third sentence of the introduction.** "No parser that rejects
   an incoherent skill, no type checker …, no compiler that guarantees the
   declared goal is reachable" — clauses one and three are falsified by SkCC and
   by Agentproof/TraceFix. Reframe: skill compilers exist but are intra-role;
   workflow verifiers exist but consume already-written graphs; neither types
   the interaction discipline *between* skills.
2. **Add a TraceFix paragraph beside the ZipperGen one**, and a row in the
   positioning table — differentiating on projection soundness, the unbounded
   check, payload-dependent choice, goal reachability, and cost. **Do not
   differentiate on "they only check topology"; that is false and checkable
   against their public repository.** Drop the four claims listed above that
   TraceFix falsifies, and concede its repair loop and evaluation breadth.
   Consider running its deadlock/livelock ablation shape so the comparison is
   on the record rather than dodged.
3. **Fix the ZipperGen sentence about absent data-level verification** — the
   Causal Past Logic follow-up closes that gap. Restate as statically checked
   guards against runtime-evaluated ones.
4. **Add `llmcontract` to related work** and narrow the session-types claim to
   multiparty + static + projected + scheduling. Use its τ²-bench finding
   (0.6% of *passing* trajectories violate the written confirmation rule) and
   its Playwright numbers (9% and 29%) as third-party motivation.
5. **Reframe the cost contribution** around PSMAS: not "we discovered structure
   is cheaper" but "lossless static projection beats learned scheduling with
   lossy compression, 63% against 27.3%, with no accuracy tax, and the gap
   grows with role count." The role-count scaling law (9.2× to 17.1×) is the
   part nobody else has, so it should carry more weight than the single ratio.
   Separately, name SkillSmith's −57.44% as the compiled-skill baseline and say
   what our savings are on top of it, or state that we do not separate the two.
6. **Stop claiming judge-free evaluation as novel** (GroundEval) and rewrite the
   contribution as contract provenance in one sentence: prior judge-free
   evaluators draft per-task contracts from observed runs with human review;
   ours are projections of one validated global protocol, so adding a task adds
   no specification. Name the before-emission gate as distinct from trace-based
   enforcement (AgentLTL) or a reviewer will read them as identical.
7. **Narrow "we check statically" to what is actually unclaimed** — asynchronous
   deadlock-freedom and multi-party session fidelity — since Agentproof and
   AgentFlow own generic static checking of agent workflows.
8. **Update the MCP citation to the 2026-07-28 revision** and turn the deleted
   session layer into motivation.
9. **Replace self-reported motivation with the third-party numbers** in the
   Tier 2 table, and state the arXiv:2606.17182 contrast — runtime concurrency
   control that costs +8% to 2.3× in tokens against static checks that cost
   none — being careful not to imply that paper does static analysis.
10. **Add the missing theory citation** (Stutz & D'Osualdo ESOP 2025) and the
    declarative-protocol line (Ahoy, Strabo, Pact).
11. **State the permutation answer explicitly in the methodology** — session
    fidelity holds up to permutation of independent actions, monitors are
    per-role, and the linearized event log is a reporting choice, not a
    semantic commitment. This pre-empts the Causal Past Logic objection in one
    sentence.
12. **Add a parallel-enabled-set scheduler arm.** The type already proves which
    roles may act concurrently and both runtimes discard that by taking one.
    This converts the scheduler contribution from a call-count saving into
    "the validated type computes the safe parallel schedule," and it is the
    principled answer to the charge that a central scheduler limits
    scalability.

Three things must be checked from an unblocked network before submission.
**Every arXiv identifier in this document**, because one first-round identifier
was fabricated. **Agentproof's six structural checks**, individually enumerated,
because one of them being a progress check would narrow the static claim again.
And **arXiv:2605.11770** (*Behavioral Integrity Verification for AI Agent
Skills*), which is probably the real paper behind the fabricated identifier and
is entirely unexamined.

## Sources

Verified by direct fetch: [llmcontract](https://github.com/chrisbartoloburlo/llmcontract) ·
[llmcontract-playwright-mcp](https://github.com/chrisbartoloburlo/llmcontract-playwright-mcp) ·
[llmcontract-tau2](https://github.com/chrisbartoloburlo/llmcontract-tau2) ·
[agenticraft-foundation](https://github.com/agenticraft/agenticraft-foundation) ·
[agnix](https://github.com/agent-sh/agnix) ·
[tau2-bench#298](https://github.com/sierra-research/tau2-bench/issues/298) ·
[MCP spec blog](https://blog.modelcontextprotocol.io/)

Verified by search: [TraceFix arXiv](https://arxiv.org/abs/2605.07935) ·
[TraceFix ACM](https://dl.acm.org/doi/10.1145/3786335.3813159) ·
[TraceFix project page](https://ortiz.rutgers.edu/projects/tracefix/) ·
[ZipperGen](https://arxiv.org/abs/2604.17612) ·
[Causal Past Logic](https://arxiv.org/abs/2605.20923) ·
[VIGIL](https://arxiv.org/abs/2606.26524) ·
[PSMAS](https://arxiv.org/abs/2604.17400) ·
[In-Context Prompting Obsoletes Orchestration](https://arxiv.org/abs/2604.27891) ·
[Compiling Workflows into Weights](https://arxiv.org/abs/2605.22502) ·
[SkCC](https://arxiv.org/abs/2605.03353) ·
[SkillSmith](https://arxiv.org/abs/2605.15215) ·
[Skill-as-Pseudocode](https://arxiv.org/abs/2605.27955) ·
[Agentproof](https://arxiv.org/abs/2603.20356) ·
[DPBench](https://arxiv.org/abs/2602.13255) ·
[AgentLeak](https://arxiv.org/abs/2602.11510) ·
[PerspectiveGap](https://arxiv.org/abs/2606.08878) ·
[IAL-Scan](https://arxiv.org/abs/2607.01641) ·
[Wasted computation](https://arxiv.org/abs/2606.01365) ·
[Coordination as an architectural layer](https://arxiv.org/abs/2605.03310) ·
[Ahoy](https://arxiv.org/abs/2606.05390) ·
[Strabo](https://arxiv.org/abs/2606.05043) ·
[Pact](https://arxiv.org/abs/2605.03143) ·
[Stutz & D'Osualdo ESOP 2025](https://arxiv.org/abs/2501.16977) ·
[GroundEval](https://arxiv.org/abs/2606.22737) ·
[AgentLTL](https://arxiv.org/abs/2607.02599) ·
[NL-to-TLA+ evaluation](https://arxiv.org/abs/2606.05792) ·
[LLMs and high-level MSCs](https://arxiv.org/abs/2605.13773)

Also verified in round two: [SkillFortify](https://arxiv.org/abs/2603.00195) ·
[concurrency anomalies](https://arxiv.org/abs/2606.17182) ·
[AgentFlow](https://arxiv.org/abs/2607.01640)

Fabricated by a first-round agent, does not resolve: `arXiv:2605.23951`. The
real paper is probably
[Behavioral Integrity Verification for AI Agent Skills](https://arxiv.org/abs/2605.11770),
unexamined.

Needs a confirming read before quotation:
[TLA-Prover](https://arxiv.org/abs/2606.06133) ·
[Rocq MPST liveness](https://arxiv.org/abs/2605.23633) ·
[Mixed choice async MPST](https://arxiv.org/abs/2602.23927)
