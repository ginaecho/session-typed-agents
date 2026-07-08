# Use Cases: Why Interaction Safety Matters

Concrete examples where protocols catch real problems that would crash unreliable systems.

**Date: 2026-07-03**

> Two acronyms appear near the end of this file: **SLA** = Service Level
> Agreement (a contractual promise about uptime or response time) and **QoS** =
> Quality of Service (how responsive and reliable the system feels in practice).

---

## 1. The deadlock nightmare: Trade execution

### The scenario

A brokerage has two agents:

- **DeskAgent:** Trader requests a trade
- **ExecutorAgent:** Clears and executes the trade

Naturally, someone writes the protocol like this:

```scribble
global protocol Trade(role Desk, role Executor) {
    trade_request(Order) from Desk to Executor;
    confirmation(OrderID) from Executor to Desk;
}
```

That looks fine. But here's what each agent is told (their local instructions):

**Desk's part:** "Wait for ExecutorAgent to say it's ready before sending the trade request."

**Executor's part:** "Wait for DeskAgent to send the trade request before confirming you're ready."

### The deadlock

```
Desk: "I'll send the trade, but first... is Executor ready?"
      [waits for Executor's signal]

Executor: "I'll confirm, but first... do I have the trade request?"
          [waits for Desk's request]

Both agents wait forever. Neither sends anything.
```

The agents are stuck in a circular dependency:
- Desk waits for Executor
- Executor waits for Desk

### Without STJP

The developer has to:
1. Run the code and wait for a timeout (could be minutes)
2. Notice that both agents are stuck
3. Dig through logs to figure out why (circular wait)
4. Manually fix the protocol
5. Redeploy and test again

**Cost:** Wasted time, real money, confused users, potentially lost trades.

### With STJP

Scribble analyzes the global protocol:

```
Desk → Executor: trade_request
Executor → Desk: confirmation
```

**Scribble's check:** "Can every agent make progress on this protocol?"

- Does Desk have something to send first? Yes: `trade_request`
- Then Executor has something to send? Yes: `confirmation`
- Any cycles? No.

**Verdict:** Safe. No deadlock.

**Cost:** Zero. Caught before the first line of agent code runs.

---

## 2. Wrong branch, wrong path: Revenue audit failure

### The scenario

A bank's revenue processing pipeline has a rule: **"If revenue exceeds $50,000, you must audit it."**

The protocol says:

```scribble
choice at TaxSpecialist {
    high_revenue(Double) from TaxSpecialist to Auditor;
    low_revenue(Double) from TaxSpecialist to RevenueReporter;
}
```

This gives TaxSpecialist a choice: send to Auditor OR RevenueReporter depending on the amount.

### Without STJP (and how things go wrong)

The developer writes:

```python
class TaxSpecialist:
    def act(self, revenue: float):
        if revenue > 50000:
            # HIGH BRANCH: must audit
            send(Auditor, revenue)
        else:
            # LOW BRANCH: skip audit
            send(RevenueReporter, revenue)
```

This looks correct. But what if:

1. **Wrong threshold:** The agent is trained on web data that talks about "$55,000" as a cutoff, not $50,000. It uses 55,000.
   - Revenue $51,000 → Agent skips audit (DISASTER)

2. **Reversed logic:** A typo flips the comparison.
   - Revenue $30,000 → Agent triggers audit (inefficient)

3. **Floating-point rounding:** Revenue 50000.01 might round to 50000 in some calculations.
   - Revenue $50,000.01 → Agent treats it as low (DISASTER)

4. **Agent confusion:** The LLM agent forgets the rule and makes its own judgment.
   - "I think this $60,000 is probably fine without audit" → DISASTER

### Result without guards

The auditors don't catch it because the report bypassed them. The filed report never gets reviewed. Compliance violation discovered 3 months later in an audit.

---

### With STJP (guards prevent every path)

STJP adds refinements (value guards):

```ini
[TaxSpecialist -> Auditor : high_revenue]
type: float
require: x > 50000.0

[TaxSpecialist -> RevenueReporter : low_revenue]
type: float
require: x <= 50000.0

[choice at TaxSpecialist]
require_high: x > 50000.0
require_low: x <= 50000.0
```

Now:

