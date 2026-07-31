Role descriptions (what each agent does):
  - BuyerA: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - BuyerB: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - Seller: real AgenticPay seller (adapted); ships per funded buyer
  - Escrow: authored; sequences buyer funding and releases per confirmed receipt
  - Carrier: authored; delivers to each buyer

Carrier@AgenticPayMultiBuyer local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 74 (start): RECV ShipA(String) from Seller -> state 76
  state 76: SEND DeliverA(String) to BuyerA -> state 77
  state 77: RECV ShipB(String) from Seller -> state 78
  state 78: SEND DeliverB(String) to BuyerB -> state 75

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementCompleteB' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.