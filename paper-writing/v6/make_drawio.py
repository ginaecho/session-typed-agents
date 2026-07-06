#!/usr/bin/env python3
"""Generate STJP_system_figure.drawio — editable draw.io source for paper Figure 1."""
import html
import xml.etree.ElementTree as ET

cells = []
_id = [1]
def nid():
    _id[0] += 1
    return f"c{_id[0]}"

INK = "#3A3A3A"; EDGE = "#9AA3AD"
FILL_N = "#F6F7F9"; FILL_C = "#EAF1F8"; FILL_V = "#EAF5EF"; FILL_R = "#FBF0EC"
GREEN = "#4E9B6F"; RED = "#D55E00"; GREY = "#8A939C"

def esc(s):  # HTML label, XML-escaped
    return html.escape(s, quote=True)

def box(x, y, w, h, title, sub="", fill=FILL_N, stroke=EDGE):
    i = nid()
    lbl = f"<b>{title}</b>" + (f"<br><font style='font-size:9px;color:#555555'>{sub}</font>" if sub else "")
    cells.append(dict(kind="v", id=i, value=lbl,
        style=f"rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor={fill};strokeColor={stroke};"
              f"fontColor={INK};fontSize=11;verticalAlign=middle;spacing=4;",
        x=x, y=y, w=w, h=h))
    return i

def badge(x, y, s):
    i = nid()
    cells.append(dict(kind="v", id=i, value=f"<b>{s}</b>",
        style=f"ellipse;html=1;fillColor={INK};strokeColor=none;fontColor=#FFFFFF;fontSize=9;",
        x=x, y=y, w=26, h=26))
    return i

def label(x, y, w, text, size=11, color="#5A6570", bold=True, italic=False):
    i = nid()
    st = f"text;html=1;fontSize={size};fontColor={color};align=left;verticalAlign=middle;"
    if bold: st += "fontStyle=1;"
    if italic: st += "fontStyle=2;"
    cells.append(dict(kind="v", id=i, value=text, style=st, x=x, y=y, w=w, h=22))
    return i

def edge(src, dst, color=INK, dashed=False, lbl="", style_extra="", exitp=None, entryp=None, points=None):
    i = nid()
    st = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor={color};strokeWidth=1.5;"
          f"endArrow=blockThin;endFill=1;fontSize=9;fontColor={color};fontStyle=2;{style_extra}")
    if dashed: st += "dashed=1;dashPattern=6 4;"
    if exitp: st += f"exitX={exitp[0]};exitY={exitp[1]};exitDx=0;exitDy=0;"
    if entryp: st += f"entryX={entryp[0]};entryY={entryp[1]};entryDx=0;entryDy=0;"
    cells.append(dict(kind="e", id=i, value=lbl, style=st, src=src, dst=dst, points=points))
    return i

def sepline(y, w=1560):
    i = nid()
    cells.append(dict(kind="v", id=i, value="",
        style=f"line;html=1;strokeColor=#C9CED4;dashed=1;dashPattern=2 4;strokeWidth=1;",
        x=20, y=y, w=w, h=8))
    return i

# ---------- lane headers ----------
label(30, 20, 220, "COMPILE TIME", 12)
label(180, 20, 420, "static — runs before any agent exists", 10, GREY, bold=False, italic=True)
label(30, 322, 160, "RUN TIME", 12)
label(130, 322, 620, "deterministic code, not agents — O(1) per message, zero tokens", 10, GREY, bold=False, italic=True)
label(30, 560, 200, "MEASUREMENT", 12)
label(180, 560, 320, "offline, bit-reproducible", 10, GREY, bold=False, italic=True)
sepline(310); sepline(548)

# ---------- compile row ----------
Y1 = 90; H1 = 100
b_int  = box(30,  Y1, 170, H1, "User intent", "natural language<br>task + policies", FILL_N)
b_llm  = box(250, Y1, 175, H1, "LLM drafter", "intent → protocol<br>(+ guard sidecar)", FILL_C)
b_scr  = box(475, Y1, 185, H1, "Global type G", "Scribble .scr + .refn guards<br>+ goal markers", FILL_C)
b_val  = box(710, Y1, 200, H1, "Static validator", "projectability · deadlock<br>guarded recursion<br>goal reachability", FILL_V, GREEN)
b_proj = box(960, Y1, 190, H1, "Projection G↾Rᵢ", "one local type per role<br>→ EFSM", FILL_V, GREEN)
b_art  = box(1400, Y1, 150, H1, "3 artifacts per role", "", FILL_V, GREEN)
badge(238, Y1 - 14, "S1"); badge(698, Y1 - 14, "S2"); badge(948, Y1 - 14, "S3")

