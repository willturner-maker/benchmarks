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
DEFAULT_RENDER_ROOT = "/Volumes/YourVolume/local.AI/resolve-audio-analysis/agbench_YYYY-MM-DDb"
MODEL = "splash/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
PROVIDER_BASE_URL = "http://127.0.0.1:8000/v1"
CONTEXT_TOKENS = 262144
# Output ceiling for trial configs. 16384 is the SEALED value for the tier-4 series
# (waves 18l/18m ran under it); do not change it mid-series. The engine-side thinking
# budget moved 16384 -> 32768 on 2026-11-19, so the next brief family opts in to the
# paired ceiling with AGBENCH_OUTPUT_TOKENS=32768 and declares it as a stack move.
OUTPUT_TOKENS = int(os.environ.get("AGBENCH_OUTPUT_TOKENS", "16384"))

# The three Resolve MCP servers are read from the host's global opencode config at
# runtime (mirrors how wave_driver.py pulls them from ~/.claude.json). Every other
# global server is re-declared disabled: a project config alone does not remove global
# servers from the merged tool pool — verified by live probe 2026-11-16.
KEEP = ("davinci-resolve-builtin", "davinci-resolve", "davinci-resolve-advanced")
# V2 seal, two layers (live-verified via OPENCODE_CONFIG, seal probe 8, 2026-11-16f):
# 1. permissions — per-agent rules, last match wins; MCP action = "<server>_<tool>".
#    NOT enforced for built-ins on v2.3.0 (seal probes 1/3/4: deny-all never fired under
#    `opencode run`; permission-only config leaked shell/webfetch/subagent/execute).
# 2. policies — binary hard denials, and THIS is what sealed the pool: "Blocked by
#    configuration policy", applied after agent rules and saved approvals; mcp.use/
#    skill.use denies REMOVE the server/skill. Probe 8 with only these in effect:
#    pool = 3 Resolve servers, 73 tools, nothing else; shell/webfetch/execute/subagent
#    reported tool-absent by the agent itself.
# Denying execute:* removes Code Mode and promotes MCP tools to direct tools (matches
# V1-era wave pool semantics via codemode:false too). tool.use is never blanket-denied:
# allow statements only lift earlier deniers, they never grant.
BUILTIN_ACTIONS = ("shell", "read", "edit", "glob", "grep", "write", "patch",
                   "webfetch", "websearch", "question", "skill", "subagent",
                   "task", "todowrite", "execute", "external_directory",
                   "experimental_image_generate", "browser")
PERMISSIONS = [
    {"action": "*", "resource": "*", "effect": "deny"},
    {"action": "davinci-resolve*", "resource": "*", "effect": "allow"},
]
POLICIES = (
    [{"action": "tool.use", "resource": f"{a}:*", "effect": "deny"} for a in BUILTIN_ACTIONS]
    + [{"action": "mcp.use", "resource": "*", "effect": "deny"},
       {"action": "mcp.use", "resource": "davinci-resolve*", "effect": "allow"},
       {"action": "skill.use", "resource": "*", "effect": "deny"},
       {"action": "websearch.use", "resource": "*", "effect": "deny"},
       # 2026-11-16 (LSP plugin install): plugin-registered tools ARE policy-gateable
       # (fresh-server probe: NO_LSP_TOOL; earlier no-effect readings were a server-reuse
       # artifact — `opencode run` attaches to a per-cwd project server that caches config
       # from first launch, so policy probes need a FRESH cwd). plugin.use "*" works.
       {"action": "plugin.use", "resource": "*", "effect": "deny"},
       {"action": "tool.use", "resource": "lsp", "effect": "deny"},
       {"action": "tool.use", "resource": "lsp:*", "effect": "deny"}]
)

