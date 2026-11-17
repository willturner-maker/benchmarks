#!/usr/bin/env python3
"""Suite-wide reasoning-effort A/B on the Resolve agentic suite (first wave 2026-11-17g).

Question: what does the per-request `reasoning_effort` setting cost or buy on real agentic
work? The engine's daily default is xhigh (16k thinking budget); a side probe showed short
tasks stop thinking early at low/medium. This wave measures the difference on the full
seven-brief suite (T1,T2,T3,T7,T8,F1,F2 x 3 trials), both arms:

  * gx  (xhigh, daily config): provider baseURL straight to the engine :8000 —
        OpenCode sends no reasoning_effort field (proxy probe 2026-11-17: effort_in_body=None),
        so direct == engine default xhigh.
  * gm  (medium): provider baseURL -> logging proxy :8011, which INJECTS
        "reasoning_effort": "medium" into every chat body (audit line effort_injected=medium).
        Engine untouched, no restart: effort is a per-request API param.

Fixture: one scratch project per arm (identical shape, verified pre-wave):
  _mcp_AGBench-2026-11-17gx / _mcp_AGBench-2026-11-17gm, 10 timelines each, armed F1/F2 copies,
  render roots agbench_2026-11-17g/{gx,gm}/T7r*/.

Pairing: for every brief-trial, the two arms run CONCURRENTLY (same brief text except the
arm's own TL_BASE/render paths), mirroring v2's two-at-a-time load. Seal is v2's:
OPENCODE_CONFIG + permissions + policies; global AGENTS.md hidden for the wave.

Arm evidence is NOT assumed: the proxy audit (epoch ms) is correlated against each session's
start/end window after the wave -> audit_by_session.json proves which session saw injected
medium and which saw none.
"""
import json, pathlib, sys, threading, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wave_driver_f1f2_opencode_v2 as v2

ARMS = {"gx": "xhigh", "gm": "medium"}
ARM_TL = {"gx": "_mcp_AGBench-2026-11-17gx", "gm": "_mcp_AGBench-2026-11-17gm"}
ARM_RENDER = {a: f"/Volumes/YourVolume/resolve-audio-analysis/agbench_2026-11-17g/{a}"
              for a in ARMS}   # operator runs point this at the real volume (publish convention)
OUT = HERE / "results" / "2026-11-17g-effort-ab-wave"
AUDIT = HERE.parent / "effort-ab-2026-11-17" / "proxy-audit.jsonl"
PROXY_URL = {"gx": "http://127.0.0.1:8010/v1",      # passthrough proxy: body unchanged, audit-only
             "gm": "http://127.0.0.1:8011/v1"}      # injecting proxy: reasoning_effort=medium
# Both arms ride one proxy hop (probe-proven behavior-neutral), so arm attribution is by PORT:
# concurrent sessions' windows overlap, but each session's requests only ever appear on its own port.
PROXY_PORT = {"gx": 8010, "gm": 8011}


def trial_config_arm(arm):
    cfg = v2.trial_config()                      # provider/model/mcp/permissions/policies
    cfg["providers"]["splash"]["settings"]["baseURL"] = PROXY_URL[arm]
    return cfg


