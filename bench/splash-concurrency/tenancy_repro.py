#!/usr/bin/env python3
"""Tenancy reproduction — can co-tenant residency produce the 2026-11-16b KV trip?

The published sequence is:
  * 16b (2026-11-16, dirty window): KV stage TRIPPED at width 10 — 509,370 tokens = 3.89x the then
    131,072-token budget, peak admission.suspended 2, waiting_memory 2, pages_active 7,238,
    lifetime resource_suspensions +3, disk kv_demotions +1,502. Published as "first trip on record",
    with the threshold shift explicitly unestablished.
  * 19c-clean (2026-11-19, single-tenant by attribution): NO TRIP at 2,652,720 tokens = 17.04x the
    155,648-token budget, and pages_active pinned at 0.39x of budget because width becomes queue
    depth. That retires the token-threshold reading of 16b, and we published that the *cause* of
    16b's trip is still open.

This script attacks the open half on purpose. Same KV ladder in two arms, back to back on one engine
launch, and the only thing that changes is whether something else is holding long contexts resident:

  arm A  clean        — KV widths 2,4,6,8,10,12 at the 16b prompt scale, nothing else on the engine
  arm B  co-tenanted  — identical KV rounds, with N synthetic "operator" sessions running the whole
                        time: long-context prompts (~120k tokens) with real decode (512 tokens), which
                        is what a coding agent on the same engine actually puts in KV.

If B trips (suspensions / waiting_memory / spill / demotions) where A does not, the 16b regime is
reproducible and the mechanism is residency contention, not prompt volume. If B also does not trip,
the hypothesis is not supported and 16b stays unexplained.

Stop rule per round (deltas only): refusal, admission.suspended > 0, resource/priority suspension
delta, kv_demotions_refused delta, capacity_failures delta. Prompts use a fresh seed namespace and
every round validates prefill_rows against its own prompt tokens, so a cache-served round is never
mistaken for pressure (suite rule 3).
"""
import argparse
import json
import os
import sys
import concurrent.futures as cf
import threading
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
WIDTHS = (2, 4, 6, 8, 10, 12)
CO_TENANT_TARGET_TOKENS = 120_000   # an operator/agent context, not a benchmark prompt
CO_TENANT_MAX_TOKENS = 512
CO_TENANT_CONCURRENCY = 3
ROUNDS_PER_WIDTH = 2


def status():
    with urllib.request.urlopen(BASE + "/status", timeout=10) as r:
        return json.load(r)


def counters(s):
    return {
        "cache.resource_suspensions": s["cache"]["resource_suspensions"],
        "cache.priority_suspensions": s["cache"]["priority_suspensions"],
        "kv_spill.spill_moves": s["kv_spill"]["spill_moves"],
        "disk.kv_demotions": s["disk"]["kv_demotions"],
        "disk.kv_demotions_refused": s["disk"]["kv_demotions_refused"],
        "metrics.capacity_failures": s["metrics"]["capacity_failures"],
        "scheduler.prefill_rows": s["scheduler"]["prefill_rows"],
    }


def peaks(s):
    a, kv, sc = s["admission"], s["kv"], s["scheduler"]
    return {"admission.waiting": a["waiting"], "admission.waiting_memory": a["waiting_memory"],
            "admission.suspended": a["suspended"], "admission.restoring": a.get("restoring", 0),
            "kv.pages_active": kv["pages_active"],
            "kv_tokens_active": kv["pages_active"] * kv["block_tokens"],
            "kv.pages_cache": kv["pages_cache"], "scheduler.queued": sc["queued"],
            "scheduler.prefilling": sc["prefilling"], "scheduler.decoding": sc["decoding"]}


