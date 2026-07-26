PDF = main.pdf
all: $(PDF)
$(PDF): main.tex references.bib neurips_2026.sty fig1_system.pdf fig3_projected.pdf fig4_ladder.pdf
	pdflatex -interaction=nonstopmode main.tex
	bibtex main
	pdflatex -interaction=nonstopmode main.tex
	pdflatex -interaction=nonstopmode main.tex
	@grep -c "Undefined" main.log || true
clean:
	rm -f *.aux *.log *.out *.bbl *.blg *.png main.pdf
