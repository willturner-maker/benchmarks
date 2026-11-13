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
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, time, threading

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "bench" / "resolve-agentic" / "results" / "2026-11-13-wave"
SESS = OUT / "sessions"
TL_BASE = "_mcp_AGBench-2026-11-13"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
# Fixture-derived frame numbers (read from the untracked ground_truth at grade time; the
# briefs embed only the numbers, never the media path).
BASE_SRC, INS_SRC, INS_F, PROB_SRC, PROB_F = 5036, 25181, 101, 10072, 121
RENDER_ROOT = "/Volumes/YourVolume/resolve-audio-analysis/agbench_2026-11-13"

# --- harness (agent CLI) warning protocol -------------------------------------
# Operator rule (2026-11-13): Claude Code auto-update stays ON — this driver never
# disables or pins it. Harness build is part of the measured system (RUNBOOK §6), so
# the driver instead (a) prints the build plus a same-build verdict against the PREVIOUS
# wave before any trial dispatches, so the operator decides up front, and (b) records a
# loud deviation if the build moves mid-wave (what happened in 2026-11-13i, pair 4→5).
RESULTS_ROOT = REPO / "bench" / "resolve-agentic" / "results"

def harness_state():
    """(version, resolved binary path, binary mtime) for the `claude` this driver uses."""
    exe = shutil.which("claude")
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    real = os.path.realpath(exe) if exe else None
    mt = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(os.path.getmtime(real))) if real and os.path.exists(real) else None
    return ver, real, mt

def previous_harness(exclude):
    """Most recent prior wave's harness build, for the same-build verdict.
    Sources, newest first: a wave dir's harness.json, else a committed
    results-*.json build.claude_code (older waves recorded it by backfill)."""
    cands = []
    if RESULTS_ROOT.exists():
        for hj in RESULTS_ROOT.glob("*/harness.json"):
            if hj.parent == exclude:
                continue
            try:
                cands.append((hj.stat().st_mtime, json.loads(hj.read_text()).get("claude_code"),
                              hj.parent.name, "harness.json"))
            except Exception:
                continue
    for rj in (REPO / "bench" / "resolve-agentic").glob("results-*.json"):
        try:
            build = json.loads(rj.read_text()).get("build") or {}
            cc = build.get("claude_code")
            if cc:
                cands.append((rj.stat().st_mtime, cc, rj.name, "results-json"))
        except Exception:
            continue
    if not cands:
        return None, None
    cands.sort()
    return {"claude_code": cands[-1][1], "source": cands[-1][3]}, cands[-1][2]

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

