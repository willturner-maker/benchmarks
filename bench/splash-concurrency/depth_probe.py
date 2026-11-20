#!/usr/bin/env python3
"""Splash depth probe — one context walking the RESIDENT line while held across turns.

Every wave in this suite has pushed prompt VOLUME (many long requests at once) and none of them could
trip the KV pool: at 17.04x the 155,648-token resident budget, pages_active pinned at 0.39x of it,
because extra width becomes scheduler queue depth, not residency (see
results/splash-1.7.0-2026-11-19c-clean/RECORD.md). The lever that has never been measured is the other
axis: ONE conversation, growing turn over turn, crossing the resident line and then the window.

Design:
  * one chat conversation, N turns; each turn appends a fresh filler block (unique per turn, fresh seed
    namespace, so nothing is served from the persistent prefix cache);
  * replies stay tiny (max_tokens 8) so decode is irrelevant and the cost is prefill + KV residency;
  * every turn records: prompt_tokens as the engine reports it (usage), pages_active / kv_tokens_active,
    admission + spill + demote + suspension COUNTER DELTAS for that turn, governor headroom, context_bounds,
    and wall time;
  * stop at the first refusal / truncation signal / counter movement, or at the reported window.

The interesting readings are (a) whether prompt_tokens keeps equaling the sent size or the server starts
silently truncating, (b) whether pages_active finally climbs past the plateau once residency is the
constraint, (c) what the response header/status says at the resident line (155,633) and the window (262,144).

Run it in a window you can claim is single-tenant: python3 depth_probe.py --out <dir>/depth_probe.jsonl
"""
import argparse
import json
import os
import statistics as st
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
SEED_NAMESPACE = "depth-2026-11-19"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
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


def gauges(s):
    kv, ad, mp = s["kv"], s["admission"], s["memory_plan"]
    return {
        "kv.pages_active": kv["pages_active"],
        "kv_tokens_active": kv["pages_active"] * kv["block_tokens"],
        "kv.pages_free": kv["pages_free"],
        "kv.pages_cache": kv["pages_cache"],
        "admission.waiting": ad["waiting"],
        "admission.waiting_memory": ad["waiting_memory"],
        "admission.suspended": ad["suspended"],
        "budget.kv_capacity_tokens": mp["budget"]["kv_capacity_tokens"],
        "budget.maximum_batch_width": mp["budget"].get("maximum_batch_width"),
        "governor.headroom_bytes": s["memory_governor"].get("headroom_bytes"),
    }


def filler(turn, tokens):
    # unique-per-turn words so the prefix cache cannot serve the block back
    words = [f"{SEED_NAMESPACE}-t{turn}-w{i}" for i in range(tokens)]
    return ("Reply with the single word READY. Context block: " + " ".join(words))


