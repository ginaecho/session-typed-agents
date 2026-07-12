# STJP paper v8 — changes from v7

## Repositioning (ICLR-facing)
1. TITLE: "Guarantees, Not Averages: Type-Checking Agent Conversations with MPST"
   — thesis-first; compiler framing retained in abstract/intro.
2. ABSTRACT: rewritten ~40% shorter, empirical-first. Leads with the three
   regularities (concurrency collapse of prose compliance; capability-dependent
   vs capability-invariant safety; safest-and-cheapest). Ends on the thesis line.
3. CONTRIBUTIONS reordered: reframing (rescoped) -> judge-free eval + CGC ->
   three empirical regularities -> guarantee transfer -> released benchmark.

## New citations & positioning (5 edits)
4. Related Work: new paragraph "Projection-based coordination for LLM agents"
   — ZipperGen (Bollig–Függer–Nowak, arXiv:2604.17612): trust-boundary argument
   (their LLM never holds send keys; trusted codegen vs enforcement on untrusted
   agents), static-vs-runtime assurance (guarantees before spend), artifact
   portability (markdown skills vs runtime-bound Python), Lean concession,
   "no empirical evaluation" scoping. Also cites Li–Stutz–Wies–Zufferey
   (CAV'23 / OOPSLA'25 / ITP'25) and Paduraru et al. (arXiv:2603.18096).
5. Table 1: new row "MSC codegen [Bollig et al.]" with n/a† on unauthorized-
   recipient blocking; caption updated ("before execution AND enforced on
   untrusted agents") + dagger footnote.
6. Contribution 1 rescoped: "first ... deployed artifacts ... enforced on
   free-running, untrusted LLM agents" (survives ZipperGen).
7. Intro one-liner: "Concurrent work obtains coordination guarantees by taking
   communication away from the agents; STJP leaves the agents free and makes
   the boundary trustworthy."
8. §3.2 merge-as-lint flip: why STJP keeps the merge check that ZipperGen
   compiles away (undefined merge = diagnostic signal for human endorsement).

## New content
9. §7 (after E5): "Training the intent-to-protocol translation step is
   possible, not merely a stated goal" — grammar-constrained
   decoding, best-of-n validated sampling (fills pending E5 cells), corpus
   back-translation for (intent, gold) pairs, mutant repair curriculum.
10. Limitations "The intent-to-protocol translation step": Planned sentence
    replaced with the verifier-in-the-loop framing.
11. Governance paragraph: EU AI Act (Aug 2026) sentence, cites Kaptein et al.
    "Policies on Paths" (arXiv:2603.16586).

## Mechanical
12. §3.3 opening lightly compressed (offsets added length).
13. \includegraphics .png -> .pdf (vector figures).
14. Bib: +6 entries (bollig26, listutz23, li25oopsla, liwies25, paduraru26, pathgov).

Build verified: pdflatex x2 clean (0 undefined control sequences, 0 LaTeX errors,
0 citation warnings, 0 "??" in pdftotext); 18 pages; pandoc docx 0 warnings.
Pre-submission TODO (from review discussion): run best-of-n E5 experiment;
consider one non-Claude E3 point; swap preamble for iclr2027_conference kit.

## 2026-07-12 — plain-language terminology pass
15. Project-invented shorthand reworded per the house plain-language rule:
    the §7 lead phrase "The seam is trainable, not merely open" became
    "Training the intent-to-protocol translation step is possible, not
    merely a stated goal"; the Limitations bold lead "The translation seam."
    became "The intent-to-protocol translation step."; "seam" is now defined
    on first use (E5 paragraph) as "the intent-to-protocol translation step
    (called ``the seam'' below)", so later short-form uses of "seam" in the
    same paragraphs remain valid. "gold" (E5 paragraph) and "escrow"
    (six-arm ladder paragraph) glossed on first use. No claims, numbers, or
    labels/macros/citation keys changed. Brace/environment balance verified
    (\begin{}=\end{}=32; braces balanced, depth 0).
