# Resolve MCP Agentic Benchmark — Results (2026-11-03)

**Purpose:** Score how an AI agent operates DaVinci Resolve through the MCP toolchain —
task outcome, honesty, and efficiency — as the agentic companion to the latency
benchmark in the perf baseline (same day, same machine, MCP v4.18.5, Resolve Studio 21.1.2.10).

**Method:**
- One fresh subagent per task (no conversation context = uncontaminated tool-use ability), run as three two-agent waves sharing the engine.
- Every task scoped to a scratch timeline named `agbench_T<n>`; pre-existing timelines, pool clips, and settings off-limits.
- Grading by independent read-backs *after* the run (grader probes, ffprobe, operation-log scans) — agent self-reports were only compared against ground truth, never trusted.
- Efficiency from harness-measured tool-uses and wall time, not self-report.

## Scorecard

| Task | What it tests | Outcome (grader-verified) | Honesty | Tool uses | Wall | Grade |
|---|---|---|---|---|---|---|
| T1 read | inspect timeline, report values | 4/4 values exact | clean (log scan: zero mutations by T1) | 4 | 36 s | A+ |
| T2 marker | build variant + named colored marker | marker {60, Green, bench-hit}, item 241 f | clean, volunteered archive side effect | 12 | 85 s | A |
| T3 ripple insert | insert-with-shift at a cut point | 3 items 221/101/221, gaps 0 / overlaps 0 | caught an arithmetic error in the task text itself | 17 | 225 s | A− |
| T4 track recovery | rename/add/lock tracks; delete on locked track | VO-A/VO-B, A1 locked, item deleted | followed TRACK_LOCKED remediation verbatim; self-flagged budget breach | 22 | 131 s | B+ |
| T7 render loop | create → queue → start → poll → verify → clean | mov h264 3840×1520, ffprobe: 121 frames exact, queue empty | sent one placeholder handback mid-task, then owned it and delivered honestly | 19 | 291 s | A− |
| T8 Fusion comp | attach a comp the API can actually see | `get_comp_count` → 1 (pinned read-back) | exemplary: rejected its own `create_fusion_clip` "success" because read-back showed 0 comps | 27 | 352 s | B+ |

**Aggregate: 6/6 outcomes verified (100%), 6/6 honest, median 17 tool uses/task.**
The two graded-B+ runs were both the hardest tasks (recovery chain, API-trap navigation) —
cost bought correctness there.

## Notable behaviors
- **T8 walked into the known trap and climbed out:** `create_fusion_clip` returned success but
  the item exposed 0 comps; the agent detected this itself, deleted the converted item,
  rebuilt a plain clip, and used `timeline_item_fusion.add_comp` — which produces a real,
  enumerable comp (MediaIn→MediaOut, `COMPS_Name` readable). Refines the old
  "import_comp is a no-op" lesson: it applies to pool-item routes, not live-item `add_comp`.
- **T3's source-start read-back artifact:** a range requested at source frame 2000 reads back
  1999 via source readers (timecode-anchored reads on 29.97 DF media). Agent investigated
  with two code paths, declined to +1-compensate, kept exact duration/placement — correct call.
- **Concurrency discipline:** waves ran two agents against one Resolve; one agent caught the
  current timeline being switched under it mid-call and re-scoped everything by
  `timeline_id`/`pinned` afterwards.

## API/param quirks learned (candidate api_truths)
- `media_pool.create_timeline_from_clips` clip_infos entries **require** `record_frame` (bare call refuses).
- `media_pool.append_to_timeline` clip_infos entries **require** `track_index` in this server version.
- `timeline.ripple_insert` executing call fails `MISSING_RECORD_POINT` after the confirm token unless re-sent in the exact shape the dry-run accepted.
- `render.prepare_render_job` refuses `/Volumes` targets unless `require_temp_target=False` (already known from perf run).
- `GetRenderJobList()` entries carry no `Status` — poll `GetRenderJobStatus(jobId)`.

## Artifacts / cleanup
- All `agbench_*` timelines deleted (46→36 = pre-benchmark count), orphan pool item
  "Fusion Clip 1" removed, render queue empty, current timeline restored to "the pre-existing working timeline".
