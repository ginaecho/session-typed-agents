# Campaign status and what is left

> **ARCHIVED 2026-08-05.** This tracked the earlier campaign (old arm names, 2 models). The current campaign's status and timings live in [`../BENCHMARK_TIMELOG.md`](../BENCHMARK_TIMELOG.md) and [`../BENCHMARK_HANDOFF.md`](../BENCHMARK_HANDOFF.md) §9.

> **Historical (pre-2026-08-05).** Uses the earlier arm names. Current campaign arm names and their mapping: see BENCHMARK_PLAN_V3.md §10.8.

**Date: 2026-08-03.** A snapshot of where the STJP benchmark campaign stands,
what remains, and — the question that motivated this document — whether the
new benchmark markdowns force a re-run of anything already done. Short answer
to the last: **no; the new work is additive, the existing ladder is frozen and
citable.** Reasoning in §4.

---

## 1. Done and committed (this session)

**Documentation (origin + synced to session-typed-agents):**
- `BENCHMARK_PLAN_V3.md` — the authoritative campaign plan.
- `reference/HOW_TO_RUN_BENCHMARKS.md` — the operational runbook (classic
  ladder §2–5, hosted-group deploy §6, report format §7, error checklist §8,
  and the Level-1 fairness rules §9).
- `reference/HOW_TO_IMPLEMENT_SUBSESSIONS.md` — the modular-compilation /
  incremental-adaptation design, incl. the four Phase-0 code gaps.
- `6_/7_/8_/9_` reports — disaster column resolved (content_pipeline and
  settlement policy-scored 0; pr_review manual-trace 0), pr_review CASE 11 on
  both models, the "hosted" terminology fix, the MAF name-mapping, the
  three-MAF-kinds plan, the FAIR COMPARISON sections.

**Code / specs / evidence (origin + synced):**
- content_pipeline and agenticpay_settlement `v1.policy` (S4 catastrophe scoring).
- memory_race value layer: `Done(Int)`, working-grammar refinement guards for
  the draft and canonical protocols, value predicates restored in the
  re-anchored goals.
- `maf_groupchat` orchestrator-holds-protocol arm + collision-proof orchestrator
  name; `registry` / `evaluate_run` wiring.
- The 13 hosted-group definitions (`group_main.py`, `gen_group_specs.py`, 13
  `group_spec.json`), each validated to build a real MAF GroupChat.
- The sync skill `tools/sync_stjp_to_upstream.py`.

**Benchmark data already final (Level-2 ladder, 8 settings × 2 models, n=10):**
CASES 1–12 in `7_RUN`, all verified (independent re-derivation, per-goal audit,
S4 policy scoring). These are complete and citable.

---

## 2. In flight / blocked

**memory_race (CASE 13) — 7 of 8 settings complete on both models; `bare` stuck.**
- Complete and verified (10/10 both models, correct 150/180 payloads — the
  value-fix works): settings 3–8 plus `unchecked_skills`. The scientifically
  important result is done.
- Incomplete: **`bare`** (setting 1, intent-only) — mini 0/10, 5.4 0/10 after
  the last resume. On memory_race the unguided agents improvise enormous
  "reconciliation" chatter, so `bare` trials are slow; and the background run
  process is reaped within minutes (the logs stop mid-first-trial with no
  traceback — external termination, not a crash). Multiple relaunches have not
  gotten `bare` past 0 completed trials.
- The 7 complete settings are intact (resume correctly skips them; no data was
  lost). What `bare` needs: a robust, continuous run — either foreground, or
  via `run_campaign.py` (stall-detect + resume) in a window that is not
  interrupted, or a per-trial hard cap so a slow trial cannot stall the process.

---

## 3. Not started (planned, needs deployments free)

1. **Hosted-group runs** — deploy the 13 groups via `azd` per model, invoke
   n=10 each (20 traces/case on the portal Hosted surface), grade, add the
   hosted row. Definitions are built and validated; deployment is the pending
   step. (Runbook §6.)
