"""human_audit — Gina's §6 calibration-gate human fit/no-fit labeling tool.

See README.md in this directory for the 5-step quickstart. Modules:

  packet_builder.py  builds audit_packet.jsonl (blind, shown to the human)
                      and packet_key.jsonl (ground-truth strata, never read
                      by the Streamlit app) from existing benchmark assets.
  audit_app.py        `streamlit run` UI: one card at a time, Fit/No fit/
                       Unsure, resumable append-only labels.jsonl.
  analysis.py          post-hoc: joins labels.jsonl with packet_key.jsonl,
                       computes per-stratum agreement, intra-rater
                       consistency on repeats, and the §6 Wilson-bound gate.
"""
