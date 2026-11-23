#!/usr/bin/env python3
"""Derive the grader-format (-16f) ground truth from the builder's sealed gt + prestate.

The builder writes {_meta, timelines{...}} (raw probe read-backs) + prestate_<project>.json
(per-item property reads). grade_f1f2_wave.py consumes the OLDER flat format ({base,T1,f1,f2})
introduced in the 2026-11-16f era; every wave since 17h has derived it from the sealed files.
This is that derivation, now as an instrument instead of an ad-hoc operator step. Geometry is
END-EXCLUSIVE (probe semantics); duration_frames computed end-start.

Usage: python3 derive_grader_gt_16f.py <project> [--wave NAME] [--out FILE]
"""
import argparse, json, pathlib

def find(d, suffix):
    k = next(x for x in d if x.endswith(suffix))
    return k, d[k]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--wave", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parent
    g = json.load(open(root / f"ground_truth-{a.project}.json"))["timelines"]
    p = json.load(open(root / f"prestate-{a.project}.json"))

    tk, t1 = find(g, "_T1")
    probe = t1["probe"]
    vid = sum(tr["item_count"] for tr in probe["tracks"]["video"]["tracks"])
    aud = sum(tr["item_count"] for tr in probe["tracks"]["audio"]["tracks"])
    it0 = probe["tracks"]["video"]["tracks"][0]["items"][0]
    T1 = {"timeline": tk, "timeline_id": t1["id"],
          "duration_frames": probe["end_frame"] - probe["start_frame"],
          "video_items": vid, "audio_items": aud,
          "video_tracks": probe["tracks"]["video"]["track_count"],
          "audio_tracks": probe["tracks"]["audio"]["track_count"],
          "item1_record": [it0.get("start", 108000), it0.get("end", 108221)]}

    fk, f1m = find(g, "_f1m")
    f1p = p[f"{a.project}_f1s1"]
    src = f1m["probe"]["tracks"]["video"]["tracks"][0]["items"][0]
    v0 = {"source_start": src["source_start"], "source_end_exclusive": src["source_end"],
          "record": [src["start"], src["end"]], "duration": src["duration"],
          "speed": f1p[0]["speed"], "retime": f1p[0]["retime"], "grade_tools": f1p[0]["grade_tools"],
          "transform": f1p[0]["transform"], "crop": f1p[0]["crop"],
          "linked_item_count": f1p[0]["linked_item_count"]}
    f1 = {"timeline": fk,
          "trials": {f"f1s{k}": {"timeline": f"{a.project}_f1s{k}"} for k in (1, 2, 3)},
          "pre_state": {"video_0": v0}}

    gk, f2m = find(g, "_f2m")
    f2p = p[f"{a.project}_f2m"]
    gitems = f2m["probe"]["tracks"]["video"]["tracks"][0]["items"]
    items = [{"item_index": n, "kind": ps["kind"],
              "record": [i["start"], i["end"]], "source_start": i.get("source_start"),
              "source_end_exclusive": i.get("source_end"),
              "grade_tools": ps["grade_tools"], "linked_item_count": ps["linked_item_count"]}
             for n, (i, ps) in enumerate(zip(gitems, f2p))]
    f2 = {"timeline": gk,
          "trials": {f"f2r{k}": {"timeline": f"{a.project}_f2r{k}"} for k in (1, 2, 3)},
          "pre_state": {"video_items_including_transition": items}}

    out = {"_meta": {"project": a.project, "wave": a.wave,
                     "derived_from": [f"ground_truth-{a.project}.json", f"prestate-{a.project}.json"],
                     "geometry_convention": "END-EXCLUSIVE (probe semantics); DF reads 1 low",
                     "media": "class A (fixture.json)"},
           "base": {"timeline": f"{a.project}_base"}, "T1": T1, "f1": f1, "f2": f2}
    op = pathlib.Path(a.out) if a.out else root / f"ground_truth-{a.project}-16f.json"
    op.write_text(json.dumps(out, indent=1) + "\n")
    print("wrote", op)
    print("T1:", json.dumps(T1))
    print("f2 items:", [(i["kind"], i["record"], bool(i["grade_tools"])) for i in items])

if __name__ == "__main__":
    main()
