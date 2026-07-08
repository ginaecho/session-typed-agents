# Tech Setup — Session-Typed Judge Panel (STJP)

Everything you need to understand how STJP works technically, and how to run it.
(STJP is the *system*; the agents it runs are "session-typed agents" — the
adjective describes the agents, while STJP names the system that governs them.)

**Date: 2026-07-03**

---

## 1. What is Scribble?

Scribble is an off-the-shelf tool that takes a description of how multiple agents should talk to each other (called a "global protocol") and checks it for problems:

- **Can they deadlock?** (Agent A waits for a message Agent B will never send, and vice versa.)
- **Are the roles consistent?** (Does Agent A think it sends a message that Agent B thinks it receives?)
- **Is the conversation complete?** (Does every role reach an end state, or could someone get stuck?)

Think of Scribble like a **type checker for conversations**. Just as a type checker finds bugs in code before it runs, Scribble finds bugs in protocols before agents run.

Scribble outputs two things:
1. A "yes it's safe" verdict for the global protocol
2. A **local contract** for each agent—a summary of just that agent's part

### Two compiler backends: scribble-java and nuscr ("nuscribble")

STJP can drive **two** interchangeable protocol compilers, selected with the
`STJP_COMPILER_BACKEND` environment variable:

- **`scribble` (default)** — the reference `scribble-java` implementation
  (built from source; the 2017 Maven releases silently accept everything, so
  always build `master`).
- **`nuscr`** — the OCaml **coinductive** fork ("nuscribble"). Set
  `STJP_COMPILER_BACKEND=nuscr`. It runs either from a Docker image or, when
  Docker Hub is blocked, from a **native binary** pointed at by
  `STJP_NUSCR_BIN` (e.g. `STJP_NUSCR_BIN=/usr/local/bin/nuscr`).

Both go through the same `stjp_core/compiler/compiler_iface.get_compiler()`
seam, so the validator, the projected local types, and the EFSMs are produced
the same way regardless of backend. We verified the two backends produce
**isomorphic EFSMs** on all four RESULT_8 protocols, and the n=100 real-skills
run (`5_RUN_REPORTS_EXPLAINED.md`) was projected through nuscr.

**Full install + run instructions** (Docker route, CI-artifact native-binary
route, building scribble-java from source, and the env-var reference) are in
[`reference/NUSCR_CLOUD_INSTALL.md`](reference/NUSCR_CLOUD_INSTALL.md).

---

## 2. What does STJP add to Scribble?

STJP extends Scribble with three new capabilities:

### A. Conditional / "Value-dependent" rules

Scribble only knows about message types like `int` or `String`. STJP adds **conditions on values**, like:

- "If the revenue number is over $50,000, you MUST take the audit branch"
- "The account number must match the pattern ABC-123456"

These conditions are written in a `.refn` file (a "refinement" file) that sits next to the protocol.

**Why it matters:** You can now enforce not just the shape of messages, but whether the agent chose the right path based on what it actually saw.

### B. Cross-file composition (building bigger protocols from smaller pieces)

Real teams write protocols in separate files: `Banking.scr`, `Audit.scr`, `Reporting.scr`. STJP lets you **compose** them into one protocol without copy-pasting.

In your protocol file, you write:
```
// @use Banking from "../banking/Banking.scr"
// @use Audit from "../audit/Audit.scr"

global protocol FinancePipeline(...) {
    do Banking(...);
    do Audit(...);
    ...
}
```

STJP's composer automatically splices them together and runs Scribble on the whole thing to ensure they still fit together safely.

### C. Higher-order (passing protocols like arguments)

One agent can hand off a sub-protocol to another agent, like passing a function as an argument. Scribble's grammar already supports this—STJP just uses it.

---

## 3. How STJP works end-to-end

```
Natural language intent
    ↓
LLM drafts a protocol (.scr file)
    ↓
Scribble checks it for deadlocks & safety
    ↓
Refinements (.refn file) add value-level rules
    ↓
Projection: split into one local contract per agent
    ↓
Monitor: watch real agents, check each message against the contract
    ↓
Gate (optional): block wrong messages before they're delivered
    ↓
Scheduler (optional): use the protocol to optimize who talks when
```

---

## 4. The glossary — every term explained

### Messages and protocols

- **Global protocol** — the whole conversation written once: who sends what to whom, in what order.
- **Projection** — the automatic split that turns one global protocol into one local contract per agent.
- **Local contract** — one agent's slice of the protocol; it says "you may send X, then you must wait for Y, then send Z."

### Checking and safety

- **Deadlock** — Agent A waits for Agent B's message, but Agent B waits for Agent A's message, so both hang forever.
- **Scribble** — the tool that finds deadlocks and safety problems in protocols.
- **Well-formedness** — Scribble's yes/no verdict: "this protocol is safe to project and run."

### Enforcement

- **Runtime monitor** — a small Python program that watches each agent and checks every message: "Is this message allowed right now?"
- **Monitor acceptance** — how many messages the monitor allowed.
- **Delivered violations** — how many off-contract messages actually reached their recipient (the agent tried to send something the protocol forbids).
- **The gate** — the monitor in "enforcing" mode: it blocks wrong messages and asks the agent to try again.

### Measurements

- **Goal-Completion Rate (GCR)** — the percentage of trials where agents finished everything correctly on the first try.
- **Disaster** — an irreversible action that happened before its authorization step (e.g., filing a report before auditing it).
- **Cost-to-goal** — the average number of tokens spent per successfully delivered result.
- **Time-to-goal** — wall-clock seconds per delivered result.

### Other terms

