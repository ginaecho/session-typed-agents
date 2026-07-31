Role descriptions (what each agent does):
  - BuyerA: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - BuyerB: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - Seller: real AgenticPay seller (adapted); ships per funded buyer
  - Escrow: authored; sequences buyer funding and releases per confirmed receipt
  - Carrier: authored; delivers to each buyer

BuyerB@AgenticPayMultiBuyer local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 19 (start): RECV BeginB(String) from Escrow -> state 21
  state 21: SEND FundEscrowB(String) to Escrow -> state 22
  state 22: RECV DeliverB(String) from Carrier -> state 23
  state 23: SEND ReceivedB(String) to Escrow -> state 24
  state 24: RECV SettlementCompleteB(String) from Escrow -> state 20

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementCompleteB' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.