#!/bin/bash
# Post-1.7.1 backlog chain (2026-11-23), five stages, ordered so engine-state dependencies line up:
#   S1 tau2 confirmation wave: second 238x3 on 1.7.1 - settles whether pass^1 0.8109 was a bad draw
#      or an epoch effect (n=2 for the 1.7.1 epoch).
#   S2 tool-loop-gate (hermes-agentic-bench): the third suite's standard wave on 1.7.1.
#   S3 splash Tier-1: engine_fingerprint capture (post) + golden_probes (within-build floor x2) +
#      diff against the Tier-0 1.7.0 captures - the committed transition method, still on the
#      PINNED instance (must precede S4's relaunch).
#   S4 splash 8-lane ladder: relaunch pinned argv + --max-concurrent-requests 8 (the only new axis,
#      pre-registered in Tier-0's memory arithmetic), run kv_bracket ladder widths 1..32, then
#      ALWAYS restore the pin (launch refused = finding, pin restored anyway).
#   S5 resolve-agentic MCP wave: f1f2 opencode_v2 driver (harness self-check first; media volume
#      verified mounted).
# Initial sleep = grace window for the launching agent turn (rule 10).
set -uo pipefail

BENCH="$HOME/benchmarks"
PORT=${SPLASH_PORT:-8000}
BIN="/opt/homebrew/Cellar/splash/1.7.1/libexec/python/bin/python3"
LIBEXEC=$(dirname "$(dirname "$(dirname "$BIN")")")
MODEL_ID="ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
MODEL_PATH="$HOME/Library/Application Support/Splash/models/$MODEL_ID"
ENGINE_BIN="/opt/homebrew/Cellar/splash/1.7.1/libexec/engine/splash"
SERVE_RECORD="$HOME/Library/Application Support/Splash/runtime/serve-8000.json"
W="$BENCH/bench/tau2-bench/results/2026-11-23-backlog-chain"
mkdir -p "$W"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$W/chain.log"; }

