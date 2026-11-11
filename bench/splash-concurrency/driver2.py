#!/usr/bin/env python3
"""Splash agentic benchmark driver v2 — fixes run-1 harness flaws:
1) Bash allowed per task (run 1 put Bash in --disallowedTools, blocking curl);
2) --strict-mcp-config: no MCP server inheritance (run-1 agents fetched via Resolve MCP);
3) per-task isolated cwd (run-1 agents found S4's fixture from other tasks' dirs).
Condition otherwise unchanged: fresh session per trial, all model aliases = resident Qwen,
default permission mode, WebSearch/WebFetch disabled, 4 tasks x 3 runs, sequential."""
import json, os, subprocess, time, pathlib

DIR = "/tmp/splash-bench-2026-11-06/run2"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
ENV = {**os.environ,
       "ANTHROPIC_BASE_URL": "http://127.0.0.1:8000",
       "ANTHROPIC_AUTH_TOKEN": "splash",
       "ANTHROPIC_MODEL": MODEL,
       "ANTHROPIC_DEFAULT_OPUS_MODEL": MODEL,
       "ANTHROPIC_DEFAULT_SONNET_MODEL": MODEL,
       "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,
       "ANTHROPIC_SMALL_FAST_MODEL": MODEL,
       "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "262144",
       "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "262144"}

TASKS = {
 "S1": {"cwd": f"{DIR}/S1", "allowed": ["Bash(curl:*)"], "prompt":
        "Fetch http://127.0.0.1:8000/status exactly once (curl). Then report, one per line, EXACTLY these six lines: "
        "schema_version: <value> / model_name: <memory_plan.model.model_name> / max_context: <maximum_context_tokens> / "
        "active_sum: <admission.waiting + scheduler.queued + scheduler.decoding> / cache_hits: <cache.hits> / cold_misses: <cache.cold_misses>. "
        "Values only, no prose."},
 "S2": {"cwd": f"{DIR}/S2", "allowed": ["Bash(curl:*)"], "prompt":
        "Fetch http://127.0.0.1:8000/status exactly once (curl). Report three lines: kv_hit_tokens: <exact>, kv_disk_hit_tokens: <exact>, "
        "disk_share_percent: <kv_disk_hit_tokens / (kv_hit_tokens + kv_disk_hit_tokens) * 100 rounded to 2 decimal places>. Show no work, just the three lines."},
 "S3": {"cwd": f"{DIR}/S3", "allowed": ["Bash(curl:*)", "Write"], "prompt":
        "Fetch http://127.0.0.1:8000/status exactly once (curl). Write the file out.json in your working directory containing EXACTLY this JSON object (no other keys, valid JSON): "
        '{"schema_version": <value>, "memory_pressure": <value>, "admission": <the whole admission object>, '
        '"queued": <scheduler.queued>, "decoding": <scheduler.decoding>, "derived": <queued + decoding>}. '
        "After writing, reply DONE."},
 "S4": {"cwd": f"{DIR}/S4", "allowed": ["Read"], "prompt":
        "Read the file fixture_status.json in your working directory. Answer in exactly three numbered lines: "
        "1) the single most likely bottleneck; 2) the one field that most directly evidences it (full dotted path); "
        "3) one concrete action likely to relieve it. No other text."},
}

def run(k, n):
    t = TASKS[k]
    cmd = ["claude", "-p", t["prompt"], "--output-format", "json",
           "--strict-mcp-config",
           "--disallowedTools", "WebSearch,WebFetch",
           "--allowedTools", *t["allowed"]]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=t["cwd"], env=ENV, capture_output=True, text=True, timeout=420)
        d = json.loads(p.stdout)
    except Exception as e:
        return {"task": k, "run": n, "error": str(e)[:200], "wall_s": round(time.time() - t0, 1)}
    u = d.get("usage", {})
    return {"task": k, "run": n, "ok": p.returncode == 0,
            "result": (d.get("result") or "")[:1200],
            "num_turns": d.get("num_turns"), "duration_ms": d.get("duration_ms"),
            "duration_api_ms": d.get("duration_api_ms"),
            "in": u.get("input_tokens"), "cache_read": u.get("cache_read_input_tokens"),
            "cache_creation": u.get("cache_creation_input_tokens"),
            "out": u.get("output_tokens"), "thinking": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
            "cost_usd": d.get("total_cost_usd"), "wall_s": round(time.time() - t0, 1)}

if __name__ == "__main__":
    for t in TASKS.values(): pathlib.Path(t["cwd"]).mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"{DIR}/sessions").mkdir(exist_ok=True)
    for n in (1, 2, 3):
        for k in ("S1", "S2", "S3", "S4"):
            r = run(k, n)
            with open(f"{DIR}/sessions/summary.jsonl", "a") as f:
                f.write(json.dumps(r) + "\n")
            print(f"{k} r{n}: ok={r.get('ok')} turns={r.get('num_turns')} wall={r.get('wall_s')}s out_tok={r.get('out')}", flush=True)
            time.sleep(12)
