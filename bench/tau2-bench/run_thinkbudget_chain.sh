#!/bin/bash
# Thinking-token-budget A/B on the pinned 1.7.0 stack (2026-11-22): three 238x1 medium waves, one
# per engine-level --thinking-token-budget arm (8192, 65536, then the pinned 32768 as same-session
# control - pin restored last, so a mid-chain failure still leaves the engine pinned).
# Restart pattern per run_drafter_arm.sh: identity-gated kills (only pids this script launched,
# after confirming the live instance matches), wave/sampler check, ENGINE-IDLE wait before every
# kill (added: co-tenant agent requests are live on this engine), argv verification after every
# relaunch. Initial sleep = grace window for the launching agent turn (rule 10).
set -uo pipefail

BENCH="$HOME/benchmarks"
REC="$BENCH/bench/tau2-bench/results/2026-11-22-thinkbudget-chain"
PORT=${SPLASH_PORT:-8000}
BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/python/bin/python3"
LIBEXEC=$(dirname "$(dirname "$(dirname "$BIN")")")
MODEL_ID="ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
MODEL_PATH="$HOME/Library/Application Support/Splash/models/$MODEL_ID"
ENGINE_BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/engine/splash"
SERVE_RECORD="$HOME/Library/Application Support/Splash/runtime/serve-8000.json"
mkdir -p "$REC"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$REC/chain.log"; }

sleep "${GRACE_SECONDS:-120}"

if pgrep -f "sample_engine|tau2 run|uv run tau2|probe_requery" > /dev/null; then
  log "thinkbudget: a wave/sampler/probe is running - refusing to restart"; exit 1
fi

inst_pid(){ curl -s --max-time 5 "http://127.0.0.1:$PORT/status" | python3 -c "import json,sys
d=json.load(sys.stdin); print((d.get('instance') or {}).get('pid') or '')" 2>/dev/null; }

wait_idle(){  # safe-to-kill check: engine holds zero active requests, OR the port is dead (nothing
  # to wait for - run1 bug: after our own kill the port was closed, curl failed, '?' != '0', and the
  # chain "waited" 10 min for a nonexistent request stream then aborted).
  local n
  for _ in {1..120}; do
    n=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/status" | python3 -c "import json,sys
print(len((json.load(sys.stdin).get('active_requests') or [])))" 2>/dev/null || echo dead)
    if [ "$n" = "0" ] || [ "$n" = "dead" ]; then return 0; fi
    sleep 5
  done
  return 1
}

relaunch(){  # $1 budget, $2 log file; echoes supervisor pid
  cd "$LIBEXEC" || return 1
  export PYTHONPATH="$LIBEXEC${PYTHONPATH:+:$PYTHONPATH}"
  nohup "$BIN" -u -P -m server.server "$MODEL_PATH" \
    --model "$MODEL_ID" --binary "$ENGINE_BIN" --port "$PORT" --serve-record "$SERVE_RECORD" \
    --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache \
    --default-reasoning-effort=medium --thinking-token-budget="$1" --queue-size=64 \
    < /dev/null > "$2" 2>&1 &
  echo $!
  disown
}

verify_argv(){  # $1 supervisor pid, $2 budget. The SUPERVISOR carries the options: the engine
  # child (`splash serve-native ...`) receives them by internal config, not argv (measured 2026-11-22:
  # its 259-char argv holds no flags at all, and /status does not expose the budget either).
  if ps -o args= -p "$1" | grep -q -- "--thinking-token-budget=$2"; then return 0; fi
  log "ARGV CHECK FAILED for budget $2 (supervisor $1: '$(ps -o args= -p "$1" | tail -c 200)')"
  return 1
}

wait_ready(){  # $1 tag, $2 expected instance pid; dumps status
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
  kill "$1" 2>/dev/null
  for _ in {1..30}; do kill -0 "$1" 2>/dev/null || pgrep -f "splash serve-native" > /dev/null || break; sleep 1; done
  pkill -f "splash serve-native" 2>/dev/null || true
  for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done
}

run_arm(){  # $1 budget
  local B=$1 W="$BENCH/bench/tau2-bench/results/2026-11-22-thinkbudget-$1"
  mkdir -p "$W"
  log "arm $1: launching engine"
  local SUP
  SUP=$(relaunch "$B" "$W/serve.log"); log "arm $1 supervisor pid $SUP"
  if ! wait_ready "ready_$1" "$SUP"; then log "arm $1: launch/identity failed - aborting chain"; return 1; fi
  verify_argv "$SUP" "$B" || return 1
  log "arm $1: engine ready, identity + argv verified"
  TAU2_TRIALS=1 TAU2_SAMPLE_SECONDS=7200 bash "$BENCH/bench/tau2-bench/run_wave.sh" "$W" >> "$W/wave.log" 2>&1
  log "arm $1 wave exit=$?"
  curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$W/status_after.json"
  kill_ours "$SUP" "$1"
}

# ---------- chain ----------
# TB_ARMS lets a resumed chain skip completed arms (run1 completed 8192: full wave on a
# ready+argv-verified 8192 engine, exit=0).
ARM_LIST=${TB_ARMS:-"8192 65536 32768"}
log "thinkbudget chain start (arms: $ARM_LIST, then pin-restore 32768 + control wave if not an arm)"
for B in $ARM_LIST; do
  [ "$B" = "32768" ] && continue   # the 32768 arm IS the pin-restore step, run at the end
  if ! wait_idle; then log "engine live-but-busy >10 min before arm $B - skipping to pin restore"; break; fi
  CUR=$(inst_pid)
  if [ -n "$CUR" ]; then
    kill "$CUR" 2>/dev/null   # first kill: the live (pinned) engine, logged by design
    log "stopped live engine pid $CUR for arm $B"
  fi
  for _ in {1..30}; do pgrep -f "server.server.*--port $PORT" > /dev/null || pgrep -f "splash serve-native" > /dev/null || break; sleep 1; done
  pkill -f "splash serve-native" 2>/dev/null || true
  for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done
  run_arm "$B" || log "arm $B invalid - continuing to pin restore"
done

# pin restore (32768) + same-session control wave, always attempted
if ! wait_idle; then log "engine busy before pin restore - manual restore required"; exit 1; fi
CUR=$(inst_pid)
if [ -n "$CUR" ]; then kill "$CUR" 2>/dev/null; fi
for _ in {1..30}; do pgrep -f "server.server.*--port $PORT" > /dev/null || pgrep -f "splash serve-native" > /dev/null || break; sleep 1; done
pkill -f "splash serve-native" 2>/dev/null || true
for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done
if run_arm 32768; then
  log "thinkbudget chain complete: pin restored (32768) and control wave done"
else
  log "FATAL: pin restore arm failed - manual restore required"
fi
