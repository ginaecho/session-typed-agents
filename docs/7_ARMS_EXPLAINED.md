# The settings ("arms"), drawn out — what each configuration actually is

Every benchmark in this project compares **settings**: configurations that
differ in exactly one thing, so the difference in outcome can be attributed
to that one thing. Older documents call a setting an **"arm"** (a term from
clinical trials: each "arm" of a study gets a different treatment). Same
meaning — this page uses both words so you can read either.

This page follows the team's box-and-arrow arm diagrams: each setting is one
flow line, **left to right = what goes in → who runs it → how the agents
coordinate → what (if anything) enforces the rules.**

---

## The building blocks (read once, then every diagram below makes sense)

| Block | Plain meaning |
|---|---|
| **Intent** | The task description in plain prose: what the team should achieve, who the roles are. No coordination rules. |
| **Global protocol text** | The whole coordination plan (who sends what to whom, in what order) written out — and simply *pasted into every agent's instructions as text*. "Validated" = the Scribble compiler (a program that mathematically checks the plan has no dead ends) accepted it. "Unsafe" = the compiler rejected it. |
| **Human skills** | Job instructions written by a person (or downloaded from a public repo), never passed through the compiler check. |
| **Project to local contracts** | Instead of pasting the whole plan into everyone, a program derives each agent's **own slice** of the plan — only what *it* receives and sends. "Verbose" = the full detailed rendering; "minimal" = one line per step (lighter prompt, same information). |
| **Foundry agent** | An AI agent hosted in Azure AI Foundry (Microsoft's agent-hosting service). |
| **MAF agent / MAF GroupChat** | The same agents run through the Microsoft Agent Framework; "GroupChat" adds an orchestrator — an extra AI call that picks who speaks next ("LLM speaker selection"). |
| **Free coordination** | Nothing enforces anything: agents send whatever they decide, to whomever they decide, and every message is delivered. |
| **Decentralized execution** | No orchestrator: agents act on their own, in rounds. |
| **Runtime gate** | A program (not an AI) that checks each outgoing message against the plan and **blocks a wrong message before delivery**, asking the agent to retry. |
| **EFSM scheduler** | A program that follows the plan as a step-by-step state machine (EFSM = "extended finite state machine", i.e., a flowchart a program can execute) and **only wakes an agent whose turn it can actually be** — idle agents are never asked, so they never bill tokens for saying "wait". |

---

## Group 1 — no plan at all (the baselines)

These settings show what teams do when given only the task. They differ only
in which runtime hosts the agents, which proves the failures are not one
vendor's bug.

```
(a) bare              Intent ──▶ Foundry agent ──▶ free coordination
(b) maf_native        Intent ──▶ MAF agent     ──▶ free coordination
(c) maf_foundry       Intent ──▶ MAF agent (Foundry chat client) ──▶ free coordination
(d) maf_groupchat     Intent ──▶ MAF GroupChat ──▶ LLM picks next speaker ──▶ free coordination
```

- **(a) bare** — agents get only the task intent, role descriptions and goal.
  No protocol text, no projection, no enforcement. The floor.
- **(b)–(c)** — the same, on the Microsoft Agent Framework runtime (native
  Azure OpenAI access / the Foundry chat client). No protocol guidance.
- **(d) maf_groupchat** — adds an orchestrator that picks who speaks next.
  Still no protocol guidance: the orchestrator is guessing too.

## Group 2 — the plan exists, but only as pasted text

```
(e) maf_groupchat_unsafe    UNSAFE plan text    ──▶ MAF GroupChat ──▶ LLM picks speaker ──▶ free coordination
(f) maf_groupchat_llmvalid  VALIDATED plan text ──▶ MAF GroupChat ──▶ LLM picks speaker ──▶ free coordination
(h) global_decentralized    VALIDATED plan text ──▶ Foundry agent ──▶ decentralized execution
```

- **(e)** — agents receive an AI-drafted plan that the compiler **rejected**
  as unsafe. Mainly observational: it shows "protocol-*like* text" is not
  enough if nobody validated it.
- **(f)** — agents receive an AI-drafted plan the compiler **accepted**. They
  know the whole conversation shape — but there is no per-agent slice and no
  runtime gate; following the plan is on the honor system.
- **(h)** — same validated text, but no orchestrator. This separates the
  effect of "having the text" from the effect of "being orchestrated".

## Group 3 — human-written skills, never checked

```
(g) unchecked_skills   human skills (not compiler-checked) ──▶ Foundry agent ──▶ free coordination
```

- **(g)** — agents are driven by human-written skills/prompts that never went
  through the STJP checker. This measures how much risk remains when prompts
  are handwritten rather than derived from a checked plan. (RESULT_8 and
  RESULT_9 are this setting with *real, downloaded* public skills.)

## Group 4 — each agent gets its own slice of the plan (contracts)

```
(i) spec_llmvalid   validated plan ──▶ project to VERBOSE local contracts ──▶ Foundry agents  (no enforcement)
(j) min_llmvalid    validated plan ──▶ project to MINIMAL local contracts ──▶ Foundry agents  (no enforcement)
```

- **(i)** — every agent gets a projected local contract in a verbose,
  full-detail format. The complete "local type" idea, without enforcement.
- **(j)** — same information, compressed to one line per step. Lighter prompt,
  same class of guidance.

## Group 5 — contracts, now enforced

```
(k) spec_llmvalid_gate   verbose contracts ──▶ Foundry agents ──▶ runtime gate
(l) min_llmvalid_gate    minimal contracts ──▶ Foundry agents ──▶ runtime gate
```

- **(k)** — like (i) plus the gate: an off-plan message is rejected *before
  delivery*. Measures the value of enforcement on top of verbose contracts.
- **(l)** — like (j) plus the gate. Isolates enforcement while keeping the
  prompt minimal.

## Group 6 — the full STJP execution stack

```
(m) min_llmvalid_sched
    validated plan ──▶ project to minimal contracts ──▶ Foundry agents ──▶ runtime gate ──▶ EFSM scheduler
```

- **(m)** — minimal local contracts + enforcement gate + the scheduler that
  only wakes agents whose turn it can be. The strongest "typed execution"
  setting — and, per [RESULT_4](results/RESULT_4_FULL_STACK.md), simultaneously
  the safest and the cheapest.

---

## How to read any results table with this page

Take the ladder top to bottom: (a) proves the problem exists, (e)–(f) prove
text alone isn't the answer, (i)–(j) prove slicing the plan per agent cuts
cost, (k)–(l) prove enforcement closes the honor-system gap, and (m) shows
all three levers together. Whenever a report says "arm X vs arm Y", find the
two flow lines above and look at the **one block that differs** — that block
is what the comparison measures.

---

## Which test cases fit STJP (and how well)

The benchmark's cases (under `experiments/cases/`), with the team's fit
assessment. **Good** = multiparty coordination, branching/loops,
rollback/deadlock risk, or value constraints — the classic STJP strengths.
**Medium** = useful, but mostly linear/simple. (**Low** would mean a flow so
simple STJP is overkill; no current case is rated Low.)

| Case | What it is (short) | STJP fit | Why |
|---|---|---|---|
| `auction` | Sealed-bid multi-bidder auction with winner/outbid logic | Good | Multiparty fan-in and value constraints; good protocol-check target |
| `banking` | Transfer with amount-based approval/rejection branches | Good | Conditional branch safety and exception path are strong STJP use |
| `clinical_enrollment` | Trial enrollment with screening, consent, lab, ethics approvals | Good | Multi-role sequencing with explicit approval dependencies |
| `code_review` | PR review with reviewer quorum and CI gating | Good | Coordination + threshold-style constraints map well to contracts |
| `finance` | Finance report with audit branching | Good | Known sequencing + refinement failure case; excellent benchmark |
| `finance_nested` | Nested 2×2 branching with payload-driven choices | Good | Complex branch structure is exactly where STJP helps most |
| `intel_report` | Multi-source intel fan-in, then review/publish pipeline | Good | Parallel/fan-in ordering pressure benefits from typed sequencing |
| `iterative_polling` | Looping poll-and-log workflow | Medium | Good for recursion behavior; less rich branching complexity |
| `nested_retry` | Loop + nested branching editorial workflow | Good | Strong stress case for loops + nested choices |
| `rag` | Multi-source retrieval + verification loop | Good | Multi-agent loop with correctness checks; strong STJP candidate |
| `report_pipeline` | 6-role linear pipeline for the token-efficiency demo | Medium | Useful for cost/throughput claims; less about safety complexity |
| `report_pipeline_large` | 10-role scaled linear pipeline | Medium | Good for scaling/token tests; lower structural risk than branch-heavy cases |
| `retry_loop` | Worker/manager retry-until-accept loop | Good | Classic loop + decision-branch safety pattern |
| `trade_deadlock` | Intentional circular-wait deadlock demo | Good | Canonical compile-time deadlock-detection showcase |
| `trade_settlement` | Goods-for-payment with hidden circular dependency | Good | Strong deadlock + enforcement comparison case |
| `travel` | All-or-nothing travel booking with rollback | Good | Saga/compensation-style workflow suits protocol enforcement |
| `travel_saga` | 3-supplier booking happy path (rollback planned later) | Medium | Useful now; becomes stronger when the compensation branch is added |
| `doc_pipeline` | Announcement team built from real Anthropic public skills | Good | Real-skills approval-ordering case (see [RESULT_9](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md)) |
| `pr_merge` | Code-change team built from real GitHub Copilot public files | Good | Real-skills merge-gating case (see [RESULT_9](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md)) |
| `skills_safety/*` | 4 teams built from real OpenAI/CrewAI/AutoGen/LangGraph skills | Good | The RESULT_8 real-skills safety benchmark |
