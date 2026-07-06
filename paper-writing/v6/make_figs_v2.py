import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import numpy as np, math

# ---------------- ICLR-grade global style ----------------
OI = {  # Okabe-Ito (Wong, Nature Methods 2011)
    "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "verm": "#D55E00",
    "pink": "#CC79A7", "black": "#000000", "grey": "#8C8C8C",
}
# fixed condition -> color mapping, used in EVERY figure
ARM = {"A": OI["verm"], "B": OI["orange"], "C": OI["sky"], "Cmin": OI["blue"], "Cp": OI["green"], "STJP": OI["green"]}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5,
    "axes.titlesize": 9, "axes.labelsize": 8.5,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.8, "xtick.major.width": 0.8, "ytick.major.width": 0.8,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#DDDDDD",
    "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "figure.dpi": 200, "savefig.bbox": "tight",
})

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0, c-h), min(1, c+h))

def ci_err(pcts, n):
    lo, hi = [], []
    for p in pcts:
        if p is None: lo.append(0); hi.append(0); continue
        l, h = wilson(round(p/100*n), n)
        lo.append(p/100 - l); hi.append(h - p/100)
    return np.clip(np.array([lo, hi]) * 100, 0, None)

def panel_label(ax, s):
    ax.text(-0.11, 1.06, s, transform=ax.transAxes, fontsize=11, fontweight="bold", va="top")

# =========================================================
# Figure 1 — system architecture (clean, grid-aligned, elbow arrows)
# =========================================================
fig, ax = plt.subplots(figsize=(10.6, 5.0))
ax.set_xlim(0, 106); ax.set_ylim(0, 54); ax.axis("off"); ax.grid(False)

INK = "#3A3A3A"; EDGE = "#9AA3AD"
FILL_N = "#F6F7F9"   # neutral
FILL_C = "#EAF1F8"   # compile artifacts (blue tint)
FILL_V = "#EAF5EF"   # validated / proven (green tint)
FILL_R = "#FBF0EC"   # runtime enforcement (warm tint)

def bx(x, y, w, h, title, sub="", fill=FILL_N, edge=EDGE, tfs=8.6, sfs=7.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.9",
                                fc=fill, ec=edge, lw=1.1))
    if sub:
        ax.text(x+w/2, y+h-2.1, title, ha="center", va="center", fontsize=tfs, fontweight="bold", color=INK)
        ax.text(x+w/2, y+(h-3.4)/2, sub, ha="center", va="center", fontsize=sfs, color="#555555", linespacing=1.35)
    else:
        ax.text(x+w/2, y+h/2, title, ha="center", va="center", fontsize=tfs, fontweight="bold", color=INK)
    return (x, y, w, h)

def elbow(p1, p2, side1="r", side2="l", color=INK, ls="-", lw=1.2, label="", loff=(0, 1.0), rad=0.0):
    x1, y1, w1, h1 = p1; x2, y2, w2, h2 = p2
    a = {"r": (x1+w1, y1+h1/2), "l": (x1, y1+h1/2), "t": (x1+w1/2, y1+h1), "b": (x1+w1/2, y1)}[side1]
    b = {"r": (x2+w2, y2+h2/2), "l": (x2, y2+h2/2), "t": (x2+w2/2, y2+h2), "b": (x2+w2/2, y2)}[side2]
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11, lw=lw, color=color,
                                 linestyle=ls, shrinkA=1, shrinkB=1,
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((a[0]+b[0])/2 + loff[0], (a[1]+b[1])/2 + loff[1], label,
                ha="center", va="bottom", fontsize=7.2, color=color, style="italic")

def badge(x, y, s):
    ax.add_patch(Circle((x, y), 1.55, fc=INK, ec="none", zorder=5))
    ax.text(x, y, s, ha="center", va="center", fontsize=7.2, color="white", fontweight="bold", zorder=6)

