# Paper Writing - STJP ICLR Paper

This directory contains LaTeX sources for the STJP (Semantic Type Judgment Problems) ICLR paper in multiple versions.

## Directory Structure

- **v6/** - Version 6 of the paper
- **v7/** - Version 7 of the paper
- **v8/** - Version 8 of the paper
- **v9/** - Version 9 of the paper (latest)

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

- **v9** - Latest version: *"Guarantees, Not Averages: Type-Checking Agent Conversations with Multiparty Session Types"* (supersedes v8; same title/abstract). v9 = v8 plus the realized trainable-seam program, positioned as a bridge section. Three groups of changes:
  1. **New §8 "The Trainable Seam, Realized"** - positioned after the n=100 validation suite and before the typed extensions. v8 *promised* the intent→protocol seam is trainable; v9 shows the training program realized: the two-axis problem (validity machine-checkable via the real Scribble oracle, faithfulness not), the verifier reward stack, and four instruments **measured before any training** - grammar (100% corpus round-trip, 1,000/1,000 samples parse, 0 parse-level rejections), corpus (671 EFSM-deduped families, 200/200 signature-vs-checker, 860 repair tuples, leakage-proof splits), the memoryless faithfulness panel (14 judge seats run live; a deliberately mismatched intent/protocol check item was rejected at 0.99; the trade_deadlock case where the protocol quietly repairs the intent's deadlock was caught by the blind judge), and the real-skills miner (609 artifacts → 0 of 13 teams survive the deterministic, no-LLM extraction path; controls show the pipeline itself works, and whether the coordination structure is absent or merely implicit in prose is a preregistered follow-up) - plus the preregistered gates H1–H6 with honest audit-power math.
  2. **Results template** - `seam_results.tex` declares 26 macros (one per pending training number), each defaulting to a visible `\pending`; the §8 tables and the v8 E5 cells consume only these macros, and `TEMPLATE_HOWTO.md` maps each macro to its eval-harness output field so post-GPU numbers drop in without restructuring.
  3. **Citations + minimal claim touches** - +13 bibitems (RLVR/GRPO, autoformalization, judge-panel lineages; the Liu et al. NL→network-protocol near-miss; ZipperGen reused); Contribution 5 extended to name the released instruments (measured); Limitations translation-seam paragraph updated "Planned"→"Underway". Title, abstract, and other contributions unchanged.

  See `v9/CHANGELOG_v9.md` for all edits with rationale, `v9/TEMPLATE_HOWTO.md` for the macro fill map, and `v9/README.txt` for build/status notes.
- **v8** - *"Guarantees, Not Averages: Type-Checking Agent Conversations with Multiparty Session Types"* (supersedes v7). Three groups of changes:
  1. **Repositioning (ICLR-facing)** - thesis-first title; abstract ~40% shorter and empirical-first; contributions reordered (judge-free eval + CGC and the three empirical regularities lead, guarantee transfer follows).
  2. **Concurrent/adjacent work cited and positioned** - ZipperGen (Bollig–Függer–Nowak, arXiv:2604.17612) in Related Work plus a new Table 1 row; Contribution 1 rescoped to cite its own counterexample inline; also Li–Stutz–Wies–Zufferey (CAV'23 / OOPSLA'25 / ITP'25), Paduraru et al. (arXiv:2603.18096), and Kaptein et al. + EU AI Act motivation (arXiv:2603.16586).
  3. **New content** - §3.2 merge-as-lint flip; §7 "The seam is trainable, not merely open"; Limitations translation-seam paragraph updated to verifier-in-the-loop framing.

  See `v8/CHANGELOG_v8.md` for all edits with rationale and `v8/README.txt` for build/status notes.
- **v7** - Previous version with refinements
- **v6** - Previous stable version

## PDF Versions

Pre-compiled PDFs are available:
- `STJP_paper_v6_compiled.pdf`
- `STJP_paper_v7_compiled.pdf`
- `v8/main.pdf` and `v8/STJP_paper_v8.docx`
- v9 ships source only (compile locally with `make`; no texlive in the authoring sandbox).

## Editing

Edit `main.tex` directly in any text editor. Recommendations:
- VS Code with LaTeX Workshop extension
- TeXShop (macOS)
- TeXworks (cross-platform)
- Overleaf (online, no installation needed)

After editing, rebuild using `make` or the manual pdflatex commands above.
