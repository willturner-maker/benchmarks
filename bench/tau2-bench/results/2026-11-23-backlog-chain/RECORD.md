# Backlog chain 2026-11-23 — five-stage detached run, runner + incident log

**Runner:** `../../run_backlog_chain.sh` (commit `f4316a6`), detached 07:41→11:52Z, grace window honored,
all kills identity-gated, pin restored unconditionally. Per-stage RECORDs live in their own result dirs:

| stage | what | outcome |
|---|---|---|
| S1 | tau2 238×3 confirmation wave on 1.7.1 | exit 0 — `../2026-11-23-pass3-171-confirm/RECORD.md` |
| S2 | tool-loop-gate two-arm wave | exit 0 — `../../../tool-loop-gate/results/2026-11-23-gate-171/RECORD.md` |
| S3 | splash Tier-1: fingerprint capture/diff + golden probes/compare on pinned instance | all exit 0 — `../../../splash-concurrency/results/splash-1.7.1-transition/RECORD.md` |
| S4 | splash 8-lane ladder (identity-gated relaunch, ladder, pin restore) | exit 0 — `../../../splash-concurrency/results/ladder-8lane-2026-11-23/RECORD.md` |
| S5 | resolve-agentic MCP wave | **exit 1 — failed fast, see below**; wave relaunched manually |

## S5 incident log (published so the failure mode is searchable)

1. **exit=1 at launch:** `PermissionError: /Volumes/YourVolume` — the driver's `DEFAULT_RENDER_ROOT` is a
   placeholder path (`wave_driver_f1f2_opencode_v2.py:34`); I chained S5 without overriding `--render-root`
   the way prior waves did (tier4-18m used the real media volume's `…/resolve-audio-analysis/agbench_2026-11-18m`;
   the driver's default is the `/Volumes/YourVolume` placeholder and must be overridden per wave).
   Runner bug on my side, not the instrument.
2. **First manual relaunch (pid 35199)** got through the harness self-check but every trial seal-leaked:
   MCP returned `Failed to load '_mcp_AGBench-2026-11-23b'` — **the fixture project had never been built**
   (each new wave needs `build_fixture_effort_ab.py --project …`; the 11-18m wave project is not reused because
   timeline names are keyed to the wave tag). Killed at trial 4.
3. **Fixture build #1** verified but showed `_f2r2` missing the cross-dissolve row (2 items vs 4 — transient
   MCP failure during arming) and the killed attempt had left a partial `_T2r1`. Rebuilt with `--fresh`.
   Fixture #2 verified: all f2 reps carry `(108209→108233)` dissolve row; gt + prestate written
   (`ground_truth-_mcp_AGBench-2026-11-23b.json`, `prestate-_mcp_AGBench-2026-11-23b.json`).
4. **Wave attempt #2 (pid 36313, ~12:04Z)** running clean: only T1r1 seal-leaked (2 transient
   `davinci-resolve_timeline` errors — first-trial MCP cold start); pairs T2r2+ onward leak-free.
   Grading will mark T1r1 per the suite's seal-leak rule.

Tenancy note for S5: my session's own davinci-resolve MCP connection was live during the wave (used for
diagnosis); Resolve itself was not driven from any other session during S1–S4 windows.