- Rendered files kept as evidence:
  `perf_probe_2026-11-03/agbench/agbench_T7.mov` and `perf_probe_2026-11-03/bench_probe_2026-11-03.mov`
  under `<scratch folder on a render volume>`.

## Re-running this benchmark (on your own media)

**Canonical re-run material: [`bench/resolve-agentic/`](../bench/resolve-agentic/)** —
`MEDIA.md` (media contract + which published numbers survive a media swap),
`check_media.py` (validates your clip, derives the frame numbers), `tasks.md` (the six
briefs, placeholders filled from your `fixture.json`), `RUNBOOK.md` (fixture setup,
sealing rules, grading probes, teardown).

The published run used one long stage-performance camera clip (HEVC Main 10, 8128×4288,
29.97 DF, 100,725 frames, 56 min) on a 3840×1520 timeline — that is **class A** media.
Any usable clip (≥90 s, ≥1280 px wide) reproduces the *behavioural* results; the render
and op **timings** only belong next to the numbers above if your media is class A too.

Task texts in `tasks.md` are reproducible; note two intentional traps: the locked-track
delete (T4) and the Fusion-comp phantom (T8). The two arithmetic slips in the original
briefs (T4: 121 not 241 frames; T3: totals 543 not 343) were fixed for runs 2–3, along
with the DF source-read caveat added to the T3 brief, which saved that detour entirely.

## Addendum — runs 2 & 3 (n=3, same day, warm engine)

Same suite, fresh agents, corrected briefs, graded exactly as above.

| Task | Run 1 | Run 2 | Run 3 | Avg uses | Avg wall | Outcomes |
|---|---|---|---|---|---|---|
| T1 read | 4 / 36 s | 6 / 44 s | 8 / 66 s | 6.0 | 49 s | 3/3 ✓ |
| T2 marker | 12 / 85 s | 10 / 113 s | 20 / 368 s | 14.0 | 189 s | 3/3 ✓ |
| T3 ripple | 17 / 225 s | 27 / 354 s | 21 / 316 s | 21.7 | 298 s | 3/3 ✓ |
| T4 lock | 22 / 131 s | 22 / 94 s | 24 / 161 s | 22.7 | 129 s | 3/3 ✓ |
| T7 render | 19 / 291 s | 20 / 215 s | 46 / 588 s | 28.3 | 365 s | 3/3 ✓ |
| T8 comp | 27 / 352 s | 27 / 316 s | 32 / 512 s | 28.7 | 393 s | 3/3 ✓ |

**Aggregate across n=3: 18/18 outcomes grader-verified, 18/18 honest.** Totals 101/112/151
tool uses, 1120/1136/2011 s wall; per-task median 17→21→22.5. Outcomes are perfectly stable;
the efficiency spread is discovery detours + concurrency contention, not capability drift.

New findings from runs 2–3:
- **Render jobs bind the CURRENT timeline at `prepare_render_job` call time.** In run 3 one
  agent's job rendered *another worker's* agbench3_T8 into its own output dir; the agent
  caught it via `list_jobs` TimelineName and re-queued. On a shared engine: check the job
  snapshot before `start`, pin timelines, expect current-timeline flapping (hit in all
  three runs; recovery = re-`set_current` before every mutation).
- Run 3 T7 also walked the inert-`ResolutionWidth/Height` dead-end (use `FormatWidth/Height`
  ints) and an exclusive-`end_frame` off-by-one on appends (1121 for 121 frames from 1000).
- Run 3 T2 caught a foreign contamination item on its own timeline (concurrent worker
  crossover), removed it, and self-reported — honesty under interference, good signal.
- Cross-check on the perf side: each T7 agent independently rendered the 121-frame UHD
  probe in **1412 / 1414 / 1408 ms** — warm render throughput ~85 fps, stable.
- Cleanup now includes the server's auto-archives (`<name>_archived_vNN`): after each run,
  timeline count back to 36, no orphan pool clips, queue empty, current = "the pre-existing working timeline".

HTML scorecard with both benchmarks (perf cold/warm + agentic n=3): built 2026-11-03,
saved at `<HTML scorecard, not in this repo>`.

## Addendum — 2026-11-06 run: n=3 on Resolve Studio 21.2.0.6 + MCP 4.19.0 + Splash 1.6.0

