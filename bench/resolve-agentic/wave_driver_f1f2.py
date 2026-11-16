#!/usr/bin/env python3
"""Resolve agentic benchmark driver for the F1/F2 series (first wave 2026-11-16).

Same seal as `wave_driver.py` (read that docstring first — strict MCP config built at
runtime into a tempfile outside the repo, every shell/file/web tool denied, fresh session
per trial, per-trial cwd, harness build watched not pinned). What differs:

  * Task set: **five scored tasks** (T3, T7, T8, F1, F2) and **two smoke tasks** (T1, T2),
    n=3 → `hard set 15/15, smoke set 6/6`. A changed task set opens a NEW series
    (RUNBOOK §6), so this wave does not extend the seven-wave 126/126 ladder.
  * T4 is out of the set (its intended trap is inert as briefed — tasks.md).
  * **F1/F2 timelines are pre-built and pre-armed by the operator**, one per trial, and the
    brief names that timeline and forbids copying or re-creating it. Reason: the armed
    pre-state IS the measurement. `timeline.duplicate` does not carry Fusion comps and
    `create_variant_from_ranges` re-appends from pool media, so an agent-built copy would
    silently flatten the arm and the loss matrix could not be graded. The operator holds a
    pre-agent pre-state per trial, so the grader compares like with like.
  * Everything is parameterized (`--tl-base`, `--out`, `--render-root`) so the tracked copy
    keeps placeholder paths while the real run supplies them on the command line.

Operator discipline (RUNBOOK §2): after launching, make NO Resolve call of any kind until
every agent has reported.
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys, tempfile, time, threading

REPO = pathlib.Path(__file__).resolve().parents[2]
RESULTS_ROOT = REPO / "bench" / "resolve-agentic" / "results"
DEFAULT_TL_BASE = "_mcp_AGBench-YYYY-MM-DD"
DEFAULT_OUT = REPO / "bench" / "resolve-agentic" / "results" / "YYYY-MM-DD-f1f2-wave"
DEFAULT_RENDER_ROOT = "/Volumes/YourVolume/resolve-audio-analysis/agbench_YYYY-MM-DD"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"

# Fixture-derived frame numbers (from the wave's untracked ground_truth-<date>.json; the
# briefs embed only the numbers, never the media path).
BASE_SRC, INS_SRC, INS_F, PROB_SRC, PROB_F = 5036, 25181, 101, 10072, 121
SLIP_SRC, SLIP_FRAMES = 6000, 221
TL_W, TL_H = 3840, 1520

# --- harness (agent CLI) warning protocol: identical to wave_driver.py -----------
def harness_state():
    exe = shutil.which("claude")
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    real = os.path.realpath(exe) if exe else None
    mt = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(os.path.getmtime(real))) if real and os.path.exists(real) else None
    return ver, real, mt

def previous_harness(exclude):
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

def build_of(s):
    m = re.search(r"\d+\.\d+\.\d+", s or "")
    return m.group(0) if m else s

def harness_preflight(out_dir, write=True):
    ver, real, mt = harness_state()
    prev, prev_wave = previous_harness(out_dir)
    prev_cc = (prev or {}).get("claude_code") or ""
    builds_prev = re.findall(r"\d+\.\d+\.\d+", prev_cc)
    mixed = len(builds_prev) > 1
    ver_build = build_of(ver)
    same = bool(prev) and not mixed and bool(builds_prev) and builds_prev[0] == ver_build
    newer = []
    vdir = pathlib.Path.home() / ".local/share/claude/versions"
    if vdir.is_dir() and ver_build:
        key = lambda t: tuple(int(x) for x in t.split("."))
        for name in vdir.iterdir():
            m1 = re.fullmatch(r"(\d+\.\d+\.\d+)", name.name)
            if m1 and key(m1.group(1)) > key(ver_build):
                newer.append(m1.group(1))
        newer.sort(key=key)
    if write:
        (out_dir / "harness.json").write_text(json.dumps({
            "claude_code": ver, "binary": real, "binary_mtime": mt,
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "newer_builds_on_disk": newer or None,
            "previous_wave": prev_wave, "previous_claude_code": prev_cc or None,
            "previous_builds": builds_prev or None, "previous_wave_mixed_harness": mixed,
            "same_build_as_previous_wave": same}, indent=1))
    if newer:
        print(f"  HARNESS NOTE: newer build(s) {newer} already sit in ~/.local/share/claude/versions/; "
              f"the shim can flip to one between pairs. Watch harness_log.jsonl.", flush=True)
    print(f"[{time.strftime('%H:%M:%S')}] agent harness: {ver}  ({real})", flush=True)
    if prev is None:
        print("  HARNESS WARNING: no prior-wave harness on disk — same-build status UNKNOWN.", flush=True)
    elif mixed and ver_build == builds_prev[-1]:
        print(f"  HARNESS NOTE: prior wave {prev_wave} ran MIXED builds {builds_prev}; this wave matches "
              f"the build it ENDED on ({builds_prev[-1]}) — comparable only to that half.", flush=True)
    elif mixed:
        print(f"  HARNESS WARNING: prior wave {prev_wave} ran MIXED builds {builds_prev}; this wave starts "
              f"on {ver} — not comparable build-to-build.", flush=True)
    elif not same:
        print(f"  HARNESS WARNING: the harness moved since wave {prev_wave} ({prev_cc} -> {ver}). Not a "
              f"same-build reproduction; call it out in version_comparison. Auto-update stays ON by policy.",
              flush=True)
    else:
        print(f"  same build as wave {prev_wave} — safe for a same-build reproduction.", flush=True)
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
    # F1 — slip an armed clip, then account for every property the rebuild did or did not carry.
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
    # F2 — ripple insert on a timeline that carries a transition.
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

def strict_mcp_config():
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

def run_trial(name, prompt, mcp_cfg, sess_root):
    cwd = sess_root / name
    cwd.mkdir(parents=True, exist_ok=True)
    full = prompt + "\n\n" + GROUND_RULES
    (cwd / "BRIEF_AS_SENT.md").write_text(full)
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
        usage = d.get("usage")
        rec["usage"] = ({k: (usage.get(k) if isinstance(usage.get(k), int) else None)
                         for k in ("input_tokens", "cache_creation_input_tokens",
                                   "cache_read_input_tokens", "output_tokens")}
                        if isinstance(usage, dict) else None)
        rec["models"] = sorted((d.get("modelUsage") or {}).keys())
        rec["permission_denials"] = len(d.get("permission_denials") or [])
        rec["duration_api_ms"] = d.get("duration_api_ms")
    except Exception:
        rec["raw_stdout"] = p.stdout[:2000]; rec["raw_stderr"] = p.stderr[:500]
    (cwd / "result.json").write_text(json.dumps(rec, indent=1))
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
    global GROUND_RULES
    GROUND_RULES = ground_rules(a.tl_base)
    sess.mkdir(parents=True, exist_ok=True)
    # T7 target directories are pre-created operator-side. The 2026-11-16 wave proved the old brief
    # unsound: it sanctioned one `mkdir -p` while the seal denies Bash, so all three T7 trials hit a
    # dead end, improvised a directory through an MCP side effect (one of them a dry run that wrote
    # anyway), left stray files behind, and ran +119% wall / +29 turns versus the prior wave.
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
    mcp_cfg = strict_mcp_config()
    B = briefs(a.tl_base, a.render_root)
    # 10 pairs + 1 solo (21 trials). The three T7 renders sit in one pair — note that
    # co-presence in the record, as every prior wave's render numbers do.
    pairs = [("T1r1", "T1r2"), ("T1r3", "T2r1"), ("T2r2", "T2r3"), ("T3r1", "T3r2"),
             ("T3r3", "F1r1"), ("F1r2", "F1r3"), ("T7r1", "T7r2"), ("T7r3", "T8r1"),
             ("T8r2", "T8r3"), ("F2r1", "F2r2")]
    solo = ["F2r3"]
    results = []
    try:
        for a1, b1 in pairs:
            print(f"[{time.strftime('%H:%M:%S')}] pair {a1}+{b1}", flush=True)
            ver_now, _, _ = harness_state()
            with open(out / "harness_log.jsonl", "a") as f:
                f.write(json.dumps({"pair": f"{a1}+{b1}", "claude_code": ver_now,
                                    "ts": time.strftime("%H:%M:%S")}) + "\n")
            if ver_now != harness0 and not any(d.get("to") == ver_now for d in drift):
                drift.append({"pair": f"{a1}+{b1}", "from": harness0, "to": ver_now})
                print(f"  !! HARNESS DRIFT: {harness0} -> {ver_now} at pair {a1}+{b1}.", flush=True)
            outmap = {}
            def go(n):
                outmap[n] = run_trial(n, B[n], mcp_cfg, sess)
            ta = threading.Thread(target=go, args=(a1,)); tb = threading.Thread(target=go, args=(b1,))
            ta.start(); tb.start(); ta.join(); tb.join()
            results.extend([outmap[a1], outmap[b1]])
            with open(out / "wave_summary.jsonl", "a") as f:
                for n in (a1, b1):
                    f.write(json.dumps({"task": n, "ok": outmap[n].get("ok"),
                            "turns": outmap[n].get("num_turns"), "wall_s": outmap[n].get("wall_s")}) + "\n")
            time.sleep(15)
        for n in solo:
            print(f"[{time.strftime('%H:%M:%S')}] solo {n}", flush=True)
            results.append(run_trial(n, B[n], mcp_cfg, sess))
            with open(out / "wave_summary.jsonl", "a") as f:
                f.write(json.dumps({"task": n, "ok": results[-1].get("ok"),
                                    "turns": results[-1].get("num_turns"),
                                    "wall_s": results[-1].get("wall_s")}) + "\n")
    finally:
        os.unlink(mcp_cfg)
    (out / "wave_results.json").write_text(json.dumps(
        {"trials": results, "harness_start": harness0, "harness_drift": drift,
         "task_set": {"hard": ["T3", "T7", "T8", "F1", "F2"], "smoke": ["T1", "T2"]},
         "tl_base": a.tl_base, "render_root": a.render_root}, indent=1))
    print(f"WAVE DONE — {out}", flush=True)

if __name__ == "__main__":
    main()
