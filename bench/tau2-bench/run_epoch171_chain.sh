#!/bin/bash
# 1.7.1 epoch chain (2026-11-23): two measurements on the operator's upgraded engine, no restarts -
# the live instance (38c7a88c..., 1.7.1, pin argv operator-confirmed) serves everything.
#   1) determinism corpus RE-RUN: re-POST the 2026-11-21/22 captured bodies (airline + telecom)
#      verbatim against 1.7.1 - direct cross-epoch action-identity comparison (does the ~50 %
#      agent lottery survive the 1.7.1 decode-side changes? paged-attention "output bits
#      unchanged" predicts: yes, similar rates).
#   2) 238x3 PASS^3 REPLAY on 1.7.1: closes the epoch debt for the published medium rows and
#      measures the shared-head-cache wall-time saving (1.7.1 resumes new conversations at the
#      cached system-prompt+tools head - exactly the tau2 wave shape).
# Initial sleep = grace window for the launching agent turn (rule 10).
set -uo pipefail

BENCH="$HOME/benchmarks"
PORT=${SPLASH_PORT:-8000}
W="$BENCH/bench/tau2-bench/results/2026-11-23-epoch171"
mkdir -p "$W"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$W/chain.log"; }

sleep "${GRACE_SECONDS:-120}"
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_start.json" || { log "engine down - abort"; exit 1; }
python3 - "$W/status_start.json" <<'PY' || true
import json,sys
d=json.load(sys.stdin)
print("epoch-chain start: instance", (d.get("instance") or {}).get("id"), "ready", d.get("ready"))
PY
log "epoch171 chain start (engine untouched)"

# ---- 1) determinism re-run on both captured corpora ----
for D in 2026-11-21-determinism-probe 2026-11-22-determinism-probe-telecom; do
  SRC="$BENCH/bench/tau2-bench/results/$D/captures.jsonl"
  [ -f "$SRC" ] || { log "missing captures for $D - skipping"; continue; }
  log "determinism re-run: $D on 1.7.1 (engine direct)"
  python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W/engine_samples_$D.jsonl" 2400 10 > "$W/sampler_$D.log" 2>&1 &
  S=$!
  python3 "$BENCH/bench/tau2-bench/probe_requery.py" "$SRC" "$W/probe_rows_$D.jsonl" --reps 3 --sample 40 \
    > "$W/requery_summary_$D.txt" 2> "$W/requery_progress_$D.log"
  log "determinism re-run $D exit=$?"
  kill "$S" 2>/dev/null
done
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_mid.json"

# ---- 2) 238x3 replay ----
RW="$BENCH/bench/tau2-bench/results/2026-11-23-pass3-replay-171"
mkdir -p "$RW"
log "replay wave: 238 x 3 trials, seed 300, published args, on the live 1.7.1 instance"
TAU2_TRIALS=3 TAU2_SAMPLE_SECONDS=21600 bash "$BENCH/bench/tau2-bench/run_wave.sh" "$RW" >> "$RW/runner.log" 2>&1
log "replay wave exit=$?"
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_end.json"
log "epoch171 chain complete"
