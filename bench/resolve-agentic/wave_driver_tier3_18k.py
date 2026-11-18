#!/usr/bin/env python3
"""Driver — Tier 3 friction wave (2026-11-18k): does the adopted naming rule reduce friction?

Per PLAN-tier3-2026-11-18k.md. Same seal, same briefs, same single-project sequential design
as the published 17h waves; two arms distinguished ONLY by the trial AGENTS.md:
  Arm A (control, reps r1-r3): trial_agents() exactly as every published wave.
  Arm B (rule,   reps r4-r6): trial_agents() + the byte-identical Tier 2 probe-B rule sentence.
Both arms run on the same stack (MCP 5.3.3 / opencode 2.3.1, traps re-armed the same day).
Pair order (r1,r4)(r2,r5)(r3,r6) per brief so engine warmth cannot favour an arm.
Headline: mangled attempts, tool uses, wall time (medians per brief/arm). Pass axis recorded,
secondary. The T8 snapshot rule, placement audit, seal census, harness drift log: unchanged.
"""
import json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wave_driver_f1f2_opencode_v2 as v2                     # noqa: E402
from build_fixture_effort_ab import Client                    # noqa: E402
from probe_mangle_driver import RULE                          # byte-identical probe-B sentence

TL = "_mcp_AGBench-2026-11-18k"
RENDER = os.environ.get("AGBENCH_RENDER_ROOT",
                        "/Volumes/YourVolume/resolve-audio-analysis/agbench_2026-11-18k")
OUT = HERE / "results" / "tier3-2026-11-18k"
SNAPS = OUT / "snapshots"
REPS = (1, 2, 3, 4, 5, 6)
BRIEFS = ("T1", "T2", "T3", "F1", "T7", "T8", "F2")
# paired dispatch order: control/rule back-to-back per pair, briefs in published order
TASKS = [f"{b}r{r}" for b in BRIEFS for j in (1, 2, 3) for r in (j, j + 3)]
RULE_REPS = {4, 5, 6}


def arm(task):
    return "B_rule" if int(task[-1]) in RULE_REPS else "A_control"


