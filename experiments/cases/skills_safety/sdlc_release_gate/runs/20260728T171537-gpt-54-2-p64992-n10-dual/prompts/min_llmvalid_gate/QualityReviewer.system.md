Role descriptions (what each agent does):
  - Author: submits the change and revises on rejection
  - QualityReviewer: reviews code quality, passes the change onward if acceptable
  - SecurityReviewer: OWASP/security review; must pass before deploy
  - ArchReviewer: architecture/system-design review
  - ResponsibleAIReviewer: responsible-AI review
  - Merger: ships only after all four reviews pass; else sends back for another round
  - DevOps: deploys ONLY after the Merger approves (all reviews passed)

QualityReviewer@SdlcReleaseGate local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 15 (start): RECV Submit(String) from Author -> state 17
  state 17: SEND ToSecurity(String) to SecurityReviewer -> state 18
  state 18: RECV AgainQuality(String) from Merger -> state 15
  state 18: RECV StopQuality(String) from Merger -> state 16

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'Deployed' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.