1. **At code generation time:** STJP inserts a guard into the agent's send method:
   ```python
   def send_Auditor_high_revenue(self, revenue: float):
       assert revenue > 50000.0, f"Invariant violated: {revenue} must be > 50000"
       # Now send it
   ```

2. **At runtime:** If the agent tries to send 51,000 to RevenueReporter (wrong branch):
   ```
   Agent: "I'll send $51,000 as low_revenue"
   Guard: "ERROR: 51,000 is not <= 50,000. That violates the choice rule."
   Agent: "OK, I'll reconsider. Let me check again... I should audit this."
   Agent: "Sending $51,000 as high_revenue"
   Guard: "Accepted."
   ```

3. **In the monitor:** Even if the guard didn't catch it, the monitor re-checks:
   ```
   Monitor: "Low-revenue message of $60,000? That's impossible. This violates the protocol."
   Recorded: [CHOICE_GUARD_VIOLATION]
   ```

### Result with guards

All three failure modes are caught:
- **Wrong threshold?** Guard rejects (agent reconsiders)
- **Reversed logic?** Guard blocks (agent has to fix)
- **Rounding error?** Guard catches (agent can re-check)
- **Agent confusion?** Guard + monitor prevent it from being sent

**Cost:** Zero regulatory risk. Compliance by construction.

---

## 3. Authorization bypass: "We approve after filing"

### The scenario

A loan application system has two agents:

- **FilingAgent:** Files the application for processing
- **ApprovalAgent:** Reviews and approves

The process must be: **Approval → Filing**  (get sign-off, then file).

### Without STJP

The developer hastily implements it backwards: **Filing → Approval** (file first, then get approval).

```python
# WRONG ORDER
filing_agent.file_application(app)
approval_agent.review_and_approve(app)
```

Or the protocol is correct but the agent's local understanding is wrong:

```python
# Agent thinks: "I'll file immediately, then ask for approval"
# This is irreversible — the application is already in the system
```

### The disaster

A loan worth $500,000 is filed without approval. Hours later, an approver realizes the applicant is insolvent. The filing can't be undone; it's now in the state system. Regulatory violation. Lawsuits.

### With STJP (enforcement gate)

The protocol specifies:

```scribble
approve(Boolean) from ApprovalAgent to FilingAgent;
file(LoanApplication) from FilingAgent to LoanSystem;
```

**Critical property C3:** The protocol **proves** that the `approve` message must arrive before `file`.

At runtime, the enforcement gate watches:

```
FilingAgent: "I'll send file(app)"
Gate: "Wait. You haven't received approval yet. State machine says you must wait."
FilingAgent: "Oh right, let me wait for approval first."
Gate: [blocks the message]

ApprovalAgent: "I approve this"
Gate: "Message accepted. Approval recorded."

FilingAgent: "Now I'll file"
Gate: "Approved. Filing allowed."
```

### Result

**Zero chance of irreversible action before authorization.** The protocol *proves* the ordering. Agents can't violate it even if they try.

---

## 4. Data provenance failure: "I'll guess"

### The scenario

A compliance agent must report the exact revenue figure from a file. The protocol says:

```scribble
revenue_report(Double) from ComplianceAgent to RegulatorAgent;
```

With refinement:

```ini
[ComplianceAgent -> RegulatorAgent : revenue_report]
type: float
require: x > 0
```

### Without STJP

The compliance agent is given a task: "Report the revenue."

But the agent:
- Doesn't have access to the actual file (due to a misconfigured permission)
- Tries to help anyway
- Says "I estimate the revenue at $2.1M"

The regulator files a report based on an *estimate*, not a real number. Audit later discovers the real number was $1.8M. Compliance violation.

### With STJP

The protocol says: "Revenue must be reported."

But the **critical property C1** (data provenance) is checked:

```
ComplianceAgent: "The revenue is $2.1M"
Monitor: "Where did you get that number?"
ComplianceAgent: "I... I estimated it"
Monitor: "That violates C1 (data provenance). You must report a REAL number from a source."
```

The monitor doesn't let it through. The agent has to:
1. Admit it doesn't have the file
2. Ask for help accessing the real data
3. Report the actual number

**Result:** Compliance by construction. No guesses allowed.

---

## 5. Concurrency confusion: Two agents, two messages

### The scenario

Agents A and B communicate. The protocol has:

