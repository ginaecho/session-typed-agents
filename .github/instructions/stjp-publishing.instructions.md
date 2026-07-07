---
description: "Publishing and git-identity policy for the Session-Typed Skills (STJP) project: the single upstream source of truth is ginaecho/session-typed-skills, the internal mcaps-microsoft/eag-innovation monorepo is a downstream mirror only, and every commit/push/PR is made as the Microsoft account (Gina Chen)."
applyTo: "**"
---

# STJP publishing & git-identity policy

## Single source of truth

- **Upstream source of truth is ALWAYS `https://github.com/ginaecho/session-typed-skills`.**
  This local repo's `origin` is that repo. All authoritative history lives here.
- **`mcaps-microsoft/eag-innovation` at `agentic-governance/stjp/` is a DOWNSTREAM
  MIRROR only.** Never treat it as a source; never develop against it directly.

## Git identity — ALWAYS the Microsoft account

Every commit, push, branch, and pull request MUST be attributed to the project
owner's Microsoft account — never to Claude/an assistant:

- **Author / committer:** `Gina Chen <tzuchunchen+microsoft@microsoft.com>`
- **GitHub account for push & PR:** `tzuchunchen_microsoft` (the `gh` CLI is
  authenticated as this account).
- **Do NOT** add a `Co-Authored-By: Claude ...` trailer or any bot/assistant author.

Set identity inline on every commit so it is correct regardless of local config:

```bash
git -c user.name="Gina Chen" -c user.email="tzuchunchen+microsoft@microsoft.com" \
    commit -m "<message>"
```

Review branches use the `gc/` prefix (e.g. `gc/stjp-sync-<date>`). Open PRs with
`gh pr create` (runs as `tzuchunchen_microsoft`).

## Two-hop publishing — source first, then mirror

```
  (local working copy)
        │  hop 1: commit + push  (as Gina, Microsoft account)
        ▼
  ginaecho/session-typed-skills (main)      ← SOURCE OF TRUTH
        │  hop 2: mirror tracked files into a subfolder + PR
        ▼
  mcaps-microsoft/eag-innovation (main)
        └── agentic-governance/stjp/         ← MIRROR (internal MS monorepo)
```

### Hop 1 — push to the source (`ginaecho/session-typed-skills`)

Commit and push work here FIRST. Direct push to `main` is fine (owner's own repo);
use a `gc/<topic>` branch + PR only when review is warranted.

### Hop 2 — mirror into `mcaps-microsoft/eag-innovation`

The mirror reflects the **source of truth (ginaecho)**. Sync the source's
**tracked** files (`git ls-files`) into `agentic-governance/stjp/` via a
**branch + PR — NEVER push to that shared repo's `main` directly.**

Verified procedure (Windows / PowerShell):

```powershell
$WORK="C:\e"                     # short base path — Windows MAX_PATH
git config --global core.longpaths true
Remove-Item -Recurse -Force $WORK -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $WORK | Out-Null; Set-Location $WORK
# 1. sparse-clone ONLY agentic-governance (rest of monorepo has Windows-illegal names)
git clone --depth 1 --no-checkout --filter=blob:none https://github.com/mcaps-microsoft/eag-innovation.git
Set-Location eag-innovation
git config core.longpaths true
git sparse-checkout init --cone; git sparse-checkout set agentic-governance
git checkout main; git checkout -b gc/stjp-sync-<date>
# 2. replace old copy, then copy the source's tracked files into agentic-governance/stjp/
git rm -r --quiet agentic-governance
New-Item -ItemType Directory -Force -Path agentic-governance/stjp | Out-Null
#    (from the SOURCE repo checkout) copy each `git ls-files` path into agentic-governance/stjp/
# 3. stage, verify, commit as Gina, push branch, open PR
git add agentic-governance
git -c user.name="Gina Chen" -c user.email="tzuchunchen+microsoft@microsoft.com" `
    commit -m "Sync Session-Typed Skills (STJP) from ginaecho/session-typed-skills"
git push -u origin gc/stjp-sync-<date>
gh pr create --repo mcaps-microsoft/eag-innovation --base main --head gc/stjp-sync-<date> --title "..." --body "..."
```

### Verify before committing hop 2

- files under `agentic-governance/stjp/` == source `git ls-files | wc -l`
- zero leftovers under `agentic-governance/` outside `stjp/`
- nothing staged outside `agentic-governance/`
- no `scribble-java/`, `nuscr-coinduction/`, images, `.env`, or run outputs staged
  (these are `.gitignore`d in the source, so `git ls-files` already excludes them)

## Never mirror the vendored compilers

`scribble-java/` and `nuscr-coinduction/` are vendored upstream checkouts, kept
`.gitignore`d. They must never be committed to either repo.
