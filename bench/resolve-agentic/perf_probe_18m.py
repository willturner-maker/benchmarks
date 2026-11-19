#!/usr/bin/env python3
"""Single-tenant Resolve MCP perf stage — 2026-11-18m row (first on MCP 5.3.4).

Reproduces the sealed 2026-11-13-wave/perf/ops.json method:
  op medians x5   — prepare_render_job, verify_output, timeline set_current,
                    probe_timeline_structure (video-only 2-item + linked 4-item)
  render probe    — 121 f, mov/H.264 + pcm, 3840x1520, class A media: first render
                    = cold, three more = warm (median recorded)

Scratch project _mcp_PERF-<tag> is built AND torn down here. Media path never
enters any artifact (Client scrubs). Geometry follows fixture.json (class A).

Run solo — no other engine traffic while the render stage runs.
"""
import argparse, json, os, pathlib, statistics, subprocess, sys, time
import platform, datetime as dt

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_fixture_effort_ab import Client, rows, MEDIA_PATH, MEDIA_NAME, TL_W, TL_H, FPS, D, START  # noqa: E402

PROB_SRC, PROB_F = D["probe_source_start"], D["probe_frames"]
BASE_SRC, SEG = D["base_source_start"], 221


def timed(fn, *a, **k):
    t0 = time.time()
    r = fn(*a, **k)
    return r, round((time.time() - t0) * 1000, 1)


def med(vals):
    return round(statistics.median(vals), 1)


