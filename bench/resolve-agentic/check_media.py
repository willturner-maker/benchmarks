#!/usr/bin/env python3
"""Validate a candidate fixture clip against the Resolve agentic benchmark's media
contract, and emit the fixture.json that task briefs and graders read.

    python3 check_media.py /path/to/yourclip.mov [--out fixture.json]

Exit 0 = usable (class A = comparable to published timings, class B = comparable
outcomes only). Exit 1 = not usable, reasons printed. Needs ffprobe on PATH.

Why this exists: the benchmark was published from one workstation's footage. The
*scored* content (outcome + honesty + tool-use discipline) transfers to any media;
the *timings* only transfer if the media class matches. This script decides which
one you're in, and derives the frame numbers so briefs stay valid on your clip.
"""
import argparse, json, shutil, subprocess, sys

MIN_SECONDS = 90          # 543 frames of bench-base + a 101-frame insert + slack
MIN_WIDTH_CLASS_B = 1280
MIN_FREE_BYTES = 1_000_000_000   # proofs + per-mutation timeline auto-archives
PUBLISHED = {             # what the published run actually used (see MEDIA.md)
    "codec": "hevc", "profile": "Main 10", "width": 8128, "height": 4288,
    "fps": 29.97, "timeline": [3840, 1520], "total_frames": 100725,
}
BASE_SEGMENTS = [221, 221]        # bench-base: two items; T3's 101-f insert makes three
PROBE_FRAMES = 121                # T7 render probe length
INSERT_FRAMES = 101               # T3 inserted range length


def ffprobe(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=codec_name,profile,width,height,r_frame_rate,"
                            "avg_frame_rate,nb_frames,pix_fmt",
           "-show_entries", "format=duration,size", "-of", "json", path]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"ffprobe failed: {p.stderr.strip()[:400]}")
    d = json.loads(p.stdout)
    return (d.get("streams") or [{}])[0], d.get("format", {})


