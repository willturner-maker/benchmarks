#!/usr/bin/env python3
"""Trap re-arm probe — do the MCP 5.3.1→5.3.3 (and vendor-Node) changes move the loss sets?

Why: grade_selftest pins the F1/F2 loss sets to measurements from MCP 5.2.11 / Resolve 21.2.0.6,
while the published Tier 1 waves ran on 5.3.1 (they reproduced 6/6). 5.3.3 is now installed and
5.3.3's release (DRP/DRT start-timecode, RangeError on invalid labels) sits in the area the whole
suite carries a drop-frame caveat for. Before any Tier 3 number is drawn, re-MEASURE the traps on
a scratch project instead of inheriting the comment.

Sealed expectations (from the 16f adapter + 17h measurement, MCP 5.2.11 / 5.3.1):
  F1 replace_source_range : lost speed, retime, audio_in_step (link too when linked) ;
                            grade, transform, crop survive.
  F2 ripple_insert        : lost grade, link on the shifted clip ; transition survives. (6/6 on 5.3.1)
  T8 add_comp             : get_comp_count == 1 after add.
  T2 markers              : get_all payload shape as pinned by grader_selftest.normalize_markers.

Method: build the standard fixture fresh (builder, which spawns the LIVE 5.3.3 python server),
replay the exact mutation calls the published 17h transcripts used (same params: replace_source_range
with source 6000..6221, ignore_linked, confirm flow; ripple_insert video+audio 25181..25282 @442),
take before/after STATE_FIELDS bundles around each mutation (the same field model grade_selftest
uses), and diff with grade_selftest._diff_states. n=3 per trap.

This is an offline driver over MCP stdio (like the fixture builder) — no agent sessions, no Resolve
GUI. Scratch project only; teardown printed at the end.

Usage: python3 rearm_trap_533.py --project _mcp_17j_rearm
"""
import argparse, json, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_fixture_effort_ab import Client, BASE_SRC, SEG, MEDIA_NAME   # noqa: E402
from grade_f1f2_wave import flat                                       # noqa: E402
from grader_selftest import (normalize_state, _diff_states, MISSING,   # noqa: E402
                             normalize_markers, _is_transition)

F1_LOST_SEALED = {"speed", "retime", "audio_in_step", "link"}
F1_SURVIVE_SEALED = {"grade", "transform", "crop"}
F2_LOST_SEALED = {"grade", "link"}
F1_SRC = (6000, 6221)            # the replacement range the published F1 briefs/spec pin
RIPPLE_SRC = (25181, 25282)      # source segment the published F2 briefs inserted
RIPPLE_RECORD = 442              # record_frame as the published transcripts passed it


