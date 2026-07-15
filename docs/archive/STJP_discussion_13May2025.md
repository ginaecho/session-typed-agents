# Summary: STJP Discussion from the DELEGATE-52 Paper Onward

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The paper in question](#the-paper-in-question)
- [What DELEGATE-52 means for STJP](#what-delegate-52-means-for-stjp)
- [Your empirical finding](#your-empirical-finding)
- [Terminology clarified](#terminology-clarified)
- [Monitor design](#monitor-design)
- [The authorship disclosure](#the-authorship-disclosure)
- [Benchmarking strategy](#benchmarking-strategy)
- [Net position after today's conversation](#net-position-after-todays-conversation)
<!-- MENU:END -->

## The paper in question

Microsoft Research's DELEGATE-52 benchmark tests how LLMs corrupt documents during long delegated workflows across 52 professional domains. Headline findings: frontier models (Gemini 3.1 Pro, Claude 4.6 Opus, GPT 5.4) lose ~25% of document content over 20 interactions; weaker models lose 50%+. Agentic tool use made things worse, not better. Failures are sparse-but-severe critical errors (10+ point drops in single rounds) accounting for ~80% of total degradation, not gradual drift.

## What DELEGATE-52 means for STJP

**It's a useful supporting citation, but not in the broadest sense.** The paper empirically validates the problem space STJP claims to address — LLMs are unreliable delegates in long workflows, and adding agentic tooling doesn't fix it. This strengthens STJP's "deterministic compilation vs. probabilistic guardrails" argument with hard numbers.

**But it doesn't test what STJP claims to govern.** DELEGATE-52 measures single-LLM document editing without any skill.md or agents.md spec layer. There's no governing specification, no multi-agent composition, no protocol verification. The failure mode it documents (intra-agent content corruption) is related to but distinct from STJP's target failure mode (inter-agent protocol violation).

**Critical realization:** the paper neither proves nor disproves that skill.md / agents.md effectively harness agent behavior. That question is simply not in its experimental design.

## Your empirical finding

You reported your own experiments showing that **agents follow projected local types at near-100% on structural elements** (correct recipient, correct ordering, correct branching) **but fail on value-dependent constraints** — the canonical example being "send less than $50,000 to B" where the agent correctly sends to B but sends exactly $50,000.

This finding is significant in two ways:
- It closes the empirical gap I'd flagged earlier: skill.md is not a fiction; local types do govern interaction structure
- It precisely identifies what agents are weak at: enforcing semantic invariants over payload content

## Terminology clarified

The "send less than $50,000" constraint is a **refinement type** (more generally, a **value-dependent type**). It's first-order, not higher-order. The literature term for the failure class is **constraint satisfaction over arithmetic predicates** or **payload-level invariant enforcement**. The framework's anchored-predicate layer is the textbook answer to exactly this gap: structural session types handle routing/ordering, refinement predicates handle payload values.

## Monitor design

You converged on Monitor-as-compiled-boolean-functions: each refinement predicate compiles to `func_check(msg) := if msg.amount < 50000 then ALLOW else REJECT`, evaluated at the interaction checkpoint. This is the right design because it's decidable, stateless, terminating, auditable, hot-swappable, and integrates naturally with deterministic tools when external data is needed for the check. The literature term is **monitor synthesis from assertions** or **runtime assertion checking for multiparty sessions**.

## The authorship disclosure

You revealed you're a co-author on the Bocchi/Chen/Demangeon/Honda/Yoshida 2013 line on monitor synthesis from MPST with assertions. This reshapes the novelty argument substantively: the formal monitoring substrate is your own prior work, not borrowed foundation. The honest framing becomes:

> *The contribution is the integration: LLM elicitation of Global Protocols with embedded refinement assertions from prose intent, proposal-and-confirm goal review making formal assertions accessible to non-experts, application of monitor synthesis (our prior work) to LLM-driven agents whose failure modes we empirically characterize, and static rejection of structurally unsound agent specifications before any LLM execution. Each piece exists in some form in prior work, including our own; the integration into a coherent framework for governing LLM agent compositions is new.*

This is more defensible than "first compiler for agents" because every prior-art challenge has an explicit answer.

## Benchmarking strategy

For empirical validation against competing systems, you'd need to construct a benchmark across five distinct challenge classes (no existing benchmark covers what STJP claims):

1. **Protocol-fault corpus** — specs with known structural defects (deadlocks, missing join-points, orphan messages); measures whether each governance system catches them and at what stage
2. **Refinement-predicate corpus** — specs with value-dependent constraints like your $50,000 case; measures whether each system catches payload-semantic violations (and especially false negatives)
3. **Cost and latency** — tokens, dollars, latency across specification and runtime phases; documents the O(N) → O(1) amortization claim with actual numbers and crossover points
4. **Evolution and subtyping** — scenarios where protocols change mid-execution; measures whether each system correctly accepts safe extensions and rejects unsafe ones
5. **Pre-execution security** — specs with embedded threats (prompt injections, undeclared external calls); measures pre-execution detection rates

Critical methodology points: fix the underlying LLM across all conditions; report per-class results rather than aggregate averages; separate false-positive and false-negative rates with appropriate asymmetric weighting; include long-horizon runs (10, 50, 100+ interactions) since DELEGATE-52 showed short-horizon performance doesn't predict long-horizon behavior; pre-register the analysis plan.

The hardest engineering challenge is constructing the protocol-fault corpus at scale — likely 30–50 hand-crafted specs for an initial paper, expanding to 500+ for a benchmark-paper contribution. Splitting into two papers is more realistic than attempting both at once.

The honest framing of headline results should lean into harder classes (semantic, evolution) rather than just structural ones, since structural wins are tautological given the MPST foundation.

## Net position after today's conversation

The framework is on substantially firmer ground than at the start:

- **Static-vs-runtime as the load-bearing distinction** — not "we do verification, they don't" but "we reject malformed choreographies before LLM invocation, in polynomial time, deterministically, with theorem-backed guarantees"
- **Artifact-level framing** — STJP treats declarative agent specs as source programs, which prior agent-verification work (VeriGuard, AgentSpec, VeriPlan) does not
- **Empirical anchor** — agents follow structural local types at near-100% but fail on numerical refinement constraints, motivating the two-layer (MPST + refinement) design
- **Authorship of the substrate** — the monitor-synthesis foundation is your own prior work, not adopted technique
- **Refined novelty claim** — the contribution is the integration of LLM elicitation, proposal-and-confirm review, monitor synthesis applied to LLM agents, and pre-LLM-execution static rejection, rather than any single component

What remains open: the benchmark suite needs to be constructed; the predicate-language tier should be committed to (decidable quantifier-free fragment with linear arithmetic recommended); the proposal-and-confirm loop needs its own evaluation for autoformalization reliability; and the LLM-edits-the-spec corruption risk (raised by DELEGATE-52's findings) should be acknowledged as a residual concern that the Checker's re-verification on every Revisor edit partially addresses.