inst_pid(){ curl -s --max-time 5 "http://127.0.0.1:$PORT/status" | python3 -c "import json,sys
d=json.load(sys.stdin); print((d.get('instance') or {}).get('pid') or '')" 2>/dev/null; }
wait_idle(){ local n; for _ in {1..120}; do
  n=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/status" | python3 -c "import json,sys
print(len((json.load(sys.stdin).get('active_requests') or [])))" 2>/dev/null || echo dead)
  if [ "$n" = "0" ] || [ "$n" = "dead" ]; then return 0; fi; sleep 5; done; return 1; }
relaunch(){  # $1 extra flag (may be empty), $2 logfile; echoes supervisor pid
  cd "$LIBEXEC" || return 1
  export PYTHONPATH="$LIBEXEC${PYTHONPATH:+:$PYTHONPATH}"
  if [ -n "$1" ]; then
    nohup "$BIN" -u -P -m server.server "$MODEL_PATH" \
      --model "$MODEL_ID" --binary "$ENGINE_BIN" --port "$PORT" --serve-record "$SERVE_RECORD" \
      --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache \
      --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64 "$1" \
      < /dev/null > "$2" 2>&1 &
  else
    nohup "$BIN" -u -P -m server.server "$MODEL_PATH" \
      --model "$MODEL_ID" --binary "$ENGINE_BIN" --port "$PORT" --serve-record "$SERVE_RECORD" \
      --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache \
      --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64 \
      < /dev/null > "$2" 2>&1 &
  fi
  echo $!
  disown
}
wait_ready(){  # $1 tag, $2 expected pid, $3 outdir
  local body p
  for _ in {1..180}; do
    body=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/status" || true)
    if [ -n "$body" ] && printf '%s' "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ready') else 1)" 2>/dev/null; then
      printf '%s' "$body" > "$3/status_$1.json"
      p=$(printf '%s' "$body" | python3 -c "import json,sys; print((json.load(sys.stdin).get('instance') or {}).get('pid') or '')")
      if [ "$p" = "$2" ]; then return 0; fi
      log "IDENTITY MISMATCH ($1): live pid $p != launched $2 - hands off"; return 2
    fi
    sleep 5
  done
  return 1
}
kill_ours(){  # $1 our pid
  local live; live=$(inst_pid)
  if [ -n "$live" ] && [ "$live" != "$1" ]; then log "REFUSING to kill foreign instance pid $live"; return 1; fi
  kill "$1" 2>/dev/null
  for _ in {1..30}; do kill -0 "$1" 2>/dev/null || pgrep -f "splash serve-native" > /dev/null || break; sleep 1; done
  pkill -f "splash serve-native" 2>/dev/null || true
  for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done
}
port_free(){ for _ in {1..30}; do pgrep -f "server.server.*--port $PORT" > /dev/null || pgrep -f "splash serve-native" > /dev/null || break; sleep 1; done
  pkill -f "splash serve-native" 2>/dev/null || true
  for _ in {1..15}; do lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break; sleep 1; done; }

sleep "${GRACE_SECONDS:-120}"
log "backlog chain start (S1 tau2-confirm, S2 gate, S3 tier1-fingerprint, S4 8-lane ladder, S5 MCP wave)"

# ---------- S1: tau2 confirmation wave ----------
RW="$BENCH/bench/tau2-bench/results/2026-11-23-pass3-171-confirm"
mkdir -p "$RW"
log "S1: 238x3 confirmation wave on 1.7.1"
TAU2_TRIALS=3 TAU2_SAMPLE_SECONDS=21600 bash "$BENCH/bench/tau2-bench/run_wave.sh" "$RW" >> "$RW/runner.log" 2>&1
log "S1 exit=$?"

# ---------- S2: tool-loop-gate ----------
GW="$BENCH/bench/tool-loop-gate/results/2026-11-23-gate-171"
mkdir -p "$GW"
log "S2: tool-loop-gate on 1.7.1 (upstream pin in runner/RECORD)"
bash "$BENCH/bench/tool-loop-gate/run_gate.sh" "$GW" >> "$GW/runner.log" 2>&1
log "S2 exit=$?"

# ---------- S3: splash Tier-1 (pinned instance) ----------
TW="$BENCH/bench/splash-concurrency/results/splash-1.7.1-transition"
mkdir -p "$TW"
log "S3: fingerprint capture + golden probes on 1.7.1 pinned instance"
python3 "$BENCH/bench/splash-concurrency/engine_fingerprint.py" capture --out "$TW/fingerprint-1.7.1-post.json" > "$W/s3_fingerprint.out" 2>&1
log "S3 fingerprint exit=$?"
python3 "$BENCH/bench/splash-concurrency/golden_probes.py" --out "$TW/golden-probes-1.7.1-post.json" > "$W/s3_golden.out" 2>&1
log "S3 golden probes exit=$?"
python3 "$BENCH/bench/splash-concurrency/engine_fingerprint.py" diff \
  "$TW/fingerprint-1.7.0-pre.json" \
  "$TW/fingerprint-1.7.1-post.json" > "$W/s3_fingerprint_diff.txt" 2>&1
log "S3 fingerprint diff exit=$?"
python3 "$BENCH/bench/splash-concurrency/golden_probes.py" --compare \
  "$TW/golden-probes-1.7.0-pre.json" \
  "$TW/golden-probes-1.7.1-post.json" > "$W/s3_golden_compare.txt" 2>&1
log "S3 golden compare exit=$?"

# ---------- S4: 8-lane ladder ----------
LW="$BENCH/bench/splash-concurrency/results/ladder-8lane-2026-11-23"
mkdir -p "$LW"
if wait_idle; then
  CUR=$(inst_pid); if [ -n "$CUR" ]; then kill "$CUR" 2>/dev/null; log "S4: stopped pinned instance pid $CUR"; fi
  port_free
  SUP=$(relaunch "--max-concurrent-requests=8" "$LW/serve_8lane.log"); log "S4 8-lane supervisor pid $SUP"
  if wait_ready ready_8lane "$SUP" "$LW"; then
    python3 "$BENCH/bench/splash-concurrency/sample_engine.py" "$LW/engine_samples.jsonl" 5400 10 > "$LW/sampler.log" 2>&1 &
    S1PID=$!
    python3 "$BENCH/bench/splash-concurrency/kv_bracket_2026-11-19b.py" --out "$LW/ladder_kv.jsonl" --widths "1,2,4,8,16,32" > "$LW/run.out" 2> "$LW/run.err"
    log "S4 kv_bracket exit=$?"
    kill "$S1PID" 2>/dev/null
  else
    log "S4 8-lane launch failed or identity mismatch (Tier-0 memory arithmetic predicted possible refusal) - finding, restoring pin"
  fi
  kill_ours "${SUP:-none}" || true
else
  log "S4: engine live-but-busy >10 min - skipping 8-lane arm"
fi
port_free
SUPP=$(relaunch "" "$W/serve_pinrestore.log"); log "pin supervisor pid $SUPP"
if wait_ready pin_restored "$SUPP" "$W"; then log "S4 pin restored and ready"; else log "FATAL: pin restore not ready - manual start required"; fi

# ---------- S5: resolve-agentic MCP wave ----------
MW="$BENCH/bench/resolve-agentic/results/agbench-171-2026-11-23"
mkdir -p "$MW"
cd "$BENCH/bench/resolve-agentic" || { log "S5: no resolve-agentic dir - skipping"; exit 1; }
log "S5: MCP wave harness self-check"
python3 wave_driver_f1f2_opencode_v2.py --check-harness > "$W/s5_check.out" 2>&1
log "S5 check-harness exit=$?"
log "S5: MCP f1f2 opencode_v2 wave on 1.7.1"
python3 wave_driver_f1f2_opencode_v2.py --out "$MW" > "$W/s5_wave.out" 2>&1
log "S5 exit=$?"
log "backlog chain complete"
