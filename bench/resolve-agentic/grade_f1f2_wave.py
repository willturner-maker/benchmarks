#!/usr/bin/env python3
"""Operator grading driver for an F1/F2-series wave: live read-backs only.

Reuses the grading predicates from grader_selftest.py (the same ones the 58/58
self-test pins) and drives the community Resolve MCP server over stdio, exactly
like probe_build_sweep.py does for timed probes. Claims maps for F1/F2 honesty
are passed in as a JSON file (operator-extracted from each trial's report);
the geometry/loss side is fully mechanical.

Usage:
  python3 -I grade_f1f2_wave.py --gt ground_truth-YYYY-MM-DDx.json \
      --wave results/...-wave/ --claims claims.json --out results/.../grading.json

claims.json: {"F1r1": {"speed":"lost",...}, "F2r1": {...}} and an optional
"_deviations" list copied into the record.
"""
import argparse, glob, json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grader_selftest as gs

PROTO = "2024-11-05"
LIVE = pathlib.Path.home() / "Library/Application Support/davinci-resolve-mcp"


def server_env():
    oc = pathlib.Path.home() / ".config" / "opencode" / "opencode.json"
    if oc.exists():   # 2026-11-17: MCP registry lives in the OpenCode global config now
        srv = json.load(open(oc))["mcp"]["servers"]["davinci-resolve"]
    else:
        cfg = json.load(open(pathlib.Path.home() / ".claude.json"))
        srv = cfg["mcpServers"]["davinci-resolve"]
    env = dict(os.environ)
    env.update(srv.get("environment") or srv.get("env") or {})
    return env


class Client:
    def __init__(self):
        env = server_env()
        py = (LIVE / "venv/bin/python") if (LIVE / "venv/bin/python").exists() else sys.executable
        self.p = subprocess.Popen([str(py), "src/server.py"], cwd=str(LIVE), env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.nid = 0
        self._rpc("initialize", {"protocolVersion": PROTO, "capabilities": {},
                                 "clientInfo": {"name": "wave-grader", "version": "1"}})
        self._notify("notifications/initialized", {})

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n"); self.p.stdin.flush()

    def _notify(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _rpc(self, method, params):
        self.nid += 1; rid = self.nid
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"server died during {method}")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg["result"]

    def tool(self, name, action, params=None):
        res = self._rpc("tools/call", {"name": name, "arguments": {"action": action, "params": params or {}}})
        text = ""
        for c in res.get("content", []):
            if c.get("type") == "text":
                text += c["text"]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text[:800]}

    def close(self):
        try:
            self.p.stdin.close(); self.p.terminate(); self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def rnd(x):
    return round(x, 4) if isinstance(x, float) else x


def flat(st, kind):
    """probe_timeline_structure: tracks.{video,audio}.tracks[] -> flat item list (LIVE_SHAPE.md)."""
    out = []
    for trk in (st.get("tracks", {}).get(kind, {}) or {}).get("tracks", []):
        out += trk.get("items", [])
    return out


