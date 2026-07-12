# STJP validation report — subagent trials + integration stress (2026-07-04)

**Scope.** Full-system validation of the three components added 2026-07-04 —
the Critic (a checker that looks across several messages in the conversation
at once, catching violations no single message reveals on its own) and its
companion Revisor (which repairs a protocol the Critic flags), skill
compaction (bottom-up local→global), and incremental
sub-protocol extension — going beyond unit tests: (1) an integration stress
suite over *generated* complex protocols, run 10×; (2) three agent-in-the-loop
experiments, n=10 each, in which **independent Claude subagents** (no Azure
AI Foundry anywhere in the loop) play the roles / the compactor / the revisor
against the deterministic STJP machinery (Scribble, gate, scheduler,
monitors, Critic).

**Headline: every deterministic check passed (211/211), and across 30
agent-driven trials the ladder reproduced end-to-end — unchecked skills 0/10
(all deadlock), STJP-governed 10/10 and 10/10 at the protocol-minimum agent
cost, with 0 violations under four cross-message policies.** The stress suite
also caught (and led to the fix of) one real bug: chained extensions used to
splice the `do` call into an aux block (`incremental.py::_main_header_match`).

---

## 1. Method — agent interaction without Foundry

`experiments/subagent_trials/engine.py` provides the same turn mechanics as
the Foundry benchmark as plain files + JSON: `init → next → submit → report`.
The engine is deterministic code only — EFSM scheduler, enforcement gate,
per-role monitors, runtime Critic; **the intelligence is injected from
outside**: each poll emitted by `next` was answered by a freshly spawned,
independent Claude subagent (haiku-class for role agents; a stronger model
for the compactor/revisor agents), whose JSON reply was fed back via
`submit`. Every arm's trace is judged post-hoc by the same instruments
(monitors + runtime Critic + goal checks), so arms differ ONLY in what the
agents were given and whether the gate/scheduler was active.

| arm | agents get | delivery | polling |
|---|---|---|---|
| `unchecked` | the trade_deadlock prose skills (circular wait) | everything delivered (observe) | all roles per round |
| `stjp` | lean contract rendered from the Scribble-validated projection | gate ENFORCEs before delivery | EFSM-enabled senders only |

Deadlock rule: two consecutive rounds with zero delivered messages.

## 2. E1 — Compaction gauntlet (10 runs)

Per run, one subagent compacted the four **prose** trade skills
(`experiments/cases/trade_deadlock/unchecked_skills/`) into local-type JSONs;
the deterministic pipeline (`compaction_gauntlet.py`: parse → multiparty
compatibility → product synthesis → Scribble) judged them. A second subagent
then revised the local types given the checker's diagnosis, and was judged
again.

| stage | result |
|---|---|
| raw skills flagged UNSAFE | **10/10** (all at the compatibility stage: `SettlementComplete` has no receiver; Escrow starves waiting for `Payment`; the Buyer/Seller/Carrier circular wait sits behind those) |
| revised skills SAFE (deterministic synthesis + Scribble VALID) | **10/10, first attempt** — every revision converged on the escrow-first design (escrow: a neutral third party that holds funds until both sides deliver; Deposit → PaymentSecured → ShipGoods → DeliverGoods → Confirm → Settlement×2) |

Takeaway: the bottom-up pipeline turns "plausible prose skills that quietly
deadlock" into a **mechanically-refutable claim** in milliseconds, and its
diagnosis is actionable enough that an LLM repairs the system in one shot,
10 out of 10 times. (Raw data: `reports/e1_compaction_gauntlet.json`.)

## 3. E2 — Interaction trials, unchecked vs STJP (10 trials each)

Case `escrow_trade`: 4 roles, 7 messages, judged against 4 cross-message
policies (S1 payment-secured-before-shipping, S2 confirm-before-settlement,
A1 single deposit, F1 deposit-data-not-to-Carrier with declassification).

| metric | unchecked (prose skills) | STJP (contract+gate+scheduler) |
|---|---|---|
| success (both settlements delivered) | **0/10** | **10/10** |
| deadlocks | **10/10** | 0 |
| agent calls per trial | 8.8 (all wasted) | **7.0 = the protocol minimum** |
| monitor violations (post-hoc, Set A) | 42 | **0** |
| runtime-Critic findings (4 policies) | 0 on 2 delivered msgs* | **0 on 70 messages** |
| gate rejections | n/a (observe) | 0 needed |

