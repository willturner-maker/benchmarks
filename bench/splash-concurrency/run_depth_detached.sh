#!/usr/bin/env bash
# run_depth_detached.sh — the depth probe in a window whose tenancy can be proven afterwards.
# Same discipline as run_clean_detached.sh: detached, sample /status at 10 s, lead-in so the operator's
# own last message finishes decoding, then attribute every in-flight request to this run.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HOME/splash-depth-$(date +%Y-%m-%d)}
shift || true
TURN_TOKENS=${1:-20000}
MAX_TURNS=${2:-16}

mkdir -p "$OUT"
{ echo "splash $(/opt/homebrew/bin/splash --version 2>/dev/null || echo unknown)"
  pgrep -f -fl 'server.server' | sed "s|$HOME|~|g"; } > "$OUT/pins.txt"
curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_before.json"
date -u +"start %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/run.log"

python3 "$HERE/../tau2-bench/sample_engine.py" "$OUT/engine_samples.jsonl" 3600 10 > "$OUT/sampler.log" 2>&1 &
SAMPLER=$!
trap 'kill "$SAMPLER" 2>/dev/null' EXIT

sleep 3
sleep 90   # the operator's last message is still being decoded on this engine
python3 "$HERE/depth_probe.py" --out "$OUT/depth_probe.jsonl" \
  --turn-tokens "$TURN_TOKENS" --max-turns "$MAX_TURNS" > "$OUT/run.out" 2> "$OUT/run.err"
rc=$?
echo "depth_probe exit=$rc $(date -u +%H:%M:%SZ)" | tee -a "$OUT/run.log"

curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_after.json"
date -u +"done %Y-%m-%dT%H:%M:%SZ" | tee -a "$OUT/run.log"
kill "$SAMPLER" 2>/dev/null
trap - EXIT

# tenancy read-back. Depth turns grow, so attribution is by "is this size on the ladder of prompt_tokens
# this run recorded?" rather than a fixed size set.
python3 - "$OUT" <<'PY'
import json, sys, datetime
out = sys.argv[1]
mine = set()
for line in open(f"{out}/depth_probe.jsonl"):
    r = json.loads(line)
    if r.get("kind") == "turn" and r.get("prompt_tokens"):
        mine.add(int(r["prompt_tokens"]))
rows = [json.loads(l) for l in open(f"{out}/engine_samples.jsonl") if l.strip()]
own, foreign = 0, []
for s in rows:
    for q in (s["active_requests"] or []):
        tok = int(q.get("prompt_tokens") or 0)
        if any(abs(tok - m) <= 4096 for m in mine) or tok < 5000:
            own += 1
        else:
            foreign.append((tok, q.get("kv_mode"), q.get("phase"),
                            datetime.datetime.utcfromtimestamp(float(s["t"])).strftime("%H:%M:%S")))
print(f"tenancy: {len(rows)} status samples, {own} attributed to this run "
      f"(turn sizes {sorted(mine)[:1]}..{sorted(mine)[-1:] if mine else '-'})")
if foreign:
    print(f"  {len(foreign)} FOREIGN in-flight samples:")
    for tok, mode, phase, t in foreign[:10]:
        print(f"    {t}  {tok:,} tok  {mode}/{phase}")
else:
    print("  CLEAN: every in-flight request in the window belongs to this run")
PY
touch "$OUT/DONE"
echo "out: $OUT"
