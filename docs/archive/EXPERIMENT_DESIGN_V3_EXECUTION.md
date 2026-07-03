# Experiment design v3 (execution plane) — the unconfounded finance demo

*2026-07-02. Pre-registered: this document was written and committed BEFORE the
run it describes was executed. Predictions in §5 are falsifiable; the run
report will grade them honestly, whichever way they land.*

## 1. What this experiment is for

The claim under test: **a session-type toolchain (STJP) statically generates,
for each agent, an interaction-safe skill — and that same static artefact both
(a) keeps multi-agent behaviour correct and (b) reduces token cost.**

"Interaction-safe skill" means: the per-role prompt is not hand-written and not
LLM-improvised — it is *projected* from a Scribble-validated (deadlock-free)
global protocol, so every SEND/RECEIVE it licenses is provably consistent with
what every other role's skill licenses. The static checker is the skill
generator's type system.

Two prior findings say the existing finance runs cannot support this claim as
run (see `WHY_B_MATCHES_C_ANALYSIS.md`, `RUN_REPORT_2026-06-17.md` §3,
`STJP_RESEARCH_REPORT.md` §4.8):

1. **Correctness was confounded with orchestration.** The "global protocol as
   text" arm (B) ran on a *central LLM orchestrator* (Microsoft Agent Framework
   GroupChat) that sequences speakers; the projected arms ran on decentralized
   round-robin. B's 100% goal completion was partly the orchestrator holding
   misbehaving roles back — every projected-arm failure was the same ordering
   slip (TaxVerifier sending `Approval` early) that the orchestrator happens to
   prevent. So "B ties the gate" compares apples to oranges.
