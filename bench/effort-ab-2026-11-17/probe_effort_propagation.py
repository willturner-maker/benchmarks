#!/usr/bin/env python3
"""Does effort actually propagate through the OpenCode harness? Two questions, one probe.

 Q1: what does OpenCode put in the chat body by itself (reasoning_effort present or absent)?
 Q2: does the proxy's injected `reasoning_effort` change engine behaviour in a way the event
     stream can SEE — reasoning tokens per step (low/medium stop thinking early; the xhigh
     default burns thousands)?

Design: three sealed one-step sessions ("Name one DaVinci Resolve fusion node, one word."):
  A: provider -> engine direct            (baseline: what OpenCode sends natively)
  B: provider -> proxy(passthrough)       (control: proxy changes nothing)
  C: provider -> proxy(inject medium)     (arm mechanism test)
Judge from the proxy audit (bodies) + the event stream reasoning tokens, never from replies.
"""
import json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
CTX = 262144
PROMPT = "Name one DaVinci Resolve Fusion node type. Answer in one word, no sentence."

def seal(cwd, base_url):
    cwd.mkdir(parents=True, exist_ok=True)
    cfg = {
        "$schema": "https://opencode.ai/config.json",
        "providers": {"splash": {
            "package": "aisdk:@ai-sdk/openai-compatible",
            "settings": {"baseURL": base_url, "apiKey": "none"},
            "models": {MODEL.split("/", 1)[1]: {"limit": {"context": CTX, "output": 16384}}}}},
        "model": f"splash/{MODEL}",
        "permissions": [{"action": "*", "resource": "*", "effect": "deny"}],
        "policies": [{"action": a, "resource": "*", "effect": "deny"} for a in
                     ("tool.use", "mcp.use", "skill.use", "websearch.use", "plugin.use")],
    }
    (cwd / "opencode.json").write_text(json.dumps(cfg, indent=1))
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str((cwd / "opencode.json").resolve())
    return env

def run(tag, base_url):
    cwd = HERE / "probe-sessions" / tag
    env = seal(cwd, base_url)
    t0 = time.time()
    p = subprocess.run(["opencode", "run", "--standalone", "--format", "json", PROMPT],
                       cwd=str(cwd), env=env, capture_output=True, text=True, timeout=240)
    (cwd / "events.json").write_text(p.stdout)
    reasoning = output = 0
    for l in p.stdout.splitlines():
        try: e = json.loads(l)
        except Exception: continue
        t = (e.get("part") or {}).get("tokens") if e.get("type") == "step_finish" else None
        if t: reasoning += t.get("reasoning", 0) or 0; output += t.get("output", 0) or 0
    print(f"{tag}: wall {time.time()-t0:.1f}s | harness reasoning_tokens={reasoning} output={output} "
          f"| rc={p.returncode}", flush=True)
    return reasoning

print("Q1/Q2 effort propagation probe")
a = run("A-direct", "http://127.0.0.1:8000/v1")
b = run("B-proxy-passthrough", "http://127.0.0.1:8010/v1")
c = run("C-proxy-medium", "http://127.0.0.1:8011/v1")   # 8011 = the injecting proxy (PROXY_EFFORT=medium)
audit = [json.loads(l) for l in open(os.environ.get("PROXY_LOG", HERE / "proxy-audit.jsonl"))] if \
        pathlib.Path(os.environ.get("PROXY_LOG", HERE / "proxy-audit.jsonl")).exists() else []
for r in audit:
    print("AUDIT", r.get("ts"), r.get("path"), "| effort_in_body:", r.get("effort_in_body"),
          "| injected:", r.get("effort_injected"), "| engine reasoning_tok:", r.get("reasoning_tokens"),
          "| completion:", r.get("completion_tokens"))
rec = {"runs": {"direct_reasoning": a, "proxy_passthrough_reasoning": b, "proxy_medium_reasoning": c},
       "audit_lines": audit,
       "conclusion_partial": "read the audit: if OpenCode sends no effort natively, the proxy "
                             "injection is the arm mechanism"}
(HERE / "effort-propagation-probe.json").write_text(json.dumps(rec, indent=1))
print("recorded:", HERE / "effort-propagation-probe.json")
