"""experiments.intent_loop — the intent interrogation + validation loop.

Multi-turn interrogation of a stakeholder (real or simulated) distills a
document-scale intent into atomic typed requirements; a live-LLM drafter
turns them into a Scribble global protocol through the existing t0
validate/repair loop; a faithfulness suite checks the validated protocol
back against every requirement; and each episode feeds an append-only
corpus that prompt-level optimization (few-shot exemplars + validator-error
rulebook) mines — training the translator without touching model weights.

See README.md in this directory for the design and CLI usage.
"""
