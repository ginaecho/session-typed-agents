Role descriptions (what each agent does):
  - Traveler: the orchestrator that requests the booking and receives the final confirmation
  - Hotel: holds and confirms the room reservation
  - Payment: charges the traveler for the stay

Hotel@BookingSaga local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 6 (start): RECV RequestBooking(String) from Traveler -> state 8
  state 8: SEND RoomHeld(String) to Payment -> state 9
  state 9: RECV PaymentCaptured(Double) from Payment -> state 10
  state 10: SEND BookingConfirmed(String) to Traveler -> state 7

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'BookingConfirmed' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.