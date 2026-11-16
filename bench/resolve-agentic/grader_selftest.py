#!/usr/bin/env python3
"""Grader self-test (null tests) for the Resolve agentic benchmark.

Method change #3. A wave reported as "18/18 outcome-verified" is only meaningful if the grading
probes are *capable of saying no*. Nothing in the published record demonstrates that. This script
runs each grading predicate against (a) a conforming payload it must ACCEPT and (b) injected
wrong payloads it must REJECT, and fails loudly if any case misbehaves.

Design notes
- The predicates here mirror the grading table in RUNBOOK.md and read the same payload fields the
  MCP probes return (probe_timeline_structure / detect_gaps_overlaps / timeline_markers.get_all /
  ffprobe / list_jobs). The payload shapes those probes actually return are recorded in
  `selftest/LIVE_SHAPE.md` (captured from a real scratch timeline on 2026-11-15); re-capture and
  re-read it whenever the MCP build or the Resolve build moves, because a predicate written against
  a shape the probe no longer emits can pass a wave while reading nothing.
- Shape drift is not hypothetical: the 2026-11-15 capture showed `timeline_markers.get_all` returns
  a **dict keyed by frame string** whose entries carry `color/duration/note/name/customData` and no
  `frame` key at all. A predicate written as "iterate a list of dicts, compare `m['frame']`" reads a
  marker's frame as -1 for every entry and fails closed (it would reject a correct wave), but the
  opposite drift — a probe that starts *omitting* a key the predicate never required — fails open.
  Both directions are covered by cases below.
- Cases are labelled: `ok` must accept, `bad-*` must reject, `trap-*` is the silent-success class
  (the tool reported success, the artifact is absent), `rule-*` pins a deliberate lenient/strict
  decision so it is a documented rule rather than an accident.
- Nothing here touches Resolve; payloads are synthetic. Run the live shape check separately.

Exit code 0 = every case behaved. Non-zero = the grader is not trustworthy; the wave must not be
published as verified until it is fixed.
"""
import json
import os
import sys

GREEN = "Green"


# ---------------------------------------------------------------- payload normalizers
def normalize_markers(payload):
    """Accept both marker shapes.

    Live `timeline_markers.get_all` (captured 2026-11-15, MCP 5.2.11 / Resolve 21.2.0.6) returns a
    DICT keyed by frame string: {"60": {"color": "Green", "duration": 1, "note": ..., "name": ...,
    "customData": ""}} — the frame number is the key, and the entry has no `frame` field.
    List-of-dicts-with-`frame` is the shape older wave notes quote. `probe_timeline_structure`
    returns the same dict shape under its own `markers` key.
    """
    out = []
    if isinstance(payload, dict):
        for key, entry in payload.items():
            if not isinstance(entry, dict):
                continue
            m = dict(entry)
            m.setdefault("frame", key)
            out.append(m)
    else:
        for entry in payload or []:
            if isinstance(entry, dict):
                out.append(entry)
    return out


def _frame_of(m):
    """Read a frame number defensively.

    `int()` alone is not enough: upstream `Timeline.GetMarkers()` documents the dict key as a
    **float** (`{96.0: {...}}`), and a JSON round-trip turns that into the *string* "96.0" — which
    `int()` raises on. A raise here reads as "no marker at frame 60", so a correct wave would fail.
    """
    try:
        return int(float(m.get("frame", -1)))
    except (TypeError, ValueError):
        return -1


# ---------------------------------------------------------------- grading predicates
def grade_t1(expected, reported, archived_siblings):
    """T1 is read-only: four values must match ground truth exactly, and no mutation may occur."""
    reasons = []
    for k, v in expected.items():
        if k not in reported:
            reasons.append(f"missing field {k}")
        elif reported[k] != v:
            reasons.append(f"{k}: reported {reported[k]!r} != ground truth {v!r}")
    if archived_siblings:
        reasons.append(f"mutation detected: archive sibling(s) {archived_siblings} appeared during the trial")
    return (not reasons), reasons


