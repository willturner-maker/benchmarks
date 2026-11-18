#!/usr/bin/env python3
"""Grader — 2026-11-17h baseline wave. Read-backs only; same predicates as the 58/58 self-test.

Differences from grade_f1f2_wave.py, each traceable to a 17g VALIDITY finding:

1. T8 grades from the IN-TRIAL snapshot (snapshots/<task>.json, written by the driver at
   session end), NOT from a post-wave read. flaw 3: comps attached in-wave did not survive the
   project close/load churn (six 17g trials read 1 in-wave, 0 after). The post-wave read is
   still taken and recorded — as PRODUCT-BEHAVIOR data (does an attached comp survive?),
   never as the score.
2. Single project: no --sibling-projects merge, no cross-project placement table. Instead the
   per-trial snapshot carries a timeline census (`timelines_present`), which is the placement
   audit for this wave: a trial's own timeline must appear in its own snapshot.
3. F2 grade dimension: the 17g fixture armed the grade on the WRONG item, so no wave has ever
   measured what a ripple insert does to a correctly-placed grade. It is therefore graded in
   two ways and BOTH are recorded: `fixture_safe` (grade not asserted — the headline outcome)
   and `strict` (grade asserted). If strict and fixture_safe disagree on grade, the fixture's
   loss expectation needs a measurement pass before any future wave asserts it.

Usage:
  python3 -I grade_baseline_17h.py --gt ground_truth-_mcp_AGBench-2026-11-17h.json \
      --wave results/baseline-2026-11-17h --claims claims-baseline-17h.json \
      --render-root <real volume> --out results/baseline-2026-11-17h/grading.json
"""
import argparse, glob, json, os, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grader_selftest as gs
import grade_f1f2_wave as gw            # reuse the MCP stdio Client + flat()/rnd()/ffprobe_render()


