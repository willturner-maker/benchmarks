#!/usr/bin/env python3
"""Reasoning-effort cost probe, corrected.

Pass-2's version (run_pass2_determinism_agentic.py:effort_probe) was invalid: max_tokens=1200 was
fully consumed by reasoning tokens (reasoning_tokens=[1200,1200,1200] at every effort), finish
reason was `length`, and no ANSWER was ever emitted — so "low is 16% faster than xhigh" measured
three truncations, not three efforts. This version sizes the budget so the model can finish, and
records finish_reason + the actual ANSWER + reasoning length for every run.

Tenancy: run on the DAILY config, but this operator session shares the engine, so these are
marked tenanted; treat them as indicative, not clean-window.
"""
import json, pathlib, re, time, urllib.request

MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
BASE = "http://127.0.0.1:8000"
OUT = pathlib.Path.home() / "benchmarks/bench/splash-concurrency/results/clean-verifyrows-2026-11-17-pass2"
PROMPT = ("You are reviewing a DaVinci Resolve timeline. It has 4 items: "
          "A (0-120), B (120-300), C (300-420), D (420-600). A 30-frame insert is placed at "
          "frame 200, and a 12-frame dissolve is centred on the cut at frame 200. In your FINAL "
          "answer state: which items shift, by how many frames, and the resulting start frame of "
          "the last item. The final line of your reply must be exactly ANSWER=<number>, where the "
          "number is the start frame of the last item. Put nothing after that line.")

def chat(effort, max_tokens):
    body = {"model": MODEL, "max_tokens": max_tokens, "temperature": 0.0, "seed": 7,
            "messages": [{"role": "user", "content": PROMPT}]}
    if effort: body["reasoning_effort"] = effort
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}), timeout=900) as r:
        d = json.loads(r.read())
    wall = time.time() - t0
    u = d.get("usage") or {}
    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = msg.get("content") or ""
    ans = re.findall(r"ANSWER=(-?\d+)", content)
    return {"effort": effort, "max_tokens": max_tokens, "wall_s": round(wall, 2),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "prompt_tokens": u.get("prompt_tokens"),
            "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
            "finish": ch.get("finish_reason"), "answer": ans[-1] if ans else None,
            "content_head": content[:140].replace("\n", " | ")}

def main():
    rows = {}
    for eff in (None, "low", "medium", "high", "xhigh"):
        key = eff or "server-default"
        runs = []
        for _ in range(2):
            run = chat(eff, 3000)
            runs.append(run)
            print(f"  {key}: finish={run['finish']} reasoning={run['reasoning_tokens']} "
                  f"wall={run['wall_s']}s answer={run['answer']}", flush=True)
        med = round(sum(r["wall_s"] for r in runs) / len(runs), 2)   # n=2: mean of the pair
        rows[key] = {"median_wall_s": med,
                     "reasoning_tokens": [r["reasoning_tokens"] for r in runs],
                     "completion_tokens": [r["completion_tokens"] for r in runs],
                     "finish": [r["finish"] for r in runs],
                     "answers": [r["answer"] for r in runs], "runs": runs}
        print(f"{key}: median {med}s reasoning {rows[key]['reasoning_tokens']} answers {rows[key]['answers']}", flush=True)
    base = rows["xhigh"]["median_wall_s"]
    for k in rows:
        rows[k]["vs_xhigh_percent"] = round((rows[k]["median_wall_s"] - base) / base * 100, 1)
    rec = {"valid": all(r["finish"] == "stop" for k in rows for r in rows[k]["runs"]),
           "caveat": "operator session shared the engine during this probe (tenanted); "
                     "run 2026-11-17 10:5x on the daily config, verify-rows auto",
           "prompt": PROMPT, "rows": rows}
    (OUT / "reasoning-effort-cost-corrected.json").write_text(json.dumps(rec, indent=1))
    print("valid:", rec["valid"])

main()
