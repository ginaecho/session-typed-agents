#!/usr/bin/env bash
# run_foundry_matrix.sh — sweep the agenticpay_settlement Foundry benchmark
# across a model matrix (one Azure AI Foundry deployment name per run).
#
# WHY THIS SCRIPT EXISTS (see foundry_run.md Section 4): the harness reads
# the deployment name from AZURE_OPENAI_DEPLOYMENT exactly once, at Python
# module-import time, in experiments/baselines/foundry_runner.py:45. One
# `case_runner.py` process therefore only ever exercises one deployment.
# There is no existing harness flag that loops the matrix internally, so
# this script does the one thing that's genuinely missing: it re-invokes
# the EXISTING, documented case_runner.py command (see foundry_run.md
# Section 3) once per deployment name, with the env var set differently
# each time. It adds no new run logic of its own.
#
# Usage:
#   ./run_foundry_matrix.sh <deployment-name> [<deployment-name> ...]
#   ./run_foundry_matrix.sh opus-4.7 opus-4.6 sonnet-5 sonnet-4.6 haiku-4.5
#
# The names above are PLACEHOLDERS. Substitute the actual deployment names
# you created in your Azure AI Foundry project (foundry_run.md Section 1,
# step 3). Called with no arguments, this script falls back to that same
# placeholder list purely so it is runnable-as-written for a dry read; it
# still needs real deployments (and az login + stjp_core/.env, per
# foundry_run.md Section 1) to actually succeed. Writing and reading this
# script requires no credentials — only running it against real Foundry
# deployments does.
#
# Env overrides:
#   N_TRIALS  - trials per arm per deployment (default: 6)
#   ARMS      - comma-separated scenario keys (default:
#               unchecked_skills,spec_llmvalid,min_llmvalid — see
#               foundry_run.md Section 3 for what each arm means)
#
# What happens per deployment name:
#   1. export AZURE_OPENAI_DEPLOYMENT=<name>
#   2. python scripts/case_runner.py agenticpay_settlement "$N_TRIALS" \
#        --arms "$ARMS"                      (run from experiments/)
#   3. Read case_dir/LATEST (written by case_runner.py itself,
#      case_runner.py:540) to find the run directory that invocation
#      just created.
#   4. Write "<name>" to <run_dir>/deployment.txt, and append a row to
#      runs/model_matrix_index.csv — bookkeeping this script does itself,
#      NOT a harness feature (case_runner.py's own output files carry no
#      deployment/model field; see foundry_run.md Section 6, gap 2).
#
# On error in any one deployment's run, this script prints the failure and
# CONTINUES to the next deployment (a bad/misnamed deployment for one model
# shouldn't block measuring the other four) — check model_matrix_index.csv
# and matrix_errors.log afterwards for anything that didn't complete.

set -uo pipefail

N_TRIALS="${N_TRIALS:-6}"
ARMS="${ARMS:-unchecked_skills,spec_llmvalid,min_llmvalid}"
CASE_ID="agenticpay_settlement"

DEPLOYMENTS=("$@")
if [ ${#DEPLOYMENTS[@]} -eq 0 ]; then
  echo "No deployment names given; using placeholder example names." >&2
  echo "Substitute your real Azure AI Foundry deployment names — see" >&2
  echo "foundry_run.md Section 1, step 3." >&2
  DEPLOYMENTS=(opus-4.7 opus-4.6 sonnet-5 sonnet-4.6 haiku-4.5)
fi

CASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENTS_DIR="$(cd "$CASE_DIR/../.." && pwd)"
RUNS_DIR="$CASE_DIR/runs"
INDEX_FILE="$RUNS_DIR/model_matrix_index.csv"
ERROR_LOG="$RUNS_DIR/matrix_errors.log"
LATEST_FILE="$CASE_DIR/LATEST"

mkdir -p "$RUNS_DIR"
if [ ! -f "$INDEX_FILE" ]; then
  echo "deployment,run_dir,n_trials,arms,started_at_utc,status" > "$INDEX_FILE"
fi

echo "=== agenticpay_settlement Foundry model-matrix sweep ==="
echo "  case:      $CASE_ID"
echo "  n_trials:  $N_TRIALS"
echo "  arms:      $ARMS"
echo "  deployments: ${DEPLOYMENTS[*]}"
echo "  index:     $INDEX_FILE"
echo

for DEPLOY in "${DEPLOYMENTS[@]}"; do
  STARTED_AT="$(date -u +%FT%TZ)"
  echo "--- [$STARTED_AT] deployment: $DEPLOY ---"

  export AZURE_OPENAI_DEPLOYMENT="$DEPLOY"

  if ( cd "$EXPERIMENTS_DIR" && python scripts/case_runner.py "$CASE_ID" "$N_TRIALS" --arms "$ARMS" ); then
    if [ -f "$LATEST_FILE" ]; then
      RUN_NAME="$(cat "$LATEST_FILE")"
      RUN_DIR="$RUNS_DIR/$RUN_NAME"
      if [ -d "$RUN_DIR" ]; then
        echo "$DEPLOY" > "$RUN_DIR/deployment.txt"
        echo "$DEPLOY,$RUN_NAME,$N_TRIALS,$ARMS,$STARTED_AT,ok" >> "$INDEX_FILE"
        echo "  -> $RUN_DIR (tagged deployment=$DEPLOY)"
      else
        echo "  WARNING: LATEST points at $RUN_DIR, which does not exist." | tee -a "$ERROR_LOG"
        echo "$DEPLOY,,$N_TRIALS,$ARMS,$STARTED_AT,missing_run_dir" >> "$INDEX_FILE"
      fi
    else
      echo "  WARNING: $LATEST_FILE not found after a run that reported success." | tee -a "$ERROR_LOG"
      echo "$DEPLOY,,$N_TRIALS,$ARMS,$STARTED_AT,missing_latest_file" >> "$INDEX_FILE"
    fi
  else
    STATUS=$?
    echo "  FAILED (exit $STATUS) for deployment=$DEPLOY" | tee -a "$ERROR_LOG"
    echo "$DEPLOY,,$N_TRIALS,$ARMS,$STARTED_AT,failed_exit_$STATUS" >> "$INDEX_FILE"
  fi
  echo
done

echo "=== sweep complete ==="
echo "  index: $INDEX_FILE"
if [ -f "$ERROR_LOG" ]; then
  echo "  errors were logged to: $ERROR_LOG (review before trusting the matrix)"
fi
