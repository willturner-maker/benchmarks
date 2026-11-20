#!/usr/bin/env python3
"""Backfill re-derivable per-trial scalars into published wave records.

Why this exists: `stats.py --check` is the publication gate — a record that ships only a scorecard
string ("21/21") cannot be re-derived, cannot feed intervals/spreads/detection power, and cannot be
audited later. Six records predate per-trial shipping. The raw evidence survived in the local wave
dirs (`wave_summary.jsonl` = driver scalars, `grading*.json` = grader verdicts), so the gap is
mechanical to close — the same fix that was applied by hand to 2026-11-14l, now written down.

Copy discipline (the reason this is a script rather than a REPL session):
  * Scalars only. `verdicts[task]["notes"]` / `["why"]`, claim `_quote`s, snapshot payloads and any
    other free text are never copied — DENY_KEYS below names them and `deny_clean()` refuses to
    write if one reaches a row.
  * `verified` comes from the GRADER, never from the driver's `ok` (which only means the session
    finished). Proof they differ: 2026-11-16b T3r2 is driver-ok=true, verified=false.
  * `unmeasurable` verdicts are kept as explicit `verified: null` rows, because silently dropping
    them is how a 16/18 denominator becomes an invisible 16/21.
  * Each backfill must reproduce the scorecard the record ALREADY publishes (EXPECTED below). A
    mismatch prints and skips the file rather than writing a disagreeing record.

Usage:
  python3 backfill_trials.py            # dry run
  python3 backfill_trials.py --write    # write
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(ROOT, "results")
BACKFILLED_AT = "2026-11-19"

DENY_KEYS = {"result", "report", "reported", "note", "notes", "why", "grader_readback", "transcript",
             "output", "stdout", "_meta", "_quote", "names", "intended_map", "target_timeline_seen",
             "snapshot", "post_row4", "grading_basis", "claims_basis", "post_wave_census_vs_sealed",
             "placement_problems", "f3_headline", "f3_outcome_split", "canaries", "census_vs_sealed",
             "cross_project_placements", "single_project", "project", "sealed_gt_sha256", "outcome"}
SCALARS = ("turns", "tools", "wall_s", "cost_usd", "reasoning_tok", "output_tok")


def jload(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def jsonl(p):
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def verdict(v):
    """-> (verified, extra). Two grader shapes across waves:
         {"pass": ["r1"]} / {"fail": [...]}            (16f, 17g, 17h)
         {"pass": true, "class": ...}                  (tier4)
       plus {"unmeasurable": true, ...} for verdicts the read-back could not support."""
    if not isinstance(v, dict):
        return None, {"unmeasurable": True}
    if v.get("unmeasurable"):
        return None, {"unmeasurable": True}
    if "fail" in v:
        return False, {}
    p = v.get("pass")
    if isinstance(p, bool):
        extra = {"f3_class": v["class"]} if v.get("class") else {}
        return p, extra
    if isinstance(p, list):
        return (len(p) > 0), {}
    return None, {"unmeasurable": True}


def merge(task, drv, verified, extra=None):
    row = {"trial": task}
    if verified is None:
        row["verified"] = None
    else:
        row["verified"] = verified
    for k in SCALARS:
        if drv.get(k) is not None:
            row[k] = drv[k]
    if extra:
        row.update(extra)
    return row


def single_graded(wave_dir, grading="grading.json"):
    d = os.path.join(RESULTS, wave_dir)
    g = jload(os.path.join(d, grading))
    drv = {r["task"]: r for r in jsonl(os.path.join(d, "wave_summary.jsonl"))}
    rows, skipped = [], []
    for task, v in sorted(g["verdicts"].items()):
        if task not in drv:
            skipped.append(task)          # aggregate verdict (e.g. tier "T8"), not a trial
            continue
        verified, extra = verdict(v)
        rows.append(merge(task, drv[task], verified, extra))
    src = f"results/{wave_dir}/wave_summary.jsonl + {grading}:verdicts"
    return rows, src, {"graded_trials": len(rows), "verified": sum(1 for r in rows if r["verified"] is True),
                       "unmeasurable": sum(1 for r in rows if r["verified"] is None),
                       "aggregate_verdicts_skipped": skipped}


def build_17g():
    """Dual-arm A/B: same 21 sessions under two reasoning efforts. Trial ids carry the arm, and the
    3 `unmeasurable` T8 rows per arm are kept so the published 16/18 denominator is reconstructable."""
    d = os.path.join(RESULTS, "2026-11-17g-effort-ab-wave")
    drv = {(r["task"], r["arm"]): r for r in jsonl(os.path.join(d, "wave_summary.jsonl"))}
    rows, stats = [], {}
    for arm in ("gm", "gx"):
        g = jload(os.path.join(d, f"grading_{arm}.json"))
        ver = unm = 0
        for task, v in sorted(g["verdicts"].items()):
            verified, extra = verdict(v)
            extra = dict(extra, arm=arm)
            rows.append(merge(f"{arm}/{task}", drv[(task, arm)], verified, extra))
            if verified is True:
                ver += 1
            elif verified is None:
                unm += 1
        stats[arm] = {"verified": ver, "unmeasurable": unm, "graded": len(g["verdicts"]) - unm}
    src = "results/2026-11-17g-effort-ab-wave/wave_summary.jsonl + grading_gm.json + grading_gx.json"
    return rows, src, stats


def build_17h():
    """The 17h record publishes two passes (20/21 then 21/21 after the retry), so both wave dirs
    back one record; rows carry `pass` so the pair is not pooled into 41 trials."""
    rows, srcs, stats = [], [], {}
    for wave, tag in (("baseline-2026-11-17h", "pass1"), ("baseline-2026-11-17h2", "pass2")):
        r, s, st = single_graded(wave)
        for row in r:
            row["pass"] = tag
        rows += r
        srcs.append(s)
        stats[tag] = {"verified": st["verified"], "graded": st["graded_trials"]}
    return rows, " + ".join(srcs), stats


def build_probe():
    """Not an agent wave: read-only mangle-name probe, no ground truth, no grader. Its own summary
    calls the failure mode `never_recovered`, so the per-trial scalar is `recovered` (did the
    intended MCP call eventually land), and the record says what the scalar means."""
    d = os.path.join(RESULTS, "probe-mangle-2026-11-17h")
    p = jload(os.path.join(d, "probe-summary.json"))
    rows = []
    for tid, r in sorted(p["per_trial"].items()):
        attempts = r.get("attempts", 0)
        rows.append({"trial": tid, "attempts": attempts,
                     "distinct_names": r.get("distinct_names"),
                     "recovery_calls": r.get("recovery_calls"),
                     "wasted_ms": r.get("wasted_ms"),
                     "recovered": (attempts == 0) or (r.get("recovery_calls") is not None)})
    stats = {v: p["summary"][v]["never_recovered"] for v in p["summary"]}
    return rows, f"results/{os.path.basename(d)}/probe-summary.json:per_trial", stats


def build_tier4(wave):
    rows, src, stats = single_graded(wave)
    return rows, src, stats


# (published record, builder, expectation derived from that record's own published scorecard)
JOBS = (
    ("results-2026-11-16f.json", lambda: single_graded("2026-11-16f-opencode-f1f2-wave"),
     lambda s, rec: s["verified"] == 21 and s["graded_trials"] == 21),
    ("results-2026-11-17g.json", build_17g,
     lambda s, rec: all(v["verified"] == 16 and v["graded"] == 18 for v in s.values())),
    ("results-baseline-2026-11-17h.json", build_17h,
     lambda s, rec: s["pass1"] == {"verified": 20, "graded": 21} and s["pass2"] == {"verified": 21, "graded": 21}),
    ("results-tier4-2026-11-18l.json", lambda: build_tier4("tier4-2026-11-18l"),
     lambda s, rec: s["verified"] == 8 and s["graded_trials"] == 8
     and rec["headline_f3_outcome_split"]["destroyed_then_repaired"] == 6),
    ("results-tier4-2026-11-18m.json", lambda: build_tier4("tier4-2026-11-18m"),
     lambda s, rec: s["verified"] == 8 and s["graded_trials"] == 8),
    ("results-probe-mangle-2026-11-17h.json", build_probe,
     lambda s, rec: all(v == 0 for v in s.values()) and len(s) == 3),
)

PROVENANCE = {
    "rule": ("per-trial scalars copied from the wave's driver log; `verified` is the grader verdict, "
             "never the driver ok flag; unmeasurable verdicts are kept as explicit nulls; grader "
             "notes/why and claim quotes are not copied"),
    "not_backfilled": ("`honest` (claim-vs-read-back agreement) is not derivable from the archived "
                       "grading JSON without re-reading transcripts, so it stays only where the wave "
                       "published it at the time"),
}


def deny_clean(rows):
    bad = sorted({k for r in rows for k in r if k in DENY_KEYS})
    if bad:
        sys.exit(f"refusing to write: denied keys reached the rows: {bad}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    failures = 0
    for name, builder, expect in JOBS:
        path = os.path.join(ROOT, name)
        rows, src, stats = builder()
        deny_clean(rows)
        rec = jload(path)
        ok = expect(stats, rec)
        print(f"== {name}")
        print(f"   rows {len(rows)}  stats {json.dumps(stats)}")
        print(f"   reproduces the record's own scorecard: {'OK' if ok else 'MISMATCH'}")
        if not ok:
            failures += 1
            print("   NOT WRITTEN — reconcile grader output against the published scorecard by hand.")
            continue
        if args.write:
            rec["trials"] = rows
            rec["trials_backfill"] = dict(PROVENANCE, backfilled_at=BACKFILLED_AT, source=src)
            if "probe" in name:
                rec["trials_backfill"]["per_trial_semantics"] = (
                    "no grader on this probe: `recovered` = the intended MCP call eventually landed "
                    "(attempts 0 means the first call was correct); `never_recovered` counts per "
                    "variant are in the `variants` block")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
            print(f"   wrote {len(rows)} trial rows")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
