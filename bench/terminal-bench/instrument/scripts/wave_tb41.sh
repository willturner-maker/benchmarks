#!/bin/bash
# Stage 4 — the local wave: pinned engine x terminus-2 over the 57-task digest-pinned candidate
# set, one attempt each at the gate's concurrency. Scope chosen from measured pilot cost
# (~110k output tokens and ~19 min per trial at -n 2): full coverage at k=1, with targeted x3
# repeats to follow for any task scoring non-zero plus a control sample — rather than paying 3x
# across the whole set for a stability estimate where it may not matter.
#
# GATED: refuses without GATE2B-PASS (gate 2C passed at -n 2; the wave inherits that concurrency,
# because -n is global per job and kv-live-surgery flakes at -n 3).
set -uo pipefail
cd "$(dirname "$0")/.."

[ -f GATE2B-PASS ] || { echo "refusing: GATE2B-PASS absent — gate 2C has not been stamped"; exit 3; }

ENGINE_URL="${ENGINE_URL:-http://127.0.0.1:8000/v1}"
MODEL_ID="${MODEL_ID:-ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S}"
MAX_TURNS="${MAX_TURNS:-40}"
TIMEOUT_MULT="${TIMEOUT_MULT:-0.05}"      # task agent timeouts run to 28800 s; 0.05 -> 1440 s cap
NCONC="${NCONC:-2}"
DATASET="probe-dataset-gate2c"
OUT="${OUT:-wave-tb41-k1-n2-2026-11-25}"

echo "== engine pin check"
curl -sf "$ENGINE_URL/models" | ./tb-venv/bin/python -c "
import json,sys
ids=[m['id'] for m in json.load(sys.stdin).get('data',[])]
print('served:', ids)
assert '$MODEL_ID' in ids, 'served id != pin'
" || { echo "engine not answering at $ENGINE_URL"; exit 4; }
ps -Ao command | grep -i "engine/splash" | grep -v grep | head -1 | cut -c1-200 | sed 's/^/argv: /'

echo "== routing self-test (one request, through the agent's own client path)"
./tb-venv/bin/python scripts/routing_selftest.py "$MODEL_ID" "$ENGINE_URL" || exit 4

echo "== runner + tree checks"
grep -c "chmod 1777" tb-venv/lib/python3.12/site-packages/harbor/environments/base.py | sed 's/^/   chmod-1777 sites: /'
echo "   task tree: $(git rev-parse HEAD) ($(git describe --tags))"
N_ENTRIES=$(ls "$DATASET" | wc -l | tr -d ' ')
[ "$N_ENTRIES" -eq 58 ] || { echo "STOP: $DATASET has $N_ENTRIES entries, expected 58 (57 tasks + dataset.toml)"; exit 3; }
echo "   dataset: $DATASET ($((N_ENTRIES - 1)) tasks, digest-pinned)"
AGENT_CAP=$(./tb-venv/bin/python -c "print(int(28800 * $TIMEOUT_MULT))")

mkdir -p "$OUT"
cat > "$OUT/pins.txt" <<EOF
# Wave pins — Terminal-Bench v4.1.0 local candidate set, model-driven  (written before the run)
task tree        git $(git rev-parse HEAD) == tag $(git describe --tags); in-tree dataset, digests pinned
runner           harbor 0.27.0 + patches/tb-log-dirs-sticky.patch (required; upstream harbor#4469)
runtime          OrbStack 2.2.5 / Docker 29.8.2; docker VM 31.36 GiB / 30 CPU (raised 2026-11-25)
agent            terminus-2 (host-side; calls the engine over its OpenAI-compatible endpoint)
model            $MODEL_ID  (served id asserted from /v1/models and echoed by the engine)
routing          --model openai/<served id>: client-side provider label only; engine receives the
                 pinned id verbatim (verified by scripts/routing_selftest.py before launch)
reasoning        engine default (reasoning_effort NOT set). Measured on this engine: 'none' would
                 give reasoning=0, 'minimal' reasoning=19/23 — bounding thinking is available but
                 capability-altering, so this wave leaves it alone and states the horizon instead.
horizon          --agent-timeout-multiplier $TIMEOUT_MULT (task default up to 28800 s -> ${AGENT_CAP} s cap);
                 max_turns $MAX_TURNS. Timeouts are reported as timeouts, not folded into score.
concurrency      -n $NCONC  (must equal the gate's -n; -n is global per Harbor job)
retries          -r 0
attempts         k=1 (targeted k=3 repeats follow for non-zero tasks + a control sample)
candidate set    57 of 66 in-tree tasks; the 9 exclusions and reasons are in exclusions.txt
zero-token n/a   this wave is model-driven; model activity is proved afterwards by
                 scripts/pilot_verdict.py on per-trial model_usage billed to the pinned id
EOF
cp gate2c-full-k5-n2-2026-11-25/exclusions.txt "$OUT/exclusions.txt" 2>/dev/null || \
  echo "WARN: could not copy exclusions.txt from the gate 2C run dir"

echo "== wave: terminus-2, k=1, -n $NCONC, -r 0, max_turns=$MAX_TURNS, agent-timeout x$TIMEOUT_MULT"
echo "   -> $OUT (started $(date +%H:%M:%S); pilot rate projects ~9-11 h)"
./tb-venv/bin/harbor run \
  -p "$DATASET" \
  --agent terminus-2 \
  --model "openai/${MODEL_ID}" \
  --skip-model-parsing-and-provider-mapping \
  --base-url "$ENGINE_URL" \
  --api-key-name SPLASH_API_KEY \
  --ak "max_turns=$MAX_TURNS" \
  --agent-timeout-multiplier "$TIMEOUT_MULT" \
  -k 1 -n "$NCONC" -r 0 \
  -o "$OUT" > "wave-tb41.log" 2>&1
RC=$?

echo "== verdict (per-trial accounting is the authority)"
./tb-venv/bin/python scripts/pilot_verdict.py "$OUT" "$MODEL_ID" | tee "$OUT/verdict.txt"
echo "== summary"
./tb-venv/bin/python scripts/summarize_model_run.py "$OUT" "$MODEL_ID" --json "$OUT/wave-summary.json" \
  | tee "$OUT/summary.txt"
exit $RC
