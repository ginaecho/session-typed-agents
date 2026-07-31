Role descriptions (what each agent does):
  - Buyer: a real AgenticPay negotiation agent (adapted) that funds the purchase and confirms receipt of the goods
  - Seller: a real AgenticPay negotiation agent (adapted) that provides the goods and is paid on delivery
  - Escrow: holds the Buyer's funds and releases them to the Seller only after the Buyer confirms receipt (this is what breaks the pay-vs-ship deadlock; authored — AgenticPay has no escrow concept)
  - Carrier: transports the goods from Seller to Buyer and reports dispatch and delivery (authored — AgenticPay has no shipment/settlement concept)

Carrier@AgenticPaySettlement local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 70 (start): RECV PaymentConfirmed() from Escrow -> state 72
  state 70 (start): RECV PaymentRejected() from Escrow -> state 73
  state 72: RECV RequestShipment() from Escrow -> state 73
  state 73: SEND DeliverySuccess() to Buyer -> state 74
  state 73: SEND DeliveryFailure(String) to Buyer -> state 77
  state 74: SEND DeliverySuccess() to Seller -> state 75
  state 75: SEND DeliverySuccess() to Escrow -> state 76
  state 76: RECV SettlementComplete() from Buyer -> state 71
  state 77: SEND DeliveryFailure(String) to Seller -> state 78
  state 78: SEND DeliveryFailure(String) to Escrow -> state 76

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'SettlementComplete' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.