#!/usr/bin/env python3
"""Summarize a Harbor oracle run into one row per task.

Reads a Harbor jobs directory (the dir `-o <name>` writes) and prints, per task:
environment verdict (clean | errored | missing), the reward the task's own verifier
wrote, and the exception type when there is one. Used for gate 2 triage: an *errored*
row means the environment/verifier plumbing failed (not measurement-grade); a clean row
with reward 0.0 is a task/verifier signal, which is a different finding entirely.

Usage: summarize_oracle_run.py <jobs-dir> [--with-exception-tail]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter
from pathlib import Path


def reward_of(trial: dict) -> str:
    vres = trial.get("verifier_result") or {}
    rewards = vres.get("rewards")
    if isinstance(rewards, dict) and rewards:
        return ",".join(f"{k}={v}" for k, v in sorted(rewards.items()))
    return "-"


def exception_of(trial: dict) -> str:
    info = trial.get("exception_info") or {}
    return info.get("exception_type") or "-"


def rewards_numeric(trial: dict) -> list[float]:
    """Numeric reward values, so `1` and `1.0` are the same outcome.

    Tasks do not agree on serialization: wal-recovery-ordering writes integer 1 while every
    other task in the 4.1.0 tree writes 1.0, and a string compare would call that a mismatch.
    """
    vres = trial.get("verifier_result") or {}
    rewards = vres.get("rewards")
    if isinstance(rewards, dict):
        return [float(v) for v in rewards.values() if isinstance(v, (int, float))]
    return []


def passed(trial: dict) -> bool:
    """A trial passes iff it has rewards and every reward is 1 (numerically)."""
    nums = rewards_numeric(trial)
    return bool(nums) and all(v == 1.0 for v in nums)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_dir")
    ap.add_argument(
        "--with-exception-tail",
        action="store_true",
        help="print the last line of each errored trial's exception.txt",
    )
    args = ap.parse_args()

    jobs = sorted(glob.glob(os.path.join(args.jobs_dir, "*/result.json")))
    if not jobs:
        print(f"no Harbor job result.json under {args.jobs_dir}")
        return 2

    rows: list[tuple[str, str, str, str, str]] = []
    seen: set[str] = set()
    task_attempts: dict[str, list[bool]] = {}
    for job in jobs:
        data = json.load(open(job))
        trials = data.get("trial_results") or data.get("trials") or []
        if not trials:
            # newer Harbor keeps per-trial dirs; read their result.json files
            for tr_dir in sorted(Path(job).parent.glob("*__*/result.json")):
                trials.append(json.load(open(tr_dir)))
        for t in trials:
            name = t.get("task_name") or t.get("task") or Path(job).parent.name
            exc = exception_of(t)
            rew = reward_of(t)
            verdict = "errored" if exc != "-" else ("clean" if rew != "-" else "no-reward")
            wall = ""
            start, end = t.get("started_at"), t.get("finished_at")
            if start and end:
                wall = f"{start[:19]}..{end[11:19]}"
            rows.append((name, verdict, rew, exc, wall))
            seen.add(name)
            # gate criterion per attempt: no exception AND every reward numerically 1. An errored
            # trial that still carries a reward (e.g. a reference solution exiting nonzero after
            # the verifier scored it) counts as a failure, not a pass.
            ok = exc == "-" and bool(rewards_numeric(t)) and all(v == 1.0 for v in rewards_numeric(t))
            task_attempts.setdefault(name.split("/")[-1], []).append(ok)

    rows.sort()
    width = max((len(r[0]) for r in rows), default=10)
    print(f"{'task':<{width}}  {'verdict':<9}  {'reward':<12}  exception")
    print("-" * (width + 40))
    for name, verdict, rew, exc, wall in rows:
        print(f"{name:<{width}}  {verdict:<9}  {rew:<12}  {exc}")

    tally = Counter(r[1] for r in rows)
    exc_tally = Counter(r[3] for r in rows if r[3] != "-")
    print(
        f"\ntrials={len(rows)} "
        f"clean={tally.get('clean', 0)} "
        f"errored={tally.get('errored', 0)} "
        f"no-reward={tally.get('no-reward', 0)}"
    )

    # Gate view: per task, how many of its k attempts actually reached reward 1. A trial can be
    # "clean" (verifier ran, wrote a reward file) and still be a gate failure at reward 0 — the
    # two verdicts above deliberately keep those apart, and an oracle gate fails on the second.
    per_task = {k: (sum(1 for p in v if p), len(v)) for k, v in task_attempts.items()}
    kmax = max((tot for _, tot in per_task.values()), default=0)
    flaky = {k: v for k, v in per_task.items() if v[0] < v[1]}
    if flaky:
        print(f"\noracle short of reward 1 on {len(flaky)} task(s) — an environment/task flake to")
        print("root-cause, never rescue with retries:")
        for k, (ok, tot) in sorted(flaky.items()):
            print(f"  {ok}/{tot}  {k}")
    else:
        print(f"\nall {len(per_task)} task(s) reached reward 1 on all {kmax} attempt(s)")
    if exc_tally:
        print("exception classes:")
        for k, v in exc_tally.most_common():
            print(f"  {v:>3}  {k}")

    missing = sorted(
        d.split("/")[1]
        for d in glob.glob(os.path.join(os.path.dirname(os.path.dirname(args.jobs_dir)), "tasks", "*"))
        if os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(args.jobs_dir)), "tasks", d.split("/")[1]))
        and d.split("/")[1] not in {r[0].split("/")[-1] for r in rows}
        and not d.endswith(".toml")
    )
    if missing:
        print(f"\nnever ran ({len(missing)}): {' '.join(missing)}")

    if args.with_exception_tail:
        print("\nexception tails:")
        for exc_file in sorted(glob.glob(os.path.join(args.jobs_dir, "*/*__*/exception.txt"))):
            tail = Path(exc_file).read_text(errors="replace").strip().splitlines()[-1:] or [""]
            print(f"  {exc_file.split('/')[1][:34]:<34} {tail[0][:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