def run_trial(task, sess_root, GROUND_RULES, B):
    cwd = sess_root / task
    cwd.mkdir(parents=True, exist_ok=True)
    full = B[task] + "\n\n" + GROUND_RULES
    (cwd / "BRIEF_AS_SENT.md").write_text(full)
    agents = v2.trial_agents()
    if arm(task) == "B_rule":
        agents += "\n" + RULE + "\n"
    (cwd / "AGENTS.md").write_text(agents)
    (cwd / "opencode.json").write_text(json.dumps(v2.trial_config(), indent=1))
    env = dict(os.environ)
    env["OPENCODE_CONFIG"] = str((cwd / "opencode.json").resolve())
    cmd = ["opencode", "run", "--standalone", "--format", "json", full]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                           text=True, timeout=2400)
    except Exception as e:
        return {"task": task, "arm": arm(task), "error": str(e)[:200],
                "wall_s": round(time.time() - t0, 1)}
    t1 = time.time()
    rec = {"task": task, "arm": arm(task), "ok": p.returncode == 0,
           "wall_s": round(t1 - t0, 1), "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000)}
    ev = v2.parse_events(p.stdout)
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
    k = task[-1]
    cands = {f"{TL}_{task}", f"{TL}_{task.lower()}"}
    if task.startswith("F1"):
        cands.add(f"{TL}_f1s{k}")
    if task.startswith("F2"):
        cands.add(f"{TL}_f2r{k}")
    return [t for t in tls if t["name"] in cands]


def snapshot(task, mc):
    out = {"task": task, "arm": arm(task), "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
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
    global RENDER, SNAPS, TL
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", default=None, help="run ONE trial, e.g. --smoke T1r1, then stop")
    ap.add_argument("--skip", default="", help="comma list of TASK already done")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--render-root", default=None)
    ap.add_argument("--tl-base", default=TL)
    a = ap.parse_args()
    if a.render_root:
        RENDER = a.render_root
    TL = a.tl_base

    v2.seal_host_hygiene()
    vol = pathlib.Path(*pathlib.Path(RENDER).parts[:2])
    if "YourVolume" in RENDER or not vol.exists():
        sys.exit(f"render root unusable: {RENDER}\n"
                 "Pass --render-root <real volume path>; refusing placeholder creation.")
    out = pathlib.Path(a.out)
    SNAPS = out / "snapshots"
    sess = out / "sessions"
    sess.mkdir(parents=True, exist_ok=True)
    SNAPS.mkdir(parents=True, exist_ok=True)
    for k in REPS:
        pathlib.Path(RENDER, f"T7r{k}").mkdir(parents=True, exist_ok=True)
    (out / "archived_briefs.md").write_text(json.dumps({
        "wave": out.name, "single_project": TL, "render_root": RENDER,
        "effort": "daily (no proxy; engine default; OpenCode sends none)",
        "agents_hidden": True,
        "arms": {"A_control": "reps r1-r3: trial_agents() as published",
                 "B_rule": "reps r4-r6: trial_agents() + probe-B rule (byte-identical)",
                 "rule_text": RULE},
        "stack": "MCP 5.3.3 (fingerprint mcp-fingerprint-post5.3.3.json) / opencode 2.3.1 "
                 "(binary sha 25b6895db61be9a429ecc5513ca21ec4f5cbf62d6039950dd72e5aab6b9b319d) "
                 "/ Splash 1.7.0; traps re-armed 2026-11-18 (rearm-traps-_mcp_17j_rearm.json)",
        "tenancy": "disclosed — operator session shares the engine alongside this wave",
        "frames": {"base_src": v2.BASE_SRC, "insert_src": v2.INS_SRC, "insert_frames": v2.INS_F,
                   "probe_src": v2.PROB_SRC, "probe_frames": v2.PROB_F, "slip_src": v2.SLIP_SRC},
    }, indent=1))
    harness0 = v2.harness_preflight(out)
    engine_config_proof(out)
    B = v2.briefs(TL, RENDER, reps=REPS)
    G = v2.ground_rules(TL)
    mc = Client(out / "snapshot-mcp-calls.jsonl")

    hidden = pathlib.Path(str(v2.GLOBAL_AGENTS) + ".bench-hidden")
    if v2.GLOBAL_AGENTS.exists():
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
            print(f"[{time.strftime('%H:%M:%S')}] {task} arm={arm(task)} (sequential, daily)",
                  flush=True)
            ver_now = v2.harness_state()
            with open(out / "harness_log.jsonl", "a") as f:
                f.write(json.dumps({"task": task, "arm": arm(task), "opencode": ver_now,
                                    "ts": time.strftime("%H:%M:%S")}) + "\n")
            if ver_now != harness0 and not any(d.get("to") == ver_now for d in drift):
                drift.append({"task": task, "from": harness0, "to": ver_now})
                print(f"  !! HARNESS DRIFT: {harness0} -> {ver_now} at {task}.", flush=True)
            try:
                r = run_trial(task, sess, G, B)
            except Exception as e:
                import traceback
                traceback.print_exc()
                r = {"task": task, "arm": arm(task), "error": repr(e)[:300]}
            results.append(r)
            snap = snapshot(task, mc)
            r["snapshot"] = str((SNAPS / f"{task}.json").relative_to(out))
            if task.startswith("T8"):
                r["t8_comps_in_trial"] = {n: s.get("fusion_comps")
                                          for n, s in snap.get("owned", {}).items()}
            u = r.get("usage", {})
            with open(out / "wave_summary.jsonl", "a") as f:
                f.write(json.dumps({"task": task, "arm": r.get("arm"), "ok": r.get("ok"),
                        "turns": r.get("num_turns"), "tools": r.get("tool_use_count"),
                        "wall_s": r.get("wall_s"), "reasoning_tok": u.get("reasoning"),
                        "output_tok": u.get("output"), "cost_usd": r.get("cost_usd")}) + "\n")
            time.sleep(15)
        (out / "wave_results.json").write_text(json.dumps({
            "trials": results, "harness_start": harness0, "harness": "opencode",
            "harness_drift": drift,
            "task_set": {"hard": ["T3", "T7", "T8", "F1", "F2"], "smoke": ["T1", "T2"]},
            "arms": {"A_control": ["r1", "r2", "r3"], "B_rule": ["r4", "r5", "r6"]},
            "tl_base": TL, "render_root": RENDER,
            "grading_note": "T8 grades from snapshots/<task>.json fusion_comps (in-trial); "
                            "post-wave comp reads are product-behavior data only"}, indent=1))
        print(f"WAVE DONE — {out}", flush=True)
    finally:
        mc.close()
        if hidden.exists() and not v2.GLOBAL_AGENTS.exists():
            hidden.rename(v2.GLOBAL_AGENTS)
            print("global AGENTS.md restored", flush=True)


if __name__ == "__main__":
    main()
