#!/usr/bin/env python3
"""Splash bench — 2026-11-19b: KV pressure in the queueing regime (queue-size 64 stack move).

Supersedes what ladder_kv_ext_2026-11-19.py could measure, and fixes three flaws it exposed.

What the morning run proved (records in results/splash-1.7.0-2026-11-19-ext/):
  * The w40 HTTP 503 was NOT KV pressure. A tiny-prompt probe pinned it exactly: w32 admitted,
    w33 refused instantly, waiting_concurrency=0 and held_behind_refusal=0 (refused, never
    queued), body "frontend request capacity is exhausted / frontend_overloaded" — the
    documented --queue-size default of 32.
  * Within 32 streams the KV never suspends: pages_active sat pinned at 1,654 pages (52,928
    tokens) for every fresh round w16..w32 while kv_spill.spill_moves and disk.kv_demotions
    climbed. The governor answers KV pressure with spill/demote, so the standing stop rule
    ("wait for a suspension event") watches a gauge this stack does not use.
  * Beyond w12 prefill is flat at 3,513.7-3,520.7 tok/s (+-0.2%): width buys nothing, and
    memory_plan.maximum_batch_width = 4 is the mechanism behind the ~700 tok/s plateau.

Three flaws corrected here:
  1. Seed namespace. Prompts are deterministic, so the 11-19 w2/w12 "stitch controls" were
     byte-identical to 11-18 and came back from the persistent disk cache: 93,530 tok in 0.4 s
     and 612,180 tok in 1.5 s, with scheduler.prefill_rows moving only 26 and 84. Here seeds are
     a fresh namespace and every round REQUIRES prefill_rows delta ~= prompt tokens, or the round
     is marked cache_served and not counted as pressure.
  2. Refusals are data. chat() in the sealed primitives raises on non-2xx, which is what killed
     the morning driver and lost its SUMMARY. Here every request is wrapped, and a refusal is
     recorded (code + body) as the round's outcome.
  3. Warmth gate must be like-for-like. The morning gate used a prose prompt and read 77-117
     tok/s while the ladder's own w1 measured 294.4, so it licensed nothing. Here the gate reuses
     LADDER_PROMPT and max_tokens 512, the same primitive as the baseline it is meant to certify.

Stop rule (revised gauges): a round trips on any refusal, admission.suspended > 0, a lifetime
suspension-counter delta, disk.kv_demotions_refused delta > 0, or metrics.capacity_failures
delta > 0. Host memory pressure is sampled each round as a safety readout.

Widths stay BELOW the serve-time queue-size, and the run refuses to start otherwise: at
queue-size 64 the top probe width is 48, leaving slack for one interactive session so a refusal
means the engine's limit, not our own saturation. To probe past that, launch
QUEUE_SIZE=96 ./start.sh and pass --widths with higher values.

Same launch also carries the 2026-11-19 thinking-budget raise to 32768 (engine_config.json records
whatever the supervisor actually runs). That is a second stack move, but it is inert for both stages
here: ladder completions are pinned at 512 tokens and KV completions at 8, so no request can reach a
thinking cap. The comparable-throughput check is stage 1 - if the ladder does not land near 294 /
693-701, queue-size or the budget moved the instance state and the KV rounds are read against that.
"""
import argparse, json, os, subprocess, sys, threading, time, urllib.error, urllib.request
import concurrent.futures as cf
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ladder_kv as L  # sealed primitives: status/wait_idle/kv_prompt/ladder_width/run_ladder

BASE = L.BASE
SEAL_LADDER_WIDTHS = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32)
KV_TARGET_TOKENS = 20000          # same calibration as the sealed stage (~51k tok/request in practice)
SEED_NAMESPACE = 900_000          # fresh vs 11-18 (width*1000+i) and 11-19 (same) prompt namespaces
DEFAULT_WIDTHS = (12, 33, 36, 40, 44, 48)


def q(s, path):
    cur = s
    for p in path.split("."):
        cur = cur[p]
    return cur


