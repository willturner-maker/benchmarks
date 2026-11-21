#!/bin/bash
# Detached: restart the Splash engine BYTE-IDENTICALLY, then run the tau2 same-seed pair.
# Launched mid-turn by an agent session that the engine itself serves — the initial sleep lets that
# turn finish generating before the serving engine goes down (~2 min model load).
#
# Experiment: tau2 derives per-trial seeds as random.seed(--seed) + num_trials draws
# (runner/batch.py:517). Two --num-trials 1 waves at seed 300 BOTH draw 626729, so every task
# in wave A has an identical-seed twin in wave B. Per-task reward disagreements between A and B
# are pure engine-side nondeterminism (no user-sim seed difference left) — the share of the
# published 27.3 % flip rate that is NOT user sampling.
# Restart choice: memory/prefix-cache-cold first arm; note --persistent-cache keeps the DISK KV
# cache across the restart (disclosed in the wave RECORD).
set -euo pipefail

BENCH="$HOME/benchmarks"
REC="$BENCH/bench/splash-concurrency/results/restart-2026-11-21"
PORT=${SPLASH_PORT:-8000}
mkdir -p "$REC"

# --- 0. let the launching agent turn finish (its tokens decode on THIS engine) ---------------
sleep "${SPLASH_RESTART_DELAY:-120}"

SUPER=$(pgrep -f "server.server.*--port $PORT" | head -1)
[ -n "$SUPER" ] || { echo "$(date -u +%FT%TZ) FATAL: no supervisor on port $PORT" >> "$REC/restart.log"; exit 1; }

# --- 1. archive the closing counters of the old launch epoch ---------------------------------
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$REC/status_final_pre_restart.json"
ps -p "$SUPER" -o command= > "$REC/launch_argv.raw.txt"

# --- 2. the byte-identical relaunch command (transcribed from supervisor_pins.txt / ps) -------
BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/python/bin/python3"
ENGINE_BIN="/opt/homebrew/Cellar/splash/1.7.0/libexec/engine/splash"
MODEL_ID="ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
MODEL_PATH="$HOME/Library/Application Support/Splash/models/$MODEL_ID"
SERVE_RECORD="$HOME/Library/Application Support/Splash/runtime/serve-8000.json"
EXPECTED_PS="$BIN -u -P -m server.server $MODEL_PATH --model $MODEL_ID --binary $ENGINE_BIN --port $PORT --serve-record $SERVE_RECORD --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64"
ACTUAL_PS=$(tr -s '[:space:]' ' ' < "$REC/launch_argv.raw.txt" | sed 's/^ //;s/ $//')
if [ "$ACTUAL_PS" != "$EXPECTED_PS" ]; then
  { echo "FATAL: running argv differs from the pinned launch; refusing to restart.";
    diff <(echo "$EXPECTED_PS") <(echo "$ACTUAL_PS"); } >> "$REC/restart.log"
  exit 1
fi

# --- 3. stop supervisor + engine child, wait for the port to free ----------------------------
echo "$(date -u +%FT%TZ) killing supervisor $SUPER" >> "$REC/restart.log"
kill "$SUPER"
for _ in {1..30}; do
  pgrep -f "server.server.*--port $PORT" > /dev/null || pgrep -f "splash serve-native" > /dev/null || break
  sleep 1
done
pkill -f "splash serve-native" 2>/dev/null || true
for _ in {1..15}; do
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1 || break
  sleep 1
done

# --- 4. relaunch detached, poll until ready --------------------------------------------------
# CRITICAL: `-m server.server` resolves the `server` package (lives under libexec) via PYTHONPATH or
# CWD - every past launch inherited it from an interactive shell; a bare relaunch died of
# ModuleNotFoundError (attempt 1, from $HOME). Make the dependency explicit: cd to libexec AND
# export PYTHONPATH. (Note: -P suppresses script-dir/user-site, but PYTHONPATH IS honored.)
LIBEXEC=$(dirname "$(dirname "$(dirname "$BIN")")")   # .../splash/<ver>/libexec/python -> .../libexec
[ -d "$LIBEXEC/server" ] || LIBEXEC=$(dirname "$(find /opt/homebrew/Cellar/splash -maxdepth 3 -type d -name server | head -1)")
echo "$(date -u +%FT%TZ) relaunch from: $LIBEXEC (PYTHONPATH exported)" >> "$REC/restart.log"
cd "$LIBEXEC"
export PYTHONPATH="$LIBEXEC${PYTHONPATH:+:$PYTHONPATH}"
nohup "$BIN" -u -P -m server.server "$MODEL_PATH" \
  --model "$MODEL_ID" \
  --binary "$ENGINE_BIN" \
  --port "$PORT" \
  --serve-record "$SERVE_RECORD" \
  --max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache \
  --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64 \
  < /dev/null > "$REC/serve_stdout.log" 2>&1 &
disown
echo "$(date -u +%FT%TZ) relaunched pid $!" >> "$REC/restart.log"

ready=0
for _ in {1..180}; do
  # guard: a down engine returns an EMPTY body; only feed JSON to the parser, no tracebacks
  body=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/status" || true)
  if [ -n "$body" ] && printf '%s' "$body" | \
     python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ready') else 1)" 2>/dev/null; then
    ready=1; break
  fi
  sleep 5
done
[ "$ready" = 1 ] || { echo "$(date -u +%FT%TZ) FATAL: engine not ready after 15 min" >> "$REC/restart.log"; exit 1; }
curl -s --max-time 10 "http://127.0.0.1:$PORT/status" > "$REC/status_first_post_restart.json"

# --- 5. pin gate: identity/window/KV-pool fields must match the pre-restart snapshot ----------
python3 - "$REC" <<'PY'
import json, sys
rec = sys.argv[1]
b = json.load(open(f"{rec}/status_final_pre_restart.json"))
a = json.load(open(f"{rec}/status_first_post_restart.json"))
def pick(d):
    return {"identity": d.get("identity"), "window": d.get("maximum_context_tokens"),
            "kv": {k: (d.get("kv") or {}).get(k) for k in ("total_pages","pages_active","pages_cache","pages_free","pool_tokens")} }
pb, pa = pick(b), pick(a)
bad = [k for k in pb if pb[k] != pa[k]]
print("post-restart pin check:", "OK" if not bad else f"DRIFT in {bad}", file=sys.stderr)
sys.exit(0 if not bad else 1)
PY
echo "$(date -u +%FT%TZ) engine back, pins verified; starting same-seed pair" >> "$REC/restart.log"

# --- 6. the same-seed pair: two identical single-trial waves, seed 300 (trial seed 626729) ----
cd "$BENCH/bench/tau2-bench"
for arm in a b; do
  TAU2_TRIALS=1 TAU2_SAMPLE_SECONDS=7200 \
    bash run_wave.sh "$BENCH/bench/tau2-bench/results/2026-11-21-sameseed-$arm" \
    >> "$REC/waves.log" 2>&1
  echo "$(date -u +%FT%TZ) wave-$arm done" >> "$REC/restart.log"
done
echo "$(date -u +%FT%TZ) sameseed pair complete" >> "$REC/restart.log"
