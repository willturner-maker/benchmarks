#!/usr/bin/env bash
# run_tenancy_detached.sh — the tenancy A/B in a bounded window, with an attribution read-back.
# Hard deadline inside tenancy_repro.py is the backstop; this wrapper never waits on the engine.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HOME/splash-tenancy-$(date +%Y-%m-%d)}
DEADLINE_MIN=${2:-25}

mkdir -p "$OUT"
{ echo "splash $(/opt/homebrew/bin/splash --version 2>/dev/null || echo unknown)"
  pgrep -f -fl 'server.server' | sed "s|$HOME|~|g"; } > "$OUT/pins.txt"
curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_before.json"
date -u +"start %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/run.log"

python3 "$HERE/../tau2-bench/sample_engine.py" "$OUT/engine_samples.jsonl" 3600 10 > "$OUT/sampler.log" 2>&1 &
SAMPLER=$!
trap 'kill "$SAMPLER" 2>/dev/null' EXIT

sleep 3
sleep 90   # operator last-message lead-in; see suite rule 11
python3 "$HERE/tenancy_repro.py" --out "$OUT/tenancy_repro.jsonl" \
  --deadline-minutes "$DEADLINE_MIN" > "$OUT/run.out" 2> "$OUT/run.err"
rc=$?
echo "tenancy_repro exit=$rc $(date -u +%H:%M:%SZ)" | tee -a "$OUT/run.log"

curl -s --max-time 10 http://127.0.0.1:8000/status > "$OUT/status_after.json"
date -u +"done %Y-%m-%dT%H:%M:%SZ" | tee -a "$OUT/run.log"
kill "$SAMPLER" 2>/dev/null
trap - EXIT

# tenancy read-back: the run has TWO by-design request families (bench ~23k, co-tenant ~128k);
# anything else in flight — including the operator's agent session — is contamination.
python3 - "$OUT" <<'PY'
import json, sys, datetime
out = sys.argv[1]
rounds, ct = [], None
for line in open(f"{out}/tenancy_repro.jsonl"):
    r = json.loads(line)
    if r.get("kind") == "setup":
        ct = int(r["co_tenant"]["target_prompt_tokens"])
    if r.get("method") == "tenancy_repro" and "width" in r:
        rounds.append((r["arm"], r["width"], r["prompt_tokens_total"] // max(1, r["ok"])))
rows = [json.loads(l) for l in open(f"{out}/engine_samples.jsonl") if l.strip()]
fam = [22906, ct]  # bench round size and co-tenant target (co-tenant actuals land near target)
own, foreign = 0, []
for s in rows:
    for q in (s["active_requests"] or []):
        tok = int(q.get("prompt_tokens") or 0)
        if any(abs(tok - f) <= 4096 for f in fam if f):
            own += 1
        else:
            foreign.append((tok, q.get("phase"),
                            datetime.datetime.fromtimestamp(float(s["t"]), datetime.UTC).strftime("%H:%M:%S")))
print(f"rounds recorded: {len(rounds)} | in-flight samples attributed: {own}")
if foreign:
    print(f"  {len(foreign)} FOREIGN samples (operator or other co-tenants):")
    for tok, phase, t in foreign[:10]:
        print(f"    {t}  {tok:,} tok  {phase}")
else:
    print("  window contained only this run's two request families")
PY
touch "$OUT/DONE"
echo "out: $OUT"
