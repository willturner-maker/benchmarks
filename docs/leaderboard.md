# Leaderboard

Version-to-version standings for the local AI/editing stack. Machine-readable source:
[`leaderboard/results.json`](../leaderboard/results.json) — this page is its rendered view.

**Three rules before you read or add a row** (they're what keep a leaderboard honest):

1. **Same media class or different table.** Render ms from class B media (anything that
   isn't the [class A](../bench/resolve-agentic/MEDIA.md) equivalence class) go in the
   community table below, never alongside class A rows. A 1080p H.264 render being
   "faster" than an 8K HEVC one says nothing about the toolchain.
2. **Tenant conditions are part of the number.** Single-tenant renders only; two-agent
   waves inflate render ms (one published T7 render came in at 7285 ms because another
   agent was doing Fusion work on the same engine).
3. **Read-backs, not claims.** A row is admissible only if every value came from an
   independent probe — ffprobe on the output file, timeline item geometry, the server's
   operation log. Agent self-reports never enter a cell.

## Resolve MCP — class A media, reference host

Reference host for all rows: Apple M5 Ultra (64-core GPU), 96 GiB unified memory,
macOS 27.2, render output and scratch on external volumes.

| Date | Resolve | MCP | cold render | warm median | warm fps | prepare | verify | set_current | probe | agentic outcomes | honest |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-03 | 21.1.2.10 | 4.18.5 | 3436 ms | 1414 ms | ~85 | 243 | 61 | 127 | 7 | **18/18** | 18/18 |
| 2026-11-06 | 21.2.0.6 | 4.19.0 | 3090 ms | 1296 ms | 93.4 | 126 | 39 | 98 | 11 | **18/18** | 18/18 |
| 2026-11-06b | 21.2.0.6 | 4.19.2 | 1668 ms¹ | **1196 ms** | 101 | 162 | 50 | 97 | 11 | n/a² | n/a |
| **2026-11-06e** | 21.2.0.6 | **4.19.3** | 1670 ms | **1191 ms** | **101.6** | 174 | 41 | 109.5 | 18³ | **18/18** | 18/18 |
| **2026-11-10f** | 21.2.0.6 | **5.1.0** | 3116 ms¹ | **1198 ms** | 101.0 | 183 | 47.5 | 112 | 20³ | **18/18** | 18/18 |
| **2026-11-10g** | 21.2.0.6 | **5.2.0** | 1700 ms¹ | **1296 ms** | 93.4 | 162 | 59 | 112 | 268³⁴ | **18/18** | 18/18 |
| **2026-11-11h** | 21.2.0.6 | **5.2.2** | 3129 ms¹ | **1205 ms**⁵ | 100.4 | n/a⁵ | n/a | n/a | n/a³⁴ | **18/18** | 18/18 |
| **2026-11-13i** | 21.2.0.6 | **5.2.2** (same-build repro) | 1303 ms¹ | **1192 ms**⁶ | **101.5** | 155⁶ | 35 | 80 | 13³⁶ | **18/18** | 18/18 |

Render probe: 121 frames, 3840×1520, mov/H.264, queue time excluded
(`TimeTakenToRenderInMs`, file verified with ffprobe). Op columns are server-side
operation medians in ms.

¹ Cold ms is **host state, not an MCP signal** — the community server never touches the
render path, and the cold column has swung 3436 / 3090 / 1668 / 1670 / 3116 / 1700 across six
waves of identical media and settings. Read only the warm column. Warm 1196 (4.19.2)
equals the best prior mark; 5.1.0's 3116 ms cold is the same host-state caveat.
² No agentic n=3 for 4.19.2: the bump was behaviour-free (upstream fix of the CLAP
audio-embedding bug we filed, verified by direct probe the day it shipped).
³ The `probe` column is measured on **base geometry (4 items)**, and `probe_timeline_structure` is
item-count sensitive on this build: 14–20 ms on 4 items, 4–7 ms on a 1-item variant. Comparisons
across rows are only valid at the same item count.
⁴ On 5.2.0 the probe column also picks up a **context-switch cost**: consecutive pinned calls that
*alternate* timelines trigger a baseline_reset/restore lifecycle that costs 265–1113 ms, while the
same-context reads run 10–30 ms (re-measured 14 ms mid-wave). The 268 ms cell is the
alternation-included median from the perf stage and is **not comparable** to the 20 ms above it;
the like-for-like 5.2.0 figure is ~14–30 ms. Filed as an api_truth candidate, not yet upstream.

**Withdrawn rows.** Two 4.19.3 passes carried the labels `2026-11-06c` (perf probe + targeted
behaviour probes) and `2026-11-06d` (agentic n=3). Both were **removed on 2026-11-06**: unrelated
local processes were running during them, so their timing columns are not trusted, and rule 2
("tenant conditions are part of the number") means the honest response is withdrawal, not a
footnote. The labels stay in [`leaderboard/results.json`](../leaderboard/results.json) under
`withdrawn` so the gap is explainable. **The replacement landed** as `2026-11-06e`: the perf probe
ran single-tenant *before* the agent wave (host load sampled first) and the agentic n=3 ran after it,
so nothing could contend with the timing. Read that row, not the withdrawn ones.

Agentic column = six tasks × three fresh sealed agents, graded only from read-backs;
details and per-task cost in
[the results doc](resolve-agentic-benchmark-results.md). The 2026-11-06 runs' agents were
served by the local model (Qwen3.8-Flash-Next IQ3_S via Splash 1.6.0), not a cloud API.

**Regression worth watching:** `probe_timeline_structure` on base geometry went 7 → 11 → 11 → 18 → **20 ms**
across 4.18.5 / 4.19.0 / 4.19.2 / 4.19.3 / 5.1.0 — the 4.19.3 step (7+ ms) is the one to file if it holds;
the 5.1.0 step is +2 ms, inside run-to-run. `verify_output` sits at 47.5 ms (was 41), `prepare` 183 (was 174) —
all op columns flat-to-slightly-up; render ms are flat, as expected for releases that never touch the render path.

**5.1.0 row:** the server installed ahead of the stable channel (5.0.7) and reports `current_ahead`. The tool
surface moved (`append_to_timeline` now lives on `media_pool`) and the wave collected twelve 5.1.0 behavior
notes in [the results file](../bench/resolve-agentic/results-2026-11-10f.json) — three distinct
`record_frame` semantics, the `FormatWidth/Height` vs `ResolutionWidth/Height` render-key trap, a
gate-broken `render.get_settings`, and a now-loud `set_property("Linked")` refusal. Agentic is the third
consecutive clean 18/18 wave (four waves, 72/72 verified + honest aggregate).

**5.2.0 row:** warm 1296 ms sits at the 4.19.0 mark, inside the host-state spread; op medians flat except the
probe cell, which footnote ⁴ explains. The agentic wave is the **fifth consecutive 18/18** verified + honest
(90/90 aggregate) — and the most interesting yet for tenancy safety, because it *caught a hole in our own
protocol*: `append_to_timeline` accepts no timeline pin and silently ignores an extra `timeline_id`, so under
two-agent waves it follows whatever timeline is **current**. In round 3 the two T3/T4 agents each planted real
items on the other's timeline; both detected the cross-writes (one via the server's own drift notice), reversed
them surgically, and disclosed everything — graded verified + honest with incident annotations, live state
confirmed clean by pinned read-backs. New behaviour worth knowing before you hit it: `ripple_insert` runs
**plan-only** when the `dry_run` key is absent; render `TargetDir` is **auto-created** (the suite's mkdir
allowance was never needed); `COMPS_Name` carries a **project-global** comp counter while the item surface shows
a per-clip name (measured `Composition2/3/4` across the three T8 runs); and the in-app bridge's render polling
is blind on this build (`GetRenderJobList` entries carry no `JobStatus`; `IsRenderingInProgress()` reads false
mid-render). Upstream issue #207 (stuck-Ready job) reproduced live and fixed with the known delete-and-requeue
route. See [the results file](../bench/resolve-agentic/results-2026-11-10g.json) for all eighteen 5.2.0 notes.

⁵ **5.2.2 wave honesty notes:** the warm probe ran *concurrent with pair 1* — a deviation from rule 2 that
the operator recorded up front, so the 1205 ms cell is kept but ranked-with-note, not held against the
single-tenant column. Op medians were **not collected single-tenant** this wave; the pinned grading reads
(240–1136 ms) include the baseline_reset alternation lifecycle and would be a different measurement, so
the cells read `n/a` rather than being filled with a non-comparable number.

**5.2.2 row:** 5.2.1/5.2.2 changed no tool surface (21.0.4 method probing; a caption word-wrap fix), and
the wave confirms it: the story is on the agent side, not the server's. Walls came down **−22.8…−37.8 %**
vs the 5.2.0 wave (1484/1517/1729 → 1146/1077/1076 s) with leaner use counts and — for the first time —
**zero cross-agent write incidents**, despite `append_to_timeline` still being exactly as un-pin-able as
before. The wave ran under a **softer seal than published** (session classifier refused the off-disk move;
`chmod go-rwx` fallback, disclosed in the briefs, results and deviations). Two new API truths, both loud
enough to trip an unwary agent: positioned rows **silently ignore `record_frame_mode:"absolute"`** (items
land at wrong frames with `success:true`), and the official in-app `run_script` sandbox **returns `None`
for non-allowlisted API methods** — scripting-based grading is dead on arrival; grade from pinned read-backs.
See [the results file](../bench/resolve-agentic/results-2026-11-11h.json); note its audit-errata history
(review agents corrected three stat errors in the original record — commit `81d77cc`).

⁶ **2026-11-13i — same server build as 11h, methodology wave:** the wave ran from a **standalone python
driver** (`wave_driver.py`) instead of the operator's session, and the operator made zero Resolve calls and
zero model turns during it — the first agbench with **no operator tenancy at all**. The op cells re-open
single-tenant (perf stage before the wave): warm 1192 ms is the best recorded and reproduces the published
1196 within 0.3 %; `set_current` 80 ms shows no alternation lifecycle while the perf stage stays on one
timeline. The probe cell (13 ms, 4 items, same-context) shows the 4.19.3 step-up (18–20 ms) **did not
reproduce** on 5.2.2 — the flag stays open, not called fixed.

**2026-11-13i row:** the **seventh consecutive clean 18/18** (126/126 aggregate), and the split verdict is the
point: with tenancy removed, the placeholder-free tasks ran faster than 11h (T3 walls −27…−48 %,
T4 −25…−41 %, T2 r1 −42 %), while all three T7 runs went 1.5–2.5× **slower** — the briefs' published
`/Volumes/YourVolume` placeholder sent each agent on an honest dead-end hunt (all three named the placeholder
as such and rendered to the real pre-created dirs; T7r3 spent 118 uses surveying six MCP actions before
declaring packet counts unobtainable in-engine, which is exactly the honesty the rubric pays for). Zero
cross-agent write incidents for a second running. The seal came back **hard**, upgraded by necessity: the
strict-MCP config (which carries server env) is built at runtime into a tempfile **outside the public repo**
and deleted on exit — a session classifier rightly refused to persist credentials in the tree, and that
refusal designed the pattern. In-suite render ms (1445/1425/1447) were read by the **agents** before grading
(queue emptied per brief), so they sit in the record but not in a cell. Three new API truths:
`get_clips_linked` is not pin-able (answers `not found` against the CURRENT timeline), `render.set_settings`
silently accepts a bogus `TargetDir` (only `add_job` refuses), and `timeline.duplicate` archives the **source**
fixture — six `_base` archive siblings this wave where 11h had none.
See [the results file](../bench/resolve-agentic/results-2026-11-13i.json).

## Splash engine — reference host

| Date | Engine | Model | TTFT warm | TTFT cold | decode w1 | decode plateau | suspensions at 4.4× KV | agentic | honest |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-06 | Splash 1.6.0 | Qwen3.8-Flash-Next IQ3_S (262k ctx) | 201 ms | 380 ms | 170 tok/s¹ | **372–383 tok/s**, widths 4→32 (2.5–2.6×) | **0** | 11/12 | 12/12 |
| **2026-11-10s** | Splash 1.6.0 (same build) | same | 174 ms | 430 ms | 128 tok/s¹ | **366–369 tok/s**, widths 8→32 (2.4×)² | **0** | **12/12** | 12/12 |
| **2026-11-11h** | **Splash 1.6.1** (INT8 activations default on M5+) | same | 294 ms⁶ | 442 ms | **186.9 tok/s**⁷ | **510–525 tok/s**, widths 12→32 (**+39 %** vs 1.6.0 plateau) | **0** (but +645 disk demotions at w10) | **12/12** | 12/12 |
| **2026-11-12** | **Splash 1.6.1** (assumed — version not exposed by `/status`; see ⁸) | same | **151 ms**⁶ | 355 ms | 205.2 tok/s⁷ | **487–506 tok/s**, widths 12→32 (peak back at w8: 522.7) | **0** at 4.66× — this instance's budget is 131,072 tok⁸ | n/a⁹ | n/a |
| **2026-11-13** | **Splash 1.6.1** (`splash --version` confirms — the ⁸ assumption resolves) | same | 159 ms⁶ | **229 ms** | **209.5 tok/s**⁷ | **470–475 tok/s**, widths 8→32 (peak w12: 475.2)¹⁰ | **0** at 4.66× (budget 131,072 tok)⁸ | **12/12** | 12/12 |

¹ decode w1 is warmth-sensitive — the probe's own three passes trend (105→133→165 baseline,
111→128→136 rerun); the column is the warmed value on the baseline row, the median on the rerun row.
² The rerun rides ~2 % under the baseline plateau at every width — same shape, same dip at 6
(0.87× the width-4 peak both waves), same admission counts. Not a regression claim on one
engine instance; it bounds run-to-run spread for future diffs.

