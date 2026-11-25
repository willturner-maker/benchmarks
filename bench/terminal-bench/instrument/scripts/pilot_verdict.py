#!/usr/bin/env python3
"""Did a Harbor model run actually reach the model? Authoritative, attributable check.

Usage: pilot_verdict.py <jobs-dir> <pinned-model-id>

Why not engine counters: this operator session is served by the same engine under benchmark, and its
traffic is bursty and event-driven. Extrapolating a 120 s idle-sample across a 35-minute run voided a
run that had in fact made 48 model calls — a false negative, worse than the true positive it was built
to catch. Engine counters are printed as context only.

The authority is Harbor's own per-trial accounting: agent_result.model_usage keyed by model id, which
is attributable to a trial by construction. A run whose accounting names no pinned id (or bills zero
output tokens) never reached the model, and every reward from it is void.
"""

from __future__ import annotations

import glob
import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    out, mid = sys.argv[1], sys.argv[2]

    trials = glob.glob(os.path.join(out, "*", "*__*/result.json"))
    if not trials:
        print(f"no trials under {out}")
        return 2

    key = in_tok = out_tok = cache_tok = steps = 0
    per_trial = []
    for f in trials:
        r = json.load(open(f))
        mu = ((r.get("agent_result") or {}).get("model_usage")) or {}
        u = mu.get(mid)
        name = os.path.basename(os.path.dirname(f)).split("__")[0]
        if u:
            key += 1
            in_tok += u.get("n_input_tokens") or 0
            out_tok += u.get("n_output_tokens") or 0
            cache_tok += u.get("n_cache_tokens") or 0
        st = 0
        tj = os.path.join(os.path.dirname(f), "agent", "trajectory.json")
        if os.path.exists(tj):
            st = len(json.load(open(tj)).get("steps") or [])
            steps += st
        rw = (r.get("verifier_result") or {}).get("rewards") or {}
        exc = (r.get("exception_info") or {}).get("exception_type")
        per_trial.append((name, st, u.get("n_output_tokens") if u else 0, rw.get("reward"), exc))

    print(f"pinned model id: {mid}")
    print(f"trials: {len(trials)} | trials whose model_usage names the pinned id: {key}")
    print(f"tokens billed to the pinned id: {in_tok} in ({cache_tok} cached) / {out_tok} out")
    print(f"trajectory steps: {steps}")
    for name, st, ot, rw, exc in per_trial:
        print(f"   {name:<28} steps {st:>3}  out {ot:>7}  reward {rw}  exc {exc or '-'}")

    if key == 0 or out_tok == 0:
        print("\nVERDICT: VOID — no tokens billed to the pinned model id; the run never reached")
        print("the model. Every reward from it is void; fix routing before any wave is recorded.")
        return 5
    print(f"\nVERDICT: model reached — {out_tok} output tokens over {steps} steps in {key}/{len(trials)}")
    print("trials are attributable to the pinned id, so rewards from this run are real measurements")
    print("(they may still be 0.0 for capability reasons; that is a score, not a plumbing fault).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