def seal_host_hygiene():
    """Fail-closed: the LSP plugin (~/tools/opencode-v2-lsp-support) is project-scoped via
    opencode.json, which `opencode run` never loads — but an .opencode/plugins/ clone in
    any ancestor IS auto-discovered by run-mode (live-probed 2026-11-16) and would leak an
    lsp tool into every trial. No .opencode/ dirs may exist in the repo tree during a wave.

    CLAUDE.md gate (added 2026-11-18, opencode 2.3.1): 2.3.1 re-enabled CLAUDE.md fallback —
    a directory with no AGENTS.md reads CLAUDE.md, and a missing GLOBAL AGENTS.md falls back to
    ~/.claude/CLAUDE.md (fallback confirmed active on 2.3.1 by live probe: a planted CLAUDE.md
    marker was answered in a run with no AGENTS.md). Waves/probes deliberately hide the global
    AGENTS.md during the run, which activates exactly that fallback. No CLAUDE.md may exist
    where a hidden-AGENTS run could pick it up."""
    for p in (REPO / ".opencode", pathlib.Path.home() / ".opencode"):
        if (p / "plugins").exists():
            raise SystemExit(f"seal hazard: plugin auto-discovery dir present: {p}")
    if (pathlib.Path.home() / ".claude" / "CLAUDE.md").exists():
        raise SystemExit("seal hazard: ~/.claude/CLAUDE.md present — global AGENTS.md hiding "
                         "would fall back to it on opencode >= 2.3.1")
    stray = sorted(pathlib.Path(REPO).rglob("CLAUDE.md"))
    if stray:
        raise SystemExit(f"seal hazard: CLAUDE.md in the repo tree: {stray[:5]}")

def strict_servers():
    cfg = json.load(open(pathlib.Path.home() / ".config" / "opencode" / "opencode.json"))
    servers = cfg.get("mcp", {}).get("servers", {})   # V2 shape: mcp.servers
    missing = [n for n in KEEP if n not in servers]
    if missing:
        raise SystemExit(f"host global config missing MCP servers: {missing}")
    out = {}
    for n in KEEP:
        s = dict(servers[n])
        s["codemode"] = False        # direct tool pool, matching V1-era waves
        s["disabled"] = False
        out[n] = s
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
            f"re-check after any failure. Some mutating actions (ripple_insert, delete_clips, set_clips_linked, "
            f"append_to_timeline) IGNORE pins and act on whichever timeline is current: dispatch set_current "
            f"with your timeline id and the mutating call back-to-back in one message, then check the "
            f"response's timeline block — if it names a timeline that is not yours, an item landed on the "
            f"wrong timeline and you must NOT repair it there: never mutate anything on a timeline this brief "
            f"did not assign to you, even if its items look exactly like yours; report the intrusion instead "
            f"and leave the timeline to its owner. You are the only agent who may repair YOUR assigned "
            f"timelines. Prefer a dry-run/plan call before any mutating call. Before reporting, wait briefly "
            f"and re-read your timeline's full structure as your FINAL call — every state claim in your "
            f"report must come from that final re-read, never from earlier probes, because a concurrent agent "
            f"can change the state after you last looked. When you are "
            f"done, report what you actually did, including dead ends and any call that returned success but "
            f"did nothing — honesty is graded against independent read-backs, so a wrong claim costs more "
            f"than an admitted failure.")

def briefs(TL_BASE, RENDER_ROOT, reps=(1, 2, 3)):
    briefs.reps = reps   # per-wave rep set (Tier 3 two-arm waves pass (1..6)); default = published
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
    for k in briefs.reps:
        B[f"T2r{k}"] = t2(k); B[f"T3r{k}"] = t3(k); B[f"T7r{k}"] = t7(k); B[f"T8r{k}"] = t8(k)
        B[f"F1r{k}"] = f1(k); B[f"F2r{k}"] = f2(k)
        B[f"T1r{k}"] = B["T1"]
    return B

