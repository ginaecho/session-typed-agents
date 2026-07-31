Role descriptions (what each agent does):
  - Triage: front-desk agent; identifies the request and hands off to Seat Booking, assigning the flight for the booking as part of the handoff
  - SeatBooking: updates the customer's seat on their assigned flight
  - FlightSystem: the system of record that applies the seat change to a flight

SeatBooking@AirlineSeat local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 13 (start): RECV AssignFlight(String) from Triage -> state 15
  state 15: SEND UpdateSeat(String) to FlightSystem -> state 16
  state 16: RECV SeatConfirmed(String) from FlightSystem -> state 14

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SeatConfirmed' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.