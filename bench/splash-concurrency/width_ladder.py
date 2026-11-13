#!/usr/bin/env python3
"""Splash concurrency ladder v3 — escalates widths well past the first local dip: it
records every width and only STOPS when median aggregate drops toward the width-1
baseline (< 1.10 x the w1 median) — i.e. when added concurrency buys nothing anymore.
(v2 stopped at the first width below the previous width; user 2026-11-06: keep going,
"width 6 still seems practical" — measure the real collapse point.)
Samples /status DURING each round for admission.waiting / queued / suspended peaks.
Widths: 1,2,3,4,6,8,12,16,24,32 (cap 32); 2 rounds per width; same prompt & 512-token
output as the v1 width512 runs for comparability."""
import json, os, time, threading, urllib.request
import concurrent.futures as cf
import statistics as st

BASE = "http://127.0.0.1:8000"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
# /tmp got wiped by macOS; write beside the repo like kv_pressure_v4.py. NOTE: the 2026-11-06
# baseline record IS results/width_ladder_v3.jsonl and this file appends — for a re-run set
# SPLASH_BENCH_OUT to a dated results/<run>/ path so waves don't mix.
OUT = os.environ.get("SPLASH_BENCH_OUT",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "width_ladder_v3.jsonl"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
PROMPT = "List integers from 1 to 240, one per line, and nothing else."
MAXTOK = 512

def status():
    with urllib.request.urlopen(BASE + "/status", timeout=5) as r:
        return json.load(r)

def chat():
    body = json.dumps({"model": MODEL, "max_tokens": MAXTOK, "temperature": 0.0,
                       "messages": [{"role": "user", "content": PROMPT}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    return d.get("usage", {}).get("completion_tokens") or 0

def snap(s):
    return {"dbw": s["scheduler"]["decode_batches_by_width"],
            "suspended": s["admission"]["suspended"], "pressure": s["memory_pressure"]}

def wait_idle():
    while True:
        s = status()["scheduler"]
        if s["queued"] == 0 and s["decoding"] == 0 and s["prefilling"] == 0:
            return
        time.sleep(2)

def run_width(w):
    peak = {"waiting": 0, "queued": 0, "suspended": 0}
    stop = threading.Event()
    def sampler():
        while not stop.is_set():
            s = status()
            peak["waiting"] = max(peak["waiting"], s["admission"]["waiting"])
            peak["queued"] = max(peak["queued"], s["scheduler"]["queued"])
            peak["suspended"] = max(peak["suspended"], s["admission"]["suspended"])
            time.sleep(0.8)
    th = threading.Thread(target=sampler, daemon=True); th.start()
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=w) as ex:
        comps = list(ex.map(lambda _: chat(), range(w)))
    wall = time.time() - t0
    stop.set(); th.join(timeout=3)
    return wall, comps, peak

meds = {}
base = None
stopped = None
for w in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32):
    rounds = []
    for rnd in (1, 2):
        wait_idle()
        a = snap(status())
        wall, comps, peak = run_width(w)
        b = snap(status())
        comp = sum(comps)
        agg = round(comp / wall, 1)
        rounds.append({"round": rnd, "wall_s": round(wall, 2), "completion_each": comps,
                       "aggregate_tok_s": agg, "per_stream_tok_s": round(comp / w / wall, 1),
                       "peak_admission_waiting": peak["waiting"], "peak_queued": peak["queued"],
                       "peak_suspended": peak["suspended"], "dbw_before": a["dbw"], "dbw_after": b["dbw"],
                       "pressure": b["pressure"]})
        with open(OUT, "a") as f: f.write(json.dumps({"width": w, **rounds[-1]}) + "\n")
        print(f"w{w} r{rnd}: {agg} tok/s aggregate, per-stream {round(comp/w/wall,1)}, "
              f"peak waiting {peak['waiting']}", flush=True)
        time.sleep(8)
    med = st.median(r["aggregate_tok_s"] for r in rounds)
    meds[w] = med
    if w == 1:
        base = med
        print(f"== width 1 baseline: {med} tok/s", flush=True)
        continue
    ratio = round(med / base, 3)
    print(f"== width {w}: median {med} tok/s ({ratio}x w1 baseline)", flush=True)
    if med < 1.10 * base:
        stopped = w
        print(f"STOP: aggregate {med} within 10% of w1 baseline {base} — no gain from concurrency", flush=True)
        break

peak_w = max(meds, key=meds.get)
print(json.dumps({"SUMMARY": {"medians_by_width": meds, "stopped_at_width": stopped,
                              "peak_width": peak_w, "peak_tok_s": meds[peak_w],
                              "collapse_width": stopped,
                              "w1_baseline": meds.get(1)}}))
