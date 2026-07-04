# Testing Strategies — From Rough to Right

How we test STJP fairly, and why it took multiple tries to get it right.

**Date: 2026-07-03**

---

## 1. What are we testing? (Four separate claims)

STJP makes four distinct promises. Each one is testable only in isolation:

| # | Claim | What it means | Why it matters |
|---|---|---|---|
| **D** | Deadlock-freedom by static check | Scribble catches circular waits before runtime | Only a formal checker can catch deadlocks; unchecked specs deadlock at some rate |
| **I** | Static interaction correctness | Catches mismatched roles, inconsistent choices, and value-dependent branch errors at design time | Bugs found before any token is spent |
| **T** | Token savings | A compiled per-agent contract removes coordination overhead | Same task, fewer tokens |
| **W** | Time savings | Wall-clock seconds per delivered result | Same task, fewer seconds |

**Why separate them?** If you report one number per arm and say "this proves all four claims," you're deceiving yourself. You need separate tests.

> **What's an "arm"?** An *arm* is one configuration being compared in an
> experiment — e.g. "agents with a protocol" vs "agents without one" — the same
> way a clinical trial has a treatment arm and a control arm. This document
> compares seven arms (listed in §7).
>
> **Acronyms used below:** **MPST** = Multiparty Session Types (the theory that
> guarantees a protocol can't deadlock); **EFSM** = Extended Finite-State
> Machine (the step-by-step turn map the scheduler follows); **MAF** = Microsoft
> Agent Framework (one of the agent runtimes we test against); **projection** =
> automatically splitting the whole protocol into one contract per agent.

---

## 2. The evolution: what we learned the hard way

### **Version 1 (naive, confounded)**

Early runs compared:
- Arm A: "just the intent" (no protocol)
- Arm B: "global protocol pasted as text" (but run through a group-chat orchestrator)
- Arm C: "local contracts" (run through round-robin decentralized agents)

**The mistake:** Changed TWO variables at once:
1. What the agents got (global text vs local contracts)
2. How they were orchestrated (centralized group-chat vs decentralized round-robin)

So when Arm B won, we couldn't tell if it was because:
- Global text is better than local contracts? OR
- Orchestrated coordination is better than decentralized?

**Lesson:** Never change more than one thing in a comparison.

### **Version 2 (fairness rules established)**

We learned to hold ONE variable constant:

- To test **SPEC** (what agents are given): hold runtime constant → use decentralized for all arms
- To test **RUNTIME** (how they're orchestrated): hold spec constant → use local contracts for all arms

This let us ask cleaner questions:
- "Is global text better than local contracts?" (fix runtime)
- "Is group-chat orchestration better than round-robin?" (fix spec)

### **Version 3 (projection-aware, execution plane)**

Added a new variable: the **scheduler** (the protocol's state machine decides who acts next).

Now we can test:
- Local contract alone vs local contract + enforcement gate vs local contract + gate + scheduler
- Each step isolates whether that piece adds value

**Result (2026-07-02):** Local contract + gate + scheduler was simultaneously the safest and cheapest option.

### An honest finding we always report (do not oversell the gate)

On a strong model (GPT-5.4) with a small protocol, **pasting the whole validated protocol as plain text already fixes correctness** — the global-text arm also reaches 100% completion with zero disasters. The gate does not beat it on outcomes; the **protocol itself does the correctness work**, however it is delivered.

So what does the rest of the STJP stack actually buy? Three things the text-paste approach cannot provide:

1. **A guarantee instead of good behavior.** In the 2026-07-02 run the gate rejected 10–12 off-contract send attempts per trial — the model *did* try to stray; enforcement caught it every time. "The model happened to comply" is not the same as "non-compliance is impossible."
2. **An audit trail.** Every message gets an allow/deny verdict against the contract — evidence for compliance, not just a transcript.
3. **The cost win.** Here is the key asymmetry: a protocol pasted as text **cannot schedule**. Deciding "who can act right now" from prose requires either an LLM orchestrator (more calls, no guarantee) or a hand-written dispatcher. Only a machine-checkable protocol mechanically produces a scheduler — and that scheduler is where the 9× cost saving comes from.

Also honest: STJP's help is **model-dependent** (bigger on weaker models) and **scale-dependent** (per-agent contracts save little on a 15-message protocol, because one agent's slice isn't much smaller than the whole; the projection saving grows with protocol size). We report both dependencies rather than hiding them.

The full trace-level analysis behind this is preserved in `archive/WHY_B_MATCHES_C_ANALYSIS.md`.

---

## 3. The fairness rules (lessons paid for in muddy runs)

Apply these to every comparison:

### Rule 1: One variable per comparison

**Bad:** "Let's compare global text (orchestrated) vs local contracts (decentralized)."  
**Good:** "Let's compare global text vs local contracts, both with decentralized agents."

### Rule 2: Separate "did it work" from "what did it cost"

**Bad:** Run a task where half the arms fail, then report "this arm is cheapest."  
**Good:** Use a task everyone can finish (for token/time tests) and a separate task where failure is possible (for safety/correctness tests).

- **Success-critical tasks** → test claims D and I (completion is the only metric)
- **Completable tasks** → test claims T and W (everyone finishes; cost is the metric)

### Rule 3: Robust, structural goals (no magic strings)

**Bad:** A goal coded as `"pass" in payload`. Agents who wrote "approved for delivery" failed.  
**Good:** Use:
- Existence checks (e.g., "a report message was sent")
- Numeric predicates (e.g., "the number is exactly 50000")
- Role-pair checks (e.g., "Auditor sent to Client")
- Or a frozen LLM judge with a hand-audited sample

### Rule 4: Correct, theory-faithful monitor

**Bad:** A monitor that enforces strict ordering even when the protocol allows concurrency (e.g., two different agents sending to two different peers at the same time).  
**Good:** Follow MPST theory: allow any interleavings on different channels; only enforce ordering on the same channel.

**Fixed 2026-06-17:** The monitor now correctly allows concurrent actions on different channels.

### Rule 5: Report every model in scope

STJP's value is model-dependent:
- Stronger on weaker models (GPT-4o gets more help from structure)
- Weaker on frontier models (GPT-5.4 self-complies even with intent-only)

**Show the trend:** Report results for both weak and strong models. Never hide a model under "we tested on frontier so it's universal."

### Rule 6: Don't rig the failure (for deadlock claim)

**Bad:** Only hand-write a protocol that deadlocks, then say "look, Scribble caught it!"  
**Good:** Also let an LLM author per-agent specs from intent and report the **rate** at which unchecked authoring produces deadlock/unsafe protocols. That's the honest risk.

### Rule 7: State the control explicitly

Every result line should name:
- The task
- The one variable being changed
- What is held constant
- The metric
- The model

If you can't state all five clearly, it isn't a clean comparison.

---

## 4. The design: Two axes, four task shapes

### Axis 1: SPEC (what each agent is given)

From weakest to strongest support:

- **Intent only** — plain task description, no protocol
- **Global protocol as text** — the whole protocol pasted as a string
- **Local verbose contract** — each agent gets its full local contract (what it may send, what it must wait for)
- **Local lean contract** — same, compressed to a few key steps
- **Enforcement gate** — local contract + a monitor that blocks wrong messages
- **Execution scheduler** — local contract + gate + EFSM scheduler that optimizes turn order

### Axis 2: RUNTIME (how agents are coordinated)

- **Decentralized** (realistic) — agents send to each other via message channels; no orchestrator
- **Group-chat orchestrated** — a central orchestrator (like an Azure group chat) mediates all messages
- **EFSM-scheduled** — the protocol's state machine decides who acts next

### Four task shapes (each tests one claim)

| Task | What it tests | Why | Example case |
|---|---|---|---|
| **Deadlock-prone** | Claim D (static deadlock check) | A circular dependency hidden in plausible local rules; unchecked specs deadlock, checked specs don't | `trade_deadlock`: Agent A can't give report until Agent B approves, but Agent B won't approve until getting Agent A's report |
| **Coordination-heavy, always completable** | Claims T/W (token/time savings) | Everyone finishes; we measure cost per delivered result | `report_pipeline`: 6 agents in sequence, each adds to a report |
| **Safety-critical** | Claim I (value-dependent correctness) | An irreversible action (like filing) that must be authorized first; mistakes are disasters, not just slower | `finance`: Revenue report triggers audit if over $50k |
| **Scale** | Claim T at scale | Many roles, deep nesting; does projection's context benefit grow with size? | (Future: 20-role supply chain) |

---

## 5. How we grade results

### Grading criteria

For each trial (run of an agent group), we measure:

- **Goal-Completion Rate (GCR)** — Did they finish the task correctly on the first try? (0% = failed, 100% = all trials succeeded)
- **Critical-Goal Completion (CGC)** — Did they finish AND follow all the safety rules (data provenance, read inputs before deciding, get authorization before irreversible acts)?
- **Disaster rate** — How many trials had an irreversible action without proper authorization?
- **Tokens / Trial** — LLM tokens spent per attempt (including failed attempts)
- **Cost-to-goal** — Total tokens ÷ GCR (charges an arm for wasted tokens on failures)
- **Time-to-goal** — Wall-clock seconds per delivered result

### Example: The finance case results (2026-07-02)

| Arm | GCR | CGC | Disasters | Cost-to-goal | Seconds/trial |
|---|---|---|---|---|---|
| Intent only | 0% | 0% | 18/10 | ∞ | — |
| Global text | 100% | 100% | 0 | 120k tokens | 124s |
| Local + gate | 100% | 100% | 0 | 38k tokens | 96s |
| Local + gate + scheduler | **100%** | **100%** | **0** | **13k tokens** | **32s** |

**Read this:** Everyone with a protocol (arms 2–4) had zero disasters. But the scheduled arm was 9× cheaper than global text, 3× cheaper than gate-only, and faster too.

---

## 6. The current arms (2026-07-02 run)

Seven implementations tested on finance case, gpt-5.4, n=10 trials each:

| Arm | Spec | Runtime | Notes |
|---|---|---|---|
| A: Bare | Intent only | Decentralized | Baseline: no protocol |
| B-orch: MAF | Global text | Orchestrated (group chat) | Reference: structured, coordinated |
| B-dec: Global | Global text | Decentralized | Fair test of spec format (same runtime as C/D/E/F) |
| C-min: Min contract | Local lean | Decentralized | Observer: no enforcement |
| C+spec: Spec gate | Local verbose | Decentralized | + enforcement gate |
| C+min: Min gate | Local lean | Decentralized | + enforcement gate, compressed |
| **STJP: Scheduler** | **Local lean** | **EFSM scheduler** | **Full stack: projection + gate + optimized scheduling** |

---

## 7. What to read next

- **To understand how benchmarks measure:** Read `3_BENCHMARK_DESIGN_EXPLAINED.md`
- **To see actual results:** Read `5_RUN_REPORTS_EXPLAINED.md`
- **To understand safety cases:** Read `6_USE_CASE_DEADLOCK_SAFETY.md`
