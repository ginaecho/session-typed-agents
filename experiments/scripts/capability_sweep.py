"""capability_sweep.py — E3: does the story hold across model strength? (§4)

Two claims that need a CURVE, not two points:
  (i)  without a protocol, STRONGER models do MORE damage (they act confidently);
  (ii) with strong models, enforcement adds LESS on top of pasting the protocol
       (they self-comply). "enforcement gain" = C+ GCR − B GCR should fall to 0.

Run arms A (intent), B (global text), C+ (full STJP) across model tiers on the
same finance case, n=30 each, and plot: A-arm disaster count vs tier (rising)
and enforcement gain vs tier (falling). Two points are already measured
(gpt-4o: 4 disasters, gain +60; gpt-5.4: 22 disasters, gain 0).

MEASUREMENT PENDING here: needs multiple model families + Azure. This module
holds the run plan, the two real anchor points, and the SYNTH placeholder
targets (used by make_figs_v2.py, clearly tagged) so the figure renders now and
real points swap in later.
"""
from __future__ import annotations

import json
from pathlib import Path

# tier order: small open model, gpt-4o, gpt-5.4, frontier competitor
TIERS = ["small-open", "gpt-4o", "gpt-5.4", "frontier"]

# (*) = real anchor already measured; others are SYNTH targets.
DISASTERS_A = {"small-open": 2, "gpt-4o": 4, "gpt-5.4": 22, "frontier": 26}
DISASTERS_REAL = {"gpt-4o": True, "gpt-5.4": True}
ENFORCEMENT_GAIN = {"small-open": 70, "gpt-4o": 60, "gpt-5.4": 0, "frontier": 0}
GAIN_REAL = {"gpt-4o": True, "gpt-5.4": True}

PLAN = {
    "arms": ["A_intent", "B_global_text", "Cplus_full_stjp"],
    "n_per_cell": 30,
    "case": "finance",
    "metrics": {"A_disasters": "S4 count on the intent arm",
                "enforcement_gain": "C+ GCR minus B GCR (percentage points)"},
    "status": "MEASUREMENT PENDING (needs multiple model families + Azure)",
    "real_anchors": {"gpt-4o": {"A_disasters": 4, "enforcement_gain": 60},
                     "gpt-5.4": {"A_disasters": 22, "enforcement_gain": 0}},
}


def synth_series() -> dict:
    return {
        "tiers": TIERS,
        "A_disasters": [DISASTERS_A[t] for t in TIERS],
        "A_disasters_is_real": [DISASTERS_REAL.get(t, False) for t in TIERS],
        "enforcement_gain": [ENFORCEMENT_GAIN[t] for t in TIERS],
        "gain_is_real": [GAIN_REAL.get(t, False) for t in TIERS],
        "synthetic": True,
    }


if __name__ == "__main__":
    out = Path("experiments/reports/e3")
    out.mkdir(parents=True, exist_ok=True)
    (out / "capability_sweep_plan.json").write_text(
        json.dumps({"plan": PLAN, "synth_series": synth_series()}, indent=2),
        encoding="utf-8")
    print("E3 capability sweep — MEASUREMENT PENDING")
    print(f"  real anchors: gpt-4o (4 disasters, +60 gain), "
          f"gpt-5.4 (22 disasters, 0 gain)")
    print(f"  SYNTH targets for {TIERS}: disasters={list(synth_series()['A_disasters'])}, "
          f"gain={list(synth_series()['enforcement_gain'])}")
    print(f"  wrote {out}/capability_sweep_plan.json")
