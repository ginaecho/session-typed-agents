# Revised **Requester** skill (STJP-validated)

Fix vs original: the derived original says you brief the writing team and
wait to be handed the finished document, but it never says the brief has
to go to *both* the Writer and the DocLead, or that you'll be pulled into
reader-test rounds along the way. This contract makes both of those
explicit: your `DocRequest` reaches the DocLead directly (so it knows the
loop is starting even before a draft exists), and you stay live through
every round of the loop — either answering reader-test feedback or hearing
that styling is underway — until the final `DocShipped` arrives.

```localtype
Writer!DocRequest(String);
DocLead!DocRequest(String);
rec REFINE {
  choice at DocLead {
    DocLead?ReaderTestFeedback(String);
    continue REFINE;
  } or {
    DocLead?StyleRequest(String);
  }
}
DocLead?DocShipped(String);
```
