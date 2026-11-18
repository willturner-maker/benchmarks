#!/usr/bin/env python3
"""Fixture builder for the 2026-11-17g effort A/B (two arms, identical fixtures).

Builds, THROUGH THE COMMUNITY Resolve MCP SERVER (stdio client, same pattern as
grade_f1f2_wave.py / probe_build_sweep.py), one scratch project per arm:

    _mcp_AGBench-2026-11-17gx   (xhigh arm)        _mcp_AGBench-2026-11-17gm  (medium arm)

each holding:  _base  _T1  _f1m (armed template)  _f1s1..3  _f2m (template)  _f2r1..3

Recipe follows RUNBOOK §1 plus the deviations recorded in ground_truth-2026-11-16f.json:
append rows are END-EXCLUSIVE (end = start + frames); media_type 1+2 rows do NOT auto-link
(set_clips_linked per pair); timeline start frame 108000 ("01:00:00:00"); DF reads sit 1 low.

Stages (--stage): project | base | f1 | f2 | duplicate | gt  (run in order; each verifiable).
Ground truth is recorded from probe_timeline_structure read-backs, never from intent.
Every MCP call goes to a build-log JSONL; the media clip name/path is SCRUBBED from the log
(the log lands in the published results tree; media stays "class A").

F1 arming (video item 0): speed 80 % + pitch correction, optical-flow retime (motion estimation 2),
CDL grade, ZoomX/ZoomY 1.2, CropLeft 120, linked audio. F2: three 221-f linked pairs, 24-f Cross
Dissolve across the first cut, CDL grades on items 2 and 3.
"""
import argparse, json, os, pathlib, subprocess, time

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE.parent                                    # bench/
# fixture.json is UNTRACKED by design (it names the real media); the committed template is
# fixture.example.json. Fail with directions instead of a bare FileNotFoundError — this also
# fires when the module is only imported for Client (the 17h driver does), so the message
# must explain why an import failed.
FIX_PATH = HERE / "fixture.json"
if not FIX_PATH.exists():
    raise SystemExit("fixture.json missing (untracked by design — it names the real media).\n"
                     "  Build it: python3 check_media.py /path/to/clip.mov --out fixture.json\n"
                     "  Template: fixture.example.json (class A = timings comparable, B = outcomes only)")
FIX = json.load(open(FIX_PATH))
MEDIA_PATH, MEDIA_NAME = FIX["media_path"], FIX["clip_name"]
D = FIX["derived"]
TL_W, TL_H, FPS = FIX["timeline"]["width"], FIX["timeline"]["height"], FIX["timeline"]["fps"]
START = 108000                                         # 01:00:00:00, as every prior wave
BASE_SRC, SEG = D["base_source_start"], 221
LOGDIR = BENCH / "effort-ab-2026-11-17"
PROTO = "2024-11-05"
LIVE = pathlib.Path.home() / "Library/Application Support/davinci-resolve-mcp"


