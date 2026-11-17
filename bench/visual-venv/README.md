# Visual venv baseline — pre-OpenCV-5.1.0 (2026-11-11)

Snapshot of `~/resolve-vision-venv312` (opencv-python/-contrib **5.0.0.93**, numpy 2.5.4, Python 3.12.16)
before the 5.1.0 wheel lands (opencv-watch launchd agent is watching; expect 5.1.0.94/.95).
Rerun this same dir post-upgrade and diff `run1.json` vs `run2.json`.

## Files
- `bench_visvenv.py` — full bench: import/init timing, YuNet tiled detect (4 grids × 6 thresholds × 2
  fixtures), whole-frame control, SFace embed pass + cosine stats, `match()` in-place-normalisation probe,
  API-surface presence probe. Run: `~/resolve-vision-venv312/bin/python bench_visvenv.py --out run1.json`
- `cold_run.py` — whole-process cold-start probe (external subprocess, ×3)
- `run1.json` — the baseline numbers below
- `fixture_f240.png` (sha256 `12662c771c1a…`, 8128×4288 8-bit BGR after imread) and
  `fixture_f240_h264.mp4` (sha256 `1ec7a3a6677d…`, CRF18) — both from the same concert source frame at
  t=240 s (same source frame the 2026-11-04 choir_240 runs used; the f5200 extract was too sparse —
  0 faces at 0.5).

## Headline baseline
- import cv2 0.063 s; YuNet create 0.003 s; SFace create 0.025 s; cold process (import→91 faces) **1.49 s** wall, spread 5 ms ×3.
- Canonical route 4×3 @ 0.5: **91 faces / 0.278 s** (PNG) — 89 / 0.273 s on the H.264 decode (encoding cost ≤ 2 faces).
- Threshold ladder (4×3 merged): 0.90→57, 0.75→85, 0.60→89, 0.50→91, 0.45→94, 0.30→98.
- Whole-frame **native-res** control @0.5: 92 raw / 0.278 s (the old "whole-frame = 0" note was about *downscaled* whole-frame).
- Grid cost: 2×2 0.21 s · 4×3 0.27 · 4×4 0.30 · 8×4 0.41.
- Embed: alignCrop+feature ≈ **11.0 ms/face** window (incl. a second detect pass in the timed loop);
  raw SFace vector norms median 10.34 (un-normalised).
- Cosine over all 4095 pairs: median 0.127, p95 0.312 (below the 0.363 same-person gate).

## Behavioural markers for the 5.1.0 diff
1. **`match()` in-place normalisation — CONFIRMED MUTATING on 5.0.0.93**: passing fresh copies, norms
   9.82 / 12.40 → **1.00 / 1.00** after the call. If 5.1.0 fixes this, `in_place_mutation` flips to false.
2. API surface now: `cv2.setLogLevel` absent (moved, matches shipped fix), `cv2.utils.logging` present,
   `readNetFromTensorflow` **present** (classic TF reader removal is expected in 5.1.0),
   `readNetFromCaffe` already **absent**, `readNetFromONNX` present, YN/SF classes present.
3. Every detect config re-creates the detector (fresh `create()` per row) — matches the watch/verify shape,
   and keeps init cost visible in each row.

Note (kept honest): the embed timed window re-runs detection, so 11 ms/face is an upper bound;
(1.00 s − 0.27 s detect)/91 ≈ 8.0 ms/face net — consistent with the ~7.5 ms mark from 2026-11-04.

## Fixtures are NOT committed (privacy)

`fixture_f240.png` / `fixture_f240_h264.mp4` are real concert frames with identifiable faces and stay on the
local bench dir. SHA-256s are recorded in `run1.json`/`run2.json` (`fixtures.*.path_sha256`). To reproduce
the harness on your own media: put any face-dense frame at `fixture_f240.png` (8128×4288 or resize to match
your source) plus its CRF18 H.264 encode, run `bench_visvenv.py --out run1.json --models <dir with the two
opencv_zoo ONNX files>` — absolute counts will differ; the ladder *shape* and markers are what transfer.

## Rerun 2026-11-11 (`run2.json`, same opencv-python 5.0.0.93 — noise-band calibration, not the upgrade run)

- Determinism: 48/48 detect rows identical on counts, whole-frame control (92 raw), match-probe
  (in-place mutation reproduced), surface markers, cosine stats, fixture hashes — all bit-identical.
