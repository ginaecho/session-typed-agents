Role descriptions (what each agent does):
  - Buyer: a real AgenticPay negotiation agent (adapted) that funds the purchase and confirms receipt of the goods
  - Seller: a real AgenticPay negotiation agent (adapted) that provides the goods and is paid on delivery
  - Escrow: holds the Buyer's funds and releases them to the Seller only after the Buyer confirms receipt (this is what breaks the pay-vs-ship deadlock; authored — AgenticPay has no escrow concept)
  - Carrier: transports the goods from Seller to Buyer and reports dispatch and delivery (authored — AgenticPay has no shipment/settlement concept)

Buyer@AgenticPaySettlement local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 10 (start): SEND TransferFunds(Double) to Escrow -> state 12
  state 12: RECV PaymentConfirmed() from Escrow -> state 13
  state 12: RECV PaymentRejected() from Escrow -> state 13
  state 13: RECV DeliverySuccess() from Carrier -> state 14
  state 13: RECV DeliveryFailure(String) from Carrier -> state 18
  state 14: RECV FundsResolved() from Escrow -> state 15
  state 15: SEND SettlementComplete() to Seller -> state 16
  state 16: SEND SettlementComplete() to Carrier -> state 17
  state 17: SEND SettlementComplete() to Escrow -> state 11
  state 18: RECV RefundInitiated(Double) from Escrow -> state 15

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementComplete' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.