def snap_read(wdir, task):
    p = pathlib.Path(wdir) / "snapshots" / f"{task}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--wave", required=True)
    ap.add_argument("--claims", required=True)
    ap.add_argument("--render-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sealed-gt", default=None,
                    help="the full sealed pre-wave census (ground_truth-<proj>.json, the one with a "
                         "'timelines' map) — used only for the stray-timeline check; the -16f adapter "
                         "carries grading values, not the census")
    ap.add_argument("--sealed-gt-sha256", default=None)
    args = ap.parse_args()

    gt = json.load(open(args.gt))
    claims = json.load(open(args.claims))
    wdir = pathlib.Path(args.wave)
    wr = json.load(open(wdir / "wave_results.json"))
    tl_base = wr["tl_base"]
    trials = {t["task"]: t for t in wr["trials"]}

    c = gw.Client()
    verdicts, problems = {}, []

    def rec(task, ok, notes):
        (verdicts.setdefault(task, {}).setdefault("pass" if ok else "fail", []).append(task[-2:]))
        if notes:
            verdicts[task].setdefault("notes", []).append(f"{task[-2:]}: {notes}")

    def expected_tl(task):
        """Timeline a trial is supposed to be working on: T1 reads the prebuilt _T1 (it is
        read-only, so it creates nothing); T2/T3/T7/T8 duplicate to their own _<task>;
        F trials act on the prebuilt lowercase copies."""
        if task.startswith("T1"):
            return [f"{tl_base}_T1"]
        if task.startswith(("T2", "T3", "T7", "T8")):
            return [f"{tl_base}_{task}"]
        if task.startswith("F1"):
            return [f"{tl_base}_f1s{task[-1]}"]
        return [f"{tl_base}_f2r{task[-1]}"]

    def placement(task, kind):
        """Placement audit from the in-trial snapshot: the trial's target timeline must appear
        in the census taken at ITS session end."""
        s = snap_read(wdir, task)
        if s is None:
            problems.append(f"no in-trial snapshot for {task}")
            return None
        want = set(expected_tl(task))
        hit = [n for n in s.get("timelines_present", []) if n in want]
        verdicts.setdefault(task, {})["snapshot"] = {
            "ts": s.get("ts"), "timelines_present": len(s.get("timelines_present", [])),
            "target_timeline_seen": hit}
        if not hit:
            problems.append(f"{task}: target timeline absent from its own snapshot census")
        return s

    try:
        c.tool("project_manager", "load", {"name": tl_base})
        tids = {t["name"]: t["id"] for t in c.tool("timeline", "list").get("timelines", [])}
        census = json.load(open(args.sealed_gt))["timelines"] if args.sealed_gt else {}
        now = sorted(n for n in tids if n.startswith(tl_base))
        # post-wave census is compared to the SEALED pre-wave one: expected additions are the
        # trial-created timelines; MCP auto-archive copies are reported, not flagged; anything
        # else is a stray worth investigating before the record is published.
        expected_extra = {f"{tl_base}_{t}" for t in
                          ("T2r1", "T2r2", "T2r3", "T3r1", "T3r2", "T3r3",
                           "T7r1", "T7r2", "T7r3", "T8r1", "T8r2", "T8r3")}
        archived = [n for n in now if "_archived_" in n]
        unexplained = sorted(n for n in now
                             if n not in census and n not in expected_extra and "_archived_" not in n)
        missing = sorted(n for n in census if n not in tids)
        stray = {"post_wave_count": len(now), "sealed_count": len(census),
                 "expected_trial_created_present": sorted(n for n in now if n in expected_extra),
                 "mcp_archived_copies": archived, "unexplained_additions": unexplained,
                 "sealed_timelines_now_absent": missing}
        tnames = sorted(n for n in tids if n.startswith(tl_base))

        # ---- T1 (read-only report vs sealed gt; mutation ruled out by absent archive) ----
        t1_siblings = [n for n in tnames if n.endswith("_T1_archived_v01")]
        expected_t1 = {k: gt["T1"][k] for k in
                       ("duration_frames", "video_items", "video_tracks", "audio_tracks")}
        for k in ("r1", "r2", "r3"):
            rep = claims.get(f"T1{k}", {}).get("reported")
            if rep is None:
                ok, why = False, [f"no operator-extracted reported values for T1{k} in claims"]
            else:
                ok, why = gs.grade_t1(expected_t1, rep, t1_siblings)
            placement(f"T1{k}", "T")
            rec(f"T1{k}", ok, "; ".join(why))

        # ---- T2 marker ----
        for k in ("r1", "r2", "r3"):
            name = f"{tl_base}_T2{k}"
            tid = tids.get(name)
            if tid is None:
                # FAIL CLOSED, read nothing: a None timeline_id makes the MCP fall back to the
                # CURRENT timeline, which silently grades some other trial's work (this is
                # exactly what happened on the first run of this grader for T2r1).
                rec(f"T2{k}", False, [f"target timeline {name} does not exist at grading time — "
                                      f"the agent created nothing; no read attempted"])
                placement(f"T2{k}", "T")
                continue
            mk = c.tool("timeline_markers", "get_all", {"timeline_name": name})
            items = c.tool("timeline", "get_items", {"track_type": "video", "track_index": 1,
                                                     "timeline_id": tid})
            durs = [it["end"] - it["start"] for it in items.get("items", [])]
            ok, why = gs.grade_t2({"frame": 60, "color": "Green", "name": "bench-hit"},
                                  mk.get("markers", mk), durs, [221, 221])
            placement(f"T2{k}", "T")
            rec(f"T2{k}", ok, "; ".join(why))

        # ---- T3 ripple insert ----
        for k in ("r1", "r2", "r3"):
            name = f"{tl_base}_T3{k}"
            tid = tids.get(name)
            if tid is None:
                rec(f"T3{k}", False, [f"target timeline {name} does not exist at grading time — "
                                      f"the agent created nothing; no read attempted"])
                placement(f"T3{k}", "T")
                continue
            st = c.tool("timeline", "probe_timeline_structure", {"timeline_id": tid})
            go = c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid})
            ok, why = gs.grade_t3(gw.flat(st, "video"), [221, 101, 221],
                                  go.get("gaps", []), go.get("overlaps", []), 543)
            placement(f"T3{k}", "T")
            rec(f"T3{k}", ok, "; ".join(why))

        # ---- T7 render loop ----
        queued = c.tool("render", "list_jobs").get("jobs", [])
        for k in ("r1", "r2", "r3"):
            files = (glob.glob(os.path.join(args.render_root, f"T7{k}", "*.mov")) +
                     glob.glob(os.path.join(args.render_root, f"T7{k}", "*.mp4")))
            fp = gw.ffprobe_render(files[0] if files else None)
            if fp.get("duration"):
                fp["duration_ratio"] = fp["duration"] / (121 / 29.97)
            ok, why = gs.grade_t7(fp, {"packets": 121, "codec": "h264", "width": 3840,
                                       "height": 1520}, queued, f"{tl_base}_T7{k}")
            verdicts.setdefault("T7" + k, {})["render_file"] = files[:1]
            placement(f"T7{k}", "T")
            rec(f"T7{k}", ok, "; ".join(why))

        # ---- T8 — GRADED FROM THE IN-TRIAL SNAPSHOT (flaw 3) ----
        post_wave_comps = {}
        for k in ("r1", "r2", "r3"):
            task = f"T8{k}"
            name = f"{tl_base}_T8{k}"
            s = placement(task, "T")
            entry = None
            if s:
                for tlname, sn in (s.get("owned") or {}).items():
                    fc = sn.get("fusion_comps") or []
                    if any(x.get("item_index") == 0 for x in fc):
                        entry = next(x for x in fc if x.get("item_index") == 0)
                        break
            if entry is None:
                ok, why = False, ["no in-trial fusion read-back for item 0 — fail closed "
                                  "(the driver snapshot did not capture the task's target item)"]
            else:
                ok, why = gs.grade_t8(entry.get("comp_count"), entry.get("comp_names"))
                why = [f"GRADED AT IN-TRIAL SNAPSHOT {s.get('ts')}: " + w for w in why]
            verdicts.setdefault(task, {})["in_trial"] = entry
            # post-wave read = product-behavior data, never the score
            tid = tids.get(name)
            if tid is None:
                post = {"note": "target timeline absent at grading time — no read attempted"}
            else:
                cc = c.tool("timeline_item_fusion", "get_comp_count",
                            {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
                cn = c.tool("timeline_item_fusion", "get_comp_names",
                            {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
                post = {"comp_count": cc.get("comp_count", cc.get("count")),
                        "comp_names": cn.get("comp_names", cn.get("names"))}
            post_wave_comps[task] = {"post_wave": post, "in_trial": entry}
            verdicts.setdefault(task, {})["post_wave_read_product_behavior_only"] = post
            rec(task, ok, "; ".join(why))
        verdicts.setdefault("T8", {})["comp_survival_across_project_load"] = post_wave_comps

        # ---- F1 slip with replace_source_range ----
        f1pre_v = gt["f1"]["pre_state"]["video_0"]
        for k in ("r1", "r2", "r3"):
            name = f"{tl_base}_f1{k.replace('r','s')}"
            tid = tids.get(name)
            if tid is None:
                rec(f"F1{k}", False, [f"fixture timeline {name} missing at grading time — "
                                      f"operator-side fixture problem, not an agent failure"])
                placement(f"F1{k}", "F")
                continue
            st = c.tool("timeline", "probe_timeline_structure", {"timeline_id": tid})
            go = c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid})
            v, a0 = gw.flat(st, "video"), gw.flat(st, "audio")
            def flat_payload(p, inner):
                if isinstance(p, dict) and inner in p and isinstance(p[inner], dict):
                    return {**p, **p[inner]}
                return p or {}
            sp = flat_payload(c.tool("timeline_item", "get_speed",
                       {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid}), "speed")
            rt = flat_payload(c.tool("timeline_item", "get_retime",
                       {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid}), "retime")
            tf = flat_payload(c.tool("timeline_item", "get_transform",
                       {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid}), "transform")
            cr = flat_payload(c.tool("timeline_item", "get_crop",
                       {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid}), "crop")
            lk = c.tool("timeline_item", "get_linked_items",
                        {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            ng = c.tool("timeline_item_color", "probe_node_graph", {"source": "item", "track_type": "video",
                                                                    "track_index": 1, "item_index": 0, "timeline_id": tid})
            cc = c.tool("timeline_item_fusion", "get_comp_count",
                        {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            v0 = v[0]
            grade_tools = [t if isinstance(t, str) else t.get("name")
                           for node in ng.get("nodes", []) for t in node.get("tools", [])]
            post = {"source_start": gw.rnd(v0.get("source_start")), "source_end": gw.rnd(v0.get("source_end")),
                    "record_start": v0.get("start"), "record_end": v0.get("end"),
                    "duration": (v0.get("end") or 0) - (v0.get("start") or 0),
                    "speed_percentage": sp.get("Percentage") if "Percentage" in sp else (sp.get("speed") or {}).get("Percentage"),
                    "retime_process": rt.get("process"),
                    "retime_motion_estimation": rt.get("motion_estimation"),
                    "comp_count": cc.get("comp_count", cc.get("count")),
                    "grade_tools": sorted(grade_tools),
                    "zoom_x": gw.rnd(tf.get("ZoomX")), "zoom_y": gw.rnd(tf.get("ZoomY")),
                    "crop_left": gw.rnd(cr.get("CropLeft")), "crop_right": gw.rnd(cr.get("CropRight")),
                    "linked_item_count": len(lk.get("items", [])),
                    "audio_in_step": bool(a0) and a0[0].get("source_start") == v0.get("source_start")}
            pre = {"source_start": f1pre_v["source_start"], "source_end": f1pre_v["source_end_exclusive"],
                   "record_start": f1pre_v["record"][0], "record_end": f1pre_v["record"][1],
                   "duration": f1pre_v["duration"], "speed_percentage": f1pre_v["speed"]["Percentage"],
                   "retime_process": f1pre_v["retime"]["process"],
                   "retime_motion_estimation": f1pre_v["retime"]["motion_estimation"],
                   "comp_count": 0, "grade_tools": sorted(f1pre_v.get("grade_tools") or []),
                   "zoom_x": gw.rnd(f1pre_v["transform"]["ZoomX"]), "zoom_y": gw.rnd(f1pre_v["transform"]["ZoomY"]),
                   "crop_left": gw.rnd(f1pre_v["crop"]["CropLeft"]), "crop_right": 0,
                   "linked_item_count": f1pre_v["linked_item_count"], "audio_in_step": True}
            spec = {"source_start": 6000, "source_end": 6221, "record_start": 108000, "record_end": 108221,
                    "duration": 221, "source_tolerance": 1,
                    "expect_lost": ["speed", "retime", "audio_in_step"]}
            ok, why = gs.grade_f1(pre, post, claims.get(f"F1{k}", {}), spec)
            verdicts.setdefault("F1" + k, {})["post"] = {kk: post[kk] for kk in
                ("source_start", "source_end", "speed_percentage", "retime_process", "comp_count",
                 "grade_tools", "zoom_x", "crop_left", "linked_item_count", "audio_in_step")}
            placement(f"F1{k}", "F")
            rec(f"F1{k}", ok, "; ".join(why))

        # ---- F2 ripple insert after transition (CORRECTLY ARMED this wave) ----
        f2pre = gt["f2"]["pre_state"]
        f2c = f2pre["video_items_including_transition"][3]
        f2_measure = {}
        for k in ("r1", "r2", "r3"):
            task = f"F2{k}"
            name = f"{tl_base}_f2{k}"
            tid = tids.get(name)
            if tid is None:
                rec(f"F2{k}", False, [f"fixture timeline {name} missing at grading time — "
                                      f"operator-side fixture problem, not an agent failure"])
                placement(f"F2{k}", "F")
                continue
            st = c.tool("timeline", "probe_timeline_structure", {"timeline_id": tid})
            go = c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid})
            v, aud = gw.flat(st, "video"), gw.flat(st, "audio")
            clips = [i for i in v if not gs._is_transition(i)]
            shifted_idx = v.index(clips[-1])
            ng = c.tool("timeline_item_color", "probe_node_graph", {"source": "item", "track_type": "video",
                                                                    "track_index": 1, "item_index": shifted_idx,
                                                                    "timeline_id": tid})
            lk = c.tool("timeline_item", "get_linked_items", {"track_type": "video", "track_index": 1,
                                                              "item_index": shifted_idx, "timeline_id": tid})
            grade_tools = [t if isinstance(t, str) else t.get("name")
                           for node in ng.get("nodes", []) for t in node.get("tools", [])]
            pre = {"grade_tools": sorted(f2c.get("grade_tools", [])),
                   "linked_item_count": f2c.get("linked_item_count", 1), "transition_present": True}
            post = {"grade_tools": sorted(grade_tools), "linked_item_count": len(lk.get("items", [])),
                    "transition_present": any(gs._is_transition(i) for i in v),
                    "audio_item_count": len(aud)}
            base = {"clip_durations": [221, 221, 101, 221], "audio_count": 4,
                    "gap_count": 0, "overlap_count": 2, "expect_lost": ["link"]}
            # fixture_safe: grade dimension NOT asserted (no wave has measured what a ripple
            # insert does to a correctly-placed grade; the 17g fixture put it on the wrong item)
            safe_ok, safe_why = gs.grade_f2(v, go.get("gaps", []), go.get("overlaps", []), pre, post,
                                            claims.get(task, {}), {**base, "tracked": ["transition", "link"]})
            # strict: grade asserted too, to MEASURE the dimension and check the report's honesty
            strict_ok, strict_why = gs.grade_f2(v, go.get("gaps", []), go.get("overlaps", []), pre, post,
                                                claims.get(task, {}), {**base, "tracked": ["transition",
                                                                                           "grade", "link"]})
            lost, _unread = gs._diff_states(gs.normalize_state(pre), gs.normalize_state(post),
                                            ["transition", "grade", "link"])
            f2_measure[task] = {"observed_lost": sorted(lost),
                                "pre_grade_tools": pre["grade_tools"],
                                "post_grade_tools": post["grade_tools"]}
            verdicts.setdefault(task, {})["post"] = post
            verdicts.setdefault(task, {})["f2_grade_dimension"] = {
                "fixture_safe": safe_ok, "strict": strict_ok, "observed_lost": sorted(lost),
                "note": "headline outcome = fixture_safe; strict exists to measure the grade "
                        "dimension for the first time on a correctly armed pre-state"}
            placement(task, "F")
            rec(task, safe_ok, "; ".join(safe_why))
    finally:
        c.close()

    total_pass = sum(len(v.get("pass", [])) for v in verdicts.values() if "pass" in v or "fail" in v)
    total_done = sum(1 for v in verdicts.values() if "pass" in v or "fail" in v)
    out = {
        "wave": wdir.name,
        "graded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sealed_gt_sha256": args.sealed_gt_sha256,
        "single_project": tl_base,
        "post_wave_census_vs_sealed": stray,
        "grading_basis": "post-wave read-backs via community MCP stdio client; predicates from "
                        "grader_selftest.py (self-test green before this run); T8 graded from "
                        "snapshots/<task>.json written at each session's end",
        "t8_basis": "in-trial snapshot (flaw 3); post-wave comp reads recorded under "
                    "verdicts.T8.comp_survival_across_project_load as product-behavior data",
        "f2_grade_dimension": f2_measure,
        "claims_basis": "operator-extracted per-trial claim maps from the archived reports "
                        "(full text in sessions/<trial>/events.json)",
        "placement_problems": problems,
        "verdicts": verdicts,
        "outcome": f"{total_pass}/{total_done}",
    }
    pathlib.Path(args.out).write_text(json.dumps(out, indent=1))
    for task in sorted(verdicts):
        v = verdicts[task]
        if "pass" in v or "fail" in v:
            print(task, "PASS" if "pass" in v else "FAIL", v.get("notes", ""))
    if problems:
        print("PLACEMENT/SNAPSHOT PROBLEMS:", problems)
    print("OUTCOME:", out["outcome"], "->", args.out)
    return 0 if total_pass == total_done and not problems else 1


if __name__ == "__main__":
    sys.exit(main())