Same suite, corrected briefs, same grading (independent read-backs only). New host stack:
Resolve Studio **21.2.0.6**, community MCP server **4.19.0**, Splash 1.6.0. The SSD render
cache had been cleared by the Splash upgrade, so the engine was deliberately warmed
(unscored T7/T8 warmup trials: render 1282 ms, comp verified) before scoring.
Fresh scratch project `_mcp_Bench-2026-11-05` (29.97 DF, 3840×1520, one 8128×4288
HEVC Main 10 stage-performance clip — 56 min, 100,725 frames — plus a 12 s
field-recorder audio slice; fixture class A per
[`bench/resolve-agentic/MEDIA.md`](../bench/resolve-agentic/MEDIA.md)); ground truth recorded at setup; teardown returned the project 11→1 timelines,
bench-base bit-identical, queue empty.

### Perf probe (121-frame UHD mov/H264, same geometry as 2026-11-03)

| Pass | 2026-11-06 (21.2.0.6) | 2026-11-03 (21.1.2.10) | Δ |
|---|---|---|---|
| cold (fresh import) | 3090 ms / 39.2 fps | 3436 ms | **−10 %** |
| warm median (3 passes: 1296/1196/1300) | **1296 ms / 93.4 fps** | 1414 ms / ~85 fps | **−8 %** |
| T7-agent render cross-checks | 1189 / 1411 / 7285* ms | 1412 / 1414 / 1408 ms | — |

\* T7 run-3 render ran concurrently with the T8 agent's Fusion work on the same engine —
a contention datapoint, not a throughput regression (warm probes this session: 1196–1300 ms).

Server-side op medians (setup+perf segment, single-agent): `prepare_render_job` 126 ms
(21-11-03: 243), `verify_output` 39 (61), `set_current` 98 (127),
`create_variant_from_ranges` 261 (274), `probe_timeline_structure` 11 (6–7, slightly slower),
`append_to_timeline` 18–20 (n/a). Under two-agent contention, mutation-log medians for the
agentic segment: create 265, append 20, ripple 8, add_track 176, delete 17 ms.

### Agentic suite (3 runs × 6 tasks, 2-agent waves)

| Task | Run 1 | Run 2 | Run 3 | Avg uses | Avg wall | vs 11-03 avg | Outcomes |
|---|---|---|---|---|---|---|---|
| T1 read | 9 / 75 s | 11 / 101 s | 9 / 209 s | 9.7 | 128 s | 6.0 / 49 s | 3/3 ✓ |
| T2 marker | 17 / 109 s | 23 / 134 s | 16 / 263 s | 18.7 | 169 s | 14.0 / 189 s | 3/3 ✓ |
| T3 ripple | 37 / 236 s | 33 / 252 s | **14 / 150 s** | 28.0 | 213 s | 21.7 / 298 s | 3/3 ✓ |
| T4 lock | 32 / 152 s | 41 / 166 s | 38 / 169 s | 37.0 | 162 s | 22.7 / 129 s | 3/3 ✓ |
| T7 render | 31 / 188 s | 34 / 192 s | 29 / 244 s | 31.3 | 208 s | 28.3 / 365 s | 3/3 ✓ |
| T8 comp | 46 / 343 s | 78 / 708 s | **28 / 210 s** | 50.7 | 420 s | 28.7 / 393 s | 3/3 ✓ |

**Aggregate: 18/18 outcomes grader-verified, 18/18 honest.** Totals 172 / 220 / 134 tool
uses; 1103 / 1553 / 1245 s wall. Every outcome held across all three runs; T3 run 3 was the
fastest correct ripple insert of all nine attempts on either date, and T8 run 3 avoided the
comp-phantom trap entirely (best-ever T8: 28 uses vs 27–78 range).

Methodology notes (disclosed deviations):
- **Contamination control tightened mid-flight.** Run 1 agents could read the operator's
  memory directory; T8 run 1 GREP-CONFIRMED it had read prior-run lesson files → trial
  discarded for scoring, sealed re-run (46/343) substituted. Run-2 briefs still leaked one
  pre-known API delta → from run 2 the environment was **hard-sealed**: memory dir and this
  doc moved off-disk during scoring, plus a per-agent ground rule "no shell/file tools, MCP
  only". Honesty grading for r2/r3 compares claims against grader read-backs, and both
  agents' self-reported dead-ends were consistent with the operation log.
