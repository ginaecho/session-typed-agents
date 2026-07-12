# Source provenance — code_execution

The `skills_original/` files are adapted from the public, MIT-licensed AutoGen
two-agent code pattern (an assistant that writes code and a code-executor agent
that runs it). The unsafety is a property the source configuration already has:
in the common setup the executor auto-runs received code (human_input_mode set
to never), with no review gate — the role prompts themselves do not require a
reviewer's approval before execution.

| File | Source repo | Basis | License | Retrieved |
|---|---|---|---|---|
| Coder.md | microsoft/autogen | AssistantAgent "write code to solve the task" role | MIT | 2026-07-06 |
| Executor.md | microsoft/autogen | CodeExecutor / UserProxy auto-execute role | MIT | 2026-07-06 |
| Reviewer.md | (derived) | the human/review gate that the auto-execute config omits | MIT | 2026-07-06 |

Safety review: benign coding-assistant coordination only. No secrets, no
exfiltration, no jailbreak content. (The point of the case is that the SOURCE
config runs unreviewed code — the demo shows STJP forcing the review gate.)

## Verified URL and a license correction (added 2026-07-12, W20 source verification)

Repo: https://github.com/microsoft/autogen — **the repo's root `LICENSE`
file is CC-BY-4.0 (Creative Commons Attribution 4.0 International), not
MIT** — verified live. The code itself is separately MIT-licensed under a
different file, `LICENSE-CODE`, also verified live:
https://github.com/microsoft/autogen/blob/main/LICENSE-CODE. So the "MIT"
claim above is defensible for the code specifically, but citing the repo's
root LICENSE alone (as a casual check would) gives the wrong SPDX id — say
"MIT (LICENSE-CODE)" rather than plain "MIT" going forward. No single file
path was recorded above, so no exact-file permalink can be constructed
without guessing; this is a repo-level "adapted-from" attribution. See
`docs/reference/MINED_SKILLS_SOURCES.md` Part B.
