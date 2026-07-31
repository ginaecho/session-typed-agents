Role descriptions (what each agent does):
  - BuyerA: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - BuyerB: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - Seller: real AgenticPay seller (adapted); ships per funded buyer
  - Escrow: authored; sequences buyer funding and releases per confirmed receipt
  - Carrier: authored; delivers to each buyer

BuyerA@AgenticPayMultiBuyer local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 6 (start): SEND FundEscrowA(String) to Escrow -> state 8
  state 8: RECV DeliverA(String) from Carrier -> state 9
  state 9: SEND ReceivedA(String) to Escrow -> state 10
  state 10: RECV SettlementCompleteA(String) from Escrow -> state 7

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementCompleteB' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.