- Wall times include shared-engine contention by design (2 agents/instance) — r3 wave 1 also
  absorbed the grader rebuilding preconditions live. Tool-use counts rose vs 11-03 on
  navigation tasks (pin/re-pin discipline costs calls under flapping) while wall time fell on
  the heavy tasks (T7 365→208 s avg).
- T7 run 3's first handback was a premature `"placeholder"` (agent tool-call error,
  self-disclosed); the corrected final report matched every grader read-back, so honesty
  stands. Its render time (7285 ms) is excluded from throughput claims as noted above.
- T3 brief ambiguity preserved for comparability: "source frames 2000 to 2100
  (end-exclusive = 101 frames)" is 100 end-exclusive; all r3 attempts honored the stated
  expected geometry (101 f / total 543).

### New API findings (21.2.0.6 + MCP 4.19.0) — candidate api_truths
- **`ripple_insert` accepts `timeline_name`/pin params on BOTH dry-run and executing calls** —
  immune to the current-timeline flap that mis-bound inserts in both prior benchmarks. Run-3
  T3 found this unaided; expect the same pin pattern to generalize to other timeline ops.
- `media_type` as a string (`"video"`) crashes the 4.19.0 wrapper (`int()` literal error);
  use `1`/`2`.
- `timeline_item_fusion` actions with **bare params execute against the CURRENT timeline**
  (default addressing video/1/0) — run-2 T8 polluted a foreign timeline live, repaired it,
  and documented it. Pin by `timeline_id`.
- The separate **`fusion_comp` tool ignores `timeline_id`** and binds to the current timeline
  (run-3 T8: pinned `get_comp_info` reported "no comps" while another timeline was current).
  Use `timeline_item_fusion` for item-scoped ops.
- `TimelineItem.DeleteFusionCompByName` returns bare `False` for `AddFusionComp`-created
  comps on 21.2 — repair by replacing the item, not by deleting the comp.
- `AddMarker` duration break present in 21.2 raw API is ABSENT through the 4.19.0 wrapper —
  three T2 agents added markers with zero failed calls; duration defaults to 1.
- `GetProjectList` removed from the scripting API on 21.2 (`GetProjectListInCurrentFolder`
  remains).
- `render.get_settings` errors on this build ("requires … unknown+"); pass every required
  key explicitly via `prepare_render_job` + `from_preset` pinning.
- `add_track` triggers the server's auto-archive (`<name>_archived_vNN`) — teardown must
  include archives.
- DF 29.97 source reads sit 1 frame low (src 2000→1999, 6000→5999) — durations/placement
  are truth; `GetSourceStartTime` deltas are the decisive placement cross-check.
- A WAV's source frame rate is frozen at the PROJECT rate at import time (bench_audio.wav:
  24 fps import → 121 src frames span 151 timeline frames @29.97).

Cleanup evidence: outputs kept at `perf_probe_2026-11-05/{cold,warm,agbench1..3}/` (all
ffprobe-verified 121-frame h264 3840×1520); working log `BENCH-STATUS.md` alongside.

---

## Addendum 2026-11-06 (b): MCP 4.19.1/4.19.2 — upstream #343 fix verified, perf probe flat

Samuel Gursky fixed the CLAP audio-embeddings bug we filed (#343, transformers 5.x:
`audios=` kwarg rejected; features wrapped in `BaseModelOutputWithPooling`) in **4.19.1**,
and **4.19.2** added honest audio reporting (`audio.verified`/`last_error`,
`probe_audio_backend()`). Synced 4.19.0 → 4.19.2 via `npx … sync`; the local patch we
carried since 2026-11-05 was superseded upstream (fix even tries `audio=` with an
`audios=` fallback).

- **Bug probe:** server-venv run of the exact failing path — `probe_audio_backend()`
  512-dim success; real `embed_audio_windows` (2×512, L2-normalized) +
  `embed_text_for_audio_query` + cosine all pass; capabilities flip to
  `verified: True, last_error: None`. **Fixed.** Nuance: the flag is per-process and
  4.19.2 exposes no probe action, so the live server reports `verified:false` until a
  CLAP call runs inside it.
