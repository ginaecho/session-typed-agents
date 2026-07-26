# NeurIPS_VerifysAgents — workshop submission

Workshop cut of the STJP paper for the **NeurIPS 2026 Workshop "Who Verifies the
Agents? Toward Reliable Agent Development"** (Verify-Agents), Sydney, Dec 11/12.

- Website: https://verify-agents-workshop.github.io/
- OpenReview: https://openreview.net/group?id=NeurIPS.cc/2026/Workshop/Verify-Agents
- **Submission deadline: Aug 29, 2026 (AoE)** · Notification: Sep 29, 2026
- Format: 4–9 pages main text (refs/appendix excluded), NeurIPS 2026 template,
  double-blind, non-archival (dual submission with ICLR 2027 explicitly welcome).

## Contents
- `main.tex` — the paper (title: *The Compiler Verifies the Agents*). Main text
  ends on p.9; References p.10; Appendices A–E (protocol+sidecar, real-skills
  table, live five-arm table, reproducibility, responsible-use statement).
- `references.bib` — BibTeX (keys identical to the ICLR draft's, plus `mast`,
  `hoare69`, `barr15`, `dijkstra72` — the latter three ground the abstract's
  opening claim: verification presupposes a basis (Hoare assertions / the
  testing oracle problem), and the Dijkstra quote is now formally cited).
- `neurips_2026.sty` — **placeholder**: the official NeurIPS 2025 style with the
  year string updated. The style is historically unchanged year-to-year, but
  BEFORE SUBMITTING, download the official `neurips_2026.sty` from
  https://neurips.cc/Conferences/2026/CallForPapers and drop it in (same name);
  no other file needs to change.
- `fig1_system.pdf`, `fig3_projected.pdf`, `fig4_ladder.pdf` (used in main),
  `fig2_results.pdf` (available, currently unused).
- `make_figs_workshop.py` — regenerates all four figures **re-laid-out for the
  5.5in NeurIPS column** (fig2/fig3 as 2x2 grids, fig4 stacked 2x1, larger fonts,
  collision-checked label placement). The v10 originals were 11.6in 1x4 strips
  that crushed to ~47% scale in this template. Run `python3 make_figs_workshop.py`
  after any data change; then `make`.
- `Makefile` — `make` builds; `make clean` removes artifacts.

## Build
pdflatex → bibtex → pdflatex ×2 (or just `make`). TeX Live is sufficient.

## Framing vs. the ICLR draft (paper-writing/v10)
Same numbers, same honesty discipline, different lead: verification-first.
- Abstract opens on the verification-basis argument: every existing instrument
  verifies behavior *against* a spec/skill/markdown, but nothing verifies the
  basis itself (sound & complete as a coordination discipline — deadlock-free,
  goal-reaching); STJP checks it statically, before runtime resources are spent.
- §5 "Verifying the verifiers" promotes E0/E1 mutation testing, E2 red-teaming,
  the **harness fairness self-audit**, and the forensic audit to the paper's core
  (workshop Pillar 1: robust verifiers, red-teamed evaluation harnesses).
- §3 compresses MPST to guarantees-with-consequences (no projection calculus);
  committee has no PL/formal-methods members — theory sells by its consequences.
- MAST (Cemri, Pan, …, Stoica — two organizers + one invited speaker) is cited
  in the intro as the empirical problem statement STJP answers.
- Cut relative to ICLR draft: §8 seam training (one Limitations sentence),
  §9 typed extensions, E5/E6 detail. Nothing PENDING appears in this paper.

## Submission checklist
- [ ] Replace `neurips_2026.sty` with the official file once posted
- [ ] Confirm final CFP details on the workshop site (it said "full CFP to be
      announced"; page limits above match the current posting)
- [ ] Keep anonymous: no author block, repo link stays "withheld" (App. D);
      upload repo as OpenReview supplementary material or anonymized link
- [ ] Verify the workshop appears on the official neurips.cc workshop list
- [ ] Submit by Aug 29 AoE; ICLR 2027 full paper separately by Sep 24
