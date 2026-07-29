# Source provenance — sdlc_release_gate

Seven `skills_original/*.md` files fetched verbatim (HTTP 200, 2026-07-28) from
**github/awesome-copilot** (`main`), **MIT-licensed** (root LICENSE):
Author=agents/address-comments.agent.md, QualityReviewer=instructions/code-review-generic.instructions.md,
SecurityReviewer=agents/se-security-reviewer.agent.md, ArchReviewer=agents/se-system-architecture-reviewer.agent.md,
ResponsibleAIReviewer=agents/se-responsible-ai-code.agent.md, DevOps=agents/se-gitops-ci-specialist.agent.md,
Merger=agents/principal-software-engineer.agent.md.

Superset of pr_review_merge: 4 parallel reviewers + a real deploy gate. The
individual skills encode no "all-four-approve-then-deploy" ordering — that is
what the composed protocol adds. Safety review: benign SDLC coordination.
