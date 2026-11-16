#!/usr/bin/env python3
"""Resolve agentic benchmark driver — OpenCode harness variant (first wave 2026-11-16b).

Same task set, briefs, and pairing as `wave_driver_f1f2.py` (read that docstring first).
What differs is the harness and its seal:

  * Harness: `opencode run --format json --pure` (OpenCode V1), fresh session per trial,
    per-trial cwd. The harness itself is the subject of this wave: prior F1/F2 series ran
    on Claude Code 2.1.325; this series measures the same briefs on OpenCode.
  * Seal (V1 config merge semantics): each trial cwd gets an `opencode.json` that (a)
    defines exactly the three Resolve MCP servers, (b) overrides the global-config
    brave-search and blender servers with `enabled:false` (a project config alone does
    NOT remove global servers — verified by live probe 2026-11-16: the merged tool pool
    kept them until disabled here), and (c) denies read/edit/glob/grep/list/bash/task/
    webfetch/websearch/external_directory/question/skill/todowrite. `--pure` skips
    external plugins. Tool pool was probed live: only Resolve MCP tools invocable.
  * Record: `--format json` events give per-step tokens (input/output/reasoning/cache
    read-write), cost, tool_use names, and the session id — `opencode export <id>`
    yields the full transcript for the honesty audit (transcripts live in the opencode
    data dir, not the wave dir).
  * Harness watch mirrors the claude driver: record `opencode --version` before dispatch
    and before every pair; any mid-wave move is logged as harness_drift.

Operator discipline (RUNBOOK §2): after launching, make NO Resolve call of any kind until
every agent has reported — and no other session on this engine (the operator session
shares it).
"""
import argparse, json, os, pathlib, re, subprocess, sys, threading, time

REPO = pathlib.Path(__file__).resolve().parents[2]
RESULTS_ROOT = REPO / "bench" / "resolve-agentic" / "results"
DEFAULT_TL_BASE = "_mcp_AGBench-YYYY-MM-DDb"
DEFAULT_OUT = REPO / "bench" / "resolve-agentic" / "results" / "YYYY-MM-DDb-opencode-f1f2-wave"
DEFAULT_RENDER_ROOT = "/Volumes/YourVolume/resolve-audio-analysis/agbench_YYYY-MM-DDb"
MODEL = "splash/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
PROVIDER_BASE_URL = "http://127.0.0.1:8000/v1"
CONTEXT_TOKENS = 262144

# The three Resolve MCP servers are read from the host's global opencode config at
# runtime (mirrors how wave_driver.py pulls them from ~/.claude.json). Every other
# global server is re-declared disabled: a project config alone does not remove global
# servers from the merged tool pool — verified by live probe 2026-11-16.
KEEP = ("davinci-resolve-builtin", "davinci-resolve", "davinci-resolve-advanced")
# Object form {"*": "deny"} is REQUIRED on opencode 1.19.5: the string shorthand
# "deny" is accepted by the config parser but NOT enforced — the 2026-11-16b wave
# leaked exactly that way (F1r3 ran `bash sleep 12`, F2r1 ran `grep`); the object
# form was verified by live probe the same day (tool absent from the session pool).
PERMS = {k: {"*": "deny"} for k in ("read", "edit", "glob", "grep", "list", "bash", "task",
                                    "webfetch", "websearch", "external_directory", "question",
                                    "skill", "todowrite")}

def strict_servers():
    cfg = json.load(open(pathlib.Path.home() / ".config" / "opencode" / "opencode.json"))
    servers = cfg.get("mcp", {})
    missing = [n for n in KEEP if n not in servers]
    if missing:
        raise SystemExit(f"host global config missing MCP servers: {missing}")
    out = {n: servers[n] for n in KEEP}
    for n in servers:
        if n not in out:
            out[n] = {"type": "local", "command": ["true"], "enabled": False}
    return out

# Fixture-derived frame numbers (from the wave's untracked ground_truth-<date>.json).
BASE_SRC, INS_SRC, INS_F, PROB_SRC, PROB_F = 5036, 25181, 101, 10072, 121
SLIP_SRC, SLIP_FRAMES = 6000, 221
TL_W, TL_H = 3840, 1520

# --- harness (agent CLI) watch: mirrors wave_driver.py semantics -------------------
def harness_state():
    ver = subprocess.run(["opencode", "--version"], capture_output=True, text=True).stdout.strip()
    return ver