```scribble
A -> B: msg1
B -> A: msg2
```

This should be **sequential** (msg1, then msg2). But what if the runtime allows them **concurrently**?

**Without STJP (naive monitor):**

```
Time 1: A sends msg1
Time 2: B sends msg2 (while msg1 is still in flight)
Time 3: A receives msg2
Time 4: A receives msg1

Order received: msg2, msg1
```

A received them in the wrong order! A naive monitor would say "VIOLATION: msg2 before msg1."

But wait — **A and B are different roles**. The protocol allows *different* pairs of roles to interleave. This is legal concurrency.

**Without STJP (rigid enforcement):**

Would lock up because it enforces strict global ordering. Agents can't make progress.

---

### With STJP (theory-faithful monitor)

STJP's monitor follows **multiparty session types (MPST)** theory, which says:

- **Same channel?** Enforce strict order (A→B, then B→A)
- **Different channels?** Allow any interleaving (C→D and E→F can cross)

The monitor allows:

```
Time 1: A sends msg1 (to B)
Time 2: C sends msg3 (to D)
Time 3: B sends msg2 (to A)
Time 4: D sends msg4 (to C)

Both channels allowed to interleave because they're independent.
```

**Result:** Maximum concurrency with zero safety loss. Agents aren't needlessly blocked.

---

## 6. Why these cases matter in the real world

### Deadlock (trade execution)

- **Who cares:** Financial institutions, real-time trading systems
- **Cost of failure:** Trades don't execute, money sits in accounts, customers angry, SLA violations
- **STJP value:** Static check catches it in development, zero runtime cost

### Wrong branch (audit bypass)

- **Who cares:** Banks, insurance, healthcare, any regulated industry
- **Cost of failure:** Compliance violations, fines, lawsuits, customer data exposed
- **STJP value:** Refinements prevent irreversible actions without authorization

### Authorization bypass (loan filing)

- **Who cares:** Banks, loan processors, any system with approval workflows
- **Cost of failure:** Irreversible action in a bad state, regulatory violation
- **STJP value:** Protocol proves ordering; gate enforces it

### Data provenance (compliance reporting)

- **Who cares:** Auditors, regulators, any system reporting to external parties
- **Cost of failure:** Guessed numbers cause compliance failures, fines
- **STJP value:** Critical properties enforce "real data only"

### Concurrency (scalability)

- **Who cares:** Large multi-agent systems (10+ agents)
- **Cost of failure:** Unnecessary blocking, slow execution, poor QoS
- **STJP value:** Theory-faithful monitor allows maximum safe parallelism

---

## 7. How to design your own safety case

When creating a use case, ask:

1. **What irreversible action exists?** (File, transfer, delete, publish)
2. **What must happen first?** (Authorization, review, audit)
3. **How can an agent get it wrong?** (Forget order, skip step, guess data)
4. **What guard stops it?** (Protocol ordering, refinement, critical property)

### Example: Salary adjustment in HR

**Irreversible action:** Salary change in payroll system

**What must happen first:**
1. Employee submits adjustment request
2. Manager reviews and approves
3. HR verifies budget availability
4. Only then: Payroll applies change

**How it can fail:**
- Payroll applies change before approval (manager never reviews)
- HR checks budget, but payroll gets outdated approval message
- Employee request and manager approval cross in time

**STJP guards:**
- Protocol ordering: Approval → Budget check → Payroll
- Refinement: Approval message must reference the exact request
- Monitor: Only one approval per request

---

## 8. Summary: Why this matters

| Problem | Without STJP | With STJP |
|---|---|---|
| Deadlock | Found after timeout; days to debug | Caught by static check; zero cost |
| Wrong branch | Found by customer report; compliance violation | Prevented by refinement guard |
| Reversed order | File-then-approve disaster | Protocol proves order; gate enforces it |
| Data guessing | Discovered in audit; fines | Critical property prevents guesses |
| Concurrency issues | Overly strict, slow; or too loose, crashes | Theory-faithful, safe and fast |

---

## 9. What to read next

- **To understand testing:** Read `2_TESTING_STRATEGIES.md`
- **To create your own case:** Read `4_HOW_TO_CREATE_USE_CASES.md`
- **To see results:** Read `6_RUN_REPORTS_EXPLAINED.md`