2. **Token cost pointed the wrong way, for a diagnosed reason.** The projected
   arms cost 79k–332k tokens per delivered report vs B's 27k — not because the
   projected contract is bigger (per-call prompts are near-identical on a
   15-message protocol: ~1.8k vs ~2.1k tokens/call) but because **round-robin
   polling asks idle agents to act** (78 calls vs B's 14). The cost was the
   *execution plane*, not the contract.

Both flaws have the same fix: **hold the execution plane constant, then make
the execution plane itself the treatment.** The projection that generates each
skill also yields, for free, a scheduler: at every point, the per-role finite
state machines say exactly which roles are able to send. Polling only those
roles removed 83% of agent calls in the offline oracle smoke
(`stjp_core/runtime/delm_runner.py`, `RUN_REPORT_2026-06-17.md` §4). That
scheduler had never been wired to real LLM agents. This experiment wires it in
(`FoundryRunner(schedule="efsm")`) and measures it.

The key asymmetry, stated up front because it is the point of the demo: **a
global-protocol-as-text arm cannot have this scheduler.** Deciding "who can act
now" from prose requires either an LLM orchestrator (extra calls, no guarantee)
or a human-written dispatcher (which is exactly the artefact STJP derives
mechanically). Only a machine-checkable type projects into an execution plan.

## 2. Arms

All arms: finance case, same model (`AZURE_OPENAI_DEPLOYMENT`, gpt-5.4), real
Azure AI Foundry Agent Service agents, n = 10 trials, alternating branch hints,
identical goal set (re-anchored `llm_drafts/valid/goals.yaml` for protocol-aware
arms). New arms in **bold**.

| # | arm key | protocol info in prompt | enforcement | execution plane |
|---|---|---|---|---|
| A | `bare` | none (intent only) | none | round-robin |
| B-orch | `maf_groupchat_llmvalid` | global type as text | none | central LLM orchestrator |
| B-dec | `global_decentralized` | global type as text | none | round-robin |
| C-min | `min_llmvalid` | projected local type (lean) | observer only | round-robin |
| C+spec | `spec_llmvalid_gate` | projected local type (verbose) | gate (reject + re-prompt) | round-robin |
| **C+min** | **`min_llmvalid_gate`** | projected local type (lean) | gate | round-robin |
| **STJP** | **`min_llmvalid_sched`** | projected local type (lean) | gate | **EFSM enabled-sender scheduler** |

Every pairwise contrast changes exactly one thing:

- **A vs B-dec** — value of *having* the validated protocol, same plane.
- **B-orch vs B-dec** — the orchestration confound, finally measured directly.
  This is the contrast the old design couldn't see.
- **B-dec vs C-min** — global text vs projected local skill, same plane, no
  enforcement on either side.
- **C-min vs C+min** — enforcement gate, identical prompts, same plane.
- **C+spec vs C+min** — contract verbosity under enforcement.
- **C+min vs STJP** — the scheduler, identical prompts, identical enforcement.
  This is the token-efficiency treatment.

## 3. What is measured

Per arm (all computable from `events_<arm>.jsonl` + `summary*.json`, plus the
post-hoc graders):

- **Goal Completion Rate (GCR)** — all applicable goals plus the final goal in
  the same attempt (`summary_eval.json`, strict and role-pair rungs).
- **Disasters** — severity S4 events (irreversible act before authorization),
  from `severity_grader.py`; also full S0–S4 histogram.
- **Cost of success** — total tokens per trial ÷ GCR (tokens per *delivered*
  report; a stalling arm pays for its stalls).
- **Calls per trial** — the execution-plane metric the scheduler targets.
- **Prompt tokens per call and completion (deliberation) tokens per call** —
  separates the contract-size lever from the scheduling lever.
- **Gate interventions** (`gated` markers) — how often enforcement actually
  fired; distinguishes "the gate did work" from "the model never strayed".
- **Critical-property compliance (CGC)** — `criticality_gate.py` C1/C2/C3.

## 4. Fairness rules (unchanged from TESTING_STRATEGY.md, restated)

- Same model, same deployment, same day, arms interleaved by the runner.
- Goals graded structurally/leniently for label-inventing arms (role-pair
  rung reported alongside strict) — the DEADLOCK_DEMO over-strict lesson.
- The full per-role system prompt of every arm is persisted to
  `runs/<ts>/prompts/<arm>/` — token claims are auditable from the run dir.
- The scheduler arm keeps the same per-turn agent interface (same view builder,
  same JSON action format, same 3-attempt retry-to-success); *only* the
  decision of which role to poll changes.

## 5. Pre-registered predictions

- **P1 (correctness, unconfounded).** On the shared decentralized plane, B-dec
  falls below 100% GCR — the early-`Approval` ordering slip returns without the
  orchestrator to suppress it — while both gate arms stay at 100% with the slip
  *rejected* (visible as `gated` markers), and A stays at 0% with S4 disasters.
  If instead B-dec also scores 100%, the honest conclusion is that gpt-5.4
  self-complies with pasted text even unorchestrated, and the correctness case
  for enforcement on this case/model rests solely on guarantee + audit trail
  (the position already held in `b-ties-cplus-honesty`); the demo then leans on
  P2.
- **P2 (tokens).** STJP (scheduled) cuts calls per trial by ≥60% vs C+min
  (round-robin, identical prompts + gate) and lands the **lowest cost of
  success of any decentralized arm**, at or below B-dec. Mechanism check:
  prompt-tokens/call roughly flat vs C+min; the saving is call count.
- **P3 (skill-vs-text, same plane).** C-min ≥ B-dec on protocol adherence
  (monitor acceptance), since the local skill removes the "figure out your part
  from the global text" step; token cost per call comparable.
- **P4 (orchestrator cost accounting).** B-orch's headline cheapness shrinks
  once orchestrator calls/tokens are counted against it; report both with and
  without.

**Falsifiers.** If STJP-scheduled does not beat C+min on calls, the scheduler
claim dies on real agents (oracle smoke notwithstanding). If B-dec matches the
gate at 100% *and* beats STJP on cost, the honest headline stays "the validated
protocol does the work; enforcement buys guarantee, scheduling buys nothing on
a protocol this small" — and the next step is a larger protocol, not a louder
claim.

## 6. Run plan

```powershell
# from testing_ideas/ (C:\Python313\python.exe — NOT stjp_core/.venv, which is
# now the Flask live-demo env)
python experiments\scripts\case_runner.py finance 10 --arms bare,maf_groupchat_llmvalid,global_decentralized,min_llmvalid,spec_llmvalid_gate,min_llmvalid_gate,min_llmvalid_sched
# post-hoc graders
python experiments\scripts\severity_grader.py finance <run_dir>
python experiments\scripts\criticality_gate.py finance <run_dir>
```

Smoke first: `finance 1 --arms min_llmvalid_gate,min_llmvalid_sched` (the two
new arms) to verify the scheduler terminates, gates fire, and prompts persist.

## 7. What this experiment still does not show

Held over, deliberately, so this run stays single-treatment-per-contrast:

- Whether enforcement is *necessary* on tasks a model won't self-comply with —
  that is the criticality two-variant design
  (`BENCHMARK_DESIGN_V3_CRITICALITY.md`), unchanged by this work.
- Contract-size token savings — the finance protocol (15 messages) is too
  small; that lever is already shown on `report_pipeline`
  (`TOKEN_EFFICIENCY_DEMO.md`, −63%). This experiment isolates the *scheduling*
  lever instead.
- Weaker-model robustness (gpt-4o B scored 40% historically) — a follow-up
  sweep, not this run.
