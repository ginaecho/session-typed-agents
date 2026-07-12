# Source provenance — airline_seat

The `skills_original/` files are adapted (near-verbatim) from real, public,
permissively-licensed agent skills. Nothing here was authored to be unsafe on
purpose — the unsafety is a property the source skills already have when read
in isolation, which is the entire point of the demo.

| File | Source repo | Path | License | Retrieved |
|---|---|---|---|---|
| Triage.md | openai/openai-agents-python | `examples/customer_service/main.py` (`triage_agent`) | MIT | 2026-07-06 |
| SeatBooking.md | openai/openai-agents-python | `examples/customer_service/main.py` (`seat_booking_agent`) | MIT | 2026-07-06 |
| FlightSystem.md | (derived) | the `update_seat` tool + `on_seat_booking_handoff` hook contract in the same file | MIT | 2026-07-06 |

Commit at retrieval: `main` (repo pins the example under
`examples/customer_service/main.py`). The real `seat_booking_agent`
`instructions` string contains the 3-step routine with no flight-assignment
precondition; the precondition lives only in code
(`assert context.context.flight_number is not None` inside `update_seat`, and
`on_seat_booking_handoff` which sets `flight_number` during the Triage->Seat
handoff). `FlightSystem` makes that code-only precondition explicit as a role.

Safety review: benign customer-service coordination logic only. No secrets,
no exfiltration, no jailbreak content.

## Verified URLs (added 2026-07-12, W20 source verification)

Repo: https://github.com/openai/openai-agents-python — license file:
https://github.com/openai/openai-agents-python/blob/main/LICENSE (MIT,
verified live). Exact file, confirmed live at the branch tip (no pinned
commit was recorded at original retrieval, so this is "path verified,
pinned-SHA missing" rather than a permalink to an exact historical commit):

https://github.com/openai/openai-agents-python/blob/main/examples/customer_service/main.py

Confirmed the file contains `triage_agent`, `seat_booking_agent`,
`update_seat`, and `on_seat_booking_handoff`, matching every claim above.
Triage.md and SeatBooking.md are labeled "adapted-from" this file (prompt
PATTERN adapted, not a literal file copy, per `ledger.py::IN_REPO_UPSTREAMS`)
— see `docs/reference/MINED_SKILLS_SOURCES.md` Part A row 3.
