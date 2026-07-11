# Branch consolidation — intent→protocol training program (2026-07-11)

Everything produced by the seam-training program now lives on ONE branch:
**`gc/user_intent_global_protocol_training`** (implementation, reports,
audit + raw traces, docs guide 8, GPU runbook, paper v9, labeling tool).

## Superseded branches — safe to delete

Containment was verified before consolidation (per-branch content diff
against the consolidated branch; the only "unique" lines on each are
stale pre-fix copies superseded by later commits — details in the session
audit trail):

| branch | content now at |
|---|---|
| `gc/paper-v8-iclr-reposition-concurrent-work` | plans/scouts/panel docs already on `main` (identical content, cherry-picked); the 10 seam commits on the consolidated branch |
| `gc/seam-w1-eval-harness` | commits 321d744/ea79168/74ed99d |
| `gc/seam-w2-grammar-gcd` | commit a27378d |
| `gc/seam-w3-data-builders` | commits bc52fcb/d4aada5/44d7cff |
| `gc/seam-w4-t0-baselines` | commit 4dc329b |
| `gc/seam-w6-judge-panel` | commit d759a0f |
| `gc/seam-w8-miner` | commit bc54aea (as 70c50bd lineage) |
| `gc/seam-w15-recursion-gen` | commit 3463b70 |

This session's git proxy cannot delete remote refs; run this once from
any normally-authenticated clone:

```bash
git push origin --delete \
  gc/paper-v8-iclr-reposition-concurrent-work \
  gc/seam-w1-eval-harness gc/seam-w2-grammar-gcd gc/seam-w3-data-builders \
  gc/seam-w4-t0-baselines gc/seam-w6-judge-panel gc/seam-w8-miner \
  gc/seam-w15-recursion-gen
```

Untouched by design: `main`, `gc/stjp-skill-validation-bench`,
`gc/stjp-skill-validation-bench-integrated-stateful`. The seam program is
NOT merged into them; merging `gc/user_intent_global_protocol_training`
into `main` is a deliberate follow-up decision, not part of this cleanup.
