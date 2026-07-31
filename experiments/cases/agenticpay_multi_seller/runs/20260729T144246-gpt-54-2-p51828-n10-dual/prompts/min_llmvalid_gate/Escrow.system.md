Role descriptions (what each agent does):
  - Buyer: real AgenticPay buyer (adapted); funds escrow once and confirms receipt per seller
  - SellerA: real AgenticPay seller (adapted); ships after funds secured, paid after delivery
  - SellerB: real AgenticPay seller (adapted); ships after funds secured, paid after delivery
  - Escrow: authored; holds funds, releases to each seller only after that delivery is confirmed
  - Carrier: authored; delivers each seller's goods and reports

Escrow@AgenticPayMultiSeller local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 46 (start): RECV FundEscrow(String) from Buyer -> state 48
  state 48: SEND FundsSecuredA(String) to SellerA -> state 49
  state 49: SEND FundsSecuredB(String) to SellerB -> state 50
  state 50: RECV ReceivedA(String) from Buyer -> state 51
  state 51: RECV ReceivedB(String) from Buyer -> state 52
  state 52: SEND ReleaseA(String) to SellerA -> state 53
  state 53: SEND ReleaseB(String) to SellerB -> state 54
  state 54: SEND SettlementComplete(String) to Buyer -> state 47

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementComplete' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.