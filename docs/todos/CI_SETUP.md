# TODO: Add CI (test suite + path-portability guard)

**Status:** proposed, not implemented
**Raised:** 2026-07-29
**Owner:** _unassigned_
**Motivation:** the Windows `git clone` failure (see history below)

---

## Background — why this is on the list

A colleague's `git clone` failed on Windows with:

```
error: unable to create file experiments/seam_bench/mining/samples/llm_read_evidence/09_explicit_ref_github_awesome_copilot_agent_safety_...prompt.json: Filename too long
fatal: unable to checkout working tree
```

One committed file had a **282-char repo-relative path** (226-char basename),
built from an unbounded 1:1 slug of a large team's `team_id`. Windows caps a
full absolute path at `MAX_PATH` = 260, so the clone downloaded the objects but
failed to check out the working tree.

Two fixes have already landed / are in flight:

- **PR #22 (merged):** renamed the one offending file to
  `09_..._agent_safety_gem_team.json` (121 chars). Full `team_id` is preserved
  inside the file, so nothing was lost.
- **PR #24:** capped the slug generator (`experiments/seam_bench/mining/slug_util.py`)
  at 96 chars + a hash suffix, so regenerating the artifacts can't reintroduce
  an over-long name.

Those fix the *known* instance and its generator. **CI is the missing net** that
would catch any *future* Windows-hostile path before it reaches someone's clone —
and, separately, would run the 54 test files this repo already ships but never
executes automatically.

Current state: **no CI exists** — no `.github/workflows/`, no CircleCI / GitLab /
Azure Pipelines config anywhere on `main`.

---

## Proposed check 1 — path-portability guard (highest value)

Fail the build if any tracked path is hostile to a Windows checkout. This is the
direct defense against the bug above; it would have caught the 282-char file
automatically.

Rules to enforce over `git ls-tree -r --name-only HEAD`:

| Rule | Rationale |
|---|---|
| repo-relative path length ≤ ~200 chars | leaves headroom under `MAX_PATH` (260) once a clone dir prefix is added |
| no path component > 255 chars | NTFS per-name limit |
| no `: * ? " < > \|` in any component | illegal on Windows |
| no reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) | reserved on Windows |
| no trailing dot/space in a component | silently stripped on Windows |
| no case-only collisions (two paths equal after lowercasing) | break on case-insensitive filesystems |

A standalone script (e.g. `tools/check_path_portability.py`) that exits non-zero
on a violation is enough; it needs no dependencies and can also be wired into a
pre-commit hook. The manual scan in the session that raised this
(length / illegal chars / reserved names / trailing dot-space / case collisions)
is the reference implementation to port.

**Acceptance:** running the check on current `main` passes; deliberately adding a
300-char filename makes it fail with a clear message.

---

## Proposed check 2 — run the existing test suite on PRs

The repo has **54 `test_*.py` files** (mining, judge, eval, data, ...) that no
automation runs. A minimal GitHub Actions job would gate them on every PR.

Notes for whoever implements it:

- Dependencies are split across several files — `stjp_core/requirements*.txt`
  and per-component `requirements.txt`. The job likely needs
  `stjp_core/requirements-core.txt` (+ `pytest`) at minimum; confirm which
  suites need which extras and whether any require Java/Scribble
  (`experiments/seam_bench/mining/tests/test_formalize.py` touches formalization).
- Some tests may need network or heavy optional deps — scope the first pass to
  the fast, self-contained suites (e.g. `experiments/seam_bench/mining/tests/`,
  `experiments/seam_bench/judge/tests/`) and expand from there.
- `pytest` is not currently installed in the default dev image — add it to a
  dev/test requirements file as part of this work.

**Acceptance:** PR #24's `experiments/seam_bench/mining/tests/test_slug_util.py`
runs green in CI; a deliberately broken test turns the check red.

---

## Sketch (for reference — do not treat as final)

`.github/workflows/ci.yml`:

```yaml
name: ci
on: [pull_request, push]
jobs:
  portability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python tools/check_path_portability.py

  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pytest -r stjp_core/requirements-core.txt
      - run: pytest -q experiments/seam_bench/mining/tests experiments/seam_bench/judge/tests
```

## Decisions still open

- Where CI runs (GitHub Actions assumed; confirm that's the intended platform).
- Whether the portability guard also runs as a local pre-commit hook (`.githooks/`
  already exists in the repo — could hang it there too).
- How much of the 54-file suite to gate in the first pass vs. expand later.