⁶ warm TTFT 294 ms on the 11-11h wave was a **single sample under shared-engine conditions** —
logged as an open flag (contention or real regression). **Resolved by the 2026-11-12 wave: warm
151 ms**, the best warm figure recorded, corroborated by the same wave's ladder w1 (205.2 tok/s,
the highest w1 seen). The 294 ms reads as contention contamination, not a regression; cold
figures stay in band (442/355 vs 380/430 before INT8). The 2026-11-13 clean window corroborates
again — warm 159 ms, and **cold 229 ms**, the best cold recorded.
⁷ decode w1 on both 1.6.1 rows is the **clean ladder width-1** value; the 11-11h `engine_probe`
decode rows (81.6/80.7/149.6) were contention-contaminated by the operator session and are
excluded — see [NOTES.md](../bench/splash-concurrency/results/splash-1.6.1-rerun-2026-11-11h/NOTES.md).
The 11-12 probe was clean (152.8/167.0/148.4, flat walls) and sits at 0.745 × the ladder w1 —
the ladder figure is the comparable one across rows. The 11-13 probe (159.3/173.6/143.3) sits at
**0.760 ×** its ladder w1 (209.5) — the ratio itself reproduces.
⁸ 11-12 wave caveats (full detail in
[NOTES.md](../bench/splash-concurrency/results/rerun-2026-11-12/NOTES.md)): engine version
**assumed 1.6.1** (`/status` schema 8 exposes no version; no reported update since the 1.6.1
install on 2026-11-11); **single-tenant hygiene violated mildly** — the engine also served the
operator's Claude session between messages, with all per-round suspension counters at delta 0
(lifetime 16, all pre-existing), so numbers are kept with this note; the **resident-KV budget is
instance-variable** (131,072 tok here vs 139,264 in 1.6.0 waves), so the KV probe reads 4.66×
not 4.4×; the demote path engaged in three rounds (w6/10/12 = +382/+645/+97) — the busiest
memory path of any wave, still zero suspensions/spills.
⁹ No agentic n=3 this wave — the suite ran `engine_probe.py && ladder_kv.py` from a fresh
terminal only; driver2.py was not run.
¹⁰ **2026-11-13 clean-window run** — the first suite run with **true** single-tenancy: a detached
runner (`bench/clean-run-2026-11-13/run_clean.py`) launched from a terminal, operator session
making zero engine turns during timed stages (the tenancy lesson from the Resolve waves, applied
to the engine suite). Caveats: the driver's warm-up completion 404'd (Splash does not serve
`/v1/chat/completions`) — harmless, the probe's first passes warmed the engine; the KV memory path
ran middling-quiet (waiting_memory holds 72–196 ms at w4/6/10/12, restoring ≤2, spill/demote 0);
prefill wall not re-sampled this wave. agentic n=3 returned: 12/12 + 12/12 (S3 `out.json` exact,
S1/S2 cross-checked against live `/status` counters — monotonic and consistent). The plateau reads
**lowest** of the three 1.6.1 waves despite zero contention — plateau scatter is engine-instance
state, not tenancy; the tenancy tax lives in latency-bound suites (agentic walls), not in
saturated-decode aggregates.