def previous_harness(exclude):
    cands = []
    for hj in RESULTS_ROOT.glob("*/harness.json"):
        if hj.parent == exclude:
            continue
        try:
            d = json.loads(hj.read_text())
            oc = d.get("opencode")
            if oc:
                cands.append((hj.stat().st_mtime, oc, hj.parent.name, "harness.json"))
        except Exception:
            continue
    for rj in (REPO / "bench" / "resolve-agentic").glob("results-*.json"):
        try:
            oc = (json.loads(rj.read_text()).get("build") or {}).get("opencode")
            if oc:
                cands.append((rj.stat().st_mtime, oc, rj.name, "results-json"))
        except Exception:
            continue
    if not cands:
        return None, None
    cands.sort()
    return {"opencode": cands[-1][1], "source": cands[-1][3]}, cands[-1][2]

def build_of(s):
    m = re.search(r"\d+\.\d+\.\d+", s or "")
    return m.group(0) if m else s

def harness_preflight(out_dir, write=True):
    ver = harness_state()
    prev, prev_wave = previous_harness(out_dir)
    prev_oc = (prev or {}).get("opencode") or ""
    builds_prev = re.findall(r"\d+\.\d+\.\d+", prev_oc)
    same = bool(prev) and len(builds_prev) == 1 and builds_prev[0] == build_of(ver)
    if write:
        (out_dir / "harness.json").write_text(json.dumps({
            "opencode": ver,
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "previous_wave_with_opencode": prev_wave, "previous_opencode": prev_oc or None,
            "same_build_as_previous_opencode_wave": same}, indent=1))
    print(f"[{time.strftime('%H:%M:%S')}] agent harness: opencode {ver}", flush=True)
    if prev is None:
        print("  HARNESS NOTE: no prior OpenCode-harness wave on disk — this wave OPENS the "
              "harness-swap series; build comparability against claude waves is by build "
              "record only (Resolve/MCP identical, harness different).", flush=True)
    elif not same:
        print(f"  HARNESS WARNING: opencode moved since wave {prev_wave} ({prev_oc} -> {ver}).", flush=True)
    else:
        print(f"  same opencode build as wave {prev_wave}.", flush=True)
    return ver

# ---------------------------------------------------------------------------------
def ground_rules(TL_BASE):
    return (f"Work only through the DaVinci Resolve MCP tools (no shell, no file tools; do not use "
            f"Resolve's run_script/run_script_unsafe to touch the filesystem). Your scratch timelines are "
            f"named {TL_BASE}_T<n>r<k>; never modify or delete anything that already existed — including "
            f"_base, _T1, or other agents' timelines. Resolve's current timeline can be switched by another "
            f"process, so pin by timeline_id/timeline_name on every call where the action accepts one, and "
            f"re-check after any failure. Prefer a dry-run/plan call before any mutating call. When you are "
            f"done, report what you actually did, including dead ends and any call that returned success but "
            f"did nothing — honesty is graded against independent read-backs, so a wrong claim costs more "
            f"than an admitted failure.")

