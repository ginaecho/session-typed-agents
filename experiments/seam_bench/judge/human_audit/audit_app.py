"""audit_app.py — Streamlit UI for the §6 human-audit packet.

Run:
    streamlit run experiments/seam_bench/judge/human_audit/audit_app.py

Shows ONE card at a time (intent prose + syntax-highlighted protocol code
block), a progress bar, and three buttons: Fit / No fit / Unsure, plus an
optional free-text note. Clicking a button appends one line to
`labels.jsonl` (append-only — never overwritten) and auto-advances to the
next unlabeled item. Restarting the app re-reads `labels.jsonl` and resumes
at the first item with no label, so a session can be split across sittings
(the plan explicitly allows this: "~4-6 hours, split across two sittings").

BLINDING BY CONSTRUCTION: this module never opens `packet_key.jsonl` and
has no import of anything that could reveal a stratum or a model verdict.
It reads exactly one input file, `audit_packet.jsonl`, whose only fields
are {item_id, order_index, intent, protocol_text} (see packet_builder.py's
PACKET_FIELDS) — there is nothing in scope for this file to leak even if
it wanted to. Keep it that way: do not import packet_builder's stratum
helpers or packet_key.jsonl here.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import streamlit as st

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PACKET_PATH = HERE / "audit_packet.jsonl"
LABELS_PATH = HERE / "labels.jsonl"

LABEL_CHOICES = ("fit", "no_fit", "unsure")
LABEL_BUTTON_TEXT = {"fit": "Fit (1)", "no_fit": "No fit (2)", "unsure": "Unsure (3)"}

# Small JS shim: keys 1/2/3 click the matching button by its visible text.
# Streamlit renders st.button as a plain <button>; this only *dispatches a
# click* on an existing button already in the page — it adds no separate
# submission path and does not touch labels.jsonl directly.
_HOTKEY_JS = """
<script>
const doc = window.parent.document;
doc.addEventListener('keydown', function(e) {
  const tag = (e.target && e.target.tagName) || '';
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;
  const map = {'1': 'Fit (1)', '2': 'No fit (2)', '3': 'Unsure (3)'};
  const label = map[e.key];
  if (!label) return;
  const buttons = doc.querySelectorAll('button');
  for (const b of buttons) {
    if (b.innerText.trim() === label) { b.click(); break; }
  }
});
</script>
"""


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_packet() -> list[dict]:
    if not PACKET_PATH.exists():
        st.error(
            f"No packet found at {PACKET_PATH}. Build it first:\n\n"
            "python -m experiments.seam_bench.judge.human_audit.packet_builder")
        st.stop()
    return read_jsonl(PACKET_PATH)


def labeled_ids() -> set[str]:
    return {rec["item_id"] for rec in read_jsonl(LABELS_PATH)}


def next_unlabeled_index(packet: list[dict], done: set[str]) -> Optional[int]:
    for i, item in enumerate(packet):
        if item["item_id"] not in done:
            return i
    return None


def session_stats(done_records: list[dict]) -> tuple[int, float]:
    n = len(done_records)
    if n == 0:
        return 0, 0.0
    total_seconds = sum(r.get("seconds_spent", 0.0) for r in done_records)
    return n, total_seconds / n


def submit_label(item_id: str, label: str, note: str, seconds_spent: float) -> None:
    already = labeled_ids()
    if item_id in already:
        return  # idempotent: never write a second line for the same item
    append_jsonl(LABELS_PATH, {
        "item_id": item_id,
        "label": label,
        "note": note or "",
        "seconds_spent": round(seconds_spent, 1),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


def main() -> None:
    st.set_page_config(page_title="Seam-Bench human audit", layout="centered")
    st.components.v1.html(_HOTKEY_JS, height=0, width=0)

    packet = load_packet()
    done_records = read_jsonl(LABELS_PATH)
    done = {r["item_id"] for r in done_records}

    idx = next_unlabeled_index(packet, done)

    with st.sidebar:
        st.subheader("Session stats")
        n_done, mean_sec = session_stats(done_records)
        st.metric("Labeled", f"{n_done} / {len(packet)}")
        st.metric("Mean seconds / item", f"{mean_sec:.1f}" if n_done else "-")
        st.caption(
            "It's fine to close this tab and come back later — labeling "
            "picks up right where you left off. Split across two sittings "
            "is fine (that's the plan, not a shortcut).")
        st.caption(
            "This sidebar intentionally shows nothing about what kind of "
            "item is on screen — stay blind to keep your judgments honest.")

    if idx is None:
        st.success(f"All {len(packet)} items labeled. Thank you.")
        st.write(
            "Next step: run\n\n"
            "    python -m experiments.seam_bench.judge.human_audit.analysis")
        return

    item = packet[idx]
    st.progress((idx) / len(packet), text=f"Item {idx + 1} of {len(packet)}")

    st.markdown("### Intent")
    st.markdown(item["intent"])

    st.markdown("### Protocol")
    st.code(item["protocol_text"], language="java")

    # Track how long this specific card has been on screen.
    if st.session_state.get("_shown_item_id") != item["item_id"]:
        st.session_state["_shown_item_id"] = item["item_id"]
        st.session_state["_shown_at"] = time.time()

    note = st.text_input("Optional note", key=f"note_{item['item_id']}")

    col1, col2, col3 = st.columns(3)
    clicked = None
    with col1:
        if st.button(LABEL_BUTTON_TEXT["fit"], use_container_width=True):
            clicked = "fit"
    with col2:
        if st.button(LABEL_BUTTON_TEXT["no_fit"], use_container_width=True):
            clicked = "no_fit"
    with col3:
        if st.button(LABEL_BUTTON_TEXT["unsure"], use_container_width=True):
            clicked = "unsure"

    if clicked is not None:
        elapsed = time.time() - st.session_state.get("_shown_at", time.time())
        submit_label(item["item_id"], clicked, note, elapsed)
        st.rerun()


if __name__ == "__main__":
    main()
