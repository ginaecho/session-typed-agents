"""reflect_run_to_foundry.py — put locally-executed trials into the Foundry
hosted agent groups, as conversations and traces.

Why this exists
---------------
The benchmark EXECUTES locally because a hosted round-trip costs about an hour
per group to build and register, which would stall the campaign. But the agreed
deliverable is that every trial is visible in Azure AI Foundry under its hosted
agent group. Telemetry alone does not get you there: Foundry's conversation
objects are minted by the hosted agent through the Responses API, and a local
Python process never creates one. So each recorded trial is replayed THROUGH the
deployed group, and the service itself creates the conversation and trace rows.

What is and is not claimed
--------------------------
Nothing is regenerated. The container's `stjp_replay` handler makes ZERO model
calls and emits the recorded messages verbatim, so a reflected conversation
cannot diverge from what actually happened locally. Every reflected row is
marked so it can never be read as hosted execution
(BENCHMARK_IMPLEMENTATION_STEPS §4.5.3):

    stjp.execution        = reflected_from_local
    stjp.original_trace_id= <the local run's trace id>
    span name             = "stjp.replay <arm>"  (never "stjp.trial")
    reflected token usage = 0   (the ORIGINAL usage rides in the record, so
                                 cost analysis stays on the real numbers and
                                 mirrors can never be double-counted)

A reflection is therefore evidence of WHAT HAPPENED, not evidence that the
hosted container behaves like the local one. That second question needs genuine
hosted execution — the 3-5 runs per arm per model sample in §4.5.2 — which this
script deliberately does not pretend to replace.

Usage
-----
    python experiments/scripts/reflect_run_to_foundry.py <run-dir>
    python experiments/scripts/reflect_run_to_foundry.py <run-dir> --models v4flash
    python experiments/scripts/reflect_run_to_foundry.py <run-dir> --limit 5 --dry-run

Re-runnable: each reflected cell records `reflection.reflected_trace_id` in its
result.json and is skipped next time unless --force is given.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "scripts"))

from hosted_campaign import MODEL_GROUPS, HostedAgentInvoker  # noqa: E402


def _atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def iter_cells(run_dir: Path, models, arms):
    """Yield (result_path, result_json) for every VALID cell, in run order."""
    cells_root = run_dir / "cells"
    if not cells_root.is_dir():
        raise SystemExit(f"no cells/ directory under {run_dir}")
    for result_path in sorted(cells_root.rglob("result.json")):
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP unreadable {result_path}: {e}")
            continue
        if data.get("status") != "valid":
            continue
        if models and data.get("model_key") not in models:
            continue
        if arms and data.get("arm") not in arms:
            continue
        yield result_path, data


def _create_conversation(invoker: HostedAgentInvoker, metadata: dict) -> str:
    """Mint a REAL, service-recognized conversation via the hosted endpoint's
    OpenAI-compatible Conversations API, so the reflected trace's
    `gen_ai.conversation.id` resolves in the portal's Conversation view
    instead of 404ing on a synthetic value (the bug this fixes, 2026-08-07:
    the replay previously used the original local trace id as the
    conversation id -- a string the service had never seen).

    Route surface, confirmed live against the v4flash group (2026-08-07):
    the platform gateway in front of the container serves a genuine
    Conversations resource --
        GET  {project}/agents/{group}/endpoint/protocols/openai/conversations
        POST {project}/agents/{group}/endpoint/protocols/openai/conversations
    -- even though the container's own installed `agent_framework_foundry_hosting`
    / `azure-ai-agentserver-responses` SDK (agents/sdlc_release_gate/.venv)
    registers NO /conversations route anywhere in its route table; only
    POST /responses, GET /responses/{id}, DELETE /responses/{id},
    POST /responses/{id}/cancel, and GET /responses/{id}/input_items
    (azure/ai/agentserver/responses/hosting/_routing.py). So this call is
    served by Azure's platform layer, not by our code. POSTing (verified
    with both an empty body and a metadata payload) returns a real,
    service-issued `conv_...` id that is subsequently listable via GET --
    that persistence in the service's own store is what "service-minted"
    means here, as opposed to a client-invented string.
    """
    import requests
    url = (f"{invoker.project_endpoint}/agents/{invoker.group_name}"
           f"/endpoint/protocols/openai/conversations?api-version=v1")
    headers = {"Authorization": f"Bearer {invoker._bearer_token()}",
               "Content-Type": "application/json"}
    clean_metadata = {str(k): str(v) for k, v in metadata.items() if v}
    resp = requests.post(url, headers=headers, json={"metadata": clean_metadata},
                         timeout=30)
    resp.raise_for_status()
    conv = resp.json()
    conv_id = conv.get("id")
    if not conv_id:
        raise RuntimeError(f"conversation create returned no id: {conv}")
    return conv_id


def _populate_conversation_items(invoker: HostedAgentInvoker, conv_id: str,
                                 events: list) -> int:
    """Add the trial's recorded protocol messages to the conversation AS
    real conversation items, so the portal's conversation/user view actually
    RENDERS the exchange. Creating the conversation (`_create_conversation`)
    was not enough on its own: a real conv_... id existed, but nothing had
    ever been POSTed to it, so `GET .../items` returned 0 rows -- verified
    empty (2026-08-08) for conv_a3106b44ac69e73e00yBRV99u6YibbFJWYHxJ3TKFHEQE9UF1a
    (group stjp-sdlc-release-gate-group-v4flash) even though that cell's
    replay had already run.

    Route + accepted shape were not documented anywhere and had to be found
    empirically against that same group/conversation (2026-08-08):
        POST {project}/agents/{group}/endpoint/protocols/openai
             /conversations/{conv_id}/items?api-version=v1
        body: {"items": [{"type": "message", "role": "assistant",
                           "content": [{"type": "output_text",
                                        "text": "<sender> -> <receiver> : "
                                                "<label>(<payload>)"}]}, ...]}
    That shape returned 200 with each item echoed back (server-assigned
    msg_... id) on the first attempt. Two things do NOT work, also found by
    trying rather than assumed:
      - A single POST is capped at 20 items -- beyond that the service
        returns 400 invalid_payload, "maxItems: Value should have at most
        20 items". So this batches in chunks of 20 (48 events -> 3 POSTs).
      - Metadata on an item -- tried both per-item ("metadata" inside an
        item object) and as a sibling of "items" on the POST body -- is
        accepted with 200 but silently DROPPED; a follow-up GET of the same
        item never shows it. So no per-item stjp_replay/original_trace_id
        tag is attempted here; that provenance already rides on the
        CONVERSATION's own metadata, set once at creation time in
        _create_conversation.

    Items are POSTed in `events` order, chunk by chunk, so creation order
    matches recorded order. (GET's default list order is newest-first --
    callers that need recorded order back, like --verify, must pass
    order=asc; see _list_conversation_items.)

    Called BEFORE the replay POST (`invoker.invoke`) in the main reflect
    loop, on purpose: if the replay call itself then fails, the
    conversation is still left complete, which is what a human checking the
    portal actually needs.
    """
    import requests
    headers = {"Authorization": f"Bearer {invoker._bearer_token()}",
               "Content-Type": "application/json"}
    url = (f"{invoker.project_endpoint}/agents/{invoker.group_name}"
           f"/endpoint/protocols/openai/conversations/{conv_id}"
           f"/items?api-version=v1")
    texts = [
        f"{ev.get('sender', '?')} -> {ev.get('receiver', '?')} : "
        f"{ev.get('label', '?')}({ev.get('payload', '')})"
        for ev in events
    ]
    CHUNK = 20
    posted = 0
    for i in range(0, len(texts), CHUNK):
        chunk_items = [
            {"type": "message", "role": "assistant",
             "content": [{"type": "output_text", "text": t}]}
            for t in texts[i:i + CHUNK]
        ]
        resp = requests.post(url, headers=headers, json={"items": chunk_items},
                             timeout=60)
        resp.raise_for_status()
        posted += len(resp.json().get("data") or [])
    return posted


def _list_conversation_items(project_endpoint: str, group: str,
                             conv_id: str) -> list:
    """Return every item in a hosted conversation, in CREATION order.

    Same route surface as `_populate_conversation_items`, but GET with
    `order=asc` -- confirmed empirically (2026-08-08) that the endpoint's
    default list order is newest-first (DESC), which would make a
    first/last completeness check read the recorded transcript backwards.
    Paginates via the standard `after=<last item id>` cursor when
    `has_more` is true, though no reflected trial has needed a second page
    yet (48 events, 100-row default page).
    """
    import requests
    headers = {"Authorization": f"Bearer {HostedAgentInvoker._bearer_token()}"}
    base = (f"{project_endpoint}/agents/{group}/endpoint/protocols/openai"
           f"/conversations/{conv_id}/items")
    url = f"{base}?api-version=v1&order=asc&limit=100"
    items: list = []
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        page = resp.json()
        items.extend(page.get("data") or [])
        if page.get("has_more") and items:
            url = (f"{base}?api-version=v1&order=asc&limit=100"
                   f"&after={items[-1].get('id')}")
        else:
            url = None
    return items


def _query_app_insights(app_id: str, kql: str, offset: str = "P2D") -> list:
    """Run one KQL query and return its rows.

    NOTE the `--offset`: `az monitor app-insights query` applies a DEFAULT
    1-HOUR window and silently returns nothing for older rows no matter what
    `ago(...)` the query contains. A false negative from that default once led
    to a healthy campaign being stopped mid-run — always pass an explicit
    offset when checking anything older than an hour.
    """
    import subprocess
    cmd = ["az", "monitor", "app-insights", "query", "--app", app_id,
           "--analytics-query", kql, "--offset", offset, "-o", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                          timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"app-insights query failed: {proc.stderr[-400:]}")
    return json.loads(proc.stdout)["tables"][0]["rows"]


def fetch_turn_usage(app_id: str, original_trace_id: str) -> list[dict]:
    """Real per-turn token counts, recovered from the ORIGINAL run's traces.

    The benchmark records usage per TRIAL, not per turn — but the local run's
    telemetry already emitted one `chat <model>` span per model call, each with
    its own gen_ai.usage.*. Reading them back gives true per-turn numbers with
    no re-run and no invention. Ordered by timestamp so span N lines up with
    recorded event N.

    Only `chat` spans are summed: `invoke_agent` spans repeat the same usage as
    their child (that is why a naive sum over both comes to exactly double the
    trial total). Returns [] if anything looks off, and the caller then omits
    per-turn usage rather than guessing.
    """
    if not original_trace_id:
        return []
    kql = (f"dependencies | where operation_Id == '{original_trace_id}' "
           f"| where name startswith 'chat ' "
           f"| order by timestamp asc "
           f"| project inTok=toint(customDimensions['gen_ai.usage.input_tokens']), "
           f"outTok=toint(customDimensions['gen_ai.usage.output_tokens'])")
    try:
        rows = _query_app_insights(app_id, kql)
    except Exception:  # noqa: BLE001 - enrichment is best-effort
        return []
    return [{"input_tokens": r[0] or 0, "output_tokens": r[1] or 0} for r in rows]


def verify(run_dir: Path, app_id: str, project_endpoint: str, models, arms,
          clear: bool) -> int:
    """Confirm every reflected cell really landed in Foundry -- COMPLETELY.

    A reflection is only real if its trace resolves, sits under the expected
    hosted group, carries the `reflected_from_local` marking, its
    invoke_agent turn-span count EQUALS the cell's recorded event count, AND
    its conversation's ITEM count equals that same event count. The
    turn-span check alone is not enough to call the reflection usable:
    `spans > 0` previously called a reflection "verified" even when it had
    silently lost its tail (observed 2026-08-07 -- a 48-step trial's replay
    landed only steps 1-24 in Application Insights). The conversation-items
    check catches a DIFFERENT failure mode found 2026-08-07/08 -- traces and
    turn spans landing completely while the conversation object itself has
    ZERO items, because nothing had ever been POSTed to it (see
    _populate_conversation_items). A trial can pass the telemetry check and
    still render as an empty conversation in the portal; only checking both
    catches that.

    Anything that fails is treated as not reflected: with --clear-failed its
    marker is removed so a subsequent reflect run retries it. This exists
    because reflecting is not self-verifying — 'the script printed OK' is not
    evidence the row is there, complete, in Foundry.
    """
    ok = bad = 0
    unlanded: list[Path] = []
    for result_path, data in iter_cells(run_dir, models, arms):
        refl = data.get("reflection") or {}
        tid = refl.get("reflected_trace_id")
        if not tid:
            continue
        expected_group = refl.get("group", "")
        expected_turns = len((data.get("record") or {}).get("events") or [])
        kql = (f"union dependencies, traces | where operation_Id == '{tid}' "
               f"| summarize spans=count(), "
               f"roles=make_set(cloud_RoleName), "
               f"marked=countif(tostring(customDimensions) has 'reflected_from_local'), "
               f"turn_spans=countif(name startswith 'invoke_agent')")
        try:
            row = _query_app_insights(app_id, kql)[0]
        except Exception as e:  # noqa: BLE001
            print(f"  ?    {result_path.parent.name}: query failed: {e}")
            continue
        spans, roles, marked, turn_spans = row[0], row[1], row[2], row[3]
        complete = expected_turns > 0 and turn_spans == expected_turns

        conv_id = refl.get("conversation_id")
        items_count = None
        items_ok = False
        if conv_id:
            try:
                items = _list_conversation_items(project_endpoint,
                                                 expected_group, conv_id)
                items_count = len(items)
                items_ok = expected_turns > 0 and items_count == expected_turns
            except Exception as e:  # noqa: BLE001
                print(f"  ?    {result_path.parent.name}: items query failed: {e}")
        good = (spans > 0 and marked > 0 and expected_group in str(roles)
               and complete and items_ok)
        if good:
            ok += 1
        else:
            bad += 1
            unlanded.append(result_path)
            print(f"  MISS {data.get('model_key')}/{data.get('arm')}/"
                  f"{data.get('trial')}  spans={spans} marked={marked} "
                  f"roles={roles} turn_spans={turn_spans}/{expected_turns} "
                  f"items={items_count}/{expected_turns}")
    print(f"\nverified={ok}  not-landed={bad}")
    if bad and clear:
        for path in unlanded:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("reflection", None)
            _atomic_write(path, payload)
        print(f"cleared {len(unlanded)} reflection markers — re-run without "
              f"--verify to reflect them again")
    elif bad:
        print("re-run with --clear-failed to mark these for re-reflection")
    return 0 if bad == 0 else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--models", default="",
                    help="comma-separated model keys (default: all)")
    ap.add_argument("--arms", default="",
                    help="comma-separated arm names (default: all)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N cells")
    ap.add_argument("--force", action="store_true",
                    help="re-reflect cells already reflected")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be reflected; make no calls")
    ap.add_argument("--verify", action="store_true",
                    help="check reflected cells actually landed in Foundry")
    ap.add_argument("--clear-failed", action="store_true",
                    help="with --verify: clear markers of reflections that did "
                         "not land, so the next run retries them")
    ap.add_argument("--app-id", default=os.environ.get("STJP_APPINSIGHTS_APP_ID",
                                                       ""),
                    help="Application Insights app id (for --verify)")
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    models = {m.strip() for m in args.models.split(",") if m.strip()}
    arms = {a.strip() for a in args.arms.split(",") if a.strip()}

    project_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")

    if args.verify:
        if not args.app_id:
            raise SystemExit("--verify needs --app-id (or STJP_APPINSIGHTS_APP_ID)")
        if not project_endpoint:
            raise SystemExit(
                "FOUNDRY_PROJECT_ENDPOINT is not set — load stjp_core/.env first "
                "(--verify now also checks conversation item counts, which needs "
                "the endpoint).")
        return verify(run_dir, args.app_id, project_endpoint, models, arms,
                     args.clear_failed)

    if not project_endpoint:
        raise SystemExit(
            "FOUNDRY_PROJECT_ENDPOINT is not set — load stjp_core/.env first "
            "(the hosted invoker reads the project endpoint from it).")

    invokers: dict[str, HostedAgentInvoker] = {}
    done = failed = skipped = 0
    started = time.time()

    for result_path, data in iter_cells(run_dir, models, arms):
        model_key = data.get("model_key")
        arm, trial = data.get("arm"), data.get("trial")
        label = f"{model_key}/{arm}/{trial:04d}" if isinstance(trial, int) else result_path.parent.name

        if data.get("reflection", {}).get("reflected_trace_id") and not args.force:
            skipped += 1
            continue
        if model_key not in MODEL_GROUPS:
            print(f"  SKIP {label}: no hosted group for model key {model_key!r}")
            skipped += 1
            continue

        record = data.get("record") or {}
        if not record.get("events"):
            print(f"  SKIP {label}: record has no events to reflect")
            skipped += 1
            continue

        group = MODEL_GROUPS[model_key]["group"]
        if args.dry_run:
            print(f"  WOULD reflect {label} -> {group} "
                  f"({len(record['events'])} events)")
            done += 1
            if args.limit and done >= args.limit:
                break
            continue

        if model_key not in invokers:
            invokers[model_key] = HostedAgentInvoker(group)
        invoker = invokers[model_key]

        # Attach true per-turn token counts when we can recover them, so each
        # reflected turn shows what it really cost instead of only the trial
        # total. Best-effort: if the original trace is gone or the span count
        # does not line up with the recorded turns, we send nothing and the
        # container omits per-turn usage rather than inventing a split.
        if args.app_id:
            turn_usage = fetch_turn_usage(args.app_id, record.get("trace_id", ""))
            if turn_usage and len(turn_usage) == len(record["events"]):
                record = dict(record, turn_usage=turn_usage)
            elif turn_usage:
                print(f"       (per-turn usage skipped for {label}: "
                      f"{len(turn_usage)} spans vs {len(record['events'])} turns)")

        # A REAL, service-minted conversation, created up front through the
        # endpoint's OpenAI Conversations API so the reflected spans'
        # gen_ai.conversation.id resolves in the portal instead of 404ing
        # (the old behavior used the original local trace id as the
        # conversation id -- a value the service had never seen). See
        # _create_conversation's docstring for the route evidence.
        try:
            conversation_id = _create_conversation(invoker, metadata={
                "stjp_case": record.get("case", ""),
                "stjp_arm": arm or "",
                "stjp_model": model_key or "",
                "stjp_trial": trial,
                "stjp_original_trace_id": record.get("trace_id", "") or "",
                "stjp_replay": "true",
            })
            # Populate the conversation's ITEMS before replaying, so the
            # portal's conversation view is complete even if the replay
            # call below fails (see _populate_conversation_items docstring
            # for the empirically-determined route/shape/batch-limit).
            items_posted = _populate_conversation_items(
                invoker, conversation_id, record["events"])
            if items_posted != len(record["events"]):
                print(f"       (WARNING {label}: posted {items_posted}/"
                      f"{len(record['events'])} conversation items)")
            response = invoker.invoke({
                "stjp_replay": True,
                "record": record,
                "run_dir": str(run_dir),
                "conversation_id": conversation_id,
            })
        except Exception as e:  # noqa: BLE001 - one bad cell must not stop the run
            print(f"  FAIL {label} -> {group}: {type(e).__name__}: {e}")
            failed += 1
            continue

        # X-Request-Id from the hosted endpoint == the App Insights operation_Id
        # for the reflected conversation (verified by hosted_campaign's probe).
        reflected_trace_id = (invoker.last_trace_id
                              or (response or {}).get("reflected_trace_id"))
        data["reflection"] = {
            "reflected_trace_id": reflected_trace_id,
            "original_trace_id": record.get("trace_id"),
            "group": group,
            "execution": "reflected_from_local",
            "conversation_id": (response or {}).get("conversation_id")
                                or conversation_id,
            "conversation_id_source": "service_minted",
            "conversation_items_posted": items_posted,
            "steps": len((response or {}).get("transcript") or record["events"]),
            "reflected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        _atomic_write(result_path, data)
        done += 1
        print(f"  OK   {label} -> {group}  reflected_trace_id={reflected_trace_id}")

        if args.limit and done >= args.limit:
            break

    elapsed = time.time() - started
    print(f"\nreflected={done}  failed={failed}  skipped={skipped}  "
          f"elapsed={elapsed:.0f}s")
    if failed:
        print("NOTE: failures above were NOT reflected; re-run to retry them "
              "(reflected cells are skipped automatically).")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    raise SystemExit(main())