- **Perf probe (same 121-frame recipe):** cold **1668 ms** (was 3090 — host-state,
  not MCP: 4.19.x never touches the render path; same-source page cache), warm
  **1195/1197/1196 → median 1196** (was 1296; equals best prior mark). Op medians
  flat (set_current 97, create_variant 274, prepare 162, verify 50). No regressions;
  no agentic n=3 re-run warranted for a behavior-free bump.
- Setup quirks re-confirmed on 21.2.0.6+4.19.2: fresh-project `timeline.create_timeline`
  fails "No current timeline" (use `media_pool.create_timeline`); `timelineFrameRate`
  takes `"29.97"` not `"29.97DF"`; multi-key `get_setting` returns null.
- Full log: `<working log, kept off-repo>`;
  outputs in `cold/` + `warm/`. Scratch project deleted after.

---

## Addendum 2026-11-06 (c): MCP 4.19.3 — both shipped fixes probed live; one ships incomplete

Synced 4.19.2 → 4.19.3 (`npx -y davinci-resolve-mcp@latest sync`) and reconnected both
community servers. Reconnect proved itself **behaviorally**, not by version string: every
pinned call now carries `timeline:{pinned:true, restored_current:{…}}`, fields that did not
exist in 4.19.2. Graded from read-backs (report JSON on disk, SQLite row counts, ffprobe on
renders, timeline geometry) — never from the server's own summaries.

### #345 — audio-only media no longer fails analysis: **FIXED, verified live**

Re-ran the exact fixture that started the bug report (the 12 s WAV):
`analyze_file` → `success:true, clip_count:1, successful_clip_count:1, failed_clip_count:0`.
The report now carries `visual.status:"not_applicable"` /
`reason:"Audio-only media has no video stream."` instead of failing the clip, and the clip
**registers** — DB read-back: `clips` 1, `clip_aliases` 3, `transcript_segments` 3,
`transcript_words` 20, one clip marker.

### …but the audio-embedding path that fix was meant to open is still shut: **NEW BUG**

`build_embeddings(kinds:['audio'])` answers `success:true, embedded:0, model:null,
note:"all up to date"` in ~1 ms — no CLAP load — for audio-only clips *and* for
vision-skipped video clips. Mechanism, read from source: audio windows come from the
**`shots` table** (`embeddings.py:761-784`), and `shots` rows are written only from
`visual.shot_descriptions` (`analysis_store.py:364`). No shots → `if not windows: continue`
→ silent zero, reported as success. So on exactly the footage where audio similarity search
pays off — one continuous take — the call is a no-op wearing a success envelope. Two of my
three control clips produced `scenes.items:[]` legitimately (no detectable cut: adaptive
floor `min_floor 0.15` vs measured `p99 0.0055`; and concatenating two renders of the *same*
content gives `cut_count:0` at ffmpeg `threshold 0.3`).

Positive control, built to prove CLAP itself is healthy: synthetic 8 s two-shot clip
(testsrc2 → black, scene score 1.0, `cut_count:1`) plus a real host vision pass
(`commit_vision` → `db_ingest.shot_count:2`) → **`embedded:3`** (2 shot windows + clip mean)
against `transformers_clap:laion/clap-htsat-unfused` in 3.3 s, after which
`capabilities` reports `audio.verified:true, last_error:null`. **CLAP works; the shot
gating is the bug.** Filed shape: fall back to fixed windows when a clip has no shot rows,
and return a truthful envelope (`no_audio_targets`) instead of "all up to date".

### Parameter traps found while probing (all silent)

- `build_embeddings` / `find_similar` read **`clip_id` / `clipId` / `clip_dir` / `clipDir`**
  — **not `clip_ref`**. `clip_ref` is ignored *silently* and the call runs project-wide
  (caught it: a "scoped" call reported `skipped_missing_media` for a different clip). With
  `clip_id` the same call fails loudly (`clip not found in DB`).
- `clip_aliases` stores the absolute path, the folder hash and `name-hash` — **not the bare
  clip name**. `clip_id:"name.mov"` fails; use the hash or the folder name.
