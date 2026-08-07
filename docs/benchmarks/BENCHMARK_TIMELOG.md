# Benchmark Time Log — how long each stage takes, so we can estimate future cases

**Purpose:** We are timing every stage of our first full test case
(`sdlc_release_gate`, our "pilot") so we can estimate how long the
remaining cases (see CASE_RANKING.md) will take, instead of guessing. The
lead AI (we call it the "orchestrator") updates this log at each
checkpoint — what this project calls a "stage gate," a point where work is
reviewed before moving on. Times shown are real-world elapsed time,
including any time spent waiting on tools, not raw computer processing
time. They come from the activity logs of our AI helper workers, which
this project calls "subagents."

## One-time costs (paid once, never again for future cases)

Each row below is one stage of setup. The stage labels (S1, S1b, S1c, …)
match the step-by-step runbook in `BENCHMARK_IMPLEMENTATION_STEPS.md`.

| stage | what we did | wall time | notes |
|---|---|---|---|
| S1 | Checked that all our tools were ready to use (12 checks) — done by a fast, low-cost AI helper (Claude Haiku) | 1.1 min | 12 checks |
| S1b | Found the right cloud deployment; connected Azure's monitoring tool (Application Insights); worked out which parts of the nuscr protocol-checker apply to this case — done by a more capable AI helper (Claude Sonnet) | 2.4 min | |
| S1c | Installed the Maven build tool; downloaded and built scribble-java (the tool that turns a protocol description into per-role instructions); ran one small check to confirm it works — done by Claude Sonnet | 6.0 min | the Maven build step alone took 1 min 32 sec |
| S1d | Set up Docker (the container tool); downloaded and built our own copy of nuscr (our second, independent protocol checker), including its test suite — done by Claude Sonnet, in two parts | 8.1 + 19.4 min | building opam (the package manager nuscr depends on) took about 13 min by itself |
| — | Checked that the Qwen, Kimi, and DeepSeek AI models were available — done by Claude Haiku | 5.8 min | |
| S4 | Built the first version of our "hosted workflow template" — the reusable pattern, container code, and driver script that let a case run as a hosted cloud agent | spec ~15 min (orchestrator); build still in progress — will record when done | future cases reuse this template, so setting one up should take much less time than this first build |

**Total one-time setup so far: about 43 minutes** of AI-helper real-world
time (some steps happened at the same time as others, so this is not a
simple sum).

## Per-case preparation costs (the repeatable estimate)

| stage | what | sdlc_release_gate measured | estimate for future cases |
|---|---|---|---|
| S2 | Building the intent package: writing the task description, distilling it, checking it covers every goal, and approving it (see CASE_RANKING.md for what an intent package is) | about 3–4 min, 5 AI-model calls, roughly 10,000 tokens of setup cost (tokens are the small text chunks AI models are billed by; from the file `provenance.json`) | same |
| S3 | Checking the protocol is valid: running both checking tools (nuscr and scribble-java) and comparing results, plus a basic sanity check on the workflow-building code | included in a combined 5.4-min setup package | about 5 min |
| S4' | Applying the reusable template to a brand-new case: building the supporting files, adding entries to `agent.yaml`, and running one small check locally | not applicable — the first case pays the full cost of building the template (see stage S4 above) | to be determined after the second case; expected to be 15 min or less |

## Campaign runtime (to be measured — the numbers future estimates need most)

We still need to record the following, for each setup (this project calls
a setup an "arm") and each AI model, both during the small check run and
during the full campaign:
- seconds per test run (first from the small check run, then the campaign
  average and how much it varies)
- calls per test run and tokens per test run (billing units we already
  track)
- how long one full batch of runs takes for a single AI model (300 test
  runs per batch — 10 setups × 30 trials); we expect the DeepSeek-V4-Flash
  model (capped at 125 requests) to be the slowest
- how many times each batch hits a rate limit — a "429" error, meaning the
  server said "slow down" — which tells us whether running things in
  parallel is causing problems

| milestone | date | duration | notes |
|---|---|---|---|
| Finished building the hosted workflow template (checkpoints 1–3) | 2026-08-05 | **56.8 min** (AI-helper time) | this is the full build for the very first case, and includes 3 spec changes made while work was underway. Its first real test run (checkpoint 3, plain baseline setup on gpt-5-mini) made 25 calls, used 57,300 tokens, and stopped after hitting its turn limit — the expected result for the plain baseline with no safety checks |
| Ported the "fair reordering" logic (a method for trying different valid message orders, checked against our core system for an exact match) | 2026-08-05 | 8.8 min | 4 out of 4 small check runs passed, plus a check that this version's output exactly matches the original |
| Small check runs for each setup, across 4 AI models (40 test runs total — 10 setups × 4 models) | — | — | pending |
| Full campaign batches (1,200 test runs — 10 setups × 4 models × 30 trials, models run in parallel) | — | — | pending |
| Analyze results and write the report | — | — | pending |

## Estimation model (to refine after the pilot)

Our rough formula for a future case's total time: about 10 minutes to
prepare the case, plus about 15 minutes to apply the template, plus about
5 minutes of extra deployment time, plus the small check runs (40 runs ×
time per test run), plus the full campaign (300 runs × the time per test
run for the slowest batch, with batches running at the same time), plus
time for analysis. The one number we still need from the pilot case — and
the whole reason this log exists — is: how long does one test run actually
take, for each setup and each AI model?