# lane separators + labels
ax.axhline(27.5, xmin=0.0, xmax=1.0, color="#C9CED4", lw=0.8, ls=(0, (2, 3)))
ax.axhline(11.5, xmin=0.0, xmax=1.0, color="#C9CED4", lw=0.8, ls=(0, (2, 3)))
ax.text(0.5, 52.6, "COMPILE TIME", fontsize=8.2, fontweight="bold", color="#5A6570")
ax.text(14.5, 52.6, "static — runs before any agent exists", fontsize=7.4, color="#8A939C", style="italic")
ax.text(0.5, 25.9, "RUN TIME", fontsize=8.2, fontweight="bold", color="#5A6570")
ax.text(9.5, 25.9, "deterministic code, not agents — O(1) per message, zero tokens", fontsize=7.4, color="#8A939C", style="italic")
ax.text(0.5, 9.9, "MEASUREMENT", fontsize=8.2, fontweight="bold", color="#5A6570")
ax.text(13.0, 9.9, "offline, bit-reproducible", fontsize=7.4, color="#8A939C", style="italic")

# ---- compile row (y=34..46) ----
B_int  = bx(1,  35.5, 14, 9, "User intent", "natural language\ntask + policies", FILL_N)
B_llm  = bx(19, 35.5, 14, 9, "LLM drafter", "intent \u2192 protocol\n(+ guard sidecar)", FILL_C)
B_scr  = bx(37, 35.5, 15, 9, "Global type G", "Scribble .scr\n+ .refn guards\n+ goal markers", FILL_C)
B_val  = bx(56, 35.5, 16, 9, "Static validator", "projectability \u00b7 deadlock\nguarded recursion\ngoal reachability", FILL_V, edge="#4E9B6F")
B_proj = bx(76, 35.5, 15, 9, "Projection G\u21beRi", "one local type\nper role \u2192 EFSM", FILL_V, edge="#4E9B6F")

elbow(B_int, B_llm); elbow(B_llm, B_scr); elbow(B_scr, B_val)
elbow(B_val, B_proj, label="VALID", loff=(0, 0.6))
# reject loop (below the row)
ax.add_patch(FancyArrowPatch((64, 44.5), (28, 44.5), arrowstyle="-|>", mutation_scale=11,
                             lw=1.1, color=OI["verm"], linestyle=(0, (4, 2)),
                             connectionstyle="arc3,rad=-0.20"))
ax.text(46, 49.4, "REJECTED + counterexample \u2192 re-draft   (human endorses the final G)",
        ha="center", fontsize=7.2, color=OI["verm"], style="italic")
badge(19, 45.6, "S1"); badge(56, 45.6, "S2"); badge(76, 45.6, "S3")

# ---- artifacts emitted by projection (right column, compile row continues) ----
B_art = bx(94, 35.5, 11, 9, "3 artifacts\nper role", "", FILL_V, edge="#4E9B6F", tfs=8.2)
elbow(B_proj, B_art)

# ---- runtime row (y=14..24) ----
B_ag   = bx(1,  15, 18, 9, "LLM agents", "receive lean local skill\n(SEND/RECV table + guards);\nuntyped 'dyn' participants", FILL_N)
B_gate = bx(30, 15, 21, 9, "Monitor + Gate  (generated)", "EFSM interpreter per role;\noff-contract send rejected\npre-delivery \u2192 re-prompt", FILL_R, edge="#C2836B")
B_schd = bx(58, 15, 20, 9, "EFSM scheduler", "prompts only roles enabled\nat the current protocol state;\nno idle polling", FILL_R, edge="#C2836B")
B_log  = bx(85, 15, 20, 9, "Typed event log", "role \u00b7 state \u00b7 branch \u00b7 verdict\n\u00b7 guard result \u00b7 goal marker",
            FILL_C)
badge(30, 25.1, "S4"); badge(58, 25.1, "S5")

# artifacts -> runtime
ax.add_patch(FancyArrowPatch((99.5, 35.5), (99.5, 31.3), arrowstyle="-", lw=1.1, color="#4E9B6F"))
ax.add_patch(FancyArrowPatch((99.5, 31.3), (11, 31.3), arrowstyle="-", lw=1.1, color="#4E9B6F"))
for xd, tgt in [(10, B_ag), (40.5, B_gate), (68, B_schd)]:
    ax.add_patch(FancyArrowPatch((xd, 31.3), (xd, 24.6), arrowstyle="-|>", mutation_scale=11, lw=1.1, color="#4E9B6F"))
