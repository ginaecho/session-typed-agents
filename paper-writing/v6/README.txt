STJP paper v5 -- complete LaTeX package (n=100 measured results integrated)
===========================================================================
CONTENTS: main.tex; fig1_system fig2_results fig3_projected fig4_ladder (png+pdf);
make_figs_v2.py (all four figures); make_drawio.py + STJP_system_figure.drawio; Makefile.
BUILD: make -> main.pdf; make docx; make figs.
STATUS: everything is MEASURED from branch gc/stjp-validation-suite EXCEPT
Fig.3 panel (c) -- the E3 capability sweep is pending and is the only synthetic
curve left (tagged "projected (synthetic)" in-panel, "PENDING" in the caption).
E5's LLM-dependent rows are marked "pending" in Table 6 (no fake numbers).
For ICLR 2027: swap the geometry/times/fancyhdr preamble for
\usepackage{iclr2027_conference,times}; drop the explicit natbib line (kit loads it).
