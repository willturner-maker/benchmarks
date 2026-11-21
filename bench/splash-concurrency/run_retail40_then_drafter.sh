#!/bin/bash
# Detached driver, 2026-11-21 evening: retail-40 ENV rerun (fixed seam: runner.run_tasks with
# evaluation_type=ENV - attempt 1 died because run_domain never forwards evaluation_type and the
# judge re-engaged, 80/80 infrastructure_error) followed by the drafter-off arm
# (run_drafter_arm.sh, instance-identity gated). Initial sleep = grace window for the launching
# agent turn, which decodes on the same engine.
set -uo pipefail

BENCH="$HOME/benchmarks"
TAU2="$HOME/tau2-bench"
REC="$BENCH/bench/splash-concurrency/results/backlog-chain-2026-11-21"
W="$BENCH/bench/tau2-bench/results/2026-11-21-retail40-env"
PORT=${SPLASH_PORT:-8000}
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$REC/chain.log"; }

sleep "${GRACE_SECONDS:-90}"

log "retail40 rerun (ENV seam fixed): launching sampler + 40x2 wave"
python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W/engine_samples_rerun.jsonl" 5400 10 > "$W/sampler_rerun.log" 2>&1 &
S=$!
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_rerun_before.json"
cd "$TAU2" || exit 1
uv run python "$BENCH/bench/tau2-bench/run_retail40_env.py" --save-to wave-2026-11-21-retail40-env-retail --trials 2 > "$W/retail40_rerun.log" 2>&1
RC=$?
log "retail40 rerun exit=$RC"
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_rerun_after.json"
kill "$S" 2>/dev/null
[ "$RC" -ne 0 ] && log "retail40 rerun reported infrastructure_error sims - inspect retail40_rerun.log"

log "handing off to drafter arm"
SPLASH_RESTART_DELAY=60 bash "$BENCH/bench/splash-concurrency/run_drafter_arm.sh"
log "retail40-then-drafter driver complete"
