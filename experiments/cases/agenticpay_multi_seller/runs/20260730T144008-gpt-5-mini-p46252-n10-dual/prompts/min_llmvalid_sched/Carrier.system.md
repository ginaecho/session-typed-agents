Role descriptions (what each agent does):
  - Buyer: real AgenticPay buyer (adapted); funds escrow once and confirms receipt per seller
  - SellerA: real AgenticPay seller (adapted); ships after funds secured, paid after delivery
  - SellerB: real AgenticPay seller (adapted); ships after funds secured, paid after delivery
  - Escrow: authored; holds funds, releases to each seller only after that delivery is confirmed
  - Carrier: authored; delivers each seller's goods and reports

Carrier@AgenticPayMultiSeller local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 62 (start): RECV ShipA(String) from SellerA -> state 64
  state 64: RECV ShipB(String) from SellerB -> state 65
  state 65: SEND DeliverA(String) to Buyer -> state 66
  state 66: SEND DeliverB(String) to Buyer -> state 63

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementComplete' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.