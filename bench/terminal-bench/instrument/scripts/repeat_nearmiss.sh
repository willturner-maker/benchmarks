#!/bin/bash
# Targeted k=3 repeats on the 6 near-miss tasks from the k=1 wave
# (wave-tb41-k1-n2-2026-11-25). Selection rule fixed BEFORE this run: the six tasks with the
# highest fraction of verifier checks passed in the k=1 wave (wal-recovery-ordering 96/97,
# distributed-dedup 12/13, embedding-drift-monitor 10/11, production-planning 18/20,
# photonic-waveguide-routing 12/14, foodstuff-beta-activity 11/13). The original plan was
# "k=3 for any non-zero task + a 6-task control"; the wave produced zero non-zero tasks, so
# the control became the near-miss set — these are the tasks most likely to flip to 1, which
# is where a stability estimate is worth paying for. kv-live-surgery (5/6) is 7th by the same
# ranking and excluded by the rule, noted in the record.
#
# Everything else inherits the wave pins: same dataset digests, -n 2, -r 0, horizon x0.05
# (1440 s), max_turns 40, reasoning at engine default. A pass under the SAME horizon is a
# fair pass; horizon is not relaxed for repeats.
set -uo pipefail
cd "$(dirname "$0")/.."

[ -f GATE2B-PASS ] || { echo "refusing: GATE2B-PASS absent"; exit 3; }

ENGINE_URL="${ENGINE_URL:-http://127.0.0.1:8000/v1}"
MODEL_ID="${MODEL_ID:-ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S}"
MAX_TURNS="${MAX_TURNS:-40}"
TIMEOUT_MULT="${TIMEOUT_MULT:-0.05}"
NCONC="${NCONC:-2}"
DATASET="probe-dataset-repeat6"
OUT="${OUT:-repeat-nearmiss-k3-2026-11-26}"

./tb-venv/bin/python scripts/make_probe_dataset.py "$DATASET" \
  wal-recovery-ordering distributed-dedup embedding-drift-monitor \
  production-planning photonic-waveguide-routing foodstuff-beta-activity || exit 3
N_ENTRIES=$(ls "$DATASET" | wc -l | tr -d ' ')
[ "$N_ENTRIES" -eq 7 ] || { echo "STOP: $DATASET has $N_ENTRIES entries, expected 7 (6 tasks + dataset.toml)"; exit 3; }

curl -sf "$ENGINE_URL/models" | ./tb-venv/bin/python -c "
import json,sys
ids=[m['id'] for m in json.load(sys.stdin).get('data',[])]
assert '$MODEL_ID' in ids, 'served id != pin'
print('engine pin ok:', ids)
" || { echo "engine not answering at $ENGINE_URL"; exit 4; }
./tb-venv/bin/python scripts/routing_selftest.py "$MODEL_ID" "$ENGINE_URL" || exit 4
grep -c "chmod 1777" tb-venv/lib/python3.12/site-packages/harbor/environments/base.py | sed 's/^/   chmod-1777 sites: /'
echo "   task tree: $(git rev-parse HEAD) ($(git describe --tags))"

mkdir -p "$OUT"
{ echo "# Repeat pins: identical to wave-tb41-k1-n2-2026-11-25 except -k 3 and the 6-task subset"; \
  sed -n '2,25p' wave-tb41-k1-n2-2026-11-25/pins.txt; \
  echo "selection    top-6 by k=1 check fraction (rule above); k=3; horizon unchanged"; } > "$OUT/pins.txt"

echo "== repeat: terminus-2, k=3 (18 trials), -n $NCONC, -r 0 (started $(date +%H:%M:%S))"
./tb-venv/bin/harbor run \
  -p "$DATASET" \
  --agent terminus-2 \
  --model "openai/${MODEL_ID}" \
  --skip-model-parsing-and-provider-mapping \
  --base-url "$ENGINE_URL" \
  --api-key-name SPLASH_API_KEY \
  --ak "max_turns=$MAX_TURNS" \
  --agent-timeout-multiplier "$TIMEOUT_MULT" \
  -k 3 -n "$NCONC" -r 0 \
  -o "$OUT" > "repeat-nearmiss.log" 2>&1
RC=$?

./tb-venv/bin/python scripts/pilot_verdict.py "$OUT" "$MODEL_ID" | tee "$OUT/verdict.txt"
./tb-venv/bin/python scripts/summarize_model_run.py "$OUT" "$MODEL_ID" --json "$OUT/repeat-summary.json" | tee "$OUT/summary.txt"
exit $RC
