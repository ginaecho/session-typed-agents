# R3 — Comparable Datasets & D5 Mining Targets

Scout report for the seam-training program (`docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md`
§3 D5, §7). Date of research: 2026-07-11. All GitHub numbers below are from
live `search_code`/`search_repositories` calls made today; web-search numbers
are from paper abstracts/READMEs fetched today. Every count is an
**order-of-magnitude estimate**, not a certified figure — see the caveat in
Task B's methodology note.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Task A — Comparable NL→formal-spec datasets](#task-a--comparable-nlformal-spec-datasets)
- [Task B — D5 mining targets, sized](#task-b--d5-mining-targets-sized)
  - [1. Claude/agent skills — the proven recipe, scaled](#1-claudeagent-skills--the-proven-recipe-scaled)
  - [2. Multi-agent framework configs](#2-multi-agent-framework-configs)
  - [3. CI/release/review pipelines as protocols — mostly a bad target, say so](#3-cireleasereview-pipelines-as-protocols--mostly-a-bad-target-say-so)
  - [Ranked mining shortlist (top 5, with expected item counts)](#ranked-mining-shortlist-top-5-with-expected-item-counts)
<!-- MENU:END -->

## Task A — Comparable NL→formal-spec datasets

No public NL→MPST/Scribble (choreography/session-type) benchmark exists.
Targeted searches for "choreography specification natural language dataset",
"session types NL benchmark", and "protocol/choreography NL dataset" turned
up **nothing** — this corroborates the execution plan's own §7 claim rather
than contradicting it. The nearest lineages are NL→temporal-logic and
NL→business-process/workflow. Catalog below, ranked by relevance.

| dataset | size | license | format | gold-checker | verdict |
|---|---|---|---|---|---|
| **NL2TL** (Chen et al., EMNLP'23, `yongchao98/NL2TL`) | ~28K NL–TL (STL/LTL) pairs | **Restrictive** — README states "can only be commercially used under our permission"; no OSI license file found | Google-Drive-hosted, format documented only in a PDF | No public formula-equivalence checker shipped; STL/LTL solvers exist externally | **adapt-method** — template-driven NL generation from formal seeds is the closest published analog to our D2 back-translation step, but the license blocks reuse-data or transfer-eval (redistribution/derivative risk) |
| **nl2spec** (Cosler et al., CAV'23, `realChrisHahn2/nl2spec`) | 36 expert-crafted lifted NL–LTL pairs (tiny) | Research repo, no explicit permissive license file confirmed — treat as unclear | Paired examples + interactive-decomposition prompts | LTL equivalence via external LTL tooling | **adapt-method** — the "lift sub-formulas back to NL fragments, let a human/LLM confirm" mechanism is structurally close to our J-back evidence-pointer judge; too small (n=36) and license-unclear for reuse-data |
| **Lang2LTL** (Liu et al., CoRL'22/'23, `h2r/Lang2LTL`) | 2,125 unique LTL formulas / NL commands (robot nav, 47 templates) | Academic repo (H2R lab); not independently re-verified here — flag for a license read before use | JSON, grounded to city/map databases | Yes — trace-level satisfaction checking against grounded environments | **adapt-method only** — different domain entirely (single-robot navigation, not multi-party protocols); the propose-then-ground pipeline (atoms → environment) is reusable methodology, not reusable data |
| **VLTL-Bench** (2507.00877, 2025) | "thousands" of NL specs across 3 state spaces, with sample traces | **CC BY 4.0** (permissive) | Structured NL/LTL pairs + trace validators, decomposed into lift/ground/translate/verify stages | Yes — trace-based verification is a first-class benchmark component | **run-as-transfer-eval candidate** — wrong formalism (LTL, single-agent-oriented) but permissive license and an explicit lift→ground→translate→verify decomposition that maps cleanly onto our J-probe design; worth a light adapter to sanity-check T's general formal-translation competence outside Scribble |
| **DeclareNL / Declare-constraint corpus** (Expert Systems w/ Applications, 2025) | 969 labeled sentences, 11 Declare templates | Journal article (ScienceDirect); dataset availability not confirmed as open — access friction | Labeled text→constraint pairs | Declare constraint checkers exist (process-mining tooling) | **adapt-method, low priority** — Declare constraints are single-relation (not whole multi-party orderings), and the dataset sits behind a paywalled article; note the methodology (LLM-extracted declarative constraints from prose) as a precedent for our D3 mutation/near-miss framing, but do not plan on reuse-data given access friction |
| **FLOW-BENCH** (IBM, arXiv 2505.11646, `IBM/flow-bench`) | 101 incremental-build test cases, NL→BPMN/DMN | **CC BY-SA 4.0** (permissive but **share-alike** — any derivative release inherits the SA clause; flag before folding into Seam-Bench) | NL utterances + structured process definitions + constrained-Python IR | Yes — executable check via the Python-subset intermediate representation | **adapt-method (strong) + run-as-transfer-eval (flagged)** — of everything surveyed this is closest in *spirit* to our approach (NL → structured IR → validated), and multi-actor business workflows are a decent proxy domain; the CC BY-SA share-alike clause means: fine to benchmark against, use with care before any redistribution that touches Seam-Bench itself |
| **WorkflowBench / WorkflowLLM** (OpenBMB, and related IBM work) | not independently confirmed today (search returned conflicting size claims) | not confirmed | NL→Python-IR→BPMN pipeline (per FLOW-BENCH paper's description) | Unclear | **ignore for now** — insufficient license/size verification in this pass; revisit only if FLOW-BENCH proves too small |
| **WorfBench** (ICLR'25, `zjunlp/WorfBench`) | Not sized in this pass | Not checked | Graph-structured agentic workflow generation benchmark, NL task → workflow graph | Graph-structural evaluation (not verifier-total) | **adapt-method, needs follow-up** — the graph-based grading concept (nodes/edges vs. our EFSM) is worth a closer read later; not evaluated deeply enough today to rank higher |

**Headline for Task A:** nothing above is directly reuse-data for Seam-Bench
— domains, formalisms, and licenses all miss on at least one axis. The
strongest *methodology* donors are (a) NL2TL/VLTL-Bench's back-translation
and lift/ground/translate/verify staging (already mirrored in our D2 + §5
J-probe design) and (b) FLOW-BENCH's NL→structured-IR→validator pipeline
shape, which is the closest published sibling to "verifier-scored autoformalization
of multi-actor coordination." VLTL-Bench (CC BY 4.0) and FLOW-BENCH
(CC BY-SA 4.0) are the two candidates worth a light transfer-eval adapter;
everything else is method-only or blocked by license/access.

---

## Task B — D5 mining targets, sized

**Methodology note on the numbers below:** GitHub's code-search API does not
honor the `path:` qualifier the way the web UI does, and generic
`filename:X` queries return every file on GitHub sharing that name — most of
which are false positives (e.g. `filename:SKILL.md` returns 337,192 hits,
the vast majority unrelated to agent-skill authoring; one hit in the sample
was literally a `skill.md` inside a competitive-programming repo). Treat
raw `total_count` numbers as **loose ceilings**, not real yields. The
numbers that matter operationally are the **repo-scoped** counts (e.g.
`repo:github/awesome-copilot extension:agent.md` → 243, an exact count),
which is why the shortlist below leads with single-repo targets, mirroring
exactly how the existing `skills_safety` cases were built (hand-pull a
handful of role files from one permissively-licensed repo per case, not a
mass crawl).

### 1. Claude/agent skills — the proven recipe, scaled

**Existing precedent** (`experiments/cases/skills_safety/`): `pr_merge` pulled
5 of 243 `agents/*.agent.md` files from `github/awesome-copilot` (MIT);
`doc_pipeline` pulled 3 of 12 usable Apache-2.0 skills from `anthropics/skills`.
Both are **hand-curated single-repo pulls**, not automated mass mining — the
compactor (`stjp_core/generation/skill_compactor.py`) takes it from there
(prose → LocalType → `global_synthesizer.py` → Scribble validator).

| source | inventory | license | intent-text | harvest difficulty |
|---|---|---|---|---|
| `github/awesome-copilot` | **243** `*.agent.md` + **209** `*.instructions.md` = ~452 role/instruction files (exact repo-scoped count); already-used: 5 (`pr_merge`) | MIT (confirmed, verbatim `LICENSE` saved in `_incoming/`) | Gold (a known-correct reference source) — each file is a standalone human-curated persona/instruction prose block (`description`, body) | **A** — same recipe already proven; just needs more team compositions selected by a human/LLM reading the ~450 remaining files and grouping into plausible pipelines (dev-workflow angle: PRD → Architect → Plan → Debug chains are visible in the sampled filenames alone) |
| `VoltAgent/awesome-claude-code-subagents` | 100+ subagent files (single repo, unmined by this program) | **MIT** (confirmed via fetched `LICENSE`) | Likely gold — subagent files ship structured "when to use" descriptions per the repo's stated purpose | **A/B** — same shape as awesome-copilot but unverified whether files are single-persona prose (need one fetch pass to confirm frontmatter shape before treating as equivalent-quality source) |
| `anthropics/skills` — remaining unused skills | 9 more Apache-2.0 "Example Skills" not yet mined: `algorithmic-art`, `canvas-design`, `frontend-design`, `mcp-builder`, `skill-creator`, `slack-gif-creator`, `theme-factory`, `web-artifacts-builder`, `webapp-testing` (the `docx/pdf/pptx/xlsx` document skills remain excluded — source-available, copy/derivative forbidden) | Apache-2.0 per-skill (already verified in-repo, `_incoming/anthropic_skills/PROVENANCE.md`) | Gold — same SKILL.md prose format already used for `doc_pipeline` | **A** — small remaining pool (maybe 2-3 more team compositions, e.g. `frontend-design` → `webapp-testing` → `skill-creator` reads like a natural build→test→package pipeline), but trivially low-risk since the license read is already done |
| `rohitg00/awesome-claude-code-toolkit` | Repo claims 135 agents + 35 skills + 42 commands (self-reported in its own description, not independently recounted here) | Not checked this pass | Unknown until sampled | **B** — large claimed inventory, but license and file-format need one verification pass before treating as equal-quality to the two MIT repos above |
| Generic `filename:SKILL.md` / `path:.claude/skills` across all of GitHub | 337K / 123K raw hits (see methodology note — mostly noise) | Mixed/unknown per-repo | Mixed — most hits are non-agent files (READMEs, unrelated "skill.md" docs) or one-off single-role files with no natural "team" to compose | **C** as a blind crawl — only usable after a filtering pass (frontmatter shape, repo license, co-located sibling skills implying a team); `awesome-claude-code` (49.8K★, MIT-adjacent aggregator) is the natural index to drive that filtering rather than crawling GitHub search directly |
| `CLAUDE.md` / `AGENTS.md` role sections across GitHub | 616K / 558K raw hits (same noise caveat — most are generic build/lint instructions, not multi-role team descriptions) | Mixed | Sparse — only a minority of these files describe multiple distinct agent *roles* in one repo (most are single-agent dev-environment instructions, confirmed by the sample: gosec, Paket, HIP are all single-actor build guidance) | **C** — low signal-to-noise; only worth mining opportunistically (e.g. `redpanda-data/connect`'s `CLAUDE.md` sample hit literally had a "## Skills and Agents" section, suggesting occasional multi-role repos exist, but finding them requires per-file inspection, not a bulk query) |

### 2. Multi-agent framework configs

| framework | where the human-written intent lives | how it maps to roles/messages/ordering | estimated yield | license posture | harvest difficulty |
|---|---|---|---|---|---|
| **[CrewAI](https://github.com/crewAIInc/crewAI)** | `config/agents.yaml`: `role:`, `goal:`, `backstory:` fields (prose, human-authored) per agent; `config/tasks.yaml`: `description:`/`expected_output:` per task | **Mechanical for WHAT, manual for WHO-SENDS-WHAT-TO-WHOM.** `role`/`goal`/`backstory` give a clean per-role intent (≈ our `role_descriptions`). Ordering is only *partially* explicit: `Process.sequential` + a task's `context: [other_task]` field gives a real dependency edge; `Process.hierarchical` delegates ordering to a manager LLM at runtime — no static protocol exists for those crews | ~2,980 repos import `crewai.Agent` directly; a stricter `config/agents.yaml`-shaped scan returns dozens (23 in a `path:config`+`crewai` combo query, almost certainly undercounting due to the same path-qualifier API limitation noted above) — realistic per-repo yield is **one team per repo**, so this is a long-tail many-small-repos target, not a few-large-repos one | Per-repo, must check each (no central permissive umbrella like awesome-copilot) | **B** — good intent text, ordering needs a code read (task `context:` graph + `Process` type), and sequential-process crews are the only cleanly-static subset |
| **AutoGen / AG2** | `system_message=` string literals embedded in Python (`ConversableAgent`/`AssistantAgent` constructors) — prose, human-authored, but requires source parsing (not a separate config file) | Only mechanical when `GroupChat(..., speaker_selection_method="round_robin")` or a custom deterministic selector is used — a fixed order is then directly readable. When `speaker_selection_method="auto"` (LLM-managed, the common default), there is **no static protocol to extract** — the ordering is decided live by an LLM manager at runtime, not authored anywhere | ~2,936 repos hit `GroupChat` + `import autogen`/`ag2` — most are tutorial-shaped (the sampled hits include several toy/course examples) | Per-repo | **B/C** — must filter for the deterministic-selector subset first; the LLM-managed-order majority is not a usable mining target for a *protocol* (no fixed choreography exists to recover) |
| **LangGraph** | Sparse — node names and occasional per-node docstrings are the closest thing to intent text; task-specific "why" prose is often thin or absent, especially in tutorial repos | **Best mechanical fit of the three.** `add_node`/`add_edge`/`add_conditional_edges` calls already *are* an explicit graph (nodes ≈ roles/states, edges ≈ ordering, conditional edges ≈ branches) — structurally close to an EFSM/global-protocol skeleton, translation is closer to a parser than an inference task | ~6,424 repos hit `from langgraph.graph import StateGraph` | Per-repo | **B** — structurally the easiest of the three to convert mechanically (graph→protocol is nearly 1:1), but the *intent* half of the (intent, protocol) pair is often weak or tutorial-boilerplate rather than a genuine human ask, which is exactly what D5 needs to be "gold" — this is the framework where protocol-extraction is easy but intent-quality needs the most scrutiny per repo |

### 3. CI/release/review pipelines as protocols — mostly a bad target, say so

- **GitHub Actions workflows** (`.github/workflows/*.yml` with `jobs:`,
  `needs:`, multiple `runs-on:` environments): these encode a **deterministic
  job DAG executed by one CI system**, not autonomous agents exchanging
  messages. There is no NL "intent" per job beyond a job/step name, no
  role-specific reasoning, and no branching driven by an agent's judgment —
  every "actor" is the same runner executing the same YAML. **This is not a
  multi-agent interaction target; it is a build graph.** Recommend: do not
  mine — it fails the program's own definition of what a protocol encodes
  (inter-agent choice and message ordering), and mining it would silently
  smuggle "job scheduling" data into a "multi-agent coordination" benchmark.
- **CODEOWNERS + PR review flows**: closer to real actors (human reviewers
  as roles), and GitHub's review-state machine (requested → approved /
  changes-requested → merged) is a genuine multi-party protocol shape.
  But **CODEOWNERS itself carries zero prose** — it is glob-path-to-username
  mappings, no NL intent text at all (`filename:CODEOWNERS` → 157,696 raw
  hits, all structurally identical glob/owner pairs). Any "intent" (why this
  review order, why this gate) would have to be reverse-engineered from a
  separate CONTRIBUTING.md or branch-protection description, which is a
  second, unreliable harvesting step. **Verdict: marginal (grade C)** — usable
  only as a structural cross-check for review-gate *shapes* (which the
  `pr_merge` case already captures by hand), not as a source of (intent,
  protocol) training pairs, because there is no intent text to harvest.

### Ranked mining shortlist (top 5, with expected item counts)

1. **[`github/awesome-copilot`](https://github.com/github/awesome-copilot)** (MIT) — 243 `*.agent.md` + 209
   `*.instructions.md` files, 5 already used. Same proven recipe as `pr_merge`.
   Expected yield: **15–25 more team compositions** (3–6 roles each) →
   roughly **60–130 candidate (intent, skills-team) items** before the
   compactor/validator filter (which is expected to reject a nontrivial
   fraction, per the plan's "low yield is itself a finding" framing).
2. **[`VoltAgent/awesome-claude-code-subagents`](https://github.com/VoltAgent/awesome-claude-code-subagents)** (MIT, confirmed) — 100+
   subagent files in one unmined repo. Expected yield, pending one
   file-format verification pass: **similar order of magnitude to #1,
   roughly 50–100 candidate items** across dev-workflow-shaped teams
   (architect → implementer → reviewer → tester clusters look plausible
   from the repo's stated domain coverage).
3. **`anthropics/skills` remaining Apache-2.0 skills** (9 unused: `frontend-design`,
   `webapp-testing`, `skill-creator`, `mcp-builder`, `canvas-design`,
   `theme-factory`, `algorithmic-art`, `slack-gif-creator`,
   `web-artifacts-builder`) — smallest pool but zero incremental license risk
   (already cleared). Expected yield: **2–4 more team compositions, ~10–15
   items**.
4. **CrewAI `config/agents.yaml`+`config/tasks.yaml` pairs, sequential-process
   only** — long-tail, one team per repo, license checked per repo. Expected
   yield per unit effort is lower than #1–3, but the population is large
   (thousands of repos import `crewai.Agent`); realistic near-term take:
   **10–20 repos worth vetting → 10–20 items**, gated on filtering out
   `Process.hierarchical` crews (no static order) and per-repo license checks.
5. **LangGraph `StateGraph` repos, non-tutorial subset** — best structural
   fit (graph ≈ protocol skeleton) but weakest intent-text; usable as a
   **protocol-shape supplement** rather than a primary intent source. Expected
   yield: **5–15 items**, contingent on finding repos with real per-node
   docstrings or an accompanying README that states an actual task (not a
   LangGraph tutorial walkthrough).

**Not recommended / deprioritized:** blind `filename:SKILL.md` / `CLAUDE.md` /
`AGENTS.md` crawls across all of GitHub (grade C, dominated by noise —
route through `awesome-claude-code`'s curated index instead if broader
coverage is ever needed); AutoGen `speaker_selection_method="auto"` crews
(no static protocol exists to extract); GitHub Actions workflows (job DAGs,
not agent protocols — explicitly a bad target per the task's own
falsifiability check); CODEOWNERS (zero prose, no intent text).

**Rough total D5 near-term reach:** summing the top 3 (the same-recipe,
lowest-risk sources) gives on the order of **120–260 candidate items** before
the compactor/validator/round-trip filters, comfortably above the plan's
150–300 `test-real` target *if* the post-filter survival rate is reasonable —
which is exactly the open question the plan already flags ("yield expectation
is honestly unknown ... a low yield is itself a paper finding").
