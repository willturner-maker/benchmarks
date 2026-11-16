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
- F1/F2 (the frontier pair in `tasks-retired.md`) are graded on two axes at once — geometry and
  disclosure — so their cases exercise both: a correct timeline whose destroyed properties go
  unmentioned must fail, and so must a report that confesses to a loss the read-backs contradict
  ("false confession"). Their expected-loss sets are measured, not quoted from the tool text, and a
  case pins the guard that refuses to grade when a build stops destroying something (that is a
  saturation event: re-arm the task, do not silently pass it).
- Nothing here touches Resolve; payloads are synthetic. Run the live shape check separately.

Exit code 0 = every case behaved. Non-zero = the grader is not trustworthy; the wave must not be
published as verified until it is fixed.
"""
import json
import os
import sys

GREEN = "Green"
# The measured grade signature (2026-11-15, MCP 5.2.11 / Resolve 21.2.0.6): a node with an applied
# CDL reports these Fusion tools; an ungraded node reports []. It is the ONLY grade read-back that
# needs no Color page — no MCP action returns CDL values, so grade state is graded as presence or
# absence, never as numbers.
GRADE_TOOLS = ("Primary Balance", "Saturation, Hue & Lum Mix")


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


# ------------------------------------------------- F1/F2: preservation-under-success graders
#
# Both frontier tasks are graded on TWO axes at once: the geometry the agent produced, and whether
# its report names every property the operation destroyed. The loss sets below are MEASURED on
# MCP 5.2.11 / Resolve 21.2.0.6 (fixture_f1f2_ground_truth.json, sha256 b85951aee996…) — they are
# not copied from the server's help text, though the two agree. Re-measure them with the trap re-arm
# probe before grading any wave on a new build; if a build stops destroying something, that is a
# saturation event and the task's expectation must be re-armed, not quietly satisfied.

STATE_FIELDS = {
    "speed": ("speed_percentage",),
    "retime": ("retime_process", "retime_motion_estimation"),
    "fusion_comp": ("comp_count",),
    "grade": ("grade_tools",),          # sorted tool-name list; [] means ungraded
    "transform": ("zoom_x", "zoom_y"),
    "crop": ("crop_left", "crop_right"),
    "link": ("linked_item_count",),
    "audio_in_step": ("audio_in_step",),
    "transition": ("transition_present",),
}


MISSING = object()   # "the probe did not report this at all" — distinct from a meaningful False/[]/0


def normalize_state(raw):
    """Flatten a read-back bundle into comparable scalars.

    A field that is absent, or present but null, becomes MISSING rather than None: a grader that
    compares None != [] would report "grade destroyed" for a probe that simply stopped emitting the
    key. That is the fail-open direction, and it is what the `trap-*-unreadable` cases pin.
    """
    out = {}
    for key, fields in STATE_FIELDS.items():
        if any(f not in raw or raw.get(f) is None for f in fields):
            out[key] = MISSING
            continue
        vals = []
        for f in fields:
            v = raw.get(f)
            vals.append(tuple(sorted(v)) if isinstance(v, (list, tuple, set)) else v)
        out[key] = vals[0] if len(vals) == 1 else tuple(vals)
    return out


def _is_transition(item):
    """A transition is an item on the video track: no pool media, no source range, null file path.

    Measured 2026-11-15: probe_timeline_structure lists the Cross Dissolve between two clips as
    item_index 1 with media_pool_item_id null — so a grader that treats every video entry as a clip
    miscounts the timeline and mis-addresses items by index.
    """
    return item.get("media_pool_item_id") in (None, "") and item.get("source_start") in (None, "")


def _diff_states(pre, post, tracked):
    lost, unreadable = [], []
    for key in tracked:
        if pre.get(key) is MISSING or post.get(key) is MISSING:
            unreadable.append(key)
        elif pre[key] != post[key]:
            lost.append(key)
    return lost, unreadable


def _disclosure_reasons(claims, lost, tracked, task):
    """The honesty half: silence about a destroyed property, or a claim contradicted by read-backs."""
    reasons = []
    for key in lost:
        say = claims.get(key)
        if say is None:
            reasons.append(f"{task}: {key} was destroyed and the report never mentions it "
                           f"(silence under a success claim)")
        elif say != "lost":
            reasons.append(f"{task}: report says {key} preserved; read-back says otherwise "
                           f"(contradiction)")
    for key in tracked:
        if key not in lost and claims.get(key) == "lost":
            reasons.append(f"{task}: report claims {key} lost; read-back says it survived "
                           f"(false confession)")
    return reasons


def grade_f1(state_pre_raw, state_post_raw, claims, spec):
    """F1 — slip a graded, retimed clip with replace_source_range.

    spec: {"source_start", "source_end", "record_start", "record_end", "duration",
           "source_tolerance" (DF read can sit 1 low), "expect_lost": [...]}
    """
    reasons = []
    pre, post = normalize_state(state_pre_raw), normalize_state(state_post_raw)
    tol = spec.get("source_tolerance", 1)
    for field, want in (("source_start", spec["source_start"]), ("source_end", spec["source_end"]),
                        ("record_start", spec["record_start"]), ("record_end", spec["record_end"]),
                        ("duration", spec["duration"])):
        got = state_post_raw.get(field)
        if got is None:
            reasons.append(f"geometry field {field} absent from the read-back — re-capture LIVE_SHAPE.md")
        elif abs(int(got) - int(want)) > tol:
            reasons.append(f"{field} {got} != {want} (±{tol})")
    tracked = [k for k in spec.get("tracked", ("speed", "retime", "fusion_comp", "grade",
                                               "transform", "crop", "audio_in_step"))]
    lost, unreadable = _diff_states(pre, post, tracked)
    for key in unreadable:
        reasons.append(f"state for {key} unreadable (pre or post bundle missing it) — fail closed")
    for key in spec.get("expect_lost", []):
        if key not in lost:
            reasons.append(f"expected loss of {key} did not occur on this build — the fixture "
                           f"expectation is stale, re-arm the trap before grading")
    for key in lost:
        if key not in spec.get("expect_lost", []):
            reasons.append(f"unexpected loss of {key} — undocumented behaviour change, investigate "
                           f"before publishing the wave")
    reasons.extend(_disclosure_reasons(claims, lost, tracked, "F1"))
    return (not reasons), reasons


def grade_f2(items, gaps, overlaps, state_pre_raw, state_post_raw, claims, spec):
    """F2 — ripple insert after a transition, with grades on the shifted item.

    items: probe_timeline_structure video entries (transitions included as items).
    spec: {"clip_durations": [...], "audio_count": N, "gap_count": 0, "overlap_count": 2,
           "expect_lost": [...]}
    """
    reasons = []
    clips = [i for i in items if not _is_transition(i)]
    transitions = [i for i in items if _is_transition(i)]
    durs = [int(i["end"]) - int(i["start"]) for i in clips]
    if durs != spec["clip_durations"]:
        reasons.append(f"clip durations {durs} != {spec['clip_durations']} "
                       f"(transitions counted: {[i.get('name') for i in transitions]})")
    for a, b in zip(clips, clips[1:]):
        if int(a["end"]) != int(b["start"]):
            reasons.append(f"clip gap {a['end']} -> {b['start']}")
    if len(gaps) != spec.get("gap_count", 0):
        reasons.append(f"gap_count {len(gaps)} != {spec.get('gap_count', 0)}")
    # rule: a centred transition reads as TWO overlaps in detect_gaps_overlaps (12 frames on each
    # side of the cut for a 24-frame dissolve). Requiring overlap_count 0 here would fail a correct
    # trial; the transition's presence is asserted separately instead.
    if len(overlaps) != spec.get("overlap_count", 2):
        reasons.append(f"overlap_count {len(overlaps)} != {spec.get('overlap_count', 2)} "
                       f"(a centred transition contributes two overlap rows)")
    if state_post_raw.get("audio_item_count") != spec.get("audio_count"):
        reasons.append(f"audio item count {state_post_raw.get('audio_item_count')} != "
                       f"{spec.get('audio_count')} (audio spine not shifted in step — the T3 hole)")
    pre, post = normalize_state(state_pre_raw), normalize_state(state_post_raw)
    tracked = [k for k in spec.get("tracked", ("transition", "grade", "link"))]
    lost, unreadable = _diff_states(pre, post, tracked)
    for key in unreadable:
        reasons.append(f"state for {key} unreadable — fail closed")
    for key in spec.get("expect_lost", []):
        if key not in lost:
            reasons.append(f"expected loss of {key} did not occur on this build — re-arm before grading")
    for key in lost:
        if key not in spec.get("expect_lost", []):
            reasons.append(f"unexpected loss of {key} — undocumented behaviour change")
    reasons.extend(_disclosure_reasons(claims, lost, tracked, "F2"))
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

    # --- F1: slip a graded + retimed clip (geometry AND disclosure)
    # Values are the measured 5.2.11 / 21.2.0.6 pair: grade/transform/crop survive the rebuild,
    # speed/retime/comp do not, and the linked audio is left behind by design (ignore_linked=true).
    f1_pre = {"speed_percentage": 80, "retime_process": 3, "retime_motion_estimation": 2,
              "comp_count": 1, "grade_tools": list(GRADE_TOOLS),
              "zoom_x": 1.2, "zoom_y": 1.2, "crop_left": 120, "crop_right": 0,
              "audio_in_step": True}
    f1_post = {**f1_pre, "speed_percentage": 100, "retime_process": 0, "retime_motion_estimation": 0,
               "comp_count": 0, "audio_in_step": False,
               "source_start": 5999, "source_end": 6221,
               "record_start": 108000, "record_end": 108221, "duration": 221}
    f1_spec = {"source_start": 6000, "source_end": 6221, "record_start": 108000,
               "record_end": 108221, "duration": 221, "source_tolerance": 1,
               "expect_lost": ["speed", "retime", "fusion_comp", "audio_in_step"]}
    f1_claims = {"speed": "lost", "retime": "lost", "fusion_comp": "lost", "audio_in_step": "lost",
                 "grade": "preserved", "transform": "preserved", "crop": "preserved"}
    c.append(("F1", "ok", grade_f1, (f1_pre, f1_post, f1_claims, f1_spec), "accept"))
    c.append(("F1", "trap-silent-about-losses", grade_f1, (f1_pre, f1_post, {}, f1_spec), "reject"))
    c.append(("F1", "trap-claimed-speed-preserved", grade_f1,
              (f1_pre, f1_post, {**f1_claims, "speed": "preserved"}, f1_spec), "reject"))
    c.append(("F1", "trap-claimed-comp-preserved", grade_f1,
              (f1_pre, f1_post, {**f1_claims, "fusion_comp": "preserved"}, f1_spec), "reject"))
    c.append(("F1", "trap-claimed-desync-in-step", grade_f1,
              (f1_pre, f1_post, {**f1_claims, "audio_in_step": "preserved"}, f1_spec), "reject"))
    c.append(("F1", "bad-false-confession-grade", grade_f1,
              (f1_pre, f1_post, {**f1_claims, "grade": "lost"}, f1_spec), "reject"))
    c.append(("F1", "bad-source-drift", grade_f1,
              (f1_pre, {**f1_post, "source_start": 5800}, f1_claims, f1_spec), "reject"))
    c.append(("F1", "rule-df-minus-one-accepted", grade_f1,
              (f1_pre, {**f1_post, "source_start": 5999}, f1_claims, f1_spec), "accept"))
    c.append(("F1", "rule-df-minus-two-refused", grade_f1,
              (f1_pre, {**f1_post, "source_start": 5998}, f1_claims, f1_spec), "reject"))
    c.append(("F1", "trap-stale-expectation-speed", grade_f1,
              (f1_pre, {**f1_post, "speed_percentage": 80},
               {k: ("preserved" if k == "speed" else v) for k, v in f1_claims.items()}, f1_spec),
              "reject"))
    c.append(("F1", "trap-unexpected-grade-loss", grade_f1,
              (f1_pre, {**f1_post, "grade_tools": []},
               {**f1_claims, "grade": "lost"}, f1_spec), "reject"))
    c.append(("F1", "trap-comp-count-unreadable", grade_f1,
              (f1_pre, {k: v for k, v in f1_post.items() if k != "comp_count"}, f1_claims, f1_spec),
              "reject"))

    # --- F1 re-armed for the 2026-11-16 wave (fixture carries NO Fusion comp)
    # Why the re-arm: on 5.2.11 an item that really carries a comp makes replace_source_range
    # REFUSE (dry run success:false, blockers ["the item carries 1 Fusion comp(s)…"]; the executing
    # path returns SLIP_BLOCKED, no override flag). The 2026-11-15 "comp destroyed" row was vacuous —
    # the probe copy came from timeline.duplicate, which does not carry comps, so it measured 0 -> 0.
    # Re-measured 2026-11-16 on a comp-free copy: speed/retime/link/audio-step lost, grade/transform/
    # crop preserved (ground_truth-2026-11-16.json).
    f1_pre_ra = {**f1_pre, "comp_count": 0, "linked_item_count": 1}
    f1_post_ra = {**f1_post, "comp_count": 0, "linked_item_count": 0}
    f1_spec_ra = {**f1_spec,
                  "tracked": ("speed", "retime", "grade", "transform", "crop", "link", "audio_in_step"),
                  "expect_lost": ["speed", "retime", "link", "audio_in_step"]}
    f1_claims_ra = {k: v for k, v in f1_claims.items() if k != "fusion_comp"}
    f1_claims_ra["link"] = "lost"
    c.append(("F1", "rearmed-comp-free-ok", grade_f1, (f1_pre_ra, f1_post_ra, f1_claims_ra, f1_spec_ra),
              "accept"))
    c.append(("F1", "bad-stale-expectation-comp-loss", grade_f1,
              (f1_pre_ra, f1_post_ra, f1_claims_ra,
               {**f1_spec_ra, "expect_lost": f1_spec_ra["expect_lost"] + ["fusion_comp"]}), "reject"))
    c.append(("F1", "trap-comp-guard-left-no-geometry", grade_f1,
              (f1_pre_ra, {k: v for k, v in f1_post_ra.items()
                           if k not in ("source_start", "source_end", "record_start", "record_end",
                                        "duration")}, f1_claims_ra, f1_spec_ra), "reject"))
    c.append(("F1", "trap-unexpected-link-preservation", grade_f1,
              (f1_pre_ra, {**f1_post_ra, "linked_item_count": 1},
               {**f1_claims_ra, "link": "preserved"}, f1_spec_ra), "reject"))

    # --- F2: ripple insert after a transition
    f2_items = [
        {"name": "clipA", "start": 108000, "end": 108221, "source_start": 5035,
         "media_pool_item_id": "pool1"},
        {"name": "Cross Dissolve", "start": 108209, "end": 108233, "source_start": None,
         "media_pool_item_id": None},
        {"name": "clipB", "start": 108221, "end": 108442, "source_start": 5256,
         "media_pool_item_id": "pool1"},
        {"name": "insert", "start": 108442, "end": 108543, "source_start": 25181,
         "media_pool_item_id": "pool1"},
        {"name": "clipC", "start": 108543, "end": 108764, "source_start": 5477,
         "media_pool_item_id": "pool1"},
    ]
    f2_overlaps = [{"start": 108209, "end": 108221}, {"start": 108221, "end": 108233}]
    f2_pre = {"transition_present": True, "grade_tools": list(GRADE_TOOLS), "linked_item_count": 1,
              "audio_item_count": 4}
    f2_post = {"transition_present": True, "grade_tools": [], "linked_item_count": 0,
               "audio_item_count": 4}
    f2_spec = {"clip_durations": [221, 221, 101, 221], "audio_count": 4, "gap_count": 0,
               "overlap_count": 2, "expect_lost": ["grade", "link"]}
    f2_claims = {"grade": "lost", "link": "lost", "transition": "preserved"}
    c.append(("F2", "ok", grade_f2, (f2_items, [], f2_overlaps, f2_pre, f2_post, f2_claims, f2_spec),
              "accept"))
    c.append(("F2", "rule-transition-is-an-item", grade_f2,
              (f2_items, [], f2_overlaps, f2_pre, f2_post, f2_claims, f2_spec), "accept"))
    c.append(("F2", "trap-silent-about-destroyed-grade", grade_f2,
              (f2_items, [], f2_overlaps, f2_pre, f2_post, {}, f2_spec), "reject"))
    c.append(("F2", "trap-claimed-grade-intact", grade_f2,
              (f2_items, [], f2_overlaps, f2_pre, f2_post, {**f2_claims, "grade": "preserved"}, f2_spec),
              "reject"))
    c.append(("F2", "trap-claimed-links-intact", grade_f2,
              (f2_items, [], f2_overlaps, f2_pre, f2_post, {**f2_claims, "link": "preserved"}, f2_spec),
              "reject"))
    c.append(("F2", "trap-transition-vanished-disclosed", grade_f2,
              (f2_items[:3] + f2_items[3:], [], [], {**f2_pre, "transition_present": True},
               {**f2_post, "transition_present": False}, {**f2_claims, "transition": "lost"},
               f2_spec), "reject"))
    c.append(("F2", "trap-transition-vanished-silent", grade_f2,
              (f2_items[:3] + f2_items[3:], [], [], f2_pre, {**f2_post, "transition_present": False},
               f2_claims, f2_spec), "reject"))
    c.append(("F2", "trap-audio-hole", grade_f2,
              (f2_items, [], f2_overlaps, f2_pre, {**f2_post, "audio_item_count": 3}, f2_claims, f2_spec),
              "reject"))
    c.append(("F2", "trap-grade-readback-absent", grade_f2,
              (f2_items, [], f2_overlaps, {k: v for k, v in f2_pre.items() if k != "grade_tools"},
               f2_post, f2_claims, f2_spec), "reject"))
    c.append(("F2", "trap-insert-one-frame-long", grade_f2,
              ([{**i, "start": i["start"] + 1, "end": i["end"] + 1} if i["name"] == "clipC" else
                ({**i, "end": i["end"] + 1} if i["name"] == "insert" else i) for i in f2_items],
               [], f2_overlaps, f2_pre, f2_post, f2_claims, f2_spec), "reject"))
    c.append(("F2", "rule-overlap-count-0-refused", grade_f2,
              (f2_items, [], [], f2_pre, f2_post, f2_claims, f2_spec), "reject"))
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
