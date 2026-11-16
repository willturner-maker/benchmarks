# Resolve Studio co-tenancy RAM measurement — method notes (2026-11-15)

Answers a question the Splash benchmark had been asserting rather than measuring: **how much
memory does DaVinci Resolve Studio actually want on this host**, given that the engine's 56 GiB
working set and Resolve share one 96 GiB pool. Result is in
[`docs/splash-engine-benchmark-results.md`](../../docs/splash-engine-benchmark-results.md),
section *Co-tenancy — Resolve Studio on the same 96 GiB*.

## Host / stack at run

- Apple M5 Ultra, 96 GiB unified, macOS 27.2.0. Splash **1.6.1**,
  `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, `--max-memory=56G`,
  `--max-cache-disk=256G`, `--persistent-cache` (idle-release left at its 10 m default).
- DaVinci Resolve **Studio 21.2**, **headless** (`Resolve -nogui`, launched on demand by the
  Resolve MCP — the operator default host). Never the GUI.
- Render payload: a UHD 3840×2160 @ 29.97 test project (source is 8.1K anamorphic). One
  single-item probe timeline, 3000 frames (source frames 10072–13072), rendered twice:
  `h264_2160p_web` (mp4) and `prores422hq_master` (mov). Both verified with ffprobe:
  **3000 frames @ 3840×2160**, `codec_name=h264` / `prores`. No audio (video-only item).

## Method

`ram_sampler.py`: **`/usr/bin/footprint`** per pid, 1 Hz, for every process whose path is under
`/Applications/DaVinci Resolve` (summed — during a render a separate *DaVinci Resolve Helper*
transcode worker appears and holds ~2.4 GiB of the total), plus `ps -o rss` for the resident
figure, `vm_stat`, and `sysctl vm.swapusage`. Phase labels come from `phase.txt`, written by the
driver between steps; each CSV row carries the phase and the engine's own footprint, so a sample
can be judged for whether the engine was resident at the time.

Three passes (`peaks-pass{1,2,3}.log`), merged into `merged.csv`: **2,138 samples**. Pass 1 was
cut at 900 s mid-render; pass 2 covers the rest of that render; pass 3 is the clean ProRes phase.
`analyze.py` prints the per-phase table.

Why `footprint` and not `top`/`ps`: the number that matters for pressure is **phys_footprint**,
and `footprint -p PID` returns it (plus the category table, incl. `IOAccelerator (graphics)`) in
**41 ms**. `vmmap -summary` costs ~1 s and would have perturbed render timing. A ctypes
`proc_pid_rusage` call was the first attempt — it **segfaulted (exit 139)**; the tool route is the
shipped one. Also: `vm_stat` quotes some key names (`"Pages decompressed":`), so match on the
de-quoted key, not a line prefix.

## Resolve-side gotchas hit while measuring (these cost real time; they belong to the Resolve MCP
benchmark notes as much as here)

- **A mid-render `render.stop` wedges the queue.** The job stays queued and `is_rendering` stays
  true; `resolve_control quit` + relaunch does **not** clear it. `render.delete_all_jobs` does.
- **`create_variant_from_ranges` onto a NEW timeline inherits the SOURCE timeline's record frame**
  (1719660), leaving a 1.6 M-frame leading gap. A marks-less job then renders the gap: the first
  "3000-frame" render was really 1,614,659 frames, mostly black. Pass `pack=true` (or an explicit
  `record_frame`) and read `render.list_jobs` before `start`.
- **`timeline.set_mark_in_out` does not drive the render range** — the queued job read back
  `MarkIn/MarkOut` = full timeline extent anyway.
- **`render.get_job_status` reported "Ready for background render" / 0 % the whole time a render
  was running.** Trust `is_rendering` + the output file (ProRes writes progressively, mp4 lands at
  the end).
- Delivery targets are the reliable way to pin raster: `prepare_delivery_job(target=
  'h264_2160p_web')` set `FormatWidth/FormatHeight` correctly, whereas `prepare_render_job` with
  `ResWidth/ResHeight` reported those keys **unknown** (the typed keys are `FormatWidth`/
  `FormatHeight`; `GetRenderSettings` is not available on this build, so the inherited Deliver-page
  state can't be read back — the tool warns with `RENDER_PRESET_STATE_INHERITED`).
- Off-temp targets need `require_temp_target=False` to write outside the system temp dir.

## Caveats to carry into any quote of these numbers

- **Headless only.** No display server, no viewers; the `IOAccelerator (graphics)` category stays
  at KB-level dirty, which is why the GPU-inclusive figure is the **system wired delta**
  (~+6 GiB at peak), not the process category.
- **6.76 GiB is a floor, not a ceiling**: single item, no grades/Fusion/temporal NR, no audio,
  3840×2160 out. GUI Resolve, Fusion-heavy comps, NR and 8K output all sit above it.
- One phase (`render_h264_uhd_3000f`) straddles the engine's **idle-release** un-wire, so its
  wired/free columns mix resident and un-wired states — the `engine_fp` column in the table shows
  it (52.15 for part of the phase, 4.48–51.22 for the rest). The ProRes phase is the clean
  coexistence row.
- Render speed depends entirely on decode warmth: the cold 8.1K pass ran ~2 fps (24 min for 3000
  frames), the warm ProRes pass over the same source region ~40 fps (~75 s). Memory plateau
  duration follows whichever you are in.
- Raw data holds no media paths — the payload is described, not named.
