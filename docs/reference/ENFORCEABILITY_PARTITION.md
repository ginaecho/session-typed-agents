# The enforceability partition — AGENT.md as the worked example

Every rule a skill, spec, or agent markdown states can be sorted by one
question: **what would enforce it?** Not "is it important," not "is it written
emphatically" — what *mechanism* would catch a violation. This document
defines the four tiers, then runs the partition over this repository's own
`AGENT.md` as the worked example, because on 2026-07-25 an agent broke three
of that file's prose rules in one session while being caught by every
mechanical check it touched
([`SESSION_RECORD_2026-07-25.md`](SESSION_RECORD_2026-07-25.md) §9: zero of
three on prose, four of four on mechanism). The partition was proposed in
that record's §10; this is the record's §11.4 item, built.

Why this matters beyond housekeeping: of the systems the July 2026
literature sweep surfaced ([`RELATED_WORK_2026-07-25.md`](RELATED_WORK_2026-07-25.md)),
none partitions a specification by enforceability tier, and none reports the
residual — the list of rules it *cannot* enforce. STJP has all three
enforcement tiers, so it is the only system in that sweep that can produce
the honest partition. The most valuable output of a skill compiler may be
exactly that residual list, with the conditions under which each residual
rule is likely to be violated.

To make the comparison concrete — who checks what, and *when* (per the
sweep's own verified findings; "static" means before any run, as the
Scribble check is; "interaction" means between roles, as opposed to typing
one artifact in isolation):

| System | Static (pre-run)? | Interaction-aware? | What it actually checks |
|---|---|---|---|
| SkCC | yes | no | one skill's typed intermediate representation and formatting |
| Skill-as-Pseudocode | yes | no | per-skill trigger, input/output schema, pre/post-conditions |
| SkillFortify | yes | no | one skill's capability envelope (sound, no-false-negatives theorem) |
| SkillSmith | yes (offline compile) | no | per-skill runtime boundary contracts |
| Agentproof | yes | partially — workflow graph, not messages | graph-level properties (dead ends, unreachable exits); by its own scoping, no message ordering, no blocked-progress reasoning |
| VIGIL | no (runtime) | trace-level | monitors traces against skill specifications after actions happen |
| `llmcontract` | no (runtime) | two-party only | session-typed runtime monitoring, no projection, no static phase |
| TraceFix | yes (TLA+ model check) | yes | ordering + guards, but bounded (channel caps), safety-only, per-agent prompts written and checked by a language model |
| **STJP** | **yes (unbounded, decidable)** | **yes (multiparty, projected)** | global-type well-formedness ⇒ deadlock-freedom for every run; projection with per-role monitors; payload refinements; ledger invariants |

