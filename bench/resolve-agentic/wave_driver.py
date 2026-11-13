#!/usr/bin/env python3
"""Resolve agentic benchmark wave driver — clean, standalone method (2026-11-13).

Two-agent waves as published: 6 tasks x 3 trials = 18 fresh sessions, dispatched in
concurrent pairs (9 pairs). Each trial is a `claude -p` subprocess with the seal:
  - strict MCP config (NO inheritance of the operator's servers), containing ONLY the
    three DaVinci Resolve MCP servers — so an agent can touch Resolve and nothing else.
  - every shell/file/web tool denied (no Bash/Read/Write/Edit/WebSearch/WebFetch/...).
  - fresh session, isolated per-trial cwd, no memory access possible (no file tools).

Credential hygiene: the MCP env blocks carry API keys, and this repo has a PUBLIC remote,
so the strict config is built at runtime from ~/.claude.json, written to a tempfile OUTSIDE
any git repo, and deleted on exit. Nothing credential-bearing is ever written into the tree.

Operator discipline (RUNBOOK): after launching, make NO Resolve call of any kind until
every agent has reported. Grading is done separately, from independent read-backs, after
the wave closes.
"""
import json, os, pathlib, subprocess, sys, tempfile, time, threading

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "bench" / "resolve-agentic" / "results" / "2026-11-13-wave"
SESS = OUT / "sessions"
TL_BASE = "_mcp_AGBench-2026-11-13"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
# Fixture-derived frame numbers (read from the untracked ground_truth at grade time; the
# briefs embed only the numbers, never the media path).
BASE_SRC, INS_SRC, INS_F, PROB_SRC, PROB_F = 5036, 25181, 101, 10072, 121
RENDER_ROOT = "/Volumes/YourVolume/resolve-audio-analysis/agbench_2026-11-13"

GROUND_RULES = (
    f"Work only through the DaVinci Resolve MCP tools (no shell, no file tools; do not use "
    f"Resolve's run_script/run_script_unsafe to touch the filesystem). Your scratch timelines are "
    f"named {TL_BASE}_T<n>r<k>; never modify or delete anything that already existed — including "
    f"_base, _T1, _BenchProbe, or other agents' timelines. Resolve's current timeline can be switched "
    f"by another process, so pin by timeline_id/timeline_name on every call where the action accepts "
    f"one, and re-check after any failure. Prefer a dry-run/plan call before any mutating call. When "
    f"you are done, report what you actually did, including dead ends and any call that returned "
    f"success but did nothing — honesty is graded against independent read-backs, so a wrong claim "
    f"costs more than an admitted failure."
)

def briefs():
    B = {}
    B["T1"] = (f"The project {TL_BASE} contains a timeline {TL_BASE}_T1. Report, as values only: "
               f"(1) the timeline's duration in frames, (2) the number of video items, (3) the number of "
               f"video tracks and the number of audio tracks, (4) the start and end record frames of the "
               f"first item. Read-only: change nothing.")
    def t2(k): return (f"The media pool holds one clip and the project has a reference timeline {TL_BASE}_base "
               f"whose geometry is: two items, source frames {BASE_SRC}-{BASE_SRC+221} and {BASE_SRC+221}-{BASE_SRC+442} "
               f"(end-exclusive; DF reads sit 1 low). Create a NEW timeline named {TL_BASE}_T2r{k} reproducing that "
               f"geometry (same clip, same source ranges, linked audio kept), then place a marker at timeline frame "
               f"60, colour Green, name bench-hit. Report the resulting marker read-back and the duration of the second item.")
    def t3(k): return (f"On a NEW timeline named {TL_BASE}_T3r{k} reproducing the _base geometry (two items 221 f each, "
               f"video with linked audio), insert the source range {INS_SRC}-{INS_SRC+INS_F} (end-exclusive, {INS_F} frames) "
               f"at the cut between the two items, shifting everything after it. Run the dry-run plan first, then execute. "
               f"Report the final item list (video AND audio) with start/end record frames.")
    def t4(k): return (f"On a NEW timeline named {TL_BASE}_T4r{k} reproducing the _base geometry (ONE video track and ONE "
               f"audio track — the base item pairs are linked): rename the first two audio tracks to VO-A and VO-B (create a "
               f"second audio track if needed), add a third audio track, lock the first audio track, then delete the first "
               f"VIDEO item. If a guardrail refuses, follow the remediation the server names. Report the track names/counts/"
               f"lock states you read back and whether the item is gone.")
    def t7(k): return (f"On a NEW timeline named {TL_BASE}_T7r{k}, build one item from source frames {PROB_SRC}-{PROB_SRC+PROB_F} "
               f"(end-exclusive, {PROB_F} frames, with its audio), then queue a QuickTime/H.264 render at 3840x1520 to a directory "
               f"you create under {RENDER_ROOT}/T7r{k}/ (creating that one directory with one mkdir -p is permitted; no other "
               f"shell/file use), start it, poll it, verify the rendered FILE (packet count, codecs, resolution) with Resolve MCP "
               f"tools, and empty the render queue. Report the render ms and your verification numbers.")
    def t8(k): return (f"On a NEW timeline named {TL_BASE}_T8r{k} with one item from the pool clip (any source range is fine), "
               f"attach a Fusion composition to that timeline item such that an independent read-back reports 1 comp for the item, "
               f"and name the nodes you can enumerate from that comp. Treat creation calls' success as unproven until your own "
               f"read-back says otherwise. Report the comp count read-back, its name if readable, and the node names you enumerated.")
    for k in (1, 2, 3):
        B[f"T2r{k}"] = t2(k); B[f"T3r{k}"] = t3(k); B[f"T4r{k}"] = t4(k)
        B[f"T7r{k}"] = t7(k); B[f"T8r{k}"] = t8(k)
    for k in (1, 2, 3):
        B[f"T1r{k}"] = B["T1"]
    return B

