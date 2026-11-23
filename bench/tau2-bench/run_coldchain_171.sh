#!/bin/bash
# Cold-state chain 2026-11-23: does engine CACHE STATE touch the pass^1 lottery?
#   P1 stop pinned engine (identity-gated) -> P2 move prefix-cache aside (NOT delete;
#      weights live in ~/.cache/huggingface and are untouched) -> P3 relaunch pinned argv
#      (cold: empty prefix cache, cold FS pages) -> P4 determinism corpus re-POST COLD
#      (airline+telecom captures, reps 3 sample 40; the ~25-min distribution instrument)
#      -> P5 the pre-registered n=3 tiebreaker wave WARM+CLEAN+PINNED
#      (gate: >=0.85 closes the 2-4 pt pass^1 dip as noise; <=0.81 same-shape establishes it).
# Comparability note for the RECORD: P5 runs after the corpus re-POST re-warmed the tau2-class
# heads; provenance of warmth differs from the two prior 1.7.1 waves and is disclosed, not hidden.
set -uo pipefail

BENCH="$HOME/benchmarks"
PORT=${SPLASH_PORT:-8000}
BIN="/opt/homebrew/Cellar/splash/1.7.1/libexec/python/bin/python3"
LIBEXEC=$(dirname "$(dirname "$(dirname "$BIN")")")
MODEL_ID="ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
MODEL_PATH="$HOME/Library/Application Support/Splash/models/$MODEL_ID"
ENGINE_BIN="/opt/homebrew/Cellar/splash/1.7.1/libexec/engine/splash"
SERVE_RECORD="$HOME/Library/Application Support/Splash/runtime/serve-8000.json"
CACHE_DIR="$HOME/Library/Caches/Splash/prefix-cache"
CACHE_PARK="$HOME/Library/Caches/Splash/prefix-cache-pre-cold-2026-11-23"
W="$BENCH/bench/tau2-bench/results/2026-11-23-coldchain"
mkdir -p "$W"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$W/chain.log"; }

inst_pid(){ curl -s --max-time 5 "http://127.0.0.1:$PORT/status" | python3 -c "import json,sys
d=json.load(sys.stdin); print((d.get('instance') or {}).get('pid') or '')" 2>/dev/null; }
sup_pid(){ pgrep -f "server.server.*--port $PORT" | head -1; }
relaunch(){  # $1 logfile; echoes supervisor pid
  cd "$LIBEXEC" || return 1
  export PYTHONPATH="$LIBEXEC${PYTHONPATH:+:$PYTHONPATH}"
  nohup "$BIN" -u -P -m server.server "$MODEL_PATH" \
    --model "$MODEL_ID" --binary "$ENGINE_BIN" --port "$PORT" --serve-record "$SERVE_RECORD" \
    --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache \
    --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64 \
    < /dev/null > "$1" 2>&1 &
  echo $!
  disown
}
wait_ready(){  # $1 expected supervisor pid, $2 status out; 0 ready, 2 identity mismatch, 1 timeout
  local body
  for _ in {1..240}; do
    body=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/status" || true)
    if [ -n "$body" ] && printf '%s' "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ready') else 1)" 2>/dev/null; then
      printf '%s' "$body" > "$W/status_$2.json"
      inst=$(inst_pid)
      if [ "$inst" = "$1" ]; then return 0; fi
      log "IDENTITY MISMATCH ($2): instance pid $inst != launched $1 - hands off"; return 2
    fi
    sleep 5
  done
  return 1
}

sleep "${GRACE_SECONDS:-120}"
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_start.json" || { log "engine already down - abort (operator state unknown, hands off)"; exit 1; }
log "cold chain start"

# ---- P1: stop the live instance (only our pattern; supervisor-gated) ----
SUP=$(sup_pid); LIVE=$(inst_pid)
if [ -z "$SUP" ] || [ -n "$LIVE" ] && [ "$LIVE" != "$SUP" ]; then log "unexpected supervisor/instance pattern (sup=$SUP inst=$LIVE) - aborting before kill"; exit 1; fi
kill "$SUP" 2>/dev/null; log "P1 stopped supervisor pid $SUP"
for _ in {1..40}; do pgrep -f "splash serve-native" >/dev/null || break; sleep 1; done
pkill -f "splash serve-native" 2>/dev/null || true
for _ in {1..20}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done

# ---- P2: park the prefix cache (reversible; delete only after the chain verifies) ----
if [ -d "$CACHE_DIR" ]; then
  if [ -e "$CACHE_PARK" ]; then log "P2 parking target already exists - refusing to overwrite, abort"; exit 1; fi
  mv "$CACHE_DIR" "$CACHE_PARK" && log "P2 parked prefix-cache -> $(basename "$CACHE_PARK") ($(du -sh "$CACHE_PARK" 2>/dev/null | cut -f1))"
else
  log "P2 no prefix-cache dir present (already cold?) - continuing"
fi

# ---- P3: cold relaunch, pinned argv ----
SUP2=$(relaunch "$W/serve_cold.log"); log "P3 cold supervisor pid $SUP2"
if ! wait_ready "$SUP2" cold; then log "FATAL: cold launch not ready/identity - manual start required; chain stops here"; exit 1; fi
log "P3 cold instance ready"

# ---- P4: determinism corpus re-POST on the COLD engine ----
for D in 2026-11-21-determinism-probe 2026-11-22-determinism-probe-telecom; do
  SRC="$BENCH/bench/tau2-bench/results/$D/captures.jsonl"
  [ -f "$SRC" ] || { log "P4 missing captures for $D - skipping"; continue; }
  log "P4 cold re-POST: $D"
  python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W/engine_samples_$D.jsonl" 2400 10 > "$W/sampler_$D.log" 2>&1 &
  S=$!
  python3 "$BENCH/bench/tau2-bench/probe_requery.py" "$SRC" "$W/cold_probe_rows_$D.jsonl" --reps 3 --sample 40 \
    > "$W/cold_requery_summary_$D.txt" 2> "$W/cold_requery_progress_$D.log"
  log "P4 cold re-POST $D exit=$?"
  kill "$S" 2>/dev/null
done
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_after_corpus.json"

# ---- P5: pre-registered n=3 tiebreaker wave (warm from corpus + wave traffic) ----
RW="$BENCH/bench/tau2-bench/results/2026-11-23-pass3-171-n3"
mkdir -p "$RW"
log "P5: 238x3 tiebreaker wave on 1.7.1 (n=3), gate >=0.85 noise / <=0.81 dip"
TAU2_TRIALS=3 TAU2_SAMPLE_SECONDS=25200 bash "$BENCH/bench/tau2-bench/run_wave.sh" "$RW" >> "$RW/runner.log" 2>&1
log "P5 exit=$?"
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_end.json"
log "cold chain complete (parked cache at $CACHE_PARK - delete when RECORD is written)"
