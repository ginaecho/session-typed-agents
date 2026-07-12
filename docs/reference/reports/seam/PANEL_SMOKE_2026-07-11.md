# Panel smoke — first real faithfulness run (2026-07-11)

First live execution of the §5 faithfulness panel — a smoke test (a quick
end-to-end check) of the panel design: 3 gold (a known-correct reference
answer) (intent, G) pairs from the named cases + 1 swapped-pair canary (a
planted check item with a known correct answer), judged by 14
stateless subscription-subagent seats (no API key — the seats are
session subagents with schema-forced JSON verdicts). Seats per case:
J-fwd (Opus 4.8, roles/flow rubric) + J-fwd (Sonnet 5,
ordering/prohibitions rubric) + J-back (Sonnet 5, protocol-only blind
reconstruction) + comparator (Haiku 4.5). Runtime ~3.5 min, ~360k
subagent tokens end to end.

## Verdicts

| case | fwd Opus | fwd Sonnet | back score | outcome |
|---|---|---|---|---|
| banking | yes (0.72) | yes (0.83) | 0.72 | PASS with notes |
| trade_deadlock | yes (0.88) | yes (0.82) | **0.25** | **ESCALATE — class conflict** |
| travel | yes (0.86) | yes (0.78) | 0.68 | PASS with notes |
| canary (banking intent × travel G) | **no (0.99)** | **no (0.99)** | — | canary PASS |

## What the run demonstrated

1. **The canary discipline works.** Both seats rejected the mismatched
   pair at 0.99 — the instrument is not a rubber stamp.

2. **The class-decorrelation design earned its keep on case one.**
   trade_deadlock is the repo's deliberately deadlock-shaped intent
   ("Buyer releases payment only after goods received; Seller releases
   goods only after payment") whose canonical protocol implements the
   deadlock-FREE escrow (a neutral third party that holds funds until both
   sides deliver) linearization. Both forward seats rationalized
   this as faithful (yes 0.88/0.82) — reading the escrow sequence as
   realizing the intent's constraints. The blind J-back seat, unable to
   see the intent, reconstructed "a strictly linear escrow happy-path"
   and the comparator scored it 0.25 against the original — surfacing
   that the protocol implements a *repair* of the intent, not the
   intent as written. This is precisely the confirmation-bias failure
   J-back exists to catch, observed live on the first run. Escalated
   per §5.3: whether "protocol fixes the intent's deadlock" counts as
   faithful is a policy question for the human gate, not a vote.

3. **Judges produced real findings, not vibes.** Banking: seats flagged
   the SmallTransfer notice to Approver as an addition beyond the
   intent, and correctly observed the $10k threshold cannot be
   structurally enforced by a session type (value constraints live in
   the .refn/monitor layer — matches the repo's own architecture).
   Travel: seats flagged that availability/budget criteria are not
   represented in message payloads (quotes are bare Doubles), so the
   all-or-nothing decision rests on unmodeled Coordinator logic — a
   genuine faithfulness gap between intent and structure.

4. **Transport decision validated.** Subscription subagents serve as
   panel seats with full isolation semantics (fresh context per seat,
   sanitized payload only, schema-forced verdicts, no inter-seat
   visibility). API-key transport is only required when judging must
   run headless off-session (the T2/T3 GPU reward path).

## Operational notes

- One J-back reconstruction carried a trailing structured-output
  artifact ("</reconstructed_intent>...") — harmless here; W6's seat
  transport must strip trailing tag debris before comparison.
- Cost projection: full 23-pair calibration sweep ≈ 8× this run ≈ 2.5–3M
  subagent tokens — comfortably feasible per phase gate.
- Aggregation here was simple vote/score display; the merged W6 package
  (geometric median -- a robust way to combine scores so one extreme judge
  cannot drag the result -- evidence verification, effective-votes) takes over
  for calibration runs.
