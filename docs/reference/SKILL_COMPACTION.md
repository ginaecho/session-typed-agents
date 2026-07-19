# Skill Compaction — validating skills that ALREADY exist (bottom-up STJP)

The forward STJP pipeline starts from intent:

```
intent ─► LLM drafts global type ─► Scribble ─► projection ─► generated skills
```

But most teams already **have** skills — Claude skills, agent specs, prose
instruction sheets — written by hand, one per agent, never checked against
each other. The [`trade_deadlock`](../../experiments/cases/trade_deadlock/) case shows why that matters: the Buyer's
skill ("don't pay until goods arrive") and the Seller's ("don't ship until
paid") each read fine alone and deadlock together.

Skill compaction is the **bottom-up** entry point, implemented 2026-07-04:

```
existing skill .md (one per agent)
      │  COMPACT — reduce each skill's prose to its checkable
      │  interaction block: sends, receives, ordering, branching
      ▼
LocalType per role                        compiler/local_type.py
      │  COMPATIBILITY — sends↔receives duality across all roles
      ▼
deterministic global synthesis            compiler/global_synthesizer.py
      │  (LLM fallback for out-of-fragment shapes)
      ▼
global .scr ─► Scribble validates ─► the EXISTING skills are proven
                                      safe-or-unsafe BEFORE any run
```

Entry point: `stjp_core/generation/skill_compactor.py`.

```bash
python -m stjp_core.generation.skill_compactor <skills_dir> -o Trade.scr \
    --protocol Trade            # add --no-llm for deterministic-only sources
```

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Compaction — skill markdown → LocalType](#1-compaction--skill-markdown--localtype)
- [2. Compatibility — the cheap cross-check](#2-compatibility--the-cheap-cross-check)
- [3. Synthesis — local types → global type, deterministically](#3-synthesis--local-types--global-type-deterministically)
- [4. Scribble — the final oracle](#4-scribble--the-final-oracle)
- [5. Tests](#5-tests)
- [6. Research basis](#6-research-basis)
<!-- MENU:END -->

## 1. Compaction — skill markdown → LocalType

Per file, three sources are tried in order:

1. **Fenced ` ```localtype ` block** — an author-provided exact contract:
   ```localtype
   Escrow!Deposit(Double);          // send
   Carrier?DeliverGoods(String);    // receive
   choice {
       Escrow!ConfirmReceipt(String);
   } or {
       Escrow!RaiseDispute(String);
   }
   ```
   Parsed deterministically; no LLM involved.
2. **The STJP `*_skills.md` format** — parsed deterministically via
   `generation/skills_parser.py`, with the Execution Flow section providing
   ordering. Marked `confidence: low` when the flow section doesn't cover
   every declared message.
3. **The LLM** — for arbitrary prose. It emits the LocalType JSON schema
   (role, ordered flow of send/recv/choice items, confidence, notes); the
   reply is parsed and structurally re-validated, with parse errors fed back
   for retry. The LLM **never** gets to declare the result safe — that stays
   with the deterministic pipeline below.

The `LocalType` (role, body of `LAction`/`LChoice` nodes) **is** the
"compacted block": a local session type reconstructed from prose. Each one is
persisted next to the output (`local_types/<Role>.localtype.{json,txt}`) so a
human can diff what the compactor understood against what the skill says.

## 2. Compatibility — the cheap cross-check

`check_compatibility()` runs the duality pre-check across all local types
before any synthesis (*duality* is the simple idea that every send must be
mirrored by a matching receive on the other side): every send must have a matching receive (same
sender/receiver/label), payload types must agree, no unknown peers. This is
the multiparty generalisation of two-party duality and catches the crude
authoring bugs (typo'd labels, one-sided messages, "who is 'the seller'?")
with pinpoint messages, for free.

## 3. Synthesis — local types → global type, deterministically

`global_synthesizer.synthesize_global()` runs a product construction over
the roles' programs (it steps all the roles' state machines forward
together in lockstep, emitting a global step whenever a send and its
matching receive line up):

- a communication is emitted when a role's next action is a send and the
  receiver can accept it as its next action (entering an external-choice
  branch if needed);
- a role whose next node is a choice with all-send branch heads is an
  **internal choice**: the synthesizer emits `choice at R`, recurses per
  branch, then factors the longest common brace-balanced suffix out of the
  block (Scribble's external-choice-subject discipline);
- if nothing is enabled and roles aren't finished, synthesis **fails with a
  per-role diagnosis** — this is the circular wait, caught at composition
  time with each role's "waiting for X from Y" printed:

  ```
  synthesis stuck — no enabled communication (would-be deadlock ...):
    Buyer:   wait for DeliverGoods(String) from Carrier
    Carrier: wait for ShipGoods(String) from Seller
    Seller:  wait for Payment(Double) from Buyer
  ```

Out-of-fragment shapes (mixed choices, recursion, non-linearisable
interleavings) raise `SynthesisError`; with an LLM available the pipeline
falls back to an LLM synthesis loop **over the compacted local types** (not
the raw prose), with Scribble judging each attempt — the
`generation/skills_synthesizer.py` posture, but fed formal inputs.

## 4. Scribble — the final oracle

Whatever produced the global `.scr` (deterministic or fallback), the Scribble
compiler validates it last. Only a Scribble-accepted protocol is reported
`valid` — from there the standard forward pipeline applies (projection,
contracts, monitors, benchmark arms).

## 5. Tests

`stjp_core/tests/test_skill_compactor.py` — offline: fenced-block parsing
(with choice), compatibility mismatch detection, deterministic synthesis of
the 4-role escrow trade (escrow: a neutral third party that holds funds
until both sides deliver; Scribble-valid, escrow-first ordering
reconstructed), internal choice with common-suffix factoring
(Scribble-valid), the circular-wait diagnosis, the LLM path via an injected
fake client, and STJP-format extraction.

## 6. Research basis

- **Lange & Tuosto — *Synthesising Choreographies from Local Session Types*
  (CONCUR 2012)**: synthesising a global type from local types, the formal
  problem this pipeline solves after compaction.
- **Deniélou & Yoshida — *Multiparty Compatibility in Communicating
  Automata: Characterisation and Synthesis of Global Session Types*
  (ICALP 2013)**: multiparty compatibility (the §2 pre-check) and synthesis
  from communicating automata.
- **Honda, Yoshida, Carbone (POPL'08)**: the guarantees the validated result
  inherits (deadlock-freedom, communication safety).
- `generation/skills_synthesizer.py` is the earlier all-LLM reconstruction of
  the same direction; compaction inserts the formal LocalType layer in the
  middle so most of the work becomes deterministic and auditable.
