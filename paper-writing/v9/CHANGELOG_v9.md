# STJP paper v9 — changes from v8

v9 = v8 plus a carefully positioned treatment of the "user intent → global
protocol" trainable-seam system (the "seam" is the translation step from
plain-language intent to formal protocol): v8's §7 *promised* the seam is
trainable; v9 shows the training program *realized* as system + instruments
+ preregistration, with the GPU numbers pending and connected to a results
template so they drop in without restructuring. v8's submission shape and
every v8 claim are preserved.

## Positioning decision (rationale first)
1. NEW SECTION, not an in-place paragraph expansion. The v8 "The seam is
   trainable, not merely open" paragraph lived inside §7 (the n=100 validation
   suite), right after E5. The realized program is now substantial enough
   (system under training + four measured instruments + six preregistered
   gates + a novelty argument + a lineage-positioning paragraph) that inlining
   it would overload §7 and bury it. It is therefore a dedicated
   **§8 "The Trainable Seam, Realized"** placed as the BRIDGE: immediately
   after §7 (which ends on E5's deterministic-half-done + pre-registration
   audit) and immediately before §8-old "Three Typed Extensions" (now §9). This
   keeps the narrative arc — measured suite → the one honest open seam →
   realized program to close it → typed extensions — and lets §7's E5 flow
   forward-reference the new section rather than digress.
2. The v8 trainable-seam paragraph (§7) is REPLACED by a 2-sentence bridge that
   forward-references §8 and states the GPU outcomes are the declared next step
   and fill the pending E5 cells through the shared template. No claim lost;
   the enumerated (i)–(iv) mechanism detail moves into §8's reward-stack and
   gates subsections where it is developed properly.

## New content — §8 "The Trainable Seam, Realized" (anchor: after §7, label sec:seam)
3. §8.1 "Two axes, treated differently": validity is machine-checkable (real
   Scribble-java oracle, total + counterexample-producing) and drives training
   directly; faithfulness is not machine-decidable and is the residual judged
   surface, measured by a memoryless panel that is verifier-only until it passes
   a calibration gate. Frames the whole program as the paper's judge-free
   discipline carried into training. Rationale: the two-axis distinction is the
   load-bearing idea that keeps the training honest (no uncalibrated judge
   touches a number).
4. §8.2 "The system under training and its verifier reward stack": translator T
   + repairer R over one 7B base (LoRA heads differ), draft→validate→repair
   loop mirroring the live 4-reject→pass trace; verifier reward stack (GCD
   removes syntactic invalidity; validator pass reward; cheap canonical-EFSM
   equivalence proxy with FULL bisimulation reserved for eval because measured
   at 10–40× a validation; guard co-emission; faithfulness term = 0 until the
   calibration gate). Lineage cited (see §"citations"). Format-tax caveat cited
   and stated as the reason GCD-on/off is a primary two-sided test (H1).
5. §8.3 "The instruments, measured before any training" + Table
   `tab:seam-instruments` (MEASURED numbers, not macros — these exist today):
   - Grammar (W2): 100% corpus round-trip (113/113 non-skip .scr; 5 skips are
     rejected LLM drafts, correctly unparseable), 1,000/1,000 sampled protocols
     parse, 0 parse-level rejections under real Scribble.
   - Corpus (W3): 671 EFSM-deduped families (bounded run; ≥5k reachable),
     signature-vs-checker 200/200 agreement, 860 repair tuples + 1,746
     calibration near-misses, family splits leakage-check GREEN (599/76/76).
   - Panel (W6 / PANEL_SMOKE): 14 seats live; swapped-pair canary (a planted
     check item with a known correct answer) rejected at 0.99; the
     trade_deadlock case — both forward seats accepted (0.88/0.82)
     while the blind back-translation seat scored 0.25 (protocol-repairs-the-
     intent phenomenon), a shared forward-seat confirmation bias the class
     structure caught.
   - Mining (W8): 609 artifacts → 0 surviving deterministic compaction —
     in-the-wild evidence that hand-written skills under-determine coordination,
     explicitly tied back to the paper's thesis.
6. §8.4 "Preregistered gates, and the results template": H1 (GCD two-sided
   format-tax test), H2 (best-of-n fills E5), H3–H4 (SFT/GRPO, H4 headroom-aware),
   H5 (panel calibration with honest audit-power math: Wilson 95% LB ≥ 0.80 over
   n≥200, ~370 for an honest 85%; binds on non-circular strata), H6 (transfer as
   estimation with CI). Graceful-degradation clause (verifier rewards never
   depend on the judge). Then Tables `tab:seam-baselines` (T0 per model) and
   `tab:seam-trained` (SFT/GRPO/panel/transfer) — the TEMPLATE, every cell a
   macro rendering \pending.
