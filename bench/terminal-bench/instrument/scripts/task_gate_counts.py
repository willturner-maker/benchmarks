#!/usr/bin/env python3
"""Per-task attempt counts against the oracle gate criterion.

Usage: task_gate_counts.py <jobs-dir> [task …]      (no tasks = every task in the run)

An attempt counts as a pass only if it has no exception AND every reward is numerically 1.
Numeric on purpose: wal-recovery-ordering writes integer 1 while the rest of the 4.1.0 tree
writes 1.0, and an errored trial that still carries a reward (a reference solution exiting
nonzero after its verifier scored it) is a failure, not a pass.

Trials are recognised by the `trial_name` key, which the job-level result.json does not have —
matching on directory shape instead once counted the job summary as a phantom trial.
"""

from __future__ import annotations

import glob
import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    job = sys.argv[1]
    want = set(sys.argv[2:])

    got: dict[str, list[bool]] = {}
    for pat in ("*__*/result.json", "*/*__*/result.json"):
        for f in glob.glob(os.path.join(job, pat)):
            name = os.path.basename(os.path.dirname(f)).split("__")[0]
            if want and name not in want:
                continue
            r = json.load(open(f))
            if "trial_name" not in r:
                continue
            exc = (r.get("exception_info") or {}).get("exception_type")
            rw = (r.get("verifier_result") or {}).get("rewards") or {}
            nums = [float(v) for v in rw.values() if isinstance(v, (int, float))]
            got.setdefault(name, []).append(exc is None and bool(nums) and all(v == 1.0 for v in nums))

    if not got:
        print(f"no trials under {job}")
        return 2
    for name in sorted(got):
        ok, tot = sum(got[name]), len(got[name])
        print(f"{name} {ok}/{tot}{'' if ok == tot else '   <-- short'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
