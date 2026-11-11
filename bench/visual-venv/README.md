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
