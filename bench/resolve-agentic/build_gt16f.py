#!/usr/bin/env python3
"""Adapt the 2026-11-17g dual-arm ground truth (+prestate) to the 16f grader shape.

Inputs (all operator read-backs, never agent claims):
  ground_truth-<proj>.json  : probe_timeline_structure per timeline (sealed pre-wave)
  prestate-<proj>.json      : get_speed/get_retime/probe_node_graph/get_transform/get_crop/
                              get_linked_items per video item (sealed pre-wave)
Output:
  ground_truth-<proj>-16f.json : {"_meta","base","T1","f1","f2"} as grade_f1f2_wave.py expects.
Values are copied, not interpreted. Clip property blobs are dropped (grader never reads them).
"""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent

def strip_items(pr):
    out = []
    for it in (pr.get("tracks", {}).get("video", {}).get("tracks", [{}])[0].get("items", [])):
        it = {k: v for k, v in it.items() if k != "clip_properties"}
        out.append(it)
    return out

def main(proj):
    gt = json.load(open(HERE / f"ground_truth-{proj}.json"))
    pre = json.load(open(HERE / f"prestate-{proj}.json"))
    tls = gt["timelines"]
    p = lambda name: tls[f"{proj}{name}"]["probe"]

    t1v = strip_items(p("_T1"))
    t1a = tls[f"{proj}_T1"]["probe"].get("tracks", {}).get("audio", {})
    T1 = {"timeline": f"{proj}_T1", "timeline_id": tls[f"{proj}_T1"]["id"],
          "duration_frames": max(i["end"] for i in t1v) - min(i["start"] for i in t1v),
          "video_items": len(t1v),
          "audio_items": len(t1a.get("tracks", [{}])[0].get("items", [])),
          "video_tracks": p("_T1")["tracks"]["video"]["track_count"],
          "audio_tracks": t1a.get("track_count", 1),
          "item1_record": [t1v[0]["start"], t1v[0]["end"]]}

    f1v = strip_items(p("_f1s1"))[0]
    f1pre = next(i for i in pre[f"{proj}_f1s1"] if i["item_index"] == 0)
    f1 = {"timeline": f"{proj}_f1m", "trials": {f"f1s{k}": {"timeline": f"{proj}_f1s{k}"} for k in (1, 2, 3)},
          "pre_state": {"video_0": {
              "source_start": f1v["source_start"], "source_end_exclusive": f1v["source_end"],
              "record": [f1v["start"], f1v["end"]], "duration": f1v["end"] - f1v["start"],
              "speed": f1pre["speed"], "retime": f1pre["retime"],
              "grade_tools": f1pre["grade_tools"], "transform": f1pre["transform"],
              "crop": f1pre["crop"], "linked_item_count": f1pre["linked_item_count"]}}}

    f2v = strip_items(p("_f2r1"))
    f2pre = {i["item_index"]: i for i in pre[f"{proj}_f2r1"]}
    items = []
    for it in f2v:
        idx = it["item_index"]
        is_tr = it.get("media_pool_item_id") in (None, "") and it.get("source_start") in (None, "")
        ent = {"item_index": idx, "kind": "transition" if is_tr else "clip",
               "record": [it["start"], it["end"]]}
        if not is_tr:
            ent.update({"source_start": it["source_start"], "source_end_exclusive": it["source_end"],
                        "grade_tools": f2pre[idx]["grade_tools"] or [],
                        "linked_item_count": f2pre[idx]["linked_item_count"]})
        else:
            ent["name"] = it.get("name")
        items.append(ent)
    f2 = {"timeline": f"{proj}_f2m", "trials": {f"f2r{k}": {"timeline": f"{proj}_f2r{k}"} for k in (1, 2, 3)},
          "pre_state": {"video_items_including_transition": items}}

    out = {"_meta": {"project": proj, "wave": "2026-11-17g effort A/B",
                     "derived_from": [f"ground_truth-{proj}.json", f"prestate-{proj}.json"],
                     "geometry_convention": "END-EXCLUSIVE (probe semantics); DF reads 1 low",
                     "media": "class A (fixture.json)"},
           "base": {"timeline": f"{proj}_base"}, "T1": T1, "f1": f1, "f2": f2}
    dst = HERE / f"ground_truth-{proj}-16f.json"
    dst.write_text(json.dumps(out, indent=1))
    print("wrote", dst, "| T1 dur:", T1["duration_frames"], "| f2 items:", len(items))

if __name__ == "__main__":
    for proj in sys.argv[1:]:
        main(proj)
