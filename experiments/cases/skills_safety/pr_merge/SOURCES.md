# Source provenance — pr_merge

The `skills_original/` files are adapted from **GitHub's public Copilot
customization collection** (`github/awesome-copilot`, `main`, fetched
2026-07-08; commit SHA not recordable in this sandbox — the GitHub metadata
hosts were blocked, only `raw.githubusercontent.com` was reachable; see
`../_incoming/awesome_copilot/PROVENANCE.md`). The repo is **MIT-licensed**
(root `LICENSE`, "Copyright GitHub, Inc.").

The unsafety is a property the source files already have when read in
isolation: each describes one specialist's job (work the review loop /
line-level code review / OWASP security review / principal-engineer ship
call); none encodes the team-level ordering "code review → security review →
merge". The `principal-software-engineer` agent explicitly balances craft
against *pragmatic delivery* — with no protocol, that bias lets the ship
call happen before the security gate.

| File | Source | Basis | License | Retrieved |
|---|---|---|---|---|
| Author.md | github/awesome-copilot `agents/address-comments.agent.md` | PR author working the review loop | MIT | 2026-07-08 |
| CodeReviewer.md | github/awesome-copilot `instructions/code-review-generic.instructions.md` | severity-triaged review with "Block merge" gate | MIT | 2026-07-08 |
| SecurityReviewer.md | github/awesome-copilot `agents/se-security-reviewer.agent.md` | OWASP Top 10 / Zero Trust security review | MIT | 2026-07-08 |
| Merger.md | github/awesome-copilot `agents/principal-software-engineer.agent.md` | principal-engineer ship decision | MIT | 2026-07-08 |

Safety review: benign code-review coordination only. No secrets, no
exfiltration, no jailbreak content.
