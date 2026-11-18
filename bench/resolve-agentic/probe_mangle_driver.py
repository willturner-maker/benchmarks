#!/usr/bin/env python3
"""Tier 2 probe — does a one-line tool-naming rule remove MCP name-mangling?

Measured by mangle_analysis.py over the two 17h passes: 67 and 66 `No tool named …` attempts, in
10/21 and 14/21 trials, ~78% of them the SAME mistake — the separator between server and tool
(`davinci-resolve-timeline` for `davinci-resolve_timeline`) or folding the action into the tool
name (`davinci-resolve-timeline-list`, when the surface is one `davinci-resolve_timeline` tool that
takes an `action` parameter). The harness answer gives no suggestion ("Please use a tool from the
available tool list"), so a wrong guess is cheap and unguided. One trial (pass 1 T2r1) never
recovered and failed the task outright. OpenCode has no name-alias config hook, so the fix
candidates are prompt-side. This probe measures them.

PROBE, NOT A WAVE: read-only briefs on a scratch probe project, no grading, no ground truth, and
the operator session shares the engine throughout. Variants are interleaved so ordering cannot
favour one.

  A  control — the trial AGENTS.md exactly as every published wave ships it (no naming guidance)
  B  rule only — + the naming convention sentence
  C  rule + names — + the exact tool names this brief needs

Usage: python3 probe_mangle_driver.py --reps 4 --out results/probe-mangle-2026-11-17h
"""
import argparse, json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wave_driver_f1f2_opencode_v2 as v2          # noqa: E402
from mangle_analysis import scan_wave              # noqa: E402

PROJ = "_mcp_17i_nameprobe"
TL = f"{PROJ}_T1"

RULE = ("MCP tool names are <server>_<tool> with EXACTLY ONE underscore: the server name "
        "verbatim (it may contain hyphens, e.g. davinci-resolve-builtin), then one underscore, "
        "then the snake_case tool name. The action is a PARAMETER (action=…), never part of the "
        "tool name. If a call answers \"No tool named …\", do NOT invent another spelling: "
        "re-read the available tool list and use a name from it.")
NAMES = ("Names you will need here: davinci-resolve_project_manager, davinci-resolve_timeline, "
         "davinci-resolve_timeline_item, davinci-resolve_timeline_item_color, "
         "davinci-resolve_timeline_item_fusion.")

VARIANTS = {
    "A_control": v2.trial_agents(),
    "B_rule": v2.trial_agents() + "\n" + RULE + "\n",
    "C_rule_names": v2.trial_agents() + "\n" + RULE + "\n" + NAMES + "\n",
}

BRIEF = (f"Project {PROJ} holds timeline {TL}. Report, as values only: (1) how many timelines the "
         f"project has; (2) {TL}'s duration in frames and its number of video items; (3) the first "
         "video item's speed percentage and its CropLeft; (4) the color node tools on that item; "
         "(5) whether a Fusion comp is attached to it. Read-only: change nothing, create nothing.")


def run_probe(variant, rep, out):
    name = f"{variant}__r{rep}"
    cwd = out / "sessions" / name
    cwd.mkdir(parents=True, exist_ok=True)
    (cwd / "AGENTS.md").write_text(VARIANTS[variant])
    (cwd / "opencode.json").write_text(json.dumps(v2.trial_config(), indent=1))
    (cwd / "BRIEF_AS_SENT.md").write_text(BRIEF)
    env = dict(os.environ)
    env["OPENCODE_CONFIG"] = str((cwd / "opencode.json").resolve())
    t0 = time.time()
    p = subprocess.run(["opencode", "run", "--standalone", "--format", "json", BRIEF],
                       cwd=str(cwd), env=env, capture_output=True, text=True, timeout=900)
    t1 = time.time()
    (cwd / "events.json").write_text(p.stdout)
    return {"probe": name, "variant": variant, "rep": rep, "ok": p.returncode == 0,
            "wall_s": round(t1 - t0, 1), "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--start-rep", type=int, default=1,
                    help="first rep number (extend an existing probe without clobbering earlier reps; "
                         "the summary always re-scans the whole out dir, so it covers every rep)")
    ap.add_argument("--out", default=str(HERE / "results" / "probe-mangle-2026-11-17h"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    (out / "sessions").mkdir(parents=True, exist_ok=True)
    v2.seal_host_hygiene()
    # interleave variants across reps so a warm/cold engine cannot favour one arm
    order = [(v, r) for r in range(a.start_rep, a.start_rep + a.reps) for v in VARIANTS]
    hidden = pathlib.Path(str(v2.GLOBAL_AGENTS) + ".bench-hidden")
    if v2.GLOBAL_AGENTS.exists():
        v2.GLOBAL_AGENTS.rename(hidden)
    rows = []
    try:
        for variant, rep in order:
            print(f"[{time.strftime('%H:%M:%S')}] {variant} r{rep}", flush=True)
            r = run_probe(variant, rep, out)
            rows.append(r)
            print("   ", json.dumps(r), flush=True)
            time.sleep(5)
    finally:
        if hidden.exists() and not v2.GLOBAL_AGENTS.exists():
            hidden.rename(v2.GLOBAL_AGENTS)
            print("global AGENTS.md restored", flush=True)

    per, tot, _shapes = scan_wave(out)
    by = {}
    for probe, rec in per.items():
        variant = probe.split("__")[0]
        d = by.setdefault(variant, {"attempts": 0, "trials": 0, "trials_with_attempts": 0,
                                    "never_recovered": 0, "wasted_ms": 0, "wall_s": []})
        d["attempts"] += rec["attempts"]
        d["trials"] += 1
        d["trials_with_attempts"] += 1 if rec["attempts"] else 0
        d["never_recovered"] += 1 if (rec["attempts"] and rec["recovery_calls"] is None) else 0
        d["wasted_ms"] += rec["wasted_ms"]
    for r in rows:
        by[r["variant"]]["wall_s"].append(r["wall_s"])
    summary = {}
    for v in VARIANTS:
        d = by.get(v, {"attempts": 0, "trials": 0, "trials_with_attempts": 0,
                       "never_recovered": 0, "wasted_ms": 0, "wall_s": []})
        summary[v] = {"trials": d["trials"], "mangled_attempts_total": d["attempts"],
                      "trials_with_any_attempt": d["trials_with_attempts"],
                      "never_recovered": d["never_recovered"], "harness_ms_wasted": d["wasted_ms"],
                      "wall_s_mean": round(sum(d["wall_s"]) / len(d["wall_s"]), 1) if d["wall_s"] else 0,
                      "per_trial_attempts": sorted((rec["attempts"] for probe, rec in per.items()
                                                    if probe.startswith(v + "__")))}
        print(v, json.dumps(summary[v]))
    (out / "probe-summary.json").write_text(json.dumps({
        "probe": "tool-naming guidance (Tier 2)", "read_only": True, "project": PROJ,
        "brief": BRIEF, "variants": {k: VARIANTS[k] for k in VARIANTS},
        "sessions": rows, "per_trial": per, "summary": summary,
        "tenancy": "operator session shared the engine throughout; probe, not a wave",
        "caveat": f"n={len(per) // len(VARIANTS)} per variant in this out dir: sizing sample, not a "
                  "published effect; meant to decide whether a real wave adopts a variant"}, indent=1))
    print("wrote", out / "probe-summary.json")


if __name__ == "__main__":
    main()
