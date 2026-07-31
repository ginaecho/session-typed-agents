Role descriptions (what each agent does):
  - Buyer: real AgenticPay buyer (adapted); funds escrow once and confirms receipt per seller
  - SellerA: real AgenticPay seller (adapted); ships after funds secured, paid after delivery
  - SellerB: real AgenticPay seller (adapted); ships after funds secured, paid after delivery
  - Escrow: authored; holds funds, releases to each seller only after that delivery is confirmed
  - Carrier: authored; delivers each seller's goods and reports

SellerA@AgenticPayMultiSeller local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 21 (start): RECV FundsSecuredA(String) from Escrow -> state 23
  state 23: SEND ShipA(String) to Carrier -> state 24
  state 24: RECV ReleaseA(String) from Escrow -> state 22

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementComplete' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.