class Client:
    def __init__(self, logpath):
        cfg = json.load(open(pathlib.Path.home() / ".config" / "opencode" / "opencode.json"))
        srv = cfg["mcp"]["servers"]["davinci-resolve"]
        env = dict(os.environ); env.update(srv.get("environment") or srv.get("env") or {})
        self.log = open(logpath, "a")
        cmd = srv["command"] if isinstance(srv.get("command"), list) else [srv["command"]]
        self.p = subprocess.Popen(cmd, cwd=str(LIVE), env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.nid = 0
        self._rpc("initialize", {"protocolVersion": PROTO, "capabilities": {},
                                 "clientInfo": {"name": "effort-ab-fixture-builder", "version": "1"}})
        self._notify("notifications/initialized", {})

    def _scrub(self, s):
        return str(s).replace(MEDIA_PATH, "<media-path>").replace(MEDIA_NAME, "<clip>")

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n"); self.p.stdin.flush()

    def _notify(self, m, prm):
        self._send({"jsonrpc": "2.0", "method": m, "params": prm})

    def _rpc(self, method, prm):
        self.nid += 1; rid = self.nid
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": prm})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"server died during {method}")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == rid:
                return msg

    def tool(self, name, action, params=None):
        t0 = time.time()
        r = self._rpc("tools/call", {"name": name,
                                     "arguments": {"action": action, "params": params or {}}})
        rec = {"ts": time.strftime("%H:%M:%S"), "ms": int(t0 * 1000), "tool": name, "action": action,
               "params": json.loads(self._scrub(json.dumps(params or {}))),
               "wall_ms": round((time.time() - t0) * 1000)}
        if "error" in r:
            rec["rpc_error"] = self._scrub(json.dumps(r["error"]))[:400]
            self.log.write(json.dumps(rec) + "\n"); self.log.flush()
            return {}
        txt = "".join(c.get("text", "") for c in r.get("result", {}).get("content", [])
                      if c.get("type") == "text")
        try:
            parsed = json.loads(txt)
        except Exception:
            parsed = None
            rec["result_text"] = self._scrub(txt)[:800]
        if parsed is not None:
            # RETURNED dict is raw so callers can match real names; the LOGGED copy is scrubbed
            rec["result"] = json.loads(self._scrub(json.dumps(parsed)))
        rec["is_error"] = bool(r.get("result", {}).get("isError"))
        self.log.write(json.dumps(rec) + "\n"); self.log.flush()
        return parsed if parsed is not None else {}

    def confirm(self, name, action, params=None):
        """Destructive MCP actions issue a one-shot token; re-call with it. Both calls are logged."""
        r = self.tool(name, action, params)
        tok = (r or {}).get("confirm_token")
        if not tok:
            return r
        return self.tool(name, action, {**(params or {}), "confirm_token": tok})

    def close(self):
        try:
            self.p.stdin.close(); self.p.terminate()
        except Exception:
            pass
        self.log.close()


def rows(clip_id, src_start, frames, record):
    """One END-EXCLUSIVE video row + audio row pair over the same source/record range."""
    one = {"media_pool_item_id": clip_id, "start_frame": src_start, "end_frame": src_start + frames,
           "record_frame": record, "record_frame_mode": "absolute", "track_index": 1}
    return [dict(one, media_type=1), dict(one, media_type=2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--stage", default="all", help="settings|project|base|f1|f2|duplicate|gt|all")
    ap.add_argument("--reps", type=int, default=3,
                    help="number of F-trial copies per template (_f1s1..N / _f2r1..N); "
                         "Tier 3 two-arm waves pass 6. Default 3 = every published wave.")
    ap.add_argument("--tl-base", default=None, help="defaults to --project")
    ap.add_argument("--fresh", action="store_true", help="delete the project first if present")
    ap.add_argument("--logdir", default=str(LOGDIR),
                    help="build-log dir (17h+ waves: results/<wave>/, ignored by results/.gitignore)")
    a = ap.parse_args()
    TLB = a.tl_base or a.project
    want = lambda s: a.stage in ("all", s)
    if not os.path.exists(MEDIA_PATH):   # unmounted volume must fail here, not mid-arm
        print("!! fixture media path unreachable (volume unmounted?) — see fixture.json; aborting")
        return 1
    logdir = pathlib.Path(a.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    c = Client(logdir / f"fixture-build-{a.project}.jsonl")

    if want("settings"):
        c.tool("project_manager", "load", {"name": a.project})
        for k, v in (("timelineResolutionWidth", TL_W), ("timelineResolutionHeight", TL_H),
                     ("timelineFrameRate", str(FPS))):
            print("set", k, "->", str(c.tool("project_settings", "set_setting",
                                             {"name": k, "value": v}))[:160])

    if want("rebuild"):
        # Resolve quirk: timeline geometry is fixed at creation — the first pass created four
        # 1920x1080@24 shells before settings could apply. Delete shells, set settings, recreate.
        c.tool("project_manager", "load", {"name": a.project})
        tls = c.tool("timeline", "list")
        doomed = [t["id"] for t in tls.get("timelines", []) if t["name"].startswith(TLB)]
        print("delete shells:", str(c.confirm("media_pool", "delete_timelines",
                                           {"timeline_ids": doomed}))[:150])
        for k, v in (("timelineResolutionWidth", str(TL_W)), ("timelineResolutionHeight", str(TL_H)),
                     ("timelineFrameRate", str(FPS))):
            c.tool("project_settings", "set_setting", {"name": k, "value": v})
            print("readback", k, "->", str(c.tool("project_settings", "get_setting",
                                                  {"name": k}))[:110])
        for suffix in ("_base", "_T1", "_f1m", "_f2m"):
            print("tl", suffix, "->", str(c.tool("media_pool", "create_timeline",
                                                 {"name": TLB + suffix}))[:110])

    if want("project"):
        if a.fresh:
            c.tool("project_manager", "close")
            print("delete:", str(c.tool("project_manager", "delete", {"name": a.project}))[:120])
        print("create:", str(c.tool("project_manager", "create", {"name": a.project}))[:200])
        print("load:  ", str(c.tool("project_manager", "load", {"name": a.project}))[:160])
        # MCP 5.3.1 quirk (deviation from RUNBOOK "as ints"): resolution values must be STRINGS,
        # ints are refused with a bare success:false. Frame rate was always a string.
        for k, v in (("timelineResolutionWidth", str(TL_W)), ("timelineResolutionHeight", str(TL_H)),
                     ("timelineFrameRate", str(FPS))):
            c.tool("project_settings", "set_setting", {"name": k, "value": v})
            rb = c.tool("project_settings", "get_setting", {"name": k}).get("settings")
            print("set", k, "read back:", rb)
            if str(rb) != str(v):
                print(f"  !! setting {k} did not stick ({rb!r} != {v!r}) — aborting")
                c.close(); return 1
        imp = c.tool("media_pool", "safe_import_media", {"paths": [MEDIA_PATH]})
        print("import:", str(imp)[:180].replace(MEDIA_PATH, "<media-path>").replace(MEDIA_NAME, "<clip>"))
        for suffix in ("_base", "_T1", "_f1m", "_f2m"):
            print("tl", suffix, "->", str(c.tool("media_pool", "create_timeline",
                                                 {"name": TLB + suffix}))[:120])

    pool = c.tool("folder", "get_clips")
    clips = pool.get("clips") or pool.get("items") or []
    clip = next((x for x in clips if (x.get("name") or "").lower() == MEDIA_NAME.lower()), None)
    clip_id = (clip or {}).get("id") or (clip or {}).get("media_pool_item_id")
    print("clip id:", clip_id, "| pool:", len(clips))
    if not clip_id:
        print("!! no clip in pool — run --stage project first"); c.close(); return 1

    def pin(name):
        c.tool("timeline", "set_current", {"name": name})
        c.tool("timeline", "set_start_timecode", {"timecode": "01:00:00:00"})

    def ensure_shell(name):
        """Delete-and-recreate a shell so a rerun of any stage starts clean (the first f1 pass
        left a 177-f item0 behind when set_speed failed on option keys)."""
        ids = [t["id"] for t in c.tool("timeline", "list").get("timelines", [])
               if t["name"] == name]
        if ids:
            c.confirm("media_pool", "delete_timelines", {"timeline_ids": ids})
        return c.tool("media_pool", "create_timeline", {"name": name})

    def link_pairs(name):
        """media_type 1+2 rows do NOT auto-link on 5.3.0 (16f deviation): pair video and audio
        items by record start and link each pair explicitly."""
        vi = c.tool("timeline", "get_items", {"track_type": "video", "track_index": 1,
                                              "timeline_name": name}).get("items", [])
        ai = c.tool("timeline", "get_items", {"track_type": "audio", "track_index": 1,
                                              "timeline_name": name}).get("items", [])
        out = []
        for v in vi:
            mate = next((x for x in ai if x.get("start") == v.get("start")), None)
            if not mate:
                out.append({"unlinked_video": v.get("id") or v.get("item_id")}); continue
            ids = [v.get("id") or v.get("item_id"), mate.get("id") or mate.get("item_id")]
            out.append(c.tool("timeline", "set_clips_linked",
                              {"clip_ids": ids, "linked": True, "timeline_name": name}))
        return out

    if want("base"):
        for suffix in ("_base", "_T1"):
            name = TLB + suffix
            ensure_shell(name); pin(name)
            r = c.tool("media_pool", "append_to_timeline",
                       {"timeline_name": name,
                        "clip_infos": rows(clip_id, BASE_SRC, SEG, START)
                                    + rows(clip_id, BASE_SRC + SEG, SEG, START + SEG)})
            print(f"append {suffix}:", str(r)[:200])
            print(f"link {suffix}:", str(link_pairs(name))[:200])

    if want("f1"):
        f1 = TLB + "_f1m"; ensure_shell(f1); pin(f1)
        # 16f pre_state geometry: SOURCE 177 f, RECORD 221 f. Resolve's SetSpeed keeps the RECORD
        # length and re-cuts the source (measured: 177-source append + 80 % -> source 142, record
        # 177 — wrong). So append 221 source frames and let the 80 % speed cut it to 177.
        print("f1 item0:", str(c.tool("media_pool", "append_to_timeline",
              {"timeline_name": f1, "clip_infos": rows(clip_id, BASE_SRC, SEG, START)}))[:200])
        ti = {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_name": f1}
        print("set_speed:  ", str(c.tool("timeline_item", "set_speed",
              {**ti, "options": {"Percentage": 80.0, "PitchCorrection": True,
                                 "RippleTimeline": False}}))[:300])
        print("get_speed:  ", str(c.tool("timeline_item", "get_speed", ti))[:220])
        print("set_retime: ", str(c.tool("timeline_item", "set_retime",
              {**ti, "process": "optical_flow", "motion_estimation": 2}))[:200])
        print("safe_set_cdl:", str(c.tool("timeline_item_color", "safe_set_cdl", {**ti, "cdl": {
              "NodeIndex": 1, "Slope": [1.1, 1.05, 0.95], "Offset": [0.01, 0.0, -0.01],
              "Power": [1.0, 1.0, 1.0], "Saturation": 1.3}}))[:400])
        print("set_transform:", str(c.tool("timeline_item", "set_transform",
              {**ti, "ZoomX": 1.2, "ZoomY": 1.2}))[:200])
        print("set_crop:     ", str(c.tool("timeline_item", "set_crop",
              {**ti, "CropLeft": 120.0}))[:200])
        d = c.tool("timeline", "get_items", {"track_type": "video", "track_index": 1,
                                             "timeline_name": f1})
        items = d.get("items", [])
        print("f1 video items now:", len(items))
        if len(items) < 2:
            dur = (items or [{"end": START}])[0].get("end", START) - START
            print("f1 item1:", str(c.tool("media_pool", "append_to_timeline",
                  {"timeline_name": f1, "clip_infos": rows(clip_id, BASE_SRC + SEG, SEG, START + dur)}))[:200])
        print("f1 link:", str(link_pairs(f1))[:200])
        print("f1 probe:", str(c.tool("timeline", "probe_timeline_structure",
              {"timeline_name": f1, "include_clip_properties": True}))[:800])

    if want("f2"):
        f2 = TLB + "_f2m"; ensure_shell(f2); pin(f2)
        print("f2 append x3:", str(c.tool("media_pool", "append_to_timeline",
              {"timeline_name": f2, "clip_infos":
                  rows(clip_id, BASE_SRC, SEG, START)
                + rows(clip_id, BASE_SRC + SEG, SEG, START + SEG)
                + rows(clip_id, BASE_SRC + 2 * SEG, SEG, START + 2 * SEG)}))[:220])
        # VALIDITY 2026-11-17g flaw 4 FIX: CDLs go on the clean 3-item timeline FIRST.
        # With add_transition first, item indices shift and the "third clip" CDL landed on
        # the transition. Order now: grade -> transition -> verify. Arming verifies or aborts.
        for idx in (1, 2):
            print(f"f2 cdl item{idx}:", str(c.tool("timeline_item_color", "safe_set_cdl", {
                  "track_type": "video", "track_index": 1, "item_index": idx, "timeline_name": f2,
                  "cdl": {"NodeIndex": 1, "Slope": [1.05, 1.0, 1.0], "Offset": [0.02, 0.0, 0.0],
                          "Power": [1.0, 1.0, 1.0], "Saturation": 1.2}}))[:200])
        print("add_transition:", str(c.tool("timeline_item", "add_transition",
              {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_name": f2,
               "options": {"type": "Cross Dissolve", "category": "simple", "position": "end",
                           "alignment": "center", "duration": 24}}))[:400])
        print("f2 link:", str(link_pairs(f2))[:200])
        # Arming verification (fail loud, never arm a wrong pre-state again).
        # POST-transition row layout is the spec (docstring "grade on items 2 and 3"):
        # get_items rows -> [clip0, transition(24f), clip1, clip2]; graded rows are 2 and 3.
        # (First version of this check probed pre-shift indices and a probe key that does
        # not exist — ABORTed on a CORRECT arm; the 17h probe run caught it.)
        pv = c.tool("timeline", "probe_timeline_structure",
                    {"timeline_name": f2, "include_clip_properties": True})
        rows2 = c.tool("timeline", "get_items", {"track_type": "video", "track_index": 1,
                                                 "timeline_name": f2}).get("items", [])
        trans = [r for r in rows2 if (r.get("kind") or r.get("type") or "").lower() == "transition"
                 and (r.get("end", 0) - r.get("start", 0)) == 24]
        graded = []
        for pos in (2, 3):
            ng = c.tool("timeline_item_color", "probe_node_graph",
                        {"track_type": "video", "track_index": 1, "item_index": pos,
                         "timeline_name": f2, "max_nodes": 8})
            tools = [t for n in (ng.get("nodes") or []) for t in (n.get("tools") or [])]
            graded.append(bool(tools))
        ok = len(trans) == 1 and all(graded)
        print(f"f2 ARM CHECK: transitions={len(trans)} graded[2,3]={graded} -> {'OK' if ok else 'ABORT'}")
        if not ok:
            print("!! f2 pre-state does not match spec — fix arming before any wave uses this project")
            c.close(); return 1
        print("f2 probe:", str(pv)[:500])

    if want("duplicate"):
        for src, dsts in (("_f1m", [f"{TLB}_f1s{k}" for k in range(1, a.reps + 1)]),
                          ("_f2m", [f"{TLB}_f2r{k}" for k in range(1, a.reps + 1)])):
            for dst in dsts:
                pin(TLB + src)          # timeline.duplicate duplicates the CURRENT timeline
                print("dup", src, "->", dst, ":", str(c.tool("timeline", "duplicate",
                      {"name": dst}))[:160])

    if want("prestate"):
        c.tool("project_manager", "load", {"name": a.project})
        """probe carries geometry but NOT speed/retime/grade/transform/crop — those are separate
        read-backs (the 16f ground_truth pre_state was assembled the same way)."""
        out = {}
        for tl in [TLB + sfx for sfx in
                   ("_f1m",) + tuple(f"_f1s{k}" for k in range(1, a.reps + 1))
                   + ("_f2m",) + tuple(f"_f2r{k}" for k in range(1, a.reps + 1))]:
            ids = {t["name"]: t["id"] for t in c.tool("timeline", "list").get("timelines", [])}
            if tl not in ids:
                continue
            ti = {"timeline_name": tl}
            vi = c.tool("timeline", "get_items", {"track_type": "video", "track_index": 1, **ti})
            items = []
            for pos, it in enumerate(vi.get("items", [])):
                idx = it.get("item_index")
                idx = pos if idx is None else idx   # get_items order is the 0-based item_index
                base = {"item_index": idx, "start": it.get("start"), "end": it.get("end"),
                        "duration": (it.get("end") or 0) - (it.get("start") or 0),
                        "kind": it.get("kind") or it.get("type")}
                pti = {"track_type": "video", "track_index": 1, "item_index": idx, **ti}
                for act, key in (("get_speed", "speed"), ("get_retime", "retime"),
                                 ("get_transform", "transform"), ("get_crop", "crop"),
                                 ("get_linked_items", "linked_items")):
                    r = c.tool("timeline_item", act, pti)
                    base[key] = r.get(key if key != "linked_items" else "items", r if not r.get(key) else None)
                ng = c.tool("timeline_item_color", "probe_node_graph", {**pti, "max_nodes": 8})
                tools = [t for n in (ng.get("nodes") or []) for t in (n.get("tools") or [])]
                base["grade_tools"] = tools or None
                li = c.tool("timeline_item", "get_linked_items", pti)
                base["linked_item_count"] = len(li.get("items") or [])
                items.append(base)
            out[tl] = items
            print(tl, "->", [(i["item_index"], i["start"], i["end"], i.get("speed")) for i in items])
        pre = HERE / f"prestate-{a.project}.json"
        pre.write_text(json.dumps(out, indent=1, default=str))
        print("prestate ->", pre)

    if want("gt"):
        c.tool("project_manager", "load", {"name": a.project})
        tls = c.tool("timeline", "list")
        names = {t["name"]: t["id"] for t in tls.get("timelines", [])}
        out = {"_meta": {"project": a.project, "tl_base": TLB,
                         "captured": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "start_frame": START,
                         "geometry_convention": "END-EXCLUSIVE (probe semantics); DF reads 1 low",
                         "media": "class A (fixture.json)"}, "timelines": {}}
        # MCP auto-versioning can leave <tl>_archived_vNN copies in the project (seen in the
        # 17h probe run; the 17g sealed gt has exactly the 10 armed timelines). They are NOT
        # part of the pre-state: excluded from gt here, and the builder reports them so a
        # stray copy is visible at build time, not discovered by an agent mid-wave.
        archived = [n for n in names if "_archived_" in n]
        if archived:
            print(f"note: {len(archived)} MCP-archived version timelines present (excluded from gt): "
                  + ", ".join(n.replace(TLB, "") for n in archived))
        for n, tid in sorted(names.items()):
            if not n.startswith(TLB) or "_archived_" in n:
                continue
            pv = c.tool("timeline", "probe_timeline_structure",
                        {"timeline_id": tid, "include_clip_properties": True})
            go = c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid})
            out["timelines"][n] = {"id": tid, "probe": pv, "gaps_overlaps": go}
            print(n, "| probe keys:", str(pv)[:90])
        gt_path = HERE / f"ground_truth-{a.project}.json"
        gt_path.write_text(json.dumps(out, indent=1, default=str))
        print("gt ->", gt_path)

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
