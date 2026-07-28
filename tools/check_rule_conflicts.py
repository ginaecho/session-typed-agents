#!/usr/bin/env python3
"""check_rule_conflicts.py — detect conflicts between rule sources, and
refuse to resolve any conflict nobody declared a winner for.

Why this exists: on 2026-07-25 the hosted platform mandated a branch name
and commit trailers that AGENT.md forbids. No rule said which source wins,
so the agent resolved the conflict silently toward the nearer instruction —
the most dangerous failure mode in the session record, because there is no
moment of transgression to notice
(docs/reference/SESSION_RECORD_2026-07-25.md §7, §9). This pass makes such
a conflict a loud compile-time error instead: two sources constraining the
same subject incompatibly, with no declared precedence, fails the check.

How it decides incompatibility (deterministically, per constraint kind):
  - two required prefixes that cannot both hold (e.g. `gc/` vs `claude/`)
  - a forbidden substring appearing in another rule's required value
    (e.g. substring `claude` forbidden vs prefix `claude/` required)
  - two different required identities
  - a required trailer whose value matches a trailer forbiddance

Resolution comes only from a precedence file (tools/rules/PRECEDENCE.yaml):
an ordered source list (earlier wins) plus explicitly declared exceptions
(a losing rule tolerated anyway, with an obligation attached — e.g. the
platform-created branch name, which must be surfaced in the agent's reply).

Usage:
  python tools/check_rule_conflicts.py                 # all sources + precedence
  python tools/check_rule_conflicts.py --no-precedence # show the raw conflicts
Exit code 0 = no undeclared conflicts, 1 = at least one (refusing to guess).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).resolve().parent / "rules"


def load_sources(paths: list[Path]) -> list[dict]:
    sources = []
    for p in paths:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        for rule in doc.get("rules", []):
            rule["_source"] = doc["source"]
        sources.append(doc)
    return sources


def incompatible(a: dict, b: dict) -> str | None:
    """Return a plain-language reason if constraints a and b cannot both
    hold, else None. Only cross-checks the kinds we know; unknown pairs are
    treated as compatible (and therefore never silently resolved either)."""
    ca, cb = a.get("constraint"), b.get("constraint")
    if not ca or not cb:
        return None
    for x, y in ((ca, cb), (cb, ca)):
        kx, ky = x.get("kind"), y.get("kind")
        if kx == "prefix_required" and ky == "prefix_required":
            px, py = x["value"], y["value"]
            if not (px.startswith(py) or py.startswith(px)):
                return (f"a name cannot start with both '{px}' and '{py}'")
        if kx == "substring_forbidden" and ky in ("prefix_required",
                                                  "trailer_required"):
            needle = x["value"].lower() if not x.get("case_sensitive") \
                else x["value"]
            hay = (y.get("value") or y.get("value_contains") or "")
            hay_cmp = hay.lower() if not x.get("case_sensitive") else hay
            if needle in hay_cmp:
                return (f"substring '{x['value']}' is forbidden but the "
                        f"other rule requires a value containing it "
                        f"('{hay}')")
        if kx == "identity_required" and ky == "identity_required":
            if (x["name"], x["email"]) != (y["name"], y["email"]):
                return (f"two different required identities: "
                        f"{x['name']} <{x['email']}> vs "
                        f"{y['name']} <{y['email']}>")
        if kx == "trailer_forbidden_except_owner" and ky == "trailer_required":
            val = (y.get("value_contains") or "").lower()
            if not any(o.lower() in val for o in x.get("owner_match", [])):
                return ("a trailer is required whose value matches no "
                        "allowed owner, but non-owner trailers are forbidden")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", nargs="*", type=Path, default=None,
                    help="rule source YAMLs (default: tools/rules/*_RULES.yaml)")
    ap.add_argument("--precedence", type=Path,
                    default=RULES_DIR / "PRECEDENCE.yaml",
                    help="precedence declaration file")
    ap.add_argument("--no-precedence", action="store_true",
                    help="ignore the precedence file (show raw conflicts)")
    args = ap.parse_args()

    paths = args.sources or sorted(RULES_DIR.glob("*_RULES.yaml"))
    sources = load_sources(paths)
    all_rules = [r for s in sources for r in s.get("rules", [])]

    precedence = None
    if not args.no_precedence and args.precedence.exists():
        precedence = yaml.safe_load(args.precedence.read_text(encoding="utf-8"))

    # Group cross-source rule pairs by subject and test compatibility.
    subjects: dict[str, list[dict]] = {}
    for r in all_rules:
        subjects.setdefault(r["subject"], []).append(r)

    undeclared = 0
    resolved = 0
    tolerated = 0
    for subject, rules in sorted(subjects.items()):
        reasons = []
        pair_sources = set()
        for i, a in enumerate(rules):
            for b in rules[i + 1:]:
                if a["_source"] == b["_source"]:
                    continue
                reason = incompatible(a, b)
                if reason:
                    reasons.append((a, b, reason))
                    pair_sources.update((a["_source"], b["_source"]))
        if not reasons:
            continue

        print(f"CONFLICT on subject '{subject}':")
        for a, b, reason in reasons:
            print(f"  {a['_source']}:{a['id']}  vs  {b['_source']}:{b['id']}")
            print(f"    {reason}")

        if precedence is None:
            print("  -> UNDECLARED: no precedence declared; refusing to guess.")
            undeclared += 1
            continue
        exc = next((e for e in precedence.get("exceptions", [])
                    if e["subject"] == subject), None)
        order = precedence.get("order", [])
        ranked = sorted(pair_sources,
                        key=lambda s: order.index(s) if s in order
                        else len(order))
        if exc is not None:
            print(f"  -> TOLERATED with obligation "
                  f"(losing source '{exc['tolerate']}' accepted): "
                  f"{' '.join(str(exc['obligation']).split())}")
            tolerated += 1
        elif all(s in order for s in pair_sources):
            print(f"  -> RESOLVED: '{ranked[0]}' wins over "
                  f"'{', '.join(ranked[1:])}' (declared order)")
            resolved += 1
        else:
            missing = [s for s in pair_sources if s not in order]
            print(f"  -> UNDECLARED: source(s) {missing} not in the declared "
                  f"order; refusing to guess.")
            undeclared += 1

    print(f"\nchecked {len(all_rules)} rules from "
          f"{len(sources)} source(s) -> {resolved} resolved, "
          f"{tolerated} tolerated with obligation, {undeclared} undeclared")
    return 1 if undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())
