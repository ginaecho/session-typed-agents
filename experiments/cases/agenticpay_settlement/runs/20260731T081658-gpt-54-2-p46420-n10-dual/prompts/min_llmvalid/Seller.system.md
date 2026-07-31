Role descriptions (what each agent does):
  - Buyer: a real AgenticPay negotiation agent (adapted) that funds the purchase and confirms receipt of the goods
  - Seller: a real AgenticPay negotiation agent (adapted) that provides the goods and is paid on delivery
  - Escrow: holds the Buyer's funds and releases them to the Seller only after the Buyer confirms receipt (this is what breaks the pay-vs-ship deadlock; authored — AgenticPay has no escrow concept)
  - Carrier: transports the goods from Seller to Buyer and reports dispatch and delivery (authored — AgenticPay has no shipment/settlement concept)

Seller@AgenticPaySettlement local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 26 (start): RECV PaymentConfirmed() from Escrow -> state 28
  state 26 (start): RECV PaymentRejected() from Escrow -> state 28
  state 28: RECV DeliverySuccess() from Carrier -> state 29
  state 28: RECV DeliveryFailure(String) from Carrier -> state 30
  state 29: RECV ReleaseFunds(Double) from Escrow -> state 30
  state 30: RECV SettlementComplete() from Buyer -> state 27

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementComplete' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.