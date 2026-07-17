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
| `compiler/` | Scribble integration, protocol parsing, EFSM projection; `local_type.py` + `global_synthesizer.py` (bottom-up local→global synthesis); `incremental.py` (add a child sub-protocol: child verified once, projection diff, regen only affected roles) |
| `monitor/` | Runtime monitor (checks each message against the protocol) |
| `critic/` | Critic (cross-message policies via `.policy` sidecars — static over every path + runtime over traces) and Revisor (LLM repairs, Scribble+Critic re-judge). See `docs/reference/CRITIC_REVISOR.md` |
| `foundry/` | Azure AI Foundry integration (agents, threads, traces) |
| `generation/` | Skill/prompt generation from protocols; `skill_compactor.py` (EXISTING skills → local types, see `docs/reference/SKILL_COMPACTION.md`); `monitor_codegen.py` (standalone per-role monitor scripts) |
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
| `scripts/integration_stress.py` | Generated-protocol stress suite (10 seeded iterations over the round-trip / mutation / critic-oracle / revisor / incremental surface) — reports to `experiments/reports/stress/` |
| `subagent_trials/` | Foundry-free agent-interaction harness (engine + cases + committed reports; see `docs/results/RESULT_5_SUBAGENT_VALIDATION.md`) |
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
| `6_RUN_REPORTS_EXPLAINED.md` | How to read results; 2026-07-02 run explained |
| `7_USE_CASE_DEADLOCK_SAFETY.md` | Why safety matters—concrete examples |
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
2. Look at [`docs/7_USE_CASE_DEADLOCK_SAFETY.md`](docs/7_USE_CASE_DEADLOCK_SAFETY.md) for examples
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

### 5. Plain-language writing rule (docs, reports, replies)

Applies to prose in docs, reports, READMEs, changelogs, and chat replies — not to code, identifiers, function names, JSON fields, or test names.

**Global style rules (always, for every piece of prose):**

1. **Always use a small example to show *why* a design is the way it is.**
   Don't just state "the strict metric is unfair to bare arms" — show it:
   "the bare team is told *'the audit must be approved'* but scored on
   *'did TaxVerifier send a message labelled exactly `RevenueAuditApproval`
   to RevenueAnalyst'* — a label it was never shown." A reader who sees one
   concrete case understands the rule; a reader who sees only the rule has
   to trust you.
2. **Plain English.** Prefer the everyday phrase over the insider one:
   "takes turns in a fixed circle" over "round-robin polling" (then name the
   term in parentheses once, so the reader can find it in the code).
3. **Smooth reading flow.** Each paragraph should follow from the previous
   one; a section should read top-to-bottom without the reader jumping
   around or holding five labels in their head. Prefer prose that carries
   the argument; use tables only for genuinely tabular facts.
