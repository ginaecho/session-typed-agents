# Paper Writing - STJP ICLR Paper

This directory contains LaTeX sources for the STJP (Semantic Type Judgment Problems) ICLR paper in multiple versions.

## Directory Structure

- **v6/** - Version 6 of the paper
- **v7/** - Version 7 of the paper
- **v8/** - Version 8 of the paper (latest)

Each version contains:
- `main.tex` - Main LaTeX source file
- `main.pdf` - Compiled PDF
- Figure files (PNG and PDF)
- `fig1_system.drawio` - Diagram source file (editable with draw.io)
- `Makefile` - Build script for LaTeX compilation
- `make_figs_v2.py` - Python script for figure generation
- `README.txt` - Version-specific notes

## Building the Paper

### Prerequisites

Ensure you have LaTeX installed:

```bash
# macOS (with Homebrew)
brew install mactex

# Ubuntu/Debian
sudo apt-get install texlive-full

# Windows
# Download from https://www.tug.org/texlive/windows.html
```

### Building from Source

Navigate to the desired version and run:

```bash
cd v8  # or v7, v6
make   # Compiles main.tex -> main.pdf
```

Or manually:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

### Regenerating Figures

To regenerate figures from the diagram files:

```bash
python make_figs_v2.py
```

This requires:
- Python 3
- draw.io CLI (for `.drawio` files)
- ImageMagick (for image conversions)

## Key Files

- **main.tex** - Complete paper source with all content and formatting
- **main.pdf** - Ready-to-submit compiled PDF
- **Figures**:
  - `fig1_system.pdf/png` - System architecture
  - `fig2_results.pdf/png` - Results
  - `fig3_projected.pdf/png` - Projections
  - `fig4_ladder.pdf/png` - Ladder diagram

## Version History

- **v8** - Latest version: *"Guarantees, Not Averages: Type-Checking Agent Conversations with Multiparty Session Types"* (supersedes v7). Three groups of changes:
  1. **Repositioning (ICLR-facing)** - thesis-first title; abstract ~40% shorter and empirical-first; contributions reordered (judge-free eval + CGC and the three empirical regularities lead, guarantee transfer follows).
  2. **Concurrent/adjacent work cited and positioned** - ZipperGen (Bollig–Függer–Nowak, arXiv:2604.17612) in Related Work plus a new Table 1 row; Contribution 1 rescoped to cite its own counterexample inline; also Li–Stutz–Wies–Zufferey (CAV'23 / OOPSLA'25 / ITP'25), Paduraru et al. (arXiv:2603.18096), and Kaptein et al. + EU AI Act motivation (arXiv:2603.16586).
  3. **New content** - §3.2 merge-as-lint flip; §7 "Training the intent-to-protocol translation step is possible, not merely a stated goal"; Limitations translation-step paragraph updated to verifier-in-the-loop framing.

  See `v8/CHANGELOG_v8.md` for all edits with rationale and `v8/README.txt` for build/status notes.
- **v7** - Previous version with refinements
- **v6** - Previous stable version

## PDF Versions

Pre-compiled PDFs are available:
- `STJP_paper_v6_compiled.pdf`
- `STJP_paper_v7_compiled.pdf`
- `v8/main.pdf` and `v8/STJP_paper_v8.docx`

## Editing

Edit `main.tex` directly in any text editor. Recommendations:
- VS Code with LaTeX Workshop extension
- TeXShop (macOS)
- TeXworks (cross-platform)
- Overleaf (online, no installation needed)

After editing, rebuild using `make` or the manual pdflatex commands above.