def grade_t2(marker_spec, markers_payload, item_durations, duration_spec):
    reasons = []
    markers = normalize_markers(markers_payload)
    if markers and all(_frame_of(m) < 0 for m in markers):
        # fail-open guard: the payload has entries but no readable frame anywhere, which means the
        # probe's shape changed under us rather than that the agent missed the marker.
        reasons.append(f"marker payload shape unreadable: {len(markers)} entries, no frame key or "
                       f"frame-string key — re-capture selftest/LIVE_SHAPE.md")
    hit = None
    for m in markers:
        if str(m.get("name", "")).strip() == marker_spec["name"] and _frame_of(m) == marker_spec["frame"]:
            if str(m.get("color", "")).lower() == str(marker_spec["color"]).lower():   # rule: colour case-insensitive
                hit = m
                break
    if hit is None:
        want = f"{{{marker_spec['frame']}, {marker_spec['color']}, {marker_spec['name']}}}"
        got = [{"frame": _frame_of(m), "color": m.get("color"), "name": m.get("name")} for m in markers]
        reasons.append(f"no marker matching {want}; saw {got}")
    if sorted(item_durations) != sorted(duration_spec):
        reasons.append(f"item durations {item_durations} != {duration_spec}")
    return (not reasons), reasons


def grade_t3(structure_items, duration_spec, gaps, overlaps, total_spec):
    reasons = []
    durs = [int(i["end"]) - int(i["start"]) for i in structure_items]
    if durs != duration_spec:
        reasons.append(f"durations {durs} != {duration_spec}")
    if sum(durs) != total_spec:
        reasons.append(f"total {sum(durs)} != {total_spec}")
    if len(gaps) != 0:
        reasons.append(f"{len(gaps)} gap(s): {gaps}")
    if len(overlaps) != 0:
        reasons.append(f"{len(overlaps)} overlap(s): {overlaps}")
    return (not reasons), reasons


def grade_t7(ffprobe, spec, queued_jobs, own_timeline):
    """Render loop: exactly N packets, right codec/container/raster, queue drained, own timeline."""
    reasons = []
    packets = int(ffprobe.get("packets", -1))
    if packets != spec["packets"]:
        reasons.append(f"packet count {packets} != {spec['packets']} (a collapsed or partial render)")
    if ffprobe.get("codec_name") != spec["codec"]:
        reasons.append(f"codec {ffprobe.get('codec_name')!r} != {spec['codec']!r}")
    if (ffprobe.get("width"), ffprobe.get("height")) != (spec["width"], spec["height"]):
        reasons.append(f"raster {ffprobe.get('width')}x{ffprobe.get('height')} != {spec['width']}x{spec['height']}")
    if not ffprobe.get("file_exists", True):
        reasons.append("output file absent")
    if ffprobe.get("duration_ratio") is not None and ffprobe["duration_ratio"] < 0.98:
        reasons.append(f"duration ratio {ffprobe['duration_ratio']} (near-empty render)")
    if queued_jobs:
        reasons.append(f"render queue not empty: {queued_jobs}")
    if ffprobe.get("timeline_name") and ffprobe["timeline_name"] != own_timeline:
        reasons.append(f"job's TimelineName {ffprobe['timeline_name']!r} != the agent's own {own_timeline!r}")
    return (not reasons), reasons


def grade_t8(comp_count, comp_names, claim_comp=True):
    reasons = []
    if comp_count != 1:
        reasons.append(f"comp count {comp_count} != 1")
        if claim_comp:
            reasons.append("agent claimed a comp exists, but the read-back shows none (silent-success trap)")
    elif not comp_names:
        reasons.append("comp present but unreadable name (comp not enumerable)")
    return (not reasons), reasons


# ---------------------------------------------------------------- case battery
ITEMS_OK = [{"start": 108000, "end": 108221}, {"start": 108221, "end": 108322}, {"start": 108322, "end": 108543}]
SPEC_T3 = ([221, 101, 221], 543)


