---
title: Copilot subagent verification of STJP coordination
description: Independent 2026-07-24 verification of STJP static checking, scheduling, runtime enforcement, and subagent coordination
ms.date: 2026-07-24
ms.topic: concept
keywords:
  - STJP
  - subagents
  - multi-agent coordination
  - session types
  - runtime enforcement
estimated_reading_time: 12
---

## Executive verdict

STJP materially improves subagent organization when a workflow has multiple
roles, required message ordering, authorization gates, shared resources,
branches, retries, or deadlock risk.

Its strongest contribution is not making agents smarter. STJP turns
coordination from an informal prompt convention into an executable contract:

1. Validate the team-level protocol before execution.
2. Project the protocol into a local state machine for each role.
3. Poll only roles currently permitted to act.
4. Reject illegal messages before delivery.
5. Preserve an auditable trace of decisions and violations.

Fresh tests on 2026-07-24 verified all five behaviors. The strongest new
agent-in-the-loop comparison used independent GitHub Copilot subagents with no
shared conversation state and no Azure AI Foundry dependency. The unchecked
team deadlocked after eight wasted agent calls and delivered no messages. The
STJP-governed team completed the seven-message protocol in seven calls with no
violations.

> [!IMPORTANT]
> The fresh agent comparison is one scenario-level trial per arm. It verifies
> the mechanism end to end, but it does not establish a population-level
> success-rate estimate. Earlier STJP experiments provide larger samples; this
> report keeps those prior claims separate from the new evidence.

## Question tested

Can STJP help an orchestrator organize independent subagents, and if so, what
mechanisms create the benefit?

The evaluation treated the following claims as falsifiable:

* Circular waits should be diagnosed before agents run.
* The scheduler should invoke only roles with a currently enabled send.
* The gate should prevent an illegal message from entering the delivered trace.
* Independent subagents should complete a typed workflow without sharing a
  global conversation.
* Generated protocols should survive round-trip synthesis, mutation checks,
  policy checks, repair, and incremental extension.

## How STJP organizes subagents

STJP separates coordination into three layers.

### Static protocol checking

A Scribble global protocol defines the roles, messages, ordering, branches, and
loops for the whole team. STJP validates that protocol and can also synthesize a
global protocol from role-local types. A circular dependency can therefore be
rejected before any model calls are made.

Relevant implementation:

* [`stjp_core/compiler/`](../../stjp_core/compiler/)
* [`test_skill_compactor.py`](../../stjp_core/tests/test_skill_compactor.py)

### Role-local projection

The validated global protocol is projected into one local state machine per
role. A subagent receives only its own permitted sends, expected receives, and
relevant inbox. It does not need to infer the complete team workflow from prose.

The local contract answers three concrete questions:

* May this role act now?
* Which peer may it contact?
* Which message labels are legal in the current state?

### Runtime scheduling and enforcement

The runtime calculates the enabled sender set from the projected state
machines. Roles waiting on receives are not polled. Every proposed write is
checked before it enters the shared trace.

Relevant implementation:

* [`delm_runner.py`](../../stjp_core/runtime/delm_runner.py)
* [`monitor.py`](../../stjp_core/monitor/monitor.py)
* [`engine.py`](../../experiments/subagent_trials/engine.py)

This mechanism does not improve an agent's factual reasoning. It narrows the
coordination decision and prevents invalid actions from affecting the rest of
the team.

## Fresh agent-in-the-loop experiment

### Method

The `escrow_trade` case used four isolated roles:

* Buyer
* Carrier
* Escrow
* Seller

The safe protocol requires seven messages:

```text
Buyer -> Escrow: Deposit
Escrow -> Seller: PaymentSecured
Seller -> Carrier: ShipGoods
Carrier -> Buyer: DeliverGoods
Buyer -> Escrow: ConfirmReceipt
Escrow -> Buyer: SettlementComplete
Escrow -> Seller: SettlementComplete
```

Two arms were compared through the same deterministic engine:

| Arm      | Instructions given to subagents             | Delivery mode | Polling mode           |
|----------|---------------------------------------------|---------------|------------------------|
| Unchecked | Plausible role-local prose skills          | Observe only  | All roles each round   |
| STJP      | Compiler-projected local contract and state | Enforced      | Enabled senders only   |

Each role decision came from a fresh GitHub Copilot subagent. A subagent saw
only one role prompt and that role's inbox. It did not see another role's
prompt, private state, or the global trace.

The engine classified a deadlock after two consecutive rounds with no delivered
messages.

### Round-one behavior

The unchecked engine polled all four roles, although none had an initiating
action under their individual prose rules. Four independent subagents returned
`WAIT`:

| Role    | Decision | Reason                              |
|---------|----------|-------------------------------------|
| Buyer   | WAIT     | `DeliverGoods` not received         |
| Carrier | WAIT     | `ShipGoods` not received            |
| Escrow  | WAIT     | Payment confirmation not received   |
| Seller  | WAIT     | Payment not received                |

