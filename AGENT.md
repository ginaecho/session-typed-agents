# AGENT.md — Guidance for AI Agents

This file is for Claude and other AI agents working on the STJP codebase. It explains the project, where things live, common tasks, and the guidelines.

---

## 🎯 What This Project Does

**STJP** (Session-Typed Judge Panel) is a compiler that makes multi-agent systems safe and efficient.

**Problem:** Agents fail in the spaces between them—deadlocks, unauthorized actions, wasted tokens on coordination debates.

**Solution:** 
1. Take a natural-language task intent
2. LLM drafts a global protocol (who sends what to whom, in what order)
3. Scribble (static checker) rejects unsafe drafts (deadlocks, inconsistencies)
4. Project into one **per-agent contract** (only your role's part)
5. Compile with runtime monitor and EFSM-based scheduler
6. Result: agents never deadlock, never go off-protocol, use fewer tokens

**The claim:** This makes agents safer AND cheaper than intent-only or global-protocol-as-text.

---

## 📁 Key Files & Directories

### Core library (`stjp_core/`)

| File | Purpose |
|---|---|
| `compiler/` | Scribble integration, protocol parsing, EFSM projection |
| `monitor/` | Runtime monitor (checks each message against the protocol) |
| `foundry/` | Azure AI Foundry integration (agents, threads, traces) |
| `generation/` | Skill/prompt generation from protocols |
| `requirements-core.txt` | Dependencies |
| `CLAUDE.md` | Setup instructions (Azure config) |

### Experiments & benchmark (`experiments/`)

| File | Purpose |
|---|---|
| `cases/` | Each subdirectory is a use case (finance, banking, trade_deadlock) |
| `cases/<case>/case.yaml` | Task definition (roles, intent, goals, protocol path) |
| `cases/<case>/protocols/v1.scr` | Canonical Scribble protocol |
| `cases/<case>/protocols/v1.refn` | Value-level refinement guards (sidecar to .scr) |
| `cases/<case>/protocols/llm_drafts/valid/` | LLM-drafted protocol that Scribble accepts |
| `cases/<case>/protocols/llm_drafts/unsafe/` | LLM-drafted protocol Scribble rejects (for testing) |
| `cases/<case>/runs/` | Benchmark results (events, summaries, prompts) |
| `baselines/` | The 7 arms (runners for each variant) |
| `baselines/registry.py` | ARM DEFINITIONS — where to register new arms (4 places) |
| `baselines/instructions.py` | Prompt builders for each arm |
| `scripts/case_runner.py` | **THE** benchmark driver—run this to test |
| `scripts/case_loader.py` | Loads case.yaml into a Case object |
| `CLAUDE.md` | How the 8-arm matrix works (agents: read this!) |

### Documentation (`docs/`)

| File | Purpose |
|---|---|
| `README.md` | Start here—documentation index with role-based paths |
| `1_TECH_SETUP.md` | What is Scribble, how STJP works, glossary |
| `2_TESTING_STRATEGIES.md` | How we benchmark STJP fairly; the 4 claims |
| `3_BENCHMARK_DESIGN_EXPLAINED.md` | Metrics: GCR, CGC, cost-to-goal, severity grading |
| `4_HOW_TO_CREATE_USE_CASES.md` | Step-by-step: create protocol, agents, test |
| `5_RUN_REPORTS_EXPLAINED.md` | How to read results; 2026-07-02 run explained |
| `6_USE_CASE_DEADLOCK_SAFETY.md` | Why safety matters—concrete examples |
| `reference/` | Current technical deep-dives: `GLOSSARY.md` (canonical), `SCRIBBLE_EXTENSIONS.md`, `CHOICE_GUARDS_AND_GATE.md`, `FOUNDRY_VISIBILITY.md`, `GAP_CLOSED.md`, `PROTOCOL_EVOLUTION.md`, `STJP_V3_PLAN.md` |
| `results/` | Current evidence: `RESULT_1_DEADLOCK.md`, `RESULT_2_TOKEN_EFFICIENCY.md`, `RESULT_3_PROTOCOL_LADDER.md`, `RESULT_4_FULL_STACK.md` (latest official result) |
| `archive/` | Historical/superseded docs (reference only; nothing current) |

### Configuration & meta

| File | Purpose |
|---|---|
| `README.md` | Quick start for humans (how to run experiments) |
| `ROADMAP.md` | Future phases (static verification, refinement discharge) |
| `SCRIBBLE.md` | How Scribble integrates (no fork, only layers) |
| `RESEARCH.md` | Bibliography and related work |
| `MPST_STATIC.md` | Multiparty Session Types (theoretical foundation) |

---

## 🧠 Understanding the 7-Arm Matrix

When you run a benchmark, it tests 7 different "arms" (variants):

| Arm | What agents get | Enforcement | Scheduler |
|---|---|---|---|
| **bare** | No protocol, just intent | None | None |
| **global_text** | Whole protocol pasted as text | None | None |
| **local_verbose** | Per-agent contract (long) | Monitor only | None |
| **local_lean** | Per-agent contract (short) | Monitor only | None |
| **local_lean_gate** | Per-agent contract + enforcer | Gate (blocks wrong messages) | None |
| **local_lean_sched** | Per-agent contract + gate + scheduler | Gate | EFSM scheduler (only ask agents who can act) |

**Key insights:**
- Bare = baseline (should fail or waste tokens)
- Global text = "give them the spec as a string"
- Local variants = "give them their role's slice + guards"
- The scheduler = "we know from the protocol who must act next—don't ask idle agents"

The results show: `local_lean_sched` is safest, cheapest, fastest.

---

## 🔧 Common Agent Tasks

### 1. Adding a new use case

**Task:** Create a new benchmark case for a different domain (e.g., supply chain, healthcare).

**What to do:**
1. Read [`docs/4_HOW_TO_CREATE_USE_CASES.md`](docs/4_HOW_TO_CREATE_USE_CASES.md)
2. Create `experiments/cases/my_domain/`
3. Write `case.yaml` (roles, intent, goals)
4. Write `protocols/v1.scr` in Scribble syntax
5. Optionally add `protocols/v1.refn` (value guards)
6. Test: `python experiments/scripts/case_runner.py my_domain 3 --arms bare,min_llmvalid_sched`

**Files to touch:**
- `experiments/cases/my_domain/case.yaml` (create)
- `experiments/cases/my_domain/protocols/v1.scr` (create)

**Do NOT touch:**
- `experiments/baselines/registry.py` (only touch if adding a new arm)
- `stjp_core/` (unless there's a bug)

**Verification:**
```bash
# Scribble should accept it (no deadlocks, projectable)
# The benchmark should complete
# Check results: cases/my_domain/runs/LATEST/summary.json
```

### 2. Fixing a broken protocol

**Task:** A protocol doesn't validate (Scribble rejects it).

**What to do:**
1. Read the Scribble error message (usually mentions deadlock or wait-for cycle)
2. Look at [`docs/6_USE_CASE_DEADLOCK_SAFETY.md`](docs/6_USE_CASE_DEADLOCK_SAFETY.md) for examples
3. Identify what's wrong:
   - **Circular dependency?** Reorder messages so one role can start
   - **Missing message?** Add it to both branches of a choice
   - **Unreachable state?** Simplify the protocol
4. Edit `protocols/v1.scr` and re-test

**Example fix:** If Agent A waits for Agent B and Agent B waits for Agent A:
- **Problem:** Deadlock
- **Fix:** Have Agent A send first (no wait)

### 3. Adding a new arm (a new variant to test)

**Task:** Test a new idea—e.g., "what if we add a confidence score to the gate?"

**What to do:**
1. Read `experiments/CLAUDE.md` section "The 8 arms, mechanically"
2. Add to `experiments/baselines/registry.py` (SCENARIOS dict) with a new key and factory
3. Add a new builder in `experiments/baselines/instructions.py` (e.g., `build_my_new_variant`)
4. Register in `case_runner.py` under `_FOUNDRY_INSTALL_KEYS` and `FOUNDRY_KEYS`
5. Register in `evaluate_run.py` under `VOCABULARY_ARMS`
6. Test: `python experiments/scripts/case_runner.py finance 1 --arms my_new_arm`

**Key rule:** The `_role_prompts` dict must be populated during `setup()` so prompts are persisted.

### 4. Debugging a failing trial

**Task:** One trial failed; you need to see what went wrong.

**What to do:**
1. Locate the events file: `experiments/cases/<case>/runs/LATEST/events_<arm>.jsonl`
2. View the trace:
   ```bash
   tail -100 events_<arm>.jsonl | jq '.'
   ```
3. Look for:
   - `"violation": {...}` — message violated protocol
   - `"attempt_end"` with `all_goals_pass < goal_total` — goal missed
   - Timestamp gaps — suggests agent got stuck
4. Check the prompts:
   ```bash
   cat runs/LATEST/prompts/<arm>/<Role>.system.md
   ```
5. Check the agent's conversation log (in Foundry portal if using real agents)

**Key fields in events.jsonl:**
- `step` — message order
- `sender`, `receiver`, `label` — who said what
- `violation` — if not null, protocol was broken
- `goals_pass` — running count of satisfied goals

### 5. Re-running a case with different parameters

**Task:** The last run had n=10 trials; you want n=50 to get more stable numbers.

**What to do:**
```bash
cd experiments
python scripts/case_runner.py finance 50 --arms min_llmvalid_sched
```

**Advanced:**
```bash
# Run specific arms only
python scripts/case_runner.py finance 20 \
  --arms bare,min_llmvalid_gate,min_llmvalid_sched

# Add semantic evaluation (LLM judge)
python scripts/case_runner.py finance 10 --semantic

# Run with debug logging
python scripts/case_runner.py finance 5 --debug
```

---

## 📋 Code Guidelines

### 1. Protocol files (Scribble)

**Do:**
- Use clear, descriptive role names and message labels
- Add comments explaining branching logic
- Keep protocols under 50 lines (split into compositions if bigger)
- Ensure every role reaches a terminal state

**Don't:**
- Use circular dependencies (leads to deadlock)
- Make roles unreachable (e.g., `choice at A { skip A }`)
- Assume a role reads from a non-existent peer

**Example:**
```scribble
module finance.Finance;

global protocol Finance(role Fetcher, role Validator, role Reporter) {
    fetch(Double) from Fetcher to Validator;
    
    choice at Validator {
        validate_ok(Double) from Validator to Reporter;
        or {
            reject(String) from Validator to Fetcher;
            retry_fetch(Double) from Fetcher to Validator;
        }
    }
    
    report(String) from Reporter to Fetcher;
}
```

### 2. Refinement files (.refn)

**Do:**
- Use clear predicates (e.g., `x > 50000.0`, not `big(x)`)
- Add one guard per message type
- Test predicates with realistic values

**Don't:**
- Use undefined variables (only `x` is available)
- Call functions that aren't in the allowed list
- Leave commented-out predicates

**Example:**
```ini
[Validator -> Reporter : validate_ok]
type: float
require: x > 50000.0

[Fetcher -> Validator : fetch]
type: float
require: x > 0
```

### 3. case.yaml files

**Do:**
- Use clear, jargon-free role descriptions
- Write 2–3 example goals per case
- Set `terminal_label` to the final message label
- Set `max_steps` to 1.5× expected length

**Don't:**
- Leave role descriptions blank
- Use vague goal predicates like `"pass" in output`
- Set `max_steps` too low (agents get cut off) or too high (wastes time)

**Example:**
```yaml
case_id: finance
description: Quarterly revenue report with conditional audit
version: v1
protocol_name: QuarterlyReport
roles:
  - Fetcher
  - Validator
  - Reporter
terminal_label: report_delivered
max_steps: 15
role_descriptions:
  Fetcher: Retrieves the raw revenue number
  Validator: Checks if number is realistic; high values trigger audit
  Reporter: Compiles and delivers the final report
intent: |
  You are a finance team. Fetch quarterly revenue, validate it,
  audit if > $50k, then report to stakeholders.
goals:
  - id: G1
    description: Revenue number must be realistic
    anchor: {sender: Fetcher, receiver: Validator, label: fetch}
    predicate: float(x) > 0
```

### 4. Python code

**Do:**
- Follow PEP 8 (readable variable names, functions under 30 lines)
- Add docstrings to new functions
- Log at key points (protocol validation, agent creation)
- Handle Azure errors gracefully

**Don't:**
- Hardcode paths (use config files or env vars)
- Add features beyond the task scope
- Skip error handling for "it shouldn't happen"
- Modify monitor.py without re-testing all cases

**Example:**
```python
def load_case(case_id: str) -> Case:
    """Load case config from case.yaml."""
    case_path = Path(f"experiments/cases/{case_id}/case.yaml")
    if not case_path.exists():
        raise FileNotFoundError(f"Case not found: {case_path}")
    
    with open(case_path) as f:
        config = yaml.safe_load(f)
    
    return Case(**config)
```

---

## 🧪 Testing Your Changes

### Before committing:

1. **Protocol validation:**
   ```bash
   python -c "from stjp_core.compiler.validator import ScribbleValidator; \
              v = ScribbleValidator(); \
              v.validate_protocol('experiments/cases/my_case/protocols/v1.scr')"
   ```

2. **Run a quick benchmark:**
   ```bash
   cd experiments
   python scripts/case_runner.py my_case 1 --arms bare,min_llmvalid_sched
   ```

3. **Check output files exist:**
   ```bash
   ls -la cases/my_case/runs/LATEST/
   # Should have: events_bare.jsonl, events_min_llmvalid_sched.jsonl, summary.json
   ```

4. **Verify results make sense:**
   ```bash
   cat cases/my_case/runs/LATEST/summary.json | jq '.[] | {arm, success_rate_pct, cost_to_goal}'
   ```

---

## 🚫 Common Mistakes (Don't Repeat)

| Mistake | Impact | Fix |
|---|---|---|
| Circular protocol (A waits for B, B waits for A) | Deadlock; 0% success | Reorder so one role starts without waiting |
| Missing message in a branch | Agents get stuck | Add message to all branches |
| Too-strict refinement | Agents fail validation | Loosen predicate (e.g., `x > 0` not `x == 50000`) |
| Hardcoded paths in code | Breaks for other users | Use `Path()` and config files |
| Forgetting to populate `_role_prompts` in a new runner | Prompts not saved | Check `BaselineRunner.prompts()` returns dict |
| Modifying monitor without re-running all cases | Silent regressions | Always re-run `finance 3` after any monitor change |
| Assuming `.scr` files are authoritative in skills | Skills drift | Always re-generate from current `.scr` and `case.yaml` |

---

## 📖 Understanding the Codebase

### Architecture diagram

```
Natural language intent (case.yaml)
        ↓
LLM drafts protocol → Scribble validates → EFSM projection
        ↓                                        ↓
Refinement guards ←─────────────────── Per-agent contracts
        ↓
Instruction builders (4 variants)
        ↓
Azure AI Foundry agents (real agents)
        ↓
Runtime monitor (checks each message)
        ↓
EFSM scheduler (decides who acts next)
        ↓
Events log (.jsonl) → Post-run graders
```

### Key abstractions

- **Case** — a use case (defined by `case.yaml`)
- **Arm** — a variant (bare vs with protocol vs with gate)
- **Trial** — one run of a case through one arm
- **Run** — n trials of one or more arms
- **BaselineRunner** — abstract class for "a way to run an arm"
- **FoundryRunner** — runs agents via Azure AI Foundry
- **SessionMonitor** — checks messages against the protocol

---

## 🔗 Key Imports (for coding)

```python
# Loading cases
from experiments.scripts.case_loader import load_case

# Running benchmarks
from experiments.scripts.case_runner import run_scenario

# Compiling protocols
from stjp_core.compiler.validator import ScribbleValidator
from stjp_core.compiler.efsm_parser import get_all_efsms

# Monitoring
from stjp_core.monitor.monitor import SessionMonitor

# Azure integration
from stjp_core.foundry.session_helpers import build_view
from stjp_core.foundry.foundry_runner import FoundryRunner
```

---

## 📊 What "Success" Looks Like

After you implement a task, check:

1. **For a new use case:**
   - Protocol validates (Scribble accepts it)
   - Benchmark completes (no crashes)
   - Results make sense (bare < protocol arms)
   - Prompts are persisted (check `runs/*/prompts/`)

2. **For a bugfix:**
   - Old tests still pass
   - New tests pass
   - No regressions in other cases

3. **For a new arm:**
   - Registered in 4 places (registry, case_runner, evaluate_run, instructions)
   - Results differ meaningfully from existing arms
   - Prompts captured

---

## 🎯 Where to Ask Questions

Before jumping in, check:

1. **Project README.md** — how to run experiments
2. **docs/README.md** — which doc to read for your role
3. **experiments/CLAUDE.md** — how the 8-arm matrix works
4. **stjp_core/CLAUDE.md** — Azure configuration

If still stuck, look at existing cases (finance, banking) for examples.

---

## 📝 Commit Message Template

When you commit work:

```
<type>: <short description>

<longer explanation if needed>

Files touched:
- experiments/cases/<case>/ (if new case)
- stjp_core/<module>/ (if bug fix)
- etc.

Testing:
- Ran case_runner.py <case> 3 --arms <arms>
- Verified <metric> improved / stayed flat / regressed
```

Examples:
```
feat: add supply_chain use case

New case tests coordination across 5 suppliers.
Protocol has choice logic for inventory levels.

Files: experiments/cases/supply_chain/
Testing: finance 3 baseline still passes; supply_chain 1 succeeds
```

```
fix: monitor now allows concurrent actions on different channels

Was enforcing strict global ordering; now respects MPST theory
(concurrent on different channels is safe).

Files: stjp_core/monitor/monitor.py
Testing: re-ran finance, banking, trade_deadlock (n=3); no regressions
```

---

## 🚀 Next Steps for New Contributors

1. **Read [`docs/README.md`](docs/README.md)** — find your role's path
2. **Run a 1-trial test** — `python experiments/scripts/case_runner.py finance 1 --arms min_llmvalid_sched`
3. **Read one case** — understand `experiments/cases/finance/case.yaml` and `protocols/v1.scr`
4. **Try a small task:**
   - Add a new goal to finance case
   - Create a tiny new case (2 roles, 3 messages)
   - Run and check results
5. **Review existing changes** — look at git log to see past task patterns

---

**Good luck! This codebase is designed to be understood. When in doubt, read the docs or ask the project's author (Gina: gina.tcchen@gmail.com).**