def run_trial_arm(task, arm, sess_root, GROUND_RULES_by_arm, B_by_arm):
    name = f"{task}_{arm}"
    cwd = sess_root / name
    cwd.mkdir(parents=True, exist_ok=True)
    full = B_by_arm[arm][task] + "\n\n" + GROUND_RULES_by_arm[arm]
    (cwd / "BRIEF_AS_SENT.md").write_text(full)
    (cwd / "AGENTS.md").write_text(v2.trial_agents())
    (cwd / "opencode.json").write_text(json.dumps(trial_config_arm(arm), indent=1))
    env = dict(__import__("os").environ)
    env["OPENCODE_CONFIG"] = str((cwd / "opencode.json").resolve())
    cmd = ["opencode", "run", "--standalone", "--format", "json", full]
    t0 = time.time()
    import subprocess
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                           text=True, timeout=2400)
    except Exception as e:
        return {"task": task, "arm": arm, "error": str(e)[:200],
                "wall_s": round(time.time() - t0, 1)}
    t1 = time.time()
    rec = {"task": task, "arm": arm, "effort": ARMS[arm], "baseURL": PROXY_URL[arm],
           "ok": p.returncode == 0, "wall_s": round(t1 - t0, 1),
           "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000)}
    ev = v2.parse_events(p.stdout)
    # seal audit on REAL tool names: errored tools are logged as (name, "error") tuples, and
    # the builtin server's tool arrives WITHOUT a server prefix in 2.3.0 events (only bare
    # name seen across all 16f waves: resolve_control). 16f's seal_leaks field contained
    # false positives for exactly these two shapes; the manual event-stream audit stands.
    allowed = tuple(f"{n}_" for n in v2.KEEP) + ("resolve_control",)  # resolve_control: builtin trio
    def tool_name(t):
        return str(t[0]) if isinstance(t, tuple) else str(t)
    leaks = [str(t) for t in ev["tool_uses"] if not tool_name(t).startswith(allowed)]
    rec["seal_leaks"] = leaks
    if leaks:
        print(f"  !! SEAL LEAK in {name}: {leaks}", flush=True)
    rec.update({"result": ("\n".join(ev["texts"]))[:4000] or p.stderr[:2000],
                "num_turns": ev["steps"], "tool_use_count": len(ev["tool_uses"]),
                "tools": ev["tool_uses"], "session_id": ev["session"],
                "cost_usd": ev["cost"], "usage": ev["tokens"]})
    (cwd / "result.json").write_text(json.dumps(rec, indent=1))
    (cwd / "events.json").write_text(p.stdout)
    return rec


def correlate_audit(results):
    """Prove the arm split per PORT: each session's requests appear only on its own proxy
    port (concurrency makes time windows alone ambiguous, ports are not)."""
    if not AUDIT.exists():
        return {}
    lines = [json.loads(l) for l in AUDIT.open() if l.strip()]
    chats = [l for l in lines if l.get("path", "").startswith("/v1/chat/completions")]
    out = {}
    for r in results:
        arm = r["arm"]
        port, other = PROXY_PORT[arm], PROXY_PORT["gm" if arm == "gx" else "gx"]
        win = [c for c in chats if c.get("port") == port
               and r.get("start_ms", 0) <= c.get("ms", -1) <= r.get("end_ms", 0)]
        other_win = [c for c in chats if c.get("port") == other
                     and r.get("start_ms", 0) <= c.get("ms", -1) <= r.get("end_ms", 0)]
        inj = sum(1 for c in win if c.get("effort_injected") == "medium")
        native = sum(1 for c in win if c.get("effort_in_body"))
        out[f"{r['task']}_{arm}"] = {
            "arm": arm, "port": port,
            "requests_on_own_port": len(win),
            "effort_injected_medium": inj, "effort_native": native,
            "other_port_requests_in_window": len(other_win),  # belongs to the paired arm
            "expected": len(win) > 0 and inj == (len(win) if arm == "gm" else 0)}
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", default=None,
                    help="run ONE brief-trial in both arms, e.g. --smoke T1r1, then stop")
    ap.add_argument("--skip", default="", help="comma list of TASK to skip (already done)")
    ap.add_argument("--out", default=str(OUT), help="wave output dir (smoke runs go elsewhere)")
    a = ap.parse_args()

    v2.seal_host_hygiene()
    out = pathlib.Path(a.out)
    sess = out / "sessions"
    sess.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        for k in (1, 2, 3):
            pathlib.Path(ARM_RENDER[arm], f"T7r{k}").mkdir(parents=True, exist_ok=True)
    (out / "archived_briefs.md").write_text(json.dumps({
        "arms": {arm: {"tl_base": ARM_TL[arm], "render_root": ARM_RENDER[arm],
                       "baseURL": PROXY_URL[arm], "effort": ARMS[arm]} for arm in ARMS},
        "frames": {"base_src": v2.BASE_SRC, "insert_src": v2.INS_SRC, "insert_frames": v2.INS_F,
                   "probe_src": v2.PROB_SRC, "probe_frames": v2.PROB_F, "slip_src": v2.SLIP_SRC},
    }, indent=1))
    harness0 = v2.harness_preflight(out)
    B_by_arm = {arm: v2.briefs(ARM_TL[arm], ARM_RENDER[arm]) for arm in ARMS}
    GROUND_by_arm = {arm: v2.ground_rules(ARM_TL[arm]) for arm in ARMS}

    hidden = pathlib.Path(str(v2.GLOBAL_AGENTS) + ".bench-hidden")
    if v2.GLOBAL_AGENTS.exists():
        v2.GLOBAL_AGENTS.rename(hidden)
    elif hidden.exists():
        print("!! global AGENTS.md already renamed away by an earlier aborted run; "
              "leaving it hidden for this wave", flush=True)
    skip = set(x for x in a.skip.split(",") if x)
    try:
        drift = []
        if a.smoke:
            pairs = [(a.smoke,)]
            solo = []
        else:
            pairs = [("T1r1",), ("T1r2",), ("T1r3",), ("T2r1",), ("T2r2",), ("T2r3",),
                     ("T3r1",), ("T3r2",), ("T3r3",), ("F1r1",), ("F1r2",), ("F1r3",),
                     ("T7r1",), ("T7r2",), ("T7r3",), ("T8r1",), ("T8r2",), ("T8r3",),
                     ("F2r1",), ("F2r2",)]
            solo = ["F2r3"]
        results = []
        for (task,) in pairs:
            if task in skip:
                continue
            print(f"[{time.strftime('%H:%M:%S')}] {task} both arms concurrently", flush=True)
            ver_now = v2.harness_state()
            with open(out / "harness_log.jsonl", "a") as f:
                f.write(json.dumps({"task": task, "opencode": ver_now,
                                    "ts": time.strftime("%H:%M:%S")}) + "\n")
            if ver_now != harness0 and not any(d.get("to") == ver_now for d in drift):
                drift.append({"task": task, "from": harness0, "to": ver_now})
                print(f"  !! HARNESS DRIFT: {harness0} -> {ver_now} at {task}.", flush=True)
            outmap = {}
            def go(arm):
                try:
                    outmap[arm] = run_trial_arm(task, arm, sess, GROUND_by_arm, B_by_arm)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    outmap[arm] = {"task": task, "arm": arm, "error": repr(e)[:300]}
            ta = threading.Thread(target=go, args=("gx",))
            tb = threading.Thread(target=go, args=("gm",))
            ta.start(); tb.start(); ta.join(); tb.join()
            for arm in ("gx", "gm"):
                r = outmap[arm]
                results.append(r)
                u = r.get("usage", {})
                with open(out / "wave_summary.jsonl", "a") as f:
                    f.write(json.dumps({"task": task, "arm": r["arm"], "ok": r.get("ok"),
                            "turns": r.get("num_turns"), "tools": r.get("tool_use_count"),
                            "wall_s": r.get("wall_s"),
                            "reasoning_tok": u.get("reasoning"), "output_tok": u.get("output"),
                            "cost_usd": r.get("cost_usd")}) + "\n")
            time.sleep(15)
        for task in solo:
            if task in skip:
                continue
            print(f"[{time.strftime('%H:%M:%S')}] solo {task} both arms", flush=True)
            for arm in ("gx", "gm"):
                r = run_trial_arm(task, arm, sess, GROUND_by_arm, B_by_arm)
                results.append(r)
                u = r.get("usage", {})
                with open(out / "wave_summary.jsonl", "a") as f:
                    f.write(json.dumps({"task": task, "arm": r["arm"], "ok": r.get("ok"),
                            "turns": r.get("num_turns"), "tools": r.get("tool_use_count"),
                            "wall_s": r.get("wall_s"),
                            "reasoning_tok": u.get("reasoning"), "output_tok": u.get("output"),
                            "cost_usd": r.get("cost_usd")}) + "\n")

        audit_map = correlate_audit(results)
        unproven = [k for k, v in audit_map.items() if not v["expected"]]
        (out / "audit_by_session.json").write_text(json.dumps(audit_map, indent=1))
        (out / "wave_results.json").write_text(json.dumps({
            "trials": results, "harness_start": harness0, "harness": "opencode",
            "harness_drift": drift,
            "task_set": {"hard": ["T3", "T7", "T8", "F1", "F2"], "smoke": ["T1", "T2"]},
            "arms": {arm: {"tl_base": ARM_TL[arm], "render_root": ARM_RENDER[arm],
                           "baseURL": PROXY_URL[arm], "effort": ARMS[arm]} for arm in ARMS},
            "audit_unproven_sessions": unproven}, indent=1))
        # per-arm views so the existing grader can run unchanged per arm
        for arm in ARMS:
            (out / f"wave_results_{arm}.json").write_text(json.dumps({
                "trials": [r for r in results if r["arm"] == arm],
                "harness_start": harness0, "harness": "opencode", "harness_drift": drift,
                "tl_base": ARM_TL[arm], "render_root": ARM_RENDER[arm]}, indent=1))
        print(f"WAVE DONE — {out} | arm split unproven sessions: {len(unproven)}", flush=True)
    finally:
        if hidden.exists():
            hidden.rename(v2.GLOBAL_AGENTS)
            print("global AGENTS.md restored", flush=True)


if __name__ == "__main__":
    main()
