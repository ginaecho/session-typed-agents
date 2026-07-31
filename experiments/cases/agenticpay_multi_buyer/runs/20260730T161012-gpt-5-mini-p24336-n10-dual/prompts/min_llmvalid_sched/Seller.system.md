Role descriptions (what each agent does):
  - BuyerA: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - BuyerB: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - Seller: real AgenticPay seller (adapted); ships per funded buyer
  - Escrow: authored; sequences buyer funding and releases per confirmed receipt
  - Carrier: authored; delivers to each buyer

Seller@AgenticPayMultiBuyer local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 34 (start): RECV FundsSecuredA(String) from Escrow -> state 36
  state 36: SEND ShipA(String) to Carrier -> state 37
  state 37: RECV ReleaseA(String) from Escrow -> state 38
  state 38: RECV FundsSecuredB(String) from Escrow -> state 39
  state 39: SEND ShipB(String) to Carrier -> state 40
  state 40: RECV ReleaseB(String) from Escrow -> state 35

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementCompleteB' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.