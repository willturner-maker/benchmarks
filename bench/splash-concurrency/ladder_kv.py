#!/usr/bin/env python3
"""Splash bench — combined concurrency ladder (v3) + KV-pressure probe (v4).

This is the standing re-run entry point: one invocation runs BOTH methods and
prints ONE combined SUMMARY for the report, so every future version-to-version
diff carries the same two axes:

  Stage 1 — width ladder (v3): same prompt, 512-token outputs, widths
    1,2,3,4,6,8,12,16,24,32; two rounds per width; escalate and STOP only when
    median aggregate falls within 10% of the width-1 baseline (< 1.10x w1).
    Baseline shape (Splash 1.6.0): rise to ~378 by width 4, dip ~330 at 6,
    flat plateau 372-383 through 32, stop rule never fired.

  Stage 2 — KV pressure (v4): unique long-context prompts (calibrated to a
    20k-token target; token counts always reported from usage.prompt_tokens),
    8-token outputs, widths 2,4,6,8,10,12; sample admission/KV/spill/governor
    gauges every 0.5 s plus LIFETIME suspension-counter deltas per round.
    STOP at the first round where peak admission.suspended > 0 or the lifetime
    resource/priority_suspensions counter moves.
    Baseline shape: no suspension even at 611k tokens (4.4x the 139,264-token
    resident KV budget); first waiting_memory hold at w12.

Between stages and rounds the engine is waited to idle; the engine is NEVER
restarted (SSD cache state is part of the measurement).

--quick: minutes-long smoke run of both stages (narrower widths, shorter
  prompts) to verify the harness end to end. NOT for baselining.
Individual baseline-run scripts remain beside this file (engine_probe.py,
width512.py, width_ladder.py, kv_pressure_v4.py) for provenance."""
import argparse, json, os, sys, threading, time, urllib.request
import concurrent.futures as cf
import statistics as st

BASE = "http://127.0.0.1:8000"

def model_id():
    with urllib.request.urlopen(BASE + "/v1/models", timeout=10) as r:
        return json.load(r)["data"][0]["id"]

MODEL = None  # set in main() from /v1/models

def status():
    with urllib.request.urlopen(BASE + "/status", timeout=10) as r:
        return json.load(r)

def wait_idle():
    while True:
        s = status()
        sc, ad = s["scheduler"], s["admission"]
        if sc["queued"] == 0 and sc["prefilling"] == 0 and sc["decoding"] == 0 and ad["waiting"] == 0:
            return
        time.sleep(2)