- Timings: **uniform ~11% slower across all 48 samples** (canonical 4×3 0.278→0.302 s; median ×1.111)
  with the identical cv2 build — machine-state drift, not an OpenCV effect. Treat ×1.15 as the rerun
  noise ceiling for the future 5.1.x diff.
- **Script label erratum:** the current script's `feat_ms_total`, `det_ms_same_pass`, `ms_per_face`
  keys hold SECONDS (`ms_per_face` also loses precision at round(...,3)); run1's `*_s` keys were
  correct. Normalize before diffing: per-face window 10.99 (run1) vs 1.055 s/91 = 11.59 ms (run2).
  Label fix belongs with the post-upgrade rerun.
- run2 has no `cold_process` section (the current script never writes one; `cold_run.py` prints to
  stdout, which was not captured for run2).
- Provenance note: `run1.json` was produced by an earlier script version (it carries `unit_note`,
  `*_s` keys, and a hand-merged `cold_process` section the current script cannot emit).

## Rerun 2026-11-13 (`run3.json`, same opencv-python 5.0.0.93 — clean-window co-run)

Co-ran inside the 2026-11-13 clean window (detached driver, engine session idle); the JSON lives
with that window's records at `../splash-concurrency/results/clean-2026-11-13/run3.json` rather
than here. Every deterministic value bit-identical for a **third** consecutive run (48/48 detect
counts, whole-frame 92, cosine 0.1265 / 0.3121, `match()` still mutating in place, all surface
markers, fixture hashes). Canonical 4×3@0.5 came back at run1's exact **0.278 s** (×0.92 vs run2
— inside the ×1.15 band, so run2's lift was machine state, not the harness); embed window
10.34 ms/face, fastest recorded. Note: `cv2.__version__` reports three-segment `"5.0.0"` while pip
still shows the 5.0.0.93 wheels (same Oct install) — don't read the string as a build change.
Cold stage not captured (the repo-local fixture `cold_run.py` used has moved; run2 had none
either).

## Rerun 2026-11-16 (`run4.json`, same opencv-python 5.0.0.93 — harness-swap day co-run)

Ran on the agentic harness-swap day (before the wave's timed stages, engine idle), with the
volume fixtures passed explicitly. Every deterministic value bit-identical for a **fourth**
consecutive run (48/48 detect counts, whole-frame 92, cosine 0.1265 / 0.3121, `match()` still
mutating in place, all surface markers, fixture hashes vs run1-3). Canonical 4×3@0.5: **0.283 s**
PNG (89 faces / 0.273 s H.264) — ×1.018 vs run3, inside the ×1.15 band. Embed window 10.90 ms/face
(0.992 s / 91). `import_cv2` 0.157 s vs run3's 0.064 s — cold page cache, process state not
OpenCV. No cold stage (unchanged since run2). Fixture copies live on the external volume beside
the bench (`vision-detector-compare/bench-20261111/`); `run4.err` is empty — no stderr output.

## Tooling change 2026-11-16: records self-identify

`bench_visvenv.py` used to stamp every output with the hardcoded label
`visvenv-baseline-2026-11-11`, so `run4.json` arrived carrying run1's label and a record's date
was recoverable only from git. The label now defaults to `visvenv-<run date>` (override with
`--label`), and every record gains `measured_at` (local ISO-8601 with offset).

- **run1-run4 are not rewritten** — published records keep the labels they were written with,
  the same rule as never moving a tag. Expect `label` and `measured_at` to be the only key-set
  difference when a new run is diffed against them.
- Verified by an **unrecorded** re-run that evening (scratch output, then deleted): 48/48 detect
  counts, whole-frame raw 92, cosine stats, the `match()` in-place probe, surface markers and
  fixture hashes all bit-identical to run4; only timings moved (`det_s` 0.276 → 0.282, ×1.02;
  embed total 0.992 → 0.969 s), inside the ×1.15 ceiling. A fifth consecutive determinism pass —
  but kept out of the record set, because it exercised the tooling rather than measuring the stack.
- Still open on purpose: the `*_ms`-keys-hold-seconds mislabeling noted under the run2 section.
  Renaming those keys breaks cross-run diffs, so it waits for the post-5.1.x rerun.
