#!/usr/bin/env python3
"""Close the probe_timeline_structure regression flag (leaderboard flag, 2026-11-06e).

Question on trial: the published `probe` column went 7 -> 11 -> 11 -> 18 -> 20 ms
(4.18.5 / 4.19.0 / 4.19.2 / 4.19.3 / 5.1.0) and came back 13 ms on 5.2.7. Was the
4.19.3 step (11 -> 18) a real server-side regression, or host state / run-to-run
spread? Each historical cell is a single median, so spread cannot be separated
from a step. This sweep measures the same thing under one host state, on the SAME
timelines, with three MCP builds side by side (4.19.3 / 5.1.0 / 5.2.7), n=11 per
cell, using the server's own envelope `duration_ms` (the channel every published
op column used) plus client-side round-trip as a cross-check.

Method:
  - Timelines are pre-built in scratch project PF_PROJECT (untimed, by the operator);
    the driver only times probes. Item counts are read from probe output itself,
    so the curve is ms-vs-actual-items regardless of how the timelines were made.
  - One server subprocess per build, sequential (no contention), spawned over
    stdio exactly like the sealed trial servers. Old builds run from isolated
    extracted npm tarballs; the live install is never touched.
  - Context variants (footnote 4 question re-measured on current builds):
      A = same-context  (current timeline == target; probe pinned by name)
      B = pinned-elsewhere (current is a different timeline)
      C = filtered      (track_types=["video"])
  - Cell order alternates ascending/descending item counts; samples within a cell
    are back-to-back; 3 warm-up probes discarded per build.
  - Host idle% sampled before each build pass; a pass above the threshold is flagged.

Teardown is NOT done here: the operator deletes the scratch project afterwards.

Usage: python3 -I probe_build_sweep.py [--builds 4.19.3,5.1.0,5.2.7] [--n 11]
Writes: results/probe-flag-2026-11-13/sweep.jsonl (+ summary.json)
"""
import argparse, itertools, json, os, pathlib, random, statistics, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "probe-flag-2026-11-13"
BUILDS_DIR = OUT / "builds"                       # extracted npm tarballs (gitignored)
LIVE = pathlib.Path.home() / "Library/Application Support/davinci-resolve-mcp"
PF_PROJECT = "_mcp_ProbeFlag-2026-11-13"
TIMELINES = ["pf_n1", "pf_n2", "pf_n4", "pf_n8", "pf_n16", "pf_base"]
CURRENT_ANCHOR = "pf_anchor"                      # for the pinned-elsewhere variant
PROTO = "2024-11-05"

def mcp_env():
    """Env blocks for the community server, read from ~/.claude.json at runtime."""
    cfg = json.load(open(pathlib.Path.home() / ".claude.json"))
    srv = cfg["mcpServers"]["davinci-resolve"]
    env = dict(os.environ)
    env.update(srv.get("env", {}))
    return env, srv

def build_root(version):
    if version == "5.2.7":
        return LIVE
    root = BUILDS_DIR / f"mcp-{version}"
    if not (root / "src" / "server.py").exists():
        sys.exit(f"missing build tree: {root} (npm pack davinci-resolve-mcp@{version} first)")
    return root