7. §8 closing paragraph "Positioning and verified novelty": one-to-two-sentence
   lineage touch (RLVR/GRPO; expert iteration; back-translation/autoformalization;
   judge panels + effective-votes + robust aggregation) and the verified-novelty
   line — nine query variants, no NL→MPST prior; the two near-misses named
   (ZipperGen = MSC coordination DSL, no NL front end; Liu et al.
   arXiv:2511.17977 = NL→network I/O grammars, not MPST).

## Template mechanism (new files)
8. `seam_results.tex` — 26 result macros (+ `\pending` marker + `\seamfill`
   idiom), each defaulting to a visible \pending: E5 cells (3), T0 per-model
   validity@1/@10/repair/\$-accepted (12), SFT validity@1/bisim@1/\$-accepted (3),
   GRPO validity/equiv/repair deltas (3), panel AUC/human-LB/swap/eff-votes (4),
   transfer gap (1). \input in the preamble (anchor: after the notation macros,
   before \title).
9. `TEMPLATE_HOWTO.md` — maps every macro → the exact eval-harness output field
   (experiments/seam_bench/eval metrics / the phase-gate reports) that fills it,
   plus the one-line fill idiom and the pending-cell discipline.
10. E5 pending cells CONNECTED to macros (anchor: Table `tab:transfid`): the three
    v8 hardcoded "pending" rows (First draft passes validator / Repair rounds to
    validity / Guard sidecar co-emission) now read \seamEfiveFirstDraft /
    \seamEfiveRepairRounds / \seamEfiveGuardCoemit, so the E5 table and the §8
    tables update from one file post-GPU.

## v8 claims touched (minimally, and only to strengthen)
11. Contribution 5 ("A benchmark, released and self-tested"): appended one clause
    naming the released seam instruments (validated grammar, EFSM-equivalence
    scorer, faithfulness panel, EFSM-deduped corpus, preregistered H1–H6
    protocol) — all MEASURED — and pointing at the §8 results template, with the
    training runs flagged as the declared next step. Rationale: the instruments
    are real released artifacts and earn a contributions mention; NO pending
    number enters the contributions, preserving the empirical-first shape.
12. Limitations "translation seam": v8's "Planned:" sentence replaced with
    "Underway:" pointing at the realized §8 instruments (all measured) + the
    preregistered-and-pending GPU outcomes entering via the template.
13. NOT touched (deliberate): title, abstract, and the other four contributions.
    Rationale — the program's HEADLINE numbers (validity/bisim/panel-AUC/transfer)
    are pending GPU; promoting them into the title/abstract would front-load
    pending numbers against the paper's empirical-first, pending-cell-honest
    discipline. The abstract's thesis punchline is preserved verbatim.

## Citations (bib extended; inline thebibliography, no external .bib in this project)
14. +13 entries, `\begin{thebibliography}{28}` → `{41}`:
    - RLVR/GRPO lineage: star22 (STaR / expert iteration), deepseekmath (GRPO,
      RL-from-verifiable-rewards), dapo, gspo, drgrpo (post-R1 length-bias /
      entropy-collapse fixes).
    - Autoformalization lineage: sennrich16 (back-translation), autoform
      (Lean quality + cycle-consistency + miniF2F pass@k methodology).
    - Judge-panel lineage: poll24 (PoLL juries), kohli26 (nine-judges /
      effective-votes), ropoll26 (robust geometric-median aggregation --
      geometric median: a way to combine scores that resists being dragged
      off by one extreme judge).
    - GCD format-tax: formattax26, crane25 (basis for the H1 two-sided test).
    - Novelty near-miss: liu25netproto (NL→network-protocol I/O grammars).
    ZipperGen (bollig26) reused from v8 as the other near-miss.

## LaTeX discipline (could not compile — no texlive in sandbox)
15. No new packages; only existing environments/macros/commands used (table,
    tabular, booktabs rules, minipage, itemize, \citep/\citet, \textsc, \emph).
    New `\pending`/`\seamfill`/result macros are plain \newcommand, letters-only
    control sequences; no clash with existing macros (\gtG,\lt,\ed,\proj,\stjp,…).
