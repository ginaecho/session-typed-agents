Role descriptions (what each agent does):
  - Commander: orchestrates the phased migration and gates each phase; re-invokes a surgeon on regression
  - Auditor: audits the codebase for React 18 migration blockers first
  - DepSurgeon: upgrades dependencies after the audit
  - ClassSurgeon: migrates class components; re-invoked on regression
  - BatchingFixer: fixes automatic-batching issues
  - TestGuardian: runs tests; signs off ONLY when zero failures

BatchingFixer@React18Migration local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 68 (start): RECV FixBatching(String) from Commander -> state 70
  state 70: SEND BatchingFixed(String) to Commander -> state 69

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'Migrated' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.