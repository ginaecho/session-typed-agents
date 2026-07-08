# Revised **Requester** skill (STJP-validated)

Fix vs original: send the request to the **Writer** and then wait for the
shipped document from the **DocLead** — do not re-send the request.

```localtype
Writer!DocRequest(String);
DocLead?DocShipped(String);
```