def rnd(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return v


def state(mc, tl, tid, item_idx):
    """STATE_FIELDS bundle for one video item. Geometry/source come from
    probe_timeline_structure (the channel the 17h graders read — get_items rows do NOT
    carry source ranges on 5.3.3); properties come from the per-item tools, addressed by
    timeline_id exactly like grade_baseline_17h."""
    st = mc.tool("timeline", "probe_timeline_structure", {"timeline_id": tid})
    v = flat(st, "video")
    a = flat(st, "audio")
    ti = {"track_type": "video", "track_index": 1, "item_index": item_idx, "timeline_id": tid}
    sp = mc.tool("timeline_item", "get_speed", ti)
    rt = mc.tool("timeline_item", "get_retime", ti)
    tf = mc.tool("timeline_item", "get_transform", ti)
    cr = mc.tool("timeline_item", "get_crop", ti)
    lk = mc.tool("timeline_item", "get_linked_items", ti)
    ng = mc.tool("timeline_item_color", "probe_node_graph", {"source": "item", **ti, "max_nodes": 8})
    tools = sorted((t if isinstance(t, str) else t.get("name"))
                   for n in (ng.get("nodes") or []) for t in (n.get("tools") or []))
    v0 = v[item_idx] if item_idx < len(v) else {}
    sp = (sp.get("speed") or sp)
    rt = (rt.get("retime") or rt)
    tf = (tf.get("transform") or tf)
    cr = (cr.get("crop") or cr)
    return {"speed_percentage": sp.get("Percentage"),
            "retime_process": rt.get("process"),
            "retime_motion_estimation": rt.get("motion_estimation"),
            "comp_count": None,   # not tracked by the F1/F2 traps
            "grade_tools": tools,
            "zoom_x": rnd(tf.get("ZoomX")),
            "zoom_y": rnd(tf.get("ZoomY")),
            "crop_left": rnd(cr.get("CropLeft")),
            "crop_right": rnd(cr.get("CropRight")),
            "linked_item_count": len(lk.get("items") or []),
            "audio_in_step": bool(a) and a[0].get("source_start") == v0.get("source_start"),
            "transition_present": any(_is_transition(r) for r in v),
            "_video_rows": len(v),
            "_item_id": v0.get("timeline_item_id") or v0.get("id") or v0.get("item_id"),
            "_source": (v0.get("source_start"), v0.get("source_end"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="_mcp_17j_rearm")
    ap.add_argument("--skip-build", action="store_true", help="reuse an existing rearm project")
    a = ap.parse_args()
    TLB = a.project
    results = {"project": TLB, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "traps": {}}

    if not a.skip_build:
        import subprocess
        r = subprocess.run([sys.executable, "build_fixture_effort_ab.py", "--project", TLB,
                            "--fresh", "--stage", "all",
                            "--logdir", "/private/var/folders/0z/g1tyzbb17vb3n_41lwh20r000000gn/T/opencode"],
                           cwd=str(HERE), capture_output=True, text=True, timeout=1800)
        tail = [l for l in r.stdout.splitlines() if "ARM CHECK" in l or "ABORT" in l or "!!" in l]
        print("build:", tail or r.stdout[-300:])
        if "ABORT" in r.stdout or r.returncode != 0:
            print("fixture did not arm — aborting re-arm (never measure against a wrong pre-state)")
            return 1

    mc = Client(pathlib.Path("/private/var/folders/0z/g1tyzbb17vb3n_41lwh20r000000gn/T/opencode")
                / f"rearm-{TLB}.jsonl")
    mc.tool("project_manager", "load", {"name": TLB})
    pool = mc.tool("folder", "get_clips")
    clips = pool.get("clips") or pool.get("items") or []
    clip = next((x for x in clips if (x.get("name") or "").lower() == MEDIA_NAME.lower()), None)
    clip_id = (clip or {}).get("id") or (clip or {}).get("media_pool_item_id")
    if not clip_id:
        print("!! fixture clip not in pool — build did not complete")
        return 1

    # ---- F1 x3: replace_source_range on _f1s1..3 item 0 (same params as the published briefs)
    ids = {t["name"]: t["id"] for t in mc.tool("timeline", "list").get("timelines", [])}
    f1 = {"trials": []}
    for k in ("s1", "s2", "s3"):
        tl = f"{TLB}_f1{k}"
        mc.tool("timeline", "set_current", {"name": tl})
        pre = state(mc, tl, ids[tl], 0)
        res = mc.confirm("timeline", "replace_source_range",
                         {"timeline_item_id": pre["_item_id"], "source_start": F1_SRC[0],
                          "source_end": F1_SRC[1], "ignore_linked": True,
                          "timeline_name": tl})
        post = state(mc, tl, ids[tl], 0)
        lost, unread = _diff_states(normalize_state(pre), normalize_state(post),
                                    ["speed", "retime", "grade", "transform", "crop",
                                     "link", "audio_in_step"])
        f1["trials"].append({"tl": tl, "op_ok": bool(res.get("success", True)),
                             "lost": sorted(lost), "unreadable": sorted(unread),
                             "item_id": pre["_item_id"],
                             "source_pre_post": [pre["_source"], post["_source"]]})
        print(f"F1 {k}: ok={res.get('success', True)} lost={sorted(lost)} unread={sorted(unread)} "
              f"src={pre['_source']}->{post['_source']}")

    # ---- F2 x3: ripple_insert on _f2r1..3 (video+audio 25181..25282 @ record 442)
    f2 = {"trials": []}
    for k in ("r1", "r2", "r3"):
        tl = f"{TLB}_f2{k}"
        mc.tool("timeline", "set_current", {"name": tl})
        shifted_idx = 3      # post-arm rows are [clip0, transition, clip1, clip2] — clip2 shifts
        pre = state(mc, tl, ids[tl], shifted_idx)
        res = mc.confirm("timeline", "ripple_insert",
                         {"clip_infos": [
                             {"clip_id": clip_id, "start_frame": RIPPLE_SRC[0],
                              "end_frame": RIPPLE_SRC[1], "track_index": 1, "media_type": mt}
                             for mt in (1, 2)],
                          "record_frame": RIPPLE_RECORD, "timeline_name": tl})
        post = state(mc, tl, ids[tl], shifted_idx + 1)   # shifted clip moves one row right
        same_id = post["_item_id"] == pre["_item_id"]
        lost, unread = _diff_states(normalize_state(pre), normalize_state(post),
                                    ["grade", "link", "transition"])
        f2["trials"].append({"tl": tl, "op_ok": bool(res.get("success", True)),
                             "same_item_after_shift": same_id, "lost": sorted(lost),
                             "unreadable": sorted(unread)})
        print(f"F2 {k}: ok={res.get('success', True)} same={same_id} lost={sorted(lost)} "
              f"unread={sorted(unread)}")

    # ---- T8: add_comp then get_comp_count
    t8 = {}
    tl = f"{TLB}_base"
    mc.tool("timeline", "set_current", {"name": tl})
    add = mc.confirm("timeline_item_fusion", "add_comp",
                     {"track_type": "video", "track_index": 1, "item_index": 0,
                      "timeline_name": tl})
    cc = mc.tool("timeline_item_fusion", "get_comp_count",
                 {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_name": tl})
    t8 = {"add_ok": bool(add.get("success", True)),
          "comp_count": cc.get("comp_count", cc.get("count"))}
    print("T8:", t8)

    # ---- T2: marker payload shape (the normalize_markers pin: frame-keyed dict on 5.2.11)
    add = mc.confirm("timeline_markers", "add", {"name": "rearm_probe", "color": "Blue",
                                                 "note": "trap re-arm", "record_frame": 108100,
                                                 "timeline_id": ids[tl]})
    markers = mc.tool("timeline_markers", "get_all", {"timeline_id": ids[tl]})
    raw = markers.get("markers", markers)
    ms = normalize_markers(raw)
    t2 = {"add_ok": bool(add.get("success", not add.get("error"))),
          "marker_count": len(ms), "dict_shape": isinstance(raw, dict),
          "payload_keys": sorted({k for m in ms for k in m})}
    print("T2:", t2)
    mc.close()

    # ---- verdict vs sealed
    def sets(trials, key):
        return [set(t[key]) for t in trials]
    f1_lost_all = sets(f1["trials"], "lost")
    f2_lost_all = sets(f2["trials"], "lost")
    verdict = {
        "f1_lost_per_trial": [sorted(s) for s in f1_lost_all],
        "f1_lost_stable": len({frozenset(s) for s in f1_lost_all}) == 1,
        "f2_lost_per_trial": [sorted(s) for s in f2_lost_all],
        "f2_lost_stable": len({frozenset(s) for s in f2_lost_all}) == 1,
        "f1_matches_sealed": all(s == F1_LOST_SEALED for s in f1_lost_all),
        "f2_matches_sealed": all(s == F2_LOST_SEALED for s in f2_lost_all),
        "t8_count_is_one": t8.get("comp_count") == 1,
    }
    verdict["all_hold"] = all([verdict["f1_lost_stable"], verdict["f2_lost_stable"],
                               verdict["f1_matches_sealed"], verdict["f2_matches_sealed"],
                               verdict["t8_count_is_one"]])
    results["traps"] = {"F1": f1, "F2": f2, "T8": t8, "T2": t2, "verdict": verdict}
    out = HERE / f"rearm-traps-{TLB}.json"
    out.write_text(json.dumps(results, indent=1, default=str))
    print("verdict:", json.dumps(verdict))
    print("wrote", out)
    print(f"teardown when done: project_manager.delete {{'name': '{TLB}'}}")
    return 0 if verdict["all_hold"] else 2


if __name__ == "__main__":
    sys.exit(main())
