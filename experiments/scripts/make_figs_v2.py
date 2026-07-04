"""make_figs_v2.py — render Figure 3 panels a–d for the paper (PLAN_V2 §10).

Emits self-contained SVG (no matplotlib / no external fonts, so it runs
anywhere and versions cleanly). Every panel reads its data from the E*
report JSONs where those are REAL, and from inline SYNTH arrays where the
experiment is still measurement-pending. SYNTH panels get a grey
"projected (synthetic)" corner tag; set SYNTH_TAGS=False to drop them once
real data lands.

  (a) E1 mutation detection per defect class          [REAL]
  (b) E2 adversarial exfiltration blocked, per guard   [REAL]
  (c) E3 capability sweep (disasters + enforcement gain) [SYNTH + 2 real anchors]
  (d) E6 roles sweep coordination cost (structural)     [REAL proxy; tokens SYNTH]

    python experiments/scripts/make_figs_v2.py -o experiments/reports/figs
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent / "reports"
SYNTH_TAGS = True

W, H = 520, 340
PAD = 56
INK = "#1b2733"
BAR = "#3f7cac"
BAR2 = "#c65b3c"
GRID = "#d8dee4"


def _svg_open(title, subtitle=""):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="white"/>',
        f'<text x="{PAD}" y="26" font-size="15" font-weight="bold" fill="{INK}">{title}</text>',
        (f'<text x="{PAD}" y="44" font-size="11" fill="#5a6b7b">{subtitle}</text>'
         if subtitle else ""),
    ]


def _synth_tag(lines):
    if SYNTH_TAGS:
        lines.append(
            f'<text x="{W-10}" y="{H-8}" font-size="9" fill="#9aa7b3" '
            f'text-anchor="end">projected (synthetic); measurement pending</text>')


def _axes(lines, x0, y0, x1, y1, ylabel):
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{INK}"/>')
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{INK}"/>')
    lines.append(f'<text x="14" y="{(y0+y1)//2}" font-size="10" fill="{INK}" '
                 f'transform="rotate(-90 14 {(y0+y1)//2})" text-anchor="middle">{ylabel}</text>')


def bars(title, subtitle, labels, values, maxv, ylabel, colors=None, synth=False,
         value_fmt="{:.0f}"):
    lines = _svg_open(title, subtitle)
    x0, y0, x1, y1 = PAD, H - 60, W - 24, 60
    _axes(lines, x0, y0, x1, y1, ylabel)
    n = len(labels)
    span = (x1 - x0) / n
    bw = span * 0.6
    for i, (lab, v) in enumerate(zip(labels, values)):
        h = (v / maxv) * (y0 - y1) if maxv else 0
        bx = x0 + span * i + (span - bw) / 2
        by = y0 - h
        col = (colors[i] if colors else BAR)
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" '
                     f'height="{h:.1f}" fill="{col}"/>')
        lines.append(f'<text x="{bx+bw/2:.1f}" y="{by-4:.1f}" font-size="10" '
                     f'fill="{INK}" text-anchor="middle">{value_fmt.format(v)}</text>')
        lines.append(f'<text x="{bx+bw/2:.1f}" y="{y0+14:.1f}" font-size="9" '
                     f'fill="{INK}" text-anchor="middle">{lab}</text>')
    if synth:
        _synth_tag(lines)
    lines.append("</svg>")
    return "\n".join(l for l in lines if l)


def lines_plot(title, subtitle, xs, series, ylabel, synth=False):
    lines = _svg_open(title, subtitle)
    x0, y0, x1, y1 = PAD, H - 60, W - 24, 60
    _axes(lines, x0, y0, x1, y1, ylabel)
    maxv = max(max(s["y"]) for s in series) or 1
    span = (x1 - x0) / (len(xs) - 1 if len(xs) > 1 else 1)
    for s in series:
        pts = []
        for i, y in enumerate(s["y"]):
            px = x0 + span * i
            py = y0 - (y / maxv) * (y0 - y1)
            pts.append(f"{px:.1f},{py:.1f}")
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" '
                     f'stroke="{s["color"]}" stroke-width="2"/>')
        lines.append(f'<text x="{x1-4}" y="{y0-(s["y"][-1]/maxv)*(y0-y1)-4:.1f}" '
                     f'font-size="10" fill="{s["color"]}" text-anchor="end">{s["name"]}</text>')
    for i, xv in enumerate(xs):
        px = x0 + span * i
        lines.append(f'<text x="{px:.1f}" y="{y0+14}" font-size="9" '
                     f'fill="{INK}" text-anchor="middle">{xv}</text>')
    if synth:
        _synth_tag(lines)
    lines.append("</svg>")
    return "\n".join(l for l in lines if l)


def fig_a():
    d = json.loads((REPORTS / "e1" / "mutation_summary.json").read_text())
    pc = d["per_class"]
    order = ["undeclare_role", "flip_branch_subject", "branch_asymmetry"]
    labs = ["undeclare\nrole", "flip branch\nsubject", "branch\nasymmetry"]
    vals = [pc[c]["detection_rate_pct"] for c in order]
    labs = [l.replace("\n", " ") for l in labs]
    return bars("Fig 3a — E1: checker catches well-formedness defects",
                f"detection %, {d['corpus_size']}-protocol corpus, "
                f"false positives {d['false_positive_rate_pct']}%  [REAL]",
                labs, vals, 100, "detection %",
                colors=[BAR] * len(vals), value_fmt="{:.1f}")


def fig_b():
    d = json.loads((REPORTS / "e2" / "adversarial_summary.json").read_text())
    conds = ["none", "rules", "gate", "gate+refn"]
    vals = [d["conditions"][c]["blocked_pct"] for c in conds]
    cols = [BAR2, "#d89b3c", BAR, "#2e8b57"]
    return bars("Fig 3b — E2: exfiltration blocked, per guard",
                f"{d['templates']} injection templates, target=ExternalAuditor  [REAL]",
                conds, vals, 100, "% blocked", colors=cols, value_fmt="{:.1f}")


def fig_c():
    from capability_sweep import synth_series
    s = synth_series()
    return lines_plot("Fig 3c — E3: story holds across model strength",
                      "A-arm disasters (rising) + enforcement gain (falling)  "
                      "[SYNTH + 2 real anchors]",
                      s["tiers"],
                      [{"name": "A disasters", "y": s["A_disasters"], "color": BAR2},
                       {"name": "enforce gain", "y": s["enforcement_gain"], "color": BAR}],
                      "count / points", synth=True)


def fig_d():
    d = json.loads((REPORTS / "e6" / "roles_sweep.json").read_text())
    xs = [r["n_roles"] for r in d["rows"]]
    gt = [r["global_text_cost_proxy"] / 1000 for r in d["rows"]]
    st = [r["stjp_cost_proxy"] / 1000 for r in d["rows"]]
    return lines_plot("Fig 3d — E6: coordination cost vs #roles",
                      "structural proxy (k-chars); token-per-goal PENDING  "
                      "[REAL proxy]",
                      xs,
                      [{"name": "global text", "y": gt, "color": BAR2},
                       {"name": "STJP", "y": st, "color": BAR}],
                      "cost proxy (k)")


def main() -> int:
    import sys
    sys.path.insert(0, str(HERE))
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="experiments/reports/figs")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    figs = {"fig3a_mutation.svg": fig_a(), "fig3b_adversarial.svg": fig_b(),
            "fig3c_capability.svg": fig_c(), "fig3d_roles.svg": fig_d()}
    for name, svg in figs.items():
        (out / name).write_text(svg, encoding="utf-8")
        print(f"  wrote {out/name}")
    print(f"\n{len(figs)} figures -> {out}  (SYNTH_TAGS={SYNTH_TAGS})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