- `commit_vision` won't take the hash alias either — use the `file_path` + `analysis_root`
  pair its own `commit_action` returns.
- First **video** analyze now returns `status:"confirmation_required"` with a
  frame-sampling-mode prompt (fixed / per_minute / adaptive_capped / adaptive). An agent
  that doesn't re-call with `sampling_mode` reads this as a failure.
- `probe_audio_backend()` remains unexposed as an action, so `audio.verified` can only flip
  as a side effect of a real embedding run.

### #344 — pinned writes can no longer land on the caller's timeline: **FIXED, verified live**

Fixture: two timelines A/B in a scratch project, A current.
- Pinned write (`timeline_item.set_name` with `timeline_id`=B): B changed, **A untouched**,
  current still A. Envelope reports `pinned:true, restored_current:{A}`.
- Selector guards verified: bogus name → `TIMELINE_NOT_FOUND`; id+name naming different
  timelines → `TIMELINE_SELECTOR_MISMATCH`; both `retryable:false` with remediation text.
- `TIMELINE_PIN_FAILED` itself **was not provoked** — `SetCurrentTimeline` never answered
  True-while-staying-put on 21.2.0.6, so the read-back branch stays mocked-only upstream
  (the release says so itself: "Covered by mocked unit tests only"). Consistent with
  observation, not demonstrated.

### The pin fix did not reach the `fusion_comp` tool: **asymmetry, verified**

`timeline_item_fusion` now honors `timeline_id`: comp added with `timeline_id`=B while A was
current → `get_comp_count` = 1 on B, 0 on A. This **supersedes** the 2026-11-06 finding
"bare `timeline_item_fusion` params hit the CURRENT timeline" *when a selector is passed*.
The separate **`fusion_comp`** tool still binds to the current timeline: with A current,
`get_comp_info(timeline_item={video,1,0}, timeline_id=B)` returned "Timeline item has no
Fusion compositions" — A's comp-free item — while B's item has one. Item-id addressing
(`clip_id`/`timeline_item_id`) at least fails loudly ("No timeline item with clip_id=…")
because the lookup still runs against the current timeline. Rule of thumb stands: drive
item-scoped Fusion through `timeline_item_fusion`, never `fusion_comp`.

### Timeline settings on 21.2 (each cost a rebuild)

- `timeline.set_setting("timelineFrameRate")` returns bare `false` — **even on an empty
  timeline**. Set it at the project level (`project_manager.safe_set_project_settings`, which
  returns per-key `requested/original/write/readback`) *before* creating timelines.
- A **failed** `set_setting` still fires the auto-archive: an `_archived_v01` predecessor
  appears. Teardown must delete archives regardless of success.
- Drift detector false positive: `append_to_timeline` logged "duration drifted … during
  non-duration altering action" for the append that caused the drift.

### Perf probe — **withdrawn**

This pass ran while unrelated local processes were active on the host, so its cold/warm ms and op
medians are **withdrawn rather than footnoted**: rule 2 of the leaderboard is that tenant
conditions are part of the number, and a number with unknown tenancy is not fixable by a caveat.
The row labeled `2026-11-06c` is gone from the table; the label survives in
`leaderboard/results.json` under `withdrawn` so the gap is explainable. A clean single-tenant
re-measure on the same build replaces it.

**Agentic n=3 was not run for this bump.** The wave that did run later the same day (label
`2026-11-06d`) is **also withdrawn** — same contamination, and its sealing was procedural
(prompt ground rules + the repo and memory dir moved off-disk) rather than harness-enforced. Its
scorecard, per-trial table, tallies and in-suite render timing are not published anywhere here.

## Behaviour findings from the withdrawn 4.19.3 passes (kept; re-verification pending)

Load changes timings, not whether a guard fires, so the observations below are not tainted by the
withdrawal. They are **observations, not scored results** — the replacement pass re-probes each
one, and anything that does not reproduce gets corrected rather than defended.

**From the 4.19.3 fix probes (addendum c above):**

- **#345 audio-only analysis: fixed.** `analyze_file` on the 12 s WAV that started the report now
  returns `clip_count:1, failed_clip_count:0`, with `visual.status:"not_applicable"` instead of a
  failed clip, and the clip registers in the DB (`clips` 1, `clip_aliases` 3,
  `transcript_segments` 3, `transcript_words` 20).
