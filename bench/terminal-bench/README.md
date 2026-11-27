# bench/terminal-bench — RETIRED (2026-11-27)

Terminal-Bench as a comparison instrument on the local engine is **retired** — held
indefinitely, not deleted. Decision basis, in one line: at the pinned engine's decode
(~125 tok/s sustained at `-n 2`) the task horizons bind before capability does — 30/57
wave trials hit the 1440 s cap and a repeat task plateaued identically three times — so
scored waves measure host infrastructure, not agents, and a 0/57 baseline has zero
discriminating power against other open-source models. Cost per comparable-model k=3
run: ~30 h of wave time plus a fresh oracle gate (7.7 h) per pins change.

## What this track actually earned (all still true, all committed)
- **Gate 2C** — measurement-grade environment: 285/285 oracle trials clean at `-n 2`
  (`RECORD-gate2c-2026-11-25.md`).
- **Model wave + pre-declared repeat** — 0/57 k=1; 2/6 near-misses × 1/3; boundary-task
  stability ~1/3; k=1 check-fraction is not a stability predictor
  (`RECORD-wave-model-2026-11-25.md`; pilot `RECORD-stage3-pilot-2026-11-25.md`).
- **Verifier-convention findings** — ctrf "1/1 passed" on a 0.0-scored trial (tb#2926),
  rewardkit gating, single-test verifiers; reading order documented in the wave record.
- **Concurrency-as-measured-variable** — `-n` flips oracle outcomes; QEMU flake root-
  caused to a chunk-boundary race in the task harness (tb#2925). Rule: gate at the
  scoring concurrency, never retry-rescue.
- **Six upstream filings with root causes**: harbor#4469; terminal-bench#2922–#2926.

## Re-entry rule (objective, pre-declared — do not un-retire on vibes)
Run a new scored wave only when BOTH hold:
1. A pilot at the scoring concurrency shows the **majority of candidate tasks clean-
   finishing inside the horizon** (retirement-time fact: 30/57 timed out).
2. The comparison question actually needs Terminal-Bench's task shape; if the goal is
   honest agentic assessment, resolve-agentic (25-min waves, honesty axis) and BFCL
   (~3.6 h for 4,441 task-runs) remain the higher-ROI instruments.

If un-held: pins start from the RECORDs' harbor 0.27.0 + log-mount sticky patch
(harbor#4469 still open upstream as of 2026-11-27 — re-check whether it merged), fresh
gate at scoring concurrency, exclusions copied from gate 2C, k-rules declared pre-launch.

## Disposition
`instrument/` + the three RECORDs stay committed forever (108K, the durable value).
No renders/transcripts here to sweep. The `docs/resolve-agentic-benchmark-results.md`
Terminal-Bench section keeps its analysis; this file is the status of record.