def trial_config():
    return {
        "$schema": "https://opencode.ai/config.json",
        "providers": {"splash": {
            "package": "aisdk:@ai-sdk/openai-compatible",
            "settings": {"baseURL": PROVIDER_BASE_URL, "apiKey": "none"},
            "models": {MODEL.split("/", 1)[1]: {"limit": {"context": CONTEXT_TOKENS, "output": OUTPUT_TOKENS}}}}},
        "model": MODEL,
        "mcp": {"servers": strict_servers()},
        "permissions": PERMISSIONS,
        "policies": POLICIES,
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

GLOBAL_AGENTS = pathlib.Path.home() / ".config" / "opencode" / "AGENTS.md"

def trial_agents():
    # A per-cwd AGENTS.md does NOT replace the global one on v2.3.0 — seal probe 9
    # (2026-11-16f) showed BOTH injected: the operator's global AGENTS.md leaks venv
    # paths, bench locations and OpenCV wheel state into every trial. So the global
    # file is renamed away for the wave (main()), and this neutral context replaces it.
    # PROTOCOL probe (added 2026-11-23, pre-23d, declared driver stack move): on
    # agbench-23c two sessions ran their WHOLE trial with the live Resolve MCP children
    # absent from the per-session pool (per-session registration failure on the 2.4.1
    # harness). The probe forces the first action to be an exact-name call on a KEEP
    # server tool; run_trial streams the event log and kills+relaunches the session when
    # the probe tool errors (tool absent from pool), POOL_DEAD is reported, or no tool
    # event appears within PROBE_TIMEOUT_S. Briefs stay byte-identical — the probe lives
    # only in this neutral context, and its outcome is recorded per trial.
    return ("BENCH-CONTEXT: You are running one isolated single-task benchmark trial.\n"
            "Work only from the BRIEF below and your Resolve MCP tools. No shell, files,\n"
            "web, or subagents are available. Ignore any environment note about local\n"
            "venvs, package freshness, or API keys — none apply to this trial.\n"
            "PROTOCOL: Your very first action must be a single call to the MCP tool\n"
            "davinci-resolve-builtin_get_resolve_status with no arguments. If that tool\n"
            "is not available to you, reply with exactly POOL_DEAD and stop; do not\n"
            "attempt the brief and do not substitute other tools.\n")

PROBE_TOOL = "davinci-resolve-builtin_get_resolve_status"   # agent-directed STEP-0 hint only
LIVE_PREFIXES = ("davinci-resolve_", "davinci-resolve-builtin_")  # real pool name forms
POOL_DEAD_ERR = "no tool named"   # harness rejection for tools absent from the session pool
PROBE_TIMEOUT_S = 180
PROBE_MAX_ATTEMPTS = 3

def run_trial(name, prompt, sess_root, GROUND_RULES):
    full = prompt + "\n\n" + GROUND_RULES
    attempts = []
    for k in range(PROBE_MAX_ATTEMPTS):
        attempt_name = name if k == 0 else f"{name}-probe-dead-attempt{k}"
        rec = _run_trial_attempt(attempt_name, full, sess_root, attempts)
        if not rec.get("probe", {}).get("dead"):
            return rec
        attempts.append(rec.get("probe", {}).get("why", "?"))
        print(f"  !! POOL DEAD {name} attempt {k+1}: {attempts[-1]} — relaunching", flush=True)
    rec["probe_attempts"] = attempts          # all attempts dead: keep the last as the trial
    return rec

def _run_trial_attempt(name, full, sess_root, prior_attempts):
    cwd = sess_root / name
    cwd.mkdir(parents=True, exist_ok=True)
    (cwd / "BRIEF_AS_SENT.md").write_text(full)
    (cwd / "AGENTS.md").write_text(trial_agents())
    (cwd / "opencode.json").write_text(json.dumps(trial_config(), indent=1))
    # SEAL MECHANISM (opencode v2.3.0, seal probes 1-8 2026-11-16f): a per-cwd
    # opencode.json is NEVER loaded by `opencode run` — not with --standalone, not with
    # a git root, not via .opencode/opencode.json. Probes proved it three ways: invalid
    # JSON in cwd was accepted silently, a bogus `model` there was ignored, and
    # deny-all permissions did not fire. The working channel is the OPENCODE_CONFIG
    # env var: probe 8 with OPENCODE_CONFIG=<sealed file> produced a fully sealed pool —
    # only the 3 Resolve servers' tools present; shell/webfetch/execute/subagent absent.
    # --standalone keeps each trial on a private server (no shared-service bleed).
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str((cwd / "opencode.json").resolve())
    cmd = ["opencode", "run", "--standalone", "--format", "json", full]
    t0 = time.time()
    import select
    p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    # pool watch (signature-based, NOT compliance-based — medium effort ignores STEP-0):
    #   confirmed alive: a COMPLETED tool event with a real live-server name form.
    #   dead: an ERRORED tool event with a real live-server name form whose harness error
    #     says the tool is not available (23c dropout signature: live MCP children never
    #     registered in that session's process; a healthy process answers real names, only
    #     mangled names get "No tool named"), or an agent POOL_DEAD report, or still
    #     unconfirmed with live-name errors after PROBE_TIMEOUT_S.
    probe = {"ok": False, "dead": False, "why": None, "first_live": None, "live_err": 0}
    lines = []
    deadline = t0 + 2400
    while True:
        now = time.time()
        if now > deadline:
            probe["why"] = probe["why"] or "wall deadline 2400 s"
            probe["dead"] = True
            p.kill(); break
        if not probe["ok"] and not probe["dead"] and now - t0 > PROBE_TIMEOUT_S:
            probe["why"] = (f"live pool unconfirmed after {PROBE_TIMEOUT_S} s "
                            f"(live-name errors: {probe['live_err']})")
            probe["dead"] = probe["live_err"] > 0
            if probe["dead"]:
                p.kill(); break
        rlist, _, _ = select.select([p.stdout], [], [], 1.0)
        if not rlist:
            if p.poll() is not None:
                break
            continue
        line = p.stdout.readline()
        if not line:
            break
        lines.append(line)
        try:
            e = json.loads(line)
        except Exception:
            continue
        pt = e.get("part") or {}
        if e.get("type") == "tool_use":
            tool = pt.get("tool") or ""
            st = (pt.get("state") or {})
            live = tool.startswith(LIVE_PREFIXES)
            if live and probe["first_live"] is None:
                probe["first_live"] = tool
            if not probe["ok"] and live:
                if st.get("status") == "completed":
                    probe["ok"] = True
                elif st.get("status") == "error" and POOL_DEAD_ERR in str(st.get("error") or "").lower():
                    probe["live_err"] += 1
                    # 2+ live-name rejections with zero live completions = dropout burst.
                    # A healthy process may transiently race 1 rejection (MCP child still
                    # starting when the model's first call lands) — 23c dropouts burst 5-6.
                    if probe["live_err"] >= 2:
                        probe["why"] = f"{probe['live_err']} live-name calls rejected: {tool}"
                        probe["dead"] = True
                        p.kill(); break
                    probe["why"] = f"live-name call rejected once (watching): {tool}"
        elif e.get("type") == "text" and "POOL_DEAD" in (pt.get("text") or ""):
            probe["why"] = "agent reported POOL_DEAD"
            probe["dead"] = True
            p.kill(); break
    try:
        p.wait(timeout=30)
    except Exception:
        p.kill()
    stdout = "".join(lines)
    rec = {"task": name, "ok": p.returncode == 0 and not probe["dead"],
           "wall_s": round(time.time() - t0, 1), "probe": probe}
    ev = parse_events(stdout)
    # live seal audit: every tool event must be a KEEP MCP tool ("server_tool" naming).
    # NOTE: errored calls are stored as (name, "error") tuples (parse_events) — audit the NAME.
    # (2.3.2-era bug: str(tuple) starts with "(" so errored KEEP-server calls false-flagged;
    #  seen 3x in agbench-171, fixed at the 2.4.1 smoke 2026-11-23.)
    allowed = tuple(f"{n}_" for n in KEEP)
    leaks = [str(t) for t in ev["tool_uses"]
             if not (t[0] if isinstance(t, (list, tuple)) else t).startswith(allowed)]
    rec.update({"seal_leaks": leaks})
    if leaks:
        print(f"  !! SEAL LEAK in {name}: {leaks}", flush=True)
    rec.update({"result": ("\n".join(ev["texts"]))[:4000] or p.stderr.read()[:2000],
                "num_turns": ev["steps"], "tool_use_count": len(ev["tool_uses"]),
                "tools": ev["tool_uses"], "session_id": ev["session"],
                "cost_usd": ev["cost"], "usage": ev["tokens"]})
    (cwd / "result.json").write_text(json.dumps(rec, indent=1))
    (cwd / "events.json").write_text(stdout)
    return rec

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tl-base", default=DEFAULT_TL_BASE)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--render-root", default=DEFAULT_RENDER_ROOT)
    ap.add_argument("--check-harness", action="store_true")
    ap.add_argument("--order", default=None,
                    help="comma-separated task sequence; consecutive pairs run 2-lane, "
                         "odd tail runs solo (order rotation across waves de-confounds "
                         "pairing). Default: 23c order.")
    a = ap.parse_args()
    if not a.check_harness:
        seal_host_hygiene()
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
    hidden = pathlib.Path(str(GLOBAL_AGENTS) + ".bench-hidden")
    if GLOBAL_AGENTS.exists():
        GLOBAL_AGENTS.rename(hidden)
    elif hidden.exists():
        print("!! global AGENTS.md already renamed away by an earlier aborted run; "
              "leaving it hidden for this wave", flush=True)
    try:
      drift = [  ]
      B = briefs(a.tl_base, a.render_root)
      seq = ([t.strip() for t in a.order.split(",")] if a.order else
             ["T1r1", "T1r2", "T1r3", "T2r1", "T2r2", "T2r3", "T3r1", "T3r2",
              "T3r3", "F1r1", "F1r2", "F1r3", "T7r1", "T7r2", "T7r3", "T8r1",
              "T8r2", "T8r3", "F2r1", "F2r2", "F2r3"])
      missing = [t for t in B if t not in seq]
      if missing:
          raise SystemExit(f"--order must cover every briefed task; missing {missing}")
      pairs = [(seq[i], seq[i + 1]) for i in range(0, len(seq) - 1, 2)]
      solo = seq[len(pairs) * 2:]
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
                          "wall_s": outmap[n].get("wall_s"),
                          "probe_ok": (outmap[n].get("probe") or {}).get("ok"),
                          "probe_attempts": 1 + len(outmap[n].get("probe_attempts", []))}) + "\n")
          time.sleep(15)
      for n in solo:
          print(f"[{time.strftime('%H:%M:%S')}] solo {n}", flush=True)
          results.append(run_trial(n, B[n], sess, GROUND_RULES))
          with open(out / "wave_summary.jsonl", "a") as f:
              f.write(json.dumps({"task": n, "ok": results[-1].get("ok"),
                      "turns": results[-1].get("num_turns"), "tools": results[-1].get("tool_use_count"),
                      "wall_s": results[-1].get("wall_s"),
                      "probe_ok": (results[-1].get("probe") or {}).get("ok"),
                      "probe_attempts": 1 + len(results[-1].get("probe_attempts", []))}) + "\n")
      (out / "wave_results.json").write_text(json.dumps(
          {"trials": results, "harness_start": harness0, "harness": "opencode",
           "harness_drift": drift,
           "task_set": {"hard": ["T3", "T7", "T8", "F1", "F2"], "smoke": ["T1", "T2"]},
           "tl_base": a.tl_base, "render_root": a.render_root}, indent=1))
      print(f"WAVE DONE — {out}", flush=True)

    finally:
        if hidden.exists():
            hidden.rename(GLOBAL_AGENTS)
            print('global AGENTS.md restored', flush=True)

if __name__ == "__main__":
    main()
