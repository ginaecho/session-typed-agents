STJP paper v10 -- "Compile the Conversation: Multiparty Session Types Make
Multi-Agent Coordination Provably Safe -- and Cheaper than Failure"
============================================================================
SUPERSEDES: v9 (same structure and claims; new title + real-skills live-run
integration). Full per-edit detail in CHANGELOG_v10.md; macro fill map in
TEMPLATE_HOWTO.md (unchanged from v9).
CONTENTS: main.tex (single source, standalone preamble; \input{seam_results.tex});
seam_results.tex (results template -- 26 pending-number macros); TEMPLATE_HOWTO.md
(macro -> harness-field map); fig1_system fig2_results fig3_projected fig4_ladder
(pdf); make_figs_v2.py (all four figures); make_drawio.py + STJP_system_figure.drawio
(editable Fig.1 source); Makefile; CHANGELOG_v10.md.
BUILD: make -> main.pdf (pdflatex x2; main.tex \input{seam_results.tex}, so both
compile together); make docx (pandoc); make figs.
NOT COMPILED IN THIS SANDBOX -- no texlive/pandoc installed here. Compile locally
(texlive-full) with `make`. In lieu of a compile, v10 ran the same grep/python
sanity pass as v9 (see CHANGELOG_v10.md): \begin/\end 41/41 and per-environment
balanced; braces 1172/1172 (verbatim/comments stripped); 49 cite keys used, 49
bibitems, 0 undefined; \ref/\label 0 undefined; all \seam* macros defined; the
new tab:realcases table is 10 rows x 5 columns.
CHANGES vs v9 (summary; rationale in CHANGELOG_v10.md):
(1) NEW TITLE -- "Compile the Conversation: Multiparty Session Types Make
    Multi-Agent Coordination Provably Safe -- and Cheaper than Failure".
    Thesis-as-action + method keyword + both headline claims; "cheaper than
    failure" is now measured, not rhetorical (RESULT_10's 3.6x livelock).
(2) NEW BLOCK in Section 7 -- "Real skills, run live: nine cases and a
    livelock" (anchor sec:real) + Table tab:realcases: integrates
    docs/results RESULT_8..RESULT_11 (nine cases from unmodified public
    skill/agent files; the two-model coin flip; the first live rec/choice
    runs; the plan-as-text LIVELOCK at 3.6x the cost of the succeeding
    enforced arm; the two static Scribble rejections that debugged the
    corrected review protocol).
(3) Ripple edits: abstract +1 sentence, Contribution 3 +1 sentence,
    Conclusion +1 sentence, Limitations scope note (round-batched
    role-play independence caveat).
STATUS: submission-shaped; GPU seam numbers still pending via
seam_results.tex, unchanged from v9.
