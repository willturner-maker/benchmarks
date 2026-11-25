#!/usr/bin/env python3
"""Summarize a Harbor *model* run: one row per trial, plus aggregates and optional JSON.

Usage: summarize_model_run.py <jobs-dir> <model-id> [--json out.json]

Reads each trial's result.json plus agent/trajectory.json. Rewards are reported as measured;
exceptions (agent timeout, etc.) are kept visible next to the reward, because a 0.0 that came from
running out of horizon is a different fact from a 0.0 that came from a wrong answer.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_dir")
    ap.add_argument("model_id")
    ap.add_argument("--json", dest="json_out")
    a = ap.parse_args()

    rows = []
    for f in sorted(glob.glob(os.path.join(a.jobs_dir, "*", "*__*/result.json"))):
        r = json.load(open(f))
        d = os.path.dirname(f)
        name = os.path.basename(d).split("__")[0]
        st, en = r.get("started_at"), r.get("finished_at")
        wall = None
        if st and en:
            t0 = datetime.fromisoformat(st.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(en.replace("Z", "+00:00"))
            wall = (t1 - t0).total_seconds()
        ar = r.get("agent_result") or {}
        u = ((ar.get("model_usage") or {}).get(a.model_id)) or {}
        steps = 0
        tj = os.path.join(d, "agent", "trajectory.json")
        if os.path.exists(tj):
            try:
                steps = len(json.load(open(tj)).get("steps") or [])
            except Exception:
                steps = -1
        rows.append({
            "task": name,
            "reward": (r.get("verifier_result") or {}).get("rewards", {}).get("reward"),
            "exception": (r.get("exception_info") or {}).get("exception_type"),
            "wall_s": round(wall, 1) if wall else None,
            "steps": steps,
            "input_tokens": u.get("n_input_tokens"),
            "cache_tokens": u.get("n_cache_tokens"),
            "output_tokens": u.get("n_output_tokens"),
            "trial_dir": os.path.relpath(d, a.jobs_dir),
        })

    if not rows:
        print(f"no trials under {a.jobs_dir}")
        return 2

    width = max(len(x["task"]) for x in rows)
    print(f"{'task':<{width}}  reward  wall   steps   out_tok   in_tok  exception")
    print("-" * (width + 56))
    for x in rows:
        print(f"{x['task']:<{width}}  {str(x['reward']):<6}  {str(x['wall_s'] or ''):>5}  "
              f"{x['steps']:>5}  {str(x['output_tokens'] or ''):>8}  {str(x['input_tokens'] or ''):>7}  "
              f"{x['exception'] or '-'}")

    n = len(rows)
    walls = [x["wall_s"] for x in rows if x["wall_s"]]
    scored = [x for x in rows if x["reward"] not in (None,)]
    exc = {}
    for x in rows:
        exc[x["exception"] or "none"] = exc.get(x["exception"] or "none", 0) + 1
    nonzero = [x for x in scored if (x["reward"] or 0) > 0]
    print(f"\ntrials={n} | scored(reward present)={len(scored)} | reward>0: {len(nonzero)}"
          f"{' (' + ', '.join(x['task'] for x in nonzero) + ')' if nonzero else ''}")
    if walls:
        walls.sort()
        print(f"wall: mean {sum(walls)/len(walls):.0f}s median {walls[len(walls)//2]:.0f}s "
              f"min {walls[0]:.0f}s max {walls[-1]:.0f}s")
    print(f"exceptions: {exc}")
    print(f"tokens: in {sum(x['input_tokens'] or 0 for x in rows)} "
          f"(cache {sum(x['cache_tokens'] or 0 for x in rows)}) "
          f"/ out {sum(x['output_tokens'] or 0 for x in rows)}")

    if a.json_out:
        summary = {
            "jobs_dir": a.jobs_dir,
            "model_id": a.model_id,
            "trials": n,
            "reward_nonzero_tasks": [x["task"] for x in nonzero],
            "exception_counts": exc,
            "wall_s": ({"mean": sum(walls) / len(walls), "median": walls[len(walls) // 2],
                        "min": walls[0], "max": walls[-1]} if walls else None),
            "tokens": {"input": sum(x["input_tokens"] or 0 for x in rows),
                       "cache": sum(x["cache_tokens"] or 0 for x in rows),
                       "output": sum(x["output_tokens"] or 0 for x in rows)},
            "rows": rows,
        }
        with open(a.json_out, "w") as fh:
            json.dump(summary, fh, indent=1, sort_keys=True)
        print(f"\nwrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
