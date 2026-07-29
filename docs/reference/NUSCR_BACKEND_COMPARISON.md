# scribble-java vs coinductive nuscr — and a test-harness bug we fixed

**Date: 2026-07-28.** This records (a) a real bug in our *comparison harness*
found on 2026-07-28, (b) exactly how it was fixed, and (c) the corrected,
robust result. It exists because a first, buggy pass briefly wrote a false
conclusion into `6_RUN_REPORTS_V2` before it was caught — and the honest record
of that mistake is more valuable than hiding it.

## The one-line version

**scribble-java was CORRECT the whole time. Our test harness's judgment of
scribble's output was wrong.** We misread a legitimate *module-name error* as if
it were a *deadlock verdict*, and counted it the wrong way. The fix was in the
harness, not in scribble.

## What happened

We built the coinductive **nuscr** fork (Docker image `nuscr-coind`) to check
whether it catches deadlocks that scribble-java's inductive checker misses —
specifically the `circular_wait` class (reversed message direction), which the
E1 mutation study had flagged as a scribble-java blind spot.

The first comparison wrote each mutated protocol to a temp file with an
arbitrary name, e.g. `c002.scr`. But a Scribble `.scr` file must declare
`module <name>;` and Scribble **requires the file name to match that module
name**. Our mutant of `corpus_002` still declared `module corpus_002;` but sat
in a file called `c002.scr`. So scribble-java returned:

```
valid=False  err='corpus_002(line 1:7): Simple module name at path
                   ...\c002.scr mismatch: corpus_002'
```

That is scribble **behaving correctly** — it refused to compile a file whose
name doesn't match its module declaration. It is *not* a deadlock finding.

## The bug: outcome-capture, not the compiler

Our harness collapsed every `valid=False` into "the backend CAUGHT the injected
deadlock." So the module-name rejections were **miscounted as deadlock catches**,
making scribble-java look like it detected 8/8 circular_wait deadlocks. It
detected none of them — it never got past the name check to even look. The
error was entirely in *how we decided and captured the outcome*:

- We did not distinguish a **name/parse error** (structural, pre-semantic) from
  a **semantic rejection** (well-formedness / deadlock).
- We used an arbitrary temp filename instead of one matching the module.

Both are harness defects. scribble-java's verdicts were each correct for the
input it was actually given.

## The fix (in the harness — `experiments/scripts/backend_compare.py`)

1. **Name each mutant file after its `module` declaration** (`<module>.scr`), so
   scribble parses it and returns a real *semantic* verdict instead of a name
   error.
2. **Exclude name/parse errors from the "caught" count.** A rejection only
   counts as "caught the deadlock" when it is NOT a module-name/parse error
   (`scribble_name_errors_excluded` is reported separately).
3. **Baseline false-positive check:** validate every ORIGINAL protocol with both
   backends first; both must accept them (0 false positives) before any mutant
   number is trusted.

## The corrected result (after fixing BOTH harness bugs)

The first "fix" caught only scribble's name-error miscount. Running the fixed
tool then exposed the SAME bug on the nuscr side: nuscr emits
`"...Non tail-recursive protocol is not implemented"` on protocols it cannot
analyse, and the harness was counting that tool-limitation as "rejected the
deadlock." Excluding nuscr tool-errors too (and verifying a clean 0/30
false-positive baseline for BOTH backends), the trustworthy result on the
corpus (n=30, `backend_compare.json`) is:

| | circular_wait mutants |
|---|---|
| scribble-java | **0 caught** (over the 11 protocols both backends can judge) |
| nuscr (coinductive) | **0 caught** — AND it cannot analyse **19/30** protocols ("non-tail-recursive not implemented") |
| baseline false positives | scribble 0/30, nuscr 0/30 (verified clean) |

**Conclusion — hypothesis REFUTED, this time cleanly:** on the protocols both
backends can actually judge, neither catches these reordering mutants (0 vs 0),
and nuscr is *practically weaker* here because it fails to analyse most of the
corpus. Our earlier "nuscr catches 5/8" was entirely an artifact of miscounting
nuscr's "not implemented" errors as deadlock catches — the identical bug class,
now on the other backend.

Two honest sub-points:
- The `circular_wait` mutation frequently produces an *equivalent-valid* protocol
  (a legal reordering, not a deadlock — e.g. `M1 from R2 to R1` just lets R2 send
  first), so "0 caught" is partly *correct* (nothing to catch), not purely a gap.
- **nuscr does not, on this evidence, strengthen design-time detection over
  scribble-java.** The static circular_wait blind spot (where it is a real
  deadlock) is NOT closed by the coinductive backend in practice.

**What still stands:** `pr_review_merge` and the loop cases validate True under
BOTH backends — they are genuinely deadlock-free. And the practical lesson for
Claim 2 is stronger than ever: **static MPST checking (either backend) is
incomplete, so the runtime gate is the actual guarantee.**

## Why this is worth keeping in the record

Two lessons:
1. **Distinguish structural rejections from semantic verdicts.** A checker
   saying "no" can mean "malformed input" or "genuinely unsafe" — conflating
   them silently corrupts a benchmark.
2. **A surprising result deserves a look at the raw error, not a headline.** The
   correction came only from reading scribble's actual error string. The
   reviewer's "hard to believe it" instinct was the trigger; the fix was to
   verify rather than defend.

Reproduce: `python experiments/scripts/backend_compare.py 30`
(needs the `nuscr-coind` Docker image; build via
`docker build -t nuscr-coind -f tools/nuscr/Dockerfile <nuscr-fork>`).
