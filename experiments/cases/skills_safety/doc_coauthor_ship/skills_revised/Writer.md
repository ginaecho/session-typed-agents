# Revised **Writer** skill (STJP-validated)

Fix vs original: the real `internal-comms` skill is a single-pass template
lookup — it says nothing about who receives the draft or what happens if
it comes back with feedback. This contract closes the old case's biggest
hole: your `Draft` goes straight to the DocLead (not through a reviewer
that never sees the actual text), and every `RevisedDraft` you produce
after reader-test feedback goes back to the DocLead too, for as many
rounds as the loop runs.

```localtype
Requester?DocRequest(String);
DocLead!Draft(String);
rec REFINE {
  choice at DocLead {
    DocLead?ReaderTestFeedback(String);
    DocLead!RevisedDraft(String);
    continue REFINE;
  } or {
    DocLead?StyleRequest(String);
  }
}
```

Your `Draft` and every `RevisedDraft` must be non-empty — the delivery
gate requires `len(x) > 0` and will reject an empty draft.
