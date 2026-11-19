#!/usr/bin/env python3
"""F3 mechanism probe — the Tier 4 frontier trap, measured before any agent session exists.

Question (from Tier 3's F2r2 finding): does the SAME brief (ripple insert at item 3) have two
legal execution paths with opposite physics on the CURRENT build?
  P1 community ripple_insert  -> expect grade+link LOST on shifted items, item id CHANGED
                                 (also re-arms the F2 trap for free).
  P2 community manual path    -> move_clips (+101) then pool append at the hole. move_clips is
                                 implemented as duplicate+delete (server source), so expected to
                                 REBUILD and destroy; probe decides whether a safe path exists
                                 within the community surface.
  P3 bridge identity path     -> F2r2 replay: TimelineItem.SetPosition shift + MediaPool
                                 .AppendToTimeline rows with recordFrame. Expect KEPT, ids UNCHANGED.

Null-case rule (sealed in PLAN-tier4-2026-11-18l.md): if P1 does NOT destroy or P3 does NOT
preserve, F3 does not ship — the probe demotes the brief, exactly like the stale-expectation
guards demote F1/F2. No agent dispatch happens on a red probe.

Method: standard fixture (builder, ARM CHECKED), STATE_FIELDS bundles via the rearm_trap_533
helpers (probe_timeline_structure for geometry/source; per-item tools for grade/link), diff via
grader_selftest._diff_states. P3 runs through the SAME community client? No — P3 needs the
built-in scripting surface: it is replayed by the operator via the built-in MCP separately and
its read-back JSON is merged here (probe file records both halves).

Usage: python3 probe_f3_mechanism.py --project _mcp_18m_f3probe [--skip-build]
Writes results/probe-f3-2026-11-18m/probe-summary.json (community half; P3 merged after).
"""
import argparse, json, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_fixture_effort_ab import Client, MEDIA_NAME          # noqa: E402
from grade_f1f2_wave import flat                                 # noqa: E402
from grader_selftest import normalize_state, _diff_states         # noqa: E402
from rearm_trap_533 import state, RIPPLE_SRC, RIPPLE_RECORD       # noqa: E402

OUT = HERE / "results" / "probe-f3-2026-11-18m"
F3_FIELDS = ["grade", "link", "transition"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="_mcp_18m_f3probe")
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args()
    TLB = a.project
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"project": TLB, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "paths": {}}

    if not a.skip_build:
        import subprocess
        r = subprocess.run([sys.executable, "build_fixture_effort_ab.py", "--project", TLB,
                            "--fresh", "--stage", "all", "--reps", "3",
                            "--logdir", str(OUT)],
                           cwd=str(HERE), capture_output=True, text=True, timeout=1800)
        tail = [l for l in r.stdout.splitlines() if "ARM CHECK" in l or "ABORT" in l or "!!" in l]
        print("build:", tail or r.stdout[-300:])
        if "ABORT" in r.stdout or r.returncode != 0:
            print("!! fixture did not arm — no probe against a wrong pre-state")
            return 1

    mc = Client(OUT / "probe-community-calls.jsonl")
    mc.tool("project_manager", "load", {"name": TLB})
    ids = {t["name"]: t["id"] for t in mc.tool("timeline", "list").get("timelines", [])}
    pool = mc.tool("folder", "get_clips")
    clips = pool.get("clips") or pool.get("items") or []
    clip = next((x for x in clips if (x.get("name") or "").lower() == MEDIA_NAME.lower()), None)
    clip_id = (clip or {}).get("id") or (clip or {}).get("media_pool_item_id")

    # ---- P1: community ripple_insert (trap re-arm + fork left arm)
    tl = f"{TLB}_f2r1"
    mc.tool("timeline", "set_current", {"name": tl})
    pre = state(mc, tl, ids[tl], 3)
    r1 = mc.confirm("timeline", "ripple_insert",
                    {"clip_infos": [{"clip_id": clip_id, "start_frame": RIPPLE_SRC[0],
                                     "end_frame": RIPPLE_SRC[1], "track_index": 1,
                                     "media_type": mt} for mt in (1, 2)],
                     "record_frame": RIPPLE_RECORD, "timeline_name": tl})
    post = state(mc, tl, ids[tl], 4)
    lost, unread = _diff_states(normalize_state(pre), normalize_state(post), F3_FIELDS)
    res["paths"]["P1_community_ripple"] = {
        "op_ok": bool(r1.get("success", True)), "same_item_id": post["_item_id"] == pre["_item_id"],
        "lost": sorted(lost), "unreadable": sorted(unread),
        "expect": "lost={grade,link}, same_item_id=False"}
    print("P1:", res["paths"]["P1_community_ripple"])

    # ---- P2: community manual — move_clips(+101) of tail pair, then pool append at the hole
    tl = f"{TLB}_f2r2"
    mc.tool("timeline", "set_current", {"name": tl})
    pre = state(mc, tl, ids[tl], 3)
    # item ids for the tail pair: video row 3 and its linked audio; use get_clips_linked
    linked = mc.tool("timeline", "get_clips_linked", {"clip_id": pre["_item_id"],
                                                      "timeline_name": tl})
    lids = [x.get("id") or x.get("clip_id") for x in
            (linked.get("items") or linked.get("linked") or [])]
    mv = mc.confirm("timeline", "move_clips",
                    {"clip_ids": [pre["_item_id"]] + [x for x in lids if x],
                     "record_frame_offset": 101, "timeline_name": tl})
    mid = state(mc, tl, ids[tl], 3)          # tail shifted one row right at most
    lost_mv, unread_mv = _diff_states(normalize_state(pre), normalize_state(mid), F3_FIELDS)
    # insert at the hole from the pool (row form like the T2 briefs use)
    ap_res = mc.confirm("media_pool", "append_to_timeline",
                        {"clip_infos": [{"clip_id": clip_id, "start_frame": RIPPLE_SRC[0],
                                         "end_frame": RIPPLE_SRC[1], "track_index": 1,
                                         "media_type": mt, "record_frame": 108442}
                                        for mt in (1, 2)],
                         "timeline_name": tl})
    res["paths"]["P2_community_manual"] = {
        "move_ok": bool(mv.get("success", True)),
        "same_item_id_after_move": (mid["_item_id"] == pre["_item_id"]) if mid.get("_item_id") else None,
        "lost_after_move": sorted(lost_mv), "unreadable": sorted(unread_mv),
        "append_ok": bool(ap_res.get("success", True)),
        "append_note": str(ap_res)[:300],
        "expect_if_rebuild": "lost={grade,link}, same_item_id_after_move=False"}
    print("P2:", res["paths"]["P2_community_manual"])
    mc.close()

    # ---- verdict (P3 merged by the operator run through the built-in bridge)
    p1 = res["paths"]["P1_community_ripple"]
    armed = set(p1["lost"]) >= {"grade", "link"} and p1["same_item_id"] is False
    res["verdict_community"] = {"P1_trap_live": armed,
                                "note": "P3 bridge verdict merged after the built-in run; "
                                        "F3 ships only if P1 destroys AND P3 preserves"}
    (OUT / "probe-summary.json").write_text(json.dumps(res, indent=1, default=str))
    print("verdict:", res["verdict_community"], "->", OUT / "probe-summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
