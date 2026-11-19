#!/usr/bin/env python3
"""Splash bench — extension run 2026-11-19: bracket the KV trip point above w12.

SUPERSEDED by kv_bracket_2026-11-19b.py, kept as the instrument that produced the records this
conclusion rests on. Three flaws it exposed are fixed there: prompts reused across runs come back
from the persistent prefix cache (its w2/w12 controls cost 0.4 s and 1.5 s), refusals raise and kill
the run (it died on HTTP 503 at w40, losing its SUMMARY), and its warmth gate used a prompt other
than the ladder's, so it certified nothing. Its 503 turned out to be the --queue-size default of 32,
not KV pressure - see results/splash-1.7.0-2026-11-19-ext/ and the 19b docstring.

Why: the 2026-11-18 ladder+KV run stopped at the standing driver's top KV width
(w12 = 612,180 prompt tokens = 3.93x the 155,648-token resident KV budget) with
admission.suspended = 0 and the LIFETIME suspension counters unmoved. So "no trip"
is an censored observation, not a ceiling: the driver hit its own width limit before
the engine hit its memory limit. This run pushes KV widths past that limit to find
the first round that actually trips admission.

Engine is NOT restarted. Stack deliberately stays on the 2026-11-18 args, including
--thinking-token-budget=16384 (the host start.sh raised it to 32768 on 2026-11-19 for
interactive use; this engine predates that and keeps the sealed series intact — and
neither stage can exercise the thinking cap anyway: ladder completions are pinned at
512 tokens, KV completions at 8, so the measurement is prompt-side KV).

Three stages, reusing the sealed primitives in ladder_kv.py rather than forking them:

  Stage 0 — WARMTH GATE (new, and the reason this run can be compared round-to-round).
    11-18's w1 median spread was 260.6 vs 307.3 tok/s (18%) across its two rounds,
    which is what made the whole curve's x1.4 shift hard to attribute. So: measure
    single-stream decode three times and TTFT cold-vs-warm-prefix twice BEFORE the
    ladder, and record whether the decode estimates have converged (gate ratio
    <= 1.10 pass / <= 1.20 soft / else cold, disclosed not blocked). The w1 baseline
    is only as trustworthy as the engine's state under it.

  Stage 1 — width ladder, EXACTLY the sealed widths (1,2,3,4,6,8,12,16,24,32),
    2 rounds, same stop rule. Same widths on purpose: the curve is the instance-state
    reference the KV stage is read against.

  Stage 2 — KV pressure at the sealed per-request calibration (lines recomputed the
    same way, ~51k tokens/request in practice), with two stitch controls (w2 and w12,
    which must land near 93,530 / 612,180 tokens and no trip) and then the extension
    widths 16, 20, 24, 28, 32, 40, 48, 64, stopping at the first real trip.

Run:  python3 ladder_kv_ext_2026-11-19.py --out results/splash-1.7.0-2026-11-19-ext/ladder_kv.jsonl
      python3 ladder_kv_ext_2026-11-19.py --smoke   # harness-only, not for baselining
"""
import argparse, json, os, subprocess, sys, time, urllib.request
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ladder_kv as L  # sealed primitives: chat/status/wait_idle/ladder_width/kv_round

SEAL = {"widths": (1, 2, 3, 4, 6, 8, 12, 16, 24, 32), "kv_widths": (2, 4, 6, 8, 10, 12),
        "kv_target_tokens": 20000}
EXT_KV_WIDTHS = (16, 20, 24, 28, 32, 40, 48, 64)
P_DECODE = ("Write a 300-token technical paragraph about color-management "
            "transform chains. Do not number it.")
P_TTFT = "Numbers 1-400, one per line, no commentary." * 3


def supervisor_args():
    p = subprocess.run(["pgrep", "-f", "-fl", "server.server"], capture_output=True, text=True)
    lines = [l for l in p.stdout.splitlines() if "--" in l]
    return {"raw": lines,
            "pins": {t.split("=")[0]: t.split("=", 1)[1] for l in lines for t in l.split()
                     if t.startswith("--") and "=" in t and
                     any(k in t for k in ("thinking", "effort", "max-memory", "max-context",
                                          "cache-disk", "expert-memory"))},
            "flags": [t for l in lines for t in l.split()
                      if t.startswith("--") and "=" not in t and
                      t in ("--persistent-cache", "--verify-rows")]}


def host_state():
    def sh(cmd):
        return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
    return {"uptime": sh("uptime"), "memory_pressure_pct": sh(
        "memory_pressure 2>/dev/null | grep -o 'System capacity: *[0-9]*' | grep -o '[0-9]*'"),
        "thermal": sh("pmset -g therm 2>/dev/null | tr -s ' ' | head -4 | tail -2")}


