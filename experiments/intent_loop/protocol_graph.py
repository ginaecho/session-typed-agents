"""protocol_graph.py — read a drafted global protocol and draw it.

Three views of the same protocol, because "who talks to whom" and "in what
order, and when NOT" are different questions:

  role graph   roles as nodes, messages as directed edges. Answers "who
               talks to whom at all" — the shape of the team.
  sequence     lifelines per role, ordered arrows top to bottom, with
               choice branches and recursion drawn as bands. Answers
               "in what order, and what is conditional" — this is the
               view that shows when something must NOT happen yet.
  role FSM     one role's own automaton: the sends and receives it is
               obliged to perform, in order, with branch points. Answers
               "what is THIS agent's contract" — the projection idea, by
               hand rather than through Scribble.

PARSING POLICY, and why this file exists at all. `stjp_core/compiler/
scribble_grammar.lark` is deliberately TIGHT — single-sort payloads, no
labelled choice branches — because it drives grammar-constrained decoding
at training time. Real model drafts routinely exceed it (`M(int,string)`,
`choice at R { LabelA { ... } or { ... } }`), and the real Scribble
validator would reject some of them too.

So this reader is TOLERANT ON PURPOSE, and that tolerance is confined to
drawing. It never decides whether a protocol is valid; `validity.validate`
(real scribble-java) remains the only authority on that. A picture of a
rejected draft is exactly what you want when you are trying to see WHY it
was rejected — refusing to draw it would hide the evidence.

Anything the reader cannot understand is reported in `ir.unparsed`, never
dropped silently: a diagram that quietly omits a line it failed to read
would be the same class of cheat as a checker that passes because it
looked away.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from typing import Any, Iterator, Optional

# ---------------------------------------------------------------------------
# Intermediate representation
# ---------------------------------------------------------------------------


@dataclass
class Message:
    label: str
    payload: str
    sender: str
    receivers: list[str]        # `L(x) from A to B, C;` is legal Scribble
    line: int
    path: tuple[str, ...] = ()  # enclosing branch/loop labels, outermost first

    @property
    def receiver(self) -> str:
        return self.receivers[0] if self.receivers else "?"


@dataclass
class Choice:
    at: str
    branches: list[tuple[str, list[Any]]]   # (branch label, body)
    line: int


@dataclass
class Recursion:
    name: str
    body: list[Any]
    line: int


@dataclass
class Continue:
    name: str
    line: int


@dataclass
class ProtocolIR:
    name: str = ""
    roles: list[str] = field(default_factory=list)
    body: list[Any] = field(default_factory=list)
    unparsed: list[tuple[int, str]] = field(default_factory=list)

    def messages(self) -> Iterator[Message]:
        yield from _walk_messages(self.body)

    def stats(self) -> dict[str, int]:
        msgs = list(self.messages())
        return {"roles": len(self.roles), "messages": len(msgs),
                "choices": _count(self.body, Choice),
                "loops": _count(self.body, Recursion),
                "branched_messages": sum(1 for m in msgs if m.path),
                "unparsed_lines": len(self.unparsed)}


def _walk_messages(body: list[Any]) -> Iterator[Message]:
    for node in body:
        if isinstance(node, Message):
            yield node
        elif isinstance(node, Choice):
            for _label, sub in node.branches:
                yield from _walk_messages(sub)
        elif isinstance(node, Recursion):
            yield from _walk_messages(node.body)


def _count(body: list[Any], kind: type) -> int:
    n = 0
    for node in body:
        if isinstance(node, kind):
            n += 1
        if isinstance(node, Choice):
            for _l, sub in node.branches:
                n += _count(sub, kind)
        elif isinstance(node, Recursion):
            n += _count(node.body, kind)
    return n


# ---------------------------------------------------------------------------
# Tolerant reader
# ---------------------------------------------------------------------------

_HEADER = re.compile(r"global\s+protocol\s+(\w+)\s*\((.*?)\)\s*\{", re.S)
_ROLE = re.compile(r"(?:role\s+)?(\w+)")
# Multi-sort payloads and multi-receiver sends are accepted here (the tight
# training grammar rejects both) — see the module docstring.
_MESSAGE = re.compile(
    r"^(\w+)\s*\(([^)]*)\)\s*from\s+(\w+)\s+to\s+([\w\s,]+?)\s*;", re.S)
_CHOICE = re.compile(r"^choice\s+at\s+(\w+)\s*\{")
_OR = re.compile(r"^\}\s*or\s*\{")
_REC = re.compile(r"^rec\s+(\w+)\s*\{")
_CONTINUE = re.compile(r"^continue\s+(\w+)\s*;")
_BRANCH_LABEL = re.compile(r"^(\w+)\s*\{")


def parse_protocol(text: str) -> ProtocolIR:
    """Read a .scr global protocol into the IR. Never raises on malformed
    input — unreadable lines land in `ir.unparsed` so the caller can show
    them next to the diagram."""
    ir = ProtocolIR()
    # Strip comments but keep line numbers so `unparsed` points at the file.
    lines = [re.sub(r"//.*$", "", ln) for ln in text.splitlines()]

    head = _HEADER.search("\n".join(lines))
    if head:
        ir.name = head.group(1)
        ir.roles = [m.group(1) for m in _ROLE.finditer(head.group(2))
                    if m.group(1) != "role"]
        start_line = "\n".join(lines)[:head.end()].count("\n")
    else:
        start_line = 0

    # A stack of open containers. Each frame collects nodes into `body`.
    root: list[Any] = []
    stack: list[dict] = [{"kind": "root", "body": root}]
    buf, buf_line = "", 0

    for lineno, raw in enumerate(lines[start_line + 1:], start=start_line + 2):
        stripped = raw.strip()
        if not stripped:
            continue
        buf = (buf + " " + stripped).strip() if buf else stripped
        if buf_line == 0:
            buf_line = lineno

        top = stack[-1]["body"]

        m = _MESSAGE.match(buf)
        if m:
            receivers = [r.strip() for r in m.group(4).split(",") if r.strip()]
            top.append(Message(label=m.group(1), payload=m.group(2).strip(),
                               sender=m.group(3), receivers=receivers,
                               line=buf_line, path=_path_of(stack)))
            buf, buf_line = "", 0
            continue

        m = _CHOICE.match(buf)
        if m:
            node = Choice(at=m.group(1), branches=[], line=buf_line)
            top.append(node)
            stack.append({"kind": "choice", "node": node, "body": [],
                          "label": ""})
            buf, buf_line = "", 0
            continue

        m = _REC.match(buf)
        if m:
            node = Recursion(name=m.group(1), body=[], line=buf_line)
            top.append(node)
            stack.append({"kind": "rec", "node": node, "body": node.body})
            buf, buf_line = "", 0
            continue

        m = _CONTINUE.match(buf)
        if m:
            top.append(Continue(name=m.group(1), line=buf_line))
            buf, buf_line = "", 0
            continue

        if _OR.match(buf):
            frame = stack[-1]
            if frame["kind"] == "choice":
                frame["node"].branches.append((frame.get("label", ""),
                                               frame["body"]))
                frame["body"] = []
                frame["label"] = ""
            buf, buf_line = "", 0
            continue

        # A labelled branch head: `FixC1 {` inside a choice (not in the
        # tight grammar; models emit it constantly).
        m = _BRANCH_LABEL.match(buf)
        if m and stack[-1]["kind"] == "choice" and not stack[-1]["body"]:
            stack[-1]["label"] = m.group(1)
            buf, buf_line = "", 0
            continue

        if stripped.startswith("}"):
            frame = stack[-1]
            if frame["kind"] == "choice":
                frame["node"].branches.append((frame.get("label", ""),
                                               frame["body"]))
                stack.pop()
            elif frame["kind"] == "rec":
                stack.pop()
            buf, buf_line = "", 0
            continue

        # Not recognised yet — it may be the first half of a wrapped
        # statement, so only report it once it cannot continue.
        if buf.endswith(";") or buf.endswith("}"):
            ir.unparsed.append((buf_line, buf))
            buf, buf_line = "", 0

    if buf:
        ir.unparsed.append((buf_line, buf))

    ir.body = root
    if not ir.roles:   # header missing or unreadable: recover from messages
        seen: list[str] = []
        for msg in _walk_messages(root):
            for r in [msg.sender, *msg.receivers]:
                if r not in seen:
                    seen.append(r)
        ir.roles = seen
    return ir


def _path_of(stack: list[dict]) -> tuple[str, ...]:
    out = []
    for frame in stack:
        if frame["kind"] == "choice":
            out.append(f"choice@{frame['node'].at}"
                       + (f":{frame['label']}" if frame.get("label") else ""))
        elif frame["kind"] == "rec":
            out.append(f"loop:{frame['node'].name}")
    return tuple(out)


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------

def role_edges(ir: ProtocolIR) -> list[dict]:
    """Aggregated directed edges between roles."""
    edges: dict[tuple[str, str], dict] = {}
    for msg in ir.messages():
        for rcv in msg.receivers:
            key = (msg.sender, rcv)
            e = edges.setdefault(key, {"from": msg.sender, "to": rcv,
                                       "labels": [], "conditional": False,
                                       "count": 0})
            if msg.label not in e["labels"]:
                e["labels"].append(msg.label)
            e["count"] += 1
            if any(p.startswith("choice@") for p in msg.path):
                e["conditional"] = True
    return list(edges.values())


def role_fsm(ir: ProtocolIR, role: str) -> list[dict]:
    """This role's obligations in order: what it sends, what it waits for.

    Messages involving neither side are omitted — that omission IS the
    projection idea (a role's contract mentions only its own boundary),
    and the count of skipped messages is returned so it is never silent.
    """
    steps: list[dict] = []
    skipped = 0
    for msg in ir.messages():
        if msg.sender == role:
            steps.append({"dir": "send", "label": msg.label,
                          "peer": ", ".join(msg.receivers),
                          "payload": msg.payload, "path": list(msg.path)})
        elif role in msg.receivers:
            steps.append({"dir": "receive", "label": msg.label,
                          "peer": msg.sender, "payload": msg.payload,
                          "path": list(msg.path)})
        else:
            skipped += 1
    if steps:
        steps[0]["skipped_elsewhere"] = skipped
    return steps


# ---------------------------------------------------------------------------
# SVG rendering (server-side; works with JavaScript disabled)
# ---------------------------------------------------------------------------

_PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
            "#4a3aa7", "#e34948"]
_INK = "#0b0b0b"
_MUTED = "#898781"
_LINE = "#c3c2b7"


def _color(i: int) -> str:
    return _PALETTE[i % len(_PALETTE)]


def _svg_open(w: int, h: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="100%" height="{h}" role="img" aria-label="{escape(title)}" '
        f'style="max-width:{w}px;font:12px system-ui,-apple-system,'
        f'\'Segoe UI\',sans-serif">',
        '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{_MUTED}"/></marker></defs>',
    ]


def render_role_graph(ir: ProtocolIR, width: int = 720) -> str:
    """Roles on a circle, message flow as directed edges."""
    roles = ir.roles
    if not roles:
        return "<p>No roles found.</p>"
    import math
    h = max(360, 90 * len(roles))
    cx, cy = width / 2, h / 2
    r = min(cx, cy) - 96
    pos = {}
    for i, role in enumerate(roles):
        a = -math.pi / 2 + 2 * math.pi * i / len(roles)
        pos[role] = (cx + r * math.cos(a), cy + r * math.sin(a))

    out = _svg_open(width, h, f"Role interaction graph for {ir.name}")
    for e in role_edges(ir):
        if e["from"] not in pos or e["to"] not in pos:
            continue
        x1, y1 = pos[e["from"]]
        x2, y2 = pos[e["to"]]
        if e["from"] == e["to"]:
            out.append(f'<circle cx="{x1:.0f}" cy="{y1 - 46:.0f}" r="16" '
                       f'fill="none" stroke="{_LINE}"/>')
            continue
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # Bow the edge away from the centre so A->B and B->A stay distinct.
        ox, oy = (my - cy) * 0.18, (cx - mx) * 0.18
        qx, qy = mx + ox, my + oy
        dash = ' stroke-dasharray="5,4"' if e["conditional"] else ""
        out.append(f'<path d="M{x1:.0f},{y1:.0f} Q{qx:.0f},{qy:.0f} '
                   f'{x2:.0f},{y2:.0f}" fill="none" stroke="{_LINE}" '
                   f'stroke-width="1.6"{dash} marker-end="url(#ar)"/>')
        labels = e["labels"][:2]
        extra = len(e["labels"]) - len(labels)
        text = ", ".join(labels) + (f" +{extra}" if extra > 0 else "")
        out.append(f'<text x="{qx:.0f}" y="{qy:.0f}" fill="{_MUTED}" '
                   f'text-anchor="middle" font-size="11">{escape(text)}</text>')

    for i, role in enumerate(roles):
        x, y = pos[role]
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="30" '
                   f'fill="{_color(i)}" opacity="0.16" '
                   f'stroke="{_color(i)}" stroke-width="2"/>')
        out.append(f'<text x="{x:.0f}" y="{y + 46:.0f}" text-anchor="middle" '
                   f'fill="{_INK}" font-weight="600">{escape(role)}</text>')
    out.append("</svg>")
    return "".join(out)


def render_sequence(ir: ProtocolIR, width: int = 900,
                    max_steps: int = 70) -> str:
    """Lifelines and ordered arrows — the 'when, and when not yet' view."""
    roles = ir.roles
    if not roles:
        return "<p>No roles found.</p>"
    colw = max(150, min(230, (width - 80) // max(1, len(roles))))
    width = 60 + colw * len(roles)
    x_of = {r: 40 + colw * i + colw / 2 for i, r in enumerate(roles)}

    rows: list[dict] = []
    truncated = [False]

    def walk(body: list[Any], depth: int) -> None:
        for node in body:
            if truncated[0]:
                return
            if len(rows) >= max_steps:
                truncated[0] = True
                return
            if isinstance(node, Message):
                rows.append({"t": "msg", "m": node, "d": depth})
            elif isinstance(node, Choice):
                for bi, (label, sub) in enumerate(node.branches):
                    rows.append({"t": "band", "d": depth,
                                 "text": (f"choice at {node.at}" if bi == 0
                                          else "or")
                                 + (f" — {label}" if label else "")})
                    walk(sub, depth + 1)
            elif isinstance(node, Recursion):
                rows.append({"t": "band", "d": depth,
                             "text": f"loop {node.name}"})
                walk(node.body, depth + 1)
            elif isinstance(node, Continue):
                rows.append({"t": "band", "d": depth,
                             "text": f"↺ continue {node.name}"})

    walk(ir.body, 0)

    top, step = 64, 34
    h = top + step * (len(rows) + 1) + 30
    out = _svg_open(width, h, f"Sequence view of {ir.name}")
    for i, role in enumerate(roles):
        x = x_of[role]
        out.append(f'<rect x="{x - colw / 2 + 8:.0f}" y="16" '
                   f'width="{colw - 16:.0f}" height="30" rx="7" '
                   f'fill="{_color(i)}" opacity="0.14" stroke="{_color(i)}"/>')
        out.append(f'<text x="{x:.0f}" y="36" text-anchor="middle" '
                   f'fill="{_INK}" font-weight="600">{escape(role)}</text>')
        out.append(f'<line x1="{x:.0f}" y1="48" x2="{x:.0f}" y2="{h - 20}" '
                   f'stroke="{_LINE}" stroke-dasharray="3,4"/>')

    y = top
    for row in rows:
        y += step
        if row["t"] == "band":
            out.append(f'<rect x="20" y="{y - 15:.0f}" width="{width - 40}" '
                       f'height="21" rx="5" fill="{_MUTED}" opacity="0.10"/>')
            out.append(f'<text x="{28 + row["d"] * 12}" y="{y:.0f}" '
                       f'fill="{_MUTED}" font-size="11" '
                       f'font-weight="600">{escape(row["text"])}</text>')
            continue
        m: Message = row["m"]
        x1 = x_of.get(m.sender)
        for rcv in m.receivers:
            x2 = x_of.get(rcv)
            if x1 is None or x2 is None:
                continue
            dash = ' stroke-dasharray="5,4"' if m.path else ""
            out.append(f'<line x1="{x1:.0f}" y1="{y:.0f}" x2="{x2:.0f}" '
                       f'y2="{y:.0f}" stroke="{_MUTED}" stroke-width="1.6"'
                       f'{dash} marker-end="url(#ar)"/>')
            label = m.label + (f"({m.payload})" if m.payload else "")
            out.append(f'<text x="{(x1 + x2) / 2:.0f}" y="{y - 6:.0f}" '
                       f'text-anchor="middle" fill="{_INK}" font-size="11">'
                       f'{escape(label)}</text>')
    if truncated[0]:
        out.append(f'<text x="24" y="{h - 8}" fill="{_MUTED}" font-size="11">'
                   f'… truncated at {max_steps} steps — the protocol '
                   f'continues.</text>')
    out.append("</svg>")
    return "".join(out)


def render_role_fsm(ir: ProtocolIR, role: str, width: int = 900) -> str:
    """One role's own automaton: its sends, its waits, in order."""
    steps = role_fsm(ir, role)
    if not steps:
        return f"<p>{escape(role)} sends and receives nothing.</p>"
    per_row = max(1, (width - 60) // 210)
    rows = (len(steps) + per_row - 1) // per_row
    h = 60 + rows * 104
    out = _svg_open(width, h, f"State machine for {role}")
    x0, y0 = 40, 52

    def state_xy(i: int) -> tuple[float, float]:
        return x0 + (i % per_row) * 210, y0 + (i // per_row) * 104

    for i in range(len(steps) + 1):
        x, y = state_xy(i)
        final = i == len(steps)
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="17" '
                   f'fill="{"#1baf7a" if final else "#2a78d6"}" '
                   f'opacity="0.16" stroke="{"#1baf7a" if final else "#2a78d6"}"'
                   f' stroke-width="2"/>')
        out.append(f'<text x="{x:.0f}" y="{y + 4:.0f}" text-anchor="middle" '
                   f'fill="{_INK}" font-size="11" font-weight="600">'
                   f'{"end" if final else i}</text>')

    for i, st in enumerate(steps):
        x1, y1 = state_xy(i)
        x2, y2 = state_xy(i + 1)
        arrow = "!" if st["dir"] == "send" else "?"
        text = f'{arrow}{st["label"]} {"to" if arrow == "!" else "from"} {st["peer"]}'
        cond = any(p.startswith("choice@") for p in st["path"])
        dash = ' stroke-dasharray="5,4"' if cond else ""
        if y1 == y2:
            out.append(f'<line x1="{x1 + 19:.0f}" y1="{y1:.0f}" '
                       f'x2="{x2 - 19:.0f}" y2="{y2:.0f}" stroke="{_MUTED}" '
                       f'stroke-width="1.6"{dash} marker-end="url(#ar)"/>')
            out.append(f'<text x="{(x1 + x2) / 2:.0f}" y="{y1 - 12:.0f}" '
                       f'text-anchor="middle" fill="{_INK}" font-size="11">'
                       f'{escape(text)}</text>')
        else:   # wrap to the next row
            out.append(f'<path d="M{x1:.0f},{y1 + 19:.0f} L{x1:.0f},'
                       f'{y1 + 44:.0f} L{x2:.0f},{y2 - 44:.0f} L{x2:.0f},'
                       f'{y2 - 19:.0f}" fill="none" stroke="{_MUTED}"'
                       f'{dash} marker-end="url(#ar)"/>')
            out.append(f'<text x="{x1 + 24:.0f}" y="{y1 + 40:.0f}" '
                       f'fill="{_INK}" font-size="11">{escape(text)}</text>')
    out.append("</svg>")
    return "".join(out)


def intent_graph_payload(distilled: dict) -> dict[str, Any]:
    """The INTENDED interaction graph, from the distilled checklist alone.

    Available as soon as interrogation ends — before a single line of
    protocol exists. That ordering matters: the reviewer gets to see, and
    argue with, the intended shape of the conversation while it is still
    cheap to change, instead of reverse-engineering it from a protocol
    afterwards.

    It also gives the drafted protocol something to be compared against:
    a message matching no declared interaction is visibly invented.
    """
    roles = [str(r.get("name", "")) for r in distilled.get("roles", [])
             if r.get("name")]
    edges: dict[tuple[str, str], dict] = {}
    for ix in distilled.get("interactions", []):
        s = str(ix.get("sender") or ix.get("from") or "")
        t = str(ix.get("receiver") or ix.get("to") or "")
        if not s or not t:
            continue
        for r in (s, t):
            if r not in roles:
                roles.append(r)      # declared in an interaction, not listed
        e = edges.setdefault((s, t), {"from": s, "to": t, "labels": [],
                                      "conditional": False, "count": 0})
        what = str(ix.get("what", "")).strip() or str(ix.get("iid", ""))
        if what not in e["labels"]:
            e["labels"].append(what)
        e["count"] += 1
        if ix.get("optional"):
            e["conditional"] = True

    ir = ProtocolIR(name="intended", roles=roles)
    # Synthesise messages so the shared renderers can draw this too.
    ir.body = [Message(label=(str(ix.get("what", ""))[:28] or "…"),
                       payload="", sender=str(ix.get("sender") or ix.get("from") or ""),
                       receivers=[str(ix.get("receiver") or ix.get("to") or "")],
                       line=0, path=("optional",) if ix.get("optional") else ())
               for ix in distilled.get("interactions", [])
               if (ix.get("sender") or ix.get("from"))
               and (ix.get("receiver") or ix.get("to"))]
    return {"roles": roles, "edges": list(edges.values()),
            "stats": {"roles": len(roles),
                      "interactions": len(ir.body),
                      "optional": sum(1 for m in ir.body if m.path)},
            "svg": {"roles": render_role_graph(ir),
                    "sequence": render_sequence(ir)}}


def graph_payload(protocol_text: str) -> dict[str, Any]:
    """Everything the UI and the report need for one protocol."""
    ir = parse_protocol(protocol_text)
    return {
        "name": ir.name, "roles": ir.roles, "stats": ir.stats(),
        "edges": role_edges(ir),
        "unparsed": [{"line": n, "text": t} for n, t in ir.unparsed],
        "svg": {
            "roles": render_role_graph(ir),
            "sequence": render_sequence(ir),
            "fsm": {r: render_role_fsm(ir, r) for r in ir.roles},
        },
        "fsm_steps": {r: role_fsm(ir, r) for r in ir.roles},
    }
