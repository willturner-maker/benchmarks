#!/bin/bash
# shellcheck shell=bash
# Tool-loop gate runner (hermes-agentic-bench `hermes_loop_gate.py`) against the local Splash engine.
#
# WHY THIS EXISTS
#   The upstream script is third-party (MIT, vcruz305/hermes-agentic-bench) and is deliberately NOT
#   vendored into this repo. This wrapper is the only thing we own: it pins the endpoint, the exact
#   model id the engine accepts, and the two sampling axes we publish (harness defaults, and greedy),
#   and it captures the engine stack around the runs so a row can name its stack.
#
# Third-party source is kept OUTSIDE the benchmark tree:
#   ~/hermes-agentic-bench   (upstream commit pinned in RECORD.md; unmodified)
#   ~/hermes-agentic-bench/.venv  (isolated: python 3.12 + httpx only; NOT the MCP venv, NOT the vision venv)
#
# Usage:  ./run_gate.sh <wave-dir> [pass-label ...]
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
UP=${UPSTREAM:-$HOME/hermes-agentic-bench}
PY=$UP/.venv/bin/python
MODEL=${MODEL:-ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S}
BASE=${GATE_BASE:-http://127.0.0.1:8000/v1}

WAVE=${1:?wave dir required}
if [ "$#" -gt 0 ]; then shift; fi
if [ "$#" -gt 0 ]; then PASSES=("$@"); else PASSES=(defaults greedy); fi

mkdir -p "$WAVE"

# stack proof: read the pins from the RUNNING supervisor, never from the file on disk
pgrep -f -fl "server.server" > "$WAVE/supervisor_pins.txt"
curl -s --max-time 10 http://127.0.0.1:8000/status > "$WAVE/status_before.json"

for label in "${PASSES[@]}"; do
  case "$label" in
    defaults) extra=() ;;                                    # upstream defaults: temp 0.6 / top_p 0.95 / top_k 64
    greedy)   extra=(--temperature 0 --top-p 1.0 --top-k 1) ;;
    *) echo "unknown pass label: $label (use: defaults | greedy)"; exit 2 ;;
  esac
  echo "== $label =="
  OUT=$WAVE/gate-$label-$(date +%Y%m%dT%H%M%S)
  ( cd "$UP" && "$PY" hermes_loop_gate.py --base-url "$BASE" --api-key local \
      --model "$MODEL" ${extra[@]+"${extra[@]}"} --output "$OUT.json" ) > "$OUT.log" 2>&1
  tail -1 "$OUT.log"
done

curl -s --max-time 10 http://127.0.0.1:8000/status > "$WAVE/status_after.json"
echo "== flatten + re-derive =="
python3 "$HERE/summarize.py" "$WAVE"
