# Source provenance — gem_dev_team

The seven `skills_original/gem-*.agent.md` files are fetched verbatim (HTTP 200,
2026-07-28) from **github/awesome-copilot** (`main`), directory `agents/`,
which is **MIT-licensed** (root LICENSE, "Copyright GitHub, Inc.").

| Role | Source file |
|---|---|
| Orchestrator | agents/gem-orchestrator.agent.md |
| Planner | agents/gem-planner.agent.md |
| Implementer | agents/gem-implementer.agent.md |
| Reviewer | agents/gem-reviewer.agent.md |
| Critic | agents/gem-critic.agent.md |
| BrowserTester | agents/gem-browser-tester.agent.md |
| DevOps | agents/gem-devops.agent.md |

This is our most COMPLEX real-skills case: 7 roles with a complexity BRANCH
(medium -> reviewer; high -> reviewer + critic), a test-fail LOOP (rec/continue),
and a deploy-ordering safety property (deploy only after review + green tests)
that no individual gem-* skill encodes. Safety review: benign SDLC coordination.
