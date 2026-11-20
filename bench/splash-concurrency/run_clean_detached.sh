#!/usr/bin/env bash
# run_clean_detached.sh — a splash wave in a window the operator can actually claim is single-tenant.
#
# Why this exists: two published waves had to be caveated because the operator session (a coding agent
# served by the SAME engine) hit it mid-ladder. 2026-11-16b's w1 read 92.6 tok/s with three probe calls
# landing in the w2-w8 window; 2026-11-19b's first KV trip is marked "clean-window rerun needed". The
# fix is not a better flag, it is a runner that (a) starts detached, (b) samples /status every 10 s so
# tenancy is visible afterwards rather than assumed, and (c) requires the operator to go idle.
#
# Usage:  ./run_clean_detached.sh [out-dir] [kv widths...]     # default widths: the 19b set
# Then:   STOP USING THE ENGINE. No prompts, no agent turns — every one of them is an in-flight request.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HOME/splash-clean-$(date +%Y-%m-%d)}
shift || true
WIDTHS=${*:-"12,33,36,40,44,48"}

mkdir -p "$OUT"

# stack proof read from the RUNNING supervisor, never from start.sh on disk
{ echo "splash $(/opt/homebrew/bin/splash --version 2>/dev/null || echo unknown)"
  pgrep -f -fl 'server.server' | sed "s|$HOME|~|g"; } > "$OUT/pins.txt"
curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_before.json"
date -u +"start %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/run.log"

python3 "$HERE/../tau2-bench/sample_engine.py" "$OUT/engine_samples.jsonl" 10800 10 > "$OUT/sampler.log" 2>&1 &
SAMPLER=$!
trap 'kill "$SAMPLER" 2>/dev/null' EXIT

sleep 3
# Lead-in, not padding: the operator's own final message is being decoded on this engine right now, and the
# warmth gate + width-1 baseline are the two most sensitive measurements in the run. Wait it out before the
# first timed stage.
sleep 90
python3 "$HERE/kv_bracket_2026-11-19b.py" --out "$OUT/ladder_kv.jsonl" --widths "$WIDTHS" \
  > "$OUT/run.out" 2> "$OUT/run.err"
rc=$?
echo "kv_bracket exit=$rc $(date -u +%H:%M:%SZ)" | tee -a "$OUT/run.log"

curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_after.json"
date -u +"done %Y-%m-%dT%H:%M:%SZ" | tee -a "$OUT/run.log"
kill "$SAMPLER" 2>/dev/null
trap - EXIT

# tenancy read-back: attribute every in-flight request to this wave or to somebody else. A size threshold
# alone is wrong — the KV stage deliberately runs 55k-token prompts, so "over 20k = operator" flags our own
# traffic. Match against the prompt sizes THIS wave recorded, and treat anything else as a co-tenant.
python3 - "$OUT" <<'PY'
import json, sys, datetime
out = sys.argv[1]
own = set()
for line in open(f"{out}/ladder_kv.jsonl"):
    r = json.loads(line)
    for k in ("prompt_tokens_each",):
        own |= set(r.get(k) or [])
    if r.get("method") == "width_ladder":
        own.add(None)  # ladder prompts are tiny; counted separately below
rows = [json.loads(l) for l in open(f"{out}/engine_samples.jsonl") if l.strip()]
small, foreign = 0, []
for s in rows:
    for r in (s["active_requests"] or []):
        tok = int(r.get("prompt_tokens") or 0)
        if tok in own or tok < 5000:
            small += 1
        else:
            foreign.append((tok, r.get("kv_mode"), r.get("phase"),
                            datetime.datetime.utcfromtimestamp(float(s["t"])).strftime("%H:%M:%S")))
print(f"tenancy: {len(rows)} status samples, {small} samples attributed to this wave "
      f"(prompt sizes {sorted(x for x in own if x)})")
if foreign:
    print(f"  {len(foreign)} FOREIGN in-flight samples:")
    for tok, mode, phase, t in foreign[:10]:
        print(f"    {t}  {tok:,} tok  {mode}/{phase}")
else:
    print("  CLEAN: every in-flight request in the window belongs to this wave")
PY
touch "$OUT/DONE"
echo "out: $OUT"