16. Sanity checks run (grep/python, stated as required since no pdflatex):
    - \begin vs \end: 39 vs 39; per-environment balance diff = ALL BALANCED.
    - Brace balance (verbatim stripped, escaped braces removed): 1066 open /
      1066 close — balanced.
    - Citations: 47 distinct keys used, 48 bibitems defined, 0 used-but-undefined;
      all 13 new keys present; `owasp` remains defined-but-unused (inherited from
      v8, harmless under numbered natbib).
    - Macros: all 26 \seam* macros referenced in main.tex are defined in
      seam_results.tex; \pending and \seamfill defined once.

## 2026-07-12 — claim rescoping and terminology pass

17. **Rescoped the real-skills mining claim (§8.3, `tab:seam-instruments`).**
    The prose and table row previously said the 0/13 compaction survival rate
    was "because independently authored skills do not carry the coordination
    structure a global type requires" and called that "the paper's thesis
    observed in the wild." That is stronger than what W8 measured: W8
    (`docs/reference/reports/seam/W8_miner.md` §4, §6) shows the 0/13 result
    together with two controls — a synthetic team with an explicit
    interaction structure passes the identical pipeline, and the four mined
    `skills_safety` teams that had already been through an earlier,
    LLM-assisted compaction still fail multiparty compatibility as
    originals — which locates the failure in the inputs, not the pipeline,
    but does not establish that the coordination structure is *absent* from
    the mined skills (only that it is not stated in a machine-recoverable
    convention). Replaced the prose paragraph and the table row with the
    scoped version and added the explicit next step (an LLM-assisted
    compaction run with a human-read baseline) that would be needed before
    any `test-real` claim rests on mined data. Rationale: the paper should
    not claim more than its own controls support; the scoped version is the
    honest read of W8's own numbers. Same rescoping applied to
    `docs/8_INTENT_TO_PROTOCOL_TRAINING.md` (§"The miner's honest finding")
    and to this paper's own `README.txt`, which stated the same unscoped
    claim in the v9 change summary.
18. **Plain-language terminology pass** across `main.tex`,
    `paper-writing/v9/README.txt`, and this changelog (and, as a project-wide
    sweep, the `docs/` and `experiments/seam_bench/judge/human_audit/`
    prose), per the new "Plain-language writing rule" in the top-level
    `AGENT.md`: every term of art gets a one-clause plain-language gloss on
    first use per document (e.g. "canary" → "a planted check item with a
    known correct answer"; "seam" → "the translation step from
    plain-language intent to formal protocol"; "geometric median" → "a
    robust way to combine scores so one extreme judge cannot drag the
    result"; "escrow" → "a neutral third party that holds funds until both
    sides deliver"), and "wired"/"wire" is replaced with "connect"/
    "connected" throughout prose. No code, identifiers, JSON fields, test
    names, or LaTeX macro names were touched — only prose. Rationale: the
    project owner flagged unglossed insider shorthand as a readability
    problem; this pass fixes it without changing any measured claim.
19. **LaTeX discipline check after edits 17–18:** `\begin`/`\end` count
    39/39, matched per environment (no mismatches); brace count 1074/1074
    (open/close, escaped braces and verbatim-style spans excluded) —
    balanced. No new packages introduced.

## Build (unchanged from v8)
`make` → pdflatex ×2 → main.pdf (main.tex \input{seam_results.tex}); `make docx`
for pandoc export; `make figs` regenerates figures. NOT COMPILED in this sandbox
(no texlive/pandoc) — compile locally. Pre-submission TODO (carried from v8):
run best-of-n T0 to fill E5 + T0 cells; the T1/T2/panel-calibration runs fill the
rest via seam_results.tex; consider one non-Claude E3 point; swap preamble for
iclr2027_conference kit.

## Update 2026-07-11b — mining claim now reports the run follow-up

The §8 real-skills passage and its instruments-table row previously framed
the absent-vs-implicit question as a preregistered follow-up not yet run.
That follow-up (model-read extraction over the same 13 teams, evidence-only
discipline) has now run (report `W16_llm_read_extraction.md`). Rewrote the
passage to report its measured result: 3/13 teams yield a valid protocol
(all from this project's own worked examples), a 4th surfaces a genuine
deadlock, 7/13 have nothing to surface, and the unmodified upstream GitHub
teams recover zero — strengthening the scoped claim that real independently
authored skills under-determine coordination while noting mined data yields
too few test-real items to stand alone. Table row and docs guide 8 synced.
Human-read baseline packaged, pending. LaTeX balance re-checked: begin/end
39/39, braces balanced.