def rate(s):
    for key in ("r_frame_rate", "avg_frame_rate"):
        num, _, den = str(s.get(key, "")).partition("/")
        try:
            f = float(num) / float(den or 1)
            if f > 0:
                return f
        except ValueError:
            pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--out", default="fixture.json")
    a = ap.parse_args()

    s, fmt = ffprobe(a.media)
    w, h = int(s.get("width") or 0), int(s.get("height") or 0)
    fps = rate(s)
    dur = float(fmt.get("duration") or 0)
    frames = int(s.get("nb_frames") or 0) or int(round(dur * (fps or 0)))

    fails, warns, reasons = [], [], []

    if not (w and h and fps and frames):
        fails.append("could not read width/height/fps/frame count — unsupported or corrupt")
    if dur and dur < MIN_SECONDS:
        fails.append(f"duration {dur:.1f}s < {MIN_SECONDS}s floor (briefs need ~22s of "
                     f"mid-clip source plus headroom)")
    if w and w < MIN_WIDTH_CLASS_B:
        fails.append(f"width {w} < {MIN_WIDTH_CLASS_B} (below the smallest class that "
                     "exercises the UHD render probe meaningfully)")

    df = abs(fps - 29.97) < 0.02 or abs(fps - 59.94) < 0.02 if fps else False
    if df:
        warns.append("drop-frame-adjacent rate: source-frame reads can sit 1 frame low "
                     "(documented quirk; briefs carry the caveat, durations/placement stay truth)")
    if fps and not (23.9 <= fps <= 60.1):
        warns.append(f"fps {fps} outside 23.9–60: timeline settings may need a manual pick")

    free = shutil.disk_usage("/").free
    if free < MIN_FREE_BYTES:
        warns.append(f"only {free/1e9:.1f} GB free on the boot volume — point the render "
                     "target at a volume with ≥1 GB free instead")

    # Class A = the published equivalence class (see MEDIA.md for why).
    class_a = (s.get("codec_name") == PUBLISHED["codec"] and w >= PUBLISHED["width"]
               and h >= PUBLISHED["height"] and df)

    # Geometry derivation: keep every frame number inside the clip, away from its ends.
    # A class-A clip reproduces the published 3840x1520 window exactly; anything else
    # gets a sane standard format, which puts render ms in its own series.
    if class_a:
        tl_w, tl_h = PUBLISHED["timeline"]
    else:
        tl_w, tl_h = (3840, 2160) if w >= 3840 else (1920, 1080)
    base_start = max(200, int(frames * 0.05))      # bench-base items are cut from here
    src_insert = max(500, int(frames * 0.25))
    probe_start = max(1000, int(frames * 0.10))
    if frames and src_insert + INSERT_FRAMES > frames - 300:
        src_insert = max(0, frames - INSERT_FRAMES - 300)
    if frames and probe_start + PROBE_FRAMES > frames - 300:
        probe_start = max(0, frames - PROBE_FRAMES - 300)
    base_span = sum(BASE_SEGMENTS) + INSERT_FRAMES
    if frames and base_span > frames - 300:
        fails.append(f"clip has {frames} frames; bench-base needs {base_span} plus slack")

    if not class_a:
        if w and w < PUBLISHED["width"]:
            reasons.append(f"source {w}x{h} narrower than the published 8128x4288")
        if s.get("codec_name") != PUBLISHED["codec"]:
            reasons.append(f"codec {s.get('codec_name')} != published hevc Main 10 "
                           "(decode cost differs → render ms not comparable)")
        if tl_h != PUBLISHED["timeline"][1]:
            reasons.append(f"timeline would be {tl_w}x{tl_h}, not 3840x1520 "
                           f"(pixel count differs → render ms not comparable)")

    fixture = {
        "media_path": a.media,
        "clip_name": a.media.rsplit("/", 1)[-1],
        "source": {"codec": s.get("codec_name"), "profile": s.get("profile"),
                   "width": w, "height": h, "fps": round(fps or 0, 4),
                   "pix_fmt": s.get("pix_fmt"), "duration_s": round(dur, 2),
                   "total_frames": frames},
        "timeline": {"width": tl_w, "height": tl_h, "fps": round(fps or 29.97, 4),
                     "name_base": "_mcp_AGBench", "base_segments": BASE_SEGMENTS},
        "derived": {"base_source_start": base_start,
                    "insert_source_start": src_insert, "insert_frames": INSERT_FRAMES,
                    "probe_source_start": probe_start, "probe_frames": PROBE_FRAMES,
                    "drop_frame_caveat": df},
        "comparability": "A" if not reasons else "B",
        "comparability_notes": reasons,
        "warnings": warns,
    }

    print(f"{a.media}")
    print(f"  {w}x{h} {s.get('codec_name')} {s.get('profile') or ''} "
          f"{fps:.4f} fps  {dur:.1f} s  {frames} frames")
    for x in warns:
        print(f"  warn: {x}")
    if fails:
        for x in fails:
            print(f"  FAIL: {x}")
        print(f"\nNOT USABLE — see MEDIA.md for the contract. (no fixture file written)")
        return 1

    with open(a.out, "w") as f:
        json.dump(fixture, f, indent=2)
    grade = "A (published timings comparable)" if fixture["comparability"] == "A" \
            else "B (outcomes/honesty comparable; render ms are yours alone)"
    if reasons:
        print("  class notes: " + "; ".join(reasons))
    print(f"\nUSABLE — class {grade}")
    print(f"  bench-base: {' + '.join(map(str, BASE_SEGMENTS))} f from source {base_start} "
          f"(T3 inserts "
          f"{INSERT_FRAMES} f at the cut → {'+'.join(map(str, BASE_SEGMENTS))}"
          f"+{INSERT_FRAMES} = {sum(BASE_SEGMENTS) + INSERT_FRAMES} f) | "
          f"T7 probe at source {probe_start} ({PROBE_FRAMES} f)")
    print(f"  wrote {a.out} — briefs and graders read this file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
