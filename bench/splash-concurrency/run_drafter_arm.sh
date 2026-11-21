#!/bin/bash
# Standalone drafter-off arm, rerun of backlog-chain phase 2 with the fixed farm (assembly under
# .resolved + selection link) and an INSTANCE-IDENTITY GATE: the script only ever kills supervisors
# whose /status instance pid matches the one it launched itself - it will not touch an engine started
# by hand (attempt 2 lesson: the phase-2 restore killed the operator's manual restart because
# kill_engine matched any supervisor).
#
# Precondition: no wave/sampler running (checked). Flow: kill current engine -> launch farm (no
# drafter) -> verify ready+identity+drafted_delta==0 -> 238x1 medium wave -> kill OUR instance ->
# relaunch pinned argv -> verify identity + drafted_delta>0.
set -uo pipefail

BENCH="$HOME/benchmarks"
REC="$BENCH/bench/splash-concurrency/results/backlog-chain-2026-11-21"
PORT=${SPLASH_PORT:-8000}
BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/python/bin/python3"
LIBEXEC=$(dirname "$(dirname "$(dirname "$BIN")")")
MODEL_ID="ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
MODEL_PATH="$HOME/Library/Application Support/Splash/models/$MODEL_ID"
ENGINE_BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/engine/splash"
SERVE_RECORD="$HOME/Library/Application Support/Splash/runtime/serve-8000.json"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$REC/chain.log"; }

sleep "${SPLASH_RESTART_DELAY:-120}"

if pgrep -f "sample_engine|tau2 run|uv run tau2" > /dev/null; then
  log "drafter-arm: a wave/sampler is running - refusing to restart"; exit 1
fi

inst_pid(){ curl -s --max-time 5 "http://127.0.0.1:$PORT/status" | python3 -c "import json,sys
d=json.load(sys.stdin); print((d.get('instance') or {}).get('pid') or '')" 2>/dev/null; }

relaunch(){  # $1 model path, $2 log file; echoes supervisor pid
  cd "$LIBEXEC" || return 1
  export PYTHONPATH="$LIBEXEC${PYTHONPATH:+:$PYTHONPATH}"
  nohup "$BIN" -u -P -m server.server "$1" \
    --model "$MODEL_ID" --binary "$ENGINE_BIN" --port "$PORT" --serve-record "$SERVE_RECORD" \
    --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache \
    --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64 \
    < /dev/null > "$2" 2>&1 &
  echo $!
  disown
}

wait_ready(){  # $1 tag, $2 expected instance pid
  local body p
  for _ in {1..180}; do
    body=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/status" || true)
    if [ -n "$body" ] && printf '%s' "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ready') else 1)" 2>/dev/null; then
      printf '%s' "$body" > "$REC/status_$1.json"
      p=$(printf '%s' "$body" | python3 -c "import json,sys; print((json.load(sys.stdin).get('instance') or {}).get('pid') or '')")
      if [ "$p" = "$2" ]; then return 0; fi
      log "IDENTITY MISMATCH: ready instance pid $p != launched $2 - leaving engine untouched"; return 2
    fi
    sleep 5
  done
  return 1
}

kill_ours(){  # $1 our supervisor pid, $2 tag
  local live
  live=$(inst_pid)
  if [ -n "$live" ] && [ "$live" != "$1" ]; then
    log "REFUSING to kill: live instance pid $live is not ours ($1)"; return 1
  fi
  curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$REC/status_pre_$1_$2.json" 2>/dev/null
  kill "$1" 2>/dev/null
  for _ in {1..30}; do kill -0 "$1" 2>/dev/null || pgrep -f "splash serve-native" > /dev/null || break; sleep 1; done
  pkill -f "splash serve-native" 2>/dev/null || true
  for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done
}

draft_probe(){  # $1 zero|nonzero
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

# ---------- arm ---------------------------------------------------------------------------
log "drafter-arm rerun: killing current engine (operator's or chain's - none launched by this script yet)"
CUR=$(inst_pid)
[ -n "$CUR" ] && kill "$CUR" 2>/dev/null   # the ONLY kill of a foreign pid, logged above by design
for _ in {1..30}; do pgrep -f "server.server.*--port $PORT" > /dev/null || pgrep -f "splash serve-native" > /dev/null || break; sleep 1; done
pkill -f "splash serve-native" 2>/dev/null || true
for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done

FARM=$(python3 "$BENCH/bench/splash-concurrency/drafter_farm.py")
log "farm link: ${FARM/#$HOME/\~}"
SUP=$(relaunch "$FARM" "$REC/serve_nodraft2.log"); log "farm supervisor pid $SUP"
if wait_ready post_nodraft2 "$SUP" && draft_probe zero; then
  log "drafter CONFIRMED OFF (identity verified); running 238x1 medium wave"
  cd "$BENCH/bench/tau2-bench" || exit 1
  TAU2_TRIALS=1 TAU2_SAMPLE_SECONDS=7200 bash run_wave.sh "$BENCH/bench/tau2-bench/results/2026-11-21-drafter-off" >> "$REC/drafter_wave.log" 2>&1
  log "drafter-off wave exit=$?"
else
  log "drafter arm invalid (launch/identity/draft check failed) - restoring pin"
fi

if kill_ours "$SUP" nodraft2; then
  SUP2=$(relaunch "$MODEL_PATH" "$REC/serve_restored2.log"); log "pin supervisor pid $SUP2"
  if wait_ready post_restore2 "$SUP2" && draft_probe nonzero; then
    log "pin restored, drafter ON again, identity verified"
  else
    log "WARNING: post-restore check failed - inspect status_post_restore2.json"
  fi
else
  log "FATAL: could not kill our farm instance - manual restore required"
  exit 1
fi
