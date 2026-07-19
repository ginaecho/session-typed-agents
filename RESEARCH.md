# AI_verf — Research Notes & Bibliography

Durable record of the literature survey conducted on 2026-05-02 across three areas: multiparty session types, the AI agent harness landscape, and agent verification & formal methods. The three sub-reports below were produced by parallel research agents and are preserved verbatim (with light editorial unification).

These notes are the authoritative source the project's design decisions are drawn from. See `PROPOSAL.md` for the synthesis and `MPST_STATIC.md` for the technical core.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Part I — Multiparty Session Types for LLM Agent Verification](#part-i--multiparty-session-types-for-llm-agent-verification)
  - [1. MPST foundations](#1-mpst-foundations)
  - [2. MPST extensions relevant to agents](#2-mpst-extensions-relevant-to-agents)
  - [3. Bridging natural language → types](#3-bridging-natural-language--types)
  - [4. Verification of LLM/agent systems (2024–2026)](#4-verification-of-llmagent-systems-20242026)
  - [5. Tools and implementations](#5-tools-and-implementations)
- [Part II — The Agent Harness Landscape: Machine-Readable Surface Area for Verification](#part-ii--the-agent-harness-landscape-machine-readable-surface-area-for-verification)
  - [Executive framing](#executive-framing)
  - [1. Claude Code (Anthropic)](#1-claude-code-anthropic)
  - [2. OpenAI Agents SDK / Codex](#2-openai-agents-sdk--codex)
  - [3. LangGraph / LangChain](#3-langgraph--langchain)
  - [4. AutoGen (Microsoft)](#4-autogen-microsoft)
  - [5. Other harnesses](#5-other-harnesses)
  - [6. Emerging standards (2025–2026)](#6-emerging-standards-20252026)
  - [7. Eval / verification harnesses](#7-eval--verification-harnesses)
  - [8. Per-harness verifier surface](#8-per-harness-verifier-surface)
- [Part III — Verifying & Validating LLM Agent Behavior](#part-iii--verifying--validating-llm-agent-behavior)
  - [1. Verification paradigms applicable to LLM agents](#1-verification-paradigms-applicable-to-llm-agents)
  - [2. Specifications LLMs can be checked against](#2-specifications-llms-can-be-checked-against)
  - [3. Formal specification of agent goals](#3-formal-specification-of-agent-goals)
  - [4. Practical verification tooling](#4-practical-verification-tooling)
  - [5. Recent agent-verification papers (2024–2026)](#5-recent-agent-verification-papers-20242026)
  - [6. The hard problem: markdown as a typing system](#6-the-hard-problem-markdown-as-a-typing-system)
  - [7. Why MPST is the right core](#7-why-mpst-is-the-right-core)
- [Consolidated Bibliography](#consolidated-bibliography)
  - [Multiparty session types — foundational](#multiparty-session-types--foundational)
  - [MPST extensions](#mpst-extensions)
  - [Choreographies](#choreographies)
  - [Tools](#tools)
  - [NL → spec / agentic verification (2024–2026)](#nl--spec--agentic-verification-20242026)
  - [Harness / standards / runtime](#harness--standards--runtime)
  - [Calibration / behavioural](#calibration--behavioural)
  - [Metamorphic / property-based](#metamorphic--property-based)
  - [Goal specification](#goal-specification)
  - [Guardrails / contracts](#guardrails--contracts)
<!-- MENU:END -->

# Part I — Multiparty Session Types for LLM Agent Verification

## 1. MPST foundations

The canonical reference is Honda, Yoshida, and Carbone, *Multiparty Asynchronous Session Types* (POPL 2008; expanded in JACM 2016). They generalize binary session types to N participants by introducing a **global type** describing the protocol from a god's-eye view (e.g., `A→B: Int. B→C: Bool. end`), which is **projected** onto **local types** for each role; each endpoint is type-checked against its local type. The well-formedness of the global type plus per-endpoint conformance yields three central guarantees: **communication safety** (every send is matched by a compatible receive), **session fidelity / protocol conformance** (the trace of messages refines the global type), and **deadlock-freedom / progress** (a well-typed configuration never gets stuck in a single session).

- Honda, Yoshida, Carbone, 2008/2016 — original MPST: global types, projection, async π-calculus typing. *Relevance:* gives a battle-tested grammar for expressing what an agent and its tools/sub-agents are *supposed* to say to each other, with a decidable conformance check.
- Scalas & Yoshida, "Less is More: Multiparty Session Types Revisited," POPL 2019 — modernizes the foundations: drops global types as primitive and instead checks behavioral properties on the projected local types directly, repairing soundness gaps in the 2008 theory and broadening the class of typable protocols. *Relevance:* the "Less is More" formulation is the version any new tool should target — it is cleaner, what `mpstk` implements, and more permissive about real-world idioms (mixed choice, asymmetric branching).
- Coppo, Dezani, Padovani, Yoshida, "A Gentle Introduction to MPST," 2015 — pedagogical entry point.

**Limitations relevant to the project's goal:** classical MPST assumes (a) a *fixed* set of named participants, (b) a *closed* world (no run-time arrivals), (c) reliable FIFO async channels, and (d) typed message payloads. None of these hold cleanly for an LLM that can emit arbitrary text, spawn sub-agents, or fail nondeterministically. Hence the extensions below matter more than the core theory.

## 2. MPST extensions relevant to agents

- **Parameterised MPST** — Yoshida, Deniélou, Bejleri, Hu (2010). Dependent indices so the protocol can be parameterised over `n` workers. *Relevance:* agents-as-tools fan-out (`n` parallel reviewers) maps directly onto this.
- **Dynamic Multirole Session Types** — Deniélou & Yoshida (ESOP 2011, ICALP 2012). Roles join/leave at runtime via a "universal polling" operator. *Relevance:* matches LLM orchestrators where sub-agents are spawned on demand.
- **Dynamically Updatable MPST** — Anderson, Rathke (Oxford). Supports protocol upgrades during a live session. *Relevance:* when an agent's `SKILL.md` changes between turns, the verifier needs to express graceful migration.
- **Refinement / Asserted MPST** — Bocchi, Honda, Tuosto, Yoshida, "A Theory of Design-by-Contract for Distributed Multiparty Interactions" (CONCUR 2010); ECOOP 2024 "Refinements for Multiparty Message-Passing Protocols." Decorates message types with logical predicates (`x: Int{x > 0}`) that monitors check at runtime. *Relevance:* the mechanism for "tool call argument must match this schema/predicate" — the closest formal analogue to a markdown agent spec's natural-language preconditions.
- **Probabilistic Session Types** — Inverso, Melgratti, Padovani, Trubiani et al. (2019); Das, Pfenning (2020); Fu, "Probabilistic Refinement Session Types" (POPL 2025); "Compositional Interface Refinement Through Subtyping in Probabilistic Session Types" (2025). *Relevance:* LLMs *are* probabilistic — typing things like "with probability ≥ 0.95 the agent will call `verify` before `commit`" is directly applicable.
- **Gradual Session Types** — Igarashi, Thiemann, Tsuda, Vasconcelos, Wadler (ICFP 2017 / JFP 2019). Casts mediate between statically-typed and `dyn`-typed channel ends, preserving progress. *Relevance:* **the most important single result** for this project — the LLM endpoint is fundamentally untyped, the surrounding infrastructure (tool calls, sub-agents) is typed, and gradual session types tell you precisely how to build the casts/monitors at the boundary.
- **Monitored MPST / Run-time Enforcement** — Bocchi, Chen, Demangeon, Honda, Yoshida (FORTE 2013, TCS 2017). Dynamic monitors at network boundaries enforce projected local types on otherwise-untrusted endpoints; proves local monitor compliance implies global protocol compliance. *Relevance:* the keystone paper for the runtime story — wrap each endpoint in a generated monitor that rejects off-protocol messages.
- **Global Type Synthesis from Local Types** — Lange & Tuosto, "Synthesising Choreographies from Local Session Types" (CONCUR 2012); Deniélou & Yoshida, "Multiparty Compatibility in Communicating Automata: Characterisation and Synthesis of Global Session Types" (ICALP 2013). Given only per-participant local types / communicating automata, decide compatibility and synthesize the global type they implement. *Relevance:* **the theory behind bottom-up STJP** — teams already have per-agent skill markdowns; compaction turns each into a local type, then synthesis + Scribble validation proves (or refutes) that the existing skills interact safely (`stjp_core/generation/skill_compactor.py`, `stjp_core/compiler/global_synthesizer.py`, `docs/reference/SKILL_COMPACTION.md`).
- **Choreographic Programming** — Montesi, *Introduction to Choreographies* (Cambridge UP, 2023); Carbone, Montesi (POPL 2013); Cruz-Filipe, Montesi (TCS 2020); Giallorenzo, Montesi et al., "Choral" (TOPLAS 2024); Kashiwa, Shen, Lu, Kuper, "HasChor" (ICFP 2023). Choreographies *generate* endpoint code from a central script via Endpoint Projection (EPP). *Relevance:* `agents.md` can be thought of as a choreography script; per-agent monitors and per-tool stubs can be generated from it.

## 3. Bridging natural language → types

The thinnest area in the literature.

- Tao Xie et al., "Inferring Resource Specifications from NL API Documentation" (Doc2Spec, ASE 2009) — early NL→spec extraction. Pre-LLM and brittle.
- Sharma et al., "PROSPER: Extracting Protocol Specifications Using LLMs" (HotNets 2023); "AutoSpec / Synthesizing Precise Protocol Specs from Natural Language" (arXiv 2511.17977, 2025). Two-stage LLM pipelines turning RFCs into testable formal protocol specs. *Relevance:* directly transferable methodology — replace "RFCs" with "agents.md."
- Cosler et al., "NL2Spec" (CAV 2023) — NL→LTL; SpecGen — NL→program contracts.
- "Towards an Agentic LLM-based Approach to Requirement Formalization" (arXiv 2604.18228, 2025); VERIFYAI project.
- **No published work yet on LLM-assisted session-type synthesis** — open niche this project plausibly owns.

## 4. Verification of LLM/agent systems (2024–2026)

- Wang, Poskitt, Sun, "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents" (arXiv 2503.18666, ICSE 2026). DSL for trigger/predicate/action rules around tool calls; >90% prevention of unsafe executions; rule auto-generation by `o1`. **Closest existing tool to AI_verf** — but its DSL is rule-based, not protocol-based. MPST gives deadlock/progress guarantees AgentSpec lacks.
- "Agent-C: Enforcing Temporal Constraints for LLM Agents" (arXiv 2512.23738, 2025). DSL → first-order logic → SMT, achieving 100% conformance on its benchmark. Temporal-logic competitor to a session-types approach.
- "Runtime Governance for AI Agents: Policies on Paths" (arXiv 2603.16586). Argues governance should be path/sequence-based — exactly the MPST insight expressed in agent-safety vocabulary.
- "Policy-as-Prompt: Turning AI Governance Rules into Guardrails" (arXiv 2509.23994, 2025); "From Governance Norms to Enforceable Controls" (arXiv 2604.05229).
- "Formalizing the Safety, Security, and Functional Properties of Agentic AI" (arXiv 2510.14133, 2025) — 30 LTL/CTL properties for agents.
- Microsoft TypeAgent (open source, 2024–) — TypeChat-schema-typed agent dispatch. Type-routed agents but no protocol/temporal layer; complements rather than competes.
- OpenAI Model Spec (Dec 2025) and Anthropic Claude Constitution (2026 revision) — natural-language artifacts intended as behavioural contracts, neither has a verifier. Validates the premise that "specs as verifiable artifacts" is an industry-wide gap.
- VeriPlan (CHI 2025), "Bridging LLM Planning Agents and Formal Methods" (arXiv 2510.03469), Sherlock (arXiv 2511.00330) — adjacent verification of planning/workflow agents.

## 5. Tools and implementations

- **Scribble** (Imperial / MRG, Yoshida group). Industrial protocol description language; Java/Python/Go runtime monitors; deployed with Ocean Observatories Initiative. The reference design for "spec → projected local types → generated runtime monitors."
- **nuScr** (`github.com/nuscr/nuscr`) — actively maintained OCaml successor; parses Scribble syntax, projects, builds CFSMs, generates OCaml endpoints. Most mature open-source codebase to fork or embed.
- **mpstk** (Scalas, `github.com/alcestes/mpstk`) — Scala toolkit implementing "Less is More"; checks deadlock-freedom and liveness on projected types. The right implementation for the modern theoretical core.
- **StMungo + Mungo** (Glasgow, Gay/Voinea) — Scribble→Java typestate. Pattern transferable to TypeScript/Python.
- **Effpi** (Imperial; Scalas, Yoshida) — Scala embedded DSL, type-level session encoding. How far compile-time checking can go inside a host language.
- **STScript / RouST** — communication-safe TypeScript over WebSockets via routed MPST (Miu, Ferreira, Yoshida, Zhou; CC 2021). Existing TS implementation worth mining if the harness lands in the JS ecosystem.
- **Choral** and **HasChor** — choreography compilers (Java / Haskell). Alternative architectural pattern.
- **AgentSpec** — the LLM-agent runtime enforcer to beat.

---

# Part II — The Agent Harness Landscape: Machine-Readable Surface Area for Verification

## Executive framing

A verification tool that "drops into a repo and checks whether agents follow their declared specs" operates on a landscape that, as of mid-2026, has roughly three layers of formality:

1. **Hard schemas** with required keys (Claude Code skills/subagents, MCP, OpenAI Agents SDK Python classes, LangGraph TypedDicts, CrewAI YAML, Cursor `.mdc` frontmatter).
2. **Soft schemas** (AGENTS.md, CLAUDE.md, Aider CONVENTIONS.md, OpenHands microagents) — markdown with optional frontmatter; the *body* is free-form prose.
3. **Runtime traces** — increasingly standardising on **OpenTelemetry GenAI semantic conventions** (`gen_ai.*` spans), plus framework-native traces.

The core gap AI_verf targets — declared spec vs. observed behaviour — is exactly where almost nothing exists today: hard-schema declarations describe *capability surface* (what an agent *can* touch), but the *behavioural contract* lives in markdown prose. Verification today means LLM-as-judge.

## 1. Claude Code (Anthropic)

**Settings hierarchy** (precedence high → low): enterprise policy → `.claude/settings.local.json` → `.claude/settings.json` (project) → `~/.claude/settings.json` (user). All JSON, all parseable.

**`CLAUDE.md`**: free-form markdown context file at repo root or `~/.claude/CLAUDE.md`. No schema. Pure prose; the verifier must NLP-parse it or treat it as ground-truth narrative.

**Skills** (`SKILL.md` in `~/.claude/skills/<name>/` or `.claude/skills/<name>/`). Anthropic released the **Agent Skills Open Standard** on Dec 18, 2025 — now the most concretely machine-readable artifact in the ecosystem. YAML frontmatter keys:
- `name` (required), `description` (required)
- `allowed-tools` (list, e.g. `[Read, Grep, Glob]`) — enforced capability restriction
- `disable-model-invocation` (bool) — gates auto-invocation
- `version`, `license`, `compatibility`, `metadata` (optional)

**Subagents** (`.claude/agents/<name>.md` or `~/.claude/agents/<name>.md`). YAML frontmatter:
- `name`, `description` (required)
- `tools` (list, restricts which built-in tools the subagent can call)
- `model` (`sonnet` | `opus` | `haiku` | full ID like `claude-opus-4-7` | `inherit`)

**Slash commands** (`.claude/commands/<name>.md`): frontmatter supports `description`, `argument-hint`, `allowed-tools`. As of 2026, `/deploy` resolves identically whether defined as a command file or a skill at `.claude/skills/deploy/SKILL.md`.

**Hooks** in `settings.json` under `hooks.<event>`. Events: `PreToolUse`, `PostToolUse`, `PermissionRequest`, `SessionStart`, `SessionEnd`, `Stop`, `SubagentStop`, `UserPromptSubmit`, `Notification`, `PreCompact` (12 lifecycle events). Each entry has `matcher` (tool name, regex, `Write|Edit`, `*`) and `hooks` array of shell commands. PreToolUse hooks can return a JSON decision (`approve` / `block` / `ask`) — the only point in the harness where declared policy can hard-fail an agent action.

**MCP servers**: declared in settings under `mcpServers` with `command`, `args`, `env`. The **MCP spec (2025-11-25 release)** defines tools/resources/prompts as JSON-RPC primitives with JSON Schema input schemas — every MCP tool has a fully introspectable signature.

*Verifier latch points:* the skills/subagents frontmatter, `allowed-tools`/`tools` lists, and hook matchers are all parseable as JSON Schema. The `description` and prose body are not. Hook stdout/stderr is logged but there is no standard "did the agent honor `allowed-tools`" check — AI_verf would compute it from session transcripts vs. frontmatter.

## 2. OpenAI Agents SDK / Codex

`Agent`, `Runner`, `handoff()`, `function_tool` are Python classes. Schemas come from Pydantic introspection — every tool's input schema is a real JSON Schema. `Agent(name=..., handoffs=[...], tools=[...])` is statically inspectable via AST or imports. Tracing is enabled by default; traces capture LLM generations, tool calls, handoffs, guardrails, custom events as a structured event stream.

**Codex / AGENTS.md**: OpenAI's coding agent reads `AGENTS.md` at repo root (and nested) — pure markdown, no required structure.

**OpenAI Evals**: YAML registry at `evals/registry/evals/*.yaml` — each eval has a class, dataset reference, and `testing_criteria` (graders like `string_check`, `model_grade`).

## 3. LangGraph / LangChain

`StateGraph(State)` where `State` is a `TypedDict` or Pydantic model. Reducers declared via `Annotated[list, operator.add]`. Graph topology introspectable via `graph.get_graph()` (returns nodes and edges as data). LangSmith captures full run trees with parent/child relationships, tool I/O, token counts; trajectory evaluators score intermediate steps. No built-in invariant/contract checking — invariants must be encoded as runtime asserts inside nodes or as LangSmith evaluators run post-hoc.

## 4. AutoGen (Microsoft)

`AssistantAgent(name, model_client, description, system_message, tools)` — Python construction, no static config file. Group chat patterns: `RoundRobinGroupChat`, `SelectorGroupChat` (LLM picks next speaker; `candidate_func` filters), `Swarm`. Behaviour declaration is entirely in `system_message` strings + tool list. There is no separate spec file; the agent **is** the Python object.

## 5. Other harnesses

- **CrewAI**: `agents.yaml` and `tasks.yaml` — fully declarative. Agent keys: `role`, `goal`, `backstory`, `tools`, `llm`, `allow_delegation`, `verbose`. Tasks: `description`, `expected_output`, `agent`, `context`, `output_file`. Best YAML schema in the ecosystem for a multi-agent system.
- **Cursor Rules**: `.cursor/rules/<name>.mdc` (or as of v2.2, `.cursor/rules/<name>/RULE.md`). Frontmatter: `description`, `globs` (path patterns), `alwaysApply` (bool).
- **OpenHands**: `.openhands/microagents/<name>.md` with `trigger_type` (`always` | keyword | custom). Trigger keywords machine-readable; bodies are prose.
- **Cline**: adopted AGENTS.md (issue #5033). No dedicated schema.
- **Aider**: `--conventions-file` flag, defaults to `CONVENTIONS.md`. Pure prose.
- **Devin**: closed; "Knowledge" entries are prose with tag-based scoping.

## 6. Emerging standards (2025–2026)

- **AGENTS.md** is the de facto cross-tool prose convention, now stewarded by the **Agentic AI Foundation under the Linux Foundation**. Adopted by 20,000+ repos, supported by OpenAI Codex, Google Jules, Cursor, Aider, RooCode, Zed.
- **Agent Skills Open Standard** (Anthropic, Dec 2025) — closest thing to a hard schema for agent capabilities. Adopted by ~32 tools including Cursor, Codex, GitHub Copilot.
- **MCP** is the de facto interop layer. JSON-RPC + JSON-Schema published primitives. The Nov 2025 spec added Tasks (experimental); the 2026 roadmap focuses on auth, audit trails, gateways. MCP server manifests give a precise list of *every external capability* an agent has.
- **OpenTelemetry GenAI semantic conventions** (`gen_ai.*` spans, agent spans, events; experimental as of March 2026, but Datadog ships it natively in OTel 1.37). The most important emerging artifact for the runtime side: a standard span schema for tool calls, LLM invocations, agent handoffs.
- **"Agentic Constitution"** — being pushed in CIO/enterprise publications as machine-readable policy. Conceptual, not yet a concrete schema.
- **EU AI Act Article 50** (Aug 2026): mandates machine-readable marking for AI outputs — will force structured provenance metadata.

## 7. Eval / verification harnesses

- **Inspect AI (UK AISI)**: `Task` = dataset + solver + scorer. Built-in scorers (exact_match, includes, model_graded_qa). Sandboxed Docker execution. 200+ built-in evals + community `inspect_evals` repo. Closest thing to a "harness for harnesses."
- **OpenAI Evals**: YAML-registered, `string_check` and `model_grade` graders.
- **LangSmith**: trajectory capture; evaluators are Python/TS functions over runs.
- **Braintrust**: dataset-first, scorer functions wired into CI.
- **DeepEval**: pytest-style local-first; widest metric coverage.
- **Arize Phoenix**: OTel-native, self-hostable.

**Honest assessment**: across all of these, "did the agent do the right thing" is ~80% LLM-as-judge, ~15% string/regex/exact-match, and ~5% formal (type checks, tool-call schema validation, sandbox exit codes). No mainstream tool today verifies "the agent honored its declared `allowed-tools` list across the trajectory" or "the agent's behaviour matched the natural-language spec in CLAUDE.md."

## 8. Per-harness verifier surface

| Harness | Machine-readable artifact | Runtime trace | Spec→behaviour gap |
|---|---|---|---|
| Claude Code | `SKILL.md` frontmatter, agent `.md` frontmatter, `settings.json` hooks, MCP config | Session JSONL in `~/.claude/sessions/`, hook stdout | `description` body is prose; no harness check that subagent stayed within `tools` list |
| OpenAI Agents SDK | Python `Agent` ctor args, Pydantic tool schemas | Built-in tracing (LLM/tool/handoff events) | Handoff routing isn't declared up front — emergent from prompts |
| LangGraph | TypedDict state, graph topology object | LangSmith run tree | Node contracts only as runtime asserts |
| AutoGen | Python objects, no config files | Conversation log | No declared spec |
| CrewAI | `agents.yaml`, `tasks.yaml` | Crew kickoff logs | `expected_output` is prose |
| Cursor Rules | `.mdc` frontmatter | None published | Body is prose |
| OpenHands | microagent frontmatter | OpenHands event stream | Body is prose |
| AGENTS.md | None (markdown only) | None | Entire spec is prose |
| MCP | JSON-Schema tool definitions | JSON-RPC traffic | Schema covers I/O shape, not semantics |
| OTel GenAI | `gen_ai.*` span attributes | OTel traces | Standard for *what happened*, not *what should have* |

---

# Part III — Verifying & Validating LLM Agent Behavior

## 1. Verification paradigms applicable to LLM agents

**Runtime verification (RV) with temporal logics** is the most active formal frontier in 2025–2026. *Agent-C* (2025) compiles temporal/state-dependent properties to first-order logic and interleaves SMT solving with constrained token generation. *AgentVerify* (Preprints 2026) provides compositional LTL specifications for memory integrity, tool-call protocols, MCP/skill invocations, and human-in-the-loop boundaries. *LogicGuard / LTLCrit* (Singh et al. 2025) layers a symbolic LTL critic over an LLM actor in a two-timescale architecture. *AutoSafeLTL* (2025) uses fine-tuned NL2LTL translation. Springer's 2025 "Runtime Verification for LTL in Stochastic Systems" addresses LLM nondeterminism directly.

- *Verifies*: bounded safety/liveness ("never call tool X after sending PII", "eventually return"), per-trace temporal compliance.
- *Cannot*: open-ended semantic intent, multi-trace properties, unbounded quantifier alternation.
- *MPST combination*: LTL/MTL monitors are a natural per-endpoint complement to MPST's structural protocol guarantees — MPST defines who-talks-to-whom-when; LTL refines what each role's local message contents/timing must satisfy.

**Property-based / metamorphic testing for stochastic systems**. *LLMORPH* (Cho et al., ASE 2025) and *MTF* (ICAIAT 2025) report ~18% average failure rates and find 11% of failures missed by ground-truth oracles. The Cho et al. ICSME 2025 survey catalogs 191 metamorphic relations for NLP. A central 2025 finding: existing tools "treat each run as independent" and need *aggregated oracles* over repeated samples.

- *Verifies*: input-perturbation invariances, fairness, robustness.
- *Cannot*: absolute correctness.
- *MPST combination*: useful as the *content-level oracle* checking message payloads obey domain-specific MRs while MPST checks message-flow shape.

**Contract programming / Hoare logic**. *PropertyGPT* (Liu et al. 2025), *NeuroInv* (2025), *AutoVerus* (2025, >90% on 150 Verus tasks) bring LLM-driven invariant inference. The DbC-inspired neurosymbolic contract layer of Leoveanu-Condrei (2025, arXiv 2508.03665) is directly relevant: it attaches preconditions/postconditions to *individual LLM calls* using Pydantic-typed `LLMDataModel` subclasses. Tanzim's 2025 study "Contracts for Large Language Model APIs" tracks this thread.

- *Verifies*: local step correctness.
- *Cannot*: emergent multi-agent behaviour.
- *MPST combination*: contracts decorate the *send/receive actions* projected from a global type — each MPST local type's I/O carries pre/postconditions: a "session-typed Eiffel."

**Model checking (TLA+/SPIN)**. Multi-agent coordination has been verified in TLA+ since Paiva & Saotome (2019) and team-formation work (Authorea 2023). The 2025 "Formalizing the Safety, Security, and Functional Properties of Agent Communication" (arXiv 2510.14133) explicitly notes the *fragmentation* of MCP/A2A/ACP semantics and proposes a unified formal foundation.

- *Verifies*: finite-state protocol properties (deadlock, ordering, fairness).
- *Cannot*: infinite/data-rich state without abstraction.

**Hyperproperties / k-safety**. "Detecting Safety Violations Across Many Agent Traces" (arXiv 2604.11806) and CSL 2026's "Reasoning About Quality in Hyperproperties" frame safety as a property of *sets* of traces — needed for "did the agent's reasoning *entail* its action?" (a 2-safety relation between CoT and tool call).

- *Verifies*: non-interference, refinement, "different prompts shouldn't leak the system prompt."
- *MPST combination*: HyperLTL over MPST role projections lets you state "the data agent role never reveals to client what only the privileged role saw" — a session-typed information-flow property.

## 2. Specifications LLMs can be checked against

**LLM-as-judge** is the dominant ad-hoc pattern but suffers known biases: positional, verbosity, self-preference, agreeableness (TPR >96% / TNR <25%), and 64–68% domain expert agreement vs. inter-expert baselines (Masood 2026; Deepchecks 2025). Multilingual Fleiss-κ stays in 0.1–0.32. *Autorubric* (arXiv 2603.00077) is the leading attempt at unifying rubric-based eval. Calibration against a human-labeled golden set with 75–90% agreement is now considered table stakes.

**Constitutional AI / model specs**. Anthropic's *Claude Constitution* (2025) and the *Stress-Testing Model Specs* paper (alignment.anthropic.com 2025) generated 300k+ scenarios forcing principle conflicts and found 5–13× higher violation rates in high-disagreement cases — direct evidence that NL specs *as written today* are non-deterministic. This is precisely the problem AI_verf addresses.

**Inspect (UK AISI)**. Open-source primitives are `Dataset → Task → Solver → Scorer`. Scorers include `match`, `includes`, `pattern`, `model_graded_qa`, `model_graded_fact`, and tool-use scorers. It is *not* a formal verifier — assertions are sample-level Python predicates over `TaskState`. AISI's *Autonomous Systems Evaluation Standard* defines structured eval contracts but not formal proofs.

## 3. Formal specification of agent goals

PDDL/HTN/BDI remain classical substrates. *EmboTeam* (arXiv 2601.11063) and *Code-BT* (IJCAI 2025) show the 2025 pattern: LLM parses NL → PDDL problem → behaviour tree → reactive control. *LLM-as-BT-Planner* generates BTs in-context. Behaviour trees are attractive because natively verifiable via standard reachability analysis. LTL for goal expression ("eventually deliver", "never expose PII") is well-explored. Reward/preference modelling provides an *implicit* spec — useful as ground truth for judges but unfit as a typing system.

## 4. Practical verification tooling

| Tool | What it checks | What it cannot |
|---|---|---|
| **guardrails-ai** (Hub: 50+ validators) | Pydantic schema, PII, toxicity, regex, competitor mentions; output validators with retry | Multi-step semantic intent; cross-turn invariants; protocol shape |
| **NeMo Guardrails (Colang)** | Topical/flow restrictions; state-machine transitions; input/output rails | Formal proof of properties; richly typed payloads |
| **Pydantic AI / pydantic-ai-guardrails** | Structural validation, output retry with feedback | Behavioural or temporal semantics |
| **OpenAI/Anthropic evals, Inspect** | Sample-level scoring, model-graded QA, tool-use traces | k-safety, refinement, formal liveness |
| **Petri / Bloom (2025)** | Automated behavioural exploration, deception probing | Static guarantees |

The collective gap: *none enforce a typed protocol over multi-agent message flow*. This is the MPST-shaped hole.

## 5. Recent agent-verification papers (2024–2026)

- *VeriPlan* (CHI 2025) — LLM-extracted rules + model checker for end-user planning.
- *VeriGuard* (Miculicich et al., 2025) — offline policy verification + online monitoring.
- *Agent Behavioral Contracts* (arXiv 2602.22302) — explicit DbC for autonomous agents.
- *Mitigating Deceptive Alignment via Self-Monitoring* (arXiv 2505.18807).
- *Evaluating LLM Agent Adherence to Hierarchical Safety Principles* (arXiv 2506.02357).
- *Position: Trustworthy AI Agents Require Integration of LLMs and Formal Methods* (Hou 2025).
- *Logic-Based Verification of Task Allocation for LLM-Enabled Multi-Agent Manufacturing* (arXiv 2604.17142).
- Nature 2025: narrow-task fine-tuning causes broad misalignment — strong empirical motivation for spec-conformance checking.
- OpenAI April 2025 GPT-4o sycophancy rollback — production-scale evidence the problem is unsolved.

## 6. The hard problem: markdown as a typing system

The live frontier and the strongest research lever for AI_verf.

- **Liquid/refinement types with NL annotations**: refinements are predicates over base types, statically discharged via SMT. *AutoReSpec* (2025) uses verifier-guided conversational refinement to convert NL into verifiable specs. *VERGE* (arXiv 2601.20055) couples LLMs with SMT iteratively for formal-guaranteed answers.
- **NL → formal spec extraction (2025–2026)**: *Doc2Spec* (arXiv 2602.04892) does grammar induction. *Req2LTL* (arXiv 2512.17334) decomposes requirements into hierarchical "OnionL" trees then deterministically converts to LTL. *Transforming NL into Formal Specifications* (AgenticSE/ASE 2025), *Extracting Formal Specs from Documents* (arXiv 2504.01294), and Meng (Wiley Systems Engineering 2026) attack the same problem. **Best LLMs hit 51.7% accuracy** (Claude-3.5-Sonnet) on full-document spec extraction — *not yet trustworthy unattended*; the consensus solution is *annotate-then-convert* (split sentence-level intent tagging from formalisation).
- **Fundamental limit**: LLMs hallucinate fake specs and oversimplify boundary conditions. Implication: the markdown-to-types compiler must be *bidirectional* — extract candidate types, then *show them back to the human* for confirmation, with an SMT-checked round-trip proof.

## 7. Why MPST is the right core

(1) 20-year industrial track record (JBoss Scribble, Ocean Observatories, Rumpsteak, integration over 16 languages — Hu et al., Oxford MRG). (2) Global type → endpoint projection is exactly the "compile a spec, check each agent locally" loop AI_verf wants. (3) MPST already has runtime verification, model checking, and contract extensions in the literature (*Hybrid Multiparty Session Types*, PACMPL 2023). (4) The 2025 "Formalizing Safety/Security/Functional Properties of Agent Communication" paper notes MCP/A2A/ACP lack a unifying semantics — **MPST is the most credible candidate for that semantics**.

---

# Consolidated Bibliography

## Multiparty session types — foundational
- Honda, Yoshida, Carbone. *Multiparty Asynchronous Session Types*. POPL 2008; JACM 2016. https://mrg.doc.ic.ac.uk/publications/multiparty-asynchronous-session-types-jacm/jacm.pdf
- Scalas, Yoshida. *Less is More: Multiparty Session Types Revisited*. POPL 2019. https://dl.acm.org/doi/10.1145/3290343
- Coppo, Dezani-Ciancaglini, Padovani, Yoshida. *A Gentle Introduction to MPST*. https://mrg.cs.ox.ac.uk/publications/a-gentle-introduction-to-multiparty-asynchronous-session-types/paper.pdf
- *Comprehensive Multiparty Session Types*. https://arxiv.org/pdf/1902.00544
- *Behavioral Types in Programming Languages*. FnT 2016.
- *Foundations of Session Types and Behavioural Contracts*. ACM CSUR 2016. https://dl.acm.org/doi/pdf/10.1145/2873052

## MPST extensions
- Yoshida, Deniélou, Bejleri, Hu. *Parameterised MPST*. https://link.springer.com/chapter/10.1007/978-3-642-12032-9_10
- Deniélou, Yoshida. *Dynamic Multirole Session Types*. https://www.doc.ic.ac.uk/~yoshida/paper/main.pdf
- Anderson, Rathke. *Dynamically Updatable MPST*. Oxford. https://ora.ox.ac.uk/objects/uuid:fd3e5f94-b626-49ff-9959-396a742e3751
- Bocchi, Honda, Tuosto, Yoshida. *A Theory of Design-by-Contract for Distributed Multiparty Interactions*. CONCUR 2010.
- *Refinements for Multiparty Message-Passing Protocols*. ECOOP 2024. https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2024.41
- Igarashi, Thiemann, Tsuda, Vasconcelos, Wadler. *Gradual Session Types*. ICFP 2017. https://dl.acm.org/doi/10.1145/3110282
- Lange, Tuosto. *Synthesising Choreographies from Local Session Types*. CONCUR 2012. https://arxiv.org/abs/1204.2566
- Deniélou, Yoshida. *Multiparty Compatibility in Communicating Automata: Characterisation and Synthesis of Global Session Types*. ICALP 2013. https://link.springer.com/chapter/10.1007/978-3-642-39212-2_18
- Gheri, Yoshida. *Hybrid Multiparty Session Types: Compositionality for Protocol Specification through Endpoint Projection*. PACMPL 7(OOPSLA1) 2023. https://dl.acm.org/doi/abs/10.1145/3586031
- Bocchi, Chen, Demangeon, Honda, Yoshida. *Monitoring Networks through MPST*. FORTE 2013; TCS 2017. http://mrg.doc.ic.ac.uk/publications/monitoring-networks-through-multiparty-session-types/FORTE13.pdf
- *Monitoring Blackbox Implementations of Multiparty Session Protocols*. 2023. https://link.springer.com/chapter/10.1007/978-3-031-44267-4_4
- Inverso, Melgratti, Padovani et al. *Probabilities in Session Types*. https://arxiv.org/pdf/1909.01748
- Fu. *Probabilistic Refinement Session Types*. POPL 2025. https://dl.acm.org/doi/10.1145/3729317
- *Compositional Interface Refinement in Probabilistic Session Types*. https://arxiv.org/abs/2509.16228
- *Hybrid Multiparty Session Types*. PACMPL 2023. https://dl.acm.org/doi/abs/10.1145/3586031

## Choreographies
- Montesi. *Introduction to Choreographies*. Cambridge UP, 2023.
- Carbone, Montesi. *Deadlock-freedom-by-design: multiparty asynchronous global programming*. POPL 2013.
- Cruz-Filipe, Montesi. *A core model for choreographic programming*. TCS 2020.
- Giallorenzo, Montesi et al. *Choral: Object-oriented Choreographic Programming*. TOPLAS 2024. https://dl.acm.org/doi/10.1145/3632398
- Kashiwa, Shen, Lu, Kuper. *HasChor*. ICFP 2023. https://dl.acm.org/doi/10.1145/3607849
- *Choreography Automata*. https://link.springer.com/chapter/10.1007/978-3-030-50029-0_6

## Tools
- Scribble. http://mrg.doc.ic.ac.uk/tools/scribble/
- nuScr. https://github.com/nuscr/nuscr
- mpstk. https://github.com/alcestes/mpstk
- StMungo / Mungo. https://www.sciencedirect.com/science/article/pii/S0167642317302186
- RouST / STScript. https://dl.acm.org/doi/10.1145/3446804.3446854
- Microsoft TypeAgent. https://github.com/microsoft/TypeAgent

## NL → spec / agentic verification (2024–2026)
- PROSPER. HotNets 2023. https://conferences.sigcomm.org/hotnets/2023/papers/hotnets23_sharma.pdf
- AutoSpec. https://arxiv.org/html/2511.17977
- Doc2Spec. ASE 2009. https://taoxie.cs.illinois.edu/publications/ase09-doc2spec.pdf
- Doc2Spec (LLM era). https://arxiv.org/html/2602.04892v1
- Towards Agentic LLM-based Requirement Formalization. https://arxiv.org/html/2604.18228v1
- AutoReSpec. https://arxiv.org/html/2604.03758
- Req2LTL. https://arxiv.org/html/2512.17334v1
- Extracting Formal Specs from Documents. https://arxiv.org/html/2504.01294v1
- VERGE. https://arxiv.org/pdf/2601.20055
- AgentSpec. ICSE 2026. https://arxiv.org/abs/2503.18666
- Agent-C. https://www.arxiv.org/pdf/2512.23738
- AgentVerify. https://www.preprints.org/manuscript/202604.1029
- LogicGuard / LTLCrit. https://arxiv.org/html/2507.03293
- AutoSafeLTL. https://arxiv.org/html/2503.15840
- Runtime Verification for LTL in Stochastic Systems. Springer 2025. https://link.springer.com/chapter/10.1007/978-3-032-05435-7_20
- Runtime Governance for AI Agents: Policies on Paths. https://arxiv.org/html/2603.16586
- Policy-as-Prompt. https://arxiv.org/abs/2509.23994
- Formalizing Safety/Security/Functional Properties of Agentic AI. https://arxiv.org/pdf/2510.14133
- Position: Trustworthy AI Agents Require LLMs + Formal Methods. https://zhehou.github.io/papers/Position-Trustworthy-AI-Agents-Require-the-Integration-of-Large-Language-Models-and-Formal-Methods.pdf
- Bridging LLM Planning Agents and Formal Methods. https://arxiv.org/abs/2510.03469
- VeriPlan. CHI 2025. https://dl.acm.org/doi/10.1145/3706598.3714113
- Sherlock. https://arxiv.org/abs/2511.00330
- Agentic Verification of Software Systems. https://arxiv.org/html/2511.17330v2
- Agent Behavioral Contracts. https://arxiv.org/html/2602.22302v1
- DbC-Inspired Neurosymbolic Layer. https://arxiv.org/pdf/2508.03665
- Beyond Postconditions: LLM Formal Contracts. https://arxiv.org/pdf/2510.12702
- PropertyGPT. https://liyiweb.com/files/Liu2025PLD.pdf

## Harness / standards / runtime
- Anthropic Agent Skills (Open Standard). https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Anthropic engineering: Equipping agents with skills. https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Claude Code subagents docs. https://code.claude.com/docs/en/sub-agents
- Claude Code hooks docs. https://code.claude.com/docs/en/hooks
- AGENTS.md. https://agents.md/
- AGENTS.md as open standard (InfoQ). https://www.infoq.com/news/2025/08/agents-md/
- OpenAI Codex AGENTS.md. https://developers.openai.com/codex/guides/agents-md
- Agent Skills Open Standard (paperclipped.de). https://www.paperclipped.de/en/blog/agent-skills-open-standard-interoperability/
- OpenAI Agents SDK handoffs. https://openai.github.io/openai-agents-python/handoffs/
- OpenAI Agents SDK tracing. https://openai.github.io/openai-agents-python/tracing/
- OpenAI Evals. https://developers.openai.com/api/docs/guides/evals
- OpenAI Agent Evals. https://developers.openai.com/api/docs/guides/agent-evals
- LangGraph Graph API. https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph StateGraph. https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- LangSmith Evaluation. https://docs.langchain.com/langsmith/evaluation
- AutoGen SelectorGroupChat. https://microsoft.github.io/autogen/dev//user-guide/agentchat-user-guide/selector-group-chat.html
- CrewAI Agents. https://docs.crewai.com/en/concepts/agents
- Cursor Rules. https://cursor.com/docs/context/rules
- OpenHands microagents. https://docs.openhands.dev/openhands/usage/microagents/microagents-overview
- MCP Specification 2025-11-25. https://modelcontextprotocol.io/specification/2025-11-25
- 2026 MCP Roadmap. https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/
- Inspect AI. https://inspect.aisi.org.uk/
- Inspect AI Scorers. https://inspect.aisi.org.uk/scorers.html
- Inspect Evals. https://ukgovernmentbeis.github.io/inspect_evals/
- AISI Autonomous Systems Evaluation Standard. https://ukgovernmentbeis.github.io/as-evaluation-standard/
- OTel GenAI Semantic Conventions. https://opentelemetry.io/docs/specs/semconv/gen-ai/
- OTel GenAI agent and framework spans. https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/
- DeepEval alternatives 2026. https://www.braintrust.dev/articles/deepeval-alternatives-2026
- Top AI Agent Evaluation Tools 2026. https://www.goodeyelabs.com/articles/top-ai-agent-evaluation-tools-2026
- Survey of Agent Interoperability Protocols (MCP/ACP/A2A/ANP). https://arxiv.org/html/2505.02279v1

## Calibration / behavioural
- Stress-Testing Model Specs (Anthropic 2025). https://alignment.anthropic.com/2025/stress-testing-model-specs/
- Claude's New Constitution. https://www.anthropic.com/news/claude-new-constitution
- OpenAI Model Spec. https://model-spec.openai.com/2025-12-18.html
- Behavior Specification Transparency (FLI 2025). https://futureoflife.org/wp-content/uploads/2025/07/Indicator-Behavior_Specification_Transparency.pdf
- Autorubric. https://arxiv.org/html/2603.00077v2
- LLM-as-Judge calibration (Deepchecks). https://deepchecks.com/llm-judge-calibration-automated-issues/
- Mitigating Deceptive Alignment via Self-Monitoring. https://arxiv.org/pdf/2505.18807
- Evaluating LLM Agent Adherence to Hierarchical Safety Principles. https://arxiv.org/html/2506.02357
- Detecting Safety Violations Across Many Agent Traces. https://arxiv.org/html/2604.11806v1
- Reasoning About Quality in Hyperproperties. CSL 2026. https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CSL.2026.45
- Narrow-task fine-tuning → broad misalignment. Nature 2025. https://www.nature.com/articles/s41586-025-09937-5
- Sycophancy in LLMs (Giskard). https://www.giskard.ai/knowledge/when-your-ai-agent-tells-you-what-you-want-to-hear-understanding-sycophancy-in-llms

## Metamorphic / property-based
- LLMORPH. ASE 2025. https://valerio-terragni.github.io/assets/pdf/cho-ase-2025.pdf
- Metamorphic Testing of LLMs survey. ICSME 2025. https://valerio-terragni.github.io/assets/pdf/cho-icsme-2025.pdf
- MTF Framework. ACM 2025. https://dl.acm.org/doi/10.1145/3787120.3787123

## Goal specification
- EmboTeam (PDDL + BTs). https://arxiv.org/abs/2601.11063
- Code-BT. IJCAI 2025. https://www.ijcai.org/proceedings/2025/0980.pdf
- LLM-as-BT-Planner. https://arxiv.org/html/2409.10444v2
- StateFlow. https://arxiv.org/html/2403.11322v1
- MetaAgent (FSM-based MAS). https://arxiv.org/html/2507.22606v1
- Formal specification + validation of multi-agent behaviour (TLA+/TLC). ResearchGate.

## Guardrails / contracts
- Guardrails AI. https://github.com/guardrails-ai/guardrails
- Guardrails AI vs NeMo Guardrails. https://is4.ai/blog/our-blog-1/guardrails-ai-vs-nemo-guardrails-comparison-2026-352
- pydantic-ai-guardrails. https://pypi.org/project/pydantic-ai-guardrails/
- Contracts for LLM APIs. https://tanzimhromel.com/assets/pdf/llm-api-contracts.pdf
- Prover Agent (Lean). https://arxiv.org/abs/2506.19923