\* the unchecked arm produced almost no messages to judge — 39/40 round-one
decisions were WAIT; one Buyer improvised an off-vocabulary `RequestDelivery`
(delivered in observe mode, counted as off-protocol by the monitors), and the
system still starved. This is precisely the "quiet hang" failure mode: no
crash, tokens burned, nothing delivered.

The engine's gate path was separately exercised with a scripted off-contract
send (`Payment` straight to the Seller in round 1): the gate **rejected it
before delivery**, re-prompted the role with the rejection and the allowed
actions, and the trial still completed cleanly — rejection observable in
`report.json` (`gate_rejections: 1`, `monitor_violations: 0`).

## 4. E3 — Incrementally extended protocol (10 trials)

`setup_ext_case.py` extended the escrow protocol with the `SettlementAudit`
child via the REAL incremental pipeline: child verified once (cache),
`do SettlementAudit(Escrow, Auditor)` anchored after `ConfirmReceipt`,
projection diff = {Escrow changed, Auditor new; Buyer/Seller/Carrier
untouched}, and regenerated contracts + standalone monitors for exactly
those two roles.

The trials then ran on the composed 5-role, 9-message protocol. The **new
and changed decision points were sampled live** (10× Escrow entering the
audit branch on its regenerated contract; 10× the brand-new Auditor); the
unchanged roles' rounds replayed the decision pattern already sampled live
20/20 in E2 (disclosed design choice — the incremental claim is precisely
that unchanged roles need no re-validation).

| metric | value |
|---|---|
| success | **10/10** |
| Escrow correctly entered the new audit branch | **10/10** live samples |
| new Auditor followed its generated contract | **10/10** live samples |
| monitor violations / Critic findings (incl. S3 audit-before-settlement) | **0 / 0** |
| standalone `Escrow_monitor.py` / `Auditor_monitor.py` verdicts on all traces | **10/10 and 10/10 conformant** |

## 5. Integration stress suite (deterministic, 10 seeded iterations)

`experiments/scripts/integration_stress.py` — per iteration: generate a
fresh 4-7-role protocol with nested choices (8-20 messages), then:
round-trip project→resynthesize→Scribble (S1), inject 1 of 5 mutation
classes and require a layer to catch it (S2), critic-oracle checks with
verdicts known by construction (S3), the Revisor loop on a policy-broken
variant with a scripted repair client (S4), and a 2-deep incremental
extension chain with cache/blast-radius/monitor checks (S5).

**Result: 211/211 checks passed** (`experiments/reports/stress/`). During
development the suite caught a real defect — on a *composed* parent, the
extension header-matcher hit the child's `aux global protocol` first and
spliced the next `do` call inside it. Fixed in
`stjp_core/compiler/incremental.py` (`_main_header_match`), regression
covered by the suite and `tests/test_incremental.py`.

## 6. Honest limitations

- Role agents are haiku-class and the contracts are short linear state
  machines; harder reasoning loads (long contexts, adversarial prompts) are
  not measured here. The unchecked-arm variance we did observe (an
  improvised message in 1/80 decisions) is exactly what the gate absorbs.
- E3 rounds 1-5 and 8-9 replay decision shapes sampled live elsewhere
  (documented above); all novel decision points were sampled live, n=10.
- Trials share prompts across n (independent samples of the same state), so
  n=10 measures decision stochasticity, not scenario diversity — scenario
  diversity is what the stress suite's generated protocols cover.
- The engine's monitors are the strict sequential walkers; the async
  commuting subtleties of `monitor/monitor.py` are exercised in the unit
  suite, not here (these protocols are linear per role).

## 7. Reproduce

```bash
python experiments/scripts/integration_stress.py 10          # deterministic
cd experiments/subagent_trials
python setup_ext_case.py                                      # build ext case
python engine.py init --case escrow_trade --arm stjp --trials 10 --dir runs/x
python engine.py next --dir runs/x                            # dispatch polls to YOUR agents
python engine.py submit --dir runs/x --file replies.json
python engine.py report --dir runs/x
```

Raw per-trial data: `reports/*.json` in this directory (committed);
full states/traces under `runs/` (local, gitignored).