The STJP engine polled only Buyer. Buyer's projected contract exposed one legal
action:

```json
{"action":"send","to":"Escrow","label":"Deposit","payload":"100.0"}
```

A second fresh sample reproduced the unchecked result: all four roles waited
again. The engine then classified the unchecked run as deadlocked. Meanwhile,
the STJP enabled set advanced from Buyer to Escrow, Seller, Carrier, Buyer, and
Escrow. Fresh subagents selected the unique legal transition at each role
boundary.

### Results

| Metric                     | Unchecked skills | STJP |
|----------------------------|-----------------:|-----:|
| Goal completed             | No               | Yes  |
| Deadlock                   | Yes              | No   |
| Delivered messages         | 0                | 7    |
| Agent calls                | 8                | 7    |
| Monitor violations         | 4                | 0    |
| Gate rejections            | Not applicable   | 0    |
| Goal completion rate       | 0%               | 100% |
| Contract conformance       | 0%               | 100% |
| Estimated cost-to-goal     | Undefined        | 2,320 tokens |

Raw reports:

* [`unchecked/report.json`](../../experiments/subagent_trials/runs/copilot_verify_20260724/unchecked/report.json)
* [`stjp/report.json`](../../experiments/subagent_trials/runs/copilot_verify_20260724/stjp/report.json)

> [!NOTE]
> The run artifacts are under the benchmark's gitignored `runs/` directory.
> They are local verification evidence unless explicitly promoted to a tracked
> report location.

## Runtime gate test

The successful STJP run did not naturally require a correction because every
subagent selected a legal transition. A separate adversarial test deliberately
submitted this first action:

```text
Buyer -> Seller: Payment(100.0)
```

At that state, Buyer's only legal action was `Deposit(Double)` to Escrow.

The gate produced the following observable result:

| Check                                  | Result |
|----------------------------------------|--------|
| Illegal message delivered             | No     |
| Delivered trace length after attempt  | 0      |
| Rejection recorded                    | Yes    |
| Rejected label                        | `Payment` |
| Allowed action returned to subagent   | `Deposit(Double)` to Escrow |

The re-prompt explicitly stated that the previous action had been rejected and
identified the currently allowed transition. This verifies prevention before
delivery, not only post-hoc violation reporting.

## Static deadlock test

The focused synthesis test constructed locally plausible role contracts:

* Buyer waits for goods before paying.
* Seller waits for payment before shipping.
* Carrier waits for shipping before delivering.

The combined system contains a circular wait. STJP diagnosed the participating
roles during synthesis before runtime.

Command:

```powershell
python -m pytest \
  stjp_core/tests/test_skill_compactor.py::test_synthesis_detects_circular_wait \
  -q -s
```

Result:

```text
[synthesis] circular wait diagnosed per-role before runtime
1 passed in 0.09s
```

## Scheduler efficiency test

The offline finance runtime used a contract-following oracle to isolate the
scheduler mechanism from model variability.

| Branch   | Protocol events | STJP polls | Round-robin polls | Poll reduction |
|----------|----------------:|-----------:|------------------:|---------------:|
| High     | 11              | 11         | 66                | 83%            |
| Standard | 9               | 9          | 54                | 83%            |

The adversarial oracle selected the standard branch while holding high-revenue
data. In enforce mode, the monitor rejected the action and the session
recovered. In observe mode, the action was delivered and recorded as one
violation.

Command:

```powershell
python experiments/scripts/smoke_delm_runtime.py
```

This result verifies the scheduling mechanism. It does not independently prove
an 83% production token reduction because the actors were deterministic
oracles rather than live models.

## Generated-protocol stress test

Three fresh generated iterations exercised:

* Global-to-local projection and global recomposition
* Five mutation classes
* Static Critic policy oracles
* Protocol repair
* Two-level incremental extension
* Generated standalone monitors

The first run completed 51 of 57 checks. All six failures were Scribble CLI
path errors:

```text
Bad module arg: ..\..\..\TZUCHU~1\AppData\Local\Temp\...\orig.scr
```

No mutation, Critic, repair, or extension check failed. Re-running one complete
iteration with a short temporary directory passed 21 of 21 checks:

```powershell
$env:TEMP = "C:\tmp\stjp"
$env:TMP = "C:\tmp\stjp"
python experiments/scripts/integration_stress.py 1 \
  --report-dir experiments/subagent_trials/runs/copilot_verify_20260724/stress_shorttmp
```

Result:

```text
[stress] iteration 1/1: 21/21 PASS
```

This distinguishes a Windows path-handling problem from a protocol-logic
failure. The default long temporary-path failure remains an operational defect
that should be fixed or documented in the runner.

## Test-suite results

The final local validation used the short temporary directory.

| Suite                      | Passed | Failed | Skipped |
|----------------------------|-------:|-------:|--------:|
| `stjp_core/tests`          | 48     | 2      | 1       |
| EFSM equivalence tests     | 6      | 0      | 0       |

