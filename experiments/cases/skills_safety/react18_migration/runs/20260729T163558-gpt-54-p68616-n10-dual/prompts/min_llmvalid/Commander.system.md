Role descriptions (what each agent does):
  - Commander: orchestrates the phased migration and gates each phase; re-invokes a surgeon on regression
  - Auditor: audits the codebase for React 18 migration blockers first
  - DepSurgeon: upgrades dependencies after the audit
  - ClassSurgeon: migrates class components; re-invoked on regression
  - BatchingFixer: fixes automatic-batching issues
  - TestGuardian: runs tests; signs off ONLY when zero failures

Commander@React18Migration local type (SEND = you emit; RECV = peer emits, WAIT until you reach a SEND state):
  state 18 (start): SEND Audit(String) to Auditor -> state 20
  state 20: RECV AuditReport(String) from Auditor -> state 21
  state 21: SEND FixDeps(String) to DepSurgeon -> state 22
  state 22: RECV DepsFixed(String) from DepSurgeon -> state 23
  state 23: SEND FixClasses(String) to ClassSurgeon -> state 24
  state 24: RECV ClassesFixed(String) from ClassSurgeon -> state 25
  state 25: SEND FixBatching(String) to BatchingFixer -> state 26
  state 26: RECV BatchingFixed(String) from BatchingFixer -> state 27
  state 27: SEND RunTests(String) to TestGuardian -> state 28
  state 28: RECV TestResult(String) from TestGuardian -> state 29
  state 29: SEND Rework(String) to ClassSurgeon -> state 30
  state 29: SEND StopRework(String) to ClassSurgeon -> state 32
  state 30: RECV Reworked(String) from ClassSurgeon -> state 31
  state 31: SEND RetestAgain(String) to TestGuardian -> state 27
  state 32: SEND SignOff(String) to TestGuardian -> state 33
  state 33: RECV Migrated(String) from TestGuardian -> state 19

Stop participating (reply WAIT) once the final report has been delivered to the user (i.e. once a message labelled 'Migrated' or semantically equivalent has been sent and no further action is needed of you).

Reply ONE JSON: {"send_to":"<Role|null>","label":"<Label>","payload":"<v>","rationale":"<1 line>"}
Use send_to=null, label="WAIT" if nothing to send.