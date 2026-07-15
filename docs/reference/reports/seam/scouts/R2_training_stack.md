# Scout R2 — Training Stack Verification

Scope: `SEAM_TRAINING_EXECUTION_PLAN.md` §2 (system under training) and §4
(training phases). Verified against current web sources on 2026-07-11.
Every claim below is backed by either a fetched primary-source doc, the
actual TRL/vLLM source on GitHub (`main` branch, pulled via `curl` on
2026-07-11), or PyPI's JSON API (also queried live). Where a search-engine
summary was the only source and could not be corroborated against a
primary doc, that is flagged explicitly.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. TRL GRPOTrainer](#1-trl-grpotrainer)
- [2. vLLM guided decoding — the load-bearing check](#2-vllm-guided-decoding--the-load-bearing-check)
- [3. Qwen2.5-Coder-7B-Instruct — still the right small coder?](#3-qwen25-coder-7b-instruct--still-the-right-small-coder)
- [4. Serving/GPU — Modal vs RunPod vs Lambda](#4-servinggpu--modal-vs-runpod-vs-lambda)
- [5. Version pin block](#5-version-pin-block)
- [Summary of concrete plan edits (§2/§4 of the execution plan)](#summary-of-concrete-plan-edits-§2§4-of-the-execution-plan)
<!-- MENU:END -->

## 1. TRL GRPOTrainer

**Plan assumes (§2):** "TRL (`SFTTrainer`, `GRPOTrainer`) + PEFT LoRA + vLLM
rollouts... No custom trainer code."

**Actually true now:**

- Current stable release is **TRL v1.8.0** (released 2026-07-09, two days
  before this scout ran). TRL crossed 1.0 in ~April 2026 with a unified
  CLI/config system; v1.8.0 adds entropy regularization for GRPO and
  streamlined QLoRA via `quantization_config`.
- `reward_funcs` signature (confirmed against
  `trl/trainer/grpo_trainer.py` and `docs/source/grpo_trainer.md` on
  `main`): a callable (or async coroutine) taking `prompts`,
  `completions`, `completion_ids`, `trainer_state`, `log_extra`,
  `log_metric`, and all extra dataset columns as kwargs; **must** accept
  `**kwargs` for forward compatibility; returns `list[float]`, one reward
  per completion; `None` entries let task-specific reward fns abstain.
  Multiple reward fns are summed/weighted via `reward_weights`. This part
  of the plan's assumption is accurate and low-risk.
- vLLM rollout integration: `GRPOConfig.use_vllm` (bool) +
  `vllm_mode` = `"colocate"` (default, shares GPU with trainer) or
  `"server"` (separate process over HTTP). Confirmed live in
  `grpo_trainer.py`. Default is colocate, which the plan should state
  explicitly for a single-A100 job (server mode needs a second GPU).
- **Version ceiling that the plan does not currently pin**: TRL only
  supports `vllm>=0.16.0,<=0.23.0` — this is a hard-coded check in
  `trl/import_utils.py::is_vllm_available` (`Version("0.16.0") <=
  Version(_vllm_version) <= Version("0.23.0")`, else it warns and risks
  breakage), and is also declared in TRL's `pyproject.toml` vllm extra.
  **vLLM's own latest release is 0.24.0** (2026-06-30) — one minor above
  what TRL supports. If a worker `pip install`s "latest vllm," it will
  silently exceed TRL's tested ceiling. This must be a pinned range in
  the lockfile, not "latest."
- Multi-adapter support: PEFT supports multiple named adapters on one
  base model (`get_peft_model` + `add_adapter` + `set_adapter`), with one
  caveat — LoRA configs using `target_parameters` support only one active
  adapter at a time (falls back to adapters-disabled for ref logprobs in
  that case). In practice, joint T+R training inside a single
  `GRPOTrainer` run is **not** a first-class TRL feature; the standard
  pattern is two separate trainer runs (one adapter each), which is
  exactly what the plan already does in §4 ("Train T on D2... train R on
  D3" as separate steps) — no plan edit needed here, just confirmation
  the plan's structure already avoids the unsupported joint-training path.
- Known open issues relevant to custom deterministic rewards: reward
  functions that shell out to subprocesses (our validator call) are a
  documented friction point — TRL runs reward functions with a
  configurable number of parallel workers, and community guidance
  (Axolotl's GRPO docs, echoed in TRL issue threads) is that
  subprocess/IPC overhead can exceed the reward computation cost unless
  batched. This directly matches the plan's own throughput note (§2:
  "each validation is a JVM spawn ~0.5–1s... cache verdicts by
  protocol-text hash") — the plan already anticipated this correctly;
  just confirming it's a real, currently-open friction class, not
  something TRL solved for you.

**Alternative frameworks (friction comparison for single-node LoRA GRPO):**

| framework | single-node LoRA GRPO maturity | setup friction | vLLM rollout integration | verdict for this project |
|---|---|---|---|---|
| **TRL (HF)** | Native since ~early 2025, now v1.x stable surface | Low — same Accelerate config/dataset formats as our SFT | Built-in colocate/server modes | **Keep.** Team is already HF-stack; model is 7B (well under the ~30B point where TRL's per-GPU efficiency starts to lag verl/OpenRLHF) |
| **verl (ByteDance)** | Most complete parallelism/LoRA support, "most battle-tested," but oriented at multi-GPU/distributed scale | High — steep learning curve, non-trivial cloud config per community reports | Yes, but heavier ops surface | Overkill; adds ops friction the plan explicitly wants to avoid |
| **OpenRLHF** | Good async/colocation support; one third-party benchmark showed ~3.1x faster GRPO epoch than TRL on GSM8K | Medium — separate ecosystem from HF Trainer/Accelerate, different checkpoint/dataset conventions | Yes | Faster, but the throughput isn't the bottleneck here (reward-fn JVM spawns dominate wall-clock, not the RL step) — the ecosystem-switch cost isn't worth it for our compute envelope ($100-350 total for GRPO) |
| **Unsloth (GRPO mode)** | LoRA/QLoRA GRPO supported (incl. on free-tier GPUs); wraps TRL, doesn't replace it | Low — drop-in `FastLanguageModel` + `PatchFastRL`; patches TRL's vLLM `GuidedDecodingParams` import for compat | Rides on TRL's vLLM path (same colocate/server modes) | **Worth trialing as an accelerant**, not a replacement — see pin list caveat below |

**Verdict:** TRL is still the right choice; keep it. Concrete plan edits:
add the explicit vLLM ceiling (`vllm<=0.23.0`) to the pin block (see §5
below), and state in §2 that GRPO rollouts run in **colocate mode** by
default on the single A100 (server mode needs a second GPU it doesn't
have).

---

## 2. vLLM guided decoding — the load-bearing check

**Plan assumes (§2):** 'Serve with **vLLM guided decoding** (xgrammar
backend, `guided_grammar=`). That gives GCD in *both* eval and GRPO
rollouts with zero custom decoding code.'

**Actually true now — three separate corrections:**

1. **Param name is stale.** `guided_grammar` (and `guided_json`,
   `guided_regex`, `guided_choice`, `guided_decoding_backend`) were
   **removed in vLLM v0.12.0**. Current API (confirmed against
   `vllm/docs/features/structured_outputs.md` on `main`, which contains
   an explicit deprecation table) is `StructuredOutputsParams(grammar=...)`
   passed via `SamplingParams(structured_outputs=...)`, or
   `{"structured_outputs": {"grammar": ...}}` in the OpenAI-compatible
   server's `extra_body`. The plan must say `structured_outputs=` /
   `StructuredOutputsParams(grammar=...)`, not `guided_grammar=`.
2. **Default backend is `auto`**, which picks per-request between
   **xgrammar** and **guidance** (llguidance); you can force one with
   `--structured-outputs-config.backend`. xgrammar remains the
   performance-oriented default for grammar-heavy, reused-grammar
   workloads (exactly our case: one fixed Scribble grammar reused across
   thousands of rollouts) — plan's backend choice is directionally right,
   but should pin `backend=xgrammar` explicitly rather than relying on
   `auto`, since `auto`'s selection logic can change across vLLM releases.
3. **Grammar dialect: this is the part the plan gets wrong.** xgrammar's
   native grammar format is **EBNF following the GBNF (GGML BNF /
   llama.cpp) convention** — not Lark. vLLM does auto-detect and convert
   Lark-style input (`grammar_is_likely_lark` heuristic, added by
   vLLM PR #10870), but that heuristic has an open, confirmed bug
   (vLLM issue #11118: "`grammar_is_likely_lark` doesn't work correctly")
   where valid EBNF/GBNF can be misclassified as Lark or vice versa.
   **Concrete plan edit:** author `stjp_core`'s Scribble surface grammar
   directly in GBNF-style EBNF (the dialect in vLLM's own worked example:
   `root ::= select_statement`, `column ::= "col_1 " | "col_2 "`, etc.),
   not Lark, and do not rely on vLLM's Lark-to-GBNF auto-conversion. W2's
   "round-trip tested against the corpus" step should include a smoke
   test (a quick end-to-end check) that the grammar is *not* misclassified
   (pass it through both
   backends once and diff outputs) before trusting it in GRPO rollouts.

**The load-bearing question: does guided decoding work inside TRL's GRPO
rollout path, or does A1+A5 break?**

Answer: **it works, but not through the parameter the plan names, and
not through TRL's "official," documented structured-output surface.**

- `GRPOConfig` exposes exactly **one** dedicated structured-output field:
  `vllm_structured_outputs_regex: str | None` — confirmed by `grep`ing
  the live `trl/trainer/grpo_config.py` source directly (line ~609).
  It is **regex-only**. There is no `vllm_structured_outputs_grammar` or
  equivalent dedicated field in GRPOConfig today.
- However, both of TRL's vLLM rollout code paths — `vllm_serve.py`
  (server mode) and `trl/generation/vllm_generation.py` (colocate mode) —
  build `SamplingParams` from a generic `generation_kwargs: dict`, and
  **both contain this exact pass-through** (confirmed in both files):
  ```python
  elif isinstance(structured_outputs_kwargs := generation_kwargs.get("structured_outputs"), dict):
      generation_kwargs["structured_outputs"] = StructuredOutputsParams(**structured_outputs_kwargs)
  sampling_params = SamplingParams(**generation_kwargs)
  ```
  This means `GRPOConfig(generation_kwargs={"structured_outputs":
  {"grammar": "<our GBNF grammar text>"}})` **does** reach vLLM's real
  `StructuredOutputsParams(grammar=...)` on both the colocate and server
  rollout paths — i.e., full context-free-grammar-constrained decoding
  *is* reachable inside GRPO rollouts today. It is just undocumented (the
  GRPO docs only mention the dedicated regex field) and untested by TRL's
  own test suite as far as the two open GitHub issues below indicate.
- Corroborating open issues (both current, both directly on this gap):
  huggingface/trl **#3924** ("Feature request for GRPO trainer: vLLM
  guided decoding with xgrammar (JSON)") — still **open**, no maintainer
  fix; huggingface/trl **#5154** ("Support for constrained decoding with
  JSON Schema in GRPO Trainer + vLLM") — **closed**, proposed exactly the
  `generation_kwargs["structured_outputs"]` dict pass-through as the fix,
  consistent with what the source shows today.

**Concrete plan edit for §2:** Replace "`guided_grammar=`" with:
"pass the GBNF-EBNF grammar via `GRPOConfig(generation_kwargs=
{"structured_outputs": {"grammar": GRAMMAR_TEXT}})`, which reaches vLLM's
`StructuredOutputsParams` on both TRL rollout paths — undocumented but
present in `trl` `main` as of 2026-07-11 (see `vllm_generation.py` /
`vllm_serve.py`). This is *not* the same as the dedicated
`vllm_structured_outputs_regex` field, which is regex-only and
insufficient for a CFG." Also add a W2 acceptance check: "grammar-guided
rollout smoke test inside an actual `GRPOTrainer.train()` step (1 batch),
not just standalone `vllm.LLM.generate()`" — since the plumbing is
undocumented, a standalone-vLLM test alone would not catch a
generation_kwargs wiring regression.

No fallback needed (post-hoc filtering / different rollout engine) — the
combination works, it just needs the corrected param path.

---

## 3. Qwen2.5-Coder-7B-Instruct — still the right small coder?

**Plan assumes (§2):** Qwen2.5-Coder-7B-Instruct (Apache-2.0) as base,
with a `-14B` upgrade path and Llama-3.1-8B-Instruct as fallback.

**Actually true now:**

- **Qwen3-Coder exists only as MoE models**: `Qwen3-Coder-30B-A3B`
  (3B active) and `Qwen3-Coder-480B-A35B` (35B active), plus a newer
  `Qwen3-Coder-Next` (80B total, 3B active, ~70.6% SWE-bench Verified).
  Confirmed via the official `QwenLM/Qwen3-Coder` GitHub repo and the
  Qwen3-Coder HF collection — **there is no dense Qwen3-Coder in the
  3B–14B range**; a community request for one ("any chance of a smaller
  coding model in the 30-70b range?") is an open discussion on the
  480B model card, unresolved. So Qwen2.5-Coder remains the only dense
  coder-specific family in the target size band from this vendor.
- **Qwen3-Coder-30B-A3B (MoE, Apache-2.0) is a real alternative worth
  naming**, not adopting by default: 3B active params gives fast
  inference and it's within the "fits on one A100-80GB" envelope for
  frozen-base bf16 weights (~60GB) + LoRA, but MoE routing adds two
  friction sources the plan explicitly wants to avoid: (a) LoRA/PEFT on
  MoE routing layers is less battle-tested than dense-model LoRA, and
  (b) grammar-guided decoding through vLLM's MoE-aware batching path is
  less exercised than the dense path we just spent §2 verifying. Given
  the plan's stated "minimum implementation friction" design goal, this
  is a **documented alternative for the T1-miss escalation, not a
  default swap.**
- **Qwen3.5 / Qwen3.6 dense generalist models** now exist above the 14B
  band and outperform Qwen2.5-Coder on general/coding benchmarks —
  notably `Qwen3.6-27B` dense, reported at 77.2% SWE-bench Verified
  ("best dense open-source coder" per one source), Apache-2.0. This is
  larger than the plan's stated `-14B` ceiling but is a legitimate
  concrete target for the "H3 misses narrowly, try a bigger model" branch
  in §8, replacing the vague "-14B upgrade path" language with a named,
  currently-real ladder: **Qwen2.5-Coder-14B-Instruct → Qwen3.6-27B
  (LoRA on 80GB is tight but feasible; would need to drop vLLM colocate
  KV-cache headroom or move to server mode with a second GPU).**
- **Tokenizer sanity for Scribble-like syntax:** Qwen's tokenizer is a
  byte-level BPE (tiktoken-based) with no `<unk>` token — by
  construction it cannot fail to tokenize braces `{}`, arrows `->`,
  or ASCII keywords (`role`, `choice`, `rec`, etc.); worst case it falls
  back to single-byte tokens for rare sequences, which is inefficient
  but never invalid. This is an architectural argument, not an empirical
  one — I found no documented tokenizer pathology for Qwen2.5-Coder on
  code-like DSL syntax in current sources, but this is exactly what the
  plan's own T1-gate "decide at T1 gate, not before" language already
  covers, so no plan edit is needed beyond confirming there's no red flag
  to escalate on now.

**Verdict:** Keep `Qwen2.5-Coder-7B-Instruct` as primary. Concrete edit:
replace the vague "a `-14B` upgrade path exists" with the two-step ladder
above (14B dense, then Qwen3.6-27B dense if that also misses), and add
one sentence noting `Qwen3-Coder-30B-A3B` (MoE) as a considered-and-rejected
alternative with the specific reason (LoRA-on-MoE + guided-decoding
maturity risk), so a future reader doesn't re-litigate it from scratch.

---

## 4. Serving/GPU — Modal vs RunPod vs Lambda

**Plan assumes (§2):** "Single-node, rented GPU (Modal or RunPod...)."
Cost envelope: SFT ≈ 2–6 A100-hrs (~$10–30, i.e. ~$5/A100-hr assumed);
GRPO ≈ 24–72 A100-hrs (~$100–350, i.e. ~$4–5/A100-hr assumed).

**Actually true now (rates gathered 2026-07-11; treat as directional —
spot/community pricing moves daily, confirm at spend time):**

| provider | A100-80GB | H100 | notes |
|---|---|---|---|
| **RunPod** (Secure Cloud, on-demand) | ~$1.19–1.39/hr | SXM ~$2.69–3.29/hr; PCIe ~$1.99–2.89/hr | Community Cloud spot as low as ~$0.68/hr A100 (less availability guarantee); per-second billing; official pricing at runpod.io/pricing |
| **Modal** | ~$2.50/hr ($0.000694/sec) | ~$3.95/hr ($0.001097/sec) | Per-second billing, scale-to-zero; Starter plan free w/ $30/mo credits (~7.5 H100-hrs); startup/academic program up to $10k credits |
| **Lambda Labs** | ~$1.99/hr (PCIe, single) to $2.79/GPU/hr (SXM, 8-GPU) | $3.29/hr (PCIe) to $4.29/hr (SXM, single) | Optimized for multi-GPU 8x nodes; less competitive for a single-GPU LoRA job than RunPod |

The plan's ~$4–5/A100-hr assumption is **conservative** — current
cheapest on-demand single-A100-80GB pricing (RunPod Secure Cloud,
~$1.2–1.4/hr) is roughly 3-4x cheaper. This doesn't require a go/no-go
edit (the plan's dollar ceilings in §8 already have headroom), but it's
worth flagging so nobody over-budgets or picks a more expensive provider
"because the plan implies ~$5/hr is normal."

**Recommendation:** **Primary: RunPod Secure Cloud** — cheapest
predictable on-demand A100-80GB/H100 for a single-node job, per-second
billing matches the plan's short SFT/GRPO windows, and its templates
support custom Docker images (needed for the pinned CUDA/vLLM/xgrammar
stack + the Scribble-java/Maven toolchain from `tools/setup_scribble_cloud.sh`).
**Fallback: Modal** — higher $/hr but a cleaner Python-native SDK for
the plan's "CI-style scripts, not narrative claims" phase-gate philosophy
(§1), scale-to-zero avoids idle billing between phase gates, and the
startup/academic credit program is worth applying for given the
program's <$1k total budget. Lambda Labs is not recommended as either
primary or fallback for this specific job shape (single-GPU LoRA);
its pricing/ops model is optimized for multi-GPU nodes we don't need.

---

## 5. Version pin block

All pins below were checked for **mutual compatibility today** by reading
the actual dependency constraints declared by each package (via
`pip`/PyPI JSON metadata and TRL's `pyproject.toml`/`import_utils.py` on
GitHub `main`), not by trusting "latest is fine."

```
# CUDA / torch — must exactly match what vllm==0.23.0 pins internally
--extra-index-url https://download.pytorch.org/whl/cu128
torch==2.11.0
torchvision==0.26.0
torchaudio==2.11.0

# vLLM — DO NOT use latest (0.24.0). TRL's is_vllm_available() hard-checks
# 0.16.0 <= version <= 0.23.0 and warns/risks breakage outside that band.
vllm==0.23.0

# xgrammar — vllm==0.23.0 declares `xgrammar<1.0.0,>=0.2.0`; current
# latest (0.2.3) satisfies that.
xgrammar==0.2.3

# transformers — must satisfy BOTH constraints simultaneously:
#   trl==1.8.0      -> transformers>=4.56.2, !=5.1.0
#   vllm==0.23.0     -> transformers>=4.56.0, excludes 5.0.*,5.1.*,5.2.*,5.3.*,5.4.*,5.5.0
# Latest (5.13.1) satisfies both.
transformers==5.13.1

# PEFT — trl requires peft>=0.8.0; latest is 0.19.1.
peft==0.19.1

# accelerate — transitive dep of trl/transformers; pin to avoid drift.
accelerate==1.14.0

# TRL itself — current stable, v1.0 unified CLI/config lineage.
trl==1.8.0
```

Evidence per pin:
- `vllm>=0.16.0,<=0.23.0` and `peft>=0.8.0` and
  `transformers>=4.56.2,!=5.1.0`: read directly from TRL's
  `pyproject.toml` (`vllm = ["vllm>=0.16.0,<=0.23.0"]`, `peft =
  ["peft>=0.8.0"]`, core deps `"transformers>=4.56.2"`,
  `"transformers!=5.1.0"`) and `trl/import_utils.py`
  (`is_vllm_available` version-range assertion), both pulled live from
  [`github.com/huggingface/trl`](https://github.com/huggingface/trl) `main` on 2026-07-11.
- `torch==2.11.0` / `torchvision==0.26.0` / `torchaudio==2.11.0` and
  `xgrammar<1.0.0,>=0.2.0` and the transformers exclusion list
  (`!=5.0.*,!=5.1.*,!=5.2.*,!=5.3.*,!=5.4.*,!=5.5.0`): read directly from
  vLLM 0.23.0's own `requires_dist` metadata via
  `https://pypi.org/pypi/vllm/0.23.0/json`.
- Latest package versions (`trl` 1.8.0, `vllm` 0.24.0 vs pinned 0.23.0,
  `xgrammar` 0.2.3, `transformers` 5.13.1, `peft` 0.19.1, `accelerate`
  1.14.0): read from each package's `https://pypi.org/pypi/<name>/json`
  on 2026-07-11.
- CUDA build selection (cu128): PyTorch 2.11 supports CUDA 12.6/12.8/13.0
  wheel channels; cu128 is the safe middle choice for both Ampere (A100)
  and Hopper (H100) on current driver stacks — sourced from
  `pytorch.org/get-started/previous-versions` release notes surfaced via
  web search; **not independently re-verified against the raw PyTorch
  release notes file**, flagged as the one pin in this block with
  slightly weaker sourcing than the others (still reasonably confident;
  cu126 is a safe fallback if cu128 wheels are unavailable for a given
  RunPod/Modal base image).

**Unsloth — recommended as an optional accelerant, not a base-stack
dependency.** Unsloth (latest `2026.7.2`) wraps TRL/PEFT/vLLM rather than
replacing them, and already patches around one specific TRL/vLLM
compatibility wrinkle (stubbing `vllm.sampling_params.GuidedDecodingParams`
when absent, so TRL's unconditional import doesn't crash on newer vLLM
where that class was renamed/removed). It claims meaningful speed/VRAM
wins for GRPO+LoRA. However, I could not independently verify Unsloth
`2026.7.2`'s exact compatibility band against `trl==1.8.0` +
`vllm==0.23.0` + `transformers==5.13.1` from a primary source (Unsloth's
own compatibility notes are spread across changelogs I could not fully
fetch). **Concrete plan edit:** get the base stack above running and
green on the smoke set first; trial Unsloth in a separate branch/worktree
afterward, pinning whatever version Unsloth's own release notes state as
compatible with the already-pinned `trl`/`vllm` at trial time, and only
promote it into the main stack if it doesn't force a downgrade of the
`vllm==0.23.0` pin (which is itself already the ceiling TRL supports).

---

## Summary of concrete plan edits (§2/§4 of the execution plan)

1. Add explicit `vllm>=0.16.0,<=0.23.0` ceiling to the stack description
   (currently unstated); state GRPO rollouts run in **colocate mode**.
2. Replace `guided_grammar=` with the actual mechanism: pin vLLM's own
   deprecation (`guided_grammar` removed in v0.12.0, replaced by
   `structured_outputs`/`StructuredOutputsParams`), and specify that
   inside TRL's GRPOTrainer this must go through
   `GRPOConfig(generation_kwargs={"structured_outputs": {"grammar":
   ...}})` — undocumented but present in TRL `main` on both rollout
   paths — not the dedicated `vllm_structured_outputs_regex` field
   (regex-only). Add a W2 acceptance check that exercises this inside an
   actual `GRPOTrainer.train()` step, not just standalone vLLM.
3. Author the Scribble grammar in GBNF-style EBNF (xgrammar's native
   dialect), not Lark; vLLM's Lark auto-detection has an open,
   confirmed bug (vLLM #11118).
4. Replace the vague "-14B upgrade path" with a named ladder:
   Qwen2.5-Coder-14B-Instruct → Qwen3.6-27B-dense (Apache-2.0,
   ~77% SWE-bench Verified) if 14B also misses H3. Note
   Qwen3-Coder-30B-A3B (MoE) as a considered-and-rejected alternative.
5. Name RunPod Secure Cloud as primary GPU provider (cheapest reliable
   on-demand A100-80GB today, ~$1.2–1.4/hr) and Modal as fallback
   (~$2.50/hr A100, better fit for the plan's CI-style phase-gate
   scripting, startup credits available); drop Lambda Labs (optimized
   for multi-GPU, not this job shape).
6. Add the pin block in §5 above to whatever lockfile/`pyproject` the
   plan commits (§2 already says "image pinned by a pyproject/lockfile
   committed to the repo" — this report supplies the actual pins).