def ffprobe_render(path):
    if not path or not os.path.exists(path):
        return {"file_exists": False}
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                        "-show_entries", "stream=codec_name,width,height,nb_read_packets:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    st = (d.get("streams") or [{}])[0]
    fmt = d.get("format") or {}
    dur = float(fmt.get("duration") or 0)
    return {"file_exists": True, "codec_name": st.get("codec_name"),
            "width": st.get("width"), "height": st.get("height"),
            "packets": st.get("nb_read_packets"), "duration": dur}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--wave", required=True)
    ap.add_argument("--claims", required=True)
    ap.add_argument("--render-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sealed-gt-sha256", default=None)
    ap.add_argument("--unmeasurable", default=None)
    ap.add_argument("--wave-results", default=None,
                    help="override wave_results.json (per-arm view in the 2026-11-17g dual-arm wave)")
    ap.add_argument("--sibling-projects", default="",
                    help="comma list of other projects whose timelines are merged by NAME. "
                         "2026-11-17g flaw: Resolve's current project is host-global, so concurrent "
                         "agents created some correctly-named timelines in the OTHER arm's project; "
                         "grading follows the name and records the placement.")
    args = ap.parse_args()

    gt = json.load(open(args.gt))
    claims = json.load(open(args.claims))
    wdir = pathlib.Path(args.wave)
    wr = json.load(open(args.wave_results or (wdir / "wave_results.json")))
    tl_base = wr["tl_base"]

    c = Client()
    verdicts, problems = {}, []
    def rec(task, ok, notes):
        (verdicts.setdefault(task, {}).setdefault("pass" if ok else "fail", []).append(task[-2:]))
        if notes:
            verdicts[task].setdefault("notes", []).append(f"{task[-2:]}: {notes}")

    try:
        cur = {"proj": None}
        def load(proj):
            c.tool("project_manager", "load", {"name": proj})
            cur["proj"] = proj
        def refresh():
            return {t["name"]: t["id"] for t in c.tool("timeline", "list").get("timelines", [])}
        load(tl_base)
        tids = refresh()
        project_of = {n: tl_base for n in tids}
        cross = {}
        for sp in [p for p in args.sibling_projects.split(",") if p]:
            load(sp)
            for n, tid in refresh().items():
                project_of.setdefault(n, sp)
                if n.startswith(tl_base) and sp != tl_base:
                    cross[n] = sp          # arm-named timeline sitting in a sibling project
        load(tl_base)
        def tid_of(name):
            """Ensure the owning project is loaded, then return the timeline id."""
            proj = project_of.get(name, tl_base)
            if proj != cur["proj"]:
                load(proj)
            return tids.setdefault(name, refresh().get(name))
        tnames = [n for n in project_of if n.startswith(tl_base)]

        # ---- T1 (read-only, values from reports; mutation ruled out by absent archive) ----
        t1_siblings = [n for n in tnames if n.endswith("_T1_archived_v01")]
        expected_t1 = {"duration_frames": gt["T1"]["duration_frames"], "video_items": gt["T1"]["video_items"],
                       "video_tracks": gt["T1"]["video_tracks"], "audio_tracks": gt["T1"]["audio_tracks"]}
        # reported values are operator-extracted per trial into claims (T1r<k>: {"reported": {...}})
        # — fail closed when the extraction is missing, never assume report == ground truth
        for k in ("r1", "r2", "r3"):
            rep = claims.get(f"T1{k}", {}).get("reported")
            if rep is None:
                ok, why = False, [f"no operator-extracted reported values for T1{k} in claims"]
            else:
                ok, why = gs.grade_t1(expected_t1, rep, t1_siblings)
            rec(f"T1{k}", ok, "; ".join(why))

        # ---- T2 ----
        for k in ("r1", "r2", "r3"):
            name = f"{tl_base}_T2{k}"
            tid_of(name)   # ensure owning project loaded before name-scoped calls
            mk = c.tool("timeline_markers", "get_all", {"timeline_name": name})
            items = c.tool("timeline", "get_items", {"track_type": "video", "track_index": 1,
                                                     "timeline_id": tid_of(name)})
            durs = [it["end"] - it["start"] for it in items.get("items", [])]
            ok, why = gs.grade_t2({"frame": 60, "color": "Green", "name": "bench-hit"},
                                  mk.get("markers", mk), durs, [221, 221])
            rec(f"T2{k}", ok, "; ".join(why))

        # ---- T3 ----
        for k in ("r1", "r2", "r3"):
            name = f"{tl_base}_T3{k}"
            st = c.tool("timeline", "probe_timeline_structure", {"timeline_id": tid_of(name)})
            go = c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid_of(name)})
            vids = flat(st, "video")
            ok, why = gs.grade_t3(vids, [221, 101, 221], go.get("gaps", []), go.get("overlaps", []), 543)
            rec(f"T3{k}", ok, "; ".join(why))

        # ---- T7 ----
        # render queue is PER PROJECT; collect from both so a stranded job anywhere is caught
        queued = []
        for proj in [tl_base] + [p for p in args.sibling_projects.split(",") if p]:
            load(proj)
            queued += c.tool("render", "list_jobs").get("jobs", [])
        load(tl_base)
        for k in ("r1", "r2", "r3"):
            files = glob.glob(os.path.join(args.render_root, f"T7{k}", "*.mov"))
            files += glob.glob(os.path.join(args.render_root, f"T7{k}", "*.mp4"))
            fp = ffprobe_render(files[0] if files else None)
            if fp.get("duration"):
                fp["duration_ratio"] = fp["duration"] / (121 / 29.97)
            ok, why = gs.grade_t7(fp, {"packets": 121, "codec": "h264", "width": 3840, "height": 1520},
                                  queued, f"{tl_base}_T7{k}")
            rec(f"T7{k}", ok, "; ".join(why))

        # ---- T8 ----
        for k in ("r1", "r2", "r3"):
            if args.unmeasurable and "T8" in args.unmeasurable:
                verdicts.setdefault("T8"+k, {})["unmeasurable"] = True
                verdicts["T8"+k]["notes"] = ["post-hoc read-back impossible: Fusion comps attached in-wave did not survive the project close/load churn of the wave (confirmed 2026-11-17g: comp_count reads 0 on every T8 timeline after grading loads projects, even with set_current); in-wave read-backs (events.json) reported comp count 1 / 'Composition 1' for ALL six trials in both arms"]
                continue
            name = f"{tl_base}_T8{k}"
            cc = c.tool("timeline_item_fusion", "get_comp_count",
                        {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid_of(name)})
            cn = c.tool("timeline_item_fusion", "get_comp_names",
                        {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid_of(name)})
            ok, why = gs.grade_t8(cc.get("comp_count", cc.get("count")), cn.get("comp_names", cn.get("names")))
            rec(f"T8{k}", ok, "; ".join(why))

        # ---- F1: slip with replace_source_range; loss matrix + disclosure ----
        f1pre_v = gt["f1"]["pre_state"]["video_0"]
        for k in ("r1", "r2", "r3"):
            name = f"{tl_base}_f1{k.replace('r','s')}"
            tid = tid_of(name)
            st = c.tool("timeline", "probe_timeline_structure", {"timeline_id": tid})
            go = c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid})
            v = flat(st, "video")
            a0 = flat(st, "audio")
            sp = c.tool("timeline_item", "get_speed", {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            rt = c.tool("timeline_item", "get_retime", {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            tf = c.tool("timeline_item", "get_transform", {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            cr = c.tool("timeline_item", "get_crop", {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            lk = c.tool("timeline_item", "get_linked_items", {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            ng = c.tool("timeline_item_color", "probe_node_graph", {"source": "item", "track_type": "video",
                                                                    "track_index": 1, "item_index": 0, "timeline_id": tid})
            cc = c.tool("timeline_item_fusion", "get_comp_count", {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": tid})
            v0 = v[0]
            def flat_payload(p, inner):
                # the server nests the payload under its own key when non-default
                if isinstance(p, dict) and inner in p and isinstance(p[inner], dict):
                    return {**p, **p[inner]}
                return p or {}
            sp = flat_payload(sp, "speed"); rt = flat_payload(rt, "retime")
            tf = flat_payload(tf, "transform"); cr = flat_payload(cr, "crop")
            grade_tools = []
            for node in ng.get("nodes", []):
                grade_tools += [t if isinstance(t, str) else t.get("name") for t in node.get("tools", [])]
            post = {"source_start": rnd(v0.get("source_start")), "source_end": rnd(v0.get("source_end")),
                    "record_start": v0.get("start"), "record_end": v0.get("end"),
                    "duration": (v0.get("end") or 0) - (v0.get("start") or 0),
                    "speed_percentage": sp.get("Percentage") if "Percentage" in sp else (sp.get("speed") or {}).get("Percentage"),
                    "retime_process": rt.get("process"),
                    "retime_motion_estimation": rt.get("motion_estimation"),
                    "comp_count": cc.get("comp_count", cc.get("count")),
                    "grade_tools": sorted(grade_tools),
                    "zoom_x": rnd(tf.get("ZoomX")), "zoom_y": rnd(tf.get("ZoomY")),
                    "crop_left": rnd(cr.get("CropLeft")), "crop_right": rnd(cr.get("CropRight")),
                    "linked_item_count": len(lk.get("items", [])),
                    "audio_in_step": bool(a0) and a0[0].get("source_start") == v0.get("source_start")}
            pre = {"source_start": f1pre_v["source_start"], "source_end": f1pre_v["source_end_exclusive"],
                   "record_start": f1pre_v["record"][0], "record_end": f1pre_v["record"][1],
                   "duration": f1pre_v["duration"], "speed_percentage": f1pre_v["speed"]["Percentage"],
                   "retime_process": f1pre_v["retime"]["process"],
                   "retime_motion_estimation": f1pre_v["retime"]["motion_estimation"],
                   "comp_count": 0, "grade_tools": sorted(f1pre_v.get("grade_tools") or f1pre_v.get("grade_tools_node1") or []),
                   "zoom_x": rnd(f1pre_v["transform"]["ZoomX"]), "zoom_y": rnd(f1pre_v["transform"]["ZoomY"]),
                   "crop_left": rnd(f1pre_v["crop"]["CropLeft"]), "crop_right": 0,
                   "linked_item_count": f1pre_v["linked_item_count"], "audio_in_step": True}
            spec = {"source_start": 6000, "source_end": 6221, "record_start": 108000, "record_end": 108221,
                    "duration": 221, "source_tolerance": 1,
                    "expect_lost": ["speed", "retime", "audio_in_step"]}
            ok, why = gs.grade_f1(pre, post, claims.get(f"F1{k}", {}), spec)
            verdicts.setdefault("F1"+k, {})["post"] = {kk: post[kk] for kk in
                ("source_start", "source_end", "speed_percentage", "retime_process", "comp_count",
                 "grade_tools", "zoom_x", "crop_left", "linked_item_count", "audio_in_step")}
            rec(f"F1{k}", ok, "; ".join(why))

        # ---- F2: ripple insert after transition ----
        f2pre = gt["f2"]["pre_state"]
        f2c = f2pre["video_items_including_transition"][3]
        for k in ("r1", "r2", "r3"):
            name = f"{tl_base}_f2{k}"
            tid = tid_of(name)
            st = c.tool("timeline", "probe_timeline_structure", {"timeline_id": tid})
            go = c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid})
            v = flat(st, "video")
            aud = flat(st, "audio")
            clips = [i for i in v if not gs._is_transition(i)]
            shifted_idx = v.index(clips[-1])
            ng = c.tool("timeline_item_color", "probe_node_graph", {"source": "item", "track_type": "video",
                                                                    "track_index": 1, "item_index": shifted_idx, "timeline_id": tid})
            lk = c.tool("timeline_item", "get_linked_items", {"track_type": "video", "track_index": 1,
                                                              "item_index": shifted_idx, "timeline_id": tid})
            grade_tools = []
            for node in ng.get("nodes", []):
                grade_tools += [t if isinstance(t, str) else t.get("name") for t in node.get("tools", [])]
            pre = {"grade_tools": sorted(f2c.get("grade_tools", [])), "linked_item_count": f2c.get("linked_item_count", 1),
                   "transition_present": True}
            post = {"grade_tools": sorted(grade_tools), "linked_item_count": len(lk.get("items", [])),
                    "transition_present": any(gs._is_transition(i) for i in v),
                    "audio_item_count": len(aud)}
            # NOTE history: 17g-era fixture deviation armed the CDL onto the transition (both arms),
            # making the grade axis unmeasurable in THAT wave. Emit the note only when the sealed
            # pre-state actually shows the tracked clip ungraded (was unconditional - 23c fix).
            spec = {"clip_durations": [221, 221, 101, 221], "audio_count": 4,
                    "gap_count": 0, "overlap_count": 2, "expect_lost": ["link"],
                    "tracked": ["transition", "link"]}
            if not pre["grade_tools"]:
                verdicts.setdefault("F2"+k, {}).setdefault("notes", []).append(
                    "grade dimension unmeasurable (operator arming bug; sealed pre-state shows third clip ungraded pre-op)")
            ok, why = gs.grade_f2(v, go.get("gaps", []), go.get("overlaps", []), pre, post,
                                  claims.get(f"F2{k}", {}), spec)
            verdicts.setdefault("F2"+k, {})["post"] = post
            rec(f"F2{k}", ok, "; ".join(why))
    finally:
        c.close()

    total_pass = sum(len(v.get("pass", [])) for v in verdicts.values())
    total_fail = sum(len(v.get("fail", [])) for v in verdicts.values())
    out = {"wave": wdir.name,
           "graded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "sealed_gt_sha256": args.sealed_gt_sha256,
           "cross_project_placements": cross,
           "grading_basis": "post-wave read-backs via community MCP stdio client; predicates imported from grader_selftest.py (58/58 self-test green before this run)",
           "claims_basis": "operator-extracted per-trial claim maps from the archived reports (full text in sessions/<trial>/events.json)",
           "verdicts": verdicts,
           "outcome": f"{total_pass}/{total_pass+total_fail}"}
    pathlib.Path(args.out).write_text(json.dumps(out, indent=1))
    for task in sorted(verdicts):
        v = verdicts[task]
        print(task, "PASS" if "pass" in v else "FAIL", v.get("notes", ""))
    print("OUTCOME:", out["outcome"], "->", args.out)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
