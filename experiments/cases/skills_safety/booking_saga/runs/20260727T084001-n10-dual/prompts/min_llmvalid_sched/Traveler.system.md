Role descriptions (what each agent does):
  - Traveler: the orchestrator that requests the booking and receives the final confirmation
  - Hotel: holds and confirms the room reservation
  - Payment: charges the traveler for the stay

Traveler@BookingSaga local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 24 (start): SEND RequestBooking(String) to Hotel -> state 26
  state 26: RECV BookingConfirmed(String) from Hotel -> state 25

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'BookingConfirmed' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.