edge(b_int, b_llm); edge(b_llm, b_scr, lbl="draft"); edge(b_scr, b_val)
edge(b_val, b_proj, lbl="VALID"); edge(b_proj, b_art)
# reject loop over the top
edge(b_val, b_llm, color=RED, dashed=True,
     lbl="REJECTED + counterexample → re-draft&nbsp;&nbsp;(human endorses the final G)",
     exitp=(0.5, 0), entryp=(0.5, 0),
     points=[(810, 48), (338, 48)])

# ---------- runtime row ----------
Y2 = 380; H2 = 105
b_ag   = box(30,  Y2, 220, H2, "LLM agents", "receive lean local skill<br>(SEND/RECV table + guards);<br>untyped 'dyn' participants", FILL_N)
b_gate = box(360, Y2, 245, H2, "Monitor + Gate (generated)", "EFSM interpreter per role;<br>off-contract send rejected<br>pre-delivery → re-prompt", FILL_R, "#C2836B")
b_schd = box(715, Y2, 240, H2, "EFSM scheduler", "prompts only roles enabled at<br>the current protocol state;<br>no idle polling", FILL_R, "#C2836B")
b_log  = box(1310, Y2, 240, H2, "Typed event log", "role · state · branch · verdict<br>· guard result · goal marker", FILL_C)
badge(348, Y2 - 14, "S4"); badge(703, Y2 - 14, "S5")

# artifact bus: artifacts -> three runtime boxes (green)
edge(b_art, b_ag,   color=GREEN, lbl="skill",    exitp=(0.5, 1), entryp=(0.35, 0), points=[(1475, 250), (107, 250)])
edge(b_art, b_gate, color=GREEN, lbl="monitor",  exitp=(0.5, 1), entryp=(0.5, 0),  points=[(1475, 265), (482, 265)])
edge(b_art, b_schd, color=GREEN, lbl="schedule", exitp=(0.5, 1), entryp=(0.65, 0), points=[(1475, 280), (871, 280)])

edge(b_ag, b_gate, lbl="send m", exitp=(1, 0.35), entryp=(0, 0.35))
edge(b_gate, b_ag, color=RED, lbl="block + re-prompt", exitp=(0, 0.75), entryp=(1, 0.75))
edge(b_gate, b_schd, lbl="allow"); edge(b_schd, b_log, lbl="event")
edge(b_schd, b_ag, color=GREY, dashed=True,
     lbl="turn control: 'you are the enabled sender at this state'",
     exitp=(0.5, 1), entryp=(0.5, 1), points=[(835, 522), (140, 522)])

# ---------- measurement row ----------
Y3 = 610; H3 = 85
b_met = box(230, Y3, 700, H3, "Deterministic metric engine (no golden trajectory, no LLM judge)",
            "conformance rate · path distribution · goal progress · detour cost · repair burden · S0–S4 severity",
            FILL_V, GREEN)
b_anc = box(1080, Y3, 380, H3, "Human outcome anchor (sampled)",
            "divergence ⇒ re-draft G with the user, not patch agents", FILL_N)
edge(b_log, b_met, exitp=(0.3, 1), entryp=(0.8, 0))
edge(b_log, b_anc, exitp=(0.7, 1), entryp=(0.5, 0))

# ---------- serialize ----------
mxfile = ET.Element("mxfile", host="app.diagrams.net", agent="STJP paper toolchain", version="24.7.7")
diagram = ET.SubElement(mxfile, "diagram", name="STJP system (paper Fig. 1)", id="stjp-fig1")
model = ET.SubElement(diagram, "mxGraphModel", dx="1600", dy="900", grid="1", gridSize="10",
                      guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1",
                      pageScale="1", pageWidth="1600", pageHeight="760", math="0", shadow="0")
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")

for c in cells:
    if c["kind"] == "v":
        m = ET.SubElement(root, "mxCell", id=c["id"], value=c["value"], style=c["style"],
                          vertex="1", parent="1")
        ET.SubElement(m, "mxGeometry", x=str(c["x"]), y=str(c["y"]),
                      width=str(c["w"]), height=str(c["h"]), **{"as": "geometry"})
    else:
        m = ET.SubElement(root, "mxCell", id=c["id"], value=c["value"], style=c["style"],
                          edge="1", parent="1", source=c["src"], target=c["dst"])
        g = ET.SubElement(m, "mxGeometry", relative="1", **{"as": "geometry"})
        if c.get("points"):
            arr = ET.SubElement(g, "Array", **{"as": "points"})
            for (px, py) in c["points"]:
                ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))

ET.indent(mxfile, space="  ")
out = ET.tostring(mxfile, encoding="unicode", xml_declaration=False)
open("STJP_system_figure.drawio", "w").write(out)

# validate well-formedness + report
ET.parse("STJP_system_figure.drawio")
nv = sum(1 for c in cells if c["kind"] == "v"); ne = len(cells) - nv
print(f"drawio written: {nv} vertices, {ne} edges, XML valid")
