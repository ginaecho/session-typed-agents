# Paper Writing - STJP ICLR Paper

This directory contains the LaTeX source for the STJP ICLR paper.

Current title: **"Compile the Conversation of Multi-Agent Coordination:
Provably Safe and More Token-Efficient"**

## Directory Structure

- **v10/** - The paper (single current version; v6–v9 were removed on
  2026-07-17 — their full history remains in git)
- [`RELATED_WORK_DISCUSSION_2026-07-25.md`](RELATED_WORK_DISCUSSION_2026-07-25.md) -
  Discussion notes (not paper text) for the next version: Agentproof
  graph-vs-global-type, TraceFix boundedness and its projection gap, the
  comparison table, evidence-vs-capability, the residual-as-risk-register
  argument, and a candid self-review of the 2026-07-25 mechanisms

v10 contains:
- `main.tex` - Main LaTeX source file (single source, standalone preamble;
  `\input{seam_results.tex}`)
- `main.pdf` - Compiled PDF
- `seam_results.tex` - Results template for the trainable-seam program — the seam being the translation step from plain-language intent to formal protocol
  (26 pending-number macros; see `TEMPLATE_HOWTO.md` for the fill map)
- `fig1_system.pdf`, `fig2_results.pdf`, `fig3_projected.pdf`,
  `fig4_ladder.pdf` - Figures
- `STJP_system_figure.drawio` - Diagram source file (editable with draw.io)
- `Makefile` - Build script for LaTeX compilation
- `make_figs_v2.py` / `make_drawio.py` - Figure generation scripts
- `README.txt` - Build/status notes
- `CHANGELOG_v10.md` - All edits with rationale (including the title
  history and the v9→v10 integration of the real-skills live runs)

## Building the Paper

### Prerequisites

Ensure you have LaTeX installed:

```bash
# macOS (with Homebrew)
brew install mactex

# Ubuntu/Debian
sudo apt-get install texlive-latex-base texlive-latex-extra \
  texlive-fonts-recommended texlive-bibtex-extra

# Windows
# Download from https://www.tug.org/texlive/windows.html
```

### Building from Source

```bash
cd v10
make   # Compiles main.tex -> main.pdf (two pdflatex passes)
```

Or manually:

```bash
pdflatex main.tex
pdflatex main.tex
```

(No `bibtex` step is needed; the bibliography is inline via
`thebibliography`.)

### Regenerating Figures

```bash
python make_figs_v2.py
```

This requires:
- Python 3
- draw.io CLI (for `.drawio` files)
- ImageMagick (for image conversions)

## Version History

- **v10.1** (2026-07-19, current) - fairness-audit alignment pass: per-arm
  success rule defined in the methodology, strict-rule tables labeled with
  Wilson 95% intervals, contended wall-clock numbers marked indicative, a
  new "Fairness audit, corrected metrics, and pre-registered ablations"
  subsection (hint-free gate and last-receiver scheduling control, framed
  pending — no invented numbers), expanded Limitations and a full
  Reproducibility appendix. See `v10/CHANGELOG_v10.md` ("v10.1") and the
  readiness assessment in `ICLR_READINESS.md`.
- **v10** - *"Compile the Conversation of Multi-Agent
  Coordination: Provably Safe and More Token-Efficient"*. Three groups of
  changes over v9:
  1. **Retitled twice** - first from v8/v9's "Guarantees, Not Averages:
     Type-Checking Agent Conversations with Multiparty Session Types" to
     "Compile the Conversation: Multiparty Session Types Make Multi-Agent
     Coordination Provably Safe --- and Cheaper than Failure", then to the
     current title, with the **abstract rewritten in the same direction**:
     it now leads with the claim that the compiled arm is simultaneously
     the safest and the most token-efficient configuration, organized
     around the three token classes the compiler removes (prose re-reading
     -> projection, 63% fewer tokens and a 9.2x->17.1x scaling gap;
     polling -> scheduling, -73% LLM calls, 9x cost-to-goal, 4-22x
     cost-to-clean-goal; and failure itself -> enforcement, the 3.6x
     livelock and the zero-token static rejection).
  2. **Real skills, run live (new block in §7, anchor `sec:real`, Table
     `tab:realcases`)** - integrates `docs/results` RESULT_8–RESULT_11:
     nine cases from unmodified public skill/agent files, the two-model
     coin-flip reversal, the first live `rec`/`choice` looping runs, the
     plan-as-text **livelock** at 3.6x the cost of the succeeding enforced
     arm, and the two static Scribble rejections that debugged the
     corrected review protocol.
  3. Ripple edits: Contribution 3, Conclusion, Limitations
     (round-batched role-play independence caveat).

  See `v10/CHANGELOG_v10.md` for all edits with rationale and
  `v10/README.txt` for build/status notes.
- **v9 and earlier** - removed from the working tree on 2026-07-17;
  recoverable from git history. Summary: v9 = v8 + the realized
  trainable-seam training program (§8) and its results template; v8 =
  ICLR repositioning + concurrent-work citations; v7/v6 = earlier drafts.

## Editing

Edit `v10/main.tex` directly in any text editor. Recommendations:
- VS Code with LaTeX Workshop extension
- TeXShop (macOS)
- TeXworks (cross-platform)
- Overleaf (online, no installation needed)

After editing, rebuild using `make` or the manual pdflatex commands above.
