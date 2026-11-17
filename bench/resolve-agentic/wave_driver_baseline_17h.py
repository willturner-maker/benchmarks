#!/usr/bin/env python3
"""Driver — 2026-11-17h baseline wave (fixed fixtures, daily config, SINGLE arm).

Per PLAN-baseline-2026-11-17h.md; every design choice traces to a 17g VALIDITY flaw:
- ONE scratch project (TL below): the 17g two-project design raced on Resolve's host-global
  current project (flaws 1+2). No arm split — this wave MEASURES THE DAILY CONFIG (effort
  medium since the operator flip; OpenCode sends no reasoning_effort, engine banner captured).
- TRIALS SEQUENTIAL: the one host-global state that survives single-project is CURRENT
  TIMELINE; 17g needed concurrency only to pair arms. Sequential + named-timeline targeting
  removes the class. The per-trial placement audit (timelines_present snapshots) is kept.
- IN-TRIAL SNAPSHOTS after every session: timeline census, per-trial-timeline probe, and for
  T8 trials the comp read-backs (get_comp_count / get_comp_names per video item). The T8 cell
  grades from THAT snapshot (flaw 3: comps can be evicted later; the snapshot is the last
  moment the agent's work is guaranteed observable). Post-wave reads remain product-behavior
  data.
Seal/briefs/ground rules/harness checks are REUSED verbatim from the v2 driver; the builder's
Client (scrubbed MCP log) does the snapshots. Grading stays read-backs only.
"""
import json, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wave_driver_f1f2_opencode_v2 as v2                     # noqa: E402
from build_fixture_effort_ab import Client                    # noqa: E402

TL = "_mcp_AGBench-2026-11-17h"
# Placeholder per repo convention; the REAL volume is passed at wave time via
# --render-root (or AGBENCH_RENDER_ROOT), same sanitation as every published wave's driver.
RENDER = __import__("os").environ.get("AGBENCH_RENDER_ROOT",
                                      "/Volumes/YourVolume/resolve-audio-analysis/agbench_2026-11-17h")
OUT = HERE / "results" / "baseline-2026-11-17h"
SNAPS = OUT / "snapshots"
TASKS = ["T1r1", "T1r2", "T1r3", "T2r1", "T2r2", "T2r3",
         "T3r1", "T3r2", "T3r3", "F1r1", "F1r2", "F1r3",
         "T7r1", "T7r2", "T7r3", "T8r1", "T8r2", "T8r3",
         "F2r1", "F2r2", "F2r3"]


