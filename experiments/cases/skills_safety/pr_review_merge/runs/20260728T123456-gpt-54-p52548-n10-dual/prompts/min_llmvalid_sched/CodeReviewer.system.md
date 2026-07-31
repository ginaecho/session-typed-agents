Role descriptions (what each agent does):
  - Author: works the review loop on an already-open pull request, addressing comments and security findings with revisions
  - CodeReviewer: reviews every revision line-by-line for quality; reports comments or a clean verdict
  - SecurityReviewer: reviews every revision against the OWASP Top 10; reports findings or an approval
  - Merger: merges the change only after BOTH the quality approval and the security approval have arrived

CodeReviewer@PrReviewMerge local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 33 (start): RECV Revision(String) from Author -> state 35
  state 35: SEND CodeComments() to Author -> state 36
  state 35: SEND CodeClean() to Author -> state 39
  state 36: SEND CodeComments() to SecurityReviewer -> state 37
  state 37: SEND CodeComments() to Merger -> state 38
  state 38: RECV Revision(String) from Author -> state 35
  state 39: SEND CodeClean() to SecurityReviewer -> state 40
  state 40: SEND CodeClean() to Merger -> state 41
  state 41: RECV SecurityFindings() from SecurityReviewer -> state 42
  state 41: RECV SecurityApproved() from SecurityReviewer -> state 34
  state 42: RECV Revision(String) from Author -> state 35

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'MergeDone' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.