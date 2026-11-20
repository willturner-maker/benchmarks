# Visual venv baseline — pre-OpenCV-5.1.0 (2026-11-11)

Snapshot of `~/resolve-vision-venv312` (opencv-python/-contrib **5.0.0.93**, numpy 2.5.4, Python 3.12.16)
before the 5.1.0 wheel lands (opencv-watch launchd agent is watching; expect 5.1.0.94/.95).
Rerun this same dir post-upgrade and diff `run1.json` vs `run2.json`.

**Where the series stands now (2026-11-19):** the venv runs **5.1.0.95** since run5, numpy 2.5.5;
run1–run4 sections below keep the 5.0.0.93 labels they were written with (published records are
never relabeled). Sections run in order: run1 baseline → run2/3/4 (5.0.0.93 repeats) →
**run5 (the 5.1.0.95 upgrade)** → **run6 (same wheel, host-state control)**.

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
the bench (`vision-detector-compare/bench-20261111/`); `run4.err` was empty and was not kept on disk.

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

## Rerun 2026-11-17 (`run5.json`, opencv-python/-contrib **5.1.0.95** — the upgrade run)

The 5.1.0.95 macOS arm64 wheel hit PyPI 17:40 UTC on 2026-11-17; both opencv packages
were upgraded together (`--only-binary :all:`) and the import chain re-verified before this
run (README's open key erratum shipped with it: `feat_s_total` / `det_s_same_pass` /
`ms_per_face` are now honestly labelled — run5 is the first record using them; normalize
when diffing against run1–4). numpy 2.5.4 → 2.5.5 alongside. Fixtures re-resolved from the
external volume copy; SHA-256s match run1–run4 bit-for-bit. Engine idle (serve up, no
generation), outside the clean-window protocol — timings carry machine-state risk, but every
observed move is a *speed-up*, far outside the ×1.15 drift band.

- **Performance (the headline):** median **×0.853 across all 48 detect rows** vs run4.
  Canonical 4×3@0.5: 0.278 / 0.278 / 0.283 (run1/3/4) → **0.227 s (×0.80)**. Grid cost:
  2×2 0.208→0.135 (×0.65) · 4×3 ×0.80 · 4×4 ×0.88 · 8×4 ×0.99 — the win concentrates in the
  per-create/init overhead, least in the large grids. `import_cv2` 0.157→0.036 s (below
  run1's warm 0.063 even), YuNet create 0.013→0.005 s, SFace create 0.034→0.030 s.
  Embed window 0.992→0.933 s (10.90→10.25 ms/face, still an upper bound).
- **Cold stage (first recorded since run1):** `cold_run.py` ×3 → **1.361 / 1.368 / 1.377 s**
  (spread 16 ms), raw=91 — vs run1's 1.49 s (≈×0.92); page cache was warm, engine idle.
- **Determinism:** all 24 PNG detect rows, whole-frame (92), cosine (0.1265/0.3121) and SFace
  norm median (10.341) **bit-identical** — the detector is unchanged on identical pixels.
- **9 of 48 mp4_h264 rows shift by ±1 face** (raw and merged move together; PNG rows untouched).
  Attribution proven, not assumed: the same fixture **decodes to different pixels** under
  5.1.0.95 — first-frame sha256 `6716af2b…`/sum 5 441 800 265 (isolated 5.0.0.93 wheel) vs
  `a2bebe5f…`/sum 5 437 720 989 (5.1.0.95). It is the bundled **FFmpeg 9.0.2** decode, not the
  detector. Any future H.264 face counts are decoder-version-dependent records.
- **Behavioural markers vs the README's expectations:**
  1. `readNetFromTensorflow` → **absent** (as predicted; Caffe stayed absent, ONNX/YN/SF present).
  2. **`match()` in-place normalisation NOT fixed on 5.1.0.95** — norms 9.821/12.40 → 1.00/1.00
     reproduce bit-identically. The "fixed upstream in 5.1.0" expectation did not ship in the
     wheel; the vision code must keep copying vectors before `match()`.
  3. New stderr on every `FaceDetectorYN/FaceRecognizerSF.create()`:
     `[ WARN] setPreferableTarget Targets are not supported by the new graph engine for now` —
     55 WARN lines in the committed `run5.err` (counted 2026-11-18; run4.err was empty and not kept). Harmless but noisy for stderr-capturing
     pipelines; silence via `cv2.utils.logging.setLogLevel`.

## Rerun 2026-11-18 (`run6.json`, label `visvenv-2026-11-18` — all-suites day, same wheel)

`opencv-python`/`-contrib` **still 5.1.0.95**, numpy 2.5.5, Python 3.12.16 — nothing in the venv
changed between run5 and run6, which makes this a pure **host-state** measurement and the
suite's control pair for the ×1.15 ceiling. Measured 17:34 local during the all-suites day,
i.e. the engine and Resolve were active on the same machine: **not** a clean window, and the
timings below are read as machine state, never as a library change.

- **Determinism (the record):** leaf-by-leaf diff vs `run5.json` → **269 values identical**, and
  the only numeric non-timing difference is `embed.ms_per_face` 10.25 → 10.24, which is derived
  from the embed wall time. **All 48 detect rows identical in counts, PNG and H.264** — so
  run5's 9 shifted H.264 rows **reproduce bit-exactly**: the shift is decoder-version-bound and
  stable, not sampling noise, which is the confirmation run5's sha256 attribution was waiting for.
  Whole-frame raw 92, cosine (4095 pairs, median 0.1265, p95 0.3121), SFace norm median, surface
  markers, fixture SHA-256s, and the `match()` probe (`in_place_mutation: true`, 9.821/12.40 →
  1.00/1.00) all identical. Fifth consecutive determinism pass (run2/3/4/5/6 after the run1 baseline).
- **Timings (the control):** canonical 4×3@0.5 **0.227 → 0.268 s** (PNG; H.264 0.221 → 0.267),
  median **×1.181 across 54 timing rows** on an unchanged wheel. Largest moves are the smallest
  absolutes — YuNet create 0.0052 → 0.0177 s (×3.4), `import_cv2` 0.0363 → 0.0808 s (×2.2),
  whole-frame 0.194 → 0.407 s (×2.1) — which is what contention does to sub-100 ms measurements.
- **Why this row matters for the suite's rules:** ×1.18 is **outside** the ×1.15 same-build
  ceiling calibrated by run1→run2. Same wheel, same fixtures, different machine state — so the
  ceiling is a *band to flag*, not a threshold that proves a library effect. It also bounds
  run5's headline: run5 vs run4 was **×0.853**, the opposite direction and well outside the band,
  so the 5.1.0.95 speed-up stands while a ×1.2 move in either direction stays unclaimable.
- **Not captured:** the cold-start stage (`cold_run.py`) was not re-run — it wants an idle machine.
  `run6.err` carries the same `setPreferableTarget` WARN spam (one line per model create).
