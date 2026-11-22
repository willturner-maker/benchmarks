#!/bin/bash
# Detached second xhigh 3-trial wave (2026-11-22): the replication that decides whether the
# effort A/B's aggregate gain survives the medium-band uncertainty (pass^1 must beat ~0.882 to
# be real at pass^1; the pass^3 signal stands if it reproduces at/above ~0.71).
# Initial sleep = grace window for the launching agent turn (rule 10).
set -uo pipefail

BENCH="$HOME/benchmarks"
W="$BENCH/bench/tau2-bench/results/2026-11-22-pass3-xhigh2"
mkdir -p "$W"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$W/runner.log"; }

sleep "${GRACE_SECONDS:-90}"

XHIGH='{"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":4096,"reasoning_effort":"xhigh"}'
log "xhigh2 wave launch: 238 x 3 trials, seed 300, agent args +reasoning_effort:xhigh, user args untouched (medium default)"
TAU2_TRIALS=3 TAU2_AGENT_LLM_ARGS="$XHIGH" TAU2_SAMPLE_SECONDS=21600 \
  bash "$BENCH/bench/tau2-bench/run_wave.sh" "$W" >> "$W/runner.log" 2>&1
log "xhigh2 wave exit=$?"
