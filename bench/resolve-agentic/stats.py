#!/usr/bin/env python3
"""Wave statistics for the Resolve agentic benchmark: intervals, spreads, detection power.

Purpose (method change #1, borrowed from DeepSWE/Terminal-Bench practice): the published
record states pass counts ("18/18") and per-task median walls, which invites reading noise as
signal. This script re-derives every wave from its per-trial records and reports

  * per task per wave: n, passes, median/min/max wall, spread (max/min - 1)
  * per wave: pass rate with a Wilson score interval (95%), total wall, turns, cost
  * across waves: same, aggregated
  * detection power: P(a wave shows >=1 failure) for a given true per-trial pass rate,
    i.e. how big a regression this design can actually see

Hygiene: only whitelisted scalar keys are read, and no free-text field (grader notes, agent
reports, probe payloads) is ever printed or written. Those contain real media paths and
timeline names.

Wilson score interval (Wilson 1927), the standard binomial interval that behaves at p_hat=1:
  centre = (p_hat + z^2/2n) / (1 + z^2/n), half = z*sqrt(p_hat(1-p_hat)/n + z^2/4n^2) / (1 + z^2/n)
with z = 1.96 for 95%.

Usage:  python3 -I stats.py [--root .] [--json stats.json] [--task T7]
"""
import argparse
import json
import math
import os
import statistics
import sys
from collections import defaultdict

Z95 = 1.959963985

# trial-level fields we are willing to look at, across the shapes the waves have used
WALL_KEYS = ("wall_s", "wall", "duration_ms")
OK_KEYS = ("ok", "verified", "outcome_verified", "pass")
HONEST_KEYS = ("honest", "honest_no_contradiction")
TURNS_KEYS = ("num_turns", "turns", "tool_uses", "uses")
COST_KEYS = ("cost_usd", "cost")


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pick(d, keys):
    for k in keys:
        if k in d:
            return d[k]
    return None


def _task_id(raw):
    """'T1_r2' / 'r2-T1' / 'T7r3' -> ('T7', 3)."""
    s = str(raw)
    tpart, rpart = None, None
    i = s.find("T")
    if i >= 0:
        j = i + 1
        while j < len(s) and s[j].isdigit():
            j += 1
        tpart = s[i:j]
    for chunk in s.replace("-", " ").replace("_", " ").split():
        if chunk and chunk[0] in "rR" and chunk[1:].isdigit():
            rpart = int(chunk[1:])
        elif chunk.startswith(tpart or "\u0000") and chunk[len(tpart):].isdigit():
            rpart = int(chunk[len(tpart):])
    return tpart or s, rpart


def norm_trial(wave, raw_key, rec):
    task, rep = _task_id(raw_key)
    wall = _pick(rec, WALL_KEYS)
    if wall is None:
        wall = _num(_pick(rec, ("duration_ms",)))
        if wall is not None:
            wall = wall / 1000.0
    ok = _pick(rec, OK_KEYS)
    honest = _pick(rec, HONEST_KEYS)
    return {
        "wave": wave,
        "task": task,
        "rep": rep,
        "wall_s": _num(wall),
        "ok": (None if ok is None else bool(ok)),
        "honest": (None if honest is None else bool(honest)),
        "turns": _num(_pick(rec, TURNS_KEYS)),
        "cost_usd": _num(_pick(rec, COST_KEYS)),
    }


def load_published(path):
    wave = os.path.basename(path)[len("results-"):-len(".json")]
    data = json.load(open(path))
    out = []
    tr = data.get("trials")
    if isinstance(tr, dict):
        for k, v in tr.items():
            if isinstance(v, dict):
                out.append(norm_trial(wave, k, v))
    elif isinstance(tr, list):
        for v in tr:
            if isinstance(v, dict):
                out.append(norm_trial(wave, v.get("trial") or v.get("task"), v))
    return out, {"wave": wave, "source": os.path.basename(path), "kind": "published"}


# local working dirs are untracked (transcripts hold media paths); these are the only ones the
# published record refers to, mapped to their published wave label. None = ran locally, never
# published (kept as a labelled supplementary wave so its numbers still get statistics).
WAVE_ALIASES = {
    "2026-11-13-wave": "2026-11-13i",
    "2026-11-13-528-wave": "2026-11-13-528 (local-only wave, never published)",
    "2026-11-14-5210-wave": "2026-11-14",
    "2026-11-14-5211-wave": "2026-11-14l",
    "probe-flag-2026-11-13": None,   # not an agent wave
}


def load_wave_dir(path):
    name = os.path.basename(path.rstrip("/"))
    label = WAVE_ALIASES.get(name, name)
    if label is None:
        return [], {"wave": name, "source": name, "kind": "local", "note": "excluded (not an agent wave)"}
    for cand in ("wave_summary.jsonl", "wave_results.json"):
        p = os.path.join(path, cand)
        if not os.path.exists(p):
            continue
        out = []
        if cand.endswith(".jsonl"):
            for line in open(p):
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    out.append(norm_trial(label, rec.get("task"), rec))
        else:
            for v in json.load(open(p)).get("trials", []):
                out.append(norm_trial(label, v.get("task"), v))
        return out, {"wave": label, "source": f"{name}/{cand}", "kind": "local"}
    return [], {"wave": label, "source": name, "kind": "local", "note": "no per-trial file"}


def wilson(k, n, z=Z95):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def power(n, p):
    """P(at least one failure observed in n trials | true per-trial pass rate p)."""
    return 1 - p ** n


def fmt_pct(x):
    return "—" if x is None else f"{100 * x:.1f}%"