def chat_tolerant(text, maxtok):
    """Sealed chat() semantics, but a non-2xx response becomes a recorded refusal."""
    body = json.dumps({"model": L.MODEL, "max_tokens": maxtok, "temperature": 0.0,
                       "messages": [{"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            d = json.loads(r.read())
        u = d.get("usage", {})
        return {"ok": True, "completion": u.get("completion_tokens") or 0,
                "prompt": u.get("prompt_tokens") or 0}
    except urllib.error.HTTPError as e:
        raw = ""
        try: raw = e.read().decode()[:400]
        except Exception: pass
        return {"ok": False, "http": e.code, "body": raw}
    except Exception as e:
        return {"ok": False, "http": None, "body": f"{type(e).__name__}: {e}"}


def kv_fresh_prompt(width, i, lines):
    # same generator shape as the sealed stage, but a seed namespace that no earlier run touched
    return L.kv_prompt(SEED_NAMESPACE + width * 100 + i, lines)


def serve_pins():
    p = subprocess.run(["pgrep", "-f", "-fl", "server.server"], capture_output=True, text=True)
    lines = [l for l in p.stdout.splitlines() if "--" in l]
    pins = {}
    for l in lines:
        toks = l.split()
        i = 0
        while i < len(toks):
            t = toks[i]
            if not t.startswith("--"):
                i += 1; continue
            if "=" in t:
                k, v = t.lstrip("-").split("=", 1)
                pins[k] = v; i += 1
            elif i + 1 < len(toks) and not toks[i + 1].startswith("--"):
                # start.sh passes some flags space-separated (e.g. --queue-size 64)
                pins[t.lstrip("-")] = toks[i + 1]; i += 2
            else:
                pins[t.lstrip("-")] = True; i += 1
    return {"raw_present": bool(lines), "pins": pins,
            "queue_size": int(pins.get("queue-size", 32)) if str(pins.get("queue-size", 32)).isdigit() else 32,
            "queue_size_explicit": "queue-size" in pins}


def host_mem():
    out = subprocess.run("memory_pressure 2>/dev/null | grep -o 'System capacity: *[0-9]*' | grep -o '[0-9]*'",
                         shell=True, capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def kv_round(w, lines, out):
    before = L.status()
    peak, stop = {}, __import__("threading").Event()

    def sampler():
        while not stop.is_set():
            s = L.status()
            for name, fn in L.GAUGES:
                peak[name] = max(peak.get(name, -1), fn(s))
            for name, fn in (("memory_governor.headroom_bytes",
                              lambda s: s["memory_governor"]["headroom_bytes"]),
                             ("admission.held_behind_refusal",
                              lambda s: s["admission"].get("held_behind_refusal", 0)),
                             ("disk.kv_demotions_refused",
                              lambda s: s["disk"]["kv_demotions_refused"]),
                             ("metrics.capacity_failures",
                              lambda s: s["metrics"]["capacity_failures"])):
                peak[name] = max(peak.get(name, -1), fn(s))
            time.sleep(0.5)

    th = __import__("threading").Thread(target=sampler, daemon=True); th.start()
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=w) as ex:
        res = list(ex.map(lambda i: chat_tolerant(kv_fresh_prompt(w, i, lines), 8), range(w)))
    wall = time.time() - t0
    stop.set(); th.join(timeout=3)
    after = L.status()
    deltas = {name: fn(after) - fn(before) for name, fn in L.COUNTERS}
    deltas["disk.kv_demotions_refused"] = (after["disk"]["kv_demotions_refused"]
                                           - before["disk"]["kv_demotions_refused"])
    deltas["metrics.capacity_failures"] = (after["metrics"]["capacity_failures"]
                                           - before["metrics"]["capacity_failures"])
    ok = [r for r in res if r["ok"]]
    refusals = [r for r in res if not r["ok"]]
    ptok = sum(r["prompt"] for r in ok)
    prefill_rows = deltas["scheduler.prefill_rows"]
    rec = {"method": "kv_pressure", "variant": "fresh-seed-queue64", "width": w, "lines": lines,
           "wall_s": round(wall, 1), "requests_ok": len(ok), "requests_refused": len(refusals),
           "refusal_examples": refusals[:3], "prompt_tokens_each": [r["prompt"] for r in ok],
           "prompt_tokens_total": ptok,
           "prefill_rows_delta": prefill_rows,
           "cache_served": bool(ok) and ptok > 0 and prefill_rows < 0.5 * ptok,
           "prefill_tok_s": round(ptok / wall, 1) if wall > 0 and not refusals else None,
           "peaks": peak, "counter_deltas": deltas, "host_memory_capacity_pct": host_mem()}
    with open(out, "a") as f: f.write(json.dumps(rec) + "\n")
    budget = after["memory_plan"]["budget"]["kv_capacity_tokens"]
    print(f"[kv] w{w}: {ptok} tok ({round(ptok/budget,2)}x budget) in {rec['wall_s']}s | "
          f"ok={len(ok)} refused={len(refusals)} prefill_rows+{prefill_rows} "
          f"susp_peak={peak.get('admission.suspended')} waitmem_peak={peak.get('admission.waiting_memory')} "
          f"pages_act={peak.get('kv.pages_active')} spill+{deltas['kv_spill.spill_moves']} "
          f"demote+{deltas['disk.kv_demotions']} demote_refused+{deltas['disk.kv_demotions_refused']}"
          + ("  ** CACHE-SERVED, not pressure **" if rec["cache_served"] else ""), flush=True)
    return rec


def trip_reason(rec):
    if rec["requests_refused"]:
        ex = rec["refusal_examples"][0] if rec["refusal_examples"] else {}
        return f"client refused {rec['requests_refused']}/{rec['width']} (HTTP {ex.get('http')} {ex.get('body','')[:120]})"
    if rec["peaks"].get("admission.suspended", 0) > 0: return "admission.suspended > 0"
    if rec["counter_deltas"]["cache.resource_suspensions"] + rec["counter_deltas"]["cache.priority_suspensions"] > 0:
        return "lifetime suspension counter delta"
    if rec["counter_deltas"]["disk.kv_demotions_refused"] > 0: return "kv_demotions_refused delta"
    if rec["counter_deltas"]["metrics.capacity_failures"] > 0: return "capacity_failures delta"
    return None


def main():
    ap = argparse.ArgumentParser(description="2026-11-19b queueing-regime KV run")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "splash-1.7.0-2026-11-19b",
                    "ladder_kv.jsonl"))
    ap.add_argument("--widths", default=",".join(str(w) for w in DEFAULT_WIDTHS),
                    help="comma list of KV widths (default 12,33,36,40,44,48)")
    ap.add_argument("--skip-ladder", action="store_true")
    args = ap.parse_args()

    L.MODEL = L.model_id()
    widths = [int(x) for x in args.widths.split(",") if x.strip()]
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    gate_out = out.replace("ladder_kv.jsonl", "warmth_gate.jsonl")

    pins = serve_pins()
    top = max(widths)
    if top >= pins["queue_size"]:
        sys.exit(f"refusing to run: top width {top} >= queue-size {pins['queue_size']} "
                 f"(explicit flag present: {pins['queue_size_explicit']}). Raise QUEUE_SIZE at "
                 f"launch or lower --widths, otherwise a refusal measures our own saturation.")
    s0 = L.status()
    cfg = {"run": "splash-1.7.0-2026-11-19b", "model": L.MODEL, "supervisor": pins,
           "kv_widths": widths, "seed_namespace": SEED_NAMESPACE,
           "kv_target_tokens": KV_TARGET_TOKENS,
           "sealed_ladder_widths": SEAL_LADDER_WIDTHS,
           "status_kv_budget_tokens": q(s0, "memory_plan.budget.kv_capacity_tokens"),
           "maximum_batch_width": q(s0, "memory_plan.budget.maximum_batch_width"),
           "lifetime_at_start": {"resource_suspensions": s0["cache"]["resource_suspensions"],
                                 "priority_suspensions": s0["cache"]["priority_suspensions"],
                                 "capacity_failures": s0["metrics"]["capacity_failures"],
                                 "kv_demotions_refused": s0["disk"]["kv_demotions_refused"],
                                 "spill_moves": s0["kv_spill"]["spill_moves"]},
           "notes": "queue-size 64 stack move; refusals recorded not raised; prompts in a fresh "
                    "seed namespace and each round validated against cache-served prefill"}
    with open(out.replace("ladder_kv.jsonl", "engine_config.json"), "w") as f:
        json.dump(cfg, f, indent=1)
    print(f"[stack] queue-size={pins['queue_size']} (explicit={pins['queue_size_explicit']}) "
          f"kv_budget={cfg['status_kv_budget_tokens']} max_batch_width={cfg['maximum_batch_width']} "
          f"lifetime_at_start={cfg['lifetime_at_start']}", flush=True)

    # stage 0: warmth gate on the LADDER's own prompt, so the baseline it certifies is comparable
    dec = []
    for i in range(3):
        L.wait_idle()
        t0 = time.time()
        c, _ = L.chat(L.LADDER_PROMPT, 512)
        rate = round(c / (time.time() - t0), 1) if c else None
        dec.append(rate)
        with open(gate_out, "a") as f:
            json.dump({"method": "warmth_gate", "kind": "decode_w1_ladder_prompt", "pass": i + 1,
                       "completion_tokens": c, "tok_s": rate}, f); f.write("\n")
        print(f"[gate] ladder-prompt w1 pass {i+1}: {rate} tok/s", flush=True)
        time.sleep(4)
    d = [x for x in dec if x]
    ratio = round(max(d) / min(d), 3) if len(d) > 1 else 1.0
    gate = "pass" if ratio <= 1.10 else ("soft" if ratio <= 1.20 else "cold")
    print(f"[gate] spread {ratio} -> {gate} (11-19 ladder w1 median was 294.4)", flush=True)
    with open(gate_out, "a") as f:
        json.dump({"method": "warmth_gate", "kind": "summary", "decode_tok_s": dec,
                   "spread_ratio": ratio, "gate": gate,
                   "reference_11_19_w1": 294.4, "reference_11_18_w1": [260.6, 307.3]}, f)

    # stage 1: sealed ladder, to show queue-size did not perturb the throughput curve
    if not args.skip_ladder:
        L.wait_idle(); time.sleep(5)
        ladder = L.run_ladder(out, False)
    else:
        ladder = None

    # stage 2: KV in the queueing regime
    L.wait_idle(); time.sleep(5)
    _, cal_tokens = L.chat(L.kv_prompt(0, 300), 8)
    lines = max(1, int(300 * KV_TARGET_TOKENS / cal_tokens))
    print(f"[kv] calib: 300 lines = {cal_tokens} prompt tokens -> using {lines} lines/request", flush=True)
    rounds, trip = [], None
    for w in widths:
        rec = kv_round(w, lines, out)
        rounds.append(rec)
        why = trip_reason(rec)
        if why:
            trip = {"width": w, "why": why, "total_tokens": rec["prompt_tokens_total"]}
            print(f"[kv] TRIP at w{w}: {why}", flush=True)
            break
        time.sleep(10)
    s = L.status()
    fresh = [r for r in rounds if not r["cache_served"]]
    kv = {"rounds": len(rounds), "widths_run": [r["width"] for r in rounds],
          "cache_served_rounds": [r["width"] for r in rounds if r["cache_served"]],
          "max_total_tokens": max((r["prompt_tokens_total"] for r in fresh), default=0),
          "prefill_tok_s_by_width": {str(r["width"]): r["prefill_tok_s"] for r in fresh},
          "trip": trip,
          "resident_kv_budget_tokens": q(s, "memory_plan.budget.kv_capacity_tokens"),
          "lifetime_final": {"resource_suspensions": s["cache"]["resource_suspensions"],
                             "priority_suspensions": s["cache"]["priority_suspensions"],
                             "capacity_failures": s["metrics"]["capacity_failures"],
                             "kv_demotions_refused": s["disk"]["kv_demotions_refused"],
                             "spill_moves": s["kv_spill"]["spill_moves"]}}
    print(json.dumps({"SUMMARY": {"run": "splash-1.7.0-2026-11-19b", "model": L.MODEL,
                                  "queue_size": pins["queue_size"],
                                  "warmth_gate": {"decode_tok_s": dec, "spread_ratio": ratio,
                                                  "gate": gate},
                                  "width_ladder": ladder, "kv_pressure": kv}}))


if __name__ == "__main__":
    main()