The two core failures were optional nuScr backend tests. They could not connect
to the Docker Desktop Linux engine because Docker Desktop was not running. The
skipped test requires the optional `xgrammar` package, which was not installed.
VS Code reported no diagnostics in `stjp_core`.

These outcomes are environment prerequisites, not passing evidence. They also
do not indicate a failure in the default Scribble backend used by the fresh
agent experiment.

## What STJP helps with

### Explicit handoffs

A worker must send a declared status such as `Done` or `Blocked`. It cannot
silently assume that a coordinator will poll it later. Missing handoffs become
specific protocol-state failures rather than ambiguous stalled conversations.

### Reduced idle invocation

A subagent waiting on a receive is not invoked. The scheduler asks only roles
whose local state permits a send. This can reduce model calls substantially in
workflows where most roles are waiting at any given step.

### Shared-resource control

A protocol can model one push turn, deployment lease, approval token, or other
shared capability at a time. A worker cannot acquire the next turn until the
current holder explicitly releases it.

The repository models this pattern in
[`planner_workers/case.yaml`](../../experiments/cases/planner_workers/case.yaml).

### Mechanical review and authorization gates

A protocol can make merge, publish, execute, settle, or deploy transitions
unavailable until required review messages have occurred. The runtime does not
need to trust a subagent's claim that approval happened; the state machine must
have observed the required transition.

### Context isolation

Each role receives its local contract and relevant inbox rather than the entire
team history. This narrows the coordination decision and reduces accidental
cross-role information exposure. Information-flow policy still requires
separate policy definitions and checks; local projection alone is not a complete
confidentiality system.

### Auditable failure states

The execution trace distinguishes:

* Off-protocol action
* Wrong peer
* Failed payload refinement
* Wrong value-dependent branch
* Stateful invariant violation
* Premature termination
* Deadlock or bounded retry exhaustion

These are more actionable than a generic agent timeout.

## What the evidence does not prove

STJP does not determine whether the protocol correctly represents the business
intent. A valid protocol can be the wrong protocol.

STJP also does not guarantee:

* Factual correctness of message content
* High-quality plans or code from individual subagents
* Safety for actions not represented as monitored protocol messages
* Automatic support for open-ended workflows whose roles emerge dynamically
* Lower cost in every workflow
* Fully decentralized execution in the tested harness

The local monitors support decentralized enforcement, but the tested harness
uses a central engine to calculate enabled roles and dispatch turns. The formal
contracts are role-local; this execution implementation remains centrally
scheduled.

The fresh subagent experiment also has an instructional asymmetry. The
unchecked arm received locally plausible but mutually incompatible skills. The
STJP arm received a repaired, validated escrow-first protocol. The comparison
therefore demonstrates the value of protocol synthesis, validation, projection,
and enforcement as a complete coordination process. It does not isolate prompt
text from scheduler or gate effects. The scheduler and gate tests above isolate
those mechanisms separately using deterministic actors and adversarial input.

## Recommended use

STJP is a strong fit for structured, safety-sensitive subagent workflows such
as:

* Code review and merge authorization
* Build, test, and deployment pipelines
* Financial settlement and approval
* Publishing workflows
* Code generation followed by review before execution
* Planner-worker teams sharing one repository or deployment target
* Bounded retry and escalation workflows

STJP is likely excessive for unconstrained brainstorming, exploratory research,
or short workflows where one orchestrator can reliably hold the entire state
and no irreversible action depends on ordering.

The practical design principle is:

> Use agent reasoning to decide content. Use STJP to decide who may communicate
> what, with whom, and when.

## Reproduction

From the `stjp/` repository root:

```powershell
$env:PYTHONPATH = $PWD.Path
$env:TEMP = "C:\tmp\stjp"
$env:TMP = "C:\tmp\stjp"

python -m pytest \
  stjp_core/tests/test_skill_compactor.py::test_synthesis_detects_circular_wait \
  -q -s

python experiments/scripts/smoke_delm_runtime.py
python experiments/scripts/integration_stress.py 1 \
  --report-dir experiments/subagent_trials/runs/manual_verify/stress

python -m pytest stjp_core/tests -q
python -m pytest experiments/tests/test_efsm_equiv.py -q
```

The Foundry-free subagent engine follows this stateful interface:

```powershell
cd experiments/subagent_trials
python engine.py init --case escrow_trade --arm stjp --trials 1 --dir runs/manual
python engine.py next --dir runs/manual
# Dispatch each emitted prompt to an independent agent.
# Save replies in the engine's JSON format.
python engine.py submit --dir runs/manual --file replies.json
python engine.py report --dir runs/manual
```

## Final assessment

STJP is technically substantive rather than a prompt-formatting convention. Its
compiler, projection, monitor, gate, and scheduler are executable and produced
observable effects in fresh tests.

The strongest verified benefit is that coordination errors become explicit
machine states: invalid before execution, rejected before delivery, enabled
now, waiting now, or terminal. That makes STJP most useful as a coordination
control plane for structured subagent teams. It complements agent reasoning; it
does not replace it.