def report(records, coverage, only_task=None):
    if only_task:
        records = [r for r in records if r["task"] == only_task]
    waves, seen = [], set()
    for c in coverage:
        if c["wave"] in seen or not any(r["wave"] == c["wave"] for r in records):
            continue
        if c.get("note"):          # superseded / excluded entries are listed in coverage only
            continue
        seen.add(c["wave"])
        waves.append(c["wave"])

    print("per task per wave (n / passes / median s / min-max / spread)")
    hdr = f"{'wave':26s} " + " ".join(f"{t:>22s}" for t in sorted({r['task'] for r in records}))
    print(hdr)
    for w in waves:
        cells = []
        for t in sorted({r["task"] for r in records}):
            rs = [r for r in records if r["wave"] == w and r["task"] == t]
            if not rs:
                cells.append(f"{'-':>22s}")
                continue
            walls = [r["wall_s"] for r in rs if r["wall_s"] is not None]
            passes = sum(1 for r in rs if r["ok"])
            spread = (max(walls) / min(walls) - 1) if len(walls) > 1 else 0.0
            med = statistics.median(walls) if walls else 0.0
            cells.append(f"{len(rs)}p/{passes} {med:6.1f}s {min(walls):5.0f}-{max(walls):5.0f} {100*spread:4.0f}%".rjust(22))
        print(f"{w:26s} " + " ".join(cells))

    print("\nper wave")
    print(f"{'wave':26s} {'trials':>6s} {'pass':>5s} {'rate':>7s} {'Wilson 95%':>16s} {'honest':>7s} {'total wall':>11s} {'cost $':>7s}")
    for w in waves:
        rs = [r for r in records if r["wave"] == w]
        known = [r for r in rs if r["ok"] is not None]
        k = sum(1 for r in known if r["ok"])
        lo, hi = wilson(k, len(known))
        hknown = [r for r in rs if r["honest"] is not None]
        honest = f"{sum(1 for r in hknown if r['honest'])}/{len(hknown)}" if hknown else "n/a"
        wall = sum(r["wall_s"] or 0 for r in rs)
        cost = sum(r["cost_usd"] or 0 for r in rs)
        print(f"{w:26s} {len(rs):6d} {k:5d} {fmt_pct(k/len(known) if known else None):>7s} "
              f"{f'[{100*lo:.1f}, {100*hi:.1f}]':>16s} {honest:>7s} {wall:10.0f}s {cost:7.2f}")

    known = [r for r in records if r["ok"] is not None]
    k = sum(1 for r in known if r["ok"])
    lo, hi = wilson(k, len(known))
    print(f"\naggregate: {k}/{len(known)} verified; Wilson 95% [{100*lo:.1f}, {100*hi:.1f}]")
    n18 = [r for r in records if r["ok"] is not None]
    per_wave = max(len([r for r in records if r["wave"] == w and r["ok"] is not None]) for w in waves) if waves else 0
    print(f"largest wave n = {per_wave} trials; consecutive clean waves: "
          f"{sum(1 for w in waves if all(r['ok'] for r in records if r['wave'] == w and r['ok'] is not None))}/{len(waves)}")

    print("\ndetection power of one wave (probability it shows >=1 failure), by true per-trial pass rate")
    for p in (0.99, 0.95, 0.90, 0.85, 0.80):
        row = " ".join(f"n={n}: {power(n, p)*100:5.1f}%" for n in (per_wave or 18, 2 * (per_wave or 18), 54))
        print(f"  true {p:.2f} -> {row}")
    print("  (so a 10-point regression is visible with ~85% probability in one 18-trial wave, "
          "~96% across two; a 5-point regression is a coin flip)")

    walls = defaultdict(list)
    for r in records:
        if r["wall_s"] is not None:
            walls[r["task"]].append(r["wall_s"])
    print("\nper-task wall spread across all waves (the reason single-median deltas are not findings)")
    for t in sorted(walls):
        v = walls[t]
        if len(v) > 1:
            print(f"  {t:4s} n={len(v):3d} median {statistics.median(v):6.1f}s  min {min(v):5.1f}  max {max(v):6.1f}  spread {100*(max(v)/min(v)-1):5.0f}%")

    print("\ncoverage")
    for c in coverage:
        n = sum(1 for r in records if r["wave"] == c["wave"])
        note = f"  [{c['note']}]" if c.get("note") else ""
        print(f"  {c['wave']:26s} {c['kind']:8s} {c['source']:44s} trials={n}{note}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--json", help="also write the normalized records as JSON (scalar fields only)")
    ap.add_argument("--task", help="restrict to one task id, e.g. T7")
    ap.add_argument("--include-local", action="store_true",
                    help="also read results/<wave>/ local dirs (untracked; numbers only)")
    args = ap.parse_args()

    records, coverage = [], []
    for p in sorted(_glob(os.path.join(args.root, "results-*.json"))):
        recs, cov = load_published(p)
        if recs:
            records += recs
            coverage.append(cov)
    if args.include_local:
        d = os.path.join(args.root, "results")
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            sub = os.path.join(d, name)
            if os.path.isdir(sub):
                recs, cov = load_wave_dir(sub)
                if cov["wave"] in {c["wave"] for c in coverage}:
                    coverage.append({**cov, "note": "superseded by the published record"})
                    continue
                if recs:
                    records += recs
                    coverage.append(cov)
    if not records:
        sys.exit("no per-trial records found")
    report(records, coverage, args.task)
    if args.json:
        json.dump(records, open(args.json, "w"), indent=1)
        print(f"\nwrote {args.json} ({len(records)} records, scalar fields only)")


def _glob(pat):
    import glob as g
    return g.glob(pat)


if __name__ == "__main__":
    main()
