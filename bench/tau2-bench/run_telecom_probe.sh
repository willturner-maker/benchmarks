#!/bin/bash
# Detached telecom extension of the determinism probe (2026-11-22): does the ~85 % per-request
# action instability get worse on the longest-conversation domain, as the airline depth gradient
# predicts? Same method (proxy capture -> verbatim re-query, seq + mix arms), telecom base-split
# every-4th task (29 of 114). Initial sleep = grace window for the launching agent turn.
set -uo pipefail

BENCH="$HOME/benchmarks"
TAU2="$HOME/tau2-bench"
W="$BENCH/bench/tau2-bench/results/2026-11-22-determinism-probe-telecom"
PORT=${SPLASH_PORT:-8000}
mkdir -p "$W"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$W/probe.log"; }

sleep "${GRACE_SECONDS:-90}"

python3 "$BENCH/bench/tau2-bench/proxy_capture.py" "$W/captures.jsonl" 8011 > "$W/proxy.log" 2>&1 &
PX=$!
trap 'kill "$PX" 2>/dev/null' EXIT
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_before_capture.json"

log "capture wave: telecom base every-4th (29 x 1, via proxy)"
python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W/engine_samples_capture.jsonl" 2400 10 > "$W/sampler_capture.log" 2>&1 &
S1=$!
cd "$TAU2" || exit 1
uv run python "$BENCH/bench/tau2-bench/run_probe_capture.py" --domain telecom --step 4 --save-to wave-2026-11-22-probe-capture-telecom > "$W/capture_wave.log" 2>&1
RC=$?
kill "$S1" 2>/dev/null
CAP=$(wc -l < "$W/captures.jsonl" 2>/dev/null || echo 0)
log "capture exit=$RC captured_requests=$CAP"
[ "$CAP" -lt 150 ] && { log "too few captures - aborting"; kill "$PX" 2>/dev/null; exit 1; }

curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_before_requery.json"
log "re-query (engine direct): 40 agent + 40 user bodies, 3 reps, seq + mix"
python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W/engine_samples_requery.jsonl" 5400 10 > "$W/sampler_requery.log" 2>&1 &
S2=$!
python3 "$BENCH/bench/tau2-bench/probe_requery.py" "$W/captures.jsonl" "$W/probe_rows.jsonl" --reps 3 --sample 40 > "$W/requery_summary.txt" 2>"$W/requery_progress.log"
RC=$?
kill "$S2" 2>/dev/null
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_after.json"
kill "$PX" 2>/dev/null
trap - EXIT
log "re-query exit=$RC"
log "telecom probe chain complete"
