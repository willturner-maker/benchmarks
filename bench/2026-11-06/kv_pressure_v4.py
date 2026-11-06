#!/usr/bin/env python3
"""Splash bench v4 — KV-pressure probe (long-context, short-output).

Question: how far does load go before `admission.suspended` moves to >= 1?
v3 showed stream WIDTH alone never suspends (transport caps at 32 short requests,
KV footprint at width 32 was ~17% of the resident budget). The binding budget is
resident KV: memory_plan.budget.kv_capacity_tokens ~= 139,264 tokens (int8, 13.2 KB/token).
Prediction: suspension when the SUM of live context tokens passes ~139k and spill can't
cover it. This probe escalates total token footprint, not width:
  per-request prompt ~20k tokens, max_tokens 8, width 2,4,6,8,10,12 (footprint ~40k..240k)
Prompts are UNIQUE per request (unique number-stream offsets) so prefix-cache dedup
doesn't collapse the KV demand into one shared copy.
Sampled every 0.5 s during rounds: admission gauges (waiting/waiting_memory/waiting_concurrency/
suspended/restoring/oldest_wait_ms), kv pages (active/free/allocated), kv_spill moves/unspills,
scheduler, memory_governor headroom, and LIFETIME counters cache.resource_suspensions /
priority_suspensions (catches a suspension even if the gauge sampling misses the instant).
STOP rule: first round where peak admission.suspended > 0 OR lifetime suspension delta > 0
(one round past the first `waiting_memory` trip signal is kept, per the question)."""
import json, os, time, threading, urllib.request
import concurrent.futures as cf

BASE = "http://127.0.0.1:8000"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
# Script-relative: same file the committed baseline lives in, and it runs on any clone.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "kv_pressure_v4.jsonl")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
TARGET_PROMPT = 20000   # tokens per request
MAXTOK = 8
WIDTHS = [2, 4, 6, 8, 10, 12]

def status():
    with urllib.request.urlopen(BASE + "/status", timeout=10) as r:
        return json.load(r)

def prompt_for(seed, lines):
    # unique per (round, request): sequential 5-6 digit streams, offset by seed
    base = seed * 1_000_000
    rows = []
    n = base
    for _ in range(lines):
        rows.append(" ".join(str(n + i) for i in range(10)))
        n += 12
    return "Numbers, no commentary:\n" + "\n".join(rows)

