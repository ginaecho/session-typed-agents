# Application-Scene View — making the live demo concrete

*Design proposal. Drafted 2026-06-08. No code yet — this doc decides the shape
before anything is built.*

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. The problem](#1-the-problem)
- [2. The goal](#2-the-goal)
- [3. What we borrow from ZipperChat — and what we deliberately drop](#3-what-we-borrow-from-zipperchat--and-what-we-deliberately-drop)
- [4. Where the "concreteness" comes from — the scene mapping](#4-where-the-concreteness-comes-from--the-scene-mapping)
- [5. A flagship relatable case](#5-a-flagship-relatable-case)
- [6. Integration with the existing demo](#6-integration-with-the-existing-demo)
- [7. Worked mapping (abstract → concrete)](#7-worked-mapping-abstract--concrete)
- [8. Scope & phases](#8-scope--phases)
- [9. Open questions (for you)](#9-open-questions-for-you)
<!-- MENU:END -->

## 1. The problem

The live demo (`experiments/apps/live_demo/`) currently shows the system the way
a **session-types researcher** sees it:

- a Scribble `.scr` protocol (text),
- a **state-machine** graph (EFSM: numbered states, branches, merges),
- a **message-sequence** graph (one swim-lane per role),
- per-arm `off_protocol` / `refinement_failed` verdicts.

For the intended audience — someone deciding whether protocol-typed agents are
worth adopting — this is **too theoretical**. A message like
`HighRevenue(75000)` from `Fetcher` to `RevenueAnalyst` is abstract. Nobody
watching can tell *what just happened in the real world*.

ZipperGen's demo (ZipperChat) reads better not because of its MSC formalism, but
because its examples are **concrete and relatable**: a user emails a team, an
agent checks a calendar, the agent writes back. The viewer instantly maps each
step to something they already understand. **That concreteness is what we want —
not the MSC chart itself.**

## 2. The goal

Add a third view to each case — call it the **Scene** (or **Story**) view — that
renders the *same protocol run* as a concrete, real-world application scenario:

- **Avatars / actors** instead of role names (a person for `User`, a bot for an
  assistant agent, a calendar/inbox/ledger icon for a tool/data role).
- Each protocol message becomes a **plain-language event** with a domain prop:
  > 📧 *Taylor sent an email to the Scheduling Assistant: "Can we meet next week?"*
  > 📅 *The Assistant checked the team calendar — Tue 2pm is free.*
  > ✉️ *The Assistant replied to Taylor proposing Tue 2pm.*
- The scene **animates as the run streams** (driven by the existing
  `events_<arm>.jsonl` SSE feed — no new backend), and a **click on any step**
  opens a detail panel with the real payload, the refinement verdict, and (for
  human steps) the actual context + a response form — the part of ZipperChat
  that lands best.

The Scene view is a **presentation layer over the existing run**. The protocol,
projection, monitor, and verdicts are unchanged; we are only re-skinning the
event stream from "abstract messages" to "a story a non-expert understands".

## 3. What we borrow from ZipperChat — and what we deliberately drop

| ZipperChat idea | Adopt? | How it lands here |
|---|---|---|
| One column per agent ("lifeline") | partial | Keep agents as labelled actors, but lay them out as an **application scene** (inbox / calendar / chat panes), not strict vertical MSC lifelines. |
| Step shown as a **card** (action / message / decision) | **yes** | Each `events_<arm>.jsonl` line → one scene card with an icon + plain-language sentence. |
| **Click a step → detail dialog** with full context | **yes** | Reuse the demo's existing modal: show payload, refinement predicate + pass/fail, and the role's `*.system.md` prompt. |
| **Human control point** → context on the left, response form on the right | **yes (stretch)** | For roles flagged `human: true`, the detail dialog shows the inbound context and a form (demo-only; the form just echoes for now). |
| MSC formalism / vertical time axis as the *primary* visual | **no** | The user explicitly does not want the theoretical MSC; the formal views (state-machine + sequence) stay as separate tabs for the technical audience. |

## 4. Where the "concreteness" comes from — the scene mapping

The only new artefact is a per-case **scene map** that says, for each protocol
message `(sender, receiver, label)`, how to render it concretely. Two options:

**Option A — explicit `scene.yaml` sidecar per case** (recommended):
`experiments/cases/<case>/scene.yaml`, a sibling of `case.yaml`. Hand-authored,
fully under our control, audit-friendly (matches the repo's "sidecar beside the
artefact" convention used for `.refn`).

```yaml
# experiments/cases/scheduling/scene.yaml
title: "Scheduling a team meeting"
actors:
  User:      { display: "Taylor",   avatar: person, kind: human }
  Assistant: { display: "Scheduling Assistant", avatar: bot }
  Calendar:  { display: "Team Calendar", avatar: calendar, kind: tool }
steps:
  - match: { sender: User, receiver: Assistant, label: MeetingRequest }
    icon: email
    text: "{User} emails {Assistant}: \"{payload}\""
  - match: { sender: Assistant, receiver: Calendar, label: CheckAvailability }
    icon: calendar
    text: "{Assistant} checks the {Calendar} for an open slot"
  - match: { sender: Assistant, receiver: User, label: Proposal }
    icon: reply
    text: "{Assistant} replies to {User} proposing {payload}"
```

**Option B — derive it automatically** from `case.yaml`'s `intent` +
`role_descriptions` + label names (an LLM or template turns
`role_descriptions: { Fetcher: "retrieves raw revenue data" }` into an actor and
each `Label` into a sentence). Lower authoring cost, but drifts and needs review
— the same failure mode the retired skills files had (see `experiments/CLAUDE.md`).

**Recommendation:** start with Option A for one flagship relatable case, keep the
schema tiny, and add a graceful fallback so any case *without* a `scene.yaml`
still renders generic cards (`{sender} → {receiver}: {label}({payload})`). That
fallback means the feature ships incrementally without authoring 14 scene maps up
front.

## 5. A flagship relatable case

The current cases (finance, banking, code_review, …) are domain-heavy. To make
the Scene view land, add **one deliberately everyday case** mirroring the
ZipperGen email/calendar story:

- **`scheduling`** — `User` emails a `Assistant`; `Assistant` consults a
  `Calendar` tool; on a free slot it proposes a time, otherwise it asks the user
  to pick again (the branch = the "owned decision"). Terminal label
  `MeetingConfirmed`.

This doubles as the on-ramp: a viewer watches the abstract finance run *and* the
concrete scheduling run side by side and sees they are the same machinery.

## 6. Integration with the existing demo

Minimal, additive — reuse what's already there:

- **New tab** "Scene" next to the current state-machine / sequence views in each
  arm panel and in the stage-2 proto cards (`renderProtoCards`,
  `app.js:2345`).
- **Data source:** the same SSE `run` events the demo already streams
  (`runner.py` tails `events_<arm>.jsonl`; each line already carries
  `sender, receiver, label, payload, violation, step`). No backend change.
- **Renderer:** a new `renderScene(arm, parsedSceneMap)` in `app.js` that, per
  incoming event, looks up the matching `scene.yaml` step and appends an animated
  card; a violation tints the card (reuse the existing red-flash styling).
- **Detail modal:** reuse the existing prompt/protocol modal plumbing
  (`app.js` ~860–950) to show payload + refinement verdict + system prompt.
- **New endpoint:** `GET /api/case/<case_id>/scene` in `app.py` (mirrors the
  existing `/api/case/<case_id>/protocol` + `/refinement` routes) serving
  `scene.yaml` as JSON, with 404 → generic fallback on the client.

Nothing about projection, the monitor, or the verdicts changes. If `scene.yaml`
is absent or malformed, the view degrades to generic cards — never blank.

## 7. Worked mapping (abstract → concrete)

How an existing run line is re-skinned, using the finance case as the example
(`payload` is the hallucinated LLM value the refinement guard checks):

| Stream event (today) | Scene card (proposed) |
|---|---|
| `Fetcher → TaxSpecialist : HighRevenue(75000)` | 💰 *The Data Fetcher reports Q3 revenue of **$75,000** to the Tax Specialist* — green tick: passes `x > 50000` |
| `Fetcher → TaxSpecialist : HighRevenue(10)` | 💰 *…reports revenue of **$10**…* — red: **refinement failed**, `x > 50000` |
| `… off_protocol …` | ⚠ card tinted red: *"This step wasn't allowed at this point in the workflow."* |

The verdict semantics are identical to Set A / Set B today
(`docs/EXPERIMENT_DESIGN_v2.md`); only the wording changes.

## 8. Scope & phases

1. **Phase 1 — schema + one case.** Define `scene.yaml`, author it for the new
   `scheduling` case, build `renderScene` + the `/api/case/<id>/scene` route,
   wire the Scene tab, with the generic fallback. Ship behind the existing tab UI.
2. **Phase 2 — detail dialog + human step.** Click-through detail with payload /
   refinement / prompt; `human: true` actors get the context+form dialog.
3. **Phase 3 — backfill scene maps** for the high-value existing cases
   (`finance`, `banking`, `code_review`) and document the authoring step in
   `experiments/README.md` (alongside "Adding a new case").

## 9. Open questions (for you)

1. **Flagship case** — is `scheduling` (email → calendar → reply) the right
   everyday story, or do you have a preferred domain (travel booking, expense
   approval, support ticket)?
2. **Scene map source** — explicit `scene.yaml` (Option A, recommended) or
   auto-derive from `case.yaml` (Option B)?
3. **Human-in-the-loop** — should the demo's response form be purely visual
   (echo only), or actually feed a value back into the run?
4. **Replace vs. add** — keep the state-machine + sequence views as separate
   tabs for the technical audience (recommended), or make Scene the default and
   hide the formal views behind an "advanced" toggle?
5. **Visual fidelity** — lightweight icon+sentence cards (fast to build), or a
   richer skeuomorphic scene (inbox pane / calendar grid / chat bubbles)?

Once these are settled I'll turn this into an implementation plan and start on
Phase 1.