ax.text(23, 31.9, "skill", fontsize=7.0, color="#4E9B6F", style="italic")
ax.text(44.5, 31.9, "monitor", fontsize=7.0, color="#4E9B6F", style="italic")
ax.text(71.5, 31.9, "schedule", fontsize=7.0, color="#4E9B6F", style="italic")

elbow(B_ag, B_gate, label="send m", loff=(0, 0.4))
ax.add_patch(FancyArrowPatch((30, 16.8), (19, 16.8), arrowstyle="-|>", mutation_scale=11, lw=1.1, color=OI["verm"]))
ax.text(24.5, 14.2, "block + re-prompt", fontsize=7.0, color=OI["verm"], style="italic")
elbow(B_gate, B_schd, label="allow", loff=(0, 0.4))
elbow(B_schd, B_log, label="event", loff=(0, 0.4))
ax.plot([68, 68], [15, 13.3], color="#8A939C", lw=1.0, ls=(0, (1, 2)))
ax.plot([68, 10], [13.3, 13.3], color="#8A939C", lw=1.0, ls=(0, (1, 2)))
ax.add_patch(FancyArrowPatch((10, 13.3), (10, 14.9), arrowstyle="-|>", mutation_scale=11, lw=1.0,
                             color="#8A939C", linestyle=(0, (1, 2))))
ax.text(39, 13.7, "turn control: 'you are the enabled sender at this state'", fontsize=6.6,
        color="#8A939C", style="italic")

# ---- measurement row (y=1..8.5) ----
B_met = bx(14, 1, 56, 7.5, "Deterministic metric engine  (no golden trajectory, no LLM judge)",
           "conformance rate \u00b7 path distribution \u00b7 goal progress \u00b7 detour cost \u00b7 repair burden \u00b7 S0\u2013S4 severity", FILL_V, edge="#4E9B6F")
B_anc = bx(76, 1, 29, 7.5, "Human outcome anchor (sampled)", "divergence \u21d2 re-draft G with the user,\nnot patch agents", FILL_N)
elbow(B_log, B_met, side1="b", side2="t")
elbow(B_log, B_anc, side1="b", side2="t")

plt.savefig("fig1_system.png", dpi=260); plt.savefig("fig1_system.pdf"); plt.close()

# =========================================================
# Figure 2 — measured results (4 panels, Wilson CIs, fixed arm colors)
# =========================================================
fig, axes = plt.subplots(1, 4, figsize=(11.6, 2.75))
arm_names = ["A", "B", "C", "C-min", "C+"]
arm_cols  = [ARM["A"], ARM["B"], ARM["C"], ARM["Cmin"], ARM["Cp"]]

# (a) GCR ladder, both models, with 95% Wilson CIs (n=10)
ax = axes[0]
x = np.arange(5); w = 0.38
g4 = [0, 40, 80, 60, None]; g5 = [0, 100, 60, 50, 100]
ax.bar(x - w/2, [v or 0 for v in g4], w, color=arm_cols, alpha=0.45,
       yerr=ci_err(g4, 10), error_kw=dict(lw=0.9, capsize=2, ecolor="#666666"))
ax.bar(x + w/2, g5, w, color=arm_cols,
       yerr=ci_err(g5, 10), error_kw=dict(lw=0.9, capsize=2, ecolor="#666666"))
ax.text(4 - w/2, 3, "n/a", ha="center", fontsize=6.8, color="#888888", rotation=90)
ax.set_xticks(x, arm_names); ax.set_ylim(0, 112); ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Strict goal completion (%)")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(fc="#777777", alpha=0.45, label="gpt-4o"),
                   Patch(fc="#777777", label="gpt-5.4")],
          loc="upper left", handlelength=1.1, borderaxespad=0.1)
ax.set_title("Protocol-information ladder\n(finance, n=10/arm, 95% CI)")
panel_label(ax, "(a)")