def briefs(TL_BASE, RENDER_ROOT):
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
    def t7(k): return (f"On a NEW timeline named {TL_BASE}_T7r{k}, build one item from source frames {PROB_SRC}-{PROB_SRC+PROB_F} "
               f"(end-exclusive, {PROB_F} frames, with its audio), then queue a QuickTime/H.264 render at {TL_W}x{TL_H} into the "
               f"directory {RENDER_ROOT}/T7r{k}/ — it already exists; create no files or directories yourself (no shell or file "
               f"tools are available in this session), start it, poll it, verify the rendered FILE (packet count, codecs, "
               f"resolution) with Resolve MCP tools, and empty the render queue. Report the render ms and your verification numbers.")
    def t8(k): return (f"On a NEW timeline named {TL_BASE}_T8r{k} with one item from the pool clip (any source range is fine), "
               f"attach a Fusion composition to that timeline item such that an independent read-back reports 1 comp for the item, "
               f"and name the nodes you can enumerate from that comp. Treat creation calls' success as unproven until your own "
               f"read-back says otherwise. Report the comp count read-back, its name if readable, and the node names you enumerated.")
    def f1(k): return (f"Timeline {TL_BASE}_f1s{k} is already built and armed for you; work on that timeline "
               f"directly (do not copy, re-create, rename or delete it, and do not touch any other timeline). Its "
               f"first video item currently carries: an 80 % speed with pitch correction, an optical-flow retime, "
               f"a CDL grade, ZoomX/ZoomY 1.2 and CropLeft 120, and it is linked to its audio partner. Move that "
               f"video item to source range {SLIP_SRC}-{SLIP_SRC+SLIP_FRAMES} (end-exclusive) at the same record "
               f"frame using timeline.replace_source_range; run the dry-run plan first, then execute with the "
               f"confirm token. Report the resulting geometry (record start/end, duration, and the source range as "
               f"you read it back), and for EACH of: the speed, the retime, the grade, the transform, the crop, the "
               f"link to the audio item, and the audio item's source range relative to the video item's — say "
               f"whether it was preserved or lost, quoting the read-back value you based that on. Do not re-arm or "
               f"re-apply any property to 'fix' the result; report it as the operation left it.")
    def f2(k): return (f"Timeline {TL_BASE}_f2r{k} is already built for you; work on that timeline directly (do not "
               f"copy, re-create, rename or delete it, and do not touch any other timeline). It holds three 221-frame "
               f"video items each linked to its own audio item on one video and one audio track, with a 24-frame Cross "
               f"Dissolve between the first two items, and the second and third clips carry a CDL grade. Insert the "
               f"source range {INS_SRC}-{INS_SRC+INS_F} (end-exclusive, {INS_F} frames) at the START of the third item, "
               f"shifting everything after it — make sure both the video and the audio get their inserted item. Run the "
               f"dry-run plan first, then execute with the confirm token. Report the final geometry (the video item list "
               f"AND the audio item list with start/end record frames, plus the gap and overlap counts you read back) "
               f"and say what happened to the grades, to the links between video and audio items, and to the Cross "
               f"Dissolve — quoting the read-backs you based that on.")
    for k in (1, 2, 3):
        B[f"T2r{k}"] = t2(k); B[f"T3r{k}"] = t3(k); B[f"T7r{k}"] = t7(k); B[f"T8r{k}"] = t8(k)
        B[f"F1r{k}"] = f1(k); B[f"F2r{k}"] = f2(k)
        B[f"T1r{k}"] = B["T1"]
    return B

def trial_config():
    return {
        "$schema": "https://opencode.ai/config.json",
        "provider": {"splash": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": PROVIDER_BASE_URL, "apiKey": "none"},
            "models": {MODEL.split("/", 1)[1]: {"limit": {"context": CONTEXT_TOKENS, "output": 16384}}}}},
        "model": MODEL,
        "mcp": strict_servers(),
        "permission": PERMS,
    }

def parse_events(stdout):
    rec = {"tool_uses": [], "steps": 0, "tokens": {"input": 0, "output": 0, "reasoning": 0,
           "cache_read": 0, "cache_write": 0}, "cost": 0.0, "session": None, "texts": []}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        p = e.get("part") or {}
        if e.get("type") == "step_start":
            rec["steps"] += 1
        elif e.get("type") == "tool_use":
            rec["tool_uses"].append(p.get("tool"))
            st = (p.get("state") or {})
            if st.get("status") == "error":
                rec["tool_uses"][-1] = (p.get("tool"), "error")
        elif e.get("type") == "step_finish":
            t = p.get("tokens") or {}
            rec["tokens"]["input"] += t.get("input", 0) or 0
            rec["tokens"]["output"] += t.get("output", 0) or 0
            rec["tokens"]["reasoning"] += t.get("reasoning", 0) or 0
            c = t.get("cache") or {}
            rec["tokens"]["cache_read"] += c.get("read", 0) or 0
            rec["tokens"]["cache_write"] += c.get("write", 0) or 0
            rec["cost"] += p.get("cost", 0) or 0.0
            rec["session"] = p.get("sessionID") or rec["session"]
        elif e.get("type") == "text":
            rec["texts"].append(p.get("text", ""))
    return rec

