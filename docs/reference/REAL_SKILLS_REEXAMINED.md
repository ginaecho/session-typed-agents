# Re-examining the real-skills cases — what the source files actually say

**Date: 2026-07-15.** We went back to the real, public files behind the two
"real skills" cases and re-read them line by line. This page records what
we found: both cases had protocols that did not match what the source
files really describe, and fixing that honestly makes the STJP story
*stronger*, not weaker. Every source file is deep-linked so you can check
every claim yourself.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The short version](#the-short-version)
- [Case 1: the code-change team (github/awesome-copilot)](#case-1-the-code-change-team-githubawesome-copilot)
  - [What each real file actually says](#what-each-real-file-actually-says)
  - [The three mismatches in the old protocol](#the-three-mismatches-in-the-old-protocol)
  - [The corrected protocol, from the intent](#the-corrected-protocol-from-the-intent)
- [Case 2: the announcement team (anthropics/skills)](#case-2-the-announcement-team-anthropicsskills)
  - [The miscast reviewer](#the-miscast-reviewer)
  - [What a faithful redesign looks like](#what-a-faithful-redesign-looks-like)
- [The pivot insight: collections have agents, not teams](#the-pivot-insight-collections-have-agents-not-teams)
- [Method note: how this re-examination was run](#method-note-how-this-re-examination-was-run)
<!-- MENU:END -->

## The short version

Public agent collections such as
[github/awesome-copilot](https://github.com/github/awesome-copilot) and
[anthropics/skills](https://github.com/anthropics/skills) contain many
well-written *single-role* files — but **no file anywhere says how the
roles work together**: who speaks first, who loops with whom, what must
be approved before what. When we first built benchmark cases from these
files, some of that missing "team wiring" got invented in ways the source
files do not support. This page corrects that, and the correction is the
point: **the wiring is exactly the thing a global protocol has to add,
so it must be derived from the user's intent — and each role must be cast
as what its file really is.**

## Case 1: the code-change team (github/awesome-copilot)

The intent: *"review the change until quality and security are both
assured — then, and only then, merge it."*

### What each real file actually says

| Role | Real file (MIT) | What the file really describes |
|---|---|---|
| Author | [`agents/address-comments.agent.md`](https://github.com/github/awesome-copilot/blob/main/agents/address-comments.agent.md) | "Your job is to address comments on your pull request." It assumes a PR **already exists with review comments on it**, then loops: fix one comment → add tests → commit → "Move on to the next comment". It never submits the initial change. |
| CodeReviewer | [`instructions/code-review-generic.instructions.md`](https://github.com/github/awesome-copilot/blob/main/instructions/code-review-generic.instructions.md) | Structured, severity-triaged review; "🔴 CRITICAL (Block merge)". But nothing says who receives its verdict. |
| SecurityReviewer | [`agents/se-security-reviewer.agent.md`](https://github.com/github/awesome-copilot/blob/main/agents/se-security-reviewer.agent.md) | OWASP Top 10 / Zero-Trust review producing a report with "Ready for Production: Yes/No" — saved to a file, **no recipient named**. |
| Merger | [`agents/principal-software-engineer.agent.md`](https://github.com/github/awesome-copilot/blob/main/agents/principal-software-engineer.agent.md) | Principal-engineer ship judgment, pragmatic delivery. **No gate language at all** — nothing says reviews must come first. |

### The three mismatches in the old protocol

The old case and demo used one straight line:
`SubmitChange: Author→CodeReviewer; ReviewPassed: CodeReviewer→SecurityReviewer; SecurityPassed: SecurityReviewer→Merger; MergeDone: Merger→Author.`

1. **Wrong start.** The Author's source file never submits a change — its
   whole job begins when reviewer comments *arrive*. A faithful protocol
   starts with the reviews, not with a submission.
2. **No loop.** Real review is many rounds (comments → revision →
   re-review). The file itself loops per comment. A single-pass line
   cannot represent it.
3. **No concurrency, wrong join.** Quality review and security review are
   independent looks at the same revision, and the merge must wait for
   **both**. In the old line, the Merger only ever hears from the
   SecurityReviewer; the quality verdict is merely relayed through it.

### The corrected protocol, from the intent

The corrected case lives at
[`experiments/cases/skills_safety/pr_review_merge/`](../../experiments/cases/skills_safety/pr_review_merge/)
(the old case is kept untouched because published results reference it).
Shape, in words: the Author announces the existing PR to **both**
reviewers at once (after this fan-out, both reviewers examine the same
revision *at the same time* — the protocol fixes no order between them); a
`rec` loop carries comment→revision rounds, with every revision going to
both reviewers; the exit branch is a **join**: `SecurityApproved` and
`QualityApproved` must both reach the Merger (the runtime monitor accepts
them in either arrival order) before `MergeDone` can exist.

Two details came from the machine checker itself, and they are worth
reading as lessons rather than fine print. First, the checker rejected a
leaner draft twice — once because the Author could not always tell which
branch the team had taken, once because the Merger was silent through
loop rounds (a role that might wait forever). The fix in both cases was
to **broadcast each decision to every role**: that is what makes the
protocol provably unambiguous. Second, even with those broadcasts the
Merger only *receives* during the loop — it never has to act, and the
scheduler never calls it, until both approvals have arrived. This uses
only constructs the stack already runs today (`rec` + `choice at`, proven
in [`experiments/cases/retry_loop/`](../../experiments/cases/retry_loop/);
the monitor's out-of-order tolerance covers the either-order approvals),
and the final protocol was validated end-to-end with the repo's real
scribble-java toolchain, including all four per-role projections.

## Case 2: the announcement team (anthropics/skills)

### The miscast reviewer

The old `doc_pipeline` case cast
[`skills/brand-guidelines/SKILL.md`](https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md)
as a "BrandReviewer" that approves or rejects drafts. Re-reading the
file: it contains **no review, approval, or rejection language at all**.
It is a mechanical styling *applicator* — "Applies Poppins font to
headings", "Uses RGB color values for precise brand matching" — a
transform, not a gatekeeper.
[`skills/internal-comms/SKILL.md`](https://github.com/anthropics/skills/blob/main/skills/internal-comms/SKILL.md)
is single-pass ("identify the communication type → load the guideline →
write") with no feedback-handling step. The only file with genuine
loop-and-gate language is
[`skills/doc-coauthoring/SKILL.md`](https://github.com/anthropics/skills/blob/main/skills/doc-coauthoring/SKILL.md):
staged refinement with an explicit iteration gate ("Continue iterating
until user is satisfied") and a reader-test gate ("If issues found …
Loop back to refinement").

### What a faithful redesign looks like

Cast each file as what it is: the Writer (internal-comms) drafts on
request; the brand skill is a **styling step**, not an approval gate; the
DocLead (doc-coauthoring) runs the iterative refine → reader-test loop
and only ships when the reader test passes — that is where the real gate
lives. The content itself must flow to the DocLead (in the old protocol
the DocLead shipped a document it never received — the exact failure the
RESULT_9 traces showed when the no-plan team stalled).

## The pivot insight: collections have agents, not teams

What this re-examination demonstrates is the product gap STJP fills:

1. Collections give you **hundreds of good single-role files** — 243
   agent files and 209 instruction files in awesome-copilot alone — and
   **zero team wiring**. Nobody wrote down who talks to whom.
2. Worse, the files do not even tell you *which parts they can play*:
   one file is a gate ("Block merge"), one is a transform (brand
   styling), one is a loop-worker (address-comments). Wiring them
   correctly requires reading each file for what it is.
3. So the workflow STJP enables is: **state the intent → pick the agents
   → write the global protocol from the intent (loops where reality
   iterates, concurrency where work is independent, joins where the
   intent demands "both") → machine-check it → project a local contract
   per agent.** The protocol is the one line the collections never
   contain.

## Method note: how this re-examination was run

Following the standing method (strong model plans and verifies; cheap
subagents do the legwork): scout subagents fetched and quoted the seven
real source files and mapped the repo's compiler/monitor capabilities;
the planner cross-checked the quotes, designed the corrected protocols
against what the stack provably runs, and implementation subagents built
the corrected case and demo, each gated on validator output the planner
reviewed.