# (b) S4 disasters by model for A vs typed arms
ax = axes[1]
labels = ["gpt-4o", "gpt-5.4"]
a_dis = [4, 22]; typed = [0, 0]
xb = np.arange(2)
ax.bar(xb - 0.2, a_dis, 0.38, color=ARM["A"], label="A (intent only)")
ax.bar(xb + 0.2, typed, 0.38, color=ARM["Cp"], label="all typed arms")
for i, v in enumerate(a_dis): ax.text(i - 0.2, v + 0.5, str(v), ha="center", fontsize=8, fontweight="bold", color=ARM["A"])
for i in range(2): ax.text(i + 0.2, 0.5, "0", ha="center", fontsize=8, fontweight="bold", color=ARM["Cp"])
ax.set_xticks(xb, labels); ax.set_ylim(0, 26)
ax.set_ylabel("S4: irreversible act before\nauthorization (per 30 attempts)")
ax.legend(loc="upper left")
ax.set_title("Capability amplifies the gap\n(finance, n=10/arm)")
panel_label(ax, "(b)")

# (c) tokens per delivered goal (grand run)
ax = axes[2]
tps = [None, 24.4, 96.8, 44.7, 79.5]
ax.bar(x, [v or 0 for v in tps], 0.55, color=arm_cols)
ax.text(0, 4, "\u221e", ha="center", fontsize=13, color=ARM["A"], fontweight="bold")
for i, v in enumerate(tps):
    if v: ax.text(i, v + 2.5, f"{v:g}", ha="center", fontsize=7.6)
ax.set_xticks(x, arm_names); ax.set_ylim(0, 112)
ax.set_ylabel("Tokens per delivered goal (k)")
ax.set_title("Cost of success (gpt-5.4, n=10):\nguarantees cost \u22483\u00d7 over B \u2026")
panel_label(ax, "(c)")

# (d) scheduler ablation — horizontal bars, calls annotated
ax = axes[3]
names = ["B  global text", "lean + gate", "full STJP\n(+ scheduler)"]
tok = [120, 38, 13.3]; calls = [41.8, 34.0, 11.4]
cols = [ARM["B"], ARM["Cp"], ARM["Cp"]]
yb = np.arange(3)[::-1]
bars = ax.barh(yb, tok, 0.55, color=cols)
bars[2].set_edgecolor("#00543F"); bars[2].set_linewidth(1.4)
for yi, t, c in zip(yb, tok, calls):
    ax.text(t + 2.5, yi, f"{t:g}k \u00b7 {c:g} calls", va="center", fontsize=7.4)
ax.set_yticks(yb, names, fontsize=7.6)
ax.set_xlim(0, 165); ax.set_xlabel("Tokens per delivered goal (k)")
ax.grid(axis="x", color="#DDDDDD", lw=0.6); ax.grid(axis="y", visible=False)
ax.set_title("\u2026 the scheduler wins it back: 9\u00d7\n(same runtime; all 100% GCR, 0 disasters)")
panel_label(ax, "(d)")

plt.tight_layout(w_pad=1.6)
plt.savefig("fig2_results.png", dpi=260); plt.savefig("fig2_results.pdf"); plt.close()

# =========================================================
# Figure 3 — validation suite: E1/E2/E3/E6 ALL MEASURED
# =========================================================
fig, axes = plt.subplots(1, 4, figsize=(11.6, 2.85))

# (a) E1 mutation testing — measured + adjudicated
ax = axes[0]
cls = ["undeclared\nrole", "flipped\nchoice subj.", "branch\nasymmetry", "GROUP:\nwell-formed.", "reorderings\n(correct accept)"]
det = [100.0, 100.0, 82.5, 95.1, 0.8]
ns  = [100, 63, 63, 226, 400]
cols = [OI["blue"], OI["blue"], OI["blue"], "#00304F", "#BBBBBB"]
xb = np.arange(5)
err = np.zeros((2, 5))
for i2, (p, n) in enumerate(zip(det, ns)):
    e = ci_err([p], n); err[0, i2], err[1, i2] = e[0, 0], e[1, 0]
