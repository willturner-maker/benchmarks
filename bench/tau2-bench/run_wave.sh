#!/usr/bin/env bash
# shellcheck shell=bash
# tau2-bench runner (sierra-research/tau2-bench) against the local Splash engine.
#
# WHY THIS EXISTS
#   tau2-bench is third-party (MIT, sierra-research/tau2-bench) and is NOT vendored here. We own only this
#   wrapper plus summarize.py: it pins the tag, the endpoint, the exact model id the engine accepts, the
#   judge-free task selection, and it captures the engine stack before/after so a row can name its stack.
#
#   Third-party source lives OUTSIDE the benchmark tree:
#     ~/tau2-bench         pinned tag v1.0.1 = fc0055dc4e0a316c3f83133267fbd6faaa770992, unmodified
#     ~/tau2-bench/.venv   uv-managed (python 3.12, litellm 1.81.11); NOT the MCP venv, NOT the vision venv
#
# JUDGE-FREE SCOPE (see README.md for the derivation)
#   airline   all 50 base tasks   reward_basis [DB, COMMUNICATE]      -> DB hash + substring
#   retail    74 of 114 by id     [DB, NL_ASSERTION] but nl_assertions empty -> NL evaluator short-circuits
#   telecom   all 114 base tasks  [ENV_ASSERTION]                     -> in-process env-assertion replay
#   The 40 retail tasks carrying nl_assertions are EXCLUDED: their judge is gpt-4.1-2025-04-14, a cloud
#   model v1.0.1 gives no way to redirect (no getenv in config.py, no judge flag in cli.py).
#   Task selection uses upstream's own --task-ids; no benchmark data is edited.
#
# Usage:  ./run_wave.sh <wave-dir> [domain ...]        (default: airline retail telecom)
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
TAU2=${TAU2_DIR:-$HOME/tau2-bench}
MODEL=${TAU2_MODEL:-openai/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S}
LLM_ARGS=${TAU2_LLM_ARGS:-'{"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":4096}'}
TRIALS=${TAU2_TRIALS:-2}
CONC=${TAU2_CONCURRENCY:-3}
SEED=${TAU2_SEED:-300}
RETAIL_FREE=(0 1 5 6 7 8 9 10 11 12 13 14 15 17 18 20 22 23 25 26 27 30 31 32 33 34 35 41 42 48 49 50 51 52 53 55 56 57 58 61 64 65 66 69 71 72 73 74 75 77 78 79 80 81 82 83 84 85 86 87 88 90 91 92 93 94 96 97 98 99 100 101 102 112)   # array, not string: safe under bash AND zsh

WAVE=${1:?wave dir required}
shift
DOMS=("$@")
if [ "${#DOMS[@]}" -eq 0 ]; then DOMS=(airline retail telecom); fi

mkdir -p "$WAVE"
WAVE=$(cd "$WAVE" && pwd)   # absolute: the script cd's into $TAU2 below, relative wave dirs must survive it
cd "$TAU2" || exit 1

# pin + stack proof: the tag is verified from the clone, the flags from the RUNNING supervisor
{
  echo "pin $(git rev-parse HEAD) $(git log -1 --format=%ci) $(git log -1 --format=%s)"
  git status --porcelain
  pgrep -f -fl 'server.server' | sed "s|$HOME|~|g"
} > "$WAVE/supervisor_pins.txt"
curl -s --max-time 10 http://127.0.0.1:8000/status > "$WAVE/status_before.json"
printf 'wave started %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$WAVE/wave.log"

# engine sampler: KV residency depth, scheduler queue, admission counters, spill/demote.
# Attribution by prompt_tokens size keeps benchmark traffic separable from co-tenants.
python3 "$HERE/sample_engine.py" "$WAVE/engine_samples.jsonl" 21600 10 > "$WAVE/sampler.log" 2>&1 &
SAMPLER=$!
sleep 3

run_domain() {
  local dom=$1; shift
  echo "===== $dom $(date -u +%H:%M:%SZ) =====" | tee -a "$WAVE/wave.log"
  uv run tau2 run --domain "$dom" \
    --agent-llm "$MODEL" --user-llm "$MODEL" \
    --agent-llm-args "$LLM_ARGS" --user-llm-args "$LLM_ARGS" \
    --num-trials "$TRIALS" --max-concurrency "$CONC" --seed "$SEED" \
    --save-to "wave-$(basename "$WAVE")-$dom" "$@" \
    > "$WAVE/$dom.log" 2>&1
  echo "  exit=$? $(date -u +%H:%M:%SZ)" | tee -a "$WAVE/wave.log"
}

for dom in "${DOMS[@]}"; do
  case "$dom" in
    retail) run_domain retail --task-ids "${RETAIL_FREE[@]}" ;;
    *) run_domain "$dom" ;;
  esac
done

curl -s --max-time 10 http://127.0.0.1:8000/status > "$WAVE/status_after.json"
kill "$SAMPLER" 2>/dev/null
printf 'wave finished %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$WAVE/wave.log"
echo "next: python3 $HERE/summarize.py --tau2-dir $TAU2 --wave-dir $WAVE --domains '${DOMS[*]}'"
