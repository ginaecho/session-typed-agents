"""cli.py — command-line entry points for the intent-interrogation loop.

    python -m experiments.intent_loop run --intent-file F [--hidden-notes F]
        [--out DIR] [--pack pack.json] [--mock] [--max-rounds N]
        [--gold F] [--corpus F]
    python -m experiments.intent_loop run --mock
        (no intent file: runs the built-in scripted demo episode offline —
         zero network, zero cost; doubles as the end-to-end smoke test)
    python -m experiments.intent_loop optimize [--corpus F] [--out pack.json]
        [--version vN] [--include-unfaithful]
    python -m experiments.intent_loop show-corpus [--corpus F]

Real runs follow the Foundry-first policy (stjp_core/CLAUDE.md): every LLM
call lands in the portal under stjp-utility threads, and the real Scribble
validator gates every draft. --mock swaps in the scripted MockChat plus the
crude mock validator, and says so on stdout and in every artifact it
writes, so a mock episode can never be mistaken for evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.intent_loop import loop as loop_mod          # noqa: E402
from experiments.intent_loop import mockdata                  # noqa: E402
from experiments.intent_loop.corpus import (DEFAULT_CORPUS_PATH,  # noqa: E402
                                            read_corpus)
from experiments.intent_loop.llm import Meter, MockChat       # noqa: E402
from experiments.intent_loop.optimize import (PromptPack,     # noqa: E402
                                              build_prompt_pack)

SESSIONS_DIR = HERE / "sessions"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _resolve_validator(args: argparse.Namespace):
    """(validate_fn, label) — the LLM seam and the validator are independent
    choices. Default: mock under --mock, real Scribble otherwise. A live-LLM
    run on a machine without the Scribble toolchain is legitimate for
    development (`--validator mock`), and every artifact it writes carries
    `validator: mock` so it can never be mistaken for a validated result."""
    choice = args.validator or ("mock" if args.mock else "real")
    if choice == "mock":
        return loop_mod.mock_validate, "mock"
    try:
        from experiments.seam_bench.eval.validity import require_toolchain
        require_toolchain()
    except Exception as e:
        print(f"error: real validator unavailable — {e}\n"
              f"       wire it with `bash tools/setup_scribble_cloud.sh`, "
              f"or pass --validator mock for a development run.")
        return None, None
    return loop_mod.real_validate(), "scribble-java"


def cmd_run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out) if args.out else SESSIONS_DIR / _ts()
    pack = PromptPack.load(Path(args.pack)) if args.pack else None
    gold = Path(args.gold).read_text(encoding="utf-8") if args.gold else None
    validate_fn, validator_label = _resolve_validator(args)
    if validate_fn is None:
        return 2
    corpus_path = Path(args.corpus) if args.corpus else DEFAULT_CORPUS_PATH

    if args.mock:
        print(f"MODE: --mock (scripted MockChat + {validator_label} "
              f"validator; NOT evidence).")
        document = (Path(args.intent_file).read_text(encoding="utf-8")
                    if args.intent_file else mockdata.DEMO_DOCUMENT)
        hidden = (Path(args.hidden_notes).read_text(encoding="utf-8")
                  if args.hidden_notes else mockdata.HIDDEN_NOTES)
        meter = Meter()
        record = loop_mod.run_episode(
            MockChat(mockdata.INTERROGATOR_SCRIPT, meter=meter),
            document, out_dir=out_dir, hidden_notes=hidden,
            stakeholder_llm=MockChat(mockdata.STAKEHOLDER_SCRIPT, meter=meter),
            drafter_chat=MockChat(mockdata.DRAFTER_SCRIPT, meter=meter),
            eval_llm=MockChat(mockdata.EVAL_SCRIPT, meter=meter),
            prompt_pack=pack, max_rounds=args.max_rounds,
            validate_fn=validate_fn, validator_label=validator_label,
            gold_protocol=gold, corpus_path=corpus_path)
    else:
        if not args.intent_file:
            print("error: --intent-file is required without --mock")
            return 2
        document = Path(args.intent_file).read_text(encoding="utf-8")
        hidden = (Path(args.hidden_notes).read_text(encoding="utf-8")
                  if args.hidden_notes else None)
        from experiments.intent_loop.llm import FoundryChat
        llm = FoundryChat()
        print(f"MODE: live ({llm.label}) + {validator_label} validator"
              + ("  [DEV RUN — mock validator, not evidence]"
                 if validator_label == "mock" else ""))
        record = loop_mod.run_episode(
            llm, document, out_dir=out_dir, hidden_notes=hidden,
            prompt_pack=pack, max_rounds=args.max_rounds,
            validate_fn=validate_fn, validator_label=validator_label,
            gold_protocol=gold,
            bisim_fn=(_real_bisim() if gold else None),
            corpus_path=corpus_path)

    faith = record.faithfulness or {}
    print(f"episode:   {record.episode_id}")
    print(f"artifacts: {out_dir}")
    print(f"valid:     {record.valid} "
          f"({len(record.draft_attempts)} attempt(s))")
    print(f"faithful:  {faith.get('faithful')} "
          f"(recall={faith.get('recall')}, "
          f"backtranslation={faith.get('backtranslation', {}).get('score')})")
    print(f"meter:     {json.dumps(record.meter, ensure_ascii=False)}")
    return 0 if record.valid else 1


def _real_bisim():
    from experiments.seam_bench.eval import validity
    return validity.bisim_equivalent


def cmd_optimize(args: argparse.Namespace) -> int:
    corpus = Path(args.corpus) if args.corpus else DEFAULT_CORPUS_PATH
    pack = build_prompt_pack(corpus, version=args.version,
                             require_faithful=not args.include_unfaithful)
    out = Path(args.out) if args.out else HERE / "packs" / f"pack_{args.version}.json"
    pack.save(out)
    print(f"prompt pack {pack.version}: {len(pack.exemplars)} exemplar(s), "
          f"{len(pack.rulebook)} rulebook lesson(s)")
    print(f"built from: {json.dumps(pack.built_from, ensure_ascii=False)}")
    print(f"saved to:   {out}")
    return 0


def cmd_show_corpus(args: argparse.Namespace) -> int:
    corpus = Path(args.corpus) if args.corpus else DEFAULT_CORPUS_PATH
    n = valid = faithful = 0
    for rec in read_corpus(corpus):
        n += 1
        valid += int(rec.valid)
        faithful += int(bool((rec.faithfulness or {}).get("faithful")))
        rounds = len(rec.transcript)
        print(f"{rec.episode_id}  valid={rec.valid} "
              f"faithful={(rec.faithfulness or {}).get('faithful')} "
              f"qa_rounds={rounds} attempts={len(rec.draft_attempts)} "
              f"ts={rec.ts}")
    print(f"-- {n} episode(s): {valid} valid, {faithful} faithful "
          f"({corpus})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="intent_loop", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one interrogate->draft->evaluate "
                                   "episode")
    r.add_argument("--intent-file", help="path to the intent document (.md)")
    r.add_argument("--hidden-notes", help="facts the stakeholder knows but "
                                          "the document omits")
    r.add_argument("--out", help="session artifact dir (default "
                                 "sessions/<ts>)")
    r.add_argument("--pack", help="prompt pack JSON from `optimize`")
    r.add_argument("--gold", help="known-correct reference protocol (.scr) "
                                  "for the E5 equivalence check")
    r.add_argument("--corpus", help=f"corpus JSONL (default "
                                    f"{DEFAULT_CORPUS_PATH})")
    r.add_argument("--max-rounds", type=int, default=5)
    r.add_argument("--mock", action="store_true",
                   help="offline scripted episode (demo/smoke; never "
                        "evidence)")
    r.add_argument("--validator", choices=("real", "mock"), default=None,
                   help="protocol validator, independent of the LLM seam: "
                        "'real' = Scribble-java (default for live runs), "
                        "'mock' = crude structural check (default under "
                        "--mock; use for a live-LLM development run where "
                        "the Scribble toolchain is not wired — every "
                        "artifact is labeled validator: mock)")
    r.set_defaults(fn=cmd_run)

    o = sub.add_parser("optimize", help="mine the corpus into a prompt pack")
    o.add_argument("--corpus")
    o.add_argument("--out")
    o.add_argument("--version", default="v1")
    o.add_argument("--include-unfaithful", action="store_true",
                   help="admit valid-but-unfaithful episodes as exemplars "
                        "(measurement only; not recommended)")
    o.set_defaults(fn=cmd_optimize)

    s = sub.add_parser("show-corpus", help="list corpus episodes")
    s.add_argument("--corpus")
    s.set_defaults(fn=cmd_show_corpus)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