def run_trial(task, sess_root, GROUND_RULES, B):
    cwd = sess_root / task
    cwd.mkdir(parents=True, exist_ok=True)
    full = B[task] + "\n\n" + GROUND_RULES
    (cwd / "BRIEF_AS_SENT.md").write_text(full)
    (cwd / "AGENTS.md").write_text(v2.trial_agents())
    (cwd / "opencode.json").write_text(json.dumps(v2.trial_config(), indent=1))
    env = dict(__import__("os").environ)
    env["OPENCODE_CONFIG"] = str((cwd / "opencode.json").resolve())
    cmd = ["opencode", "run", "--standalone", "--format", "json", full]
    t0 = time.time()
    import subprocess
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                           text=True, timeout=2400)
    except Exception as e:
        return {"task": task, "error": str(e)[:200], "wall_s": round(time.time() - t0, 1)}
    t1 = time.time()
    rec = {"task": task, "ok": p.returncode == 0, "wall_s": round(t1 - t0, 1),
           "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000)}
    ev = v2.parse_events(p.stdout)
    # seal audit with 17g semantics: errored tools log as (name,"error"); builtin tools
    # arrive UNprefixed in 2.3.0. Distribution of mangled-name ATTEMPTS is itself reported.
    allowed = tuple(f"{n}_" for n in v2.KEEP) + ("resolve_control",)
    def tool_name(t):
        return str(t[0]) if isinstance(t, tuple) else str(t)
    leaks = [str(t) for t in ev["tool_uses"] if not tool_name(t).startswith(allowed)]
    rec["seal_leaks"] = leaks
    if leaks:
        print(f"  !! SEAL LEAK in {task}: {leaks}", flush=True)
    rec.update({"result": ("\n".join(ev["texts"]))[:4000] or p.stderr[:2000],
                "num_turns": ev["steps"], "tool_use_count": len(ev["tool_uses"]),
                "tools": ev["tool_uses"], "session_id": ev["session"],
                "cost_usd": ev["cost"], "usage": ev["tokens"]})
    (cwd / "result.json").write_text(json.dumps(rec, indent=1))
    (cwd / "events.json").write_text(p.stdout)
    return rec


def owned_timeline(tls, task):
    """Trial-owned timeline candidates: T-trials create NEW <TL>_<task>; F-trials act on the
    prebuilt lowercase copies (<TL>_f1s<k> / <TL>_f2r<k>)."""
    k = task[-1]
    cands = {f"{TL}_{task}", f"{TL}_{task.lower()}"}
    if task.startswith("F1"):
        cands.add(f"{TL}_f1s{k}")
    if task.startswith("F2"):
        cands.add(f"{TL}_f2r{k}")
    return [t for t in tls if t["name"] in cands]


def snapshot(task, mc):
    """In-trial read-back — the state of record for T8, the placement audit for all."""
    out = {"task": task, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    tls = mc.tool("timeline", "list").get("timelines", [])
    out["timelines_present"] = sorted(t["name"] for t in tls if t["name"].startswith(TL))
    for t in owned_timeline(tls, task):
        name = t["name"]
        snap = {"id": t["id"], "probe": mc.tool("timeline", "probe_timeline_structure",
                                                {"timeline_id": t["id"]})}
        if task.startswith("T8"):
            items = mc.tool("timeline", "get_items", {"track_type": "video",
                                                      "track_index": 1,
                                                      "timeline_name": name}).get("items", [])
            comps = []
            for pos, _it in enumerate(items):
                cc = mc.tool("timeline_item_fusion", "get_comp_count",
                             {"track_type": "video", "track_index": 1, "item_index": pos,
                              "timeline_id": t["id"]})
                cn = mc.tool("timeline_item_fusion", "get_comp_names",
                             {"track_type": "video", "track_index": 1, "item_index": pos,
                              "timeline_id": t["id"]})
                comps.append({"item_index": pos,
                              "comp_count": cc.get("comp_count", cc.get("count")),
                              "comp_names": cn.get("comp_names", cn.get("names"))})
            snap["fusion_comps"] = comps
            print(f"  T8 snapshot {name}: {comps}", flush=True)
        out.setdefault("owned", {})[name] = snap
    (SNAPS / f"{task}.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def engine_config_proof(out):
    """Daily-config proof: the supervisor's own arg line + the startup banner's effort line
    (same source the start.sh flip record used — config on disk is not proof)."""
    import subprocess
    ps = subprocess.run(["pgrep", "-f", "-fl", "server.server"], capture_output=True, text=True)
    args = [l for l in ps.stdout.splitlines() if "--default-reasoning-effort" in l]
    log = pathlib.Path.home() / "Library/Logs/splash/splash.err.log"
    banner = []
    if log.exists():
        banner = [l for l in log.read_text(errors="ignore").splitlines()
                  if "reasoning-effort" in l or "effort absent" in l][-6:]
    (out / "engine_config.json").write_text(json.dumps(
        {"supervisor_args": [a[:400] for a in args], "banner_lines": banner}, indent=1))
    print("engine proof:", (args[:1] or ["<no supervisor arg line>"])[0][:120], flush=True)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", default=None, help="run ONE trial, e.g. --smoke T1r1, then stop")
    ap.add_argument("--skip", default="", help="comma list of TASK already done")
    ap.add_argument("--out", default=str(OUT), help="wave output dir (smoke runs go elsewhere)")
    ap.add_argument("--render-root", default=None,
                    help="real render volume for this wave (overrides env/placeholder)")
    # 17h adds --keep-agents: with tenancy disclosed (the operator session runs alongside),
    # hiding the operator's global AGENTS.md for hours only starves the operator, while the
    # TRIAL sessions were already proven seal-clean (smoke: 0 leaks, project untouched).
    ap.add_argument("--keep-agents", action="store_true",
                    help="do not hide the operator's global AGENTS.md (tenancy-disclosed waves only)")
    a = ap.parse_args()
    global RENDER, SNAPS
    if a.render_root:
        RENDER = a.render_root

    v2.seal_host_hygiene()
    # Refuse a placeholder/unmounted render root BEFORE any mkdir(parents=True): on macOS
    # /Volumes is writable, so a forgotten --render-root would silently create junk dirs.
    vol = pathlib.Path(*pathlib.Path(RENDER).parts[:2])   # /Volumes/<name>
    if "YourVolume" in RENDER or not vol.exists():
        sys.exit(f"render root unusable: {RENDER}\n"
                 "Pass --render-root <real volume path> (the volume must already exist); "
                 "refusing to create a placeholder on the root volume.")
    out = pathlib.Path(a.out)
    SNAPS = out / "snapshots"   # module SNAPS is bound to the default OUT; follow --out
    sess = out / "sessions"
    sess.mkdir(parents=True, exist_ok=True)
    SNAPS.mkdir(parents=True, exist_ok=True)
    for k in (1, 2, 3):
        pathlib.Path(RENDER, f"T7r{k}").mkdir(parents=True, exist_ok=True)
    (out / "archived_briefs.md").write_text(json.dumps({
        "wave": "baseline-2026-11-17h", "single_project": TL, "render_root": RENDER,
        "effort": "daily (no proxy; engine default; OpenCode sends none)",
        "agents_hidden": not a.keep_agents,
        "tenancy": "disclosed — operator session shares the engine alongside this wave",
        "frames": {"base_src": v2.BASE_SRC, "insert_src": v2.INS_SRC, "insert_frames": v2.INS_F,
                   "probe_src": v2.PROB_SRC, "probe_frames": v2.PROB_F, "slip_src": v2.SLIP_SRC},
    }, indent=1))
    harness0 = v2.harness_preflight(out)
    engine_config_proof(out)
    B = v2.briefs(TL, RENDER)
    G = v2.ground_rules(TL)
    mc = Client(out / "snapshot-mcp-calls.jsonl")   # one stdio session for all snapshots

    hidden = pathlib.Path(str(v2.GLOBAL_AGENTS) + ".bench-hidden")
    if a.keep_agents:
        print("--keep-agents: operator global AGENTS.md left in place (tenancy disclosed)",
              flush=True)
    elif v2.GLOBAL_AGENTS.exists():
        v2.GLOBAL_AGENTS.rename(hidden)
    elif hidden.exists():
        print("!! global AGENTS.md already renamed away by an earlier aborted run; "
              "leaving it hidden for this wave", flush=True)
    skip = set(x for x in a.skip.split(",") if x)
    try:
        drift = []
        tasks = [a.smoke] if a.smoke else TASKS
        results = []
        for task in tasks:
            if task in skip:
                continue
            print(f"[{time.strftime('%H:%M:%S')}] {task} (sequential, daily config)", flush=True)
            ver_now = v2.harness_state()
            with open(out / "harness_log.jsonl", "a") as f:
                f.write(json.dumps({"task": task, "opencode": ver_now,
                                    "ts": time.strftime("%H:%M:%S")}) + "\n")
            if ver_now != harness0 and not any(d.get("to") == ver_now for d in drift):
                drift.append({"task": task, "from": harness0, "to": ver_now})
                print(f"  !! HARNESS DRIFT: {harness0} -> {ver_now} at {task}.", flush=True)
            try:
                r = run_trial(task, sess, G, B)
            except Exception as e:
                import traceback
                traceback.print_exc()
                r = {"task": task, "error": repr(e)[:300]}
            results.append(r)
            snap = snapshot(task, mc)
            r["snapshot"] = str((SNAPS / f"{task}.json").relative_to(out))
            if task.startswith("T8"):
                r["t8_comps_in_trial"] = {n: s.get("fusion_comps")
                                          for n, s in snap.get("owned", {}).items()}
            u = r.get("usage", {})
            with open(out / "wave_summary.jsonl", "a") as f:
                f.write(json.dumps({"task": task, "ok": r.get("ok"),
                        "turns": r.get("num_turns"), "tools": r.get("tool_use_count"),
                        "wall_s": r.get("wall_s"), "reasoning_tok": u.get("reasoning"),
                        "output_tok": u.get("output"), "cost_usd": r.get("cost_usd")}) + "\n")
            time.sleep(15)
        (out / "wave_results.json").write_text(json.dumps({
            "trials": results, "harness_start": harness0, "harness": "opencode",
            "harness_drift": drift,
            "task_set": {"hard": ["T3", "T7", "T8", "F1", "F2"], "smoke": ["T1", "T2"]},
            "tl_base": TL, "render_root": RENDER,
            "grading_note": "T8 grades from snapshots/<task>.json fusion_comps (in-trial); "
                            "post-wave comp reads are product-behavior data only"}, indent=1))
        print(f"WAVE DONE — {out}", flush=True)
    finally:
        mc.close()
        # Restore only OUR copy, and only if nothing else occupies the real path (a --keep-agents
        # run over a leftover .bench-hidden from an aborted earlier wave must not clobber state).
        if hidden.exists() and not v2.GLOBAL_AGENTS.exists():
            hidden.rename(v2.GLOBAL_AGENTS)
            print("global AGENTS.md restored", flush=True)


if __name__ == "__main__":
    main()
