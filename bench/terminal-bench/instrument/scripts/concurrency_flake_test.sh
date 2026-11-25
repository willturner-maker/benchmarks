#!/bin/bash
# Controlled experiment: does trial concurrency change *outcomes* (not just wall time)?
#
# Why this exists: in gate 2B (-n 3) two tasks failed at oracle, while both passed in phase A
# (-n 2, k=1). Suspect class = load-sensitive verifiers:
#   uefi-bootkit    qemu-system-x86_64 -machine q35,smm=off,accel=kvm:tcg  → on an arm64 host
#                   there is no KVM for an x86 guest, so QEMU runs TCG (software emulation);
#                   its boot checks have fixed timeouts. Passing trials 131/135 s, failing 370/394 s.
#   kv-live-surgery watchdog on a probe loop: deadline 1000 ms; failing trial logged
#                   watchdog_max_gap_ms = 2500.6 (passing trial: 3.0).
#
# Design: same pins, same tasks, only -n varies. k=5 per concurrency level, no retries, so the
# flake rate per concurrency is directly comparable. This must not overlap the gate run itself,
# hence the wait on the gate PID.
set -uo pipefail
cd "$(dirname "$0")/.."

GATE_PID="${1:-}"
TASKS=(uefi-bootkit kv-live-surgery)

if [ -n "$GATE_PID" ]; then
  echo "waiting for gate 2B (pid $GATE_PID) to finish before starting, to avoid adding load…"
  while kill -0 "$GATE_PID" 2>/dev/null; do sleep 30; done
  echo "gate exited at $(date +%H:%M:%S)"
fi

for N in 1 2; do
  OUT="flake-probe-n${N}-2026-11-25"
  ./tb-venv/bin/python scripts/make_probe_dataset.py "probe-dataset-flake-n${N}" "${TASKS[@]}" | head -1
  echo "== -k 5 -n $N -r 0 → $OUT (started $(date +%H:%M:%S))"
  ./tb-venv/bin/harbor run -p "probe-dataset-flake-n${N}" --agent oracle -k 5 -n "$N" -r 0 -o "$OUT" \
    > "flake-probe-n${N}.log" 2>&1
  ./tb-venv/bin/python scripts/summarize_oracle_run.py "$OUT" | tail -8
done

# Outcome + timing distribution per concurrency, since for these two tasks wall time is the
# mechanism (TCG throughput / scheduling gaps), not an incidental detail.
./tb-venv/bin/python - <<'PY'
import json, glob, os
from collections import defaultdict
rows = defaultdict(list)
for out in ("gate2b-full-k5-2026-11-25", "flake-probe-n1-2026-11-25", "flake-probe-n2-2026-11-25"):
    for job in glob.glob(f"{out}/*"):
        n_conc = {"gate2b-full-k5-2026-11-25": 3}.get(out)
        for f in glob.glob(os.path.join(job, "*", "result.json")):
            r = json.load(open(f))
            name = os.path.basename(os.path.dirname(f)).split("__")[0]
            if name not in ("uefi-bootkit", "kv-live-surgery"):
                continue
            if n_conc is None:  # read concurrency from the job config
                cfg = os.path.join(job, "config.json")
                if os.path.exists(cfg):
                    n_conc = json.load(open(cfg)).get("n_concurrent_trials")
            rw = (r.get("verifier_result") or {}).get("rewards") or {}
            rows[(name, n_conc)].append((rw.get("reward"), r.get("started_at"), r.get("finished_at")))
from datetime import datetime
def dur(r):
    a = datetime.fromisoformat(r[1].replace("Z", "+00:00")); b = datetime.fromisoformat(r[2].replace("Z", "+00:00"))
    return (b - a).total_seconds()
print(f"\n{'task':<18} {'-n':>3}  passes  wall times (s)")
for (name, n), v in sorted(rows.items()):
    ok = sum(1 for x in v if x[0] == 1)
    walls = sorted(int(dur(x)) for x in v)
    print(f"{name:<18} {str(n):>3}  {ok}/{len(v)}   {walls}")
PY
