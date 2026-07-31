Role descriptions (what each agent does):
  - Researcher: gathers source material and hands a research brief to the Writer
  - Writer: writes the article from the research brief and submits it for editing
  - Editor: reviews the draft for accuracy/compliance and approves it before it can be published
  - Publisher: publishes the article only after the Editor has approved it

Researcher@ContentPipeline local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 21 (start): SEND ResearchBrief(String) to Writer -> state 22

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'Published' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.