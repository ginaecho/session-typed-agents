Role descriptions (what each agent does):
  - BuyerA: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - BuyerB: real AgenticPay buyer (adapted); funds escrow, confirms receipt
  - Seller: real AgenticPay seller (adapted); ships per funded buyer
  - Escrow: authored; sequences buyer funding and releases per confirmed receipt
  - Carrier: authored; delivers to each buyer

Escrow@AgenticPayMultiBuyer local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 55 (start): RECV FundEscrowA(String) from BuyerA -> state 57
  state 57: SEND FundsSecuredA(String) to Seller -> state 58
  state 58: RECV ReceivedA(String) from BuyerA -> state 59
  state 59: SEND ReleaseA(String) to Seller -> state 60
  state 60: SEND BeginB(String) to BuyerB -> state 61
  state 61: RECV FundEscrowB(String) from BuyerB -> state 62
  state 62: SEND FundsSecuredB(String) to Seller -> state 63
  state 63: RECV ReceivedB(String) from BuyerB -> state 64
  state 64: SEND ReleaseB(String) to Seller -> state 65
  state 65: SEND SettlementCompleteA(String) to BuyerA -> state 66
  state 66: SEND SettlementCompleteB(String) to BuyerB -> state 56

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementCompleteB' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.