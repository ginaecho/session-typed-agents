# How we use nuScr on this branch — a short guide

This is a plain-English guide for anyone joining the branch
`gc/user_intent_validation_loop`. It explains what nuScr is, how we run it,
and — important — the two fallback mechanisms built around it.

## What nuScr is, in one paragraph

nuScr is a command-line tool that checks a multi-agent protocol file
(`.scr` / `.nuscr`) for structural problems — for example, a role that can
end up waiting forever for a message nobody will send. We use a special
fork of it (`phou/nuscr_coinduction`, branch `coinductive_projection`)
because the fork can handle loop-shaped protocols that the stock tool
rejects. It sits alongside our older checker, Scribble-java. The two tools
overlap but are not the same: nuScr only understands a subset of the
protocol language.

## The one command you actually run

```bash
python experiments/scripts/validate_protocol_provenance.py <case_id>
# default case if you leave it out: skills_safety/sdlc_release_gate
```

This runs the case's protocol (`protocols/llm_drafts/valid/v1.scr`) through
**both** checkers — nuScr *and* Scribble — and writes the evidence to disk:

- `protocol_validation.json` next to the protocol — both verdicts, the
  protocol's SHA-256 hash, and per-role projection stats.
- `intent/provenance.json` — gets a `protocol_validation` block pointing at
  that file.

You must run this **before** a hosted benchmark campaign. The campaign
driver (`experiments/scripts/hosted_campaign.py`) refuses to start if the
evidence file is missing, or if the protocol file changed since it was
written (the SHA no longer matches).

## Fallback mechanism 1: how nuScr itself gets invoked

`stjp_core/compiler/nuscr_compiler.py` finds the tool in this order:

1. **Native binary** — if the environment variable `STJP_NUSCR_BIN` points
   at a nuScr executable, it runs that directly. This is the route for
   machines that cannot pull Docker images (cloud sandboxes). How to get
   such a binary is documented step by step in
   [NUSCR_CLOUD_INSTALL.md](NUSCR_CLOUD_INSTALL.md) (Route B — it is built
   on a GitHub Actions runner and committed to the fork's `ci-artifacts`
   branch).
2. **Docker** — otherwise it falls back to `docker run` with the image
   named by `STJP_NUSCR_IMAGE` (default `nuscr-coind:latest`), built from
   `tools/nuscr/Dockerfile` (Route A in the same doc).

So: set `STJP_NUSCR_BIN` if you have the binary; do nothing and it will try
Docker.

## Fallback mechanism 2: what happens when nuScr can't cope

nuScr only supports a fragment of our protocol language. Some perfectly
good protocols make it say things like "not implemented" (the `finance`
case is a known example — its protocol is not tail-recursive). We do
**not** treat that as a failure. The validation script sorts nuScr's answer
into three buckets:

- **pass** — nuScr checked the protocol and projected every role.
- **not-implemented** — nuScr couldn't process this protocol at all
  (message contains "not implemented", "unsupported", etc.). Tolerated.
- **fail** — nuScr understood the protocol and found a real problem.

The rule the campaign enforces (`_load_protocol_validation` in
`hosted_campaign.py`):

- **Scribble must pass. Always. No fallback for that.** Scribble-java is
  the authority on whether a protocol is safe.
- **nuScr must be "pass" or "not-implemented".** Only a hard "fail" blocks
  the run.

In short: Scribble is the gate, nuScr is a second opinion — valuable when
it works, excused when it doesn't, blocking only when it finds a genuine
problem.

## One more default worth knowing

The harness-wide backend switch `STJP_COMPILER_BACKEND`
(`stjp_core/config.py`) still defaults to `scribble`. nuScr is opt-in per
run (`STJP_COMPILER_BACKEND=nuscr`). The dual-validation script above
ignores this switch — it always runs both.

## Where to read more

- [NUSCR_CLOUD_INSTALL.md](NUSCR_CLOUD_INSTALL.md) — installing nuScr
  (Docker route and restricted-network route) and running it by hand.
- [NUSCR_BACKEND_COMPARISON.md](NUSCR_BACKEND_COMPARISON.md) — how the two
  checkers compare.
- [NUSCR_AND_SKILL_SAFETY_PLAN.md](NUSCR_AND_SKILL_SAFETY_PLAN.md) — why
  the fork was brought in.
