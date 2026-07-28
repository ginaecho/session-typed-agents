# GPU Training Runbook — intent→protocol translator (T) and repairer (R)

Practitioner runbook for actually executing the training phases specified in
`docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md` (the "plan"; binding for
hyperparameters, reward design, and gates). This document adds nothing to
the plan's design — it is the sequence of commands, click-paths, and
config skeletons needed to run it, for whichever GPU account the owner
picks. Every provider path is written to be executable the day one is
chosen; no step says "configure the environment" without naming the exact
command. Training terms used throughout (SFT, GRPO, LoRA, gold) are defined
once at the top of the plan document above — this runbook does not repeat
those definitions.

**No GPU account has been chosen yet.** §2 covers all three concrete paths
(Modal, RunPod, Azure ML) side by side so this doc does not need to be
rewritten when the choice is made — just skip to the relevant subsection.

Status references: W1 (eval harness) DONE, W2 (grammar/GCD) DONE, W3 (data
builders) DONE at sample scale (full-size build not yet run — that is the
first thing this runbook has you do), W6 (judge panel) DONE (real API smoke
not yet run — no `ANTHROPIC_API_KEY` in the scouting/build sandboxes). W9
(SFT), W10 (GRPO), W12 (persistent validator service), W13 (GRPO plumbing
smoke), W14 (artifact persistence) had not landed reports as of this
writing (2026-07-11) — where this runbook describes their expected output
it is inferring from the plan's task-card done-criteria (§9), not from a
worker report; **if `docs/reference/reports/seam/W9_sft_report.md` /
`W10_grpo_report.md` / `W12_validator_service.md` / `W13_plumbing_smoke.md`
/ `W14_artifact_manifest.md` exist by the time you read this, they
supersede the corresponding section below** — read them first and treat
this runbook as the scaffold they fill in, not the other way around.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Prerequisites checklist](#1-prerequisites-checklist)
  - [1.1 Already in the repo (nothing to build)](#11-already-in-the-repo-nothing-to-build)
  - [1.2 What the GPU run actually consumes](#12-what-the-gpu-run-actually-consumes)
  - [1.3 Full-size data build — run BEFORE renting GPU](#13-full-size-data-build--run-before-renting-gpu)
- [2. Provider setup — three paths](#2-provider-setup--three-paths)
  - [2(a) Modal](#2a-modal)
  - [2(b) RunPod (Secure Cloud, A100-80GB)](#2b-runpod-secure-cloud-a100-80gb)
  - [2(c) Azure ML (NC A100 v4, spot)](#2c-azure-ml-nc-a100-v4-spot)
- [3. Environment — pin block and model ladder](#3-environment--pin-block-and-model-ladder)
- [4. W13 plumbing smoke — gates everything downstream](#4-w13-plumbing-smoke--gates-everything-downstream)
- [5. SFT (W9 / T1)](#5-sft-w9--t1)
- [6. GRPO (W10 / T2)](#6-grpo-w10--t2)
- [7. Artifact persistence (W14) — surviving an ephemeral sandbox](#7-artifact-persistence-w14--surviving-an-ephemeral-sandbox)
- [8. Reporting results back](#8-reporting-results-back)
<!-- MENU:END -->

## 1. Prerequisites checklist

### 1.1 Already in the repo (nothing to build)

| component | path | verified state |
|---|---|---|
| Real Scribble validator | `stjp_core/compiler/validator.py::ScribbleValidator` | 30/30 corpus pass, corrupt rejected (2026-07-11) |
| Toolchain installer | `tools/setup_scribble_cloud.sh` | idempotent, connects Maven build + nuscr binary per worktree |
| E5 bisimulation checker | `experiments/scripts/efsm_equiv.py::protocols_equivalent` | wrapped by `experiments/seam_bench/eval/validity.py::bisim_equivalent` |
| Lark grammar + GBNF mirror (GCD) | `stjp_core/compiler/scribble_grammar.lark`, `stjp_core/compiler/gcd_adapter.py` | 100% corpus round-trip, 1000/1000 sampled strings parse (W2) |
| Eval harness (metric block, splits, report gen) | `experiments/seam_bench/eval/` (`schema.py`, `metrics.py`, `validity.py`, `report_gen.py`, `smoke.py`) | 86 tests pass; smoke reproduces on 30-corpus set |
| Data builders (D1–D4) | `experiments/seam_bench/data/` (`d1_expand.py`, `d2_backtranslate.py`, `d3_repair.py`, `splitter.py`, `leakage_check.py`, `signature.py`) | 22 tests pass; sample-scale runs green; full-size runs NOT yet executed |
| Judge panel (5-layer isolation) | `experiments/seam_bench/judge/` (`payloads.py`, `seats.py`, `classes.py`, `aggregate.py`, `canaries.py`, `cache.py`, `run_panel.py`) | 62 tests pass; real-API smoke not yet run (no key in build sandbox) |
| D5 miner (test-real set) | `experiments/seam_bench/data/` D5 module (see `W8_miner.md`) | — |

### 1.2 What the GPU run actually consumes

The GPU job needs, as **inputs already sitting on disk before you rent
anything**:

1. Full-size `train`/`dev`/`test-syn` JSONL splits from D1–D4 (§1.3 below).
2. The GBNF grammar text (`gcd_adapter.to_ebnf_for_xgrammar()` output,
   frozen to a file — see §4).
3. The base model weights (pulled from HF Hub — the Hugging Face model
   hosting service — at container-start time, not
   pre-staged — see §3).
4. A pinned lockfile for the training image (§3) — **does not exist in the
   repo yet**; the first environment-setup step under whichever provider
   you pick is to freeze one (`pip freeze > requirements-gpu.lock` after
   installing the exact pin block below, then commit it — the plan's §2
   says "image pinned by a pyproject/lockfile committed to the repo," and
   that commit has not happened as of this writing).

### 1.3 Full-size data build — run BEFORE renting GPU

This is CPU/JVM-bound (each validation is a `java` subprocess spawn,
~0.5–1s), **not** GPU-bound. Running it on a rented GPU box burns GPU-hour
money on idle GPU while the CPU does the work. Run it on a plain compute
box (a laptop, a cheap CPU VM, or the free tier of whatever cloud you'll
later use for GPU — just don't attach a GPU to this step) and copy the
output JSONL into the GPU environment afterward (or straight into the
provider's persistent volume — see §7).

Exact commands (from `docs/reference/reports/seam/W3_data_builders.md`,
reproduced here verbatim so this doc is self-contained):

```bash
bash tools/setup_scribble_cloud.sh                       # once per checkout, ~5-10 min (Maven build)
D=experiments/seam_bench/data

# signature agreement re-check (cheap, run once)
python $D/signature.py --verify --pairs 200 --seed 0

# D1 — expand to >=5000 unique families. Measured throughput: ~0.60
# candidates/s / ~0.50 uniques/s on 4 cores -> ~3-4h wall-clock for 5k
# at --max-candidates ~20000. Checkpoints every 30s; safe to background
# and resume.
python $D/d1_expand.py --target 5000 --max-candidates 20000 --seed 1 \
    --workers 4 -o out/d1.jsonl

# D3 — repair tuples. Measured yield 0.27 repairs/attempt (~1.35/s) ->
# ~4h wall-clock for 20k at --max-mutations ~74000.
python $D/d3_repair.py --target 20000 --max-mutations 74000 --seed 1 \
    --workers 4 --gold-jsonl out/d1.jsonl -o out/d3.jsonl \
    --calibration-out out/cal.jsonl

# D2 — back-translation. Needs ANTHROPIC_API_KEY for the live client
# (omit --mock); budget cap via --budget-usd (default $5 per W3).
python $D/d2_backtranslate.py --gold-jsonl out/d1.jsonl -o out/d2.jsonl

# D4 — splits + leakage gate (must print VERDICT: GREEN before anything
# downstream touches this data)
python $D/splitter.py --in out/d1.jsonl out/d2.jsonl out/d3.jsonl \
    --out-dir out/splits --seed 1
python $D/leakage_check.py --split-dir out/splits \
    --files d1.jsonl d2.jsonl d3.jsonl
```

Total wall-clock for D1+D3 alone: **~7-8 hours** on a 4-core box (scale
cores up to shrink this — the workload is embarrassingly parallel and
JVM-bound, not CPU-architecture-sensitive). Run D1 and D3 in parallel
processes if core count allows (`--workers` split across two invocations)
since they're independent until the D4 split step. D2 depends on D1's
output and needs an API key; budget ≈ $150–400 per the plan's §2 cost
envelope for the full D2 back-translation pass (2013 pairs were produced
mocked at zero cost in the sample run — the paid run is roughly proportional
to family count times ~3 registers times per-call token cost).

Known limitation to plan around, not silently pad: D1's recursion axis
saturates at ~9 families with the current operators (the `retry` shape is
the only recursion-bearing generator). If the diversity floor in plan §3
(≥8 topology classes) is not met at 5k, the honest move is the saturation
curve + new-operator proposal the plan calls for — do not keep re-running
the same command expecting more recursive families to appear.

**Do not proceed to §2 until `leakage_check.py` prints `VERDICT: GREEN`.**

---

## 2. Provider setup — three paths

Recommendation (per R2 training-stack scout + R5 pricing factsheet, both
`docs/reference/reports/seam/scouts/`): **Modal for SFT** (T1) — the
free/starter credit plausibly covers the whole SFT phase (~2–6 A100-hours,
plan §2's $10–30 estimate), and Modal's Python-native SDK fits the
program's "CI-style scripts, not narrative claims" philosophy (plan §1).
**RunPod or Azure ML for GRPO** (T2) — GRPO's 24–72 A100-hour envelope
($100–350) will exceed free credit on any provider, so cost-per-hour
dominates; RunPod Secure Cloud is the cheapest reliable on-demand
A100-80GB per both R2 and R5 (~$1.2–1.4/hr on-demand, R2; RunPod on-demand
$1.49–1.64/hr per R5's independently-pulled table). Azure ML is the
second GRPO option specifically if the owner already has Azure spend /
credits from elsewhere — the repo's `stjp_core/requirements-core.txt`
already carries a full Azure AI SDK stack (`azure-ai-projects`,
`azure-identity`, etc.) for the Foundry integration, so an Azure account
may already exist for this project. **Note the R2 vs R5 pricing tables
disagree on which provider is cheapest in their prose summaries (R2 says
RunPod primary; R5's own summary line says Lambda is "most cost-effective"
even though R5's own table shows RunPod's on-demand row below Lambda's) —
treat R5's raw table numbers as the source of truth over its prose
summary, and re-verify at the provider's pricing page before committing
spend regardless (prices move; see the URLs below).**

### 2(a) Modal

1. Create an account at <https://modal.com> (owner does this in a browser,
   not inside an agent sandbox — see the Azure note in 2(c) for why this
   matters generally).
2. Install and authenticate the CLI:
   ```bash
   pip install modal
   modal token new        # opens a browser flow, writes ~/.modal.toml
   ```
3. Verify the free/starter credit balance at
   <https://modal.com/settings/billing> before planning phase timing —
   the plan cites "~$30/mo credits" as directional; **verify the exact
   current figure at that URL**, it is exactly the kind of number that
   changes without the plan being updated.
4. App skeleton (`train/modal_app.py` — create this file; nothing like it
   exists in the repo yet):
   ```python
   import modal

   app = modal.App("seam-sft")

   image = (
       modal.Image.from_registry("nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.11")
       .pip_install_from_requirements("requirements-gpu.lock")  # §3 pin block, frozen
       .run_commands("bash tools/setup_scribble_cloud.sh")      # only if in-container validation is needed
   )

   volume = modal.Volume.from_name("seam-artifacts", create_if_missing=True)

   @app.function(
       image=image,
       gpu="A100-80GB",
       timeout=6 * 60 * 60,
       volumes={"/artifacts": volume},
       secrets=[modal.Secret.from_name("hf-token"), modal.Secret.from_name("anthropic-key")],
   )
   def sft_train(config_path: str):
       import subprocess
       subprocess.run(["python", "train/sft_train.py", "--config", config_path], check=True)
   ```
5. Register secrets once, from the owner's machine (HF token needed to pull
   `Qwen2.5-Coder-7B-Instruct`; Anthropic key only if D2/back-translation
   or judge-panel calls happen inside the same job):
   ```bash
   modal secret create hf-token HF_TOKEN=hf_xxx
   modal secret create anthropic-key ANTHROPIC_API_KEY=sk-ant-xxx
   ```
6. Dispatch: `modal run train/modal_app.py::sft_train --config configs/t1_sft.yaml`.
   `modal run` streams logs live; `modal app logs seam-sft` reattaches to a
   detached run.

### 2(b) RunPod (Secure Cloud, A100-80GB)

1. Create an account at <https://runpod.io>, add a payment method
   (owner's browser, not the sandbox).
2. Console click-path: **Pods → Deploy → Secure Cloud → GPU filter:
   A100 80GB → select a template** (start from "RunPod PyTorch 2.x" and
   layer the pin block on top, or build a custom Docker image from §3's
   pins and push it to Docker Hub / GHCR first, then **Deploy → Custom
   Container** and paste the image reference).
3. Confirm current on-demand rate at <https://www.runpod.io/pricing>
   before deploying — plan/R2/R5 all cite ~$1.2–1.6/hr as of 2026-07-11
   but per-second billing rates move.
4. Enable SSH: in the pod's detail page, **Connect → SSH over exposed TCP**
   (RunPod auto-generates a keypair, or upload your own under **Settings →
   SSH Public Keys** before deploying so it's injected at boot). Connect:
   ```bash
   ssh root@<pod-ip> -p <exposed-port> -i ~/.ssh/runpod_key
   ```
5. Inside the pod: clone the repo, `pip install -r requirements-gpu.lock`
   (§3), `bash tools/setup_scribble_cloud.sh` if the reward function or
   in-loop validation runs on the same box (it does for GRPO — see §6),
   copy the D1–D4 output JSONL in (`scp` from the CPU box that ran §1.3,
   or pull from wherever it was pushed per §7).
6. RunPod pods bill while running regardless of GPU utilization — **stop
   or terminate the pod** (`Pods → ⋮ → Stop` to keep the disk / `Terminate`
   to release it) the moment a phase-gate run finishes; Secure Cloud
   volumes persist across stop/start, so `Stop` (not `Terminate`) is
   correct between the SFT and GRPO phases if reusing the same pod.
7. Template alternative for repeat runs: **Templates → New Template**,
   save the custom container + env vars + volume mount once, then
   `runpodctl` or the console can relaunch identical pods without
   re-clicking through the wizard each time.

### 2(c) Azure ML (NC A100 v4, spot)

**`az login` happens on the OWNER's machine, never inside an agent
sandbox.** This is a hard rule, not a style preference: `az login` opens
an interactive browser OAuth flow tied to the owner's Microsoft account
credentials and produces a long-lived token cache under `~/.azure/` —
running it inside an ephemeral/agent-controlled environment would either
fail (no browser) or, worse, succeed and leave Azure credentials sitting
in a sandbox that outlives the session's trust boundary. Every step below
after `az login` can run from a script the owner triggers, but the login
itself is manual, on the owner's own machine.

1. Owner, on their own machine: `az login` (opens browser; note the repo
   already has Azure SDK dependencies in `stjp_core/requirements-core.txt`
   for the Foundry integration, so an existing tenant/subscription may
   already be available — check `az account list` first before creating a
   new subscription).
2. Create (or reuse) a resource group and ML workspace:
   ```bash
   az group create --name seam-training-rg --location eastus
   az ml workspace create --name seam-ws --resource-group seam-training-rg
   ```
3. Create the compute (spot NC A100 v4 — *spot* is discounted capacity the
   cloud may reclaim at any moment, so the job must checkpoint; confirm the exact SKU name and
   quota availability for the chosen region at
   <https://azure.microsoft.com/en-us/pricing/details/machine-learning/>
   and in the portal's **Quotas** blade before scripting this, quota for
   A100 SKUs is not granted by default on new subscriptions and may need
   an owner-filed quota-increase request first):
   ```bash
   az ml compute create --name seam-gpu-spot \
     --resource-group seam-training-rg --workspace-name seam-ws \
     --type AmlCompute --size Standard_NC24ads_A100_v4 \
     --min-instances 0 --max-instances 1 \
     --tier LowPriority
   ```
   (`--tier LowPriority` is Azure ML's spot-equivalent for AmlCompute;
   confirm the flag name against the `az ml compute create` version
   installed, it has changed across CLI extension versions.)
4. Register the training environment from the §3 pin block (Azure ML
   environments are a Docker image + conda/pip spec):
   ```bash
   az ml environment create --name seam-train-env --version 1 \
     --resource-group seam-training-rg --workspace-name seam-ws \
     --image mcr.microsoft.com/azureml/curated/acpt-pytorch-2.11-cuda12.8:latest \
     --conda-file environment/seam-conda.yml
   ```
   (verify the curated base image tag exists for the exact torch/CUDA
   combo at deploy time — `az ml environment list` from the curated
   registry, or fall back to a plain `nvidia/cuda` base + the pin block's
   `pip install`, same as the Modal/RunPod images.)
5. Submit the training job:
   ```bash
   az ml job create --file jobs/t2_grpo_job.yml \
     --resource-group seam-training-rg --workspace-name seam-ws
   ```
   with `jobs/t2_grpo_job.yml` (create this file) pointing at
   `compute: azureml:seam-gpu-spot`, `environment: azureml:seam-train-env@1`,
   and the training script + args.
6. Monitor via `az ml job stream --name <job-name> ...` or the Studio UI
   (**ml.azure.com → Jobs**). Spot preemption means the training script
   must checkpoint (TRL's `Trainer.save_state`/`resumable` checkpointing —
   already standard, just confirm `--resume_from_checkpoint` is connected in
   the launch script) since a spot NC A100 v4 node can be reclaimed
   mid-run.

---

## 3. Environment — pin block and model ladder

**Pin block (R2-verified mutually compatible on 2026-07-11 — do NOT float
any of these; the ceiling notes below are why).** This is the source of
truth for `requirements-gpu.lock`; note R5's fact-sheet independently
pulled newer "latest stable" numbers for several of these packages
(`vllm==0.24.0`, `torch==2.13.0`) — **those are NOT what this program
uses**. R2 checked actual cross-package dependency constraints (TRL's
`pyproject.toml`, vLLM's PyPI `requires_dist`) and found TRL hard-caps
vLLM at `<=0.23.0`; R5 only checked each package's own latest-release
number in isolation. Use R2's pins, not R5's "latest" column, for
anything that goes in the lockfile.

```
--extra-index-url https://download.pytorch.org/whl/cu128
torch==2.11.0
torchvision==0.26.0
torchaudio==2.11.0

vllm==0.23.0          # NOT 0.24.0 — TRL's is_vllm_available() hard-checks
                       # 0.16.0 <= version <= 0.23.0; 0.24.0 is vLLM's
                       # actual latest and WILL be picked by a bare
                       # `pip install vllm` — pin it explicitly.
xgrammar==0.2.3
transformers==5.13.1
peft==0.19.1
accelerate==1.14.0
trl==1.8.0
lark==1.2.2            # already pinned in stjp_core/requirements-core.txt
                        # and requirements-secure.txt
```

Freeze this into `requirements-gpu.lock` (`pip install <above> && pip
freeze > requirements-gpu.lock`, commit it) as the first concrete action
inside whichever provider's image build you're doing — this satisfies the
plan §2 requirement ("image pinned by a pyproject/lockfile committed to
the repo") that has not yet been executed in this repo.

Also pin, if your GRPO rollout serves via a dedicated vLLM process
(`vllm_mode="server"` rather than the default `colocate`):
`--structured-outputs-config.backend xgrammar` explicitly on the vLLM
server launch — do not rely on vLLM's `auto` backend selection (R2 §2).

**Base model ladder** (T and R share the base; LoRA adapters differ):

1. **`Qwen/Qwen2.5-Coder-7B-Instruct`** (Apache-2.0) — primary. Fits one
   A100-80GB with LoRA. Try first.
2. **`Qwen/Qwen2.5-Coder-14B-Instruct`** (Apache-2.0) — escalation if H3
   misses (plan §8).
3. **`Qwen3.6-27B` dense** (Apache-2.0, ~77% SWE-bench Verified per R2) —
   escalation if the 14B also misses. LoRA on 80GB is tight at this size;
   plan to either drop vLLM colocate KV-cache headroom or move to
   `vllm_mode="server"` with a second GPU.

**Do not use** `Qwen/Qwen2.5-Coder-3B-Instruct` in any released artifact —
it ships under the **Qwen Research license, not Apache-2.0** (R5,
confirmed against the HF/GitHub model card). It's fine for cheap
iteration/smoke testing only (e.g. a first pass at W13's plumbing smoke
before burning A100 time), never for T1/T2 checkpoints that get reported
or released.

Fallback family (only if Qwen shows tokenizer pathologies on Scribble
syntax at the T1 gate — decide there, not before, per plan §2):
`Llama-3.1-8B-Instruct`.

---

## 4. W13 plumbing smoke — gates everything downstream

**Run this before spending real GRPO compute.** It answers one question:
does grammar-constrained decoding actually reach vLLM's sampler inside a
live `GRPOTrainer.train()` step, through the undocumented pass-through R2
found in TRL's source. If this fails, GRPO cannot proceed with GCD at all
and the plan's fallback (parse-reject-retry, H1's demotion path) has to be
decided before committing GRPO GPU-hours.

Config skeleton (`train/w13_smoke.py` — create this if
`W13_plumbing_smoke.md` doesn't already exist with one):

```python
from trl import GRPOConfig, GRPOTrainer
from stjp_core.compiler.gcd_adapter import to_ebnf_for_xgrammar

GRAMMAR_TEXT = to_ebnf_for_xgrammar()   # frozen GBNF text, W2's output

config = GRPOConfig(
    output_dir="/tmp/w13_smoke",
    per_device_train_batch_size=2,
    num_generations=4,               # small group size, smoke only
    max_steps=1,                     # ONE step — this is a plumbing check,
                                      # not a training run
    use_vllm=True,
    vllm_mode="colocate",            # default; single A100, no 2nd GPU
    generation_kwargs={
        "structured_outputs": {"grammar": GRAMMAR_TEXT},
    },
    logging_steps=1,
)

trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-Coder-7B-Instruct",   # or the 3B Research-license
                                                # twin for an even cheaper
                                                # smoke pass, per §3's
                                                # iteration-only carve-out
    reward_funcs=[lambda prompts, completions, **kw: [0.0] * len(completions)],  # stub reward, plumbing only
    args=config,
    train_dataset=smoke_dataset,   # a handful of prompts, e.g. 8-16 rows
                                    # from the dev split
)

trainer.train()
```

**What "pass" looks like**, concretely:

1. `trainer.train()` completes the one step without raising — specifically
   without the wiring falling silently back to *unconstrained* generation
   (the plan explicitly flags this path as "undocumented and untested by
   TRL's own test suite," so a silent no-op is the realistic failure mode,
   not a crash).
2. Positive proof, not absence-of-error: sample a handful of the rollout
   completions logged during the step and confirm every one parses under
   `stjp_core/compiler/gcd_adapter.py`'s Lark loader (or, cheaper, that
   every completion is well-formed enough to reach the Scribble validator
   without an ANTLR/parse-level rejection — see W1's
   `semantic-validity@1` heuristic for exactly this distinction). If
   completions contain free text outside the grammar (unconstrained
   markdown, code fences, prose), the pass-through did not reach the
   sampler — that is the failure this smoke test exists to catch.
3. Also run the **reason-then-clamp** variant (plan §2, W13's second
   deliverable): free reasoning prefix unconstrained, grammar clamps only
   the emitted protocol body. Confirm both variants produce parseable
   protocol bodies before deciding which one T2 uses — the choice is
   whatever recovers the H1 format-tax gap (plan §8) at the T1/T2 dev
   comparison, not a default.

If `W13_plumbing_smoke.md` already exists with a different config or a
different "pass" definition, that report is authoritative — this section
is what to do if it doesn't exist yet or needs re-running after a TRL/vLLM
version bump.

---

## 5. SFT (W9 / T1)

**Dataset files** (from §1.3's D1–D4 output, after the full-size build and
green leakage check):

- T's training data: `out/splits/train/d2_backtranslate.jsonl` filtered to
  D2-**accepted** pairs only (round-trip probe passed; `hard/`-quarantined
  pairs are excluded from SFT per plan §3).
- R's training data: `out/splits/train/d3_repair.jsonl` — every record is
  `(intent, mutant, counterexample, gold)`; the counterexample is the
  validator's verbatim error string (already banner-stripped per W1 §6.7).
- Dev: `out/splits/dev/{d2_backtranslate,d3_repair}.jsonl` for checkpoint
  selection.
- Record schema: `experiments/seam_bench/eval/schema.py::DatasetRecord` /
  `RepairRecord` (unknown-field writes fail loud — use this module's
  writer, don't hand-roll JSONL).

**Hyperparameters** (plan §2, starting points, tune on dev only):

- LoRA: `r=32, alpha=64, dropout=0.05`, target modules = attention + MLP.
- Learning rate: `1e-4`, cosine schedule.
- Effective batch size: 64.
- Epochs: 2–3.
- Max sequence length: 4096 (covers corpus max + intent).

**Two separate `SFTTrainer` runs** — T and R do not share a trainer (TRL's
multi-adapter support doesn't do joint training as a first-class path per
R2 §1; the plan already structures this as two runs, no change needed).

**Checkpoint selection**: dev **validity@1** for T, dev **fix-rate@1** for
R — both computed via `experiments/seam_bench/eval/metrics.py` against
checkpoints saved every N steps; pick the checkpoint that maximizes the
metric on dev, never on test-syn/test-real (plan §7 gate discipline — any
read of a restricted split must go through
`experiments/seam_bench/eval/test_access_log.py::guarded_read_jsonl` and
gets logged).

**Expected cost**: 2–6 A100-hours, ~$10–30 (plan §2). At RunPod's ~$1.2–
1.4/hr this is 2–6 hours of wall clock money; at Modal's free-credit tier
this plausibly costs $0 against the ~$30/mo starter credit (verify the
current figure at <https://modal.com/settings/billing> before assuming
zero out-of-pocket).

**Eval command that produces the metric block** (§7's standing metric
table, run against the selected checkpoint over `dev` first, then
`test-syn` only at the phase gate):

```bash
python -m experiments.seam_bench.eval.report_gen \
    docs/results/T1_sft_report_metrics.md \
    out/t1_sft_dev_runs.jsonl \
    --resamples 10000
```

This produces the validity@1/@k, semantic-validity@1, bisim@1/@k,
repair-rounds, tokens-to-accepted, $-to-accepted table with 95% CIs — the
same table format every system in plan §7's systems matrix reports. Feed
its `RunRecord` JSONL from a generation pass over dev/test-syn prompts
through `experiments/seam_bench/eval/validity.py`'s `validate_many()` /
`bisim_many()` adapters (real toolchain required — `bash
tools/setup_scribble_cloud.sh` must have run in this environment too, not
just the CPU box that built the data).

**Gate**: H3 (plan §8) — S4 (SFT-7B+GCD) validity@1 ≥ S0-Sonnet validity@1
− 10 pts at ≤ 1/20th the $-to-accepted; bisim@1 ≥ S1-Sonnet − 5 pts. Miss
→ try the 14B once (§3's ladder); miss again → the program stops at
T0+panel results as a still-publishable outcome (plan explicitly
preregisters this exit).

---

## 6. GRPO (W10 / T2)

**Precondition**: §4's W13 smoke must pass (constrained rollouts confirmed
working inside a live `train()` step) and H3 must have been evaluated
(§5) before starting — T2 initializes from the T1 checkpoint.

**Reward function wiring** (plan §2 v2, redesigned after the B2 red-team
finding that the v1 reward's within-group variance collapses post-SFT):

```python
def reward_fn(prompts, completions, completion_ids, **kwargs) -> list[float]:
    rewards = []
    for completion in completions:
        # parse is guaranteed by GCD -> not separately rewarded
        valid, msg = validate_many([completion])[0]          # +1.0 validator pass
        equiv = graded_equivalence_proxy(completion, gold)     # +2.0 * equiv_score, equiv_score in [0,1]
                                                                 # cheap structural proxy: canonical-EFSM
                                                                 # feature overlap (roles matched,
                                                                 # transition-label multiset F1,
                                                                 # branch/rec skeleton match) — ms-scale,
                                                                 # NOT full bisimulation (bisim is eval-only,
                                                                 # 10-40x a single validation per W1 §5)
        brevity_penalty = one_sided_brevity(completion, gold_len)  # 0 if len <= 1.25*gold_len, penalty above
        guard_bonus = 0.5 if guard_coemitted_correctly(completion) else 0.0
        r = (1.0 if valid else 0.0) + 2.0 * equiv + brevity_penalty + guard_bonus
        rewards.append(r)
    return rewards
```

`graded_equivalence_proxy` and `one_sided_brevity` are W5's deliverable
(`reward fn: validator+bisim callable, subprocess-safe, <200ms cached`,
plan §9 row W5) — check for `experiments/seam_bench/reward/` before
writing this from scratch; if it doesn't exist yet, this is the shape it
needs to have to match the reward math above.

**Gradient-starvation guard** (hard requirement, not optional tuning):
if within-group reward std < 0.05 on >50% of groups for 200 consecutive
steps, **halt the run and escalate** — this is the plan's B2 red-team
finding manifesting live (shortest-valid mode collapse once the validator
term saturates). Connect this as a `TrainerCallback` that reads
`trainer_state`/logged group-reward variance every step and raises
`RuntimeError` (not a warning) at the threshold, so a background run
cannot silently keep spending GPU-hours on a collapsed policy.

**W12 persistent-validator-service prerequisite.** Do not point the reward
function at a fresh `java` subprocess per rollout — GRPO needs ~16k
validations/epoch (plan §9 W12 row) and process-per-call throughput will
not hold (`~0.5-1s` JVM spawn cost per W3/R2, multiplied by rollout
volume, dominates wall-clock over the actual RL step per R2 §1). W12's
deliverable is a long-lived JVM in batch mode reachable at ≥50
validations/sec; if `experiments/seam_bench/validator_service/` (or
similar — check `docs/reference/reports/seam/W12_validator_service.md`
for the actual path once it exists) is not yet landed, this is a hard
blocker for GRPO — the reward function will either be too slow to run a
GRPO epoch in reasonable wall-clock time, or (worse) will silently degrade
by caching stale/wrong verdicts under time pressure. Confirm the service
is live and throughput-tested (`≥50/s` sustained) before starting T2, not
partway through.

**Curriculum**: epoch 1 restricted to ≤4-role non-recursive families, then
anneal to unrestricted. Filter the GRPO prompt dataset by the D1 family
metadata (`role_count`, `has_recursion` — same fields the D4 splitter
stratifies on) for the epoch-1 subset.

**Divergence guard**: every 200 steps, dev validity may rise only if dev
*panel score on a fixed probe set* does not fall >2 pts (reward-hacking
signature = validity↑, faithfulness→flat/↓; auto-halts the run). If the
§6-calibration gate in the plan has not passed (H5, panel not yet
promoted from advisory), the guard's faithfulness leg is **not** silently
dropped — it switches to the deterministic substitute: J-probe pass-rate
on a fixed dev probe set (compiled once via
`experiments/seam_bench/judge/classes.py::compile_probes_from_intent`,
verdicts are pure EFSM checks, no panel API calls in the loop). Check
which mode applies before configuring this — it changes what number the
callback reads.

**Divergence at accepted checkpoint**: the plan requires the guard to
never have tripped at whatever checkpoint gets accepted, and repair-rounds
strictly down vs. S4, as part of H4 regardless of which H4 branch (headroom
vs. ceiling) applies.

**Cost envelope**: 24–72 A100-hours, ~$100–350 (plan §2). At RunPod's
~$1.2–1.4/hr this is real out-of-pocket spend (~$29–100 for the GPU-hours
themselves at the low end of the range, scaling with the high end); Azure
ML spot pricing for `Standard_NC24ads_A100_v4` should be checked at spend
time — spot rates fluctuate more than RunPod's on-demand rate and can be
preempted mid-run (checkpoint resumption must work, see §2(c) step 6).

**Gate**: H4 (plan §8, headroom-aware) — if S4 validity@1 < 85%: S6 ≥ S4 +
10 pts validity@1 on test-syn. If S4 validity@1 ≥ 85% (H3 success makes
+10 arithmetically impossible): primary metric switches to graded
equivalence@1 (+5 pts) with validity@1 non-decreasing. Miss → ship S4/S5
and report GRPO honestly as negative (an explicitly acceptable outcome per
the plan, not a failure to hide).

---

## 7. Artifact persistence (W14) — surviving an ephemeral sandbox

Rented GPU boxes (RunPod pods especially, but also Modal containers and
Azure spot nodes) are ephemeral by default — nothing on local disk survives
a terminate/preemption. Persist, at minimum, at the end of every phase
(T0 baseline JSONL, T1 SFT adapter, T2 GRPO adapter):

1. **LoRA adapters and checkpoints → HF Hub** (private repo unless the
   plan calls for a public release, which Seam-Bench itself does at W11
   packaging time, not the intermediate checkpoints):
   ```bash
   huggingface-cli login   # or HF_TOKEN env var, already a Modal/RunPod secret per §2
   python -c "
   from huggingface_hub import HfApi
   HfApi().create_repo('gina-tcchen/seam-t1-sft-lora', private=True, exist_ok=True)
   HfApi().upload_folder(folder_path='/artifacts/t1_sft/checkpoint-best',
                          repo_id='gina-tcchen/seam-t1-sft-lora')
   "
   ```
2. **Verdict caches** (judge panel `cache.py`'s disk-backed
   `(class, model, temp, prompt_hash, payload_hash)` store, and the eval
   harness's validator/bisim in-process caches if persisted to disk) →
   push to the same release storage as checkpoints, or a dedicated
   `seam-verdict-cache` HF dataset repo — these are expensive to
   regenerate (bisim calls alone are 10-40x a plain validation, W1 §5) and
   losing them on a preempted spot node wastes real money, not just time.
3. **Full-size data build outputs** (§1.3's `out/d1.jsonl`, `out/d3.jsonl`,
   `out/splits/`) — these are NOT committed to git (the repo's convention,
   per W3, is samples ≤200 records only). Push the full JSONL to the same
   HF Hub org as a dataset repo, or to whatever blob storage the chosen
   provider makes cheapest (Azure Blob if on Azure ML, since
   `azure-storage-blob` is already a repo dependency; RunPod/Modal have no
   native equivalent, so HF Hub datasets is the simplest common target).
4. **Manifest committed to git** — the piece that actually makes "a fresh
   container reconstructs any phase gate from git + manifest" (plan §9 W14
   done-criterion) true. Commit
   `docs/reference/reports/seam/artifacts/MANIFEST.json` (or wherever W14 lands it — check for the actual file
   before creating a second one) recording, per phase gate: HF repo id +
   commit SHA for every checkpoint/dataset/cache pushed, the exact command
   that produced it, and the git SHA of the code that ran it. A fresh
   sandbox should be able to `git checkout <sha>`, read the manifest, and
   `huggingface-cli download` everything named in it without asking anyone
   what happened.

Do this **at the end of every phase**, not just at the very end of the
program — a T1 checkpoint lost because nobody pushed it before the RunPod
pod was terminated means re-running an already-paid-for SFT job.

---

## 8. Reporting results back

Every phase-gate run produces a `RunRecord` JSONL (§5/§6's `report_gen.py`
output) with the full §7-of-the-plan metric block: validity@1/@k,
semantic-validity@1, bisim@1/@k, repair-rounds, tokens-to-accepted,
$-to-accepted, panel-score, probe pass-rate, probe compile-rate, transfer
gap. These numbers are the raw material for two downstream consumers:

1. **The paper** (`paper-writing/v9/` — being authored in parallel with
   this training work; the directory does not exist in this checkout as
   of 2026-07-11, so treat this as a forward reference, not a path to
   `cd` into today). Its results section is expected to reference a
   `seam_results.tex` (or similarly-named) file with macros for exactly
   the metric-block cells above, per system row (S0–S7, plan §7's systems
   matrix) and split (dev/test-syn/test-real). When that file exists,
   populate its macros directly from `report_gen.py`'s output tables — do
   not hand-transcribe numbers, the whole point of the CI-style report
   generator is that the paper's numbers and the phase-gate report's
   numbers are the same JSONL run through the same code.
2. **The go/no-go gates** (plan §8, H1–H6) — each phase gate's report
   should state explicitly which H-numbers it resolves:
   - **H1** (GCD format-tax): resolved by the GCD-on vs GCD-off dev
     comparison at T1 *and* T2 — semantic-validity@1 and graded
     equivalence deltas between arms.
   - **H2** (best-of-n, measurement not gate): resolved by T0's baselines,
     already fillable before any GPU spend.
   - **H3** (SFT): resolved by T1's validity@1 and bisim@1 vs S0-Sonnet
     and the $-to-accepted ratio — §5's gate.
   - **H4** (GRPO): resolved by T2's validity@1 or graded-equivalence@1
     delta vs S4, conditional on the headroom branch — §6's gate.
   - **H5** (panel): resolved by the §6 calibration numbers (AUC, Wilson
     lower bound, effective votes) — independent of GPU spend, run
     whenever `ANTHROPIC_API_KEY` is available for the judge panel's real
     smoke (currently blocked on that, per W6's report).
   - **H6** (transfer gap): resolved by comparing (trained gap − baseline
     gap) on `test-real` (D5's mined set) with a bootstrap CI, at whichever
     phase gate opens `test-real` — remember every opening is logged via
     `guarded_read_jsonl` (plan §7 cadence: dev freely, test-syn/test-real
     only at phase gates).

Every table in the phase-gate report should carry n per cell and a 95% CI
— never a bare mean (plan §7 house rule) — which `report_gen.py` already
enforces by construction, so the discipline is "use the generator," not
"remember the rule by hand."
