# Provenance — github/awesome-copilot role instruction files

- **Source repo:** https://github.com/github/awesome-copilot
- **Branch fetched:** `main`
- **Fetch date:** 2026-07-08
- **License:** **MIT License** — permissive. Read from
  https://raw.githubusercontent.com/github/awesome-copilot/main/LICENSE
  ("Copyright GitHub, Inc." / "Permission is hereby granted, free of charge ...").
  A verbatim copy is saved next to this file as `LICENSE`.
  Because the license is permissive, the selected instruction files were saved (per task step 7).

## Commit SHA — NOT AVAILABLE (could not be retrieved honestly)

The exact commit SHA of `main` could **not** be recorded. In this session the egress
policy blocks every GitHub host that exposes commit metadata:

- `api.github.com` → 403 `{"message":"GitHub access to this repository is not enabled for this session. Use add_repo to request access."}`
- `github.com` (incl. the `commits/main.atom` feed) → same 403 body
- `codeload.github.com` (tarball, whose top-level dir encodes the short SHA) → 403 same body
- `data.jsdelivr.com` / `cdn.jsdelivr.net` (GitHub CDN mirror that resolves a branch to a SHA) → CONNECT tunnel 403

Only `raw.githubusercontent.com` is reachable, and it serves file content with no commit SHA
(its `ETag` is a content SHA-256, not a git commit). Per the task's "accuracy matters more than
success" instruction, no SHA is fabricated. All files below were fetched from the `main` branch
raw endpoint on the fetch date above. Note: the repo has been restructured — customization files
now live under `agents/*.agent.md` (plus `instructions/*.instructions.md`); the older
`prompts/` and `chatmodes/` directories referenced in the task no longer exist on `main`.

## Selected files — a code-review-and-merge team (5 distinct roles)

All chosen files are self-contained prose instructions. Together they staff a small
change → review → merge pipeline with non-overlapping roles.

### 1. Author (prepares/revises the change in response to review)
- **File saved:** `address-comments.agent.md`
- **Source:** https://raw.githubusercontent.com/github/awesome-copilot/main/agents/address-comments.agent.md
- **Role fit:** The "Universal PR Comment Addresser" — the change author working the review loop:
  applying reviewer feedback, pushing back when a comment is wrong, adding tests, and committing.
- **Quote:**
  > Your job is to address comments on your pull request.
  > Reviewers are normally, but not always right. If a comment does not make sense to you, ask for more clarification.

### 2. Code reviewer (line-level quality / correctness, merge triage)
- **File saved:** `code-review-generic.instructions.md`
- **Source:** https://raw.githubusercontent.com/github/awesome-copilot/main/instructions/code-review-generic.instructions.md
- **Role fit:** General-purpose code reviewer that triages findings by severity and explicitly
  gates the merge on critical issues (security, correctness, breaking changes, data loss).
- **Quote:**
  > ### 🔴 CRITICAL (Block merge)
  > - **Security**: Vulnerabilities, exposed secrets ...
  > - **Correctness**: Logic errors, data corruption risks, race conditions

### 3. Security reviewer
- **File saved:** `se-security-reviewer.agent.md`
- **Source:** https://raw.githubusercontent.com/github/awesome-copilot/main/agents/se-security-reviewer.agent.md
- **Role fit:** Dedicated security-review specialist (the "SE: Security" team agent) focused on
  OWASP Top 10, Zero Trust, and LLM/ML threats — the security gate on the change.
- **Quote:**
  > Review code for security vulnerabilities with focus on OWASP Top 10, Zero Trust principles,
  > and AI/ML security (LLM and ML specific threats).

### 4. Architecture reviewer
- **File saved:** `se-system-architecture-reviewer.agent.md`
- **Source:** https://raw.githubusercontent.com/github/awesome-copilot/main/agents/se-system-architecture-reviewer.agent.md
- **Role fit:** The "SE: Architect" team agent — validates design/scalability/reliability of the
  change against Well-Architected frameworks, distinct from line-level and security review.
- **Quote:**
  > Review and validate system architecture with focus on security, scalability, reliability,
  > and AI-specific concerns. Apply Well-Architected frameworks strategically based on system type.

### 5. Merge decider / technical lead
- **File saved:** `principal-software-engineer.agent.md`
- **Source:** https://raw.githubusercontent.com/github/awesome-copilot/main/agents/principal-software-engineer.agent.md
- **Role fit:** Principal-engineer guidance ("as if you were Martin Fowler") balancing craft vs.
  pragmatic delivery — the senior voice who weighs the reviews, assesses risk/tech-debt, and
  makes the ship/hold call.
- **Quote:**
  > Balance engineering excellence with delivery needs - good over perfect, but never compromising
  > on fundamentals
