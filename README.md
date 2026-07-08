# Session-Typed Judge Panel (STJP) — Quick Start & Running Experiments

**A session-typed static compiler for safe interactions in multi-agent systems.**

Multi-agent systems fail in the spaces *between* agents: one agent acts before authorization, two agents wait forever (deadlock), everyone wastes tokens negotiating coordination. STJP type-checks the **conversation itself** before any agent runs — catching deadlocks, catching unsafe orderings, and compiling safe per-agent prompts with a runtime guard and scheduler.

## 📖 Documentation

**Start here:** Read [`docs/README.md`](docs/README.md) for the full documentation index.

**Quick tours:**
- **What is STJP?** → [`docs/1_TECH_SETUP.md`](docs/1_TECH_SETUP.md) (15 min)
- **How do we test it?** → [`docs/2_TESTING_STRATEGIES.md`](docs/2_TESTING_STRATEGIES.md) (20 min)
- **Latest results** → [`docs/6_RUN_REPORTS_EXPLAINED.md`](docs/6_RUN_REPORTS_EXPLAINED.md) (plain English)
- **Why safety matters** → [`docs/7_USE_CASE_DEADLOCK_SAFETY.md`](docs/7_USE_CASE_DEADLOCK_SAFETY.md) (real examples)

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
git clone https://github.com/ginaecho/session-typed-skills
cd session-typed-skills

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

### 3. Run the full 7-arm benchmark (1 hour)

This runs all arms on a case with n=10 trials each (produces the results in `docs/results/RESULT_4_FULL_STACK.md`):

```bash
# Run all arms (this is the official benchmark)
python scripts/case_runner.py finance 10

# View dashboard
python scripts/index_builder.py
open INDEX.html
```

**The 7 arms tested:**
- **bare** — intent only (baseline)
- **maf_groupchat_llmvalid** — global protocol text with orchestrator
- **global_decentralized** — global protocol text, decentralized
- **min_llmvalid** — per-agent contract (observer, no enforcement)
- **spec_llmvalid_gate** — per-agent contract + enforcement gate
- **min_llmvalid_gate** — lean contract + enforcement gate
- **min_llmvalid_sched** — lean contract + gate + EFSM scheduler (full STJP)

### 4. Run a different case

Available cases: `finance`, `banking`, `trade_deadlock`, `report_pipeline`

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
│   ├── 6_RUN_REPORTS_EXPLAINED.md
│   ├── 7_USE_CASE_DEADLOCK_SAFETY.md
│   ├── reference/                 # Current technical deep-dives (glossary, Scribble
│   │                              #   extensions, gate internals, Foundry wiring, v3 plan)
│   ├── results/                   # Current evidence (latest run report, canonical
│   │                              #   results, deadlock + token-efficiency demos)
│   └── archive/                   # Superseded docs (nothing deleted)
├── experiments/
│   ├── cases/
│   │   ├── finance/              # Example case
│   │   ├── banking/
│   │   ├── trade_deadlock/
│   │   └── report_pipeline/
│   ├── baselines/                # The 7 arms (runners)
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
  url = {https://github.com/ginaecho/session-typed-skills}
}
```
