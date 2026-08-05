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
        rec_path = d / "record.json"
        if not d.is_dir() or not rec_path.exists():
            continue
        try:
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        faith = rec.get("faithfulness") or {}
        dist = rec.get("distilled") or {}
        reqs = dist.get("requirements") or []
        out.append({
            "session": d.name,
            "episode_id": rec.get("episode_id", d.name),
            "ts": rec.get("ts", ""),
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
    """Is a live LLM configured? Checked from config only — probing would
    cost a call on every health check."""
    import os
    backend = os.environ.get("STJP_LLM_BACKEND", "foundry").lower()
    key = ("AZURE_OPENAI_ENDPOINT" if backend == "chat"
           else "AZURE_AI_PROJECT_ENDPOINT")
    configured = bool(os.environ.get(key))
    if not configured:  # .env is loaded lazily by the client
        env_file = REPO_ROOT / "stjp_core" / ".env"
        configured = env_file.exists() and key in _read(env_file)
    return {"configured": configured, "backend": backend,
            "expects_env": key,
            "deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT")}


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

        label_prefix = "mock" if mock else "live"
        out_dir = (app.config["SESSIONS"]
                   / f"{label_prefix}_{_now_stamp()}")
        params = {"mock": mock, "validator": label,
                  "intent_chars": len(document),
                  "max_rounds": int(body.get("max_rounds", 5)),
                  "pack": body.get("pack"), "session": out_dir.name}

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
                from experiments.intent_loop.llm import FoundryChat
                kwargs = dict(llm=FoundryChat())

            llm = kwargs.pop("llm")
            record = loop_mod.run_episode(
                llm, document, out_dir=out_dir, hidden_notes=hidden,
                prompt_pack=pack, max_rounds=params["max_rounds"],
                validate_fn=validate_fn, validator_label=label,
                corpus_path=app.config["CORPUS"], progress=progress,
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
