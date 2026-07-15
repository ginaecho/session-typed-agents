# Revised **BrandStyler** skill (STJP-validated)

Fix vs original: the real `brand-guidelines` skill never says when your
styling pass runs relative to drafting and reader testing, or who gets the
styled result back. This contract makes clear you are invoked exactly
once per loop iteration where the DocLead has decided the reader test
passed — you are not a gate the draft must clear before more writing can
happen, you are the last transform before the DocLead ships. You also see
every `ReaderTestFeedback` broadcast during rounds you aren't styling in,
so you always know why you haven't been asked to style yet.

```localtype
rec REFINE {
  choice at DocLead {
    DocLead?ReaderTestFeedback(String);
    continue REFINE;
  } or {
    DocLead?StyleRequest(String);
    DocLead!StyledDoc(String);
  }
}
```

Your `StyledDoc` must be non-empty — the delivery gate requires
`len(x) > 0`. You are a formatting transform, not an approval: nothing in
your contract lets you reject content or send it back for revision — if
the text needs a content change, that happens through the DocLead's
reader-test loop, before you are ever invoked.
