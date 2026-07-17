PDF = main.pdf
all: $(PDF)
$(PDF): main.tex seam_results.tex fig1_system.png fig2_results.png fig3_projected.png fig4_ladder.png
	pdflatex -interaction=nonstopmode main.tex
	pdflatex -interaction=nonstopmode main.tex
	@grep -c "Undefined control" main.log || true
figs:
	python3 make_figs_v2.py
drawio:
	python3 make_drawio.py
docx: main.tex
	pandoc main.tex -o STJP_paper.docx --from latex --to docx
clean:
	rm -f *.aux *.log *.out main.pdf