2. **MAF 3-kind campaign** — `maf_groupchat` / `maf_groupchat_llmvalid` /
   `maf_groupchat_llmvalid_orch` × all cases × both models × n=10. Arms exist;
   campaign not launched.
3. **Level-1 (big-intent) suite** — entirely new; see §4. Blocked on the four
   Phase-0 code gaps in `HOW_TO_IMPLEMENT_SUBSESSIONS.md` §3.

---

## 4. Do we have to re-run everything? — No.

The new markdowns are **additive by design**, not a retrofit. The existing
8-setting ladder is a valid **Level-2** benchmark (paragraph-scale intents);
the new framework *scopes* it, it does not invalidate it.

**What the new markdowns actually say about the existing runs:**
- Runbook §9 rule 10: "Additive, never a retrofit. … Existing Level-2 cases,
  runs, and reports are frozen and stay citable with the scope statement …
  Nothing in this section changes a case mid-campaign."
- SUBSESSIONS phasing: "Nothing in any phase modifies existing Level-2 cases,
  their runs, or their reports; those stay frozen and citable … The running
  campaign is untouched."

**Nothing in the new plan changes the existing ladder's inputs:** the 8
settings are unchanged, the projected local contracts are unchanged, the Set A
/ Set B grading is unchanged. So no trial needs re-running. Three specifics:
- **The S0–S4 severity scale** is a richer *presentation* of deviations that
  can be re-derived from the existing raw `events_*.jsonl` — no new trials.
- **The FAIR COMPARISON adjustment** (runbook §7 rule 7, as revised): raw
  end-to-end totals are the PRIMARY numbers, the shared-prose subtraction is a
  SECONDARY robustness check "valid at paragraph-scale intents only." The
  current tables already carry the raw totals; this is a wording alignment in
  the reports, not a re-run.
- **Policy-version provenance** (§7 rule 8): a manifest root-hash line to add to
  provenance — a doc/metadata addition, not a re-run.

**What IS genuinely new work (additive, not re-work):**
- Hosted-group rows and the MAF 3-kind rows — new *execution* on new surfaces /
  arms, appended to the existing tables; they do not replace the ladder.
- **The Level-1 big-intent suite is greenfield:** new case directories, a new
  `case.yaml` schema (P/R/E artifacts with hashes), the five-condition matrix
  (L1–L5), compile-cost accounting — and it must not launch until the four
  Phase-0 gaps are closed (change-signature completeness, sidecar composition,
  a single lean-contract builder, `do`-expansion for message-level consumers).
  This touches new code and new cases only; it never rewrites a Level-2 run.

**The one honest caveat.** If we later decide the *existing* cases should also
be measured under the Level-1 conditions (a handbook-scale standing policy, a
retrieval baseline, the compile bill), those would be *new* runs of those cases
under the L1–L5 matrix — a deliberate extension, not a correction. The current
Level-2 numbers remain valid for exactly what they claim: paragraph-scale
coordination, ladder settings 1–8.

**So:** re-run nothing that exists. Finish `bare` (CASE 13), then do the
additive execution (hosted groups, MAF kinds) and, separately and later, build
the Level-1 suite behind the Phase-0 gaps.

---

## 5. Recommended order when work resumes

1. Finish memory_race `bare` robustly → verify → add CASE 13 → sync.
2. Small report alignment (no runs): add the Level-2 scope statement to
   `7_/9_`, confirm raw-primary / adjusted-secondary wording, add the
   policy-version provenance line where applicable.
3. Hosted-group deploy + invoke (both models, 13 cases) → hosted rows.
4. MAF 3-kind campaign → MAF rows.
5. Level-1: close the four Phase-0 gaps (+ their exit tests), then the new
   big-intent cases and the L1–L5 matrix. Longest pole; entirely additive.
