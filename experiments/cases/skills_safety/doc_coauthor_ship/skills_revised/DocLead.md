# Revised **DocLead** skill (STJP-validated)

Fix vs original: the real `doc-coauthoring` skill's loop language ("Continue
iterating until user is satisfied", "Loop back to refinement for
problematic sections") never says who else needs to hear about each round,
or when styling fits relative to the loop. This contract makes you the
one true gate: you decide, every round, whether to send reader-test
feedback (and wait for a revision) or to conclude the reader test passed
and request styling — and either decision is broadcast to every other
role, so the whole team always knows which state the loop is in. Only
after the styled document comes back do you ship.

```localtype
Requester?DocRequest(String);
Writer?Draft(String);
rec REFINE {
  choice at self {
    Writer!ReaderTestFeedback(String);
    Requester!ReaderTestFeedback(String);
    BrandStyler!ReaderTestFeedback(String);
    Writer?RevisedDraft(String);
    continue REFINE;
  } or {
    BrandStyler!StyleRequest(String);
    Writer!StyleRequest(String);
    Requester!StyleRequest(String);
    BrandStyler?StyledDoc(String);
  }
}
Requester!DocShipped(String);
```

Your `DocShipped` must be non-empty — the delivery gate requires
`len(x) > 0`. This is a positive presence check, not a keyword ban: an
honest shipped document does not need to contain any particular word
(there is no reason it should say "SHIPPED" anywhere in its own text), so
the gate only asks that real content actually went out, not that it
matches a phrase.
