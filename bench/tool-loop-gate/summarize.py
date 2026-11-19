#!/usr/bin/env python3
"""Flatten hermes-agentic-bench gate JSONs into per-task rows and RE-DERIVE the headline numbers.

Rule-3 discipline: the harness prints its own SUMMARY line, but nothing in this repo publishes a
harness self-report without an independent recomputation. This script recomputes n_pass / mean_tools
/ hit-cap / parse-fail / dup counts from the per-task rows and refuses to stay silent when the two
disagree.

Published rows deliberately carry NO model free text. `tests[*].final_content` is the model's own
answer; the evidence we publish is the observed tool-call trace (name + arguments + what the scripted
world returned), plus scalars derived from the answer (answered, answer_chars).

Usage:  summarize.py <wave-dir> [--raw <dir-with-upstream-jsons>] [--allow-partial]
Reads:  <raw>/gate-*.json        (upstream output, unmodified; defaults to <wave-dir>)
Writes: <wave-dir>/wave.jsonl   (one row per task per pass; no model free text)
        <wave-dir>/summary.json (re-derived band + confounds)
        summarize.py <wave-dir> --from-rows   -> re-check published numbers from wave.jsonl alone
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

STUB_PREFIX = "ok: ran"          # world_readonly's generic reply to a command it does not model
UPSTREAM_DEFAULTS = {"temperature": 0.6, "top_p": 0.95, "top_k": 64}


def axis_of(run: dict) -> str:
    s = run.get("sampling") or {}
    if s.get("temperature") == 0:
        return "greedy"
    if all(s.get(k) == v for k, v in UPSTREAM_DEFAULTS.items()):
        return "defaults"
    return "custom-" + json.dumps(s, sort_keys=True)


def stub_count(task: dict) -> int:
    return sum(1 for c in task["calls"] if (c.get("result_head") or "").startswith(STUB_PREFIX))


def trace_key(task: dict) -> str:
    """Canonical call trace, for cross-pass determinism on the same sampling axis."""
    return json.dumps([[c["name"], json.dumps(c["arguments"], sort_keys=True, separators=(",", ":"))]
                       for c in task["calls"]], separators=(",", ":"))


def rederive(tests: dict) -> dict:
    n = len(tests)
    return {
        "n_tasks": n,
        "n_pass": sum(1 for t in tests.values() if t.get("pass")),
        "pass_rate": round(sum(1 for t in tests.values() if t.get("pass")) / n, 3) if n else 0.0,
        "mean_tools": round(sum(t.get("n_tools") or 0 for t in tests.values()) / n, 2) if n else 0,
        "n_hit_cap": sum(1 for t in tests.values() if t.get("hit_cap")),
        "n_parse_fail_tasks": sum(1 for t in tests.values() if (t.get("parse_fails") or 0) > 0),
        "n_dup_tasks": sum(1 for t in tests.values() if (t.get("duplicate_calls") or 0) > 0),
    }


def from_rows(wave: str) -> int:
    """Re-derive the band from PUBLISHED per-task rows, so a reviewer can check our numbers without
    our raw files (which hold model free text and are not published)."""
    path = os.path.join(wave, "wave.jsonl") if not wave.endswith(".jsonl") else wave
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    by_pass: dict[str, list[dict]] = {}
    for r in rows:
        by_pass.setdefault(r["pass"], []).append(r)
    print(f"rows: {len(rows)}  passes: {len(by_pass)}  (re-derived from published rows)")
    ok_all = True
    for pid, rs in sorted(by_pass.items()):
        tests = {r["task"]: {"pass": r["ok"], "n_tools": r["n_tools"], "hit_cap": r["hit_cap"],
                             "parse_fails": r["parse_fails"], "duplicate_calls": r["duplicate_calls"]}
                 for r in rs}
        s = rederive(tests)
        print(f"  {pid:12s} {s['n_pass']}/{s['n_tasks']}  mean_tools {s['mean_tools']}  "
              f"hit_cap {s['n_hit_cap']}  parse_fail {s['n_parse_fail_tasks']}  dup {s['n_dup_tasks']}")
        ok_all &= s["n_tasks"] == 20
    print(f"every pass has all 20 tasks: {ok_all}")
    return 0 if ok_all else 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    wave = sys.argv[1]
    raw_dir = wave
    for i, a in enumerate(sys.argv):
        if a == "--raw" and i + 1 < len(sys.argv):
            raw_dir = sys.argv[i + 1]
    if "--from-rows" in sys.argv[2:]:
        return from_rows(wave)
    files = sorted(glob.glob(os.path.join(raw_dir, "gate-*.json")))
    if not files:
        print(f"no gate-*.json in {wave}")
        return 1

    rows: list[dict] = []
    passes: list[dict] = []
    seen_axis: dict[str, int] = {}
    for path in files:
        run = json.load(open(path, encoding="utf-8"))
        if run.get("kind") != "hermes_loop_gate":
            print(f"  skip (not a gate record): {os.path.basename(path)}")
            continue
        if len(run["tests"]) != 20 and "--allow-partial" not in sys.argv[2:]:
            print(f"  skip (partial run, {len(run['tests'])}/20 tasks - transport probe, not a pass): "
                  f"{os.path.basename(path)}")
            continue
        ax = axis_of(run)
        seen_axis[ax] = seen_axis.get(ax, 0) + 1
        pid = f"{ax}-{seen_axis[ax]}"
        claimed = run.get("summary") or {}
        mine = rederive(run["tests"])
        agree = claimed == mine
        lat = sorted(tr["elapsed_s"] for t in run["tests"].values() for tr in t["turns"])
        passes.append({
            "pass_id": pid,
            "file": os.path.basename(path),
            "axis": ax,
            "sampling": run.get("sampling"),
            "max_turns": run.get("max_turns"),
            "harness_summary": claimed,
            "derived_summary": mine,
            "agree": agree,
            "llm_calls": len(lat),
            "call_latency_s": {"min": lat[0], "median": lat[len(lat) // 2], "max": lat[-1],
                               "total": round(sum(lat), 1)},
            "tool_calls": sum(len(t["calls"]) for t in run["tests"].values()),
            "stub_responses": sum(stub_count(t) for t in run["tests"].values()),
        })
        for tid, t in run["tests"].items():
            rows.append({
                "pass": pid, "axis": ax, "task": tid, "ok": bool(t.get("pass")),
                "n_tools": t.get("n_tools"), "turns": len(t["turns"]),
                "duplicate_calls": t.get("duplicate_calls"), "hit_cap": t.get("hit_cap"),
                "parse_fails": t.get("parse_fails"), "error": t.get("error"),
                "stub_responses": stub_count(t),
                "finish_reasons": [tr["finish_reason"] for tr in t["turns"]],
                "answered": bool((t.get("final_content") or "").strip()),
                "answer_chars": len(t.get("final_content") or ""),
                "calls": [{"name": c["name"], "arguments": c["arguments"],
                           "world_returned": (c.get("result_head") or "")[:90]} for c in t["calls"]],
            })

    with open(os.path.join(wave, "wave.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # per-task stability + trace determinism per axis
    axes: dict[str, list[dict]] = {}
    for p in passes:
        axes.setdefault(p["axis"], []).append(p["pass_id"])
    task_view: dict[str, dict] = {}
    for ax, pids in axes.items():
        by_task: dict[str, list[dict]] = {}
        for r in rows:
            if r["axis"] == ax:
                by_task.setdefault(r["task"], []).append(r)
        for tid, rs in by_task.items():
            traces = {trace_key({"calls": r["calls"]}) for r in rs}
            task_view.setdefault(tid, {})[ax] = {
                "passes": sum(1 for r in rs if r["ok"]),
                "out_of": len(rs),
                "n_tools": [r["n_tools"] for r in rs],
                "distinct_traces": len(traces),
            }

    print(f"wave: {wave}\npasses: {len(passes)}  tasks/pass: 20  rows: {len(rows)}")
    for p in passes:
        s = p["derived_summary"]
        print(f"\n  {p['pass_id']:12s} {p['file']}")
        print(f"    {s['n_pass']}/{s['n_tasks']} (pass_rate {s['pass_rate']})  mean_tools {s['mean_tools']}"
              f"  hit_cap {s['n_hit_cap']}  parse_fail {s['n_parse_fail_tasks']}  dup {s['n_dup_tasks']}")
        print(f"    llm_calls {p['llm_calls']}  latency_s min/med/max "
              f"{p['call_latency_s']['min']}/{p['call_latency_s']['median']}/{p['call_latency_s']['max']}"
              f"  tool_calls {p['tool_calls']}  stub_responses {p['stub_responses']}"
              f" ({100 * p['stub_responses'] / max(p['tool_calls'], 1):.0f}%)")
        if not p["agree"]:
            print(f"    !! HARNESS vs RE-DERIVED MISMATCH\n       harness {p['harness_summary']}\n"
                  f"       derived {p['derived_summary']}")

    print("\nper-task, by axis (passes / out-of, n_tools per pass, distinct traces):")
    for tid in sorted(task_view):
        parts = []
        for ax, v in sorted(task_view[tid].items()):
            flag = "" if v["passes"] == v["out_of"] or v["passes"] == 0 else " UNSTABLE"
            parts.append(f"{ax}: {v['passes']}/{v['out_of']} tools={v['n_tools']} traces={v['distinct_traces']}{flag}")
        print(f"  {tid:30s} " + "  |  ".join(parts))

    always_fail = [t for t, v in task_view.items()
                   if all(x["passes"] == 0 for x in v.values())]
    always_pass = [t for t, v in task_view.items()
                   if all(x["passes"] == x["out_of"] for x in v.values())]
    print(f"\nalways-fail ({len(always_fail)}): {always_fail}")
    print(f"always-pass ({len(always_pass)}): {len(always_pass)} tasks")

    band = {}
    for ax, pids in axes.items():
        sel = [p["derived_summary"] for p in passes if p["axis"] == ax]
        band[ax] = {
            "n_pass": [s["n_pass"] for s in sel],
            "pass_rate": [s["pass_rate"] for s in sel],
            "mean_tools": [s["mean_tools"] for s in sel],
            "hit_cap": [s["n_hit_cap"] for s in sel],
            "stub_pct": [round(100 * p["stub_responses"] / max(p["tool_calls"], 1)) for p in passes
                         if p["axis"] == ax],
        }
        band[ax]["median_pass_rate"] = statistics.median(band[ax]["pass_rate"])
    summary = {"passes": passes, "band": band, "always_fail": always_fail,
               "always_pass_count": len(always_pass), "task_view": task_view,
               "all_harness_reports_agreed": all(p["agree"] for p in passes)}
    with open(os.path.join(wave, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print(f"\nband: {json.dumps(band, indent=1)}")
    print(f"harness reports all re-derived clean: {summary['all_harness_reports_agreed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
