#!/usr/bin/env python3
"""Token accounting for the Resolve agentic benchmark — the cost axis, never a correctness axis.

    python3 -I usage_stats.py results/<wave-dir> [--json out.json]
    python3 -I usage_stats.py --selftest

Why: `wall_s`, `turns` and `cost_usd` say a trial was expensive without saying *in what way*. Two
trials with the same wall and the same turn count can differ by an order of magnitude in how much
prompt the model re-read, and that is exactly the mechanism behind the tenancy/prompt-growth
findings in the results doc. The harness emits a `usage` block per trial
(`claude -p --output-format json`); this turns it into per-task token medians, a **cache-read share**,
and spreads — reported beside, and never instead of, outcome verification.

Rules this script enforces:
- Scalars only. `result.json` also holds the agent's verbatim report, which echoes real timeline and
  media paths; nothing here prints a string field, and the `--json` output is safe to paste into a
  wave record (which is itself untracked, per RUNBOOK §2).
- **Never score an absent field as zero.** A record with no `usage` key came from a driver that
  predates the token stage; `usage: null` means the harness stopped emitting it (a build change worth
  noticing); a null inside the block means that one counter is missing. All three are labelled, and
  the summary prints `n/a` rather than a number computed over a hole.
- Quote the spread or quote neither, so every median comes with min/max and a max/min ratio.
"""
import json
import pathlib
import sys

TOKEN_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
NOT_CAPTURED = "no usage key (driver predates the token stage)"
EMPTY_BLOCK = "usage block absent/null (harness did not emit it)"


def task_of(name):
    """T3r2 -> T3, F1r2 -> F1 (the F pair joins the scored set from the 2026-11-16 wave)."""
    n = name.lower()
    for i, ch in enumerate(n):
        if ch == "r" and i and n[:i].startswith(("t", "f")) and n[i + 1:].isdigit():
            return name[:i]
    return name


def read_trials(wave_dir):
    root = pathlib.Path(wave_dir)
    sessions = root / "sessions"
    files = sorted(sessions.glob("*/result.json")) if sessions.is_dir() else []
    if not files:                      # older layout: <wave>/<task>/result.json
        files = sorted(p for p in root.glob("*/result.json"))
    rows = []
    for f in files:
        try:
            rec = json.load(open(f))
        except Exception as e:
            rows.append({"trial": f.parent.name, "task": task_of(f.parent.name),
                         "status": f"result.json unreadable: {type(e).__name__}"})
            continue
        rows.append(summarize(rec.get("task") or f.parent.name, rec))
    return rows


def summarize(trial, rec):
    """One trial -> scalar token fields, with the capture state labelled rather than zero-filled."""
    out = {"trial": trial, "task": task_of(trial),
           "turns": rec.get("num_turns"), "wall_s": rec.get("wall_s"), "cost_usd": rec.get("cost_usd")}
    if "usage" not in rec:
        out["status"] = NOT_CAPTURED
        return out
    usage = rec.get("usage")
    if not isinstance(usage, dict):
        out["status"] = EMPTY_BLOCK
        return out
    missing = [k for k in TOKEN_KEYS if usage.get(k) is None]
    if missing:
        out["status"] = "usage block incomplete: " + ", ".join(missing)
    for k in TOKEN_KEYS:
        out[k] = usage.get(k)
    # A prompt total must not be built over a hole: if any of the three prompt counters is missing,
    # the total is None, not a partial sum presented as if it were complete.
    prompt_fields = TOKEN_KEYS[:3]
    if any(usage.get(k) is None for k in prompt_fields):
        out["prompt_tokens"] = None
    else:
        out["prompt_tokens"] = sum(usage[k] for k in prompt_fields)
    cached = usage.get("cache_read_input_tokens")
    out["cache_read_share"] = (round(cached / out["prompt_tokens"], 4)
                               if isinstance(cached, int) and isinstance(out["prompt_tokens"], int)
                               and out["prompt_tokens"] > 0 else None)
    return out


def _stats(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return None
    vals.sort()
    med = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
    ratio = (max(vals) / min(vals)) if min(vals) > 0 else None
    return {"n": len(vals), "median": med, "min": min(vals), "max": max(vals), "spread": ratio}


def aggregate(rows):
    by_task, problems = {}, []
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)
        if r.get("status"):
            problems.append((r["trial"], r["status"]))
    report = {}
    for task, rs in sorted(by_task.items()):
        report[task] = {
            "n": len(rs),
            "prompt_tokens": _stats([r.get("prompt_tokens") for r in rs]),
            "cache_read_share": _stats([r.get("cache_read_share") for r in rs]),
            "output_tokens": _stats([r.get("output_tokens") for r in rs]),
            "turns": _stats([r.get("turns") for r in rs]),
            "cost_usd": _stats([r.get("cost_usd") for r in rs]),
            "captured": sum(1 for r in rs if r.get("prompt_tokens") is not None),
        }
    return report, problems