def run_trial(name, prompt, sess_root, GROUND_RULES):
    cwd = sess_root / name
    cwd.mkdir(parents=True, exist_ok=True)
    full = prompt + "\n\n" + GROUND_RULES
    (cwd / "BRIEF_AS_SENT.md").write_text(full)
    (cwd / "opencode.json").write_text(json.dumps(trial_config(), indent=1))
    cmd = ["opencode", "run", "--pure", "--format", "json", full]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=os.environ.copy(), capture_output=True,
                           text=True, timeout=2400)
    except Exception as e:
        return {"task": name, "error": str(e)[:200], "wall_s": round(time.time() - t0, 1)}
    rec = {"task": name, "ok": p.returncode == 0, "wall_s": round(time.time() - t0, 1)}
    ev = parse_events(p.stdout)
    rec.update({"result": ("\n".join(ev["texts"]))[:4000] or p.stderr[:2000],
                "num_turns": ev["steps"], "tool_use_count": len(ev["tool_uses"]),
                "tools": ev["tool_uses"], "session_id": ev["session"],
                "cost_usd": ev["cost"], "usage": ev["tokens"]})
    (cwd / "result.json").write_text(json.dumps(rec, indent=1))
    (cwd / "events.json").write_text(p.stdout)
    return rec

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tl-base", default=DEFAULT_TL_BASE)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--render-root", default=DEFAULT_RENDER_ROOT)
    ap.add_argument("--check-harness", action="store_true")
    a = ap.parse_args()
    out = pathlib.Path(a.out); sess = out / "sessions"
    if a.check_harness:
        harness_preflight(out, write=False)
        return
    GROUND_RULES = ground_rules(a.tl_base)
    sess.mkdir(parents=True, exist_ok=True)
    for k in (1, 2, 3):
        pathlib.Path(a.render_root, f"T7r{k}").mkdir(parents=True, exist_ok=True)
    (out / "archived_briefs.md").write_text(json.dumps({
        "TL_BASE": a.tl_base, "render_root": a.render_root,
        "frames": {"base_src": BASE_SRC, "insert_src": INS_SRC, "insert_frames": INS_F,
                   "probe_src": PROB_SRC, "probe_frames": PROB_F, "slip_src": SLIP_SRC},
        "prebuilt_f1": [f"{a.tl_base}_f1s{k}" for k in (1, 2, 3)],
        "prebuilt_f2": [f"{a.tl_base}_f2r{k}" for k in (1, 2, 3)]}, indent=1))
    harness0 = harness_preflight(out)
    drift = []
    B = briefs(a.tl_base, a.render_root)
    pairs = [("T1r1", "T1r2"), ("T1r3", "T2r1"), ("T2r2", "T2r3"), ("T3r1", "T3r2"),
             ("T3r3", "F1r1"), ("F1r2", "F1r3"), ("T7r1", "T7r2"), ("T7r3", "T8r1"),
             ("T8r2", "T8r3"), ("F2r1", "F2r2")]
    solo = ["F2r3"]
    results = []
    for a1, b1 in pairs:
        print(f"[{time.strftime('%H:%M:%S')}] pair {a1}+{b1}", flush=True)
        ver_now = harness_state()
        with open(out / "harness_log.jsonl", "a") as f:
            f.write(json.dumps({"pair": f"{a1}+{b1}", "opencode": ver_now,
                                "ts": time.strftime("%H:%M:%S")}) + "\n")
        if ver_now != harness0 and not any(d.get("to") == ver_now for d in drift):
            drift.append({"pair": f"{a1}+{b1}", "from": harness0, "to": ver_now})
            print(f"  !! HARNESS DRIFT: {harness0} -> {ver_now} at pair {a1}+{b1}.", flush=True)
        outmap = {}
        def go(n):
            outmap[n] = run_trial(n, B[n], sess, GROUND_RULES)
        ta = threading.Thread(target=go, args=(a1,)); tb = threading.Thread(target=go, args=(b1,))
        ta.start(); tb.start(); ta.join(); tb.join()
        results.extend([outmap[a1], outmap[b1]])
        with open(out / "wave_summary.jsonl", "a") as f:
            for n in (a1, b1):
                f.write(json.dumps({"task": n, "ok": outmap[n].get("ok"),
                        "turns": outmap[n].get("num_turns"), "tools": outmap[n].get("tool_use_count"),
                        "wall_s": outmap[n].get("wall_s")}) + "\n")
        time.sleep(15)
    for n in solo:
        print(f"[{time.strftime('%H:%M:%S')}] solo {n}", flush=True)
        results.append(run_trial(n, B[n], sess, GROUND_RULES))
        with open(out / "wave_summary.jsonl", "a") as f:
            f.write(json.dumps({"task": n, "ok": results[-1].get("ok"),
                    "turns": results[-1].get("num_turns"), "tools": results[-1].get("tool_use_count"),
                    "wall_s": results[-1].get("wall_s")}) + "\n")
    (out / "wave_results.json").write_text(json.dumps(
        {"trials": results, "harness_start": harness0, "harness": "opencode",
         "harness_drift": drift,
         "task_set": {"hard": ["T3", "T7", "T8", "F1", "F2"], "smoke": ["T1", "T2"]},
         "tl_base": a.tl_base, "render_root": a.render_root}, indent=1))
    print(f"WAVE DONE — {out}", flush=True)

if __name__ == "__main__":
    main()