Rerun in one pass: `python3 -I bench/splash-concurrency/ladder_kv.py` (width ladder + KV-pressure
probe, one combined summary). The plateau is a wall, not a cliff; the KV probe's negative
result (no suspension at 611,244 prompt tokens) is a finding, not a missing number — and it
reproduced on **all five waves**, with the memory path's secondary signals shifting wave to wave
(the 11-10s rerun ran quietest; the 1.6.1 waves ran hottest — 11-11h demoted 645 blocks at width
10, exactly the baseline's figure, 11-12 demoted at w6/10/12 with one pacing hold at w10, and the
11-13 clean window ran middling-quiet: small waiting_memory holds at w4/6/10/12 but spill and
demote deltas zero; suspensions and spills stayed zero everywhere).

Cross-hardware context (DGX Spark / RTX Spark / RTX 5090 on the same resident model): the
[comparison section](splash-engine-benchmark-results.md#cross-hardware--the-same-model-on-nvidia-boxes-external-data-2026-11-13).
Those numbers are external, n≈1 and fail rules 2–3, so they deliberately do **not** appear as
leaderboard rows — the section exists precisely to keep them out of the ranked tables while
keeping the comparison on the record.

### Splash width-ladder scores — aggregate tok/s medians, all waves

Same host, same model (Qwen3.8-Flash-Next IQ3_S, 262k ctx), same spec: 512-token rounds, two
rounds per width, median shown. Comparable across rows only because the harness is identical;
1.6.1's INT8 default means numerics are not bit-comparable with the 1.6.0 rows.

| width | 1.6.0 (11-06) | 1.6.0 (11-10s) | 1.6.1 (11-11h) | 1.6.1 (11-12) | **1.6.1 (11-13 clean)** |
|---|---|---|---|---|---|
| 1 | 147.6 | 151.5 | 186.9 | 205.2 | **209.5** |
| 2 | 259.1 | 250.7 | 301.0 | 334.5 | 299.2 |
| 3 | 306.1 | 290.9 | 378.5 | 393.4 | 362.6 |
| 4 | **377.7** ← peak | **369.7** ← peak | 427.5 | 464.3 | 453.3 |
| 6 | 330.4 (0.87×) | 322.4 (0.87×) | 396.9 (0.93×) | 417.6 (0.90×) | 438.1 (0.97×) |
| 8 | 373.9 | 368.7 | 488.4 | **522.7** ← peak | 470.2 |
| 12 | 375.7 | 367.7 | **524.8** ← peak | 487.1 | **475.2** ← peak |
| 16 | 371.9 | 369.1 | 510.0 | 505.7 | 470.7 |
| 24 | 382.9 | 368.8 | 518.5 | 493.1 | 474.5 |
| 32 | 371.7 | 365.5 | 519.8 | 500.5 | 474.4 |

The 1.6.1 plateau is **+39.2 %** mean (per-width +32.5…+42.7 %), but read the shape with it: the
peak moves from width 4 to width 12, the w6 dip gets shallower, and w1 itself rose +23.4 % —
concurrency-normalized (plateau ÷ w1) the gain is only +12.8 %, so most of the headline is
single-stream decode speed. The gain is decode-side (prefill walls: 611k tokens in 170.5 vs
171.1 s — unchanged), consistent with, but not proven by, the INT8-activations default. Stop
rule (halt when median aggregate falls below 1.10× w1) never fired in any wave.

**Three 1.6.1 waves bound the current run-to-run band** (11-11h → 11-12 → 11-13 clean): plateau
(w12–32) means 518.3 → 496.6 → 473.7 (the swing is now −8.6 % end to end), w1
**186.9 → 205.2 → 209.5** (best recorded), the w6 dip flattening 0.93× → 0.90× → 0.97×, peak
position swinging w12 → w8 → w12. Crucially, the cleanest wave has the **lowest** plateau — so the
plateau scatter is engine-instance state, not contention: the tenancy tax is a latency-suite effect
(see the Resolve wave walls), not something a saturated-decode aggregate feels. Read plateau and
peak position as scatter (the 11-10s lesson), not shape change; the invariants that hold are w1
rising, the no-collapse-by-32 result, and identical admission counts. The 1.6.1 gain over 1.6.0
stands at every wave: plateau 473.7–518.3 vs 375.6 (11-06) / 367.7 (11-10s) means, w1 186.9–209.5
vs 147.6 / 151.5 — and the prefill walls stayed 170.5–171.5 s in every wave that sampled them, so
decode-side remains the unchanged-half of the story.

## Visual venv (OpenCV) — reference host

Face-pipeline baseline for the Resolve vision tooling, version-pinned against the pending
OpenCV 5.1.x wheels (watched by a launchd agent; wheels land as `5.1.0.xxxx`).

| Date | OpenCV | Canonical 4×3 @0.5 | Threshold ladder (merged) | Embed window | Cold process | Markers |
|---|---|---|---|---|---|---|
| 2026-11-11 run1 | 5.0.0.93 | **91 faces / 0.278 s** (PNG; 89 / 0.273 s H.264) | 0.90→57 · 0.75→85 · 0.60→89 · 0.50→91 · 0.45→94 · 0.30→98 | 10.99 ms/face⁸ | 1.488 / 1.491 / 1.486 s | `match()` mutates in-place ✓ · TF reader present · Caffe reader absent |
| 2026-11-11 run2 (same build) | 5.0.0.93 | 91 / 0.302 s | counts **bit-identical** | 11.59 ms/face⁸ | not captured⁹ | all identical |
| 2026-11-13 run3 (same build, clean window) | 5.0.0.93 (unchanged install)¹⁰ | 91 / **0.278 s** (PNG; 89 / 0.270 s H.264) | counts **bit-identical** (third time) | 10.34 ms/face⁸ | not captured⁹ | all identical |

Run2 is a same-build rerun that calibrates the noise band before the upgrade: **every deterministic
value reproduced** (48/48 detect counts, whole-frame 92, match-probe, cosine stats, surface markers,
fixture hashes) while all 48 timings rose uniformly ~11 % (median ×1.111) — machine-state drift, not
an OpenCV effect. **×1.15 is therefore the ceiling for calling a future 5.1.x timing change "real."**
The `match()` in-place-mutation marker flipping to false will be the first visible upstream fix.
A third data point landed on 2026-11-13 (run3, from the clean-window driver, engine idle): every
deterministic value bit-identical again, canonical timing back at run1's 0.278 s — the ×1.15 band
holds, and run1 ≈ run3 is more evidence the run2 lift was machine state, not the harness.

⁸ units normalized: run2's script emits `*_ms`-named keys holding seconds (erratum in
[the README](../bench/visual-venv/README.md)); run3's 0.941 s ÷ 91 = 10.34 ms/face.
⁹ `cold_run.py` prints to stdout; run2's stdout was never saved. Its repo-local fixture has since
moved, so run3 ran without a cold stage too — run2/run3 stay comparable without it.
¹⁰ run3 ran inside the Splash clean window (engine idle) — timings the fastest recorded, canonical
back at run1's 0.278 s (×0.92 vs run2, inside the ×1.15 band). Every deterministic value bit-identical
for a third consecutive run. `cv2.__version__` now reads the 3-segment `5.0.0` while pip still shows
the 5.0.0.93 wheels — same install, untouched since October.

