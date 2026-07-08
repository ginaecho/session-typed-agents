# How to Create Use Cases for STJP

A step-by-step guide to building your own benchmark task and running STJP on it.

**Date: 2026-07-03**

---

## 1. What is a use case?

A use case is a **concrete multi-agent task** that demonstrates STJP's value. It should:

- Have multiple agents talking to each other
- Require coordination (so protocol helps)
- Have clear success/failure criteria
- Be runnable in 30 seconds to 2 minutes per trial

Examples:
- **Finance:** Revenue review with conditional audit branching
- **Banking:** Account opening with authorization gates
- **Supply chain:** Order fulfillment with validation steps
- **Trading:** Deadlock-prone trade agreement (agents wait for each other)

---

## 2. Anatomy of a use case

Each use case lives in a directory with four files:

```
use_cases/my_task/
├── protocol.scr           # Global protocol (Scribble format)
├── protocol.refn          # Value conditions (optional)
├── agents/
│   ├── Agent1.py          # LLM-based agent for role Agent1
│   ├── Agent2.py          # LLM-based agent for role Agent2
│   └── ...
└── test_case.py           # Harness to run the benchmark
```

---

## 3. Step 1: Write the protocol (`.scr` file)

Start with a plain English description of the interaction:

> "Agent A fetches data, Agent B validates it. If valid, Agent C processes it; if not, Agent B retries fetching. Once processed, Agent D approves the result before Agent E delivers it."

Then write it in **Scribble format** (`protocol.scr`):

```scribble
module my_task.MyTask;

data type Status { VALID, INVALID }

global protocol MyTask(role Fetcher, role Validator, role Processor, 
                       role Approver, role Deliverer) {
    fetch(String) from Fetcher to Validator;
    
    choice at Validator {
        validate_ok(String) from Validator to Processor;
        rec RETRY {
            retry_fetch(String) from Validator to Fetcher;
            fetch(String) from Fetcher to Validator;
            continue RETRY;
        }
    }
    
    process(String) from Processor to Approver;
    approve(Boolean) from Approver to Deliverer;
    deliver(String) from Deliverer to Fetcher;
}
```

### Scribble syntax basics

- `data type X { A, B, C }` — enumerate possible values
- `message(Type)` — send a message with a payload
- `from Role1 to Role2` — direction
- `choice at Role { ... } or { ... }` — branching (Role decides)
- `rec NAME { ... continue NAME; }` — loop
- `;` — sequence (must happen in order)

### Key rules

- Every role must eventually reach an end state (no hanging agents)
- The protocol must be **projectable** (turn into per-agent contracts)
- No deadlocks (A waits for B while B waits for A)

---

## 4. Step 2: Add refinements (`.refn` file)

Refinements are **value-level conditions**. Add a `protocol.refn` file:

```ini
[Validator -> Processor : validate_ok]
type: str
require: len(x) > 0

[Approver -> Deliverer : approve]
type: bool
require: x == True    # Must be explicitly approved

[Validator -> Fetcher : retry_fetch]
require: "[RETRY]" in x  # Marker indicating retry
```

Format:
- `[Sender -> Receiver : MessageLabel]` — identifies the message
- `type:` — coerce to this type (str, int, float, bool)
- `require:` — predicate on the value `x`

### Allowed predicates

- Comparisons: `x > 100`, `x == "approved"`, `len(x) > 0`
- Patterns: `matches(r"^[A-Z]+$", x)`, `startswith("VALID", x)`
- Boolean: `and`, `or`, `not`
- Functions: `len`, `abs`, `min`, `max`, `int`, `float`, `str`

---

## 5. Step 3: Implement the agents

Each agent is a Python class that implements one role in the protocol.

Create `agents/FetcherAgent.py`:

```python
import os
from anthropic import Anthropic

class FetcherAgent:
    def __init__(self, role_name: str, model: str = "gpt-5.4"):
        self.role_name = role_name
        self.model = model
        self.client = Anthropic()
        self.messages = []
    
    def act(self, instruction: str, context: dict = None) -> str:
        """
        Execute this agent's turn.
        
        Args:
            instruction: What this agent should do (from the protocol)
            context: Received messages so far
        
        Returns:
            The message to send (or decision made)
        """
        prompt = f"""You are {self.role_name} in a multi-agent task.

Protocol instruction: {instruction}

Context so far:
{self._format_context(context or {})}

Your turn. Respond naturally and follow the protocol."""
        
        self.messages.append({"role": "user", "content": prompt})
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=self.messages
        )
        
        reply = response.content[0].text
        self.messages.append({"role": "assistant", "content": reply})
        
        return reply
    
    def _format_context(self, context: dict) -> str:
        """Format received messages for the agent to read."""
        lines = []
        for role, msg in context.items():
            lines.append(f"{role}: {msg}")
        return "\n".join(lines)
```

### Key points

- Each agent gets a **system role** (it doesn't see the whole protocol, just its part)
- Agents receive **context** (messages from other agents)
- Return the agent's next move as a string

---

## 6. Step 4: Write the test harness

Create `test_case.py` to run the benchmark:

```python
import sys
sys.path.insert(0, "/path/to/STJP")

from stjp_core.runner import FoundryRunner
from stjp_core.monitor import SessionMonitor
from agents.FetcherAgent import FetcherAgent
from agents.ValidatorAgent import ValidatorAgent
# ... import all agents

def run_trial(use_protocol: bool = True, use_gate: bool = False):
    """Run one trial of the use case."""
    
    agents = {
        "Fetcher": FetcherAgent("Fetcher"),
        "Validator": ValidatorAgent("Validator"),
        "Processor": ProcessorAgent("Processor"),
        "Approver": ApproverAgent("Approver"),
        "Deliverer": DelivererAgent("Deliverer"),
    }
    
    runner = FoundryRunner(
        protocol_file="protocol.scr",
        refinement_file="protocol.refn" if use_protocol else None,
        agents=agents,
        gate=use_gate,  # Enforce violations if True
        model="gpt-5.4",
    )
    
    result = runner.run()
    
    return {
        "success": result.goal_complete,
        "tokens": result.total_tokens,
        "disasters": result.disaster_count,
        "violations": result.violations,
        "time_seconds": result.wall_time,
    }

if __name__ == "__main__":
    # Run 10 trials per arm
    n_trials = 10
    
    for arm_name, use_protocol, use_gate in [
        ("Intent only", False, False),
        ("Protocol", True, False),
        ("Protocol + Gate", True, True),
    ]:
        print(f"\n{arm_name}:")
        successes = 0
        total_tokens = 0
        
        for trial in range(n_trials):
            result = run_trial(use_protocol, use_gate)
            successes += result["success"]
            total_tokens += result["tokens"]
            
            print(f"  Trial {trial+1}: {'✓' if result['success'] else '✗'} "
                  f"({result['tokens']} tokens)")
        
        print(f"  GCR: {100*successes/n_trials}%")
        print(f"  Cost-to-goal: {total_tokens/n_trials:.0f} tokens/trial")
```

---

## 7. Step 5: Define success criteria

The harness needs to know what "success" means. Add a `goals.yaml`:

```yaml
task: "MyTask"
success_criteria:
  - type: "message_sent"
    from: "Deliverer"
    to: "Fetcher"
    label: "deliver"
    required: true
  
  - type: "critical_property"
    property: "C3_Authorization"
    description: "Approve message must come before deliver"
    required: true
  
  - type: "no_disaster"
    description: "No irreversible actions without approval"
    severity: "S4"
    required: true
```

---

## 8. Step 6: Run and analyze

```bash
# Run the benchmark
cd use_cases/my_task
python test_case.py

# Run with monitoring enabled (see all messages)
python test_case.py --monitor

# Run with enforcement gate (block violations)
python test_case.py --gate

# View traces in Azure AI Foundry
# (deployed agents will appear in the Foundry portal under "Traces")
```

### Output to expect

```
Intent only:
  Trial 1: ✗ (71300 tokens)
  Trial 2: ✗ (68900 tokens)
  ...
  Trial 10: ✗ (72100 tokens)
  GCR: 0%
  Cost-to-goal: ∞ tokens/trial

Protocol:
  Trial 1: ✓ (82000 tokens)
  Trial 2: ✓ (85300 tokens)
  ...
  Trial 10: ✓ (80900 tokens)
  GCR: 100%
  Cost-to-goal: 82,540 tokens/trial

Protocol + Gate:
  Trial 1: ✓ (39200 tokens)
  Trial 2: ✓ (38900 tokens)
  ...
  Trial 10: ✓ (39100 tokens)
  GCR: 100%
  Cost-to-goal: 39,100 tokens/trial
```

---

## 9. Use case design patterns

### Pattern 1: Deadlock-prone (tests Claim D)

**Design:** Create a circular dependency hidden in plausible local rules.

```scribble
choice at A {
    proceed_B() from A to B;
}

choice at B {
    proceed_A() from B to A;
}
```

Agent A says "I'll proceed once B tells me it's ready."  
Agent B says "I'll proceed once A tells me it's ready."  
Result: Deadlock. Unchecked specs deadlock ~30% of the time; Scribble catches 100%.

**Task:** Let an LLM author per-agent specs from intent and count how many deadlock.

### Pattern 2: Coordination-heavy (tests Claim T/W)

**Design:** A long pipeline where everyone can finish, just inefficiently.

```scribble
R1 -> R2: msg1
R2 -> R3: msg2
R3 -> R4: msg3
R4 -> R5: msg4
R5 -> R6: msg5
R6 -> R1: done
```

**Task:** Everyone finishes. Measure tokens/time. Protocol saves by eliminating polling/deliberation.

### Pattern 3: Safety-critical (tests Claim I)

**Design:** An irreversible action that needs authorization.

```scribble
choice at Auditor {
    approve() from Auditor to FilingAgent;
}
FilingAgent -> Database: file_report(data)
```

Authorization must come before filing. Unchecked agents violate this ~20% of the time.

**Task:** Measure disaster rate. Protocol prevents disasters by enforcing order.

### Pattern 4: Many roles (tests Claim T at scale)

**Design:** 15–20 roles with deep nesting.

**Task:** Measure how per-agent contract size grows vs global protocol size.

---

## 10. Checklist: Before running a benchmark

- [ ] Protocol is well-formed (run `scribble protocol.scr` — no errors)
- [ ] Protocol is projectable (no role appears undefined)
- [ ] No deadlocks (Scribble -deadlock check)
- [ ] Agents implemented for each role
- [ ] Success criteria defined and testable
- [ ] One variable per comparison (don't change runtime AND spec in same arm)
- [ ] n ≥ 10 trials per arm
- [ ] Report model name
- [ ] Define the task in plain English (what is the user asking agents to do?)
- [ ] State the control (what is held constant across arms?)

---

## 11. Real example: Finance case

File structure:
```
use_cases/finance/
├── protocol.scr
├── protocol.refn
├── agents/
│   ├── FetcherAgent.py
│   ├── ValidatorAgent.py
│   ├── TaxSpecialistAgent.py
│   ├── AuditorAgent.py
│   ├── TaxLawyerAgent.py
│   ├── RevenueReporterAgent.py
│   └── FilingAgentAgent.py
└── test_case.py
```

Run: `python test_case.py`

Result: 13.3k tokens with protocol + gate + scheduler vs 120.3k with global text (9× cheaper).

---

## 12. What to read next

- **To understand the testing framework:** Read `2_TESTING_STRATEGIES.md`
- **To understand benchmark metrics:** Read `3_BENCHMARK_DESIGN_EXPLAINED.md`
- **To see real results:** Read `6_RUN_REPORTS_EXPLAINED.md`
