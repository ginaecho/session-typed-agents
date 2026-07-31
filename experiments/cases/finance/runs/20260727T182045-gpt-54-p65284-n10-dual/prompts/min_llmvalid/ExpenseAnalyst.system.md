Role descriptions (what each agent does):
  - Fetcher: retrieves raw revenue data on request
  - RevenueAnalyst: analyzes revenue, classifying it as high (>$50k) or standard
  - ExpenseAnalyst: analyzes expense data
  - Writer: composes the final quarterly report from approved analyses and delivers it back to the user (the Fetcher)
  - TaxVerifier: verifies the tax audit is correct before approved figures land in the report
  - TaxSpecialist: audits high-revenue items when an audit is requested

ExpenseAnalyst@QuarterlyFinanceReport local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 41 (start): SEND ExpenseData(Double) to RevenueAnalyst -> state 42

Payload guards (HARD; runtime rejects violations):
  -> RevenueAnalyst.ExpenseData (type float): require x >= 0

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'GenerateReport' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.