def chat(messages, maxtok):
    body = json.dumps({"model": MODEL, "max_tokens": maxtok, "temperature": 0.0,
                       "messages": messages}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return None, {"code": e.code, "body": e.read().decode("utf-8", "replace")[:400]}


def main():
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/splash-bench/depth_probe.jsonl")
    ap.add_argument("--turn-tokens", type=int, default=20000)
    ap.add_argument("--max-turns", type=int, default=16)
    args = ap.parse_args()

    MODEL = get("/v1/models")["data"][0]["id"]
    s0 = get("/status")
    cb = s0.get("context_bounds") or {}
    budget = s0["memory_plan"]["budget"]["kv_capacity_tokens"]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    print(f"model {MODEL}\nresident KV budget {budget:,} tok  context_bounds {json.dumps(cb)}\n"
          f"turn size ~{args.turn_tokens:,} words, max {args.max_turns} turns", flush=True)

    header = {"method": "depth_probe", "kind": "setup", "model": MODEL, "seed_namespace": SEED_NAMESPACE,
              "turn_words": args.turn_tokens, "context_bounds": cb,
              "maximum_context_tokens": s0.get("maximum_context_tokens"),
              "kv_capacity_tokens": budget,
              "kv_page_bytes": s0["memory_plan"]["budget"].get("kv_page_bytes"),
              "kv_capacity_pages": s0["memory_plan"]["budget"].get("kv_capacity_pages"),
              "lifetime_at_start": counters(s0), "gauges_at_start": gauges(s0)}

    msgs = [{"role": "user", "content": filler(0, 200)}]
    # calibrate: the token cost of a filler word is engine-side, not ours to assume
    d0, e0 = chat(msgs, 8)
    words = args.turn_tokens
    if not e0:
        per_word = ((d0.get("usage") or {}).get("prompt_tokens") or 0) / 220.0
        if per_word > 0:
            words = max(50, int(args.turn_tokens / per_word))
            print(f"calibration: 200-word probe = {(d0.get('usage') or {}).get('prompt_tokens')} prompt "
                  f"tokens -> {per_word:.2f} tok/word, so a {args.turn_tokens:,}-token turn is "
                  f"~{words:,} words", flush=True)
    header["turn_words"] = words
    with open(args.out, "a") as f:
        f.write(json.dumps(header) + "\n")
    prev = counters(s0)
    sent_words = 0
    stop = None
    for turn in range(1, args.max_turns + 1):
        block = filler(turn, words)
        sent_words += words
        msgs.append({"role": "user", "content": block})
        pre = gauges(get("/status"))
        t0 = time.time()
        d, err = chat(msgs, 8)
        wall = round(time.time() - t0, 2)
        post_s = get("/status")
        post = gauges(post_s)
        now = counters(post_s)
        deltas = {k: now[k] - prev[k] for k in now}
        prev = now
        rec = {"method": "depth_probe", "kind": "turn", "turn": turn,
               "sent_words_cum": sent_words, "messages": len(msgs)}
        if err:
            rec.update({"ok": False, "error": err, "wall_s": wall,
                        "gauges_pre": pre, "gauges_post": post, "counter_deltas": deltas})
            with open(args.out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"[turn {turn:2d}] REFUSED {err['code']}: {err['body'][:90]}", flush=True)
            stop = "refusal"
            break
        u = d.get("usage") or {}
        pt, ct = u.get("prompt_tokens"), u.get("completion_tokens")
        choice = (d.get("choices") or [{}])[0]
        rec.update({"ok": True, "prompt_tokens": pt, "completion_tokens": ct,
                    "finish_reason": choice.get("finish_reason"),
                    "content": (choice.get("message") or {}).get("content"),
                    "wall_s": wall, "gauges_pre": pre, "gauges_post": post,
                    "counter_deltas": deltas,
                    "prompt_over_resident": round(pt / budget, 3) if pt else None})
        with open(args.out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[turn {turn:2d}] prompt {pt:,} tok ({pt/budget:.2f}x resident) out {ct} finish "
              f"{rec['finish_reason']} wall {wall}s pages_active {post['kv.pages_active']} "
              f"({post['kv_tokens_active']:,} tok) susp+{deltas['cache.resource_suspensions']} "
              f"spill+{deltas['kv_spill.spill_moves']} demote+{deltas['disk.kv_demotions']}", flush=True)
        msgs.append({"role": "assistant", "content": rec["content"] or "READY"})
        for k in ("cache.resource_suspensions", "disk.kv_demotions_refused", "metrics.capacity_failures"):
            if deltas[k] > 0:
                stop = f"counter moved: {k} +{deltas[k]}"
        if stop:
            break
        time.sleep(4)

    s_end = get("/status")
    tail = {"method": "depth_probe", "kind": "summary", "stopped": stop,
            "turns": turn, "lifetime_deltas": {k: counters(s_end)[k] - header["lifetime_at_start"][k]
                                               for k in counters(s_end)},
            "gauges_end": gauges(s_end)}
    with open(args.out, "a") as f:
        f.write(json.dumps(tail) + "\n")
    print(json.dumps(tail, indent=1), flush=True)


if __name__ == "__main__":
    main()