class Server:
    """Newline-delimited JSON-RPC over stdio, minimal MCP client."""
    def __init__(self, version, env):
        self.version = version
        self.root = build_root(version)
        py = (LIVE / "venv/bin/python") if (LIVE / "venv/bin/python").exists() else sys.executable
        self.p = subprocess.Popen([str(py), "src/server.py"], cwd=str(self.root), env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.nid = 0
        self._rpc("initialize", {"protocolVersion": PROTO, "capabilities": {},
                                 "clientInfo": {"name": "probe-flag-sweep", "version": "1"}})
        self._notify("notifications/initialized", {})

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n"); self.p.stdin.flush()

    def _notify(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _rpc(self, method, params):
        self.nid += 1; rid = self.nid
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"server died (v{self.version}) during {method}")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg["result"]

    def tool(self, name, action, params=None):
        """Compound-tool call: arguments = {action, params} (params is required nesting)."""
        return self.call(name, {"action": action, "params": params or {}})

    def call(self, tool, arguments):
        """Returns (envelope_dict_or_raw, client_ms)."""
        t0 = time.perf_counter()
        res = self._rpc("tools/call", {"name": tool, "arguments": arguments})
        cms = round((time.perf_counter() - t0) * 1000, 1)
        text = ""
        for c in res.get("content", []):
            if c.get("type") == "text":
                text += c["text"]
        try:
            env = json.loads(text)
        except json.JSONDecodeError:
            env = {"raw": text[:500]}
        return env, cms

    def close(self):
        try:
            self.p.stdin.close(); self.p.terminate(); self.p.wait(timeout=5)
        except Exception:
            self.p.kill()

def deep_get(obj, keys, _depth=0):
    """First int under any of `keys`, at any depth (envelope schemas vary by build)."""
    if _depth > 8:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if isinstance(obj.get(k), (int, float)) and not isinstance(obj.get(k), bool):
                return obj[k]
        for v in obj.values():
            r = deep_get(v, keys, _depth + 1)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = deep_get(v, keys, _depth + 1)
            if r is not None:
                return r
    return None

def envelope_ms(env):
    # measured envelope: {..., "_operation": {"duration_ms": N}}; older builds may differ
    op = env.get("_operation") if isinstance(env, dict) else None
    if isinstance(op, dict) and isinstance(op.get("duration_ms"), (int, float)):
        return op["duration_ms"]
    return deep_get(env, ("duration_ms", "_duration_ms", "elapsed_ms"))

def item_count(env):
    if isinstance(env, dict):
        for k in ("item_count", "total_items"):
            if isinstance(env.get(k), int):
                return env[k]
    return deep_get(env, ("total_items",))

def find_index(resp, name, _depth=0):
    """Walk an unknown-schema response; return the 1-based index of timeline `name`."""
    if _depth > 6:
        return None
    if isinstance(resp, dict):
        if resp.get("name") == name:
            for k in ("index", "timeline_index", "position"):
                if isinstance(resp.get(k), int):
                    return resp[k]
            return None
        for v in resp.values():
            r = find_index(v, name, _depth + 1)
            if r is not None:
                return r
    elif isinstance(resp, list):
        for i, v in enumerate(resp, 1):
            if isinstance(v, dict) and v.get("name") == name:
                for k in ("index", "timeline_index", "position"):
                    if isinstance(v.get(k), int):
                        return v[k]
                return i
            r = find_index(v, name, _depth + 1)
            if r is not None:
                return r
    return None

def host_idle():
    try:
        out = subprocess.run(["top", "-l", "1", "-n", "0"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("CPU usage"):
                return line.strip()
    except Exception:
        pass
    return "unknown"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--builds", default="4.19.3,5.1.0,5.2.7")
    ap.add_argument("--n", type=int, default=11)
    ap.add_argument("--variants", default="A,B,C")  # comma-separated
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    jl = open(OUT / "sweep.jsonl", "w")
    env, _ = mcp_env()

    def record(rec):
        jl.write(json.dumps(rec) + "\n"); jl.flush()

    order = list(TIMELINES)
    rnd = random.Random(20261113)
    for bi, build in enumerate(args.builds.split(",")):
        idle = host_idle()
        started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        print(f"[{time.strftime('%H:%M:%S')}] === build {build} (host: {idle}) ===", flush=True)
        try:
            srv = Server(build, env)
        except Exception as e:
            print(f"  FAILED to start {build}: {e}", flush=True)
            record({"kind": "build_error", "build": build, "error": str(e), "started": started})
            continue
        # warm-up
        for _ in range(3):
            srv.tool("timeline", "probe_timeline_structure", {"timeline_name": "pf_n4"})
        cells = []
        for tl in order:
            for var in [v for v in args.variants.split(",") if v]:
                if var == "B" and tl != "pf_base":
                    continue
                cells.append((tl, var))
        rnd.shuffle(cells)
        # one index map per build pass (set_current is 1-based within the current project)
        lst, _ = srv.tool("timeline", "list")
        record({"kind": "timeline_list", "build": build, "raw": lst if isinstance(lst, dict) else str(lst)[:800]})
        anchor_idx = find_index(lst, CURRENT_ANCHOR)
        idx_cache = {}
        for (tl, var) in cells:
            for i in range(args.n):
                if tl not in idx_cache:
                    idx_cache[tl] = find_index(lst, tl)
                idx = idx_cache[tl] if var != "B" else anchor_idx
                if idx is None:
                    print(f"  !! no index for {tl} (variant {var}); skip cell", flush=True)
                    break
                ctx, _ = srv.tool("timeline", "set_current", {"index": idx})
                cur = tl if var != "B" else CURRENT_ANCHOR
                if var != "B" and not (isinstance(ctx, dict) and find_index(ctx, tl) is not None):
                    pass  # set_current response schema varies; probe's pinned echo is the real check
                p2 = {"timeline_name": tl}
                if var == "C":
                    p2["track_types"] = ["video"]
                if var == "D":
                    p2["include_clip_properties"] = True
                env_, cms = srv.tool("timeline", "probe_timeline_structure", p2)
                dms = envelope_ms(env_)
                ok = isinstance(env_, dict) and "error" not in env_ and env_.get("success", True)
                record({"kind": "sample", "build": build, "timeline": tl, "variant": var,
                        "sample": i, "duration_ms": dms, "client_ms": cms,
                        "items": item_count(env_) if var != "C" else None,
                        "current": cur, "success": ok, "host_idle": idle})
                if not ok:
                    print(f"  !! {build} {tl}/{var} #{i}: {str(env_)[:200]}", flush=True)
                if i == 0 and (tl, var) == cells[0]:
                    record({"kind": "probe_raw", "build": build, "timeline": tl,
                            "keys": list(env_.keys()) if isinstance(env_, dict) else str(type(env_)),
                            "items": item_count(env_)})
        srv.close()
        # per-build summary
        recs = [json.loads(l) for l in open(OUT / "sweep.jsonl")]
        recs = [r for r in recs if r["kind"] == "sample" and r["build"] == build and r["duration_ms"] is not None]
        summ = {}
        for (tl, var), g in itertools.groupby(sorted(recs, key=lambda r: (r["timeline"], r["variant"])),
                                              key=lambda r: (r["timeline"], r["variant"])):
            g = [r["duration_ms"] for r in g]
            summ[f"{tl}/{var}"] = {"n": len(g), "median": statistics.median(g),
                                   "min": min(g), "max": max(g),
                                   "p90": sorted(g)[int(0.9 * (len(g) - 1))]}
        print(json.dumps({"build": build, "started": started, "idle": idle, "cells": summ}, indent=1), flush=True)
        record({"kind": "summary", "build": build, "started": started, "idle": idle, "cells": summ})
    jl.close()
    print("done ->", OUT / "sweep.jsonl")

if __name__ == "__main__":
    main()