So the honest competitive sentence is narrow and survives the sweep: the
skill compilers are static but intra-role; the interaction-aware systems
are either runtime-only, two-party, graph-level, or bounded safety-only
model checking. **Static, unbounded, multiparty, projection-sound
interaction validation before any run is STJP's cell in the table** — and
because it also has the refinement and lint tiers, it is the only entrant
that can partition a whole spec and report a residual at all.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The four tiers](#the-four-tiers)
- [The worked example: every normative rule in AGENT.md, sorted](#the-worked-example-every-normative-rule-in-agentmd-sorted)
  - [Tier 1 — type-checkable (properties of a whole conversation)](#tier-1--type-checkable-properties-of-a-whole-conversation)
  - [Tier 2 — refinement-checkable (properties of a value or a running total)](#tier-2--refinement-checkable-properties-of-a-value-or-a-running-total)
  - [Tier 3 — lint-checkable (properties of artifacts outside any session)](#tier-3--lint-checkable-properties-of-artifacts-outside-any-session)
  - [Tier 4 — unenforceable prose (judgment and taste)](#tier-4--unenforceable-prose-judgment-and-taste)
- [Predicting violation of the residual](#predicting-violation-of-the-residual)
- [Two honest limits](#two-honest-limits)
- [What changed on 2026-07-25](#what-changed-on-2026-07-25)
<!-- MENU:END -->

## The four tiers

1. **Type-checkable.** Ordering, choice coherence, role legality, goal
   reachability — properties of a *whole conversation*, not of any single
   call. "Registration precedes the trial" and "authorization precedes the
   irreversible act" have the same shape, and no per-call rule language can
   express either. Compiled into the global protocol; guaranteed for every
   run, not only observed ones.
2. **Refinement-checkable.** Predicates on a message's payload, forbidden
   substrings, budgets and running totals. Compiled into guards and the
   ledger (the opt-in running-value mechanism described in the root
   `README.md`); decided at the message boundary. A small example of why
   this tier exists apart from tier 1: "never overdraw the search budget"
   cannot be checked per message, because whether *this* spend overdraws
   depends on every spend before it — that is what the ledger's running
   value is for.
3. **Lint-checkable.** Facts about artifacts outside any session — file
   names, branch names, commit strings, link targets, word choices in
   committed prose. Compiled to a hook or a checker script. Guaranteed, but
   not by the session monitor: the guarantee holds only where the hook
   actually runs (a clone that never enables the pre-push hook is back to
   prose).
4. **Unenforceable prose.** Judgment and taste: "no playing smart," "write
   for a capable developer," "loosen the predicate rather than fight it."
   No mechanism exists. This tier is the residual, and claiming a mechanism
   covers it would be worse than admitting it does not.

## The worked example: every normative rule in AGENT.md, sorted

`AGENT.md` is ~800 lines with roughly 34 normative statements. Grouped and
sorted below; "status" says what enforces the rule **today** in this
repository.

### Tier 1 — type-checkable (properties of a whole conversation)

| Rule in AGENT.md | What enforces it | Status |
|---|---|---|
| Protocol files: no circular waits, every branch carries its messages, projectable to every role | the Scribble compiler's well-formedness check | **enforced** — it rejected a real draft with `Subject not enabled: Scout` on 2026-07-25 (session record §8) |
| "Registration precedes the trial" (pre-register in `docs/predictions/` before running) | expressible as a protocol ordering property when the experiment itself runs under STJP; today, for the human workflow, it is convention plus review | **partially** — in-session it is core competence; as a repo workflow it has no checker yet |
| "Modify `monitor.py` only with all cases re-run" (an ordering between an edit and a validation) | a CI job that runs the case suite on any monitor change | **not built** — currently prose plus habit |

### Tier 2 — refinement-checkable (properties of a value or a running total)

| Rule in AGENT.md | What enforces it | Status |
|---|---|---|
| Refinement predicates on payloads (`amount > 0`, label vocabulary) | the refinement checker; guards compiled into send tools ([`GAP_CLOSED.md`](GAP_CLOSED.md)) | **enforced** at the message boundary |
| Budgets that must never go negative | the `__ledger__` running-value invariant | **enforced when declared** — demonstrated rejecting a real overdraw pre-delivery on 2026-07-25 (session record §8); opt-in per case |

### Tier 3 — lint-checkable (properties of artifacts outside any session)

| Rule in AGENT.md | What enforces it | Status |
|---|---|---|
| Git identity: author/committer `ginaecho`, no assistant trailers, no "claude" keyword anywhere, `gc/` branch prefix | `tools/check_git_rules.py` + `.githooks/pre-push` | **enforced** as of this document (was prose; violated four times the day before) |
| Every relative link and menu anchor resolves | `tools/check_md_links.py` | **enforced** — 2,370 links checked at last run |
| Known-offender jargon appears only with its gloss | `tools/check_style.py` | **enforced** as of this document (was prose; the day before, "lens" — an undefined nickname for a role's task assignment — was coined in breach of it) |
| case.yaml structural requirements (roles match the protocol, arms exist) | the case loader raises on missing files; full schema validation | **partially** — loader checks existence, not schema |
| Python style rules (type hints, `Path()` over hardcoded paths, docstrings) | a standard Python linter would cover most | **not built** — no linter configured in this repo |

### Tier 4 — unenforceable prose (judgment and taste)

"Unenforceable" is a statement about *guarantees*, not about helplessness.
For every residual rule there is still a **compensating control** — a
mechanism that does not decide the judgment but shrinks the room in which
the judgment goes wrong — and a placement for it. The honest report is
therefore three columns, not one:

| Rule in AGENT.md | Why no mechanism can decide it | Compensating control (and where it runs) |
|---|---|---|
| "No playing smart" — don't compress a point to sound expert | whether a sentence "needs the reader to already be an expert" is a judgment call | the known-offender lint catches the *recurring* offenders mechanically (`tools/check_style.py`); new coinages are caught at review, where the reviewer's checklist names this rule |
| "Write for a capable developer, not a compiler researcher" | audience-fit is not decidable | same lint for vocabulary; the "gloss at first use" rule is enforced, which removes the most common way audience-fit fails |
| "Smooth reading flow", "always use a small example" | a checker can count examples, not whether they carry the argument | review checklist; a counter *could* flag sections with zero examples as candidates, never as verdicts |
| "Loosen a too-strict refinement rather than fight it" | which predicate is "too strict" depends on intent | the monitor's violation record shows *which* predicate failed and with what value — the evidence for the judgment arrives mechanically even though the judgment stays human |
| "Ask questions in the right doc first" | a routing preference, not a checkable property | the docs index (one line per doc) lowers the cost to obey, which is one of the three violation predictors below |

Each residual rule also carries its **violation forecast** from the three
predictors (distance, conflict, cost-to-obey): that is what makes the
residual list a risk register rather than a shrug. And residual is not a
life sentence — the 2026-07-25 events moved three rules *out* of this tier
in one day (see "What changed"). The claim to defend in the paper is
symmetric: mechanisms for what can be mechanized, named compensating
controls plus a predicted failure profile for what cannot, and no rule
left in the gap between.

## Predicting violation of the residual

For tier 4 (and for any rule whose mechanism is not yet built), violation is
predictable from three properties, all evidenced in the session record:

- **Distance** from where the rule is written to where the action happens.
  The two rules broken on 2026-07-25 sat ~200 lines from each other in the
  same file; the agent had one in context and not the other. The mitigation
  used here: the non-negotiables are restated at the top of `AGENT.md`
  ("🧭 Read this first"), shrinking the distance to zero for the rules that
  matter most.
- **Presence of a conflicting instruction** with no precedence rule. The
  platform mandated a branch name and trailers the repo forbids; nothing
  said which wins, so the conflict was resolved silently toward the nearer
  instruction. The mitigation: `AGENT.md` now states precedence explicitly
  (this file wins for repository contents) and names the one tolerated
  exception.
- **Cost to obey** against the active objective. "Do not confound your
  variables" was known and still lost to the pull of narrating eight agent
  reports into a result. No doc edit fixes this tier; only a mechanism
  (here, the pre-registration workflow plus the harness's held-constant
  design) removes the temptation's room to operate.

## Two honest limits

Stated here so a reviewer does not have to discover them.

1. The monitor converts "did the agent behave well?" into "was the required
   check performed?" — a large gain, because the check becomes unskippable,
   but not a truth guarantee. A Verifier that confirms a wrong citation
   satisfies the protocol perfectly and still ships a wrong citation.
2. Every mechanism above governs only the channels it owns. The worst
   failures of 2026-07-25 happened in chat replies and shell commands —
   neither is a typed message between roles, and no checker in this
   repository sees them at composition time. The lints see their *artifacts*
   (commits, docs) after the fact; that is the fence, not the field.

## What changed on 2026-07-25

Three rules moved tiers from "prose" to "lint-enforced" in direct response
to the session record: the four-clause git rule (`check_git_rules.py` +
pre-push hook), the known-offender gloss rule (`check_style.py`), and — 
already in place before the incident — link integrity (`check_md_links.py`).
The residual list above is what remains prose, on purpose and said plainly.
