# STJP paper v10 — changes from v9

## v10.2 (2026-07-26) — clarity and presentation pass (no numbers changed)

Purpose: address reader feedback that the paper was hard to follow. No
experimental number, claim, or table value was added or changed; every edit
is presentational. All edits in `main.tex` (plus title lines in the READMEs).

1. **Title** — "Compile the Conversation …" → "Compiling the Coordination
   Protocols of Multi-Agent Systems: …". "Conversation" wrongly suggested
   runtime chat; the object being compiled is the statically defined
   interaction protocol. The intro's framing question was reworded the same
   way, and remaining uses of "conversation" for the protocol/session were
   replaced throughout (§3, §4 conclusion).
2. **Professional terminology for the artifact class** — "skill files, agent
   markdowns, and specification documents" are now *examples* of a named
   class, "natural-language coordination artifacts" (abstract, intro ¶1,
   contribution 1, conclusion).
3. **Abstract rewritten for story and readability** — problem → mechanism →
   scenario ("a financial-reporting team in which an audit and an approval
   must precede an irreversible filing") → the three findings, each stated
   in plain language before its numbers (63% fewer tokens; 73% fewer calls;
   9× per successful run; 4–22× per violation-free run; 95/100 vs 0
   unauthorized irreversible acts; the livelock and static-deadlock stories;
   95.1% mutation detection; 100% vs 41.7% exfiltration blocking).
4. **Every abbreviation expanded at first use** — LLM, MPST, EFSM (endpoint
   finite-state machine), MCP, DSL, SMT, MSC, LTL, CuP, FIFO, GCR, CGC, GCD
   (grammar-constrained decoding), SFT, RL, GRPO, LGA, AUC, CI, pass^k, LoRA,
   +CF, T0.
5. **Every label family explained at first use** — pipeline stages S1–S5
   ("S" for stage, explicitly distinguished from severity grades S0–S4, "S"
   for severity); experiments E0–E10 ("E" for experiment) with a new lead
   paragraph in §7 stating the question each experiment answers; theorems
   T1–T4; predictions P1–P5; hypotheses H1–H6.
6. **Scenario story added at the top of §6** — the six-role finance case,
   why filing-before-approval is the failure that matters, and what an
   "arm" is (defined in §5.3 with the clinical-trial analogy and the
   information-ladder reading of A/B/C/C-min/C+).
7. **Citations renumbered by order of first appearance** — the manual
   thebibliography was reordered so [1], [2], [3] … follow the text
   (natbib numbers by list position); the one uncited entry (owasp) sits
   last. Verified: clean compile, 0 undefined citations/references.
8. **E6 scaling paragraph rewritten** — explains that "roles" are
   participating agents, what the structural proxy is, and why the
   9.2×→17.1× widening from two to ten roles means the advantage grows
   with team size; `tab:ctcg` caption now defines the arm abbreviations.

## v10.1 (2026-07-19) — fairness-audit alignment, statistical rigor, reproducibility

Purpose: bring every claim in line with the 2026-07-17 benchmark fairness
audit (`docs/BENCHMARK_FAIRNESS_REVIEW.md`) and ICLR statistical/reporting
norms. No experimental number was added or changed; only qualifications,
pending-framed ablations, and reporting infrastructure. All edits in
`main.tex`.

1. **Abstract** — the "cuts LLM calls by 73%" scheduler claim is now scoped
   "relative to round-robin polling", with a note that a protocol-free
   scheduling control is pre-registered. (The 9× / 73% numbers are tokens
   and calls, unaffected by the audit's wall-clock finding, so they stand.)
2. **§5.1 (goal achievement)** — new passage defining the **per-arm fair
   success rule**: strict label-matching for arms shown the protocol
   vocabulary, the role-pair rung for bare arms (right sender, right
   receiver, predicate-satisfying payload, any label), with the
   essay-answer-key example explaining why strict-for-everyone was unfair.
   States that pre-fix tables report strict for all arms, are labeled, and
   that bare-arm scores are lower bounds pending re-runs.
3. **§5.3 (arms and fairness)** — three new binding rules: Wilson 95%
   intervals printed at n≤10 (with the 0% vs 40% overlap example);
   answer-key invariance guard (relabel-only re-anchoring, human sign-off
   for forced payload-type translations, the two corrected finance
   predicates); one-time setup cost (drafting/re-anchoring) disclosed.
4. **Table captions** `tab:ladder`, `tab:gate`, `tab:grand` — strict-rule
   caveat (A's 0% is a lower bound), concrete Wilson 95% intervals for the
   cells shown, and "seconds are from contended parallel execution,
   indicative only" labels. Gate caption also flags the hint-free ablation.
5. **§6.2 / §6.4 body** — the −28% time and 32s/trial wall-clock figures
   labeled as contended-parallel/indicative; the scheduler win explicitly
   scoped against round-robin with the last-receiver control named as the
   opponent it must beat next (on branching/fan-in, not linear pipelines).
6. **New §6.5 "Fairness audit, corrected metrics, and pre-registered
   ablations" (`sec:fairaudit`)** — plain-language account of the audit's
   five findings and fixes: (1) strict-rule unfairness → per-arm rule;
   (2) drifted answer keys → invariance guard (with the `"true" in x`
   /"untrue" example and the forced Bool-translation nuance); (3) shared
   stopwatch → `--sequential` mode + execution-mode stamping, speed claims
   withheld; (4) cheap-scheduler control arm `min_llmvalid_gate_lastrecv`
   (offline linear-flow simulation: 3 sends in 3 polls — the linear case
   is conceded; pre-registered prediction: control ties on
   `report_pipeline`, loses on `finance_nested`/`intel_report`/`auction`);
   (5) hint ablation arm `min_llmvalid_gate_nohint` (prediction: zero
   disasters preserved, some liveness lost). All framed pending — **no
   invented numbers**, same discipline as the seam template.
7. **Limitations** — four additions: n≤10 CI overlap (re-run headline
   claims at n≥30); scoring-rule history (strict-rule tables are lower
   bounds for bare arms; contended wall-clock carries no comparative
   claim); no tools / invented data (C1 provenance certifies message
   discipline, not data lineage; tool-served-data variant named);
   single-deployment headline runs (`gpt-5.4` is an unverifiable
   user-set deployment name).
8. **Appendix B (Reproducibility)** — expanded from three lines to a full
   statement: repo layout, runner command with `--sequential`, what
   summaries record (success_rule, execution_mode, CIs, truncation,
   prompt checksums), determinism boundary (stochastic hosted role-players,
   bit-reproducible evaluators), and cost estimates per
   `docs/reference/COST_ESTIMATES.md` (~$20–45 full finance run on gpt-4o;
   <$100 for the 1,200-trial suite).
9. **§6.3** — "0% completion" for the A arm annotated as strict-rule lower
   bound.

Compile status: pdflatex is not installed in this container; a static
check passed (braces 1263/1263 balanced, all environments matched, 0
undefined refs, 0 undefined cites). Re-compile before submission.


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

## Compile status

texlive-latex-base/-extra/-recommended, texlive-fonts-recommended, and
texlive-bibtex-extra were installed and both v9 and v10 were compiled with
two `pdflatex` passes each (no `bibtex` needed; the bibliography is
inline via `\begin{thebibliography}`).

- **v9/main.pdf**: 21 pages, 0 undefined references, 0 undefined
  citations (previously verified only by static grep/brace-balance; now
  confirmed by an actual compile).
- **v10/main.pdf**: 23 pages, 0 undefined references, 0 undefined
  citations. The new `tab:realcases` table initially overflowed its
  column width by 28pt; tightened to `\footnotesize` with three cells
  shortened (``double writes''→``dbl.\ writes'', etc.) and re-verified
  clean — the remaining overfull hboxes (5--12pt, five instances) are
  pre-existing in v9 and unrelated to this table.

Static sanity pass (superseded by the compile above, kept for the record):
`\begin`/`\end` 41/41 balanced; braces 1172/1172; citations 49 used/49
defined/0 undefined; all `\seam*` macros defined; `tab:realcases` 10
rows × 5 columns.

## Update 2026-07-17 — second retitle + abstract rewrite; v6–v9 removed

- **Title (final)**: *"Compile the Conversation of Multi-Agent
  Coordination: Provably Safe and More Token-Efficient"* — replacing the
  interim v10 title ("... Provably Safe — and Cheaper than Failure").
  Direction set by the author: lead with token efficiency alongside
  provable safety. (Grammar lightly normalized from the requested
  "Provable Safe and More Token Efficiency".)
- **Abstract rewritten** in the same direction. Same opening (missing
  compiler) and same closing cadence, but the empirical middle is now
  organized around the three token classes the compiler removes:
  (i) prose re-reading → projection (63% fewer tokens; 9.2×→17.1×
  structural gap from 2→10 roles); (ii) polling → scheduling (−73% LLM
  calls, 9× cost-to-goal, 4–22× cost-to-clean-goal, zero unauthorized
  irreversible acts at every tier vs up to 95/100 unenforced);
  (iii) failure itself → enforcement (nine real-skills cases where found
  files deadlock/stall/coin-flip; the 3.6× plan-as-text livelock; the
  zero-token static rejection — "the cheapest failure is the one that
  never runs"). Closing line updated: "...and the property spends fewer
  tokens."
- **v6–v9 removed** from the working tree (git history retains them);
  paper-writing/README.md rewritten for the single-version layout.
- Recompiled: two pdflatex passes, 0 undefined references/citations.
