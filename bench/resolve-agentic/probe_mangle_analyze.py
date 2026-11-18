#!/usr/bin/env python3
"""Tier 2 read-out — summarises probe_mangle_driver.py runs (results/probe-mangle-*/probe-summary.json).

The driver's own summary counts attempts; this adds the axes the decision actually turns on:
  - median attempts/trial and median wall time (means get wrecked by one wandering session,
    e.g. A_control__r2 = 50 tool calls / 249 s in the n=4 pass)
  - name-pattern breakdown per variant: does the rule (B) actually kill the separator error,
    or does it just move it? does the name list (C) get ADOPTED, or does the model still
    kebab the names it was handed verbatim (C_rule_names__r4 tried 'davinci-resolve:project_manager')?
  - brief completion per session (did it answer all 5 read-only questions) so a variant can't
    win by quitting early.

Usage: python3 probe_mangle_analyze.py --dir results/probe-mangle-2026-11-17h
"""
import argparse, collections, json, pathlib, re, statistics

GROUND = {  # probe project read-backs (from probe build log, _T1 state)
    "timelines": 4, "duration_frames": 442, "video_items": 2,
    "speed_pct": 100.0, "crop_left": 0.0,
}


def answer_axes(session_dir):
    """Crude but uniform completion check over the final text: did each brief item get a value?"""
    txt = []
    ev = pathlib.Path(session_dir) / "events.json"
    if not ev.exists():
        return {}
    for ln in ev.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if e.get("type") == "text":
            txt.append(e["part"].get("text", ""))
    t = "\n".join(txt).lower()
    return {
        "timeline_count": bool(re.search(r"\b4\b", t)),
        "duration": bool(re.search(r"442", t)),
        "items": bool(re.search(r"\b2\b", t)),
        "speed": bool(re.search(r"100", t)),
        "crop": bool(re.search(r"crop", t)),
        "comp": bool(re.search(r"comp", t)),
    }


def classify(name):
    n = name
    if re.search(r"\n|<parameter|</", n):
        return "structurally broken"
    if ":" in n:
        return "colon separator"
    if re.match(r"^davinci[-_]resolve[-_](builtin|advanced)[-_]", n):
        return "hyphen-joined builtin/advanced + action"
    if re.match(r"^davinci-resolve-[a-z_]+$", n):
        return "right shape, separator/missing action"
    return "other kebab"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    d = json.loads((pathlib.Path(a.dir) / "probe-summary.json").read_text())
    rows = {r["probe"]: r for r in d["sessions"]}
    per = d["per_trial"]
    variants = sorted({p.split("__")[0] for p in per})
    out = {}
    for v in variants:
        probes = [p for p in per if p.startswith(v + "__")]
        att = [per[p]["attempts"] for p in probes]
        wall = [rows[p]["wall_s"] for p in probes if p in rows]
        pat = collections.Counter()
        for p in probes:
            for n in per[p]["names"]:
                pat[classify(n)] += 1
        answered = {p: answer_axes(pathlib.Path(a.dir) / "sessions" / p) for p in probes}
        complete = [sum(answered[p].values()) for p in probes]
        never = [p for p in probes if per[p]["attempts"] and per[p]["recovery_calls"] is None]
        out[v] = {
            "n": len(probes),
            "attempts_total": sum(att),
            "attempts_median": statistics.median(att),
            "trials_with_attempts": sum(1 for x in att if x),
            "never_recovered": len(never),
            "wall_median_s": round(statistics.median(wall), 1) if wall else 0,
            "wall_mean_s": round(statistics.mean(wall), 1) if wall else 0,
            "brief_axes_answered_min": min(complete) if complete else 0,
            "name_patterns": dict(pat),
            "worst_names": collections.Counter(
                n for p in probes for n in per[p]["names"]).most_common(5),
        }
        print(f"\n== {v} (n={len(probes)}) ==")
        for k in ("attempts_total", "attempts_median", "trials_with_attempts",
                  "never_recovered", "wall_median_s", "wall_mean_s", "brief_axes_answered_min"):
            print(f"  {k:26} {out[v][k]}")
        print("  name patterns:", dict(pat))
        print("  top wrong names:", out[v]["worst_names"])
    out["ground_values_used"] = GROUND
    out["caveat"] = d.get("caveat", "") + "; probe on read-only briefs: sizing, not a published effect"
    (pathlib.Path(a.dir) / "probe-analysis.json").write_text(json.dumps(out, indent=1))
    print("\nwrote", pathlib.Path(a.dir) / "probe-analysis.json")


if __name__ == "__main__":
    main()