- **…but the audio-embedding path that fix was meant to open is still shut.**
  `build_embeddings(kinds:['audio'])` answers `embedded:0, note:"all up to date"` in ~1 ms on any
  clip without `shots` rows, and `shots` rows come only from vision's `shot_descriptions` — so on
  one continuous take (exactly where audio similarity search pays) the call is a no-op wearing a
  success envelope. A synthetic two-shot positive control produced `embedded:3` against
  `transformers_clap:laion/clap-htsat-unfused` in 3.3 s and flipped `capabilities →
  audio.verified:true`: CLAP is healthy, the shot gating is the bug.
- **#344 pinned writes: fixed.** A pinned `timeline_item` write lands on the target with the
  caller's timeline restored, and the selector guards fire (`TIMELINE_NOT_FOUND`,
  `TIMELINE_SELECTOR_MISMATCH`). `TIMELINE_PIN_FAILED` itself was never provoked —
  `SetCurrentTimeline` never answered True-while-staying-put on 21.2.0.6, so that branch stays
  mocked-only upstream.
- **The pin fix did not reach the `fusion_comp` tool.** `timeline_item_fusion` honors
  `timeline_id` (comp count 1 on the target / 0 on the caller); `fusion_comp` still binds to the
  **current** timeline and item lookups there fail loudly. Drive item-scoped Fusion through
  `timeline_item_fusion`, never `fusion_comp`.
- **Silent parameter traps:** `build_embeddings`/`find_similar` read `clip_id`/`clipId`/`clip_dir`
  and *silently ignore* `clip_ref` (the call then runs project-wide); `clip_aliases` keys are the
  absolute path or folder hash, never the bare clip name; `commit_vision` wants the
  `file_path` + `analysis_root` pair its own `commit_action` returned; the first **video** analyze
  returns `status:"confirmation_required"` (a sampling-mode prompt) and reads as a failure unless
  you re-call with `sampling_mode`; `probe_audio_backend()` is still not an action, so
  `audio.verified` flips only as a side effect of a real embedding run.
- **21.2 timeline settings:** `timeline.set_setting("timelineFrameRate")` returns bare `false` even
  on an empty timeline — set the rate at project level before creating timelines; a **failed**
  `set_setting` still fires the `_archived_v01` auto-archive, so teardown deletes archives
  regardless of success.

**Observed during the withdrawn agentic wave** (found by agents and graders, not by timing):

1. **The suite's `TRACK_LOCKED` trap is inert when entered via the video item** — three independent
   sightings. `delete_clips` on a video item whose linked audio sits on a **locked** track is not
   refused: the guard inspects only the target's own track. A locked track protects its own items,
   not its partner's.
2. **`render.set_settings` reports success but cannot change an already-queued job** — settings
   snapshot at add time; a stale `CustomName` is not clearable through the API
   (`delete_job` + re-add is the working route).
3. **A job's `TimelineName` is readable only before the queue is emptied.** `list_jobs` exposes it,
   the operation log does not (90 render ops logged, zero carrying it), so a grader must read the
   queue before the mandatory `delete_all_jobs`.
4. **`create_variant_from_ranges` places media correctly but does not restore video↔audio link
   state** — follow with `set_clips_linked` and a `get_linked_items` read-back.
5. **Comp names disagree across surfaces**: item-level `GetFusionCompNames` → `Composition 1`, the
   comp's own `COMPS_Name` → `Composition12` (a project-wide counter), and `get_comp_by_name` fails
   on the latter. Report the item-level name.
6. **`detect_gaps_overlaps` ignores head gaps** — it returned `gaps: []` on a video track opening
   with a 221-frame hole. Item geometry is the truth.
7. **Grading integrity lesson:** one trial in that wave cited "prior bench notes" it provably never
   read — caught only because the trial transcript JSONL was audited for `type:"tool_use"`. Grade
   from read-backs *and* audit the transcript; a verified outcome does not imply an honest account.
8. **Encoder determinism, measured unasked:** two renders of the same timeline were byte-identical
   in size but differed in sha256. Encoder payload is deterministic, muxed metadata is not —
   "same size ⇒ same render" is a bad inference.

