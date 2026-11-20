#!/usr/bin/env python3
"""Sample the Splash engine /status during a tau2 run: KV residency depth, scheduler queue, prefill rate.

τ² is the first workload here that holds ONE context across many turns with tool schemas in the
prompt, so this is the depth-not-volume KV probe. Written to JSONL; join later on wall clock.
"""
import json, sys, time, urllib.request

out = sys.argv[1] if len(sys.argv) > 1 else "engine_samples.jsonl"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
interval = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
t_end = time.time() + secs
with open(out, "w") as f:
    while time.time() < t_end:
        try:
            s = json.load(urllib.request.urlopen("http://127.0.0.1:8000/status", timeout=5))
        except Exception as e:
            time.sleep(interval); continue
        kv, sc, mp = s["kv"], s["scheduler"], s["memory_plan"]
        rec = {
            "t": round(time.time(), 1),
            "active_requests": s["active_requests"],
            "pages_active": kv["pages_active"],
            "kv_tokens_active": kv["pages_active"] * kv["block_tokens"],
            "kv_budget_tokens": mp["budget"]["kv_capacity_tokens"],
            "queued": sc["queued"], "prefilling": sc["prefilling"], "decoding": sc["decoding"],
            "prefill_rows": sc["prefill_rows"], "prefill_batches": sc["prefill_batches"],
            "decode_batches_by_width": sc["decode_batches_by_width"],
            "admission": s["admission"],
            "spill_moves": s.get("kv_spill", {}).get("spill_moves"),
            "kv_demotions": s.get("disk", {}).get("kv_demotions"),
            "suspensions": s["cache"].get("resource_suspensions", 0) + s["cache"].get("priority_suspensions", 0),
        }
        f.write(json.dumps(rec) + "\n"); f.flush()
        time.sleep(interval)
