#!/bin/bash
# Detached chain for the same-request determinism probe (2026-11-21 night).
# Phase A: proxy + small capture wave (25 airline x 1) recording every wire request.
# Phase B: re-query sampled bodies verbatim (seq arm alone; mix arm in width-3 batches).
# Initial sleep = grace window for the launching agent turn (rule 10).
set -uo pipefail

BENCH="$HOME/benchmarks"
TAU2="$HOME/tau2-bench"
W="$BENCH/bench/tau2-bench/results/2026-11-21-determinism-probe"
PORT=${SPLASH_PORT:-8000}
mkdir -p "$W"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$W/probe.log"; }

sleep "${GRACE_SECONDS:-90}"

python3 "$BENCH/bench/tau2-bench/proxy_capture.py" "$W/captures.jsonl" 8011 > "$W/proxy.log" 2>&1 &
PX=$!
trap 'kill "$PX" 2>/dev/null' EXIT
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_before_capture.json"

log "phase A: capture wave (25 airline x 1, via proxy)"
python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W/engine_samples_capture.jsonl" 1800 10 > "$W/sampler_capture.log" 2>&1 &
S1=$!
cd "$TAU2" || exit 1
uv run python "$BENCH/bench/tau2-bench/run_probe_capture.py" > "$W/capture_wave.log" 2>&1
RC=$?
kill "$S1" 2>/dev/null
CAP=$(wc -l < "$W/captures.jsonl" 2>/dev/null || echo 0)
log "phase A exit=$RC captured_requests=$CAP"
[ "$CAP" -lt 100 ] && { log "too few captures - aborting probe"; exit 1; }

curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_before_requery.json"
log "phase B: re-query probe (engine direct, proxy out of path)"
python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W/engine_samples_requery.jsonl" 5400 10 > "$W/sampler_requery.log" 2>&1 &
S2=$!
python3 "$BENCH/bench/tau2-bench/probe_requery.py" "$W/captures.jsonl" "$W/probe_rows.jsonl" --reps 3 --sample 40 > "$W/requery_summary.txt" 2>"$W/requery_progress.log"
RC=$?
kill "$S2" 2>/dev/null
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_after.json"
kill "$PX" 2>/dev/null
trap - EXIT
log "phase B exit=$RC"
log "probe chain complete"
