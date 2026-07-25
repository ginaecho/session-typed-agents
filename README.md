# Session-Typed Judge Panel (STJP) — Quick Start & Running Experiments

**A session-typed static compiler for safe interactions in multi-agent systems.**

Multi-agent systems fail in the spaces *between* agents: one agent acts before authorization, two agents wait forever (deadlock), everyone wastes tokens negotiating coordination. STJP type-checks the **conversation itself** before any agent runs — catching deadlocks, catching unsafe orderings, and compiling safe per-agent prompts with a runtime guard and scheduler.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [📖 Documentation](#-documentation)
- [🚀 Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Setup (5 minutes)](#setup-5-minutes)
  - [Configuration](#configuration)
  - [Protocol checker and extensions are opt-in (safe defaults)](#protocol-checker-and-extensions-are-opt-in-safe-defaults)
- [🧪 Running Experiments](#-running-experiments)
  - [1. Run a single case with one arm (5 minutes)](#1-run-a-single-case-with-one-arm-5-minutes)
  - [2. Compare STJP with baseline (10 minutes)](#2-compare-stjp-with-baseline-10-minutes)
  - [3. Run the full benchmark (1 hour)](#3-run-the-full-benchmark-1-hour)
  - [4. Run a different case](#4-run-a-different-case)
  - [5. Run with custom options](#5-run-with-custom-options)
- [📊 Understanding the Results](#-understanding-the-results)
  - [The summary.json (Set A — Conformance & Cost)](#the-summaryjson-set-a--conformance--cost)
  - [The summary_eval.json (Set B — Goal Achievement)](#the-summary_evaljson-set-b--goal-achievement)
  - [The events file (detailed trace)](#the-events-file-detailed-trace)
- [🆕 Creating a New Use Case](#-creating-a-new-use-case)
- [🔍 Troubleshooting](#-troubleshooting)
  - ["Protocol validation failed"](#protocol-validation-failed)
  - ["Agents are getting stuck"](#agents-are-getting-stuck)
  - ["High token usage"](#high-token-usage)
  - ["Azure authentication failed"](#azure-authentication-failed)
- [📁 Project Structure](#-project-structure)
- [🎯 Key Results (2026-07-02, n=10 finance case, GPT-5.4)](#-key-results-2026-07-02-n10-finance-case-gpt-54)
- [📖 Next Steps](#-next-steps)
- [🤝 Contributing](#-contributing)
- [❓ Questions?](#-questions)
- [📄 License](#-license)
- [📖 Citation](#-citation)
<!-- MENU:END -->

## 📖 Documentation

**Start here:** Read [`docs/README.md`](docs/README.md) for the full documentation index.

**Quick tours:**
- **What is STJP?** → [`docs/1_TECH_SETUP.md`](docs/1_TECH_SETUP.md) (15 min)
- **How do we test it?** → [`docs/2_TESTING_STRATEGIES.md`](docs/2_TESTING_STRATEGIES.md) (20 min)
- **What is each "arm"?** → [`docs/5_ARMS_EXPLAINED.md`](docs/5_ARMS_EXPLAINED.md) (10 min)
- **Latest results** → [`docs/6_RUN_REPORTS_EXPLAINED.md`](docs/6_RUN_REPORTS_EXPLAINED.md) (plain English)
- **Why safety matters** → [`docs/7_USE_CASE_DEADLOCK_SAFETY.md`](docs/7_USE_CASE_DEADLOCK_SAFETY.md) (real examples)
- **Is the benchmark fair?** → [`docs/BENCHMARK_FAIRNESS_REVIEW.md`](docs/BENCHMARK_FAIRNESS_REVIEW.md) (the audit)

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.13**
- **Java 17** (for Scribble compiler)
- **Azure subscription** with Azure AI Foundry access
- **Git**

### Setup (5 minutes)

```bash
# Clone the repo
git clone https://github.com/ginaecho/session-typed-agents
cd session-typed-agents

# Clone Scribble (the static checker)
git clone https://github.com/scribble/scribble-java

# Install Python dependencies
pip install -r stjp_core/requirements-core.txt

# Configure Azure
az login
# Create .env file (see "Configuration" section below)
```

### Configuration

Create `stjp_core/.env`:

```
AZURE_TENANT_ID=<your-tenant-id>
AZURE_SUBSCRIPTION_ID=<your-subscription-id>
AZURE_RESOURCE_GROUP=<your-resource-group>
AZURE_PROJECT_NAME=<your-ai-foundry-project>
AZURE_LOCATION=eastus
OPENAI_API_KEY=<your-openai-key>  # optional, for non-Foundry models
```

See `stjp_core/CLAUDE.md` for detailed setup instructions.

### Protocol checker and extensions are opt-in (safe defaults)

If you are running the existing benchmark and cases, **you do not need to
change anything** — the defaults preserve the original behavior. Two
capabilities were added as *optional extensions*, layered beside the old
behavior rather than replacing it:

| capability | default | how to turn it on | effect when off |
|---|---|---|---|
| Protocol checker backend | the original Scribble-Java compiler (`STJP_COMPILER_BACKEND=scribble`) | set env var `STJP_COMPILER_BACKEND=nuscr` (plus `STJP_NUSCR_BIN`) | the newer nuscr checker is never invoked; validation is unchanged |
| Stateful session invariants (the "ledger": running value constraints across a whole conversation, e.g. a budget that must never go negative) | off | add a `__ledger__` entry to a case's refinement (`.refn`) sidecar | `monitor.py` sets `self.ledger = None` and behaves exactly as before; no case without a `__ledger__` entry is affected |

**What this means in practice:** a checkout that does not set
`STJP_COMPILER_BACKEND` and whose cases declare no `__ledger__` entry runs
against the original Scribble checker with the original monitor logic —
identical to before these extensions existed. Existing tests and cases are
unaffected. Turn either extension on deliberately, per run, only when you
want it.

**A worked ledger example** (verified end to end against the real compiler
and monitor on 2026-07-25 — the full account, including the overdraw the
monitor rejected pre-delivery, is in
[`docs/reference/SESSION_RECORD_2026-07-25.md`](docs/reference/SESSION_RECORD_2026-07-25.md)
§8). Three lines in a case's `.refn` sidecar are the whole thing:

```
state searches_left: int = 12
on SearchSpend(cost): searches_left -= cost
invariant searches_left >= 0  @S4
```

Read as: declare a running value; debit it by the `cost` field of every
`SearchSpend` message; never let it go below zero, treating a breach as an
irreversible-resource failure. The middle line is what a per-message rule
cannot express — whether *this* request is the one that overdraws depends on
every request before it. In the verified run, three spends of five against a
budget of twelve left the budget at 2, with exactly one overdraw rejected
*before delivery* (never a committed negative value).

---

## 🧪 Running Experiments

### 1. Run a single case with one arm (5 minutes)

The simplest way to test STJP:

```bash
cd experiments

# Run finance case, 1 trial, with the full STJP stack (min_llmvalid_sched)
python scripts/case_runner.py finance 1 --arms min_llmvalid_sched

# Check results
ls cases/finance/runs/
```

**Output:**
- `events_min_llmvalid_sched.jsonl` — every message, in order
- `summary.json` — metrics (success rate, tokens, violations)
- `prompts/min_llmvalid_sched/` — the exact prompts each agent saw

### 2. Compare STJP with baseline (10 minutes)

Run intent-only vs the full STJP stack on the same case:

```bash
# Run 3 trials each
python scripts/case_runner.py finance 3 \
  --arms bare,min_llmvalid_sched
```

**Output comparison:**

| Metric | bare (intent-only) | min_llmvalid_sched (STJP) |
|---|---|---|
| Success rate | Often 0% | 100% |
| Disasters | Usually many | 0 |
| Tokens/trial | Highly variable | ~13k (optimized) |
| Cost-to-goal | ∞ (fails) | 13k/success |

### 3. Run the full benchmark (1 hour)

This runs all arms on a case with n=10 trials each (the 2026-07-02 official
run of this kind produced `docs/results/RESULT_04_FULL_STACK.md`):

```bash
# Run all arms (this is the official benchmark)
python scripts/case_runner.py finance 10

# View dashboard
python scripts/index_builder.py
open INDEX.html
```

**The arms tested** (15 in the current registry, `experiments/baselines/registry.py`;
each is one configuration being compared — like the treatment and control
groups of a medical trial):

- **bare**, **maf_native**, **maf_foundry**, **maf_groupchat** — intent only, on
  different runtimes (baselines)
- **maf_groupchat_unsafe** — a compiler-REJECTED protocol pasted as text
- **maf_groupchat_llmvalid** — validated protocol text with an LLM orchestrator
- **unchecked_skills** — human-written/downloaded skills, never compiler-checked
- **global_decentralized** — validated protocol text, decentralized
- **spec_llmvalid** / **min_llmvalid** — verbose / minimal per-agent contract
  (observer, no enforcement)
- **spec_llmvalid_gate** / **min_llmvalid_gate** — contract + enforcement gate
- **min_llmvalid_gate_nohint** — gate without the per-turn state hint (isolates
  how much the reminder itself contributes)
- **min_llmvalid_gate_lastrecv** — gate + "ask whoever just received a message"
  turn-taking (a protocol-free stand-in for the scheduler, so the scheduler's
  win can't be credited to mere orderliness)
- **min_llmvalid_sched** — lean contract + gate + EFSM scheduler (full STJP)

Each arm is drawn as a one-line flow diagram in
[`docs/5_ARMS_EXPLAINED.md`](docs/5_ARMS_EXPLAINED.md).

### 4. Run a different case

Every case is a directory under [`experiments/cases/`](experiments/cases/).
The current set:

| Case | One-line description |
|---|---|
| [`agenticpay_settlement`](experiments/cases/agenticpay_settlement/) | Payment settlement demo run on Azure AI Foundry (deadlock vs checked protocol) |
| [`auction`](experiments/cases/auction/) | Sealed-bid multi-bidder auction with winner/outbid logic |
| [`banking`](experiments/cases/banking/) | Transfer with amount-based approval/rejection branches |
| [`clinical_enrollment`](experiments/cases/clinical_enrollment/) | Trial enrollment with screening, consent, lab, ethics approvals |
| [`code_review`](experiments/cases/code_review/) | PR review with reviewer quorum and CI gating |
| [`composition`](experiments/cases/composition/) | Composed sub-protocol examples (audit, banking, pipeline) |
| [`finance`](experiments/cases/finance/) | Quarterly revenue report with conditional audit (the flagship benchmark case) |
| [`finance_nested`](experiments/cases/finance_nested/) | Nested 2×2 branching with payload-driven choices |
| [`intel_report`](experiments/cases/intel_report/) | Multi-source intel fan-in, then review/publish pipeline |
| [`iterative_polling`](experiments/cases/iterative_polling/) | Looping poll-and-log workflow |
| [`nested_retry`](experiments/cases/nested_retry/) | Loop + nested branching editorial workflow |
| [`planner_workers`](experiments/cases/planner_workers/) | Planner fanning work out to worker agents |
| [`rag`](experiments/cases/rag/) | Multi-source retrieval + verification loop |
| [`report_pipeline`](experiments/cases/report_pipeline/) | 6-role linear pipeline (token-efficiency demo) |
| [`report_pipeline_large`](experiments/cases/report_pipeline_large/) | 10-role scaled linear pipeline |
| [`retry_loop`](experiments/cases/retry_loop/) | Worker/manager retry-until-accept loop |
| [`trade_deadlock`](experiments/cases/trade_deadlock/) | Intentional circular-wait deadlock demo |
| [`trade_settlement`](experiments/cases/trade_settlement/) | Goods-for-payment with hidden circular dependency |
| [`travel`](experiments/cases/travel/) | All-or-nothing travel booking with rollback |
| [`travel_saga`](experiments/cases/travel_saga/) | 3-supplier booking happy path |
| [`skills_safety/airline_seat`](experiments/cases/skills_safety/airline_seat/) | Airline customer-service team from a real OpenAI Agents SDK example (wrong-order safety) |
| [`skills_safety/booking_saga`](experiments/cases/skills_safety/booking_saga/) | LangGraph supervisor booking saga (deadlock / saga ordering) |
| [`skills_safety/code_execution`](experiments/cases/skills_safety/code_execution/) | AutoGen write-then-execute code pair (execute-before-review safety) |
| [`skills_safety/content_pipeline`](experiments/cases/skills_safety/content_pipeline/) | CrewAI research/write/edit/publish content team (wrong-order safety) |
| [`skills_safety/doc_pipeline`](experiments/cases/skills_safety/doc_pipeline/) | Announcement team from real Anthropic public skills |
| [`skills_safety/doc_coauthor_ship`](experiments/cases/skills_safety/doc_coauthor_ship/) | Corrected announcement case (looping protocol) |
| [`skills_safety/pr_merge`](experiments/cases/skills_safety/pr_merge/) | Code-change team from real GitHub Copilot public files |
| [`skills_safety/pr_review_merge`](experiments/cases/skills_safety/pr_review_merge/) | Corrected code-review case (looping protocol) |
| [`_corpus`](experiments/cases/_corpus/) | Generated protocol corpus used by the stress/mutation benchmarks |

```bash
# Try the deadlock case (tests claim: "only static check catches deadlock")
python scripts/case_runner.py trade_deadlock 3 --arms bare,min_llmvalid_sched

# This should show:
# - bare: 0% success (agents deadlock forever)
# - min_llmvalid_sched: 100% success (Scribble caught it before running)
```

### 5. Run with custom options

```bash
# Run a subset of arms
python scripts/case_runner.py finance 5 \
  --arms bare,min_llmvalid_gate,min_llmvalid_sched

# Run with semantic goal evaluation (LLM judge for goals)
python scripts/case_runner.py finance 3 --semantic

# Run and log to file
python scripts/case_runner.py finance 5 2>&1 | tee my_run.log

# Run arms one at a time instead of in parallel (--sequential), so wall-clock
# timings are trustworthy: parallel arms compete for the same API quota, so a
# "slow" arm may just have been starved by its neighbors
python scripts/case_runner.py finance 5 --sequential

# See all options
python scripts/case_runner.py --help
```

---

## 📊 Understanding the Results

### The summary.json (Set A — Conformance & Cost)

```json
{
  "case": "finance",
  "arm": "min_llmvalid_sched",
  "n_trials": 10,
  "succeeded": 10,
  "success_rate_pct": 100,
  "viol_events": 0,
  "total_tokens": 133140,
  "total_seconds": 320,
  "tokens_per_trial": 13314,
  "calls_per_trial": 11.4,
  "cost_to_goal": 13314
}
```

**Key metrics:**
- **success_rate_pct** — % of trials that finished correctly (0–100%)
- **viol_events** — how many messages violated the protocol
- **cost_to_goal** — tokens ÷ success rate (the true cost of delivery)

### The summary_eval.json (Set B — Goal Achievement)

```json
{
  "strict_pct": 100,
  "role_pair_pct": 100,
  "strict_per_goal": {
    "G1_high_revenue_above_50k": 100,
    "G2_audit_if_high": 100
  }
}
```

**Key metrics:**
- **strict_pct** — % of trials where all goals achieved (100% = perfect)
- **role_pair_pct** — relaxed version (any message between roles counts)

### The events file (detailed trace)

```bash
# View the message trace
tail -50 cases/finance/runs/LATEST/events_min_llmvalid_sched.jsonl

# Human-readable format
cat cases/finance/runs/LATEST/events_min_llmvalid_sched.jsonl | jq '.[] | "\(.step): \(.sender) -> \(.receiver) [\(.label)] = \(.payload)"'
```

Each line is a message:
```json
{
  "step": 3,
  "sender": "Fetcher",
  "receiver": "TaxSpecialist",
  "label": "HighRevenue",
  "payload": "60000",
  "violation": null
}
```

If `violation` is not null, the protocol was violated:
```json
{
  "violation": {
    "type": "off_protocol",
    "role": "TaxSpecialist",
    "state": "state_5",
    "expected": ["HighRevenue"]
  }
}
```

---

## 🆕 Creating a New Use Case

Follow the step-by-step guide in [`docs/4_HOW_TO_CREATE_USE_CASES.md`](docs/4_HOW_TO_CREATE_USE_CASES.md).

**Quick checklist:**

1. **Create case directory:**
   ```bash
   mkdir -p experiments/cases/my_case/protocols
   ```

2. **Write `case.yaml`:**
   ```yaml
   case_id: my_case
   description: My new protocol
   version: v1
   protocol_name: MyProtocol
   roles: [Agent1, Agent2, Agent3]
   terminal_label: Done
   intent: |
     Your task description here
   goals:
     - id: G1
       description: First goal
       anchor: {sender: Agent1, receiver: Agent2, label: FirstMessage}
   ```

3. **Write protocol (`protocols/v1.scr`):**
   ```scribble
   global protocol MyProtocol(role Agent1, role Agent2, role Agent3) {
       msg1(String) from Agent1 to Agent2;
       msg2(String) from Agent2 to Agent3;
       done(String) from Agent3 to Agent1;
   }
   ```

4. **Add refinements (`protocols/v1.refn`, optional):**
   ```ini
   [Agent1 -> Agent2 : msg1]
   type: str
   require: len(x) > 0
   ```

5. **Test it:**
   ```bash
   python scripts/case_runner.py my_case 3 --arms bare,min_llmvalid_sched
   ```

See [`docs/4_HOW_TO_CREATE_USE_CASES.md`](docs/4_HOW_TO_CREATE_USE_CASES.md) for detailed steps.

---

## 🔍 Troubleshooting

### "Protocol validation failed"

The Scribble compiler found a problem (deadlock, unreachable state, inconsistency).

**Fix:**
1. Read the Scribble error message carefully
2. Check [`docs/7_USE_CASE_DEADLOCK_SAFETY.md`](docs/7_USE_CASE_DEADLOCK_SAFETY.md) for examples
3. Revise your protocol and re-run

### "Agents are getting stuck"

Agents reach a state where nothing can happen next (liveness failure).

**Causes:**
- Missing a required message in the protocol
- Refinement too strict (payloads fail validation)
- Wrong choice logic

**Debug:**
```bash
# View the trace where it got stuck
cat cases/<case>/runs/LATEST/events_<arm>.jsonl | jq '.[] | select(.step > 20)'

# Check the agent's view at that step
tail -100 <run_dir>/<agent>_transcript.log
```

### "High token usage"

If intent-only (bare) uses way more tokens than expected:

- **Expected:** Agents guess, debate coordination, waste tokens (that's the point of the test)
- **If bare is cheap:** Try a harder case that requires real coordination

### "Azure authentication failed"

```bash
# Verify login
az account show

# Re-authenticate
az login --use-device-code
```

---

## 📁 Project Structure

```
.
├── docs/                          # Documentation (start here)
│   ├── README.md                  # Docs index
│   ├── 1_TECH_SETUP.md           # Foundation guide
│   ├── 2_TESTING_STRATEGIES.md   # Testing methodology
│   ├── 3_BENCHMARK_DESIGN_EXPLAINED.md
│   ├── 4_HOW_TO_CREATE_USE_CASES.md
│   ├── 5_ARMS_EXPLAINED.md       # Every arm as one flow line
│   ├── 6_RUN_REPORTS_EXPLAINED.md
│   ├── 7_USE_CASE_DEADLOCK_SAFETY.md
│   ├── 8_INTENT_TO_PROTOCOL_TRAINING.md
│   ├── BENCHMARK_FAIRNESS_REVIEW.md   # Fairness audit of the benchmark
│   ├── reference/                 # Current technical deep-dives (glossary, Scribble
│   │                              #   extensions, gate internals, Foundry wiring, v3 plan)
│   ├── results/                   # Current evidence (RESULT_00 … RESULT_11 + runs/)
│   ├── predictions/               # Pre-registered predictions (written before runs)
│   ├── diary/                     # Project journal
│   └── archive/                   # Superseded docs (nothing deleted; see its README.md)
├── experiments/
│   ├── cases/                     # All benchmark cases (see the table above)
│   │   ├── finance/              # Example case
│   │   ├── banking/
│   │   ├── trade_deadlock/
│   │   └── ...                   # 20+ more, incl. skills_safety/
│   ├── baselines/                # The 15 arms (runners)
│   ├── scripts/
│   │   ├── case_runner.py        # Main benchmark driver
│   │   ├── case_loader.py        # Load case.yaml
│   │   └── index_builder.py      # Build dashboard
│   └── INDEX.html                # Results dashboard
├── stjp_core/                     # Library
│   ├── compiler/                 # Scribble integration
│   ├── monitor/                  # Runtime monitor
│   ├── foundry/                  # Azure integration
│   ├── generation/               # Skill/prompt generation
│   └── CLAUDE.md                 # Setup guide
├── scribble-java/                # Scribble compiler (vendored)
├── ROADMAP.md                    # Future phases
└── README.md                     # (you are here)
```

---

## 🎯 Key Results (2026-07-02, n=10 finance case, GPT-5.4)

| Arm | Success | Disasters | Cost-to-goal | Calls | Speed |
|---|---|---|---|---|---|
| bare (intent-only) | 0% | 18 | ∞ | — | — |
| global text | 100% | 0 | 120k | 41.8 | 124s |
| local contract | 60% | 0 | 144k | 84.9 | 223s |
| **STJP (full stack)** | **100%** | **0** | **13.3k** | **11.4** | **32s** |

**The headline:** STJP is 9× cheaper, 4× faster, same safety as global protocol text.

**Read this table with two caveats** (from the
[fairness review](docs/BENCHMARK_FAIRNESS_REVIEW.md)): bare's 0% was scored
under the strict label-matching rule, which grades the bare team on message
labels it was never shown — so treat 0% as a lower bound until the fair-rule
re-run lands. And the seconds column came from arms running in parallel
against one rate-limited deployment, so speed claims should rest on the
tokens and calls columns; re-measure time with
`case_runner.py --sequential`.

See [`docs/6_RUN_REPORTS_EXPLAINED.md`](docs/6_RUN_REPORTS_EXPLAINED.md) for the full breakdown.

---

## 📖 Next Steps

**Learn the system:**
1. Read [`docs/1_TECH_SETUP.md`](docs/1_TECH_SETUP.md) (15 min)
2. Run a 1-trial test: `python experiments/scripts/case_runner.py finance 1 --arms min_llmvalid_sched`
3. Read [`docs/6_RUN_REPORTS_EXPLAINED.md`](docs/6_RUN_REPORTS_EXPLAINED.md) to interpret results

**Run the full benchmark:**
1. Read [`docs/2_TESTING_STRATEGIES.md`](docs/2_TESTING_STRATEGIES.md) (understand fairness)
2. Run: `python experiments/scripts/case_runner.py finance 10`
3. View: `python experiments/scripts/index_builder.py && open INDEX.html`

**Create your own case:**
1. Follow [`docs/4_HOW_TO_CREATE_USE_CASES.md`](docs/4_HOW_TO_CREATE_USE_CASES.md)
2. Add a new directory under `experiments/cases/`
3. Define protocol, case config, goals
4. Test with: `python experiments/scripts/case_runner.py <case_id> 3`

---

## 🤝 Contributing

**New cases:** Add to `experiments/cases/`. Start with a task description, protocol (Scribble), and goals.

**New arms:** Add to `experiments/baselines/registry.py` and `instructions.py`. See `experiments/CLAUDE.md` for the mechanics.

**Theory/roadmap:** See `ROADMAP.md` and `RESEARCH.md`.

---

## ❓ Questions?

- **How do I run STJP?** → This README (you are here)
- **What is STJP technically?** → [`docs/1_TECH_SETUP.md`](docs/1_TECH_SETUP.md)
- **Why are tests confounded?** → [`docs/2_TESTING_STRATEGIES.md`](docs/2_TESTING_STRATEGIES.md)
- **How do I read results?** → [`docs/6_RUN_REPORTS_EXPLAINED.md`](docs/6_RUN_REPORTS_EXPLAINED.md)
- **Why does safety matter?** → [`docs/7_USE_CASE_DEADLOCK_SAFETY.md`](docs/7_USE_CASE_DEADLOCK_SAFETY.md)
- **How do I create a case?** → [`docs/4_HOW_TO_CREATE_USE_CASES.md`](docs/4_HOW_TO_CREATE_USE_CASES.md)

---

## 📄 License

[MIT](LICENSE) © Tzu-Chun Chen and contributors.  
Scribble (vendored in `scribble-java/`) is Apache 2.0 © Imperial College.

## 📖 Citation

```bibtex
@software{chen2026stjp,
  author = {Chen, Tzu-Chun},
  title = {Session-Typed Skills: A static compiler for safe multi-agent interactions},
  year = {2026},
  url = {https://github.com/ginaecho/session-typed-agents}
}
```