def chat(text, maxtok):
    body = json.dumps({"model": MODEL, "max_tokens": maxtok, "temperature": 0.0,
                       "messages": [{"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read())
    u = d.get("usage", {})
    return u.get("completion_tokens") or 0, u.get("prompt_tokens") or 0

# ---------------------------------------------------------------- stage 1: width ladder (v3)

LADDER_PROMPT = "List integers from 1 to 240, one per line, and nothing else."

def ladder_width(w, maxtok):
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
        comps = [c for c, _ in ex.map(lambda _: chat(LADDER_PROMPT, maxtok), range(w))]
    wall = time.time() - t0
    stop.set(); th.join(timeout=3)
    return wall, comps, peak

def run_ladder(out, quick):
    widths = (1, 2, 4) if quick else (1, 2, 3, 4, 6, 8, 12, 16, 24, 32)
    maxtok = 128 if quick else 512
    meds, base, stopped = {}, None, None
    for w in widths:
        rounds = []
        for rnd in (1, 2):
            wait_idle()
            wall, comps, peak = ladder_width(w, maxtok)
            agg = round(sum(comps) / wall, 1)
            rec = {"method": "width_ladder", "quick": quick, "width": w, "round": rnd,
                   "wall_s": round(wall, 2), "completion_each": comps, "aggregate_tok_s": agg,
                   "per_stream_tok_s": round(sum(comps) / w / wall, 1),
                   "peak_admission_waiting": peak["waiting"], "peak_queued": peak["queued"],
                   "peak_suspended": peak["suspended"]}
            rounds.append(rec)
            with open(out, "a") as f: f.write(json.dumps(rec) + "\n")
            print(f"[ladder] w{w} r{rnd}: {agg} tok/s aggregate, per-stream "
                  f"{rec['per_stream_tok_s']}, peak waiting {peak['waiting']}", flush=True)
            time.sleep(8)
        med = st.median(r["aggregate_tok_s"] for r in rounds)
        meds[w] = med
        if w == 1:
            base = med
            print(f"[ladder] width 1 baseline: {med} tok/s", flush=True)
            continue
        print(f"[ladder] width {w}: median {med} tok/s ({round(med/base,3)}x w1)", flush=True)
        if med < 1.10 * base:
            stopped = w
            print(f"[ladder] STOP: aggregate {med} within 10% of w1 baseline {base}", flush=True)
            break
    peak_w = max(meds, key=meds.get)
    return {"medians_by_width": meds, "stopped_at_width": stopped, "peak_width": peak_w,
            "peak_tok_s": meds[peak_w], "collapse_width": stopped, "w1_baseline": meds.get(1)}

# ---------------------------------------------------------------- stage 2: KV pressure (v4)

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
    ("disk.kv_demotions", lambda s: s["disk"]["kv_demotions"]),
    ("scheduler.prefill_rows", lambda s: s["scheduler"]["prefill_rows"]),
]

def kv_prompt(seed, lines):
    base = seed * 1_000_000
    rows, n = [], base
    for _ in range(lines):
        rows.append(" ".join(str(n + i) for i in range(10)))
        n += 12
    return "Numbers, no commentary:\n" + "\n".join(rows)

def kv_round(width, lines, out, quick):
    before = status()
    peak = {}
    stop = threading.Event()
    def sampler():
        while not stop.is_set():
            s = status()
            for name, fn in GAUGES:
                peak[name] = max(peak.get(name, -1), fn(s))
            time.sleep(0.5)
    th = threading.Thread(target=sampler, daemon=True); th.start()
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=width) as ex:
        usages = list(ex.map(lambda i: chat(kv_prompt(width * 1000 + i, lines), 8), range(width)))
    wall = time.time() - t0
    stop.set(); th.join(timeout=3)
    after = status()
    deltas = {name: fn(after) - fn(before) for name, fn in COUNTERS}
    rec = {"method": "kv_pressure", "quick": quick, "width": width, "lines": lines,
           "wall_s": round(wall, 1),
           "prompt_tokens_each": [u[1] for u in usages],
           "prompt_tokens_total": sum(u[1] for u in usages),
           "peaks": peak, "counter_deltas": deltas}
    with open(out, "a") as f: f.write(json.dumps(rec) + "\n")
    susp_delta = deltas["cache.resource_suspensions"] + deltas["cache.priority_suspensions"]
    print(f"[kv] w{width}: {rec['prompt_tokens_total']} tok total in {rec['wall_s']}s | "
          f"susp_peak={peak['admission.suspended']} susp_delta={susp_delta} "
          f"waitmem_peak={peak['admission.waiting_memory']} wait_peak={peak['admission.waiting']} "
          f"pages_active_peak={peak['kv.pages_active']} spill+{deltas['kv_spill.spill_moves']} "
          f"demote+{deltas['disk.kv_demotions']}", flush=True)
    return rec, susp_delta

def run_kv(out, quick):
    widths = (2, 4) if quick else (2, 4, 6, 8, 10, 12)
    target = 4000 if quick else 20000
    wait_idle()
    cal_prompt, cal_tokens = chat(kv_prompt(0, 300), 8)  # unused completion, calibrate tokens
    lines = max(1, int(300 * target / cal_tokens))
    print(f"[kv] calib: 300 lines = {cal_tokens} prompt tokens -> using {lines} lines/request", flush=True)
    rounds, trip = [], None
    for w in widths:
        rec, susp_delta = kv_round(w, lines, out, quick)
        rounds.append(rec)
        if rec["peaks"]["admission.suspended"] > 0 or susp_delta > 0:
            trip = {"width": w,
                    "why": "suspended gauge" if rec["peaks"]["admission.suspended"] > 0 else "lifetime counter delta",
                    "total_tokens": rec["prompt_tokens_total"]}
            break
        time.sleep(10)
    wait_idle()
    s = status()
    return {"rounds": len(rounds), "max_total_tokens": max(r["prompt_tokens_total"] for r in rounds),
            "trip": trip, "resident_kv_budget_tokens": s["memory_plan"]["budget"]["kv_capacity_tokens"],
            "lifetime_final": {"resource_suspensions": s["cache"]["resource_suspensions"],
                               "priority_suspensions": s["cache"]["priority_suspensions"],
                               "capacity_failures": s["metrics"]["capacity_failures"]}}

# ---------------------------------------------------------------- main

def main():
    global MODEL
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="/tmp/splash-bench/ladder_kv.jsonl")
    ap.add_argument("--quick", action="store_true", help="smoke mode, not for baselining")
    args = ap.parse_args()
    MODEL = model_id()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    print(f"model: {MODEL}\nout:   {args.out}{'  (QUICK — not for baselining)' if args.quick else ''}", flush=True)
    ladder = run_ladder(args.out, args.quick)
    print("[stage break] waiting for engine idle before KV stage", flush=True)
    wait_idle(); time.sleep(5)
    kv = run_kv(args.out, args.quick)
    print(json.dumps({"SUMMARY": {"quick": args.quick, "model": MODEL,
                                  "width_ladder": ladder, "kv_pressure": kv}}))

if __name__ == "__main__":
    main()
