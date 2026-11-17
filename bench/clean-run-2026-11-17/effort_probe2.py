#!/usr/bin/env python3
"""Effort probe #2: the two arms that truncated at 3,000 tokens, re-run at 8,000.

effort_probe.py (budget 3000) showed the knob works — low finished at 1,771 reasoning tokens with
the correct ANSWER=450, medium at 2,320 — but server-default and high/xhigh hit `length` at the
3,000 cap, so their walls measure truncation, not effort. This run sizes the budget so every run
reaches `stop`; low/medium are taken from probe #1's stopped runs.
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

def chat(effort, max_tokens=8000):
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
    content = (ch.get("message") or {}).get("content") or ""
    ans = re.findall(r"ANSWER=(-?\d+)", content)
    return {"effort": effort, "wall_s": round(wall, 2),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "finish": ch.get("finish_reason"), "answer": ans[-1] if ans else None}

rows = {}
for eff in ("xhigh", None):
    key = eff or "server-default"
    runs = [chat(eff) for _ in range(2)]
    for r in runs: print(f"  {key}: finish={r['finish']} reasoning={r['reasoning_tokens']} wall={r['wall_s']}s answer={r['answer']}", flush=True)
    rows[key] = {"mean_wall_s": round(sum(r["wall_s"] for r in runs)/2, 2),
                 "reasoning_tokens": [r["reasoning_tokens"] for r in runs],
                 "finish": [r["finish"] for r in runs], "answers": [r["answer"] for r in runs],
                 "runs": runs}
    print(f"{key}: mean {rows[key]['mean_wall_s']}s reasoning {rows[key]['reasoning_tokens']} answers {rows[key]['answers']}", flush=True)
base = rows["xhigh"]["mean_wall_s"]
for k in rows: rows[k]["vs_xhigh_percent"] = round((rows[k]["mean_wall_s"]-base)/base*100, 1)
rec = {"valid": all(r["finish"] == "stop" for k in rows for r in rows[k]["runs"]),
       "budget": 8000,
       "caveat": "operator session shares the engine; tenanted probe, indicative not clean-window. "
                 "low/medium arms: 1,771 / 2,320 reasoning tokens to `stop` with ANSWER=450 (probe #1, budget 3000)",
       "rows": rows}
(OUT / "reasoning-effort-cost-corrected.json").write_text(json.dumps(rec, indent=1))
print("valid:", rec["valid"])
