#!/bin/bash
# Stage 3 — model pilot: the pinned local engine driven through Harbor's own agent (terminus-2).
#
# GATED: refuses to run until gate 2B has been reviewed and marked, because the whole point of
# the oracle gate is that we do not spend model tokens against an unproven environment.
# Override with --force only deliberately.
#
# Pins this depends on (all recorded in PLAN-2026-11-25.md):
#   task tree    git tag v4.1.0 = 4070d6cef56a7d20cb5dc98d5e10ada88a6b9440, subset datasets built
#                by scripts/make_probe_dataset.py (upstream digests copied verbatim)
#   runner       harbor 0.27.0 + patches/tb-log-dirs-sticky.patch (REQUIRED; see harbor#4469)
#   runtime      OrbStack 2.2.5 / Docker 29.8.2, docker VM 31.36 GiB / 30 CPU (raised 2026-11-25)
#   engine       Splash 1.7.1, OpenAI-compatible at http://127.0.0.1:8000/v1,
#                served model id ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S (owned_by splash)
#   agent        terminus-2, max_turns capped, agent timeout multiplied down (task defaults are
#                up to 28800 s, which is a horizon we do not need for a pilot)
set -euo pipefail
cd "$(dirname "$0")/.."

FORCE=0
for a in "$@"; do [ "$a" = "--force" ] && FORCE=1; done
if [ ! -f GATE2B-PASS ] && [ $FORCE -eq 0 ]; then
  echo "refusing: gate 2B not marked (write GATE2B-PASS after reviewing the 58x5 oracle table)."
  echo "current gate 2B state:"
  ls -d gate2b-full-k5-2026-11-25/*/ 2>/dev/null | head -2 || echo "  (no gate 2B job dir)"
  exit 3
fi

ENGINE_URL="${ENGINE_URL:-http://127.0.0.1:8000/v1}"
MODEL_ID="${MODEL_ID:-ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S}"
MAX_TURNS="${MAX_TURNS:-40}"
TIMEOUT_MULT="${TIMEOUT_MULT:-0.05}"
OUT="${OUT:-pilot-terminus-2026-11-25}"

echo "== engine pin check"
curl -sf "$ENGINE_URL/models" | ./tb-venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)
ids=[m['id'] for m in d.get('data',[])]
print('served:', ids)
assert '$MODEL_ID' in ids, 'served model id does not match the pin — stop'
" || { echo "engine not answering at $ENGINE_URL"; exit 4; }
ps -Ao command | grep -i "engine/splash" | grep -v grep | head -1 | cut -c1-220 | sed 's/^/argv: /'

# Routing prefix. Harbor's split_provider_model_name() treats the first "/"-separated
# component as a provider, so the HF-style served id "ISTA-DASLab/Qwen3.8-…:IQ3_S" parses as
# provider "ista-daslab" and litellm raises "LLM Provider NOT provided" (this is what voided the
# first pilot: 3/3 BadRequestError in 2m38s). The `openai/` prefix is a CLIENT-SIDE routing label
# only: verified below, the engine receives and echoes the pinned id unchanged
# (response.model == "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S").
LITELLM_MODEL="openai/${MODEL_ID}"

# Routing self-test: one request through the exact client path the agent uses (litellm + api_base),
# asserting the engine's reported model equals the pin. Cheaper than discovering this again via a
# whole pilot of void trials.
./tb-venv/bin/python scripts/routing_selftest.py "$MODEL_ID" "$ENGINE_URL" || exit 4

echo "== runner patch check"
grep -c "chmod 1777" tb-venv/lib/python3.12/site-packages/harbor/environments/base.py \
  | sed 's/^/chmod-1777 sites: /'
git -C . rev-parse HEAD | sed 's/^/task tree: /'

# "Did the run actually reach the model?" needs attributable evidence, because global engine
# counters are NOT attributable here: this operator session is itself served by the engine it is
# benchmarking, so request/token counters move during every run regardless. Evidence used instead:
#   (1) the engine log numbers requests monotonically ("TTFT of request N: …"), so the run's own
#       window is a count of requests in play;
#   (2) a short idle control window measures this session's own request rate, and the run's window
#       must exceed that baseline by a wide margin;
#   (3) per-trial agent trajectory files under the job dir, which are attributable to a trial.
# Token counters are still recorded, as context for cost sizing, not as the pass/fail test.
LOG="$HOME/Library/Logs/splash/splash.err.log"
METRICS_URL="${ENGINE_URL%/v1}/metrics"
mkdir -p "$OUT"
lastreq(){ [ -f "$LOG" ] && grep -oE "request [0-9]+" "$LOG" | tail -1 | grep -oE "[0-9]+" || echo 0; }
snap(){ curl -sf -m 5 "$METRICS_URL" | grep -E "splash_(requests_(submitted|completed)_total|prefill_input_tokens_total|decode_output_tokens_total)" | awk '{print $1, $2}'; }
snap > "$OUT/engine-metrics-before.txt" || { echo "engine /metrics unavailable at $METRICS_URL"; exit 4; }
R0=$(lastreq); T0=$(date +%s)
echo "== engine request number at start: $R0 | counters (context):"; sed 's/^/   /' "$OUT/engine-metrics-before.txt"
echo "== 120 s idle control: measuring this session's own request rate as a baseline"
sleep 120
RCTL=$(($(lastreq) - R0)); TCTL=$(( $(date +%s) - T0 ))
RC0=$(lastreq)
echo "   session-only baseline: $RCTL requests over ${TCTL}s"

echo "== pilot dataset (3 cheap clean tasks)"
./tb-venv/bin/python scripts/make_probe_dataset.py probe-dataset-pilot \
  session-window-debug fin-saccr-rwa music-harmony | head -1

echo "== pilot run: terminus-2, k=1, n=2, no retries, max_turns=$MAX_TURNS, agent-timeout x$TIMEOUT_MULT"
./tb-venv/bin/harbor run \
  -p probe-dataset-pilot \
  --agent terminus-2 \
  --model "$LITELLM_MODEL" \
  --skip-model-parsing-and-provider-mapping \
  --base-url "$ENGINE_URL" \
  --ak "max_turns=$MAX_TURNS" \
  --api-key-name SPLASH_API_KEY \
  --agent-timeout-multiplier "$TIMEOUT_MULT" \
  -k 1 -n 2 -r 0 \
  -o "$OUT"
STATUS=$?

R1=$(lastreq); T1=$(date +%s)
snap > "$OUT/engine-metrics-after.txt"
{ echo "request_window: $R0 -> $R1"; echo "session_baseline_raw: $RCTL over ${TCTL}s (NOT extrapolated — see below)"; } > "$OUT/engine-attribution.txt"
echo "== attribution: Harbor's own per-trial model_usage is the authority, engine counters are context"
./tb-venv/bin/python scripts/pilot_verdict.py "$OUT" "$MODEL_ID"
echo "== engine token counters (context for cost sizing; includes this session's inference):"
sed 's/^/   /' "$OUT/engine-metrics-after.txt" 2>/dev/null
exit $STATUS