def chat(text, maxtok):
    body = json.dumps({"model": MODEL, "max_tokens": maxtok, "temperature": 0.0,
                       "messages": [{"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            d = json.loads(r.read())
    except Exception as e:                       # refusals are data (suite rule 4)
        return {"error": str(e)[:300]}
    u = d.get("usage") or {}
    return {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens")}


def bench_prompt(tag, words):
    return ("List nothing. Reference block: " + " ".join(f"{tag}-w{i}" for i in range(words)))


def wait_idle():
    while True:
        s = status()
        sc, ad = s["scheduler"], s["admission"]
        if sc["queued"] == 0 and sc["prefilling"] == 0 and sc["decoding"] == 0 and ad["waiting"] == 0:
            return
        time.sleep(2)


class CoTenant:
    """Synthetic operator: continuous long-context requests with real decode."""

    def __init__(self, n, tokens):
        self.n, self.tokens = n, tokens
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.stats = {"sent": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0,
                      "wall_s_sum": 0.0}
        self.thr = []

    def _worker(self, k):
        i = 0
        while not self.stop.is_set():
            tag = f"tenancyrepro-ct{k}-i{i}"
            t0 = time.time()
            r = chat(bench_prompt(tag, self.tokens // 13), CO_TENANT_MAX_TOKENS)
            with self.lock:
                self.stats["wall_s_sum"] += time.time() - t0
                if "error" in r:
                    self.stats["errors"] += 1
                else:
                    self.stats["sent"] += 1
                    self.stats["prompt_tokens"] += r.get("prompt_tokens") or 0
                    self.stats["completion_tokens"] += r.get("completion_tokens") or 0
            i += 1

    def __enter__(self):
        for k in range(self.n):
            t = threading.Thread(target=self._worker, args=(k,), daemon=True)
            t.start(); self.thr.append(t)
        return self

    def __exit__(self, *a):
        self.stop.set()
        for t in self.thr:
            t.join(timeout=30)


def run_arm(out, widths, arm):
    words = 1500                                   # ~20k tokens at the engine's own tokenizer
    prev = counters(status())
    for w in widths:
        for rnd in range(1, ROUNDS_PER_WIDTH + 1):
            wait_idle()
            before = peaks(status())
            t0 = time.time()
            with cf.ThreadPoolExecutor(max_workers=w) as ex:
                res = list(ex.map(lambda j: chat(bench_prompt(f"tenancyrepro-{arm}-w{w}-{rnd}-{j}", words),
                                                 8), range(w)))
            wall = round(time.time() - t0, 2)
            after_s = status()
            after = peaks(after_s)
            now = counters(after_s)
            deltas = {k: now[k] - prev[k] for k in now}
            prev = now
            ok = [r for r in res if "error" not in r]
            errs = [r for r in res if "error" in r]
            ptot = sum(r.get("prompt_tokens") or 0 for r in ok)
            rec = {"method": "tenancy_repro", "arm": arm, "width": w, "round": rnd,
                   "ok": len(ok), "errors": errs, "prompt_tokens_total": ptot,
                   "prefill_rows_delta": deltas["scheduler.prefill_rows"],
                   "fresh_prefill": deltas["scheduler.prefill_rows"] >= ptot * 0.98,
                   "peaks_pre": before, "peaks_post": after, "counter_deltas": deltas,
                   "wall_s": wall}
            trip = (errs or deltas["cache.resource_suspensions"] > 0
                    or deltas["cache.priority_suspensions"] > 0
                    or deltas["disk.kv_demotions_refused"] > 0
                    or deltas["metrics.capacity_failures"] > 0
                    or after["admission.suspended"] > 0)
            rec["trip"] = bool(trip)
            with open(out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"[{arm}] w{w:2d} r{rnd}: {ptot:,} tok {wall}s ok={len(ok)} err={len(errs)} "
                  f"pages_active {after['kv.pages_active']} ({after['kv_tokens_active']:,} tok) "
                  f"susp+{deltas['cache.resource_suspensions']} waitmem_peak {after['admission.waiting_memory']} "
                  f"spill+{deltas['kv_spill.spill_moves']} demote+{deltas['disk.kv_demotions']}"
                  f"{'  <-- TRIP' if trip else ''}", flush=True)
            if trip:
                return rec
            time.sleep(6)
    return None


def main():
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/splash-bench/tenancy_repro.jsonl")
    ap.add_argument("--widths", default=",".join(str(w) for w in WIDTHS))
    ap.add_argument("--co-tenant-concurrency", type=int, default=CO_TENANT_CONCURRENCY)
    ap.add_argument("--co-tenant-tokens", type=int, default=CO_TENANT_TARGET_TOKENS)
    ap.add_argument("--skip-clean", action="store_true",
                    help="only run the co-tenanted arm (use when the clean arm already ran)")
    args = ap.parse_args()

    MODEL = json.load(urllib.request.urlopen(BASE + "/v1/models", timeout=10))["data"][0]["id"]
    s0 = status()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    widths = [int(x) for x in args.widths.split(",") if x.strip()]
    header = {"method": "tenancy_repro", "kind": "setup", "model": MODEL, "widths": widths,
              "rounds_per_width": ROUNDS_PER_WIDTH,
              "co_tenant": {"concurrency": args.co_tenant_concurrency,
                            "target_prompt_tokens": args.co_tenant_tokens,
                            "max_tokens": CO_TENANT_MAX_TOKENS},
              "kv_capacity_tokens": s0["memory_plan"]["budget"]["kv_capacity_tokens"],
              "maximum_context_tokens": s0.get("maximum_context_tokens"),
              "lifetime_at_start": counters(s0)}
    with open(args.out, "a") as f:
        f.write(json.dumps(header) + "\n")
    print(f"model {MODEL}  KV budget {header['kv_capacity_tokens']:,} tok  widths {widths}", flush=True)

    if not args.skip_clean:
        print("== arm A: clean (nothing else on the engine) ==", flush=True)
        run_arm(args.out, widths, "clean")
        wait_idle(); time.sleep(10)

    print(f"== arm B: co-tenanted ({args.co_tenant_concurrency} sessions @ "
          f"~{args.co_tenant_tokens:,} tok) ==", flush=True)
    with CoTenant(args.co_tenant_concurrency, args.co_tenant_tokens) as ct:
        time.sleep(20)                       # let the co-tenant reach steady state
        trip = run_arm(args.out, widths, "co_tenant")
        ct_stats = dict(ct.stats)
    s_end = status()
    tail = {"method": "tenancy_repro", "kind": "summary", "trip_round": trip,
            "co_tenant_stats": ct_stats,
            "lifetime_deltas": {k: counters(s_end)[k] - header["lifetime_at_start"][k] for k in counters(s_end)}}
    with open(args.out, "a") as f:
        f.write(json.dumps(tail) + "\n")
    print(json.dumps(tail, indent=1)[:1200], flush=True)


if __name__ == "__main__":
    sys.exit(main())