def cases():
    c = []

    # --- T1: read-only fidelity + mutation detector
    gt = {"duration_frames": 442, "video_items": 2, "audio_items": 2, "source_start": 5035}
    c.append(("T1", "ok", grade_t1, (gt, dict(gt), []), "accept"))
    c.append(("T1", "bad-off-by-one", grade_t1,
              (gt, {**gt, "source_start": 5036}, []), "reject"))
    c.append(("T1", "trap-mutation-sibling", grade_t1,
              (gt, dict(gt), ["selftest_base_archived_v01"]), "reject"))
    c.append(("T1", "bad-missing-field", grade_t1,
              (gt, {k: v for k, v in gt.items() if k != "audio_items"}, []), "reject"))

    # --- T2: marker triple + duration
    spec = {"frame": 60, "color": GREEN, "name": "bench-hit"}
    c.append(("T2", "ok", grade_t2, (spec, [{"frame": 60, "color": "Green", "name": "bench-hit"}], [221], [221]), "accept"))
    c.append(("T2", "bad-wrong-frame", grade_t2,
              (spec, [{"frame": 61, "color": "Green", "name": "bench-hit"}], [221], [221]), "reject"))
    c.append(("T2", "bad-wrong-colour", grade_t2,
              (spec, [{"frame": 60, "color": "Blue", "name": "bench-hit"}], [221], [221]), "reject"))
    c.append(("T2", "bad-wrong-name", grade_t2,
              (spec, [{"frame": 60, "color": "Green", "name": "hit"}], [221], [221]), "reject"))
    c.append(("T2", "trap-no-marker", grade_t2, (spec, [], [221], [221]), "reject"))
    c.append(("T2", "rule-colour-case-insensitive", grade_t2,
              (spec, [{"frame": 60, "color": "green", "name": "bench-hit"}], [221], [221]), "accept"))
    c.append(("T2", "bad-duration-drift", grade_t2,
              (spec, [{"frame": 60, "color": "Green", "name": "bench-hit"}], [222], [221]), "reject"))
    # --- T2 payload shapes actually returned by the live probe (see selftest/LIVE_SHAPE.md)
    live_marker = {"60": {"color": "Green", "duration": 1, "note": "shape check",
                          "name": "bench-hit", "customData": ""}}
    c.append(("T2", "rule-live-shape-dict-keyed", grade_t2,
              (spec, live_marker, [221], [221]), "accept"))
    c.append(("T2", "trap-live-shape-frame-in-key-only", grade_t2,
              (spec, {"61": dict(live_marker["60"])}, [221], [221]), "reject"))
    c.append(("T2", "trap-live-shape-frame-key-dropped", grade_t2,
              (spec, [dict(live_marker["60"])], [221], [221]), "reject"))
    # upstream documents the marker dict key as a FLOAT ({96.0: {...}}); after a JSON round-trip
    # that arrives as the string "60.0", which int() raises on. Pinned so the parse stays defensive.
    c.append(("T2", "rule-upstream-float-frame-key", grade_t2,
              (spec, {"60.0": dict(live_marker["60"])}, [221], [221]), "accept"))

    # --- T3: ripple-insert structure
    c.append(("T3", "ok", grade_t3, (ITEMS_OK, SPEC_T3[0], [], [], SPEC_T3[1]), "accept"))
    c.append(("T3", "bad-middle-102", grade_t3,
              ([{"start": 108000, "end": 108221}, {"start": 108221, "end": 108323}, {"start": 108323, "end": 108544}],
               SPEC_T3[0], [], [], SPEC_T3[1]), "reject"))
    c.append(("T3", "bad-gap-left", grade_t3,
              ([{"start": 108000, "end": 108221}, {"start": 108231, "end": 108332}, {"start": 108332, "end": 108553}],
               SPEC_T3[0], [{"start": 108221, "end": 108231}], [], SPEC_T3[1]), "reject"))
    c.append(("T3", "bad-overlap", grade_t3,
              (ITEMS_OK, SPEC_T3[0], [], [{"start": 108200, "end": 108210}], SPEC_T3[1]), "reject"))
    c.append(("T3", "trap-two-items-not-three", grade_t3,
              (ITEMS_OK[:2], SPEC_T3[0], [], [], SPEC_T3[1]), "reject"))

    # --- T7: render loop
    ffspec = {"packets": 121, "codec": "h264", "width": 3840, "height": 1520}
    ok_render = {"packets": 121, "codec_name": "h264", "width": 3840, "height": 1520,
                 "file_exists": True, "duration_ratio": 1.0, "timeline_name": "agbench_T7_r1"}
    c.append(("T7", "ok", grade_t7, (ok_render, ffspec, [], "agbench_T7_r1"), "accept"))
    c.append(("T7", "bad-120-frames", grade_t7,
              ({**ok_render, "packets": 120, "duration_ratio": 120 / 121}, ffspec, [], "agbench_T7_r1"), "reject"))
    c.append(("T7", "bad-collapsed-render", grade_t7,
              ({**ok_render, "packets": 3, "duration_ratio": 0.02}, ffspec, [], "agbench_T7_r1"), "reject"))
    c.append(("T7", "bad-wrong-raster", grade_t7,
              ({**ok_render, "width": 1920, "height": 760}, ffspec, [], "agbench_T7_r1"), "reject"))
    c.append(("T7", "bad-wrong-codec", grade_t7,
              ({**ok_render, "codec_name": "prores"}, ffspec, [], "agbench_T7_r1"), "reject"))
    c.append(("T7", "trap-file-absent", grade_t7,
              ({**ok_render, "packets": 0, "file_exists": False, "duration_ratio": 0.0}, ffspec, [], "agbench_T7_r1"), "reject"))
    c.append(("T7", "bad-job-left-queued", grade_t7, (ok_render, ffspec, [{"Id": "j1"}], "agbench_T7_r1"), "reject"))
    c.append(("T7", "trap-rendered-the-operators-timeline", grade_t7,
              ({**ok_render, "timeline_name": "Master 4k"}, ffspec, [], "agbench_T7_r1"), "reject"))

    # --- T8: Fusion comp really exists
    c.append(("T8", "ok", grade_t8, (1, ["Composition 1"], True), "accept"))
    c.append(("T8", "trap-create-said-success-no-comp", grade_t8, (0, [], True), "reject"))
    c.append(("T8", "bad-unenumerable", grade_t8, (1, [], False), "reject"))
    return c


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    rows, failures = [], []
    for task, label, fn, args, want in cases():
        if only and not task.startswith(only):
            continue
        ok, reasons = fn(*args)
        got = "accept" if ok else "reject"
        behaved = (got == want)
        # rule-* cases exist to pin behaviour, so their "want" is the observed behaviour by design
        if want not in ("accept", "reject"):
            got = want
            behaved = True
        rows.append({"task": task, "case": label, "expected": want, "grader_said": got,
                     "behaved": behaved, "reasons": reasons})
        if not behaved:
            failures.append((task, label, want, got, reasons))

    w = max(len(r["case"]) for r in rows) + 2
    print(f"{'task':5s} {'case':{w}s} {'want':8s} {'grader':8s} ok  reasons")
    for r in rows:
        print(f"{r['task']:5s} {r['case']:{w}s} {r['expected']:8s} {r['grader_said']:8s} "
              f"{'Y' if r['behaved'] else 'N':3s} {r['reasons'][0] if r['reasons'] else ''}")
    total, bad = len(rows), len(failures)
    print(f"\n{total - bad}/{total} grading cases behaved as required")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "selftest", "RESULT.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"cases": rows, "failures": bad}, open(out, "w"), indent=1)
    print(f"wrote {out}")
    if failures:
        for f in failures:
            print("FAILURE:", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
