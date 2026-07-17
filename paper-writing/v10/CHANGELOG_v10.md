# STJP paper v10 — changes from v9

v10 = v9 plus two things: a **new title** and the **integration of the
real-skills live-run program** (docs/results RESULT_8–RESULT_11, the last
two dated 2026-07-15) that v9 predated. v9's structure, section numbering,
seam results template, and every v9 claim are preserved.

## 1. New title

- OLD (v8/v9): *"Guarantees, Not Averages: Type-Checking Agent
  Conversations with Multiparty Session Types"*
- NEW (v10): *"Compile the Conversation: Multiparty Session Types Make
  Multi-Agent Coordination Provably Safe — and Cheaper than Failure"*

Rationale:
- **"Compile the Conversation"** is the paper's actual thesis stated as an
  action — it answers the intro's own framing question ("can we type-check
  the conversation itself, before any agent runs?") and echoes the
  abstract's closing line ("compiled enforcement is a property").
  "Guarantees, Not Averages" named a *contrast* but not the *method* or the
  *object*; a reader could not tell from the old title what the system does.
- **"Multiparty Session Types"** is retained verbatim for search/reviewer
  keyword matching.
- **"Provably Safe — and Cheaper than Failure"** carries both headline
  claims, and "cheaper than failure" is now *literally measured*, not
  rhetorical: in RESULT_10 (`pr_review_merge`) the plan-as-text arm
  livelocks through its whole 16-round budget at 3.6× the token cost of
  the STJP arm that succeeds — failing costs more than succeeding safely.
  This is a stronger economic claim than v9's "the property is cheaper"
  (which compared two *successful* arms).

Alternative titles considered (kept here for the record):
- *"Cheaper Than Failure: Type-Checking Agent Conversations with
  Multiparty Session Types"* — leads with the hook but drops "compile".
- *"The Missing Compiler: Static Session Types for Free-Running LLM
  Agents"* — strong hook, but "missing compiler" undersells the empirical
  program.

## 2. New content — "Real skills, run live: nine cases and a livelock" (§7, anchor sec:real)

A new bold-paragraph block + Table `tab:realcases`, inserted at the end of
§7 (The Validation Suite at n=100), after E6/E7 and before the
pre-registration/audit paragraph. Integrates:

- **RESULT_8** (2026-07-06): four cases from OpenAI Agents SDK / LangGraph
  / AutoGen / CrewAI sources — unmodified files 0/10 in all four
  (deadlock/stall); plan-as-text completes but with 10/10 double
  seat-writes and 10/10 double charges; STJP 10/10, 0 disasters, cheapest.
- **RESULT_9** (2026-07-08): two-model sweep (120 trials) — the no-plan
  coin flip *reverses direction* between Haiku and Sonnet (10/10 vs 0/10
  flipping to 0/10 vs 10/10); STJP identical on both models. Feeds the
  "capability relocates the failure, it does not fix it" clause,
  replicating E3 on found artifacts.
- **RESULT_10** (2026-07-15, `pr_review_merge`): first live run of a
  `rec`/nested-`choice` protocol with a two-approval join; the headline
  **livelock** finding — bare arm 0/10, all 10 trials burn the full
  16-round budget, 530 rule-breaking messages, ~42k tokens/trial, 3.6×
  the cost and 5.3× the calls of the succeeding STJP arm (10/10, 0
  violations, 7 rounds). Also the two static Scribble rejections
  ("inconsistent external choice subjects", "role progress violation")
  that debugged the protocol before any agent ran.
- **RESULT_11** (2026-07-15, `doc_coauthor_ship`): sibling looping case —
  unchecked 0/10 (budget exhausted), bare 10/10 with 220 violations, STJP
  10/10 clean and ~40% cheaper, running the reader-test loop more than
  once before shipping.

Honesty notes carried into the paper text: (a) the earlier `pr_merge` /
`doc_pipeline` casts had misread their source files, and the corrected
cases move the loop/gate to where the sources actually put them; (b) the
runs are n=10/arm with round-batched role-play, so same-role trials within
a round share a model context (also added to Limitations).

## 3. Ripple edits (all small, no restructuring)

- **Abstract**: one sentence added after the circular-wait sentence —
  nine real-source cases run live; found files deadlock/stall/coin-flip;
  the looping code-review case livelocks under plan-as-text at 3.6× the
  cost of the enforced arm ("failing costs more than succeeding safely").
- **Contribution 3**: one sentence added — the wild replication and the
  fourth regularity (text plans fail both ways on looping protocols:
  deadlock without, livelock with), with \S\ref{sec:real}.
- **Conclusion**: one sentence added mirroring the same finding.
- **Limitations** ("Statistics and scope"): scope note for the
  round-batched real-case runs.

## 4. Not changed

- Section numbering, the §8 seam program, seam_results.tex and its 26
  macros, all figures, the bibliography (no new entries needed — sources
  are cited via deep links in the repo's docs, consistent with how the
  ladders cite their data map), and every v9 number.

## Sanity pass (no texlive in this sandbox; same discipline as v9)

- `\begin`/`\end`: 41/41, per-environment balanced.
- Braces (verbatim/comments stripped): 1172/1172.
- Citations: 49 used, 49 defined, 0 undefined; `\ref`/`\label`: 0 undefined.
- All `\seam*` macros used are defined in seam_results.tex.
- New `tab:realcases`: 10 rows × 5 columns, consistent.
