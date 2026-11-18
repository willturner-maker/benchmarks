#!/usr/bin/env python3
"""Tier 3 read-out — friction per arm for the two-arm 2026-11-18k wave.

The ONLY clean read is paired B-vs-A on the same stack (PLAN-tier3-2026-11-18k): pairs are
(r1,r4), (r2,r5), (r3,r6) per brief, dispatched back-to-back. Cross-wave reads (arm A vs 17h
pass 2) are confounded by the stack move + tenancy and are printed as context only.

Per brief reports: mangled attempts (mangle_analysis), tool uses, wall s, wasted harness ms —
each as A / B / paired delta; per-arm medians headline. The pass axis comes from grading.json
and is echoed secondary, never blended.

Usage: python3 tier3_friction_readout.py --wave results/tier3-2026-11-18k \
           --also results/baseline-2026-11-17h2   # context baseline (optional)
"""
import argparse, json, pathlib, statistics, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mangle_analysis import scan_wave    # noqa: E402

BRIEFS = ("T1", "T2", "T3", "F1", "T7", "T8", "F2")
PAIRS = (("r1", "r4"), ("r2", "r5"), ("r3", "r6"))


def arm(rep):
    return "B" if rep in ("r4", "r5", "r6") else "A"


def per_trial_metrics(wdir):
    mangle, _, _ = scan_wave(pathlib.Path(wdir))
    rows = {}
    summ = pathlib.Path(wdir) / "wave_summary.jsonl"
    for ln in summ.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        r = json.loads(ln)
        task = r["task"]
        rows[task] = {"brief": task[:-2], "rep": "r" + task[-1], "arm": arm("r" + task[-1]),
                      "tools": r.get("tools"), "wall_s": r.get("wall_s"), "ok": r.get("ok")}
    for task, m in mangle.items():
        if task in rows:
            rows[task]["mangled"] = m["attempts"]
            rows[task]["wasted_ms"] = m["wasted_ms"]
            rows[task]["recovery_calls"] = m["recovery_calls"]
    return rows


def med(vals):
    vals = [v for v in vals if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    ap.add_argument("--also", default="")
    a = ap.parse_args()
    rows = per_trial_metrics(a.wave)
    out = {"wave": a.wave, "briefs": {}, "arm_medians": {}, "pairs": {}}

    print(f"{'brief':5} {'pair':10} {'A man→B man':>14} {'A tools→B tools':>18} "
          f"{'A wall→B wall':>18} {'A ms→B ms':>14}")
    for b in BRIEFS:
        ptext = []
        for ra, rb in PAIRS:
            ta, tb = f"{b}{ra}", f"{b}{rb}"
            if ta not in rows or tb not in rows:
                continue
            x, y = rows[ta], rows[tb]
            print(f"{b:5} {(ra+rb):10} {str(x.get('mangled',0))+'→'+str(y.get('mangled',0)):>14} "
                  f"{str(x['tools'])+'→'+str(y['tools']):>18} "
                  f"{str(x['wall_s'])+'→'+str(y['wall_s']):>18} "
                  f"{str(x.get('wasted_ms',0))+'→'+str(y.get('wasted_ms',0)):>14}")
            ptext.append({"pair": f"{ra}/{rb}",
                          "delta_mangled": y.get("mangled", 0) - x.get("mangled", 0),
                          "delta_tools": (y["tools"] or 0) - (x["tools"] or 0),
                          "delta_wall": (y["wall_s"] or 0) - (x["wall_s"] or 0)})
        out["pairs"][b] = ptext
        A = [r for r in rows.values() if r["brief"] == b and r["arm"] == "A"]
        B = [r for r in rows.values() if r["brief"] == b and r["arm"] == "B"]
        out["briefs"][b] = {
            "A": {"mangled": med([r.get("mangled", 0) for r in A]),
                  "tools": med([r["tools"] for r in A]), "wall_s": med([r["wall_s"] for r in A]),
                  "wasted_ms": med([r.get("wasted_ms", 0) for r in A])},
            "B": {"mangled": med([r.get("mangled", 0) for r in B]),
                  "tools": med([r["tools"] for r in B]), "wall_s": med([r["wall_s"] for r in B]),
                  "wasted_ms": med([r.get("wasted_ms", 0) for r in B])}}
        print(f"{b:5} {'MEDIAN':10} "
              f"{str(out['briefs'][b]['A']['mangled'])+'→'+str(out['briefs'][b]['B']['mangled']):>14} "
              f"{str(out['briefs'][b]['A']['tools'])+'→'+str(out['briefs'][b]['B']['tools']):>18} "
              f"{str(out['briefs'][b]['A']['wall_s'])+'→'+str(out['briefs'][b]['B']['wall_s']):>18} "
              f"{str(out['briefs'][b]['A']['wasted_ms'])+'→'+str(out['briefs'][b]['B']['wasted_ms']):>14}")

    for name in ("A", "B"):
        sel = [r for r in rows.values() if r["arm"] == name]
        out["arm_medians"][name] = {"trials": len(sel),
                                    "mangled": med([r.get("mangled", 0) for r in sel]),
                                    "tools": med([r["tools"] for r in sel]),
                                    "wall_s": med([r["wall_s"] for r in sel]),
                                    "wasted_ms": med([r.get("wasted_ms", 0) for r in sel]),
                                    "trials_with_mangling": sum(1 for r in sel if r.get("mangled", 0))}
    print("\narm medians:", json.dumps(out["arm_medians"]))

    # ship/don't-ship test from the plan
    mA, mB = out["arm_medians"]["A"]["mangled"], out["arm_medians"]["B"]["mangled"]
    verdict = {"rule_effect_mangled_median": {"A": mA, "B": mB},
               "criterion_a_rule_not_worse": (mB is not None and mA is not None and mB <= mA)}
    grading = pathlib.Path(a.wave) / "grading.json"
    if grading.exists():
        g = json.load(open(grading))
        flips = [t for t, v in (g.get("trials", g.get("verdicts", {})) or {}).items()
                 if arm(str(t)[-2:]) == "B" and isinstance(v, dict) and not v.get("pass", True)]
        verdict["criterion_b_no_armB_only_flips_note"] = "see grading.json; arm-A flips listed for parity"
        verdict["armB_ungraded_pass"] = len(flips) == 0
    out["verdict"] = verdict
    print("verdict:", json.dumps(verdict))

    # context baseline (confounded — never the rule effect)
    if a.also:
        base = per_trial_metrics(a.also)
        out["context_17h2_medians"] = {
            "mangled": med([r.get("mangled", 0) for r in base.values()]),
            "tools": med([r["tools"] for r in base.values()]),
            "wall_s": med([r["wall_s"] for r in base.values()])}
        print("17h2 context (confounded):", out["context_17h2_medians"])
    (pathlib.Path(a.wave) / "friction-readout.json").write_text(json.dumps(out, indent=1))
    print("wrote", pathlib.Path(a.wave) / "friction-readout.json")


if __name__ == "__main__":
    main()
