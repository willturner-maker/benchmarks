# Wave RECORD — agbench-23d-2026-11-23

**What**: second wave of the opencode **2.4.1** + davinci-resolve MCP **5.4.0** build series
(first within-series repeat; 23c was wave 1). Engine: **Splash 1.7.1**, pinned argv unchanged
(`--max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache
--default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64`), warm cache.
Full 21-task set ×3, 2-lane pairs, order rotated vs 23c (opened F2r1+F2r2, soloed T8r3).
Driver v2.1 at launch (pre-session pool watchdog + `--order`), upgraded to v2.2 mid-close-out
(see deviations).

**Fixture**: `_mcp_AGBench-2026-11-23d` — `build_fixture_effort_ab.py --fresh`, builder arm
checks green (f2: transitions=1, graded[2,3]=[True,True]), gt+prestate sealed at build. Archive
siblings purged pre-dispatch with the newly committed `purge_fixture_archives.py`
(14→10, logged). Kept loaded after the wave (parked-fixture policy).

**Window**: 2026-11-23T22:54:12Z → 23:20:44Z (26.5 min — parity with 23c's 24.0 and 171's 23.7).
Tenancy: engine samples every 30 s in-wave; queue never congested, no foreign work.

**Result**: raw **19/21**; corrected **21/21** — identical shape to 23c. The within-series
band at n=2: raw {19,19}/21 (both raw misses are harness dropouts), corrected {21,21}/21.
**Zero genuine model misses in 42 same-build trials.**

**Deviations (all recorded)**:
1. **T1r1 + T8r1 harness-invalid re-runs.** The 2.4.1 per-session MCP registration failure
   recurred at the same 2/21 rate (build bug confirmed). Burst form varies: 23c dropouts
   errored real underscore tool names; 23d's T1r1/T8r1 errored mangled hyphen forms with
   zero Resolve completions (T8r1's advanced server stayed alive). Agents again honest:
   T1r1 reported "values unavailable" with 12 rejected calls and zero changes; T8r1 probed
   repeatedly, then reported inability. Originals preserved
   (`sessions/<name>-invalid-mcp-down/`, `wave_results.json.invalid_attempts`); re-runs
   (23:40–23:41Z) both PASS.
2. **Watchdog v2.1→v2.2** (committed): v2.1's underscore-name signature missed the 23d
   dropout form. v2.2 confirms the pool only on a live/builtin-named completion (an
   advanced-only session cannot execute live briefs) and counts "No tool named" rejections
   across ANY `davinci-resolve*` form, killing at 6 with no completion, with an EOF re-check.
   Verified by offline replay of all 21 sealed sessions: exactly T1r1/T8r1 flag DEAD. Then
   caught one live: T8r1 re-run attempt 0 was killed at the 6th rejection and attempt 1
   PASSed (`sessions/T8r1-attempt0-probe-dead/` preserved). A naming bug that put the
   winning retry under a `-probe-dead` dir was fixed the same commit; wave artifacts renamed
   to match.
3. **F2r2 misfire (agent-side, honest recovery):** `ripple_insert` double-offsets
   `record_frame` (elapsed-from-start PLUS the 108000 offset): the first execute landed at
   absolute 216442, leaving a 107,779-frame gap. The agent disclosed it, deleted the two
   misplaced items, verified the baseline restored (0 gaps / 2 overlaps), then inserted
   correctly at 108442. Geometry graded PASS. New api_truths friction row for the action.

**Seal audit**: 0 real leaks across 24 sessions; 50 flagged mangled-name attempts (23c: 81).

**Watch items**: F2 link-repair did not recur — 0/3 `set_clips_linked` this wave, 0/6 across
the series' two same-build waves. T7 render storm did not recur (3/3 rendered + verified,
~16 MB each under the canonical render root, `agbench_23d-2026-11-23`).

**How to relaunch** (fresh `--fresh` fixture name required):
```
python3 build_fixture_effort_ab.py --project _mcp_AGBench-<next> --fresh
python3 purge_fixture_archives.py _mcp_AGBench-<next>
python3 derive_grader_gt_16f.py _mcp_AGBench-<next> --wave agbench-<next>
bash run_wave_23d.sh    # pattern: rotated --order, render root per RUNBOOK §3
python3 grade_f1f2_wave.py --wave results/agbench-<next> \
    --claims claims-agbench-<next>.json --gt ground_truth-_mcp_AGBench-<next>-16f.json \
    --out results/agbench-<next>/grading.json
```

**Artifacts**: raw wave (sessions incl. invalid + probe-dead attempts, `wave_results.json`
incl. `invalid_attempts`, `grading.json`, `harness_log.jsonl`, `engine_samples.jsonl`) under
`results/agbench-23d-2026-11-23/` — gitignored; published distillation is
`results-agbench-23d-2026-11-23.json` + this RECORD + claims at suite root.