- **Refinement** — a value-level condition on a message (e.g., "this number must be > 0").
- **Choice guard** — a rule that says "if the data looks like this, you MUST take this branch of the decision."
- **Multiparty Session Types (MPST)** — the formal theory Scribble and STJP are built on. It says: "If your global protocol passes all the checks, then every agent can safely follow their local contract and never deadlock."

---

## 5. Running STJP with Azure AI Foundry (Hosted Agents)

### Prerequisites

You need:
- Python 3.9+
- An Azure subscription with Azure AI Foundry access
- Azure Developer CLI (`azd`) installed

### Setup steps

1. **Install the hosted agent tools:**

```bash
azd ext install azure.ai.agents
azd extension upgrade azure.ai.agents
```

2. **Authenticate with Azure:**

```bash
azd auth login --client-id "<your client id>" \
               --client-secret "<your client secret>" \
               --tenant-id "<your tenant id>"
```

3. **Initialize a new agent project:**

```bash
azd ai agent init
```

Follow the terminal prompts to:
- Select "Agent Framework" as your runtime
- Choose which MCP tools you want available to your agents

This creates a starter template you can modify.

4. **Deploy to Azure:**

```bash
azd deploy
```

5. **Run the agents and test locally:**

```bash
# Start the agent runtime locally
azd ai agent run

# In another terminal, invoke an agent to test it
azd ai agent invoke --local "Your request here"
```

### Viewing traces and executions in Foundry

Once your agents are running, the Foundry portal has **three separate places** to see what they're doing. Each has its own requirement — if you miss one, that view stays empty even though the data exists:

| Portal view | Where to find it | What makes it appear |
|---|---|---|
| **Agents** | "Create and debug your agents" → My agents | The agent was created with a model that is deployed in *this* project (check Project → Models + endpoints) |
| **Threads** | Same page → My threads tab | A run that **finished successfully**. Failed runs do NOT show their thread in the portal (it still exists via the API) |
| **Tracing** | Tracing tab in the left navigation | Your code exports OpenTelemetry data to the project's connected Application Insights resource — this is NOT automatic; the run scripts in this repo wire it up (`foundry_tracing.py`) |

Practical tips (learned the hard way):

- **Nothing showing?** Click **Refresh**, and click the **Filter** button and clear any agent/date filters. New data can take 30–60 seconds to appear.
- **A thread is "missing"?** If the run failed, the portal hides the thread. The API is the source of truth — the repo's `dump_conversations.py` writes every thread to readable markdown files.
- **Tracing tab empty?** The project needs an Application Insights connection (Project Settings → Connections). The benchmark scripts print `[trace] tracing enabled -> ...` at startup when tracing is correctly wired.
- Each trace shows every message sent and received, every model call, and (in this repo's runs) whether the runtime monitor accepted or rejected each message.

For the exact code that wires each of these up, see `reference/FOUNDRY_VISIBILITY.md`.

### Key files in a hosted agent project

- `app.py` — the entry point; defines which hosted agent handles requests
- `config.json` — configuration for your agents (roles, tools, etc.)
- `prompts/` — system prompts for each agent

---

## 6. The execution plane — how STJP optimizes token usage

STJP includes a **scheduler** that uses the protocol to decide who should act next. Instead of asking every agent "is it your turn?" each round, the scheduler knows from the protocol exactly which agent should move next, and only asks that one.

This cuts token usage dramatically because:
- You're not polling idle agents
- You send smaller prompts ("it's your turn now, here's what you need to do")
- Fewer wasted back-and-forth clarifications

The scheduler is an **EFSM** (Extended Finite-State Machine)—a simple state machine that walks through the protocol one step at a time.

---

## 7. STJP's latest plan (version 3)

Versions 1 and 2 proved that STJP makes agent coordination **correct**. Version 3 (the current plan, drafted 2026-06-17) plugs that same verified contract into two ecosystems instead of running it only in our own test harness:

### Plane A — Governance ("is this allowed, and prove it for audit")

STJP becomes a **policy generator**: it takes a verified protocol and automatically writes out a policy document that governance tools (like the Microsoft Agent Governance Toolkit) can enforce. Every rule in the policy comes from the protocol:

- Each allowed step in the protocol → an "allow" rule
- Each value condition (refinement or choice guard) → a rule condition
- Everything else → "deny" by default (fail closed)

**Status: built and verified.** The finance case exports 30 rules; the banking case exports 44. A benchmark run now also produces a **compliance audit trail** — every message logged with an allow/deny decision and which rule matched — not just a benchmark log. This is the enterprise story: the same protocol that keeps agents safe also produces the evidence auditors ask for.

### Plane B — Decentralized execution ("run it fast without a central boss, safely")

Instead of a central orchestrator asking every agent "is it your turn?" each round, the protocol's own state machine says exactly which agents are able to act at any moment. The runtime only asks those agents.

**Status: built and measured.** This is the scheduler described in section 6, wired to real Azure agents on 2026-07-02. Results: same 100% completion and zero disasters, at −65% tokens and −66% agent calls versus the identical prompts on the ask-everyone runtime.

The one-line summary of v3: **one verified contract drives everything** — the per-agent prompt, the runtime guard, the scheduler, and the compliance policy.

Full details: `reference/STJP_V3_PLAN.md`.

---

## 8. What to read next

- **To understand how STJP is tested:** Read `2_TESTING_STRATEGIES.md`
- **To understand how benchmarks measure STJP:** Read `3_BENCHMARK_DESIGN_EXPLAINED.md`
- **To create your own protocols:** Read `4_HOW_TO_CREATE_USE_CASES.md`
- **To see real results:** Read `5_RUN_REPORTS_EXPLAINED.md`
- **To see why safety matters:** Read `6_USE_CASE_DEADLOCK_SAFETY.md`