ax.bar(xb, det, 0.6, color=cols, yerr=err, error_kw=dict(lw=0.8, capsize=1.6, ecolor="#666666"))
ax.bar([2], [92.9 - 82.5], 0.6, bottom=[82.5], color=OI["blue"], alpha=0.35, hatch="///", edgecolor="white")
ax.annotate("92.9 after adjudication\n(7/11 survivors were valid)", xy=(2, 92.9), xytext=(0.35, 62),
            fontsize=5.8, color="#333333", arrowprops=dict(arrowstyle="->", lw=0.7, color="#555555"))
for i2, (v, n) in enumerate(zip(det, ns)):
    ax.text(i2, (v if i2 != 2 else 92.9) + 3.0, f"{v:g}", ha="center", fontsize=6.4)
    ax.text(i2, -14, f"n={n}", ha="center", fontsize=5.6, color="#777777")
ax.axvline(3.5, color="#CCCCCC", lw=0.8, ls=":")
ax.text(2.1, 111, "false positives on valid corpus: 0/100", fontsize=6.2, color=ARM["A"], ha="center")
ax.set_xticks(xb, cls, fontsize=5.8); ax.set_ylim(0, 118); ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Flagged by validator (%)")
ax.set_title("E1 Checker: mutation testing\n(100-protocol corpus, measured)")
panel_label(ax, "(a)")

# (b) E2 adversarial — measured four-condition layering
ax = axes[1]
sysn = ["no\nguard", "keyword\nrules", "structural\ngate", "gate +\nrefinement"]
blocked = [0.0, 41.7, 91.7, 100.0]
cols = ["#BBBBBB", OI["pink"], OI["sky"], ARM["Cp"]]
xb = np.arange(4)
ax.bar(xb, blocked, 0.6, color=cols, yerr=ci_err(blocked, 1200), error_kw=dict(lw=0.8, capsize=1.6, ecolor="#666666"))
for i2, v in enumerate(blocked): ax.text(i2, v + 3, f"{v:g}", ha="center", fontsize=6.8)
ax.annotate("7 template classes evade\n(encoding, synonym, split)", xy=(1, 44), xytext=(0.6, 72),
            fontsize=5.8, color="#555555", arrowprops=dict(arrowstyle="->", lw=0.7, color="#555555"))
ax.annotate("1 template: payload smuggled\nover a legal route", xy=(2, 93), xytext=(1.15, 108),
            fontsize=5.8, color="#555555", arrowprops=dict(arrowstyle="->", lw=0.7, color="#555555"))
ax.set_xticks(xb, sysn, fontsize=6.6); ax.set_ylim(0, 122); ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Exfiltration blocked (%)")
ax.set_title("E2 Gate: injected exfiltration\n(12 templates \u00d7 100, measured)")
panel_label(ax, "(b)")

# (c) E3 capability sweep — MEASURED, Claude tier ladder, revenue_audit
ax = axes[2]
tiers = ["haiku\n(weak, n=100)", "sonnet\n(mid, n=30)", "opus\n(strong, n=10)"]
xs = np.arange(3)
cgc_A = [2, 100, 100]
cgc_B = [5, 100, 100]
cgc_G = [100, 100, 100]
ax.plot(xs, cgc_A, "-o", color=ARM["A"], lw=1.4, ms=4, label="A: intent only")
ax.plot(xs, cgc_B, "-s", color=ARM["B"], lw=1.4, ms=4, label="B: global text")
ax.plot(xs, cgc_G, "-D", color=ARM["Cp"], lw=1.8, ms=4, label="C+min: local + gate")
ax.annotate("95 premature\nfilings / 100", xy=(0, 5), xytext=(0.42, 34),
            fontsize=6.0, color=ARM["A"], fontweight="bold",
            arrowprops=dict(arrowstyle="->", lw=0.8, color=ARM["A"]))
ax.text(1.0, 106.5, "gate: 0 disasters at every tier", fontsize=6.0, color=ARM["Cp"], ha="center")
ax.set_xticks(xs, tiers, fontsize=6.2)
ax.set_ylim(0, 118); ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Clean-goal completion (%)")
ax.legend(loc="center right", fontsize=6.2)
ax.set_title("E3 Sweep (measured): unenforced\nsafety is capability-dependent")
panel_label(ax, "(c)")

