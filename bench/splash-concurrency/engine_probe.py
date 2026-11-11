#!/usr/bin/env python3
"""Splash engine deterministic probe — 2026-11-06 baseline (Splash 1.6.0, schema 8).
Adapted from archive/concurrency-scaling-test.md (draft, never run) for schema 8 + keyless :8000.
Lighter context size (800-1000 tokens, not 32K) to spare the shared engine; noted in results."""
import json, time, urllib.request, statistics as st

BASE = "http://127.0.0.1:8000"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
OUT = "/tmp/splash-bench-2026-11-06/engine_probe.jsonl"

def status():
    with urllib.request.urlopen(BASE + "/status", timeout=5) as r:
        return json.load(r)

def chat(prompt, max_tokens, temperature=0.0):
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "temperature": temperature,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    wall = time.time() - t0
    u = d.get("usage", {})
    return {"wall_s": round(wall, 3), "completion_tokens": u.get("completion_tokens"),
            "prompt_tokens": u.get("prompt_tokens")}

def snap(d):
    s = status()
    return {"decode_batches": s["scheduler"]["decode_batches"],
            "prefill_rows": s["scheduler"]["prefill_rows"],
            "dbw": s["scheduler"]["decode_batches_by_width"],
            "cache_hits": s["cache"]["hits"], "cold_misses": s["cache"]["cold_misses"],
            "requests_completed": s["requests"]["completed"],
            "admission_waiting": s["admission"]["waiting"]}

def wait_idle():
    while True:
        s = status()["scheduler"]
        if s["queued"] == 0 and s["decoding"] == 0 and s["prefilling"] == 0:
            return
        time.sleep(2)

FILLER = ("The quick brown fox jumps over the lazy dog near the riverbank while geese gather. " * 15).strip()
P_DECODE = "List integers from 1 to 240, one per line, and nothing else."
P_TTFT = FILLER + "\n\nQuestion: how many times is 'fox' written above? Answer with just the number."
P_W = FILLER[:1600] + "\n\nAnswer with exactly: READY"

rows = []
def emit(kind, extra):
    r = {"kind": kind, **extra}
    rows.append(r)
    with open(OUT, "a") as f: f.write(json.dumps(r) + "\n")
    print(json.dumps(r), flush=True)

if __name__ == "__main__":
    meta = status()
    emit("meta", {"splash_model": MODEL, "ready": meta["ready"],
                  "mem": meta["memory_pressure"], "thermal": meta["thermal_state"]})

    # A) single-stream decode, 3 passes
    for i in range(3):
        wait_idle(); a = snap(status())
        r = chat(P_DECODE, 300)
        b = snap(status())
        r.update({"pass": i + 1, "decode_batch_delta": b["decode_batches"] - a["decode_batches"],
                  "engine_tok_s": round(r["completion_tokens"] / r["wall_s"], 1) if r["completion_tokens"] else None})
        emit("decode_w1", r); time.sleep(5)

    # B) TTFT cold vs warm (same 1k prompt twice; second hits prefix cache)
    for i in range(2):
        wait_idle()
        r = chat(P_TTFT, 8)
        r["pass"] = i + 1; r["note"] = "cold" if i == 0 else "warm-prefix"
        emit("ttft", r); time.sleep(3)

    # C) concurrency widths 1,2,4 (2 rounds each)
    import concurrent.futures as cf
    for width in (1, 2, 4):
        for rnd in (1, 2):
            wait_idle(); a = snap(status())
            t0 = time.time()
            with cf.ThreadPoolExecutor(max_workers=width) as ex:
                rs = list(ex.map(lambda _: chat(P_W, 24), range(width)))
            wall = time.time() - t0
            b = snap(status())
            emit("width", {"width": width, "round": rnd, "wall_s": round(wall, 3),
                           "per_request": rs, "aggregate_tok_s": round(sum(x["completion_tokens"] or 0 for x in rs) / wall, 2),
                           "decode_batch_delta": b["decode_batches"] - a["decode_batches"],
                           "admission_waiting_max_seen": b["admission_waiting"]})
            time.sleep(10)

    dec = [r["engine_tok_s"] for r in rows if r["kind"] == "decode_w1" and r["engine_tok_s"]]
    print(json.dumps({"SUMMARY": {"decode_w1_med_tok_s": st.median(dec) if dec else None}}))
