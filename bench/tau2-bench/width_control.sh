#!/usr/bin/env bash
# width_control.sh — does removing batching remove the tau2 flips?
#
# The published answer (bench/tau2-bench/results/2026-11-19b-width-control/RECORD.md): NO. At
# --max-concurrency 1 the engine produced b1 batches only (19,439 of them, peak 1 request in flight,
# zero co-tenant samples), and 3 of 8 sampled flipping tasks still flipped — the same count as the
# --max-concurrency 3 replication of the same tasks, with almost no overlap in WHICH tasks flipped.
#
# Design rules this script encodes, learned the hard way:
#   * Run DETACHED and stay off the engine. The first attempt at this control was discarded because the
#     operator session was live: /status showed 8,599 batches wider than b1 during a "concurrency 1" run.
#   * Sample /status at 10 s and read the decode widths from the DELTAS. The flag you passed is not proof
#     of the condition the engine ran in.
#   * Same tasks, same seed, two trials per arm; both arms in one script so the comparison cannot drift.
#
# Usage: ./width_control.sh [out-dir] [airline ids...] -- retail ids... -- telecom ids...
#        (defaults are the 8 tasks the published control used)
set -uo pipefail

TAU2=${TAU2_DIR:-$HOME/tau2-bench}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HOME/tau2-width-control-$(date +%Y-%m-%d)}
shift || true
MODEL=${TAU2_MODEL:-openai/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S}
LLM_ARGS=${TAU2_LLM_ARGS:-'{"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":4096}'}
SEED=${TAU2_SEED:-300}
TRIALS=${TAU2_TRIALS:-2}

AIRLINE=(12 33 29)
RETAIL=(66 91 90)
TELECOM=('[mobile_data_issue]airplane_mode_on|bad_network_preference|bad_vpn|data_saver_mode_on|data_usage_exceeded|user_abroad_roaming_enabled_off[PERSONA:None]'
         '[mms_issue]break_app_both_permissions|unseat_sim_card|user_abroad_roaming_disabled_on[PERSONA:Hard]')

mkdir -p "$OUT"
cd "$TAU2" || exit 1

# pin + live stack proof: tag/commit from the clone, engine flags from the RUNNING supervisor
{ echo "pin $(git rev-parse HEAD) $(git log -1 --format=%ci)"; git status --porcelain;
  pgrep -f -fl 'server.server' | sed "s|$HOME|~|g"; } > "$OUT/pins.txt"
curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_before.json"
date -u +"start %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/control.log"

python3 "$HERE/sample_engine.py" "$OUT/engine_samples.jsonl" 7200 10 > "$OUT/sampler.log" 2>&1 &
SAMPLER=$!
trap 'kill "$SAMPLER" 2>/dev/null' EXIT
sleep 3

run_arm() {
  local conc=$1 dom=$2; shift 2
  echo "== arm c$conc $dom n=$# $(date -u +%H:%M:%SZ)" | tee -a "$OUT/control.log"
  uv run tau2 run --domain "$dom" \
    --agent-llm "$MODEL" --user-llm "$MODEL" \
    --agent-llm-args "$LLM_ARGS" --user-llm-args "$LLM_ARGS" \
    --num-trials "$TRIALS" --max-concurrency "$conc" --seed "$SEED" \
    --task-ids "$@" --save-to "ctl-c${conc}-${dom}" > "$OUT/c${conc}-${dom}.log" 2>&1
  echo "   exit=$? $(date -u +%H:%M:%SZ)" | tee -a "$OUT/control.log"
}

for conc in 1 3; do
  run_arm "$conc" airline "${AIRLINE[@]}"
  run_arm "$conc" retail "${RETAIL[@]}"
  run_arm "$conc" telecom "${TELECOM[@]}"
done

curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_after.json"
date -u +"done %Y-%m-%dT%H:%M:%SZ" | tee -a "$OUT/control.log"
kill "$SAMPLER" 2>/dev/null
trap - EXIT
echo "next: python3 build_rows.py --out <dir>/tasks.jsonl $TAU2/data/simulations/ctl-c{1,3}-{airline,retail,telecom}"
