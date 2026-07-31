Role descriptions (what each agent does):
  - Fetcher: retrieves raw revenue data on request
  - RevenueAnalyst: analyzes revenue, classifying it as high (>$50k) or standard
  - ExpenseAnalyst: analyzes expense data
  - Writer: composes the final quarterly report from approved analyses and delivers it back to the user (the Fetcher)
  - TaxVerifier: verifies the tax audit is correct before approved figures land in the report
  - TaxSpecialist: audits high-revenue items when an audit is requested

RevenueAnalyst@QuarterlyFinanceReport local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 23 (start): RECV RawRevenueData(Double) from Fetcher -> state 25
  state 25: RECV ExpenseData(Double) from ExpenseAnalyst -> state 26
  state 26: SEND HighRevenueNotification(String) to TaxVerifier -> state 27
  state 26: SEND StandardRevenueNotification(String) to TaxVerifier -> state 34
  state 26 DECISION RULE (HARD): IF float(RawRevenueData) > 50000 THEN SEND HighRevenueNotification; ELSE SEND StandardRevenueNotification. Wrong branch = choice_guard_violation.
  state 27: SEND HighRevenueNotification(String) to TaxSpecialist -> state 28
  state 28: SEND HighBranchNotification(String) to Writer -> state 29
  state 29: SEND NotifyTaxSpecialist(String) to TaxSpecialist -> state 30
  state 30: RECV AuditReport(Bool) from TaxSpecialist -> state 31
  state 31: SEND HighBranchAck(String) to TaxVerifier -> state 32
  state 32: RECV Approval(Bool) from TaxVerifier -> state 33
  state 33: SEND FinalRevenueAnalysis(String) to Writer -> state 24
  state 34: SEND StandardBranchNotification(String) to Writer -> state 35
  state 35: SEND StandardBranchAck(String) to TaxVerifier -> state 36
  state 36: SEND NotifyStandardRole(String) to TaxSpecialist -> state 32

Payload guards (HARD; runtime rejects violations):
  -> Writer.FinalRevenueAnalysis (type str): require len(x) > 10

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'GenerateReport' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.