4. **No jargon, and no terminology without explanation.** Every term of art
   gets a one-clause plain-English gloss at first use ("an **arm** is one
   configuration being compared — like the treatment and control groups of
   a medical trial"). This includes project-internal nicknames.
5. **No playing smart.** Never compress a point into dense shorthand to
   sound expert. If a sentence needs the reader to already be an expert to
   parse it, rewrite it. Clarity is the skill being demonstrated — not
   vocabulary.

**Do:**
- Define every term of art on first use in a doc, in one plain clause, right where the term first appears.
- Write for a capable developer who is **not** a compiler/PL researcher. If a plain phrase says the same thing, use it instead of insider shorthand.
- If a metaphor or codename was invented mid-project (a nickname for a mechanism, a project-internal label), it must never appear in a doc without its definition — even if it feels "obvious" to the team by now.
- Once a term is glossed the first time in a document, later uses in that same document may use the short form freely.

**Don't:**
- Don't assume the reader already knows project slang from Slack, standups, or earlier docs.
- Don't drop a term of art into a heading, table cell, or bullet with no adjacent gloss anywhere in the doc.

**Known offenders and how to gloss or replace them:**

| Term | Plain phrase / gloss |
|---|---|
| canary | a planted check item with a known correct answer |
| AST re-emission | re-printing the protocol from its parsed structure, so comments and hidden text are dropped |
| pillar | (avoid; name the actual thing it refers to instead) |
| wire / wired | connect |
| seam | the translation step from plain-language intent to formal protocol (define on first use in *any* doc) |
| escrow | a neutral third party that holds funds until both sides deliver |
| geometric median | a robust way to combine scores so one extreme judge cannot drag the result |

**Example:** first use in a doc — "a planted check item with a known correct answer (a *canary*)"; every later use in that doc may just say "canary."

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

## 🔐 Git identity — ALWAYS commit/push/PR as ginaecho

**Every** git commit, push, branch, and pull request you make in this project must be attributed to the project owner, never to Claude or any other AI/bot identity:

- **Author / committer for this repo (`ginaecho/session-typed-agents`):** `ginaecho <gina.tcchen@gmail.com>`
- **GitHub account for push & PR:** `ginaecho`
- **Do NOT** add a `Co-Authored-By: Claude ...` trailer or any assistant/session trailer. Do NOT set the author to any bot/assistant identity.
- **No "claude" keywords anywhere** in git artifacts: not in branch names, commit messages, trailers, tags, or PR titles/bodies.
- When working in the Microsoft mirror flow (below), the identity there is `Gina Chen <tzuchunchen+microsoft@microsoft.com>` / account `tzuchunchen_microsoft`.

Set the identity inline on every commit so it is correct regardless of local git config:

```bash
git -c user.name="ginaecho" -c user.email="gina.tcchen@gmail.com" \
    commit -m "<message>"
```

**Branch naming:** every branch ALWAYS starts with the `gc/` prefix, e.g.
`gc/paper-v8-iclr-reposition-concurrent-work`. Never create `claude/...` or
other-prefixed branches.

---

## 🚀 Publishing workflow — TWO hops, in this order

This project lives in two GitHub repos. Changes flow **source first, then mirror** —
never publish to the mirror without the source being updated first.

```
  (local working copy)
        │  hop 1: commit + push
        ▼
  ginaecho/session-typed-skills  (main)      ← the SOURCE OF TRUTH
        │  hop 2: sync tracked files into a subfolder + PR
        ▼
  mcaps-microsoft/eag-innovation  (main)
        └── agentic-governance/stjp/          ← the MIRROR (internal MS monorepo)
```

### Hop 1 — commit & push to the source repo (`ginaecho/session-typed-skills`)

This local repo's `origin` **is** `ginaecho/session-typed-skills`. Commit your work
here first and push to `main`:

```bash
# from the project root
git add -A
git -c user.name="Gina Chen" -c user.email="tzuchunchen+microsoft@microsoft.com" \
    commit -m "<type>: <short description>

<longer explanation if needed>"
git push origin main
```

Use a `gc/<topic>` branch + PR instead of pushing straight to `main` only if the
change warrants review; otherwise a direct push to `main` is fine for this repo
(it is the owner's own project).

### Hop 2 — mirror into the internal monorepo (`mcaps-microsoft/eag-innovation`)

Sync the **tracked** files (everything `git ls-files` returns — this already
excludes `scribble-java/`, images, `.env`, `.docx`/`.pptx`, venvs, and run outputs
via `.gitignore`) into `agentic-governance/stjp/` in the internal repo, via a
branch + PR. **Never push to that repo's `main` directly** — it is a shared
Microsoft org repo.

The exact procedure (verified 2026-07-03, PR #107):

```bash
SRC="/c/Users/tzuchunchen/OneDrive - Microsoft/Documents/Projects/testing_ideas"
WORK="/c/Users/TZUCHU~1/e"        # short base path — Windows MAX_PATH (260) blocks
                                  # the deep experiments/.../llm_drafts/ paths otherwise
git config --global core.longpaths true   # also required for the deep paths

# 1. Sparse-clone ONLY agentic-governance (the monorepo has Windows-illegal
#    filenames elsewhere that break a full checkout)
rm -rf "$WORK" && mkdir -p "$WORK" && cd "$WORK"
git clone --depth 1 --no-checkout --filter=blob:none \
    https://github.com/mcaps-microsoft/eag-innovation.git
cd eag-innovation
git config core.longpaths true
git sparse-checkout init --cone
git sparse-checkout set agentic-governance
git checkout main
git checkout -b gc/stjp-updates-docs

# 2. Replace the old copy: delete everything under agentic-governance/,
#    then copy the source repo's tracked files into agentic-governance/stjp/
git rm -r --quiet agentic-governance
mkdir -p agentic-governance/stjp
cd "$SRC"
git ls-files -z | while IFS= read -r -d '' f; do
    mkdir -p "$WORK/eag-innovation/agentic-governance/stjp/$(dirname "$f")"
    cp "$f" "$WORK/eag-innovation/agentic-governance/stjp/$f"
done

# 3. Stage, verify, commit as Gina, push, PR
cd "$WORK/eag-innovation"
git add agentic-governance
#   sanity checks before committing:
#   - files under stjp/:   git ls-files -- agentic-governance/stjp | wc -l   (== source count)
#   - leftovers:           git ls-files -- agentic-governance | grep -v '/stjp/' | wc -l   (== 0)
#   - nothing outside:     git diff --cached --name-only | grep -v '^agentic-governance/'   (empty)
#   - no excluded types:   git diff --cached --name-only --diff-filter=A | grep -Ei '\.(png|jpg|env|docx|pptx)$|/scribble-java/'   (empty)
git -c user.name="Gina Chen" -c user.email="tzuchunchen+microsoft@microsoft.com" \
    commit -m "Restructure agentic-governance: sync Session-Typed Skills (STJP) under stjp/"
git push -u origin gc/stjp-updates-docs
gh pr create --repo mcaps-microsoft/eag-innovation \
    --base main --head gc/stjp-updates-docs \
    --title "..." --body "..."
```

**Gotchas already discovered (don't re-learn them):**
- Git reports many files as **renames** (R), not adds (A), because the old copy
  had the same basenames. `git diff --cached --diff-filter=A | wc -l` will
  under-count — trust `git ls-files -- agentic-governance/stjp | wc -l` instead.
- The full monorepo checkout fails ("checkout failed") due to Windows-illegal
  filenames outside `agentic-governance/` — that is why the sparse checkout is
  mandatory.
- Do **not** run history-rewriting git ops (`pull --rebase`, etc.) against a repo
  while a live experiment run is writing to it.

### Commit message shape (both hops)

```
<type>: <short description>

<longer explanation if needed>

Testing (for code changes):
- Ran case_runner.py <case> 3 --arms <arms>
- Verified <metric> improved / stayed flat / regressed
```

Examples: `feat: add supply_chain use case`,
`fix: monitor now allows concurrent actions on different channels`.

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
