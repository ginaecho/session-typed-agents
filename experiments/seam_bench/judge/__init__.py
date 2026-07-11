"""Faithfulness judge panel — plan v2.1 §5, §6.

Modules:
    payloads   - §5.2 payload sanitizer (comment-free canonical G)
    seats      - §5.1/§5.3/§5.4 seat config + stateless SDK call primitives
    classes    - J-fwd / J-back / J-probe
    aggregate  - §5.3/§5.5 deterministic aggregation (geometric median,
                 J-probe veto, evidence verification, escalation)
    canaries   - §5.5 collusion/degeneration audit battery
    cache      - §5.1 verdict cache
"""
