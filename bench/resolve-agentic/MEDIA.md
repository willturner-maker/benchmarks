# Bring your own media — the Resolve agentic benchmark's media contract

The benchmark was published from one workstation's footage (a single long stage-
performance camera clip). **Nothing in the suite requires that footage.** The scored
content is how an agent behaves against Resolve's API — planning, dry-run discipline,
read-back verification, honesty about what actually happened. That transfers to any
media. What does *not* transfer is the timing column, unless your media is in the
same equivalence class.

Run the validator first; it decides your class and derives every frame number the
briefs use:

```bash
python3 -I check_media.py /path/to/yourclip.mov --out fixture.json
```

## Required fixture: one video clip

| Property | Requirement | Why |
|---|---|---|
| Count | **exactly one** video file | every task builds its own timelines from one clip; a second clip changes T3's geometry |
| Duration | **≥ 90 s** continuous (single file, not a sequence) | bench-base is 221+221 frames; T3 inserts 101 f mid-clip; T7 renders 121 f mid-clip → ~22 s touched, with slack so inserts/probes never touch the head or tail where trims and timecode oddities live |
| Resolution | **≥ 1280 px wide** to be usable at all; see classes below | T7 is a render-throughput probe: below HD it measures scheduling overhead, not media handling |
| Frame rate | 23.976 – 60; timeline rate = clip rate | mixed-fps timelines change what read-backs mean (the agent would be graded against geometry that never existed) |
| Codec | anything Resolve decodes (HEVC, H.264, ProRes, DNx, BRAW, DNG) | decode cost drives T7's ms — that is why codec is a comparability axis, not a gate |
| Bit depth / colour | anything | no task grades pixel values |
| Audio in the clip | optional | no scored task consumes it |

**Optional fixture: one WAV, 10–15 s.** Only used for the api_truth observation that a
WAV's source frame rate freezes at the *project* rate at import time. Not scored; skip
it and nothing breaks.

**Disk:** ≥ 1 GB free on the volume you point the render target at (121-frame proofs are
tens of MB; the MCP server auto-archives a timeline copy before each mutation, and T2/T3/T4/T7
each trigger one). Put proofs on an external volume, not the boot disk.

## Two equivalence classes — this is the honest-comparison rule

| | **Class A** (timings comparable to published) | **Class B** (outcomes comparable, timings are yours) |
|---|---|---|
| Source | HEVC Main 10, **≥ 8128×4288** | anything usable |
| Rate | 29.97 (drop-frame family) | anything in band |
| Timeline the validator emits | **3840×1520**, 29.97 | 3840×2160 if source ≥ 3840 wide, else 1920×1080 |
| Published reference (2026-11-06, Resolve 21.2.0.6 + MCP 4.19.2, M5 Ultra 96 GB) | cold 1668 ms, warm median **1196 ms / 93.4 fps** for 121 frames; op medians `prepare_render_job` 162, `verify_output` 50, `set_current` 97, `create_variant_from_ranges` 274, `probe_timeline_structure` 11 | — |
| What you can legitimately say | "reproduced the published render and op timings on like media" | "same 6/6 outcomes and honesty profile; my render ms are 2.1 s on 1080p H.264" |

Reporting class B ms next to published class A ms is the one way to make this
benchmark misleading — a 1080p H.264 render being "faster" says nothing about the
toolchain. Say which class you were in.

## Frame numbers come from your clip, not from the doc

`fixture.json` derives, and every brief in `tasks.md` reads those values:

- `derived.insert_source_start` — mid-clip source frame for T3's ripple insert
  (≈25 % of total frames, floor 500 so it never sits in the first few seconds)
- `derived.probe_source_start` — T7's 121-frame render range (≈10 %, floor 1000)
- `timeline.base_segments` — the two bench-base items (221 + 221 f)
- both are pulled back if they would land within 300 frames of the clip's end

The published run's briefs said "source frames 2000 to 2100" because the reference
clip was 100,725 frames long; on your clip those numbers come from the validator.

## Drop-frame caveat (carried in the briefs)

On 29.97/59.94 DF media, Resolve's source-second readers are timecode-anchored and read
**one frame low** (a range asked for at source 2000 reads back 1999). Every published run
hit this; agents that investigated and *declined to +1-compensate* were right — durations
and record placement are the truth, and `GetSourceStartTime` deltas are the decisive
cross-check. If your clip is at an integer rate (24/25/30/50/60) this quirk disappears
entirely, which makes grading cleaner: prefer a non-DF rate if you have the choice.
