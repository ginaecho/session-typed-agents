# Discussion notes — related work and self-review, 2026-07-25

Working notes from the owner's discussion with the assistant, written down
so the next paper version can draw on them as references and discussion
material. **This document does not revise the paper**; it records the
arguments, the evidence behind them, and an honest self-review of the new
mechanisms. Verified competitor facts all trace to
[`../docs/reference/RELATED_WORK_2026-07.md`](../docs/reference/RELATED_WORK_2026-07.md)
(per-item verification status there; arXiv confirming reads still pending
an unblocked network). Terms glossed once: the **seam** is the translation
step from plain-language intent to formal protocol; an **arm** is one
configuration being compared, like a trial's treatment and control groups.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Agentproof: why a workflow graph is not a global type](#1-agentproof-why-a-workflow-graph-is-not-a-global-type)
- [2. TraceFix: which mathematics, what is bounded, where the soft spot is](#2-tracefix-which-mathematics-what-is-bounded-where-the-soft-spot-is)
- [3. The one-table comparison](#3-the-one-table-comparison)
- [4. Evidence strength vs. system capability](#4-evidence-strength-vs-system-capability)
- [5. The residual as a risk register, not a shrug](#5-the-residual-as-a-risk-register-not-a-shrug)
- [6. Self-review: enough? needed? distinctive? on-vision?](#6-self-review-enough-needed-distinctive-on-vision)
<!-- MENU:END -->

## 1. Agentproof: why a workflow graph is not a global type

A workflow graph and a global type sound similar — both are "the whole
system drawn from above" — but they hold different information, and
everything multiparty session types (MPST) guarantee lives in the
difference. A graph records nodes (agents/steps) and edges (handoffs,
dependencies); Agentproof extracts this across four frameworks with no
manual modelling and checks "properties expressible over the workflow
graph" — its named defect classes (dead ends, unreachable exits) are
reachability on the drawing.

Three things a graph cannot even *represent* — not "does not check,"
cannot express:

1. **Waiting.** The `trade_deadlock` case as a graph looks healthy: Buyer
   and Seller nodes, edges both ways — "they communicate." The deadly fact
   is not an edge; it is that in its current state Buyer has only a
   *receive* enabled (waiting for goods) and Seller has only a *receive*
   enabled (waiting for payment). "Who is blocked waiting for what, in
   which state" is a property of the joint state machine; a dependency
   edge has no slot for it. A global type carries direction, order, and
   continuation for every interaction, so a circular wait becomes a
   syntactic defect rejected before any run — exactly the "blocked
   progress" Agentproof scopes itself away from.
2. **Choice coherence.** In the `finance` protocol, Fetcher branches and
   both analysts must learn which branch was taken. As a graph, both
   branches contain the same Fetcher→Analyst edges — indistinguishable. In
   a global type the branches are distinct continuations, and
   well-formedness rejects a branch that leaves a role uninformed — the
   "missing message in a branch → agents get stuck" mistake, caught at
   compile time.
3. **Projection — nothing to project.** A graph does not decompose into
   per-role behavioral obligations; there is no "Seller's local view" that
   constrains Seller's next act. A global type projects into one local
   contract per role, with the theorem `stjp_core/monitor/monitor.py`
   cites: global compliance = all local monitors pass. No graph formalism
   has an analogue — so no local contracts, no per-role monitors, no
   soundness relation between whole and parts.

Verdict for the paper: Agentproof validates the shape of the drawing, not
the discipline of the conversation. **Open caveat, highest-value check
left:** its "six structural checks" are never individually enumerated in
any retrievable text; if one is a genuine progress check, the delta
narrows and this section must be updated.

## 2. TraceFix: which mathematics, what is bounded, where the soft spot is

TraceFix is neither MPST nor ZipperGen's lineage (ZipperGen is itself an
MPST/Scribble-family system — same theorem family as STJP, different
packaging). TraceFix is the third tradition: **explicit-state model
checking** (TLA+/PlusCal). Pipeline: an LLM writes the protocol in
PlusCal → the TLC model checker searches the state space → counterexamples
drive a repair loop → per-agent finite-state monitors are extracted
mechanically; per-agent *prompts* are written by an LLM.

**What "bounded" means.** Model checking enumerates reachable states; with
asynchronous channels the state space is infinite (a channel's content is
part of the state). TraceFix caps channel length (`ChannelBound`) — its own
architecture document says this exists to stop state-space explosion. So
"100% verified" means: verified for every execution in which no channel
ever holds more than k messages, and the guarantee is re-earned per
protocol, by search, at search cost. MPST's route differs in kind:
Scribble well-formedness is a syntactic, polynomial check whose metatheorem
delivers deadlock-freedom and session fidelity for **all** executions with
**unbounded** buffers, by construction — nothing enumerated, nothing
re-earned. (That is why `publish_flow` validated in seconds with no
buffer-size asterisk.)

**Safety-only.** Their "termination" property is *no reachable deadlock* —
stated with unusual candor as not liveness, not fairness, not a proof that
executions finish. Goal reachability is territory they explicitly do not
enter — and they flagged the deadlock-freedom-renamed-as-termination
conflation against themselves, so STJP's reachability claim will be held
to the same standard and must be a genuine reachability property.

**The projection gap — their real soft spot.** Their per-agent monitors
are extracted mechanically (solid — and why "we generate per-role FSM
monitors" is not novel for STJP; theirs won a best-paper award). But the
per-agent *prompts* — what the agent actually obeys — are LLM-written,
LLM-checklist-checked, and guarded by sixteen hand-written anti-patterns.
No theorem connects prompt to checked spec. STJP's local contract *is* the
projection of the checked global type; the anti-pattern list is the
evidence for why that matters.

**Payload-dependent choice.** Their "sole-mediation" rule forbids message
content from affecting coordination: channels carry a label only, guards
range over loop counters, content rides an unverified side plane. The
`banking` case (amount above threshold must route through the Approver) is
payload-dependent choice, checked; unrepresentable on their verified plane.

**What to concede — updated.** The sweep originally listed two clear
TraceFix strengths. One has since been cut in half: the
counterexample→repair loop already exists in this repository as an
instrumented component (`experiments/seam_bench/t0/repair_loop.py`: draft →
real-Scribble validate → repair on the validator's counterexample →
revalidate, 3-round cap; per-attempt records; repair-rounds metric;
first-attempt validity — the direct analogue of their 62.5% statistic;
test suite 10/10 in a fresh container). The D3 mutation-based repair
tuples go further than their sixteen anti-patterns: a *training corpus*
for the repairer, classed per mutation operator. What remains theirs until
one metered T0 run with a real drafting model (priced at $5–20 in
[`ICLR_READINESS.md`](ICLR_READINESS.md)): published *numbers*. The
concession to keep in full is **evaluation breadth** (48 tasks, 3,456-run
comparison, fault injection at 0/30/60/90%). Shared weakness to state, not
hide: both systems leak off-protocol side channels (their content plane;
our shell/filesystem plane) — do not claim to close a hole they leave open
until the domain plane is sandboxed.

## 3. The one-table comparison

| Property | Agentproof (graph) | TraceFix (model check) | STJP (MPST) |
|---|---|---|---|
| Deadlock under async messaging | cannot represent waiting | yes, within channel bound k | yes, unbounded, by well-formedness |
| Choice coherence | branches indistinguishable | yes, within bound | yes, syntactic check |
| Per-role local contract | nothing to project | monitors mechanical; prompts LLM-written (16 guardrails, no theorem) | projection with soundness theorem |
| Local ⇒ global compliance | no analogue | not stated | the monitorability theorem `monitor.py` cites |
| Payload-dependent choice | n/a | forbidden by design | refinements + choice guards |
| Goal reachability / liveness | reachability on the drawing only | safety only, says so | claimed — must be proven as genuine reachability |
| Cost of the guarantee | cheap, weak | search, re-earned per protocol, bounded | polynomial, once, unbounded |

Short version: Agentproof checks the drawing; TraceFix searches the state
space until a budget runs out; MPST's theorem makes the guarantee a
property of the syntax itself. The full nine-system when/what table
(including the skill compilers and runtime monitors) is in
[`../docs/reference/ENFORCEABILITY_PARTITION.md`](../docs/reference/ENFORCEABILITY_PARTITION.md).

## 4. Evidence strength vs. system capability

Their 48-task / 3,456-run evaluation measures evidence, not capability:
no theorem gets weaker because someone else ran more trials. But STJP
makes two kinds of claims, and only one is theorem-covered. "The protocol
cannot deadlock" needs a demonstration, not an n. "This makes real agent
teams safer and cheaper in practice, across models" is empirical, and for
empirical claims evaluation breadth *is* the substance — a reviewer
compares n to n, not potential to n. The opportunity hiding in this
concession: two of their axes test exactly what STJP's thesis predicts it
wins — **fault injection** (enforcement should degrade far more gracefully
than prompted compliance as the misbehavior rate climbs) and the
**model-capability degradation curve** (the metered version of the
AgenticPay three-tier result: the deadlock is capability-invariant, the
protocol fix works at every tier). Running their ablation shapes is not
matching effort for appearances; it is collecting evidence for our
strongest differentiators in a format their reviewers already accept.

## 5. The residual as a risk register, not a shrug

"We cannot enforce it" would be weak if it ended there. The partition's
residual tier is a three-column risk register: every unenforceable rule
carries (a) a **named compensating control and placement** (the recurring
offenders of the writing rule are linted; new coinages route to review
with the rule on the checklist — the control does not decide the judgment,
it shrinks the room where the judgment fails), (b) a **violation
forecast** from three predictors — distance, conflicting instruction,
cost-to-obey — each with a demonstrated mitigation, and (c) the record
that residual is a **pipeline, not a verdict**: three rules moved from
residual-in-practice to lint-enforced in one day. The claim this supports:
*every rule is either enforced by a named mechanism, or carries a named
control plus a predicted failure profile — no rule sits in the unexamined
gap between.* Competitors cannot make that claim because, lacking the
three enforcement tiers, they cannot produce the list.

## 6. Self-review: enough? needed? distinctive? on-vision?

An honest tiering of the 2026-07-25 mechanisms, asked three ways: does it
solve something others cannot, is it needed, and does it serve the vision
(compile-time interaction safety for agent teams via checked global
protocols, projected per-role)?

**Distinctive — others cannot do this, and it is the paper's material:**

- **The enforceability partition with its residual register.** No system
  in the sweep partitions a spec by enforcement tier or reports what it
  cannot enforce; only a system with all three tiers can. Weakness to fix
  before it is a *result*: n=1 (AGENT.md, self-referential). The upgrade
  that makes it measurable: run the partition over the mined real-world
  skills corpus and report the tier distribution of real rules — that
  turns a worked example into a finding.
- **The conflict/precedence pass.** Instruction conflict as a compile-time
  type error ("refusing to guess") addresses a failure class — silent
  precedence resolution — that has no analogue in any swept system, and it
  came from a real incident with first-person evidence. This is a genuine
  candidate for a paper section.

**Needed, but supporting — honest about novelty:**

- **The gate generator** (`gen_gate.py`). Offline-compiling declared rules
  into boundary checks is what SkillSmith-style compilers already do
  intra-role; ours is not research novelty on its own. Its value is
  structural: it proves the registry→mechanism pipeline and feeds the same
  registry as the typed channel, so the lint tier stays honest ("guaranteed,
  but not by the monitor").
- **The publish-flow typed channel.** On-vision — it moves an irreversible
  act from a fence (a hook that must be enabled) to the field (a payload
  refinement on the only path to the act), and it points at the
  side-channel hole both we and TraceFix currently share. But today it is
  a demonstration: the *real* `git push` does not yet go through it. Until
  Stage 4 (the working session as a session) makes the channel the actual
  execution path, this is a seed, not a solution — the paper may show it
  as mechanism, not claim it as deployed protection.

**Not enough yet — the gaps that matter more than more tooling:**

1. **One metered T0 run** with a real drafting model fills the
   repair-loop comparison cell against TraceFix's 62.5% (needs an LLM
   key; $5–20). Highest value per dollar in the whole plan.
2. **The parallel scheduler**, implemented and measured against its
   pre-registration — the standing answer to "a central scheduler cannot
   scale," gated on an environment that can re-run the case suite.
3. **Stage 4** — typing the working session itself, so orderings like
   "rules loaded before first push" and "registration precedes the trial"
   become type structure. This is the genuinely novel follow-through of
   the incident record, and the only path by which the lint tier's rules
   migrate into the monitor's jurisdiction.
4. **Their ablation shapes** (fault injection, capability degradation) on
   our benchmark, where our thesis predicts wins.

**Vision check, stated as a risk:** the failure mode to avoid is
accumulating ad-hoc linters and calling them STJP. The partition is the
guard against that — it labels every lint-tier mechanism as outside the
monitor's guarantee, and Stage 4 is the declared path from "linted beside
the session" to "typed inside it." As long as each new checker is either a
compiled projection of a declared rule or explicitly tagged residual
support, the tooling serves the thesis instead of diluting it.
