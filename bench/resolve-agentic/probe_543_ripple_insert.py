#!/usr/bin/env python3
"""Continuity probe for MCP 5.4.3 (anomalyco/davinci-resolve-mcp#389 fix):
spawn a fresh 5.4.3 server over stdio, JSON-RPC by hand, dry-run ripple_insert
ambiguity refusal + absolute-mode plan on the 23e fixture (start-offset 108000)."""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path.home() / "Library/Application Support/davinci-resolve-mcp"
PY = ROOT / "venv/bin/python"

p = subprocess.Popen([str(PY), str(ROOT / "src/server.py")],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, text=True)

def send(obj):
    p.stdin.write(json.dumps(obj) + "\n"); p.stdin.flush()

def recv():
    while True:
        line = p.stdout.readline()
        if not line: raise SystemExit("server closed")
        try: msg = json.loads(line)
        except Exception: continue
        if "id" in msg: return msg

def text(msg):
    c = msg.get("result",{}).get("content",[])
    return c[0].get("text","") if c else json.dumps(msg)

send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
    "protocolVersion":"2024-11-05","capabilities":{},
    "clientInfo":{"name":"continuity-probe","version":"1"}}})
init = recv()
send({"jsonrpc":"2.0","method":"notifications/initialized","params":{}})

def call(tool, args):
    send({"jsonrpc":"2.0","id":2,"method":"tools/call",
          "params":{"name":tool,"arguments":{"action":args.get("action"),
                                              "params":{k:v for k,v in args.items() if k!="action"}}}})
    return recv()

# STEP 0: timeline start (probe reads, harmless)
t = call("timeline", {"action":"get_structure","project_name":"_mcp_AGBench-2026-11-25e",
                      "timeline_name":"_mcp_AGBench-2026-11-25e_T1"})
# STEP 0: media-pool id comes from the wave GT file (media_pool_item_id of <source-clip>)
gt = json.loads(pathlib.Path("ground_truth-_mcp_AGBench-2026-11-25e.json").read_text())
import re
m = re.search(r'"media_pool_item_id":\s*"([0-9a-f-]{36})"', json.dumps(gt))
clip_id = m.group(1)
print("== clip used:", clip_id)

# STEP 1: ambiguous record_frame, dry-run
a = call("timeline", {"action":"ripple_insert","project_name":"_mcp_AGBench-2026-11-25e",
                      "timeline_name":"_mcp_AGBench-2026-11-25e_T1",
                      "clip_infos":[{"clip_id":clip_id,"start_frame":0,"end_frame":100}],
                      "record_frame":108100,"dry_run":True})
# STEP 2: explicit absolute mode, dry-run
b = call("timeline", {"action":"ripple_insert","project_name":"_mcp_AGBench-2026-11-25e",
                      "timeline_name":"_mcp_AGBench-2026-11-25e_T1",
                      "clip_infos":[{"clip_id":clip_id,"start_frame":0,"end_frame":100}],
                      "record_frame":108100,"record_frame_mode":"absolute","dry_run":True})
p.terminate()

def text(msg):
    c = msg.get("result",{}).get("content",[])
    return c[0].get("text","") if c else json.dumps(msg)

print("== INIT ok:", bool(init.get("result")))
print("== STEP1 (ambiguous, dry-run):"); print(text(a)[:700])
print("== STEP2 (absolute, dry-run):");  print(text(b)[:700])
