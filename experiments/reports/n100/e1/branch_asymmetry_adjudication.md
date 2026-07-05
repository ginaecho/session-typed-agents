# E1 — branch_asymmetry survivor adjudication (P-1 item 4, 2026-07-05)

The E1 mutation bench reported `branch_asymmetry`: 63 applied, 52 caught, **11
survived → 82.5%** detection. The 82.5% was left unclassified. This resolves it:
each of the 11 survivors is either a **genuine checker gap** (Scribble accepted
a truly ill-formed protocol) or an **accidentally-valid** mutant (the deletion
left a still-well-formed protocol, so acceptance is *correct*).

Method: the 11 mutants were reconstructed deterministically (seeded RNG replay,
saved under `_survivors/`), re-validated against Scribble (all 11 confirmed
ACCEPT — matching the CSV), and each was projected per-role with `-project`.

## Verdict: 4 genuine gaps, 7 accidentally-valid

| mutant | deleted message | branch emptied? | verdict |
|---|---|---|---|
| corpus_016 | `M8(Bool) R1→R4` | **yes** | **GENUINE GAP** |
| corpus_059 | `M6(String) R2→R3` | **yes** | **GENUINE GAP** |
| corpus_080 | `M5(String) R1→R5` | **yes** | **GENUINE GAP** |
| corpus_088 | `M7(Int) R3→R4` | **yes** | **GENUINE GAP** |
| corpus_000 | `M7(String) R3→R1` | no | accidentally-valid |
| corpus_019 | `M12(String) R0→R1` | no | accidentally-valid |
| corpus_035 | `M5(Bool) R2→R1` | no | accidentally-valid |
| corpus_056 | `M8(Double) R2→R0` | no | accidentally-valid |
| corpus_067 | `M6(String) R0→R2` | no | accidentally-valid |
| corpus_072 | `M5(String) R3→R1` | no | accidentally-valid |
| corpus_075 | `M17(Bool) R2→R1` | no | accidentally-valid |

## The genuine-gap defect pattern (reproducible)

When `branch_asymmetry` deletes the **only** message in a branch, that branch
becomes **empty** — e.g. corpus_016:

```
choice at R1 {
    M6(Double) from R1 to R4;
    M7(Bool)   from R4 to R1;
} or { }                        // ← emptied by deleting M8(R1→R4)
M9(Int) from R4 to R5;
```

Scribble accepts this, and `-project Gen R4` returns a local type in which the
empty branch has been **silently dropped**:

```
local protocol Gen_R4(...) {
    choice at R1 {              // ← single branch; the empty alternative is gone
        M6(Double) from R1;
        M7(Bool)   to R1;
    }
    M9(Int) to R5;
    ...
}
```

R4's projection therefore **unconditionally waits for `M6`** — but the global
protocol lets R1 choose the empty branch and never send `M6`. If R1 does, **R4
blocks forever → deadlock**, a liveness violation the checker should reject.
This is knowledge-of-choice failure: R4 participates in one branch but not the
other and is never told which was taken. All four gap mutants
(016/059/080/088) exhibit exactly this — verified in the projected local type
of the idle role (R4, R3, R5, R4 respectively).

The 7 accidentally-valid mutants deleted a message that left **both branches
non-empty**, so every role still distinguishes the branches (the chooser knows;
receivers get distinct first messages). Scribble's acceptance is **correct**
for those — they are not defects.

## Effect on the E1 number

The 7 accidentally-valid mutants are not defects and should not sit in the
"missed defects" denominator. Re-scoping to genuinely-ill-formed
branch_asymmetry mutants:

- caught (rejected, correctly): **52**
- genuinely ill-formed but accepted (real gaps): **4**
- **true detection rate = 52 / 56 = 92.9%** (was a diluted 82.5%)

Two paper-positive outcomes, both predicted in `VALIDATION_TODO.md` §P-1.4:

1. **The detection rate rises** from 82.5% → **92.9%** once accidentally-valid
   mutants are excluded.
2. **A concrete, named limitation to report honestly:** the checker (Scribble
   as invoked) accepts choices with an **empty branch after deletion**, dropping
   it in projection and producing a deadlocking local type for the uninformed
   idle role. Defect pattern: *empty-branch-after-choice → knowledge-of-choice
   deadlock.* Reproducible on corpus_016/059/080/088 (`_survivors/`).

Reproduce: `_survivors/*_{base,mutant}.scr`; validate with
`stjp_core/compiler/validator.py` (unset `JAVA_TOOL_OPTIONS` first — a proxy
env var this VM injects prints to stdout and trips the "silence = success"
parser; Scribble itself needs no network).