def strict_mcp_config():
    """Build a strict MCP config at runtime (credentials never persisted to the repo)."""
    cfg = json.load(open(pathlib.Path.home() / ".claude.json"))
    servers = cfg["mcpServers"]
    keep = {n: servers[n] for n in ("DaVinci Resolve", "davinci-resolve", "davinci-resolve-advanced")}
    fd, path = tempfile.mkstemp(prefix="agbench-mcp-", suffix=".json", dir=tempfile.gettempdir())
    with os.fdopen(fd, "w") as f:
        json.dump({"mcpServers": keep}, f)
    return path

ENV = {**os.environ,
       "ANTHROPIC_BASE_URL": "http://127.0.0.1:8000",
       "ANTHROPIC_AUTH_TOKEN": "splash",
       "ANTHROPIC_MODEL": MODEL, "ANTHROPIC_DEFAULT_OPUS_MODEL": MODEL,
       "ANTHROPIC_DEFAULT_SONNET_MODEL": MODEL, "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,
       "ANTHROPIC_SMALL_FAST_MODEL": MODEL,
       "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "262144", "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "262144"}

DISALLOW = "Bash,Read,Write,Edit,MultiEdit,Glob,Grep,NotebookEdit,WebSearch,WebFetch,Task,Skill,SlashCommand,design_suggest_slot,NotifyGarageChange,ComputerUse,ExitPlanMode,EnterPlanMode,PushNotification,TodoWrite,Agent,run_script,run_script_unsafe"

def run_trial(name, prompt, mcp_cfg):
    cwd = SESS / name
    cwd.mkdir(parents=True, exist_ok=True)
    full = prompt + "\n\n" + GROUND_RULES
    (cwd / "BRIEF_AS_SENT.md").write_text(full)   # archive the brief as sent
    cmd = ["claude", "-p", full, "--output-format", "json",
           "--strict-mcp-config", "--mcp-config", mcp_cfg,
           "--disallowedTools", DISALLOW]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=ENV, capture_output=True, text=True, timeout=2400)
    except Exception as e:
        return {"task": name, "error": str(e)[:200], "wall_s": round(time.time() - t0, 1)}
    rec = {"task": name, "ok": p.returncode == 0, "wall_s": round(time.time() - t0, 1)}
    try:
        d = json.loads(p.stdout)
        rec.update({"result": (d.get("result") or "")[:4000], "num_turns": d.get("num_turns"),
                    "duration_ms": d.get("duration_ms"), "cost_usd": d.get("total_cost_usd")})
    except Exception:
        rec["raw_stdout"] = p.stdout[:2000]; rec["raw_stderr"] = p.stderr[:500]
    (cwd / "result.json").write_text(json.dumps(rec, indent=1))
    return rec

def main():
    SESS.mkdir(parents=True, exist_ok=True)
    (OUT / "archived_briefs.md").write_text(json.dumps({"TL_BASE": TL_BASE,
        "frames": {"base_src": BASE_SRC, "insert_src": INS_SRC, "probe_src": PROB_SRC}}, indent=1))
    mcp_cfg = strict_mcp_config()
    B = briefs()
    # 9 concurrent pairs: (T1r1,T1r2)(T1r3,T2r1)(T2r2,T2r3)(T3r1,T3r2)(T3r3,T4r1)
    # (T4r2,T4r3)(T7r1,T7r2)(T7r3,T8r1)(T8r2,T8r3)
    pairs = [("T1r1","T1r2"),("T1r3","T2r1"),("T2r2","T2r3"),("T3r1","T3r2"),
             ("T3r3","T4r1"),("T4r2","T4r3"),("T7r1","T7r2"),("T7r3","T8r1"),("T8r2","T8r3")]
    results = []
    try:
        for a, b in pairs:
            print(f"[{time.strftime('%H:%M:%S')}] pair {a}+{b}", flush=True)
            out = {}
            def go(n):
                out[n] = run_trial(n, B[n], mcp_cfg)
            ta = threading.Thread(target=go, args=(a,)); tb = threading.Thread(target=go, args=(b,))
            ta.start(); tb.start(); ta.join(); tb.join()
            results.extend([out[a], out[b]])
            with open(OUT / "wave_summary.jsonl", "a") as f:
                for n in (a, b):
                    f.write(json.dumps({"task": n, "ok": out[n].get("ok"),
                            "turns": out[n].get("num_turns"), "wall_s": out[n].get("wall_s")}) + "\n")
            time.sleep(15)
    finally:
        os.unlink(mcp_cfg)
    (OUT / "wave_results.json").write_text(json.dumps(results, indent=1))
    print(f"WAVE DONE — {OUT}", flush=True)

if __name__ == "__main__":
    main()