def main():
    ap = argparse.ArgumentParser(description="2026-11-19 KV trip-point extension run")
    ap.add_argument("--out", default=os.path.join(HERE, "results",
                    "splash-1.7.0-2026-11-19-ext", "ladder_kv.jsonl"))
    ap.add_argument("--smoke", action="store_true", help="harness check only, not for baselining")
    args = ap.parse_args()

    L.MODEL = L.model_id()
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    gate_out = out.replace("ladder_kv.jsonl", "warmth_gate.jsonl")
    print(f"model: {L.MODEL}\nout:   {out}" + ("  (SMOKE - not for baselining)" if args.smoke else ""),
          flush=True)

    # ---- stack proof, before any load
    s0 = L.status()
    cfg = {"run": "splash-1.7.0-2026-11-19-ext", "model": L.MODEL,
           "supervisor": supervisor_args(), "host": host_state(),
           "status_kv_budget_tokens": s0["memory_plan"]["budget"]["kv_capacity_tokens"],
           "lifetime_at_start": {"resource_suspensions": s0["cache"]["resource_suspensions"],
                                 "priority_suspensions": s0["cache"]["priority_suspensions"],
                                 "capacity_failures": s0["metrics"]["capacity_failures"]},
           "sealed_stack_inherit": SEAL,
           "note": "engine not restarted; thinking budget stays at the sealed 16384 and is "
                   "structurally inert for both stages (max_tokens 512 ladder / 8 KV)"}
    with open(out.replace("ladder_kv.jsonl", "engine_config.json"), "w") as f:
        json.dump(cfg, f, indent=1)
    print(f"[stack] kv_budget={cfg['status_kv_budget_tokens']} tok  "
          f"lifetime_susp={cfg['lifetime_at_start']}  "
          f"pins={cfg['supervisor']['pins']}", flush=True)

    # ---- stage 0: warmth gate
    dec, ttft = [], []
    passes = 2 if args.smoke else 3
    for i in range(passes):
        L.wait_idle()
        wall, comps = None, None
        t0 = time.time()
        c, _ = L.chat(P_DECODE if not args.smoke else "Count 1 to 60, one per line.", 300)
        wall = time.time() - t0
        rate = round(c / wall, 1) if c else None
        dec.append(rate)
        rec = {"method": "warmth_gate", "kind": "decode_w1", "pass": i + 1,
               "completion_tokens": c, "wall_s": round(wall, 2), "tok_s": rate}
        with open(gate_out, "a") as f: f.write(json.dumps(rec) + "\n")
        print(f"[gate] decode w1 pass {i+1}: {rate} tok/s", flush=True)
        time.sleep(4)
    for i in range(2):
        L.wait_idle()
        t0 = time.time()
        c, ptok = L.chat(P_TTFT if not args.smoke else "Count 1 to 40, one per line.", 8)
        tt = round((time.time() - t0) * 1000)
        ttft.append(tt)
        rec = {"method": "warmth_gate", "kind": "ttft", "pass": i + 1,
               "note": "cold" if i == 0 else "warm-prefix", "prompt_tokens": ptok, "ttft_ms": tt}
        with open(gate_out, "a") as f: f.write(json.dumps(rec) + "\n")
        print(f"[gate] ttft pass {i+1} ({'cold' if i==0 else 'warm-prefix'}): {tt} ms", flush=True)
        time.sleep(3)
    d = [x for x in dec if x]
    ratio = round(max(d) / min(d), 3) if len(d) > 1 else 1.0
    gate = "pass" if ratio <= 1.10 else ("soft" if ratio <= 1.20 else "cold")
    print(f"[gate] decode spread ratio {ratio} -> {gate}", flush=True)
    with open(gate_out, "a") as f:
        json.dump({"method": "warmth_gate", "kind": "summary", "decode_tok_s": dec,
                   "spread_ratio": ratio, "gate": gate, "ttft_ms": ttft}, f)

    # ---- stage 1: sealed width ladder (reuse the primitive, same widths/stop rule)
    print("[stage break] waiting for engine idle before ladder", flush=True)
    L.wait_idle(); time.sleep(5)
    ladder = L.run_ladder(out, args.smoke)

    # ---- stage 2: KV, stitch controls then extension widths
    print("[stage break] waiting for engine idle before KV stage", flush=True)
    L.wait_idle(); time.sleep(5)
    widths = (2, 4) if args.smoke else (2, 12) + EXT_KV_WIDTHS
    target = 4000 if args.smoke else SEAL["kv_target_tokens"]
    L.wait_idle()
    _, cal_tokens = L.chat(L.kv_prompt(0, 300), 8)
    lines = max(1, int(300 * target / cal_tokens))
    print(f"[kv] calib: 300 lines = {cal_tokens} prompt tokens -> using {lines} lines/request",
          flush=True)
    rounds, trip = [], None
    for w in widths:
        rec, susp_delta = L.kv_round(w, lines, out, args.smoke)
        rounds.append(rec)
        budget = L.status()["memory_plan"]["budget"]["kv_capacity_tokens"]
        print(f"[kv] w{w}: {round(rec['prompt_tokens_total']/budget, 2)}x budget", flush=True)
        if rec["peaks"]["admission.suspended"] > 0 or susp_delta > 0:
            trip = {"width": w,
                    "why": "suspended gauge" if rec["peaks"]["admission.suspended"] > 0
                           else "lifetime counter delta",
                    "total_tokens": rec["prompt_tokens_total"],
                    "multiple_of_budget": round(rec["prompt_tokens_total"] / budget, 2)}
            print(f"[kv] TRIP at w{w}: {trip['why']} at {trip['total_tokens']} tok "
                  f"({trip['multiple_of_budget']}x budget)", flush=True)
            break
        time.sleep(10)
    L.wait_idle()
    s = L.status()
    kv = {"rounds": len(rounds), "widths_run": [r["width"] for r in rounds],
          "max_total_tokens": max(r["prompt_tokens_total"] for r in rounds),
          "trip": trip, "resident_kv_budget_tokens": s["memory_plan"]["budget"]["kv_capacity_tokens"],
          "lifetime_final": {"resource_suspensions": s["cache"]["resource_suspensions"],
                             "priority_suspensions": s["cache"]["priority_suspensions"],
                             "capacity_failures": s["metrics"]["capacity_failures"]}}
    print(json.dumps({"SUMMARY": {"run": "splash-1.7.0-2026-11-19-ext", "smoke": args.smoke,
                                  "model": L.MODEL, "warmth_gate": {"decode_tok_s": dec,
                                  "spread_ratio": ratio, "gate": gate, "ttft_ms": ttft},
                                  "width_ladder": ladder, "kv_pressure": kv}}))


if __name__ == "__main__":
    main()