# (d) E6 roles sweep — measured structural cost proxy
ax = axes[3]
roles = [2, 5, 10]
b_cost = [1376, 4550, 12820]
s_cost = [150, 375, 750]
ax.plot(roles, b_cost, "-o", color=ARM["B"], lw=1.4, ms=4, label="B: protocol as text")
ax.plot(roles, s_cost, "-s", color=ARM["Cp"], lw=1.4, ms=4, label="full STJP")
for r, b, st, ratio in zip(roles, b_cost, s_cost, ["9.2\u00d7", "12.1\u00d7", "17.1\u00d7"]):
    ax.annotate(ratio, xy=(r, (b*st)**0.5), fontsize=6.6, ha="center", color="#333333",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#CCCCCC", lw=0.5))
ax.set_yscale("log"); ax.set_ylim(90, 30000)
ax.set_xticks(roles)
ax.set_xlabel("Number of roles"); ax.set_ylabel("Coordination cost proxy (log)")
ax.legend(loc="upper left", fontsize=6.6)
ax.set_title("E6 Scaling (measured proxy):\ngap widens 9.2\u00d7\u219217.1\u00d7")
panel_label(ax, "(d)")

plt.tight_layout(w_pad=1.7)
plt.savefig("fig3_projected.png", dpi=260); plt.savefig("fig3_projected.pdf"); plt.close()

# =========================================================
# Figure 4 — six-arm ladder at n=100 (FINAL post-audit numbers)
# =========================================================
fig, axes = plt.subplots(1, 2, figsize=(11.6, 3.0))
arms6 = ["A\nintent", "B\nglobal text", "C-min\nobserve", "C+spec\ngate", "C+min\ngate", "STJP\n+sched"]
cols6 = [ARM["A"], ARM["B"], ARM["C"], OI["pink"], ARM["Cmin"], ARM["Cp"]]

data = {
    "revenue_audit  (3 roles; safety axis)": dict(
        gcr=[100, 100, 32, 98, 100, 100], cgc=[2, 5, 2, 98, 100, 100],
        dis=[0, 95, 0, 0, 0, 0], calls=[9.0, 3.3, 23.3, 9.1, 9.0, 3.0]),
    "escrow_trade  (4 roles; cost axis)": dict(
        gcr=[83, 82, 100, 97, 83, 98], cgc=[70, 73, 75, 97, 83, 98],
        dis=[26, 35, 49, 0, 0, 0], calls=[27.8, 28.8, 27.1, 28.0, 24.7, 7.0]),
}
for ax, (name, d), pl in zip(axes, data.items(), ["(a)", "(b)"]):
    xb = np.arange(6); w = 0.4
    ax.bar(xb - w/2, d["gcr"], w, color=cols6, alpha=0.32)
    ax.bar(xb + w/2, d["cgc"], w, color=cols6,
           yerr=ci_err(d["cgc"], 100), error_kw=dict(lw=0.8, capsize=1.6, ecolor="#666666"))
    for i2, (dv, cv) in enumerate(zip(d["dis"], d["calls"])):
        if dv > 0:
            ax.text(i2 - w/2, d["gcr"][i2] + 8, f"{dv}\u26a0", ha="center", fontsize=7.0,
                    color=ARM["A"], fontweight="bold")
        ax.text(i2, -21, f"{cv:g}", ha="center", fontsize=6.2, color="#555555")
    ax.text(-0.9, -21, "calls:", ha="right", fontsize=6.2, color="#555555")
    ax.set_xticks(xb, arms6, fontsize=6.6)
    ax.set_ylim(0, 118); ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("% of 100 trials")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(fc="#777777", alpha=0.32, label="GCR: goal reached"),
                       Patch(fc="#777777", label="CGC: goal + zero violations"),
                       Patch(fc="none", ec="none", label="\u26a0 = disasters (count)")],
              loc="upper left" if "escrow" in name else "center left", fontsize=6.2)
    ax.set_title(name)
    panel_label(ax, pl)

plt.tight_layout(w_pad=2.0)
plt.savefig("fig4_ladder.png", dpi=260); plt.savefig("fig4_ladder.pdf"); plt.close()
print("figs v5 done")
