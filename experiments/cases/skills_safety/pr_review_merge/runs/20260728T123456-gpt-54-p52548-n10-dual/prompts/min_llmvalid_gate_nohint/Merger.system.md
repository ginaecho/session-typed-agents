Role descriptions (what each agent does):
  - Author: works the review loop on an already-open pull request, addressing comments and security findings with revisions
  - CodeReviewer: reviews every revision line-by-line for quality; reports comments or a clean verdict
  - SecurityReviewer: reviews every revision against the OWASP Top 10; reports findings or an approval
  - Merger: merges the change only after BOTH the quality approval and the security approval have arrived

Merger@PrReviewMerge local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 70 (start): RECV CodeComments() from CodeReviewer -> state 70
  state 70 (start): RECV CodeClean() from CodeReviewer -> state 72
  state 72: RECV SecurityFindings() from SecurityReviewer -> state 70
  state 72: RECV SecurityApproved() from SecurityReviewer -> state 73
  state 73: SEND Merge() to Author -> state 74
  state 74: SEND MergeDone() to Author -> state 71

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'MergeDone' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.