Role descriptions (what each agent does):
  - Coder: writes code to satisfy the task and submits it for review
  - Reviewer: inspects the code for safety/correctness and approves it before execution
  - Executor: runs the code only after the Reviewer has approved it, then returns the result

Reviewer@CodeExecution local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 20 (start): RECV SubmitCode(String) from Coder -> state 22
  state 22: SEND Approve(String) to Executor -> state 21

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'ResultReturned' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.