def harness_preflight(write=True):
    """Print the harness build + same-build verdict BEFORE any trial dispatches.
    write=False is the `--check-harness` mode: report only, never touch a wave record."""
    ver, real, mt = harness_state()
    prev, prev_wave = previous_harness(OUT)
    prev_cc = (prev or {}).get("claude_code") or ""
    builds_prev = re.findall(r"\d+\.\d+\.\d+", prev_cc)
    mixed = len(builds_prev) > 1
    # compare by version token: prior records may carry prose around the number
    # (e.g. "2.1.322 (backfilled …)"); a MIXED prior wave is only comparable to the
    # build it ENDED on, which the "mixed" branches below handle, never `same`.
    m0 = re.search(r"\d+\.\d+\.\d+", ver)
    ver_build = m0.group(0) if m0 else ver
    same = bool(prev) and not mixed and bool(builds_prev) and builds_prev[0] == ver_build
    # drift hazard specific to the native installer: the updater can install a newer
    # build and flip the shim between pairs (13i's mechanism) — a newer build already
    # on disk means that flip is one updater pass away.
    newer = []
    vdir = pathlib.Path.home() / ".local/share/claude/versions"
    if vdir.is_dir() and ver_build:
        def key(t): return tuple(int(x) for x in t.split("."))
        for name in vdir.iterdir():
            m1 = re.fullmatch(r"(\d+\.\d+\.\d+)", name.name)
            if m1 and key(m1.group(1)) > key(ver_build):
                newer.append(m1.group(1))
        newer.sort(key=key)
    if write:
        (OUT / "harness.json").write_text(json.dumps({
            "claude_code": ver, "binary": real, "binary_mtime": mt,
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "newer_builds_on_disk": newer or None,
            "previous_wave": prev_wave,
            "previous_claude_code": prev_cc or None,
            "previous_builds": builds_prev or None,
            "previous_wave_mixed_harness": mixed,
            "same_build_as_previous_wave": same}, indent=1))
    if newer:
        print(f"  HARNESS NOTE: newer build(s) {newer} already sit in ~/.local/share/claude/versions/; "
              f"the shim can flip to one between pairs (that is how 13i split). Watch harness_log.jsonl.",
              flush=True)
    print(f"[{time.strftime('%H:%M:%S')}] agent harness: {ver}  ({real})", flush=True)
    if prev is None:
        print("  HARNESS WARNING: no prior-wave harness on disk to compare — same-build status UNKNOWN.", flush=True)
    elif mixed and ver_build == builds_prev[-1]:
        print(f"  HARNESS NOTE: prior wave {prev_wave} ran MIXED builds {builds_prev}; this wave "
              f"matches the build it ENDED on ({builds_prev[-1]}), so it is comparable only to that "
              f"wave's second half. Note it in version_comparison.", flush=True)
    elif mixed:
        print(f"  HARNESS WARNING: prior wave {prev_wave} ran MIXED builds {builds_prev} "
              f"(ended on {builds_prev[-1]}); this wave starts on {ver} — not comparable "
              f"build-to-build. Per RUNBOOK §6 call it out in version_comparison.", flush=True)
    elif not same:
        print(f"  HARNESS WARNING: the harness moved since wave {prev_wave} "
              f"({prev.get('claude_code')} -> {ver}). This is NOT a same-build reproduction: "
              f"per RUNBOOK §6 treat it like a server bump and call it out in version_comparison. "
              f"Auto-update is deliberately left ON (operator decision 2026-11-13), so this is a "
              f"warning, not a block.", flush=True)
    else:
        print(f"  same build as wave {prev_wave} — safe for a same-build reproduction.", flush=True)
    return ver

def main():
    if "--check-harness" in sys.argv:
        # report-only: never writes, so it is safe to run any time (before, during,
        # or after a wave) without touching a wave record.
        harness_preflight(write=False)
        return
    SESS.mkdir(parents=True, exist_ok=True)
    (OUT / "archived_briefs.md").write_text(json.dumps({"TL_BASE": TL_BASE,
        "frames": {"base_src": BASE_SRC, "insert_src": INS_SRC, "probe_src": PROB_SRC}}, indent=1))
    # harness version is part of the measured system (RUNBOOK §6): claude -p startup,
    # context accounting on third-party gateways, and deny-rule enforcement all move
    # agent walls/uses across Claude Code releases. Warn up front, never block.
    harness0 = harness_preflight()
    drift = []
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
            # mid-wave harness watch: record every dispatch build, shout if it moves.
            # (13i lost same-build status silently between pairs 4 and 5.)
            ver_now, _, _ = harness_state()
            with open(OUT / "harness_log.jsonl", "a") as f:
                f.write(json.dumps({"pair": f"{a}+{b}", "claude_code": ver_now,
                                    "ts": time.strftime("%H:%M:%S")}) + "\n")
            if ver_now != harness0 and not any(d.get("to") == ver_now for d in drift):
                drift.append({"pair": f"{a}+{b}", "from": harness0, "to": ver_now})
                print(f"  !! HARNESS DRIFT: {harness0} -> {ver_now} at pair {a}+{b}. Trials dispatched "
                      f"from this pair onward run the new build (each is labelled in harness_log.jsonl); "
                      f"treat deltas across this boundary as not same-build. Recorded in wave_results.json.",
                      flush=True)
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
    # Shape note: this file gained a wrapper (was a bare trial list) so harness state
    # travels with the trials that were measured under it.
    (OUT / "wave_results.json").write_text(json.dumps(
        {"trials": results, "harness_start": harness0, "harness_drift": drift}, indent=1))
    print(f"WAVE DONE — {OUT}", flush=True)

if __name__ == "__main__":
    main()
