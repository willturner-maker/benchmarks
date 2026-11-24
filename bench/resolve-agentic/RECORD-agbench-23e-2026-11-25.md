# Wave RECORD — agbench-23e-2026-11-25

**What**: wave 1 of the opencode **2.4.1** + davinci-resolve MCP **5.4.3** build series
(live install bumped to tag `79d68de` pre-wave; the 5.4.0 series' two-wave story is closed).
Engine: **Splash 1.7.1**, pinned argv unchanged
(`--max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache
--default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64`), warm cache.
Full 21-task set ×3, 2-lane pairs, order rotated vs 23d (opened T7r1+T7r2, cycled
T8,F2,T1,T2,T3,F1; F1r3 solo). Driver v2.2 unchanged.

**Label note (disclosed)**: the wave/fixture label says **2026-11-25**; actual dispatch was
**2026-11-24 09:29–09:51 local**. Fixture `_mcp_AGBench-2026-11-25e`, results dir, GT, and
claims all carry the same label consistently — the series stays diffable, the label is just
one day ahead of the calendar day.

**Fixture**: `_mcp_AGBench-2026-11-25e` — `build_fixture_effort_ab.py --fresh`, gt+prestate
sealed at build, archive siblings purged pre-dispatch (`purge_fixture_archives.py`, 14→10,
logged), grader GT `ground_truth-_mcp_AGBench-2026-11-25e-16f.json` derived. Kept loaded
after the wave (parked-fixture policy).

**Pre-wave probes (committed before dispatch, `f0b590f`)**:
1. **MCP fingerprint** (sealed method): live tree at 5.4.3, `server_py_sha256 8a9e61e9…`
   (5.3.4 anchor `1d061c96…`), `server_py_lines` 36689 vs 36542 → new build series by
   definition; registry/action-branch diffs in `mcp-fingerprint-post5.4.3.json`.
2. **ripple_insert #389 continuity probe PASS** (`probe_543_ripple_insert.py`, direct stdio
   JSON-RPC, dry-run only): ambiguous `record_frame 108100` on a T1 starting at 108000 →
   **refused `AMBIGUOUS_RECORD_FRAME`** (5.4.0 planned 216442 with `success:true` — the trap
   that invalidated F2r2's first execute in 23d is gone); `mode:'absolute'` → clean plan
   echoing `insert_frame_absolute 108100 / insert_frame_relative 100 /
   timeline_start_frame 108000 / record_frame_mode_used absolute`.
   api_truths row flips trap→refusal for the 5.4.3 series, pre-registered.
   Note: the probe's first attempt *through opencode* confabulated every MCP tool name and
   self-declared the pool empty — the documented model-side mechanism (see 23d addenda /
   opencode#65932 closure) caught live; the server-side claim is instrumented harness-free.

**Window**: ~22 min wall (23c 24.0, 23d 26.5) — fastest wave of the series. Tenancy: engine
samples in-wave, no congestion.

**Result**: raw **21/21**, corrected **21/21** — first wave in the series with **zero
invalid sessions and zero operator re-runs**. Series band across three waves: raw
{19,19,21}/21, corrected {21,21,21}/21; zero genuine model misses in 63 same-harness trials
(two build series).

**Watchdog/confabulation scoreboard (new framing after the #65932 closure)**: 34 flagged
mangled-name attempts across **5/21 sessions** (T7r1:2, T7r3:3, T3r2:4, T8r2:23, T8r3:2) —
but **zero session deaths**. Three sessions confabulated at the probe stage only and were
killed+restarted before task start (T8r2 attempts 0+1, T8r3 attempt 0 — preserved as
`sessions/<name>-attempt<k>-probe-dead/`); the other two self-recovered mid-session.
Contrast 23c (81 flagged, 2 invalid) and 23d (50 flagged, 2 invalid). With the mechanism
reframed as model-side name confabulation, the restart-at-probe policy converted what would
have been 2 invalids into PASSes. Seal audit: **0 real leaks across 24 sessions**; every
flag is a harness-side `No tool named` rejection (never reached the server);
`cross_project_placements {}`.

**Behaviour observations**:
- **F2 link-repair**: 0/3 `set_clips_linked` again — 0/9 across three waves; watch item closed.
- **F1 off-by-one disclosure**: 3/3 F1 trials quoted the tool's own warning "source start
  reads 5999, not 6000" and left it unrepaired — consistent friction for
  `replace_source_range` on 5.4.3 (property-level api_truths row, not a grading miss).
- **Value-level read-backs** held again (CDL numbers quoted before/after; F2r2 volunteered a
  read-back-ordering caveat unprompted).
- **T7**: 3/3 rendered + verified on disk (16.4/16.4/15.4 MB under the canonical render root)
  — no render storm in any of the three waves.
- **Intrusions**: current-timeline theft observed and disclosed by all three F1 sessions +
  F2r2 (unpinned misreads read-only, pin-then-read discipline held); zero cross-timeline writes.
- **Wall times**: per-trial median 96.7 s (23c 108.1, 23d 100.6); 376 turns / 582 tool calls.

**Engine note (recorded at the wave boundary, per house rule)**: Splash **1.7.2 released
mid-wave** (2026-11-24) — **deliberately not adopted**. Their own upgrade notes warn of
output drift on 32+ core Apple10 GPUs (wide-format projection split order changes at
near-ties) and INT8 Q8_0-activation prefill changes on long prompts, plus a named cold
SSD-cache reset for Qwen3.8-Flash-Next. No correctness/capability gain for our subject;
adoption would open a new series in every suite for free. The one genuinely attractive item
is agent prompt-cache reuse (heads reused on cwd/git change, `--persistent-cache` now covers
system+tools) — candidate for a future *deliberate* engine-efficiency wave, not a silent bump.

**How to relaunch** (fresh `--fresh` fixture name required):
```
python3 build_fixture_effort_ab.py --project _mcp_AGBench-<next> --fresh
python3 purge_fixture_archives.py _mcp_AGBench-<next>
python3 derive_grader_gt_16f.py _mcp_AGBench-<next> --wave agbench-<next>
python3 wave_driver_f1f2_opencode_v2.py --tl-base _mcp_AGBench-<next> \
    --out results/agbench-<next> --render-root <RUNBOOK §3 path> --order "<rotation>"
python3 grade_f1f2_wave.py --wave results/agbench-<next> \
    --claims claims-agbench-<next>.json --gt ground_truth-_mcp_AGBench-<next>-16f.json \
    --render-root <same path> --out results/agbench-<next>/grading.json
```

**Artifacts**: raw wave (sessions incl. 3 probe-dead attempts, `wave_results.json`,
`grading.json`, `harness_log.jsonl`, `engine_samples.jsonl`) under
`results/agbench-23e-2026-11-25/` — gitignored; published distillation is
`results-agbench-23e-2026-11-25.json` + this RECORD + claims at suite root.
