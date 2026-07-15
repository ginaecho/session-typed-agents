# Scout R5: Seam-Training Fact-Sheet
**Retrieved 2026-07-11**

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Anthropic Claude API Pricing (per Million Tokens)](#1-anthropic-claude-api-pricing-per-million-tokens)
- [2. Stable Package Versions (as of 2026-07-11)](#2-stable-package-versions-as-of-2026-07-11)
- [3. GPU Rental Pricing (per hour, as of 2026-07-11)](#3-gpu-rental-pricing-per-hour-as-of-2026-07-11)
  - [H100 Pricing](#h100-pricing)
  - [A100-80GB Pricing](#a100-80gb-pricing)
- [4. Qwen2.5-Coder-Instruct Model Family](#4-qwen25-coder-instruct-model-family)
- [5. arXiv Paper Verification](#5-arxiv-paper-verification)
- [Summary Notes](#summary-notes)
<!-- MENU:END -->

## 1. Anthropic Claude API Pricing (per Million Tokens)

| Model | Base Input | Base Output | 5m Cache Write | 1h Cache Write | Cache Hit (0.1x) | Batch Input (50% off) | Batch Output (50% off) | Source |
|-------|-----------|-----------|----------------|----------------|------------------|-----------------------|------------------------|--------|
| Claude Fable 5 | $10.00 | $50.00 | $12.50 | $20.00 | $1.00 | $5.00 | $25.00 | [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude Opus 4.8 | $5.00 | $25.00 | $6.25 | $10.00 | $0.50 | $2.50 | $12.50 | [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude Opus 4.7 | $5.00 | $25.00 | $6.25 | $10.00 | $0.50 | $2.50 | $12.50 | [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude Sonnet 5* | $2.00–3.00† | $10.00–15.00† | $2.50–3.75† | $4.00–6.00† | $0.20–0.30† | $1.00–1.50† | $5.00–7.50† | [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude Sonnet 4.6 | $3.00 | $15.00 | $3.75 | $6.00 | $0.30 | $1.50 | $7.50 | [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude Haiku 4.5 | $1.00 | $5.00 | $1.25 | $2.00 | $0.10 | $0.50 | $2.50 | [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) |

*Introductory pricing $2/$10 through 2026-08-31; standard $3/$15 from 2026-09-01
†Introductory through 2026-08-31; standard rates from 2026-09-01
Source: [https://platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing)

---

## 2. Stable Package Versions (as of 2026-07-11)

| Package | Version | Released | Stability | Source |
|---------|---------|----------|-----------|--------|
| transformers | 5.13.1 | 2026-07-11 | Production | [PyPI](https://pypi.org/project/transformers/) |
| trl | 1.8.0 | 2026-07-09 | Production | [PyPI](https://pypi.org/project/trl/) |
| peft | 0.19.1 | 2026-04-16 | Production | [PyPI](https://pypi.org/project/peft/) |
| vllm | 0.24.0 | 2026-06-30 | Production | [PyPI](https://pypi.org/project/vllm/) |
| torch (PyTorch) | 2.13.0 | 2026-07-08 | Production | [PyPI](https://pypi.org/project/torch/) |
| unsloth | 2026.7.2 | 2026-07-08 | Production | [PyPI](https://pypi.org/project/unsloth/) |
| xgrammar | 0.2.3 | 2026-06-27 | Production | [PyPI](https://pypi.org/project/xgrammar/) |
| lark | 1.3.1 | 2025-10-27 | Production | [PyPI](https://pypi.org/project/lark/) |

Sources: [transformers](https://pypi.org/project/transformers/), [trl](https://pypi.org/project/trl/), [peft](https://pypi.org/project/peft/), [vllm](https://pypi.org/project/vllm/), [torch](https://pypi.org/project/torch/), [unsloth](https://pypi.org/project/unsloth/), [xgrammar](https://pypi.org/project/xgrammar/), [lark](https://pypi.org/project/lark/)

---

## 3. GPU Rental Pricing (per hour, as of 2026-07-11)

### H100 Pricing

| Provider | Spot | On-Demand | Billing | Source |
|----------|------|-----------|---------|--------|
| RunPod | $1.99–2.39 | $2.69–3.29 | per-second | [RunPod Pricing](https://www.runpod.io/pricing) |
| Lambda Labs | UNVERIFIED | $3.29–4.29 | per-second | [Lambda Labs](https://lambda.ai/pricing) |
| Modal | UNVERIFIED | $3.95–4.29 | per-second | [Modal Pricing](https://modal.com/pricing) |

Sources: [RunPod](https://www.runpod.io/pricing), [Lambda Labs](https://lambda.ai/pricing), [Modal](https://modal.com/pricing)

### A100-80GB Pricing

| Provider | Spot | On-Demand | Billing | Source |
|----------|------|-----------|---------|--------|
| RunPod | $0.99–1.49 | $1.49–1.64 | per-second | [RunPod Pricing](https://www.runpod.io/pricing) |
| Lambda Labs | UNVERIFIED | $1.99–2.49 | per-second | [Lambda Labs](https://lambda.ai/pricing) |
| Modal | $2.50 | $2.50–2.49 | per-second | [Modal Pricing](https://modal.com/pricing) |

Sources: [RunPod](https://www.runpod.io/pricing), [Lambda Labs](https://lambda.ai/pricing), [Modal](https://modal.com/pricing)

**Note:** Modal bills per-second of active compute with region multipliers (1.25x–2.5x). RunPod and Lambda Labs billing also per-second. Spot pricing represents 50–80% savings vs. on-demand.

---

## 4. Qwen2.5-Coder-Instruct Model Family

| Parameter Count | HuggingFace Model ID | License | Available | Source |
|-----------------|----------------------|---------|-----------|--------|
| 0.5B | Qwen/Qwen2.5-Coder-0.5B-Instruct | Apache 2.0 | Yes | [HF Model Card](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct) |
| 1.5B | Qwen/Qwen2.5-Coder-1.5B-Instruct | Apache 2.0 | Yes | [HF Model Card](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct) |
| 3B | Qwen/Qwen2.5-Coder-3B-Instruct | Qwen Research | Yes | [HF Model Card](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct) |
| 7B | Qwen/Qwen2.5-Coder-7B-Instruct | Apache 2.0 | Yes | [HF Model Card](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) |
| 14B | Qwen/Qwen2.5-Coder-14B-Instruct | Apache 2.0 | Yes | [HF Model Card](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct) |
| 32B | Qwen/Qwen2.5-Coder-32B-Instruct | Apache 2.0 | Yes | [HF Model Card](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) |

**Context Window:** 128K tokens (all sizes)
**Training Data:** 5.5 trillion code-related tokens
**License Note:** 0.5B, 1.5B, 7B, 14B, 32B under Apache 2.0 (commercial use allowed); 3B under Qwen Research license.

Sources: [Qwen2.5-Coder Collection](https://huggingface.co/collections/Qwen/qwen25-coder), [Alibaba Blog](https://www.alibabacloud.com/blog/qwen2-5-coder-series-powerful-diverse-practical_601765)

---

## 5. arXiv Paper Verification

| arXiv ID | Title | Authors | Submitted | Status | Source |
|----------|-------|---------|-----------|--------|--------|
| 2604.17612 | Provable Coordination for LLM Agents via Message Sequence Charts | Benedikt Bollig, Matthias Függer, Thomas Nowak | 2026-04-19 (rev. 2026-04-29) | FOUND | [arXiv](https://arxiv.org/abs/2604.17612) |
| 2603.18096 | A Trace-Based Assurance Framework for Agentic AI Orchestration: Contracts, Testing, and Governance | Ciprian Paduraru, Petru-Liviu Bouruc, Alin Stefanescu | 2026-03-18 | FOUND | [arXiv](https://arxiv.org/abs/2603.18096) |
| 2603.16586 | Runtime Governance for AI Agents: Policies on Paths | Maurits Kaptein, Vassilis-Javed Khan, Andriy Podstavnychy | 2026-03-17 | FOUND | [arXiv](https://arxiv.org/abs/2603.16586) |

**Note on 2604.17612:** ZipperGen is the open-source Python implementation of this framework.

Sources: [arXiv 2604.17612](https://arxiv.org/abs/2604.17612), [arXiv 2603.18096](https://arxiv.org/abs/2603.18096), [arXiv 2603.16586](https://arxiv.org/abs/2603.16586)

---

## Summary Notes

- **Pricing:** All Claude model tiers confirmed; batch + caching stack for up to 95% savings on Haiku 4.5. Sonnet 5 introductory pricing ends 2026-08-31.
- **Package Versions:** All eight packages confirmed stable; transformers and torch updated within past 3 days.
- **GPU Pricing:** RunPod offers lowest H100 rates ($1.99/hr spot). A100-80GB most cost-effective on Lambda ($1.99/hr). Modal requires per-second/region calculations.
- **Qwen2.5-Coder:** Full 0.5B–32B family available on HF; 3B uses Research license; others Apache 2.0.
- **arXiv Papers:** All three papers verified as published; authors and titles confirmed. No discrepancies.

---

**Report compiled:** 2026-07-11 | **Data freshness:** <24h for all pricing and versions
