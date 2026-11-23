# Wave RECORD — agbench-23c-2026-11-23

**What**: first resolve-agentic wave of the new build series — opencode **2.4.1** (previous wave
ran 2.3.2; 2.4.0 changed session storage) + davinci-resolve MCP server **5.4.0** (previous 5.3.4,
parked-then-removed after byte-identical transition capture, see HARNESS-MIGRATION.md).
Engine: **Splash 1.7.1**, pinned argv unchanged and re-verified from the supervisor process at
launch; host rebooted same day, golden probes re-captured 8/8 byte-identical post-reboot
(scratch golden-postreboot-2026-11-23). Full 21-task set x3 (T1,T2,T3,F1,F2,T7,T8), medium effort,
2-lane pairs, task order rotated vs the 171 wave.

**Fixture**: `_mcp_AGBench-2026-11-23c` — built with `build_fixture_effort_ab.py --fresh` at
19:44Z, gt+prestate sealed same minute, 4 builder `_archived_vNN` siblings purged pre-dispatch
(confirm-gated timeline deletes; log: fixture-purge-_mcp_AGBench-2026-11-23c.jsonl, 14->10).
Fixture kept loaded after the wave (not destroyed), matching the parked-fixture policy.

**Window**: launched 2026-11-23T19:58:46Z (detached, `run_wave_23c.sh`), driver-exit 20:22:47Z
(24.0 min — full parity with the 171 wave's 23.7). Tenancy samples every 30 s in-wave
(engine_samples.jsonl, 48 samples): queue never left [0,1], 10/10 polls saw this wave's
sessions, zero foreign work.

**Result**: raw **19/21**; after re-issuing two harness-invalid trials, **21/21** graded.
Two watch items closed WITHOUT recurrence: F2 link-repair (0/3 — none even attempted, F2r2
explicitly declined as out-of-brief) and T7 no-render/storm (3/3 rendered+verified).

**Deviations (all recorded)**:
1. **T2r2 + T8r2 harness-invalid re-runs.** Both originals reported the live davinci-resolve +
   builtin MCP children absent from their session pool for the entire session (only the offline
   advanced server answered); their pair-siblings minutes earlier had working servers, and
   sibling sessions' transcripts log 5-6 pool-missing errors on tools that exist in-wave.
   Per-session MCP child registration failure on the 2.4.1 build — pre-registered rule (smoke
   addendum) attributes to the build. Agents behaved correctly (honest failure reports, no
   offline .drt faking, no mutations). Originals preserved: `sessions/T2r2-invalid-mcp-down/`,
   `sessions/T8r2-invalid-mcp-down/`, and `wave_results.json.invalid_attempts`. Re-runs
   (22:12-22:14Z, same briefs/seal stack/fixture) PASS with full read-backs.
2. **Grader fix (committed)**: the 17g-era "grade dimension unmeasurable" note was hardcoded
   unconditional; now emitted only when the sealed pre-state shows the tracked clip ungraded.
   The 23c pre-state IS properly armed (third clip: 3 grade tools), so all F2 grade-loss
   claims were actually verified against live read-backs — a first for the F2 family.
   Selftest still 69/69.
3. **Committed new instrument** `derive_grader_gt_16f.py`: derives the grader-format (-16f)
   ground truth from the builder's sealed gt+prestate (the ad-hoc step every wave since 17h did
   by hand); 23c derivation verified against the 171b one (T1 census + f1/f2 pre-states match
   modulo project id and null-vs-absent transition source keys).

**Raw first-pass FAILs explained**: T2r2 — grader probe fell back to current timeline (_f2r2)
because the invalid session never created its timeline; _f2r2 itself un-contaminated. T8r2 —
"comp count 0" from the same missing-timeline artifact; the agent never claimed a comp, it
reported total MCP unavailability. No cross-trial contamination anywhere in the wave.

**Seal audit**: 0 real leaks across 23 sessions (576+ graded-trial tool events + re-runs). The
81 auditor flags were all mangled-tool-name attempts (hyphen / claude-style / bare names) that
errored at the harness — the medium-arm sloppiness tax (171: 50, 23c: 81). The auditor itself
had a false-positive bug (errored `(name,'error')` tuples matched the prefix rule — fired in the
171 post-wave audit too, never in graded verdicts); fixed before this wave.

**How to relaunch** (same procedure; a fresh `--fresh` fixture name is required):
```
python3 build_fixture_effort_ab.py --project _mcp_AGBench-<next> --fresh   # then seal gt+prestate
bash run_wave_23c.sh    # pattern: results dir + render root per RUNBOOK §3 + driver argv below
python3 derive_grader_gt_16f.py _mcp_AGBench-<next> --wave agbench-<next>
python3 grade_f1f2_wave.py --wave results/agbench-<next> \
    --claims claims-agbench-<next>.json --gt ground_truth-_mcp_AGBench-<next>-16f.json \
    --out results/agbench-<next>/grading.json
```

**Artifacts**: raw wave (`sessions/*/` transcripts, `wave_results.json` incl. invalid_attempts,
`harness_log.jsonl`, `grading.json`, `engine_samples.jsonl`) under
`results/agbench-23c-2026-11-23/` — **gitignored**; durable published distillation is
`results-agbench-23c-2026-11-23.json` + this RECORD + claims + sealed gt/prestate at suite root.
Renders (T7 x3 + verification pass, 157 MB) under the canonical render root, dir
`agbench_23c-2026-11-23`.
