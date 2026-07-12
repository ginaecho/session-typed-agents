STJP paper v8 -- "Guarantees, Not Averages: Type-Checking Agent Conversations
with Multiparty Session Types" (repositioned for ICLR; concurrent work cited)
============================================================================
SUPERSEDES: v7 (which added the E8-E10 typed extensions to v6).
Full per-edit detail in CHANGELOG_v8.md.
CONTENTS: main.tex (single source, standalone preamble); main.pdf (18 pages);
STJP_paper_v8.docx (pandoc export); fig1_system fig2_results fig3_projected
fig4_ladder (pdf); make_figs_v2.py (all four figures); make_drawio.py +
STJP_system_figure.drawio (editable Fig.1 source); Makefile; CHANGELOG_v8.md.
BUILD: make -> main.pdf; make docx; make figs.
CHANGES vs v7: (1) Repositioning -- thesis-first title; abstract ~40% shorter
and empirical-first, ending on the thesis line ("prompted compliance is a
behavior; compiled enforcement is a property -- and the property is cheaper");
contributions reordered (judge-free eval + CGC and the three empirical
regularities lead; guarantee transfer follows). (2) Concurrent/adjacent work
cited and positioned -- ZipperGen (Bollig-Fugger-Nowak, arXiv:2604.17612) in
Related Work (trusted codegen around opaque LLM calls vs. enforcement on
free-running untrusted agents; static-vs-runtime assurance; markdown skills vs.
runtime-bound Python; Lean concession; "no empirical evaluation" scoping) with a
new Table 1 row (n/a dagger); Contribution 1 rescoped to cite its own
counterexample inline; also Li-Stutz-Wies-Zufferey (CAV'23 / OOPSLA'25 /
ITP'25), Paduraru et al. (arXiv:2603.18096), Kaptein et al. "Policies on Paths"
+ EU AI Act motivation (arXiv:2603.16586). (3) New content -- Sec.3.2
merge-as-lint flip (why STJP keeps the merge check MSC codegen compiles away);
Sec.7 "Training the intent-to-protocol translation step is possible, not merely
a stated goal" (grammar-constrained decoding, best-of-n validated sampling,
corpus back-translation, mutant repair curriculum); Limitations
translation-step paragraph updated to verifier-in-the-loop framing.
STATUS: build verified -- pdflatex clean (0 undefined control sequences,
0 LaTeX errors, 0 citation warnings, 0 "??" in pdftotext); pandoc 0 warnings.
PENDING: E5 LLM-dependent cells (first-draft validity, repair rounds, guard
co-emission) -- cheapest win is best-of-n validated sampling, which fills the
table and lets the Sec.7 training-the-translation-step paragraph point at
measured numbers;
E3 still lacks a non-Claude frontier point (declared access limitation).
For ICLR 2027: swap the geometry/times/fancyhdr preamble for
\usepackage{iclr2027_conference,times}; drop the explicit natbib line (kit loads it).