Fixtures are real face frames and are **never committed** — SHA-256s live in the run JSONs, and
`bench/visual-venv/README.md` documents reproducing the harness on your own face-dense media.
Rerun: `~/resolve-vision-venv312/bin/python -I bench/visual-venv/bench_visvenv.py --out runN.json`
(+ `--models <dir with the two opencv_zoo ONNX files>`).

## Reports — what's in each scorecard

Self-contained HTML (no external assets, no build step). GitHub's file view shows source;
view them rendered through Pages (links), or open the files after a clone. Newest first.

| Report | What's in it |
|---|---|
| [**Benchmark reruns, all four suites**](https://willturner-maker.github.io/benchmarks/reports/2026-11-11-reruns.html) (`reports/2026-11-11-reruns.html`) | The 2026-11-11 day: MCP 5.2.2 agentic wave h (18/18, sixth clean wave, walls −23…−38 %), Splash 1.6.1 engine rerun (+39 % plateau, peak moves to width 12, KV secondary signals shift), agentic suite 12/12, OpenCV same-build rerun (bit-identical, ×1.11 band) — plus the ladder comparison chart and every review-audit correction |
| [Resolve MCP 21.2.0.6 · MCP 5.2.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-10g-resolve-21-2-mcp-520.html) (`reports/2026-11-10g-resolve-21-2-mcp-520.html`) | Fifth straight 18/18; the append-pinning tenancy catch (agents' cross-writes caught, reversed, disclosed), ripple's plan-only default, probe alternation cost, upstream #207 live |
| [Splash engine 1.6.0 rerun](https://willturner-maker.github.io/benchmarks/reports/2026-11-10s-splash-160-rerun.html) (`reports/2026-11-10s-splash-160-rerun.html`) | Same-build re-measure: shape-by-shape ladder diff (peak 4, dip 0.87×, ~2 % spread band), quieter KV memory path, agentic 12/12; now carries the concurrency-scaling bar ladder |
| [Resolve MCP 21.2.0.6 · MCP 5.1.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-10f-resolve-21-2-mcp-510.html) (`reports/2026-11-10f-resolve-21-2-mcp-510.html`) | First 5.1.0 pass: 18/18, the `record_frame` semantics trio, append moved to `media_pool`, other v5 deltas |
| [Resolve MCP 21.2.0.6 · MCP 4.19.3](https://willturner-maker.github.io/benchmarks/reports/2026-11-06e-resolve-21-2-mcp-4193.html) (`reports/2026-11-06e-resolve-21-2-mcp-4193.html`) | The replacement pass after two withdrawals: single-tenant probe first, tenancy tax measured, method-honesty section |
| [Splash engine 1.6.0 baseline](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-splash-engine.html) (`reports/2026-11-06-splash-engine.html`) | Engine probe, the width-ladder plateau and its concurrency-scaling figure, KV-pressure chase for a first suspension that never came |
| [Resolve MCP 21.2.0.6 · MCP 4.19.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-resolve-21-2.html) (`reports/2026-11-06-resolve-21-2.html`) | The 21.2 debut: render probes, op medians, n=3 agentic |
| [Resolve MCP 21.1.2.10 · MCP 4.18.5](https://willturner-maker.github.io/benchmarks/reports/2026-11-03-resolve-21-1-2.html) (`reports/2026-11-03-resolve-21-1-2.html`) | The baseline: cold/warm render probes, agentic n=3, two-tier concurrency sweep |

## Community runs — your numbers

Empty by design. Add a row and you get credit *and* scrutiny: state the media class, the
stack versions, n, and whether runs were single-tenant.

| Date | Host | Resolve | MCP | media class | render probe ms | agentic outcomes | honest | notes |
|---|---|---|---|---|---|---|---|---|
| _open_ | | | | B expected | | | | |

### How to add a row

1. Validate your fixture clip: `python3 -I bench/resolve-agentic/check_media.py yourclip.mov`
   → it prints your **class** and derives the frame numbers.
2. Run the suite: [`bench/resolve-agentic/RUNBOOK.md`](../bench/resolve-agentic/RUNBOOK.md)
   (fixture setup → seal the conditions → six briefs in `tasks.md` → grade from read-backs).
3. For the engine suite: `python3 -I bench/splash-concurrency/ladder_kv.py --out my-run.jsonl`.
4. Submit it through the
   **[Leaderboard row issue form](https://github.com/willturner-maker/benchmarks/issues/new?labels=leaderboard&template=leaderboard-row.yml)**
   — it asks for exactly what `suites.community_runs` needs (date, host, exact builds,
   agent model and how it was served, media class plus the validator output, tenant
   conditions, the numbers, and deviations). You don't have to know the JSON schema;
   the row gets added to `leaderboard/results.json` from your issue.

   The form ends in a four-item attestation — read-back-only grading, media class stated,
   tenant conditions stated, deviations disclosed. All four must be true for a row to be
   **ranked**; a row missing one is still welcome, listed with a note instead.

Rows that omit the media class or mix tenant conditions get the row, not the number:
they're listed with a note rather than ranked.
