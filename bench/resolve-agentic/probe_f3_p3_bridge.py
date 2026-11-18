"""F3 probe P3 — bridge identity path, replayed from the F2r2 (tier3) transcript idiom.

Run via the BUILT-IN Resolve MCP (run_script), not the community client. Operates on
_mcp_18l_f3probe_f2r3: SetPosition shift of the tail video+audio pair (+101), then
MediaPool.AppendToTimeline rows with recordFrame at the hole. Expect: geometry 221/221/101/221,
shifted items' CDL byte-identical (grade KEPT), links KEPT, item unique ids UNCHANGED.

The result dict is the probe evidence: print it, then merge into
results/probe-f3-2026-11-18l/probe-summary.json under paths.P3_bridge.
"""
import hashlib

TL_NAME = "_mcp_18l_f3probe_f2r3"
INSERT_LEN = 101
SRC = (25181, 25282)          # end-exclusive, matches rearm_trap_533.RIPPLE_SRC
HOLE_START = 108442           # record frame where the third item started pre-shift

pm = resolve.GetProjectManager()
proj = pm.GetCurrentProject()
tgt = None
for i in range(1, proj.GetTimelineCount() + 1):
    tlx = proj.GetTimelineByIndex(i)
    if tlx and tlx.GetName() == TL_NAME:
        tgt = tlx
        break
if not tgt:
    result = {"ABORT": "timeline not found: " + TL_NAME}
else:
    proj.SetCurrentTimeline(tgt)
    t = proj.GetCurrentTimeline()
    if t.GetName() != TL_NAME:
        result = {"ABORT": "pin failed"}
    else:
        vids = [it for it in t.GetItemListInTrack('video', 1) if it.GetType() == 'video']
        auds = [it for it in t.GetItemListInTrack('audio', 1)]
        v3 = [it for it in vids if int(it.GetStart()) == HOLE_START]
        a3 = [it for it in auds if int(it.GetStart()) == HOLE_START]
        pre = {it.GetUniqueId(): (int(it.GetStart()), int(it.GetEnd())) for it in vids + auds}

        def cdl_sig(it):
            g = it.GetNodeGraph()
            n = g.GetNumNodes() if g else 0
            sig = {}
            for j in range(1, (n or 0) + 1):
                try:
                    sig[j] = it.GetCDL(j)
                except Exception as e:
                    sig[j] = "EXC:" + str(e)[:60]
            return sig

        pre_cdl = {it.GetUniqueId(): cdl_sig(it) for it in vids}
        ok_pre = len(vids) == 3 and len(auds) == 3 and v3 and a3
        res = {"pre_ok": ok_pre, "pre": pre, "pre_cdl": pre_cdl}
        if ok_pre:
            r1 = v3[0].SetPosition({'trackType': 'video', 'trackIndex': 1,
                                    'startFrame': HOLE_START + INSERT_LEN})
            r2 = a3[0].SetPosition({'trackType': 'audio', 'trackIndex': 1,
                                    'startFrame': HOLE_START + INSERT_LEN})
            res["setposition"] = [r1, r2]
            mp = proj.GetMediaPool()
            mpi = v3[0].GetMediaPoolItem()
            newV = mp.AppendToTimeline([{'mediaPoolItem': mpi, 'startFrame': SRC[0],
                                         'endFrame': SRC[1], 'mediaType': 1,
                                         'trackIndex': 1, 'recordFrame': HOLE_START}])
            newA = mp.AppendToTimeline([{'mediaPoolItem': mpi, 'startFrame': SRC[0],
                                         'endFrame': SRC[1], 'mediaType': 2,
                                         'trackIndex': 1, 'recordFrame': HOLE_START}])
            res["appended"] = [bool(newV), bool(newA)]
            # ---- after-state read-backs
            vids2 = [it for it in t.GetItemListInTrack('video', 1) if it.GetType() == 'video']
            post = {it.GetUniqueId(): (int(it.GetStart()), int(it.GetEnd())) for it in vids2}
            post_cdl = {it.GetUniqueId(): cdl_sig(it) for it in vids2}
            kept = all(uid in post_cdl and post_cdl[uid] == pre_cdl[uid] for uid in pre_cdl)
            links = {it.GetUniqueId(): [x.GetUniqueId() for x in (it.GetLinkedItems() or [])]
                     for it in vids2}
            res.update({
                "post": post, "post_cdl": post_cdl,
                "ids_unchanged": all(uid in post for uid in pre),
                "cdl_byte_identical": kept,
                "links_after": links,
                "geometry": sorted((s, e) for s, e in post.values()),
            })
        result = res