def chat(text):
    body = json.dumps({"model": MODEL, "max_tokens": MAXTOK, "temperature": 0.0,
                       "messages": [{"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    u = d.get("usage", {})
    return {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens")}

GAUGES = [
    ("admission.waiting", lambda s: s["admission"]["waiting"]),
    ("admission.waiting_memory", lambda s: s["admission"]["waiting_memory"]),
    ("admission.waiting_concurrency", lambda s: s["admission"]["waiting_concurrency"]),
    ("admission.suspended", lambda s: s["admission"]["suspended"]),
    ("admission.restoring", lambda s: s["admission"]["restoring"]),
    ("admission.oldest_wait_ms", lambda s: s["admission"]["oldest_wait_ms"]),
    ("kv.pages_active", lambda s: s["kv"]["pages_active"]),
    ("kv.pages_free", lambda s: s["kv"]["pages_free"]),
    ("kv.pages_cache", lambda s: s["kv"]["pages_cache"]),
    ("scheduler.queued", lambda s: s["scheduler"]["queued"]),
    ("scheduler.prefilling", lambda s: s["scheduler"]["prefilling"]),
    ("scheduler.decoding", lambda s: s["scheduler"]["decoding"]),
    ("gov.headroom_bytes", lambda s: s["memory_governor"]["headroom_bytes"]),
]
COUNTERS = [
    ("cache.resource_suspensions", lambda s: s["cache"]["resource_suspensions"]),
    ("cache.priority_suspensions", lambda s: s["cache"]["priority_suspensions"]),
    ("cache.resource_replay_tokens", lambda s: s["cache"]["resource_replay_tokens"]),
    ("kv_spill.spill_moves", lambda s: s["kv_spill"]["spill_moves"]),
    ("kv_spill.unspills", lambda s: s["kv_spill"]["unspills"]),
    ("kv_spill.requests.spill", lambda s: s["kv_spill"]["requests"]["spill"]),
    ("disk.kv_demotions", lambda s: s["disk"]["kv_demotions"]),
    ("scheduler.prefill_rows", lambda s: s["scheduler"]["prefill_rows"]),
]

def get(dotted, s):
    for _, fn in GAUGES + COUNTERS:
        pass
    # dotted lookup via the lambdas table
    tbl = dict(GAUGES + COUNTERS)
    return tbl[dotted](s)

def wait_idle():
    while True:
        s = status()
        sc, ad = s["scheduler"], s["admission"]
        if sc["queued"] == 0 and sc["prefilling"] == 0 and sc["decoding"] == 0 and ad["waiting"] == 0:
            return
        time.sleep(2)

def run_round(width, lines):
    before = status()
    peak = {}
    stop = threading.Event()
    def sampler():
        while not stop.is_set():
            s = status()
            for name, fn in GAUGES:
                v = fn(s)
                if name.endswith("_bytes") or name.endswith("_ms"):
                    peak[name] = max(peak.get(name, 0), v)
                else:
                    peak[name] = max(peak.get(name, -1), v)
            time.sleep(0.5)
    th = threading.Thread(target=sampler, daemon=True); th.start()
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=width) as ex:
        usages = list(ex.map(lambda i: chat(prompt_for(width * 1000 + i, lines)), range(width)))
    wall = time.time() - t0
    stop.set(); th.join(timeout=3)
    after = status()
    deltas = {name: fn(after) - fn(before) for name, fn in COUNTERS}
    return {"width": width, "lines": lines, "wall_s": round(wall, 1),
            "prompt_tokens_each": [u["prompt_tokens"] for u in usages],
            "prompt_tokens_total": sum(u["prompt_tokens"] or 0 for u in usages),
            "peaks": peak, "counter_deltas": deltas}

wait_idle()
# calibration: one request, then resize the line count to hit TARGET_PROMPT
cal = chat(prompt_for(0, 300))
per300 = cal["prompt_tokens"]
lines = max(1, int(300 * TARGET_PROMPT / per300))
print(f"calib: 300 lines = {per300} prompt tokens -> using {lines} lines/request", flush=True)

trip = None
for w in WIDTHS:
    r = run_round(w, lines)
    susp_delta = r["counter_deltas"]["cache.resource_suspensions"] + r["counter_deltas"]["cache.priority_suspensions"]
    print(f"w{w}: {r['prompt_tokens_total']} tok total in {r['wall_s']}s | "
          f"susp_peak={r['peaks']['admission.suspended']} susp_delta={susp_delta} "
          f"waitmem_peak={r['peaks']['admission.waiting_memory']} wait_peak={r['peaks']['admission.waiting']} "
          f"pages_active_peak={r['peaks']['kv.pages_active']} spill+{r['counter_deltas']['kv_spill.spill_moves']} "
          f"unspill+{r['counter_deltas']['kv_spill.unspills']} demote+{r['counter_deltas']['disk.kv_demotions']}", flush=True)
    with open(OUT, "a") as f: f.write(json.dumps(r) + "\n")
    if r["peaks"]["admission.suspended"] > 0 or susp_delta > 0:
        trip = {"width": w, "why": "suspended gauge" if r["peaks"]["admission.suspended"] > 0 else "lifetime counter delta",
                "total_tokens": r["prompt_tokens_total"]}
        break
    time.sleep(10)

wait_idle()
s = status()
print(json.dumps({"TRIP": trip,
                  "predicted_trip_tokens": s["memory_plan"]["budget"]["kv_capacity_tokens"],
                  "final": {"resource_suspensions": s["cache"]["resource_suspensions"],
                            "priority_suspensions": s["cache"]["priority_suspensions"],
                            "replay_tokens": s["cache"]["resource_replay_tokens"],
                            "spill_moves": s["kv_spill"]["spill_moves"], "unspills": s["kv_spill"]["unspills"],
                            "disk_demotions": s["disk"]["kv_demotions"],
                            "capacity_failures": s["metrics"]["capacity_failures"]}}))
