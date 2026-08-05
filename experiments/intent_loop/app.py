"""app.py — the Flask app: one service for humans, agents, and training.

    python -m experiments.intent_loop web [--port 8765] [--host 127.0.0.1]

then in VS Code: Ctrl+Shift+P -> "Simple Browser: Show" -> the printed URL.

Two audiences, one API. The browser UI at `/` is a thin client over exactly
the endpoints an agent calls — no private routes — so anything a human can
do here, an agent can do headlessly, and vice versa. `GET /api/manifest`
describes every endpoint in machine-readable form so an agent can discover
the surface without reading this file.

    GET  /api/health          readiness: is an LLM configured, is the real
                              Scribble toolchain wired
    GET  /api/manifest        self-describing endpoint catalog (for agents)
    GET  /api/episodes        every recorded episode
    GET  /api/episodes/<s>    one episode in full (Q&A, requirements,
                              attempts, protocol, faithfulness)
    POST /api/runs            start an episode -> {job_id} (async)
    GET  /api/runs            job list
    GET  /api/runs/<id>       job state + the loop's stage events
    GET  /api/corpus          corpus statistics
    POST /api/packs           mine a prompt pack (prompt-level training)
    GET  /api/packs           list packs
    GET  /api/packs/<v>       one pack
    GET  /api/training/stats  how many fine-tuning examples exist, and what
                              was dropped
    POST /api/training/export write train/validation JSONL for a real
                              fine-tune

SECURITY: binds to 127.0.0.1 by default and has NO authentication. It can
start LLM-spending jobs, so do not bind it to a public interface. `--host`
exists for container/devcontainer use; put an authenticating proxy in front
if you ever use it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.intent_loop import loop as loop_mod          # noqa: E402
from experiments.intent_loop import mockdata                  # noqa: E402
from experiments.intent_loop.corpus import (DEFAULT_CORPUS_PATH,  # noqa: E402
                                            read_corpus)
from experiments.intent_loop.export import (build_dataset,     # noqa: E402
                                            write_dataset)
from experiments.intent_loop.jobs import Job, JobRegistry      # noqa: E402
from experiments.intent_loop.llm import Meter, MockChat        # noqa: E402
from experiments.intent_loop.optimize import (PromptPack,      # noqa: E402
                                              build_prompt_pack)

DEFAULT_SESSIONS = HERE / "sessions"
DEFAULT_PACKS = HERE / "packs"
DEFAULT_EXPORTS = HERE / "exports"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ---------------------------------------------------------------------------
# Episode reading
# ---------------------------------------------------------------------------

def load_episodes(sessions_dir: Path) -> list[dict]:
    """Summary row per sessions/<dir>/record.json, newest first. The
    directory name is the key: re-running the same intent yields the same
    episode_id (it is the document's sha), so ids alone would collide."""
    out: list[dict] = []
    if not sessions_dir.is_dir():
        return out
    for d in sorted(sessions_dir.iterdir()):
        if not d.is_dir():
            continue
        rec_path = d / "record.json"
        if rec_path.exists():
            try:
                rec = json.loads(rec_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            complete = True
        else:
            # An UNFINISHED session — killed mid-run, or still going. It has
            # real work on disk (transcript, distilled checklist, drafts)
            # and listing only completed sessions made that work
            # unreachable: the user could not even see what survived.
            partial = load_partial(sessions_dir, d.name)
            if not partial or not (partial.get("distilled")
                                   or partial.get("transcript")):
                continue
            rec = partial
            complete = False
        faith = rec.get("faithfulness") or {}
        dist = rec.get("distilled") or {}
        reqs = dist.get("requirements") or []
        out.append({
            "session": d.name,
            "complete": complete,
            "episode_id": rec.get("episode_id", d.name),
            "ts": rec.get("ts", "") or _mtime_iso(d),
            "valid": bool(rec.get("valid")),
            "faithful": bool(faith.get("faithful")),
            "graded": bool(faith),
            "recall": faith.get("recall"),
            "backtranslation": (faith.get("backtranslation") or {}).get("score"),
            "validator": (rec.get("meter") or {}).get("validator", "?"),
            "attempts": len(rec.get("draft_attempts") or []),
            "qa_rounds": len(rec.get("transcript") or []),
            "requirements": len(reqs),
            "from_answers": sum(1 for r in reqs
                                if r.get("source") == "answer"),
            "intent_chars": rec.get("intent_chars", 0),
        })
    out.sort(key=lambda e: e["ts"], reverse=True)
    return out


def _mtime_iso(path: Path) -> str:
    """A timestamp for an unfinished session, which has no `ts` yet — so the
    list can still sort newest-first instead of dumping it at the bottom."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime,
                                      timezone.utc).isoformat(
                                          timespec="seconds")
    except OSError:
        return ""


def load_partial(sessions_dir: Path, session: str) -> dict | None:
    """Whatever a session has produced SO FAR, mid-run.

    The loop writes each artifact as it is finished — the transcript and
    distilled checklist the moment interrogation ends, each draft as it is
    attempted — so a run that takes minutes has real content on disk long
    before `record.json` appears at the end. Polling this makes a long run
    legible instead of a spinner: the questions show up while the protocol
    is still being drafted.
    """
    d = (sessions_dir / session).resolve()
    if d.parent != sessions_dir.resolve() or not d.is_dir():
        return None
    out: dict[str, Any] = {"session": session, "complete": False}

    rec_path = d / "record.json"
    if rec_path.exists():
        try:
            out.update(json.loads(rec_path.read_text(encoding="utf-8")))
            out["complete"] = True
        except json.JSONDecodeError:
            pass

    if not out["complete"]:
        tr = d / "transcript.json"
        if tr.exists():
            try:
                interro = json.loads(tr.read_text(encoding="utf-8"))
                out["transcript"] = interro.get("transcript", [])
                out["distilled"] = interro.get("distilled", {})
            except json.JSONDecodeError:
                pass
        attempts = []
        drafts = d / "drafts"
        if drafts.is_dir():
            for p in sorted(drafts.glob("attempt_*.scr"),
                            key=lambda q: len(q.name)):
                k = int(p.stem.split("_")[1])
                verdict = drafts / f"attempt_{k}.verdict.txt"
                vtext = _read(verdict)
                attempts.append({
                    "k": k, "text": _read(p),
                    "valid": vtext.startswith("valid: True"),
                    "validator_msg": vtext.split("\n\n", 1)[-1]
                    if "\n\n" in vtext else ""})
        out["draft_attempts"] = attempts
        proto = d / "protocol.scr"
        if proto.exists():
            out["final_protocol"] = _read(proto)
        out["document"] = _read(d / "document.md")

    out["stage_files"] = sorted(p.name for p in d.iterdir() if p.is_file())
    return out


def load_episode(sessions_dir: Path, session: str) -> dict | None:
    d = (sessions_dir / session).resolve()
    if d.parent != sessions_dir.resolve() or not (d / "record.json").exists():
        return None                       # path traversal / unknown session
    rec = json.loads((d / "record.json").read_text(encoding="utf-8"))
    rec["session"] = session
    rec["document"] = _read(d / "document.md")
    for att in rec.get("draft_attempts") or []:
        att["text"] = _read(d / "drafts" / f"attempt_{att.get('k')}.scr")
    return rec


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

def toolchain_status() -> dict:
    """Is the REAL Scribble validator wired into this checkout?"""
    try:
        from experiments.seam_bench.eval.validity import require_toolchain
        require_toolchain()
        return {"available": True, "detail": "scribble-java jars present"}
    except Exception as e:
        return {"available": False, "detail": str(e)[:300]}


def llm_status() -> dict:
    """Is a live LLM configured? From saved settings + environment only —
    probing would cost a real call on every health check."""
    from experiments.intent_loop import settings as settings_mod
    s = settings_mod.load()
    d = s.masked()
    return {"configured": s.is_usable(), "provider": s.provider,
            "deployment": s.model, "endpoint": s.endpoint,
            "auth": d["auth"], "api_key_fingerprint":
                d["api_key_fingerprint"]}


# ---------------------------------------------------------------------------
# Server-rendered report (works with JavaScript disabled)
# ---------------------------------------------------------------------------

_REPORT_CSS = """
:root{color-scheme:light;--s:#fcfcfb;--p:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;
 --mut:#898781;--line:#e1e0d9;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;
 --acc:#2a78d6}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--s:#1a1a19;
 --p:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--line:#2c2c2a;--acc:#3987e5}}
*{box-sizing:border-box}
body{margin:0;padding:22px;background:var(--p);color:var(--ink);
 font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
 max-width:1100px;margin-inline:auto}
h1{font-size:18px;margin:0 0 4px} h2{font-size:12px;text-transform:uppercase;
 letter-spacing:.07em;color:var(--mut);margin:24px 0 8px}
h3{font-size:13px;margin:14px 0 5px}
a{color:var(--acc)} .sub{color:var(--ink2);font-size:13px}
pre{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:var(--s);
 border:1px solid var(--line);border-radius:9px;padding:11px;overflow-x:auto;
 white-space:pre-wrap;word-break:break-word}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:11px;text-transform:uppercase;color:var(--mut);
 padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.b{display:inline-block;font-size:11px;padding:1px 8px;border-radius:999px;
 border:1px solid rgba(128,128,128,.35);color:var(--ink2);white-space:nowrap}
.card{border:1px solid var(--line);border-radius:9px;background:var(--s);
 padding:13px;margin-bottom:10px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:9px}
.tile{border:1px solid var(--line);border-radius:9px;padding:10px 12px;
 background:var(--s)} .tile .v{font-size:21px;font-weight:650}
.tile .k{font-size:11px;color:var(--mut);text-transform:uppercase}
.eps{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.warn{border:1px solid var(--warn);border-radius:9px;padding:9px 12px;
 background:var(--s);margin-bottom:12px}
"""

_COVER_LABEL = {"yes": "covered", "partial": "partial", "no": "missing",
                "out_of_scope": "policy — not gradable"}


def render_report(sessions_dir: Path, session: str | None) -> str:
    from html import escape as e

    eps = load_episodes(sessions_dir)
    head = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>STJP Intent Loop — report</title>"
            f"<style>{_REPORT_CSS}</style></head><body>")
    out = [head, "<h1>STJP Intent Loop</h1>",
           "<div class='sub'>Server-rendered view (no JavaScript). "
           "The interactive app is at <a href='/'>/</a>.</div>"]

    if not eps:
        out.append("<div class='card'>No episodes recorded yet.</div>")
        return "".join(out) + "</body></html>"

    out.append("<h2>Episodes</h2><div class='eps'>")
    for x in eps:
        mark = "▸ " if x["session"] == session else ""
        out.append(
            f"<a class='b' href='/report?session={e(x['session'])}'>{mark}"
            f"{e(x['session'])} · {'valid' if x['valid'] else 'invalid'}"
            f" · {'faithful' if x['faithful'] else 'not faithful'}</a>")
    out.append("</div>")

    chosen = session or eps[0]["session"]
    ep = load_episode(sessions_dir, chosen)
    if ep is None:
        out.append(f"<div class='card'>No such episode: {e(chosen)}</div>")
        return "".join(out) + "</body></html>"

    d = ep.get("distilled") or {}
    f = ep.get("faithfulness") or {}
    bt = f.get("backtranslation") or {}
    reqs = d.get("requirements") or []
    asked = sum(1 for r in reqs if r.get("source") == "answer")
    pct = (lambda v: "—" if v is None else f"{round(v * 100)}%")

    out.append(f"<h2>{e(chosen)}</h2>")
    if (ep.get("meter") or {}).get("validator") == "mock":
        out.append("<div class='warn'><b>validator: mock</b> — this episode "
                   "used the crude structural check, not Scribble. A "
                   "development run, never evidence.</div>")
    out.append(
        "<div class='tiles'>"
        f"<div class='tile'><div class='v'>{len(reqs)}</div>"
        "<div class='k'>Requirements</div></div>"
        f"<div class='tile'><div class='v'>{asked}</div>"
        "<div class='k'>Only by asking</div></div>"
        f"<div class='tile'><div class='v'>{len(ep.get('draft_attempts') or [])}"
        "</div><div class='k'>Draft attempts</div></div>"
        f"<div class='tile'><div class='v'>{pct(f.get('recall'))}</div>"
        "<div class='k'>Coverage recall</div></div>"
        f"<div class='tile'><div class='v'>{bt.get('score', '—')}</div>"
        "<div class='k'>Back-translation</div></div>"
        f"<div class='tile'><div class='v'>{len(f.get('ungrounded') or [])}"
        "</div><div class='k'>Ungrounded steps</div></div></div>")

    goals = d.get("goals") or []
    if goals:
        out.append("<h2>Goals — what must be true at the end</h2><ul>")
        out += [f"<li><b>{e(g.get('gid', ''))}</b> {e(g.get('text', ''))}"
                + (f" <span class='sub'>— evidence: "
                   f"{e(g.get('evidence', ''))}</span>"
                   if g.get("evidence") else "") + "</li>" for g in goals]
        out.append("</ul>")

    inters = d.get("interactions") or []
    if inters:
        out.append("<h2>Intended interactions — who hands what to whom, "
                   "carrying what, how often</h2><table><tr><th>ID</th>"
                   "<th>From → To</th><th>What</th><th>Carries</th>"
                   "<th>How often</th></tr>")
        for i in inters:
            carries = "<br>".join(
                f"<code>{e(f.get('name', ''))}</code>: "
                f"{e(f.get('type', 'string'))}"
                + (f" <span class='b'>{e(f.get('constraint'))}</span>"
                   if f.get("constraint") else "")
                for f in i.get("carries", [])) or "—"
            out.append(
                f"<tr><td>{e(i.get('iid', ''))}</td>"
                f"<td>{e(i.get('sender', ''))} → {e(i.get('receiver', ''))}"
                + (" <span class='b'>conditional</span>"
                   if i.get("optional") else "") + "</td>"
                f"<td>{e(i.get('what', ''))}"
                + (f"<div class='sub'>when: {e(i.get('when'))}</div>"
                   if i.get("when") else "") + "</td>"
                f"<td class='sub'>{carries}</td>"
                f"<td class='sub'>{e(i.get('cardinality', '') or '—')}</td>"
                "</tr>")
        out.append("</table>")
        guards = [(i.get("iid"), f) for i in inters
                  for f in i.get("carries", []) if f.get("constraint")]
        if guards:
            out.append("<h3>Value constraints → refinement guards</h3><ul>")
            out += [f"<li><code>{e(iid)}.{e(f.get('name'))}</code> — "
                    f"{e(f.get('constraint'))}</li>" for iid, f in guards]
            out.append("</ul>")
        unbounded = [i.get("iid") for i in inters
                     if "unbounded" in str(i.get("cardinality", "")).lower()
                     or "one or more" in str(i.get("cardinality", "")).lower()]
        if unbounded:
            out.append(f"<div class='warn'>Unbounded repeat declared for "
                       f"{e(', '.join(unbounded))} — no stated bound, which "
                       f"is how a session fails to terminate.</div>")

    if d.get("non_goals"):
        out.append("<h3>Out of scope (do NOT build)</h3><ul>")
        out += [f"<li>{e(n)}</li>" for n in d["non_goals"]]
        out.append("</ul>")

    out.append("<h2>Distilled requirements</h2><table><tr><th>ID</th>"
               "<th>Kind</th><th>Source</th><th>Requirement</th></tr>")
    for r in reqs:
        out.append(f"<tr><td>{e(r.get('rid', ''))}</td>"
                   f"<td><span class='b'>{e(r.get('kind', ''))}</span></td>"
                   f"<td><span class='b'>{e(r.get('source', ''))}</span></td>"
                   f"<td>{e(r.get('text', ''))}</td></tr>")
    out.append("</table>")
    if d.get("open_questions"):
        out.append("<h3>Open questions (left unresolved, not invented)</h3><ul>")
        out += [f"<li>{e(q)}</li>" for q in d["open_questions"]]
        out.append("</ul>")

    out.append("<h2>Interrogation</h2>")
    for t in ep.get("transcript") or []:
        out.append(f"<div class='card'><h3>Round {t.get('round')} — asks</h3>"
                   f"<pre>{e(t.get('question', ''))}</pre>"
                   f"<h3>Stakeholder answers</h3>"
                   f"<pre>{e(t.get('answer', ''))}</pre></div>")

    protocol_text = ep.get("final_protocol")
    if not protocol_text:
        atts = ep.get("draft_attempts") or []
        protocol_text = atts[-1].get("text") if atts else None
    if protocol_text:
        from experiments.intent_loop.protocol_graph import (parse_protocol,
                                                            render_role_graph,
                                                            render_sequence,
                                                            render_role_fsm)
        ir = parse_protocol(protocol_text)
        st = ir.stats()
        out.append(f"<h2>The protocol as a graph</h2><div class='sub'>"
                   f"{st['roles']} roles · {st['messages']} messages · "
                   f"{st['choices']} decision points · {st['loops']} loops · "
                   f"{st['branched_messages']} messages that only happen on "
                   f"some branch</div>")
        if ir.unparsed:
            out.append(f"<div class='warn'>{len(ir.unparsed)} line(s) could "
                       f"not be read and are NOT drawn.</div>")
        out.append("<h3>Who talks to whom</h3>"
                   f"<div class='card'>{render_role_graph(ir)}</div>")
        out.append("<h3>In what order — grey bands are conditional</h3>"
                   f"<div class='card'>{render_sequence(ir)}</div>")
        for role in ir.roles:
            out.append(f"<h3>{e(role)} — its own contract</h3>"
                       f"<div class='card'>{render_role_fsm(ir, role)}</div>")

    if ep.get("final_protocol"):
        out.append("<h2>Validated protocol</h2>"
                   f"<pre>{e(ep['final_protocol'])}</pre>")

    out.append("<h2>Draft attempts</h2>")
    for a in ep.get("draft_attempts") or []:
        verdict = "accepted" if a.get("valid") else "rejected"
        out.append(f"<div class='card'><h3>Attempt {a.get('k')} — {verdict}"
                   "</h3>")
        if a.get("validator_msg"):
            out.append(f"<div class='sub'>validator: "
                       f"{e(a['validator_msg'])}</div>")
        out.append(f"<pre>{e(a.get('text', ''))}</pre></div>")

    if f:
        out.append(f"<h2>Faithfulness</h2><div class='card'>{e(f.get('rule', ''))}"
                   "</div><table><tr><th>ID</th><th>Verdict</th>"
                   "<th>Evidence</th></tr>")
        for c in f.get("coverage") or []:
            label = _COVER_LABEL.get(c.get("covered"), c.get("covered", ""))
            out.append(f"<tr><td>{e(c.get('rid', ''))}</td>"
                       f"<td><span class='b'>{e(label)}</span></td>"
                       f"<td>{e(c.get('evidence', ''))}</td></tr>")
        out.append("</table>")
        if f.get("ungrounded"):
            out.append("<h3>Ungrounded structure — in the protocol, required "
                       "by nothing</h3><ul>")
            out += [f"<li>{e(u)}</li>" for u in f["ungrounded"]]
            out.append("</ul>")
        if bt:
            out.append("<h3>Back-translation (reconstructed from the protocol "
                       f"alone) — score {bt.get('score', '—')}</h3>")
            for key, title in (("missing", "Lost in translation"),
                               ("added", "Added by the protocol")):
                if bt.get(key):
                    out.append(f"<h3>{title}</h3><ul>")
                    out += [f"<li>{e(m)}</li>" for m in bt[key]]
                    out.append("</ul>")
            out.append(f"<pre>{e(bt.get('reconstructed', ''))}</pre>")

    out.append("<h2>Intent document</h2>"
               f"<pre>{e(ep.get('document', ''))}</pre>")
    return "".join(out) + "</body></html>"


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(sessions_dir: Path = DEFAULT_SESSIONS,
               corpus_path: Path = DEFAULT_CORPUS_PATH,
               packs_dir: Path = DEFAULT_PACKS,
               exports_dir: Path = DEFAULT_EXPORTS) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(SESSIONS=Path(sessions_dir), CORPUS=Path(corpus_path),
                      PACKS=Path(packs_dir), EXPORTS=Path(exports_dir))
    registry = JobRegistry()
    app.config["JOBS"] = registry

    @app.after_request
    def _cors(resp):
        # Localhost-only dev tool; agents may call it from another process
        # or a devcontainer, so keep the API reachable without a proxy.
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return resp

    # -- UI ---------------------------------------------------------------
    @app.get("/")
    def index():
        return send_from_directory(HERE, "ui.html")

    @app.get("/report")
    def report():
        """Server-rendered, JavaScript-free view of the same episodes.

        Embedded viewers sometimes sandbox scripts (VS Code's Simple
        Browser can), which leaves the single-page UI blank with no
        explanation. This route renders everything server-side so the
        framework is always inspectable, whatever the viewer allows."""
        return render_report(app.config["SESSIONS"],
                             request.args.get("session"))

    # -- discovery --------------------------------------------------------
    @app.get("/api/health")
    def health():
        return jsonify({
            "ok": True, "service": "stjp-intent-loop",
            "sessions_dir": str(app.config["SESSIONS"]),
            "corpus": str(app.config["CORPUS"]),
            "episodes": len(load_episodes(app.config["SESSIONS"])),
            "validator": toolchain_status(), "llm": llm_status(),
        })

    @app.get("/api/manifest")
    def manifest():
        """Machine-readable endpoint catalog, so an agent can drive this
        service without reading the source."""
        return jsonify({
            "service": "stjp-intent-loop",
            "purpose": "Interrogate a stakeholder about a document-scale "
                       "intent, distill typed requirements, draft a "
                       "Scribble protocol under the real validator, grade "
                       "its faithfulness, and mine the resulting corpus "
                       "into prompt packs or fine-tuning datasets.",
            "endpoints": [
                {"method": "GET", "path": "/api/health",
                 "returns": "readiness incl. validator + LLM configuration"},
                {"method": "GET", "path": "/api/episodes",
                 "returns": "episode summaries"},
                {"method": "GET", "path": "/api/episodes/<session>",
                 "returns": "one full episode"},
                {"method": "POST", "path": "/api/runs",
                 "body": {"mock": "bool - scripted offline episode",
                          "intent_text": "str - the intent document",
                          "intent_file": "str - path instead of text",
                          "hidden_notes_text": "str - facts the document "
                                               "omits (stakeholder-only)",
                          "validator": "'real'|'mock'",
                          "max_rounds": "int - interrogation round cap",
                          "pack": "str - prompt pack version to draft with"},
                 "returns": "{job_id} - poll /api/runs/<job_id>"},
                {"method": "GET", "path": "/api/runs/<job_id>",
                 "returns": "job state + stage events "
                            "(start|interrogated|drafted|evaluated|done)"},
                {"method": "GET", "path": "/api/episodes/<session>/graph",
                 "returns": "role graph, sequence view and per-role state "
                            "machines as inline SVG, plus the edge list"},
                {"method": "POST", "path": "/api/episodes/<session>/explain",
                 "returns": "per-message rationale: which requirement each "
                            "message realizes and why it sits there"},
                {"method": "POST",
                 "path": "/api/episodes/<session>/questions",
                 "returns": "questions about this draft, each anchored to a "
                            "measured defect"},
                {"method": "POST", "path": "/api/episodes/<session>/refine",
                 "body": {"answers": "[{question, answer}] from /questions "
                                     "or from a human",
                          "validator": "'real'|'mock'"},
                 "returns": "{job_id} — redrafts with the answers folded in "
                            "as new requirements, producing a NEW episode"},
                {"method": "GET", "path": "/api/corpus",
                 "returns": "corpus statistics"},
                {"method": "POST", "path": "/api/packs",
                 "body": {"version": "str", "require_faithful": "bool"},
                 "returns": "prompt pack summary (prompt-level training)"},
                {"method": "GET", "path": "/api/training/stats",
                 "returns": "fine-tuning example counts + what was dropped"},
                {"method": "POST", "path": "/api/training/export",
                 "body": {"validation_fraction": "float 0-1",
                          "kinds": "['drafting','repair']"},
                 "returns": "written JSONL paths (chat format, ready for "
                            "Azure OpenAI / OpenAI fine-tuning)"},
            ],
            "notes": [
                "Runs are asynchronous; poll the job.",
                "A mock run is never evidence: its artifacts are stamped "
                "validator: mock.",
                "Faithfulness excludes 'policy' requirements — constraints "
                "no session type can express (e.g. separation of duties).",
            ],
        })

    # -- episodes ---------------------------------------------------------
    @app.get("/api/episodes")
    def episodes():
        return jsonify({"episodes": load_episodes(app.config["SESSIONS"])})

    @app.get("/api/episodes/<path:session>")
    def episode(session: str):
        ep = load_episode(app.config["SESSIONS"], session)
        if ep is None:
            return jsonify({"error": "no such episode"}), 404
        return jsonify(ep)

    # -- runs -------------------------------------------------------------
    @app.post("/api/runs")
    def start_run():
        body = request.get_json(silent=True) or {}
        mock = bool(body.get("mock", False))
        validator = body.get("validator") or ("mock" if mock else "real")

        # A scripted mock replies from a fixed script REGARDLESS of the
        # document, so pairing it with a real intent silently returns
        # canned answers about a quarterly-report demo. That combination is
        # never what anyone means; refuse it instead of producing
        # confident nonsense.
        if mock and (body.get("intent_text") or body.get("intent_file")):
            return jsonify({
                "error": "mock=true ignores your intent document — every "
                         "reply comes from a fixed script, so the result "
                         "would describe the built-in demo, not your text.",
                "hint": "send mock=false to actually run your document "
                        "through the model.",
            }), 400

        if body.get("intent_text"):
            document = str(body["intent_text"])
        elif body.get("intent_file"):
            p = Path(body["intent_file"])
            if not p.exists():
                return jsonify({"error": f"no such file: {p}"}), 400
            document = p.read_text(encoding="utf-8")
        elif mock:
            document = mockdata.DEMO_DOCUMENT
        else:
            return jsonify({"error": "intent_text or intent_file is "
                                     "required for a live run"}), 400

        hidden = body.get("hidden_notes_text")
        if not hidden and body.get("hidden_notes_file"):
            hp = Path(body["hidden_notes_file"])
            hidden = hp.read_text(encoding="utf-8") if hp.exists() else None
        if mock and hidden is None:
            hidden = mockdata.HIDDEN_NOTES

        if validator == "real":
            status = toolchain_status()
            if not status["available"]:
                return jsonify({"error": "real validator unavailable",
                                "detail": status["detail"],
                                "hint": "pass validator='mock' for a "
                                        "development run"}), 409
            validate_fn, label = loop_mod.real_validate(), "scribble-java"
        else:
            validate_fn, label = loop_mod.mock_validate, "mock"

        pack = None
        if body.get("pack"):
            pp = app.config["PACKS"] / f"pack_{body['pack']}.json"
            if not pp.exists():
                return jsonify({"error": f"no such pack: {body['pack']}"}), 400
            pack = PromptPack.load(pp)

        # Who answers the learner's questions: the strong expert model, or
        # a strict document-quoting stakeholder (which says NOT SPECIFIED
        # when the text is silent — right for measuring what interrogation
        # recovers, wrong for getting a protocol finished unattended).
        # Who answers the learner's questions:
        #   human    a person, live, turn by turn — the run WAITS
        #   expert   the stronger model (watch two models converse)
        #   document a strict quoting stakeholder (says NOT SPECIFIED)
        #   expert_reviewed  the expert DRAFTS, you approve or rewrite
        #                    (default: an unreviewed model decision becomes a
        #                    requirement, and the checker cannot tell)
        answered_by = str(body.get("answered_by") or "expert_reviewed").lower()
        if answered_by not in ("expert", "document", "human",
                              "expert_reviewed"):
            answered_by = "expert_reviewed"

        # Guard against a double-click launching two runs of the same
        # document against one deployment: they contend for the same rate
        # limit and each makes the other slower, which is exactly what a
        # user reads as "stuck".
        doc_sha = hashlib.sha256(document.encode("utf-8")).hexdigest()
        for existing in registry.list():
            if (existing.state in ("queued", "running")
                    and existing.params.get("doc_sha") == doc_sha):
                return jsonify({
                    "error": "a run of this same document is already in "
                             "flight — two runs against one deployment "
                             "contend for the same rate limit and both get "
                             "slower.",
                    "job_id": existing.id,
                    "session": existing.params.get("session"),
                    "hint": "watch that job, or change the document"}), 409

        # Phase gate: stop after the understanding by default so a human
        # endorses it BEFORE any protocol is written or checked.
        stop_after = ("all" if str(body.get("stop_after", "")).lower()
                      == "all" else "understanding")

        label_prefix = "mock" if mock else "live"
        out_dir = (app.config["SESSIONS"]
                   / f"{label_prefix}_{_now_stamp()}")
        from experiments.intent_loop import settings as settings_mod
        cfg = settings_mod.load()
        repair_rounds = int(body.get("max_repair_rounds")
                            or cfg.max_repair_rounds)
        params = {"mock": mock, "validator": label,
                  "intent_chars": len(document),
                  "max_rounds": int(body.get("max_rounds", 5)),
                  "max_repair_rounds": repair_rounds,
                  "pack": body.get("pack"), "session": out_dir.name,
                  "stop_after": stop_after,
                  "answered_by": answered_by, "doc_sha": doc_sha,
                  "learner": cfg.model,
                  "expert": cfg.expert_model if answered_by == "expert"
                  else None}

        def _work(job: Job) -> dict:
            def progress(stage: str, detail: dict) -> None:
                job.emit(stage, detail)

            if mock:
                meter = Meter()
                kwargs = dict(
                    llm=MockChat(mockdata.INTERROGATOR_SCRIPT, meter=meter),
                    stakeholder_llm=MockChat(mockdata.STAKEHOLDER_SCRIPT,
                                             meter=meter),
                    drafter_chat=MockChat(mockdata.DRAFTER_SCRIPT,
                                          meter=meter),
                    eval_llm=MockChat(mockdata.EVAL_SCRIPT, meter=meter))
            else:
                from experiments.intent_loop.llm import build_chat
                # The learner drafts; a STRONGER expert model answers its
                # questions in place of a human. Same model for both would
                # be the learner interrogating itself.
                kwargs = dict(llm=build_chat(role="learner"))
                if answered_by == "expert":
                    kwargs["stakeholder_llm"] = build_chat(role="expert")
                elif answered_by == "expert_reviewed":
                    # The expert drafts; the human approves or rewrites.
                    from experiments.intent_loop.stakeholder import (
                        ReviewedStakeholder, StakeholderSim)
                    expert = StakeholderSim(build_chat(role="expert"),
                                            document,
                                            hidden_notes=hidden,
                                            mode="expert")
                    reviewed = ReviewedStakeholder(
                        expert, on_propose=lambda q, p: job.ask(q, p))
                    job.answer_sink = reviewed.submit
                    kwargs["stakeholder_obj"] = reviewed
                elif answered_by == "human":
                    # The run BLOCKS on each question until the person
                    # replies through /api/runs/<id>/answer.
                    from experiments.intent_loop.stakeholder import (
                        HumanStakeholder)
                    human = HumanStakeholder(on_ask=job.ask)
                    job.answer_sink = human.submit
                    kwargs["stakeholder_obj"] = human

            llm = kwargs.pop("llm")
            record = loop_mod.run_episode(
                llm, document, out_dir=out_dir, hidden_notes=hidden,
                prompt_pack=pack, max_rounds=params["max_rounds"],
                validate_fn=validate_fn, validator_label=label,
                max_repair_rounds=repair_rounds,
                corpus_path=app.config["CORPUS"], progress=progress,
                stop_after=stop_after,
                stakeholder_mode=("expert" if answered_by in
                                  ("expert", "expert_reviewed")
                                  and not mock else "document"),
                **kwargs)
            faith = record.faithfulness or {}
            return {"session": out_dir.name,
                    "episode_id": record.episode_id,
                    "valid": record.valid,
                    "faithful": bool(faith.get("faithful")),
                    "recall": faith.get("recall"),
                    "attempts": len(record.draft_attempts)}

        job = registry.submit("run", params, _work)
        return jsonify({"job_id": job.id, "session": out_dir.name}), 202

    @app.get("/api/runs")
    def list_runs():
        return jsonify({"jobs": [j.to_dict(include_events=False)
                                 for j in registry.list()]})

    @app.get("/api/runs/<job_id>")
    def get_run(job_id: str):
        job = registry.get(job_id)
        if job is None:
            return jsonify({"error": "no such job"}), 404
        return jsonify(job.to_dict())

    @app.post("/api/runs/<job_id>/answer")
    def answer_run(job_id: str):
        """A human answers the learner's open question; the run resumes.

        This is what makes the interrogation a conversation rather than a
        transcript: the run thread is blocked inside the interrogation
        waiting for exactly this."""
        job = registry.get(job_id)
        if job is None:
            return jsonify({"error": "no such job"}), 404
        body = request.get_json(silent=True) or {}
        text = str(body.get("answer", "")).strip()
        if not text:
            return jsonify({"error": "answer is required"}), 400
        if not job.answer(text):
            return jsonify({"error": "this run is not waiting for an "
                                     "answer right now"}), 409
        return jsonify({"ok": True, "job_id": job_id})

    # -- settings: bring your own LLM -------------------------------------
    @app.get("/api/settings")
    def get_settings():
        """The saved configuration, ALWAYS masked — the key is never
        returned, only a last-four fingerprint so you can tell which one is
        loaded."""
        from experiments.intent_loop import settings as settings_mod
        return jsonify(settings_mod.load().masked())

    @app.post("/api/settings")
    def post_settings():
        """Partial update. Omit `api_key` to keep the stored one; send an
        empty string to clear it (that is how Azure falls back to
        `az login`)."""
        from experiments.intent_loop import settings as settings_mod
        body = request.get_json(silent=True) or {}
        s = settings_mod.update(body)
        return jsonify(s.masked())

    @app.post("/api/settings/test")
    def test_settings():
        """One tiny real call, so 'saved' never gets mistaken for 'works'.

        Tests the SUBMITTED settings when a body is given (so you can
        verify before saving), otherwise the stored ones."""
        from experiments.intent_loop import settings as settings_mod
        from experiments.intent_loop.llm import ApiChat
        body = request.get_json(silent=True) or {}
        current = settings_mod.load()
        if body:
            data = current.to_dict()
            for k, v in body.items():
                if k in data and not (k == "api_key" and v is None):
                    data[k] = v
            current = settings_mod.Settings(
                **{k: data[k] for k in settings_mod.Settings.__dataclass_fields__})
        if not current.is_usable():
            return jsonify({"ok": False,
                            "error": "endpoint and model are required"
                                     + ("" if current.provider == "azure"
                                        else "; an OpenAI-compatible "
                                             "endpoint also needs a key")}), 400
        try:
            chat = ApiChat(current)
            reply = chat.complete("Reply with exactly: OK",
                                  "Say OK.", stage="settings_test")
        except Exception as e:
            return jsonify({"ok": False, "model": current.model,
                            "error": f"{type(e).__name__}: "
                                     f"{str(e)[:400]}"}), 502
        return jsonify({"ok": True, "model": current.model,
                        "provider": current.provider,
                        "reply": reply.strip()[:120],
                        "approx_tokens": chat.meter.to_dict()})

    # -- the draft, seen and questioned -----------------------------------
    def _live_llm():
        from experiments.intent_loop.llm import build_chat
        return build_chat()

    @app.get("/api/episodes/<path:session>/partial")
    def episode_partial(session: str):
        """Poll a run in flight — returns artifacts as they land."""
        p = load_partial(app.config["SESSIONS"], session)
        if p is None:
            return jsonify({"error": "no such session"}), 404
        return jsonify(p)

    @app.get("/api/episodes/<path:session>/intent-graph")
    def episode_intent_graph(session: str):
        """The INTENDED interaction graph, from the distilled checklist.

        Available as soon as interrogation ends — minutes before a
        protocol exists — so the intended shape can be reviewed while it
        is still cheap to change."""
        ep = load_partial(app.config["SESSIONS"], session)
        if ep is None:
            return jsonify({"error": "no such session"}), 404
        distilled = ep.get("distilled") or {}
        if not distilled.get("interactions"):
            return jsonify({"error": "no interactions distilled yet",
                            "hint": "this episode predates the interactions "
                                    "field, or interrogation is still "
                                    "running"}), 404
        from experiments.intent_loop.protocol_graph import intent_graph_payload
        return jsonify(intent_graph_payload(distilled))

    @app.get("/api/episodes/<path:session>/graph")
    def episode_graph(session: str):
        """Role graph, sequence view and per-role state machines, as SVG.

        Rendered from the drafted protocol by a tolerant reader — it draws
        what the model actually emitted, including constructs the strict
        Scribble grammar rejects, because seeing a rejected draft is how
        you find out why it was rejected. Validity remains the validator's
        verdict alone; anything unreadable is listed, never dropped."""
        # Partial load, so a protocol can be drawn the moment it is
        # drafted — the graph is the thing worth watching for, and waiting
        # for the whole episode to finish just to see it is the difference
        # between a legible run and a spinner.
        ep = load_partial(app.config["SESSIONS"], session)
        if ep is None:
            return jsonify({"error": "no such episode"}), 404
        protocol = ep.get("final_protocol")
        if not protocol:
            attempts = ep.get("draft_attempts") or []
            protocol = attempts[-1].get("text") if attempts else None
        if not protocol:
            return jsonify({"error": "this episode has no protocol to draw"}), 404
        from experiments.intent_loop.protocol_graph import graph_payload
        payload = graph_payload(protocol)
        payload["from_valid_draft"] = bool(ep.get("final_protocol"))
        return jsonify(payload)

    @app.get("/api/episodes/<path:session>/checks")
    def episode_checks(session: str):
        """Deadlock precursors + the turn order.

        Fast, JVM-free, pre-validator signals: which join can starve, and
        whose move it is at each step. The real Scribble checker remains
        the authority on deadlock-freedom; a clean result here proves
        nothing on its own, and the payload says so."""
        ep = load_partial(app.config["SESSIONS"], session)
        if ep is None:
            return jsonify({"error": "no such episode"}), 404
        protocol = ep.get("final_protocol")
        if not protocol:
            atts = ep.get("draft_attempts") or []
            protocol = atts[-1].get("text") if atts else None
        if not protocol:
            return jsonify({"error": "no protocol to check yet"}), 404
        joins = [i for i in (ep.get("distilled") or {}).get("interactions", [])
                 if len(i.get("waits_for") or []) > 1]
        from experiments.intent_loop.protocol_checks import check_protocol
        out = check_protocol(protocol, declared_joins=joins)
        out["validator"] = (ep.get("meter") or {}).get("validator", "?")
        return jsonify(out)

    @app.post("/api/episodes/<path:session>/explain")
    def episode_explain(session: str):
        """Per-message rationale: which requirement each message realizes
        and why it sits where it does. Cached to the session directory."""
        ep = load_episode(app.config["SESSIONS"], session)
        if ep is None or not ep.get("final_protocol"):
            return jsonify({"error": "no validated protocol to explain"}), 404
        cache = app.config["SESSIONS"] / session / "rationale.json"
        if cache.exists() and not request.args.get("refresh"):
            return jsonify(json.loads(cache.read_text(encoding="utf-8")))
        from experiments.intent_loop.refine import explain_protocol
        from experiments.intent_loop.schema import DistilledIntent
        try:
            out = explain_protocol(_live_llm(),
                                   DistilledIntent.from_dict(ep["distilled"]),
                                   ep["final_protocol"])
        except Exception as e:
            return jsonify({"error": f"{type(e).__name__}: {e}"}), 502
        cache.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        return jsonify(out)

    @app.post("/api/episodes/<path:session>/repair-questions")
    def episode_repair_questions(session: str):
        """The checker rejected this draft — what must the USER decide?

        This closes the loop the app is for. An "uninformed branch"
        rejection is not a syntax slip: it means a decision is missing from
        the intent (who gets told, on which path), and redrafting without
        asking is guessing. Answers go to /refine, which folds them in as
        requirements and drafts again."""
        ep = load_partial(app.config["SESSIONS"], session)
        if ep is None:
            return jsonify({"error": "no such episode"}), 404
        attempts = ep.get("draft_attempts") or []
        rejected = [a for a in attempts if not a.get("valid")]
        if not rejected:
            return jsonify({"error": "nothing was rejected — this episode "
                                     "validated",
                            "hint": "use /questions for faithfulness gaps"}), 400
        last = rejected[-1]
        from experiments.intent_loop.protocol_checks import check_protocol
        from experiments.intent_loop.refine import questions_from_validation
        from experiments.intent_loop.schema import DistilledIntent
        checks = check_protocol(last.get("text") or "")
        try:
            out = questions_from_validation(
                _live_llm(),
                DistilledIntent.from_dict(ep.get("distilled") or {}),
                last.get("text") or "",
                last.get("validator_msg") or "",
                findings=checks.get("findings"))
        except Exception as e:
            return jsonify({"error": f"{type(e).__name__}: {e}"}), 502
        out["attempt"] = last.get("k")
        out["blockers"] = [f for f in checks.get("findings", [])
                           if f.get("severity") == "blocker"]
        (app.config["SESSIONS"] / session / "repair_questions.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify(out)

    @app.get("/api/episodes/<path:session>/skill")
    def episode_skill(session: str):
        """The episode as a reusable SKILL.md — the protocol, the decisions
        that produced it, and what the validator taught."""
        ep = load_episode(app.config["SESSIONS"], session)
        if ep is None:
            return jsonify({"error": "no such episode"}), 404
        from experiments.intent_loop.protocol_checks import check_protocol
        from experiments.intent_loop.skill import (build_skill,
                                                   collect_decisions,
                                                   write_skill)
        sdir = app.config["SESSIONS"] / session
        protocol = ep.get("final_protocol")
        checks = check_protocol(protocol) if protocol else None
        kwargs = dict(checks=checks, decisions=collect_decisions(sdir),
                      validator_label=(ep.get("meter") or {}).get(
                          "validator", "unknown"))
        path = write_skill(sdir, ep, **kwargs)
        if request.args.get("format") == "markdown":
            return (build_skill(ep, **kwargs), 200,
                    {"Content-Type": "text/markdown; charset=utf-8"})
        return jsonify({"path": str(path),
                        "markdown": build_skill(ep, **kwargs)})

    @app.post("/api/episodes/<path:session>/questions")
    def episode_questions(session: str):
        """Questions worth asking about THIS draft, each anchored to a
        measured defect (a requirement scored no/partial, an ungrounded
        message, an unresolved intake question)."""
        ep = load_episode(app.config["SESSIONS"], session)
        if ep is None or not ep.get("final_protocol"):
            return jsonify({"error": "no validated protocol to question"}), 404
        cache = app.config["SESSIONS"] / session / "questions.json"
        if cache.exists() and not request.args.get("refresh"):
            return jsonify(json.loads(cache.read_text(encoding="utf-8")))
        from experiments.intent_loop.refine import propose_questions
        from experiments.intent_loop.schema import DistilledIntent
        try:
            qs = propose_questions(_live_llm(),
                                   DistilledIntent.from_dict(ep["distilled"]),
                                   ep["final_protocol"],
                                   ep.get("faithfulness"))
        except Exception as e:
            return jsonify({"error": f"{type(e).__name__}: {e}"}), 502
        out = {"questions": qs, "session": session}
        cache.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        return jsonify(out)

    @app.post("/api/episodes/<path:session>/refine")
    def episode_refine(session: str):
        """Fold answers into the checklist and redraft -> a NEW episode.

        Body: {"answers": [{"question": "...", "answer": "..."}], ...}
        The answers may come from /questions or straight from a human —
        the endpoint does not care which, so a colleague and an agent
        refine the same way."""
        ep = load_episode(app.config["SESSIONS"], session)
        if ep is None:
            return jsonify({"error": "no such episode"}), 404
        body = request.get_json(silent=True) or {}
        answers = [a for a in (body.get("answers") or [])
                   if str(a.get("answer", "")).strip()]
        if not answers:
            return jsonify({"error": "no answered questions — refinement "
                                     "needs at least one decision"}), 400
        validator = body.get("validator") or "real"
        if validator == "real":
            status = toolchain_status()
            if not status["available"]:
                return jsonify({"error": "real validator unavailable",
                                "detail": status["detail"],
                                "hint": "pass validator='mock' for a "
                                        "development run"}), 409
            validate_fn, label = loop_mod.real_validate(), "scribble-java"
        else:
            validate_fn, label = loop_mod.mock_validate, "mock"

        pack = None
        if body.get("pack"):
            pp = app.config["PACKS"] / f"pack_{body['pack']}.json"
            if pp.exists():
                pack = PromptPack.load(pp)

        out_dir = app.config["SESSIONS"] / f"refine_{_now_stamp()}"
        params = {"parent": session, "answers": len(answers),
                  "validator": label, "session": out_dir.name}

        def _work(job: Job) -> dict:
            from experiments.intent_loop.refine import refine_episode
            record = refine_episode(
                _live_llm(), parent_record=ep,
                parent_dir=app.config["SESSIONS"] / session,
                out_dir=out_dir, answers=answers, validate_fn=validate_fn,
                validator_label=label, prompt_pack=pack,
                corpus_path=app.config["CORPUS"],
                progress=lambda s, d: job.emit(s, d))
            faith = record.faithfulness or {}
            parent_faith = ep.get("faithfulness") or {}
            return {"session": out_dir.name, "parent": session,
                    "valid": record.valid,
                    "faithful": bool(faith.get("faithful")),
                    "recall": faith.get("recall"),
                    "recall_before": parent_faith.get("recall"),
                    "requirements": len(record.distilled.get("requirements", []))}

        job = registry.submit("refine", params, _work)
        return jsonify({"job_id": job.id, "session": out_dir.name}), 202

    # -- corpus / prompt-level training -----------------------------------
    @app.get("/api/corpus")
    def corpus():
        records = list(read_corpus(app.config["CORPUS"]))
        faithful = sum(1 for r in records
                       if (r.faithfulness or {}).get("faithful"))
        return jsonify({
            "path": str(app.config["CORPUS"]),
            "episodes": len(records),
            "valid": sum(1 for r in records if r.valid),
            "faithful": faithful,
            "rows": [{"episode_id": r.episode_id, "ts": r.ts,
                      "valid": r.valid,
                      "faithful": bool((r.faithfulness or {}).get("faithful")),
                      "attempts": len(r.draft_attempts),
                      "qa_rounds": len(r.transcript)} for r in records],
        })

    @app.get("/api/packs")
    def list_packs():
        d = app.config["PACKS"]
        packs = []
        if d.is_dir():
            for p in sorted(d.glob("pack_*.json")):
                try:
                    pk = PromptPack.load(p)
                except (json.JSONDecodeError, KeyError):
                    continue
                packs.append({"version": pk.version, "path": str(p),
                              "exemplars": len(pk.exemplars),
                              "rulebook": len(pk.rulebook),
                              "built_from": pk.built_from})
        return jsonify({"packs": packs})

    @app.get("/api/packs/<version>")
    def get_pack(version: str):
        p = app.config["PACKS"] / f"pack_{version}.json"
        if not p.exists():
            return jsonify({"error": "no such pack"}), 404
        pk = PromptPack.load(p)
        return jsonify({"version": pk.version, "rulebook": pk.rulebook,
                        "built_from": pk.built_from,
                        "exemplars": [{"item_id": c.item_id,
                                       "intent": c.intent,
                                       "protocol": c.protocol}
                                      for c in pk.exemplars]})

    @app.post("/api/packs")
    def make_pack():
        body = request.get_json(silent=True) or {}
        version = str(body.get("version") or _now_stamp())
        pack = build_prompt_pack(
            app.config["CORPUS"], version=version,
            require_faithful=bool(body.get("require_faithful", True)))
        path = app.config["PACKS"] / f"pack_{version}.json"
        pack.save(path)
        return jsonify({"version": pack.version, "path": str(path),
                        "exemplars": len(pack.exemplars),
                        "rulebook": pack.rulebook,
                        "built_from": pack.built_from}), 201

    # -- weight-level training (fine-tuning datasets) ---------------------
    @app.get("/api/training/stats")
    def training_stats():
        ds = build_dataset(app.config["CORPUS"],
                           sessions_dir=app.config["SESSIONS"])
        return jsonify(ds["stats"])

    @app.post("/api/training/export")
    def training_export():
        body = request.get_json(silent=True) or {}
        kinds = tuple(body.get("kinds") or ("drafting", "repair"))
        ds = build_dataset(app.config["CORPUS"],
                           sessions_dir=app.config["SESSIONS"],
                           kinds=kinds,
                           validation_fraction=float(
                               body.get("validation_fraction", 0.0)))
        out_dir = app.config["EXPORTS"] / f"sft_{_now_stamp()}"
        written = write_dataset(ds, out_dir)
        return jsonify({"out_dir": str(out_dir), "files": written,
                        "stats": ds["stats"],
                        "format": "chat JSONL (messages[]) — accepted by "
                                  "Azure OpenAI and OpenAI fine-tuning"}), 201

    return app


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="intent_loop web", description=__doc__)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1",
                   help="default 127.0.0.1; the API is unauthenticated and "
                        "can spend LLM budget — do not expose it publicly")
    p.add_argument("--sessions", default=str(DEFAULT_SESSIONS))
    p.add_argument("--corpus", default=str(DEFAULT_CORPUS_PATH))
    p.add_argument("--debug", action="store_true")
    args = p.parse_args(argv)

    app = create_app(Path(args.sessions).resolve(),
                     Path(args.corpus).resolve())
    url = f"http://{args.host}:{args.port}"
    print(f"  STJP intent loop  ->  {url}")
    print(f"  sessions: {args.sessions}")
    print(f"  VS Code:  Ctrl+Shift+P -> 'Simple Browser: Show' -> {url}")
    print(f"  agents:   GET {url}/api/manifest")
    app.run(host=args.host, port=args.port, debug=args.debug,
            use_reloader=False, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
