#!/bin/bash
# Detached backlog chain, 2026-11-21: (1) retail-40 ENV closure wave, (2) drafter-off A/B (restart in,
# measure, restart back to the pin), (3) pass^3 replay on the new epoch. Launched mid-turn by the agent
# session the engine serves - the initial sleep is that turn's grace window.
#
# Each phase logs to chain.log; a failing phase does NOT abort the chain (except an unrecoverable
# engine-down, where restore is attempted first). All waves are run_wave.sh standard (sampler,
# status edges, supervisor pins).
set -uo pipefail

BENCH="$HOME/benchmarks"
TAU2="$HOME/tau2-bench"
REC="$BENCH/bench/splash-concurrency/results/backlog-chain-2026-11-21"
mkdir -p "$REC"
PORT=${SPLASH_PORT:-8000}
BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/python/bin/python3"
LIBEXEC=$(dirname "$(dirname "$(dirname "$BIN")")")
MODEL_ID="ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
MODEL_PATH="$HOME/Library/Application Support/Splash/models/$MODEL_ID"
ENGINE_BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/engine/splash"
SERVE_RECORD="$HOME/Library/Application Support/Splash/runtime/serve-8000.json"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$REC/chain.log"; }

sleep "${SPLASH_RESTART_DELAY:-120}"

relaunch(){  # $1 = model path (pinned or farm); relaunches with the pinned flag set
  cd "$LIBEXEC" || return 1
  export PYTHONPATH="$LIBEXEC${PYTHONPATH:+:$PYTHONPATH}"
  nohup "$BIN" -u -P -m server.server "$1" \
    --model "$MODEL_ID" --binary "$ENGINE_BIN" --port "$PORT" --serve-record "$SERVE_RECORD" \
    --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache \
    --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64 \
    < /dev/null > "$2" 2>&1 &
  disown
}

wait_ready(){  # $1 = tag for the post-restart status file
  local body
  for _ in {1..180}; do
    body=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/status" || true)
    if [ -n "$body" ] && printf '%s' "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ready') else 1)" 2>/dev/null; then
      printf '%s' "$body" > "$REC/status_$1.json"; return 0
    fi
    sleep 5
  done
  return 1
}

kill_engine(){  # $1 = tag for the pre-restart archive
  local sup
  sup=$(pgrep -f "server.server.*--port $PORT" | head -1)
  [ -n "$sup" ] || return 1
  curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$REC/status_pre_$1.json"
  kill "$sup"
  for _ in {1..30}; do
    pgrep -f "server.server.*--port $PORT" > /dev/null || pgrep -f "splash serve-native" > /dev/null || break
    sleep 1
  done
  pkill -f "splash serve-native" 2>/dev/null || true
  for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done
}

draft_probe(){  # $1 = expect zero|nonzero; returns 0 if the drafter state matches
  local before after d
  before=$(curl -s http://127.0.0.1:"$PORT"/status | python3 -c "import json,sys; print(((json.load(sys.stdin).get('metrics') or {}).get('drafted_tokens') or 0))")
  curl -s --max-time 90 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL_ID\",\"max_tokens\":256,\"messages\":[{\"role\":\"user\",\"content\":\"List three prime numbers above 90 and nothing else.\"}]}" > /dev/null
  sleep 2
  after=$(curl -s http://127.0.0.1:"$PORT"/status | python3 -c "import json,sys; print(((json.load(sys.stdin).get('metrics') or {}).get('drafted_tokens') or 0))")
  d=$((after - before))
  echo "drafted_tokens delta over probe: $d" >> "$REC/chain.log"
  [ "$1" = zero ] && [ "$d" -eq 0 ] && return 0
  [ "$1" = nonzero ] && [ "$d" -gt 0 ] && return 0
  return 1
}

# ---------- Phase 1: retail-40 ENV closure (engine as-is) -------------------------------------
log "phase 1: retail-40 ENV closure wave"
W1="$BENCH/bench/tau2-bench/results/2026-11-21-retail40-env"
mkdir -p "$W1"
python3 "$BENCH/bench/tau2-bench/sample_engine.py" "$W1/engine_samples.jsonl" 5400 10 > "$W1/sampler.log" 2>&1 &
S1=$!
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W1/status_before.json"
cd "$TAU2" && uv run python "$BENCH/bench/tau2-bench/run_retail40_env.py" --save-to wave-2026-11-21-retail40-env-retail --trials 2 > "$W1/retail40.log" 2>&1
log "phase 1 exit=$?"
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W1/status_after.json"
kill "$S1" 2>/dev/null

# ---------- Phase 2: drafter-off arm, then restore to the pin ---------------------------------
log "phase 2: drafter-off arm"
FARM=$(python3 "$BENCH/bench/splash-concurrency/drafter_farm.py")
log "farm: ${FARM/#$HOME/\~}"
DRAFTER_OK=0
if kill_engine drafter-off && relaunch "$FARM" "$REC/serve_nodraft.log" && wait_ready post_nodraft; then
  if draft_probe zero; then
    DRAFTER_OK=1
    log "drafter confirmed OFF; running comparison wave (238 x 1, like the same-seed arms)"
    cd "$BENCH/bench/tau2-bench" || exit 1
    TAU2_TRIALS=1 TAU2_SAMPLE_SECONDS=7200 bash run_wave.sh "$BENCH/bench/tau2-bench/results/2026-11-21-drafter-off" >> "$REC/drafter_wave.log" 2>&1
    log "drafter-off wave exit=$?"
  else
    log "DRAFTER STILL ON - arm invalid, restoring without measuring"
  fi
else
  log "drafter-off launch FAILED - restoring pin"
fi

if kill_engine restore && relaunch "$MODEL_PATH" "$REC/serve_restored.log" && wait_ready post_restore; then
  if draft_probe nonzero; then log "pin restored, drafter ON again"; else log "WARNING: drafter did not resume"; fi
else
  log "FATAL: restore did not become ready - manual intervention required"
  exit 1
fi
log "drafter arm result: ok=$DRAFTER_OK"

# ---------- Phase 3: pass^3 replay on the new epoch (drafter on, engine as pinned) ------------
log "phase 3: pass^3 replay (238 x 3, medium) on the new epoch"
cd "$BENCH/bench/tau2-bench" || exit 1
TAU2_TRIALS=3 TAU2_SAMPLE_SECONDS=21600 bash run_wave.sh "$BENCH/bench/tau2-bench/results/2026-11-21-pass3-replay" >> "$REC/replay.log" 2>&1
log "phase 3 exit=$?"
log "backlog chain complete"
