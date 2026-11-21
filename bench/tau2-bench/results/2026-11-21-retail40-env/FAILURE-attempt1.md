# retail-40 ENV closure — attempt 1 failure (2026-11-21, 14:54–16:19Z)

All 80 sims ended `infrastructure_error` (0 messages kept). Root cause, from the per-sim
`info.error_traceback`: `litellm.NotFoundError: model gpt-4.1-2025-04-14 not found` — the
NL-assertion judge fired despite the request for ENV-only scoring, because:

1. `evaluation_type` is NOT a field of `TextRunConfig` (tau2 v1.0.1) — pydantic silently dropped
   the kwarg from the attempt-1 config; and
2. `run_domain()` (`src/tau2/runner/batch.py:852`) delegates to `run_tasks()` WITHOUT forwarding
   `evaluation_type`, so the default `EvaluationType.ALL` re-engaged the judge on every
   NL-basis task (the 40 in exactly this scope).

Fixed seam (`run_retail40_env.py`, rewritten): call `tau2.runner.run_tasks` directly with
`evaluation_type=EvaluationType.ENV`, mirroring run_domain's task loading and save-path logic;
unmodified source, deviation still disclosed (ENV-only components, not pass^k-comparable).
Smoke (2 tasks x 1 trial): rewards computed DB-only, 0 infrastructure errors.

Engine traffic during attempt 1 (~2.1M prompt tokens of real conversations, wasted at the
scoring step) is visible in engine_samples.jsonl; the status edges and sampler from the rerun
are separate files (engine_samples_rerun.jsonl, status_rerun_*.json). The dead results.json is
quarantined at tau2 `data/simulations/wave-QUARANTINE-retail40-env-attempt1/` (local only).
