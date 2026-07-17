# Paper Writing - STJP ICLR Paper

This directory contains LaTeX sources for the STJP (Semantic Type Judgment Problems) ICLR paper in multiple versions.

## Directory Structure

- **v6/** - Version 6 of the paper
- **v7/** - Version 7 of the paper
- **v8/** - Version 8 of the paper
- **v9/** - Version 9 of the paper
- **v10/** - Version 10 of the paper (latest)

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

- **v10** - Latest version: *"Compile the Conversation: Multiparty Session Types Make Multi-Agent Coordination Provably Safe --- and Cheaper than Failure"* (supersedes v9; **retitled** and extended with the real-skills live-run results). Two groups of changes:
  1. **New title** - the v8/v9 title ("Guarantees, Not Averages: ...") named a contrast but not the method or the object. The v10 title states the thesis as an action ("Compile the Conversation"), keeps the "Multiparty Session Types" keyword for reviewers/search, and carries both headline claims - and "cheaper than failure" is now *measured*, not rhetorical: in RESULT_10 the plan-as-text arm livelocks through its entire 16-round budget at 3.6x the token cost of the enforced arm that succeeds. Rationale and the runner-up titles are recorded in `v10/CHANGELOG_v10.md`.
  2. **Real skills, run live (new block in §7, anchor `sec:real`, Table `tab:realcases`)** - integrates `docs/results` RESULT_8-RESULT_11 (the last two dated 2026-07-15, which v9 predated): nine cases assembled from unmodified public skill/agent files (Anthropic skills repo, GitHub awesome-copilot, OpenAI Agents SDK, LangGraph, AutoGen, CrewAI, AgenticPay), all executed live. Found files deadlock, stall, or coin-flip in every case (and the coin flip *reverses direction* between Claude tiers, 120-trial two-model sweep); plan-as-text completes without complying (double writes, double charges, 120-220 rule-breaking messages) - and on the first live `rec`/`choice` looping case (`pr_review_merge`) it produces a **stable livelock** (0/10, 530 rule-breaking messages, ~42k tokens/trial burned for nothing) while full STJP is 10/10, zero violations, and 3.6x cheaper than the *failing* text arm. The corrected review protocol was itself debugged by two static Scribble rejections before any agent ran. Ripple edits: abstract, Contribution 3, Conclusion, Limitations (+ the round-batched role-play independence caveat). Everything else (structure, §8 seam program, `seam_results.tex` template, figures, bibliography) unchanged from v9.

  See `v10/CHANGELOG_v10.md` for all edits with rationale and `v10/README.txt` for build/status notes.
- **v9** - Previous version: *"Guarantees, Not Averages: Type-Checking Agent Conversations with Multiparty Session Types"* (supersedes v8; same title/abstract). v9 = v8 plus the realized training program for the intent-to-protocol translation step (nicknamed "the seam" in the paper), positioned as a bridge section. Three groups of changes:
  1. **New §8 "Training the Intent-to-Protocol Translation Step, Realized"** - positioned after the n=100 validation suite and before the typed extensions. v8 *promised* this translation step is trainable; v9 shows the training program realized: the two-axis problem (validity machine-checkable via the real Scribble oracle, faithfulness not), the verifier reward stack, and four instruments **measured before any training** - grammar (100% corpus round-trip, 1,000/1,000 samples parse, 0 parse-level rejections), corpus (671 EFSM-deduped families, 200/200 signature-vs-checker, 860 repair tuples, leakage-proof splits), the memoryless faithfulness panel (14 judge seats run live; a deliberately mismatched intent/protocol check item, a canary, was rejected at 0.99; the trade_deadlock case where the protocol quietly repairs the intent's deadlock was caught by the blind judge), and the real-skills miner (609 artifacts → 0 of 13 teams survive the deterministic, no-LLM extraction path; controls show the pipeline itself works, and whether the coordination structure is absent or merely implicit in prose is a preregistered follow-up) - plus the preregistered gates H1–H6 with honest audit-power math.
  2. **Results template** - `seam_results.tex` declares 26 macros (one per pending training number), each defaulting to a visible `\pending`; the §8 tables and the v8 E5 cells consume only these macros, and `TEMPLATE_HOWTO.md` maps each macro to its eval-harness output field so post-GPU numbers drop in without restructuring.
  3. **Citations + minimal claim touches** - +13 bibitems (RLVR/GRPO, autoformalization, judge-panel lineages; the Liu et al. NL→network-protocol near-miss; ZipperGen reused); Contribution 5 extended to name the released instruments (measured); Limitations translation-step paragraph updated "Planned"→"Underway". Title, abstract, and other contributions unchanged.

  See `v9/CHANGELOG_v9.md` for all edits with rationale, `v9/TEMPLATE_HOWTO.md` for the macro fill map, and `v9/README.txt` for build/status notes.
- **v8** - *"Guarantees, Not Averages: Type-Checking Agent Conversations with Multiparty Session Types"* (supersedes v7). Three groups of changes:
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
- v9 and v10 ship source only (compile locally with `make`; no texlive in the authoring sandbox).

## Editing

Edit `main.tex` directly in any text editor. Recommendations:
- VS Code with LaTeX Workshop extension
- TeXShop (macOS)
- TeXworks (cross-platform)
- Overleaf (online, no installation needed)

After editing, rebuild using `make` or the manual pdflatex commands above.