def fmt(s, pct=False, decimals=0):
    if not s:
        return "n/a"
    if pct:
        return f"{100*s['median']:.1f}% [{100*s['min']:.1f}–{100*s['max']:.1f}]"
    spread = f"{s['spread']:.2f}x" if s["spread"] else "—"
    f = f"{{:.{decimals}f}}"
    return f"{f.format(s['median'])} ({f.format(s['min'])}–{f.format(s['max'])}, {spread})"


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        return selftest()
    wave = next((a for a in argv if not a.startswith("--")), None)
    if not wave:
        sys.exit(__doc__.strip().splitlines()[2])
    rows = read_trials(wave)
    if not rows:
        sys.exit(f"no trials found under {wave} (expected sessions/*/result.json)")
    report, problems = aggregate(rows)
    captured = sum(t["captured"] for t in report.values())
    print(f"token accounting: {wave} — {len(rows)} trials, "
          f"{captured} with usage ({len(rows) - captured} without)")
    print(f"{'task':6s} {'n':>2s} {'prompt tokens (median, min–max, spread)':40s} "
          f"{'cache-read share':22s} {'output':22s} {'cost $':22s}")
    for task, t in report.items():
        print(f"{task:6s} {t['n']:2d} {fmt(t['prompt_tokens']):40s} "
              f"{fmt(t['cache_read_share'], pct=True):22s} {fmt(t['output_tokens']):22s} "
              f"{fmt(t['cost_usd'], decimals=2):22s}")
    if problems:
        print("\ncapture gaps (never filled with zero):")
        for trial, why in problems[:24]:
            print(f"  {trial}: {why}")
        if len(problems) > 24:
            print(f"  … and {len(problems) - 24} more")
    if captured == 0:
        print("\nNothing to report on the token axis for this wave: the driver that ran it did not "
              "retain the usage block. Say that in the record — do not print 0.")
    if "--json" in argv:
        out = pathlib.Path(argv[argv.index("--json") + 1])
        out.write_text(json.dumps({"wave": wave, "tasks": report,
                                   "capture_gaps": [p[1] for p in problems]}, indent=1))
        print(f"wrote {out}")


def selftest():
    """The aggregator must label capture holes, never compute over them."""
    cases = []

    def check(label, got, want):
        ok = got == want
        cases.append((label, ok, got, want))
        return ok

    # Task-name parsing: the F1/F2 trials join the aggregation from the 2026-11-16 wave, and
    # an unparsed name would split each trial into its own "task" column.
    check("T task parsed", task_of("T3r2"), "T3")
    check("F task parsed", task_of("F1r2"), "F1")
    check("no run suffix keeps its name", task_of("T1"), "T1")

    full = summarize("T3r1", {"num_turns": 30, "cost_usd": 1.0,
                              "usage": {"input_tokens": 10, "cache_creation_input_tokens": 90,
                                        "cache_read_input_tokens": 900, "output_tokens": 500}})
    check("ok share computed", full["cache_read_share"], 0.9)
    check("ok prompt", full["prompt_tokens"], 1000)
    check("no status", full.get("status"), None)

    old = summarize("T3r1", {"num_turns": 30})
    check("old driver labelled", old.get("status"), NOT_CAPTURED)
    check("old driver prompt is None", old.get("prompt_tokens"), None)
    check("old driver share is None", old.get("cache_read_share"), None)

    nulled = summarize("T3r1", {"usage": None})
    check("null block labelled", nulled.get("status"), EMPTY_BLOCK)
    check("null block prompt None", nulled.get("prompt_tokens"), None)

    partial = summarize("T3r1", {"usage": {"input_tokens": 10, "cache_creation_input_tokens": None,
                                           "cache_read_input_tokens": 5, "output_tokens": 1}})
    check("partial labelled", "cache_creation_input_tokens" in (partial.get("status") or ""), True)
    check("partial prompt None", partial.get("prompt_tokens"), None)
    check("partial share None", partial.get("cache_read_share"), None)

    zeros = summarize("T3r1", {"usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                         "cache_read_input_tokens": 0, "output_tokens": 0}})
    check("zero prompt => share None (no ZeroDivisionError)", zeros.get("cache_read_share"), None)

    report, problems = aggregate([full, old, nulled, partial, zeros])
    check("aggregate counts captured rows (a genuine zero-usage trial counts)", report["T3"]["captured"], 2)
    check("aggregate records 3 capture gaps", len(problems), 3)
    check("median ignores rows with no turns", report["T3"]["turns"]["n"], 2)

    bad = [c for c in cases if not c[1]]
    for label, ok, got, want in cases:
        print(f"{'Y' if ok else 'N'}  {label:52s} got={got!r}")
        if not ok:
            print(f"   want={want!r}")
    print(f"\n{len(cases) - len(bad)}/{len(cases)} usage-aggregation cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