def host_sample():
    up = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
    try:
        top = subprocess.run(["top", "-l", "1", "-n", "0"], capture_output=True,
                             text=True, timeout=15).stdout
        idle = next((ln.split(",")[-1].strip().replace(" idle", "").strip()
                     for ln in top.splitlines() if "% idle" in ln), None)
    except Exception:
        idle = None
    return f"{up} | idle {idle}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="2026-11-18m")
    ap.add_argument("--render-root",
                    default="/Volumes/YourVolume/resolve-audio-analysis/agbench_YYYY-MM-DDm/perf",
                    help="pass the real volume path at invocation; the default is a placeholder")
    a = ap.parse_args()
    proj = f"_mcp_PERF-{a.tag}"
    out = HERE / "results" / f"perf-{a.tag}"
    out.mkdir(parents=True, exist_ok=True)
    os.makedirs(a.render_root, exist_ok=True)

    if not os.path.exists(MEDIA_PATH):
        print("!! media volume unmounted — aborting"); return 1

    c = Client(out / "perf-calls.jsonl")
    # Resolve background tasks were the pinned cause of bimodal op spikes in earlier stages
    c.tool("resolve_control", "disable_background_tasks_for_current_session")
    res = {"wave": a.tag, "single_tenant": True, "operator_only": True,
           "host_sample_start": host_sample(),
           "ts": dt.datetime.now().isoformat(timespec="seconds")}

    # ---- Resolve/MCP versions from the live server ----
    ver = c.tool("resolve_control", "get_version")
    res["resolve_version"] = ver.get("version") or ver

    # ---- fresh scratch project, timeline settings pinned (strings, 5.3.x quirk) ----
    c.tool("project_manager", "close")
    c.tool("project_manager", "delete", {"name": proj})
    c.tool("project_manager", "create", {"name": proj})
    c.tool("project_manager", "load", {"name": proj})
    for k, v in (("timelineResolutionWidth", str(TL_W)),
                 ("timelineResolutionHeight", str(TL_H)),
                 ("timelineFrameRate", str(FPS))):
        c.tool("project_settings", "set_setting", {"name": k, "value": v})
        rb = c.tool("project_settings", "get_setting", {"name": k}).get("settings")
        if str(rb) != str(v):
            print(f"!! {k} did not stick ({rb!r}); aborting"); return 1
    c.tool("media_pool", "safe_import_media", {"paths": [MEDIA_PATH]})

    pool = c.tool("folder", "get_clips")
    clips = pool.get("clips") or pool.get("items") or []
    clip = next((x for x in clips if (x.get("name") or "").lower() == MEDIA_NAME.lower()), None)
    clip_id = (clip or {}).get("id") or (clip or {}).get("media_pool_item_id")
    if not clip_id:
        print("!! clip not in pool; aborting"); return 1

    def pin(name):
        c.tool("timeline", "set_current", {"name": name})
        c.tool("timeline", "set_start_timecode", {"timecode": "01:00:00:00"})

    def link_pairs(name):
        vi = c.tool("timeline", "get_items", {"track_type": "video", "track_index": 1,
                                              "timeline_name": name}).get("items", [])
        ai = c.tool("timeline", "get_items", {"track_type": "audio", "track_index": 1,
                                              "timeline_name": name}).get("items", [])
        n = 0
        for v in vi:
            mate = next((x for x in ai if x.get("start") == v.get("start")), None)
            if mate:
                c.tool("timeline", "set_clips_linked",
                       {"clip_ids": [v.get("id") or v.get("item_id"),
                                     mate.get("id") or mate.get("item_id")],
                        "linked": True, "timeline_name": name})
                n += 1
        return n

    def shell(name):
        ids = [t["id"] for t in c.tool("timeline", "list").get("timelines", [])
               if t["name"] == name]
        if ids:
            c.confirm("media_pool", "delete_timelines", {"timeline_ids": ids})
        c.tool("media_pool", "create_timeline", {"name": name})
        pin(name)

    # geometry: ops timelines (2-item video-only; 4-item linked) + 121-f render probe
    shell(f"{proj}_ops_v")
    c.tool("media_pool", "append_to_timeline",
           {"timeline_name": f"{proj}_ops_v",
            "clip_infos": rows(clip_id, BASE_SRC, SEG, START)
                        + [dict({"media_pool_item_id": clip_id, "start_frame": BASE_SRC + SEG,
                                 "end_frame": BASE_SRC + 2 * SEG, "record_frame": START + SEG,
                                 "record_frame_mode": "absolute", "track_index": 1}, media_type=1)]})
    shell(f"{proj}_ops_a")
    c.tool("media_pool", "append_to_timeline",
           {"timeline_name": f"{proj}_ops_a",
            "clip_infos": rows(clip_id, BASE_SRC, SEG, START)
                        + rows(clip_id, BASE_SRC + SEG, SEG, START + SEG)})
    if link_pairs(f"{proj}_ops_a") != 2:
        print("!! ops_a link failed; aborting"); return 1
    shell(f"{proj}_render")
    c.tool("media_pool", "append_to_timeline",
           {"timeline_name": f"{proj}_render",
            "clip_infos": rows(clip_id, PROB_SRC, PROB_F, START)})
    if link_pairs(f"{proj}_render") != 1:
        print("!! render timeline link failed; aborting"); return 1

    # ---- op medians (x5) ----
    setcur = []
    for i in range(5):
        other = f"{proj}_ops_v" if i % 2 else f"{proj}_ops_a"
        _, ms = timed(c.tool, "timeline", "set_current", {"name": other})
        setcur.append(ms)

    probe_v, probe_a = [], []
    for i in range(5):
        _, ms = timed(c.tool, "timeline", "probe_timeline_structure",
                      {"timeline_name": f"{proj}_ops_v", "include_clip_properties": True})
        probe_v.append(ms)
        _, ms = timed(c.tool, "timeline", "probe_timeline_structure",
                      {"timeline_name": f"{proj}_ops_a", "include_clip_properties": True})
        probe_a.append(ms)

    # confirm probe geometry before timing renders
    geo = c.tool("timeline", "probe_timeline_structure",
                 {"timeline_name": f"{proj}_render", "include_clip_properties": False})
    items = [it for tr in geo.get("tracks", {}).get("video", {}).get("tracks", [])
             for it in tr.get("items", [])]
    if len(items) != 1:
        print(f"!! render tl geometry wrong: {len(items)} items; aborting"); return 1

    render_params = {"target_dir": a.render_root, "require_temp_target": False,
                     "format": "mov", "codec": "H264",
                     "settings": {"SelectAllFrames": True, "TargetDir": a.render_root,
                                  "CustomName": f"perf_{a.tag}",
                                  "ExportVideo": True, "ExportAudio": True,
                                  "FormatWidth": TL_W, "FormatHeight": TL_H}}
    c.tool("timeline", "set_current", {"name": f"{proj}_render"})
    prepares = []
    _, ms = timed(c.tool, "render", "prepare_render_job", render_params)
    prepares.append(ms)
    # four queued prepares total: this one renders below; queue-delete x4 timed
    for _ in range(4):
        _, ms = timed(c.tool, "render", "prepare_render_job", render_params)
        c.tool("render", "delete_all_jobs")
        prepares.append(ms)

    def render_once(job_id=None, keep=False):
        if not job_id:
            jobs = c.tool("render", "list_jobs").get("jobs", [])
            job_id = jobs[-1]["JobId"] if jobs else None
        if not job_id:
            pr = c.tool("render", "prepare_render_job", render_params)
            job_id = pr.get("job_id")
        t0 = time.time()
        c.tool("render", "start")
        status = {}
        while time.time() - t0 < 300:
            status = c.tool("render", "get_job_status", {"job_id": job_id})
            if str(status.get("JobStatus", "")).lower() in ("complete", "failed", "cancelled"):
                break
            time.sleep(0.1)
        wall = round((time.time() - t0) * 1000)
        # sealed metric for the published series is Resolve's own render-time report
        # (matches every historical row, e.g. 13i warm 1192); wall_ms additionally records
        # queue-in + MCP round-trip latency around it — disclosed as a 5.3.4 datapoint.
        internal = status.get("TimeTakenToRenderInMs")
        ok = str(status.get("JobStatus", "")).lower() == "complete"
        if not keep:
            c.tool("render", "delete_all_jobs")
        return job_id, wall, ok, internal

    # queue the first job (prepare timed above in the loop left queue empty; re-prepare)
    c.tool("render", "prepare_render_job", render_params)
    job_id, cold_wall, ok1, cold_internal = render_once()
    if not ok1:
        print("!! cold render did not complete; aborting"); return 1
    warms, walls = [], []
    vjob = None
    for i in range(3):
        c.tool("render", "prepare_render_job", render_params)
        jobs = c.tool("render", "list_jobs").get("jobs", [])
        job_id = jobs[-1]["JobId"]
        jid, w, ok, internal = render_once(job_id, keep=(i == 2))   # last warm job stays queued for verify
        if not ok:
            print("!! warm render failed"); break
        warms.append(internal)
        walls.append(w)
        vjob = jid
    verifies = []
    if vjob:
        for _ in range(5):
            _, ms = timed(c.tool, "render", "verify_output", {"job_id": vjob})
            verifies.append(ms)
        vf = c.tool("render", "verify_output", {"job_id": vjob})
    else:
        vf = {"error": "no completed warm job to verify"}
    c.tool("render", "delete_all_jobs")

    res.update({
        "prepare_render_job_ms": {"runs": prepares, "median": med(prepares)},
        "verify_output_ms": {"runs": verifies, "median": med(verifies)},
        "set_current_ms": {"runs": setcur, "median": med(setcur)},
        "probe_timeline_structure_ms": {
            "video_only_2item": probe_v, "both_4item": probe_a,
            "median_video_only": med(probe_v), "median_4item": med(probe_a)},
        "render_cold_ms": cold_internal, "render_cold_wall_ms": cold_wall,
        "render_warm_ms": med(warms), "warm_internal_runs": warms,
        "render_warm_wall_ms": med(walls), "warm_wall_runs": walls,
        "wall_overhead_note": ("wall_ms = queue-in + MCP round-trip around the internal render; "
                               "sealed series metric is the internal TimeTakenToRenderInMs"),
        "render_probe": (f"{PROB_F}f, {TL_W}x{TL_H}, mov/H.264 + pcm, class A "
                         f"({MEDIA_NAME} HEVC Main10), verified: "
                         f"{json.dumps(vf.get('verification', vf))[:200]}"),
        "host_sample_end": host_sample(),
    })
    (out / "ops.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1)[:1200])

    # teardown scratch project (never delete_timelines mid-thing: full project delete)
    c.tool("project_manager", "close")
    print("teardown:", c.tool("project_manager", "delete", {"name": proj}))
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
