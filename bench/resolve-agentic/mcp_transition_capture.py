#!/usr/bin/env python3
"""MCP-server version transitions: capture a fixed read-back surface so a server bump can be
compared against the previous build (the MCP analog of splash-concurrency's golden probes).

Why: the resolve-agentic waves grade through the community MCP server; when the SERVER moves
version (5.3.1->5.3.3->5.3.4->5.4.0...) the read-back surface is part of what changed, and ad-hoc
"it still works" is not evidence. Run this BEFORE and AFTER the upgrade against the SAME fixture
project; diff the two files. Identity-bearing fields are dropped or redacted (name/timeline_name/
file_path/media_pool_item_name keys; volume paths and camera filenames inside any string) so
captures are commit-safe.

Usage: python3 mcp_transition_capture.py OUT.json [--project _mcp_AGBench-...]
Fixed surface: server version, project load, timeline inventory (names), full structure probes
of _T1/_base/_f1s1/_f2r1, node-graph + link read-backs on fixed indexes, gaps/overlaps.
"""
import argparse, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from grade_f1f2_wave import Client  # stdio MCP client, same one the graders drive


DROP_KEYS = ("name", "timeline_name", "file_path", "media_pool_item_name")
# values that embed real media identity: volume paths, camera filenames
REDACT = re.compile(r"/Volumes/|P\d{6,}\.(MOV|MXF|MP4|mts|m2ts)", re.I)


def scrub(o):
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items() if k not in DROP_KEYS}
    if isinstance(o, list):
        return [scrub(v) for v in o]
    if isinstance(o, str) and REDACT.search(o):
        return REDACT.sub("<media>", o)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--project", default="_mcp_AGBench-2026-11-23b")
    a = ap.parse_args()
    c = Client()
    P = a.project
    c.tool("project_manager", "load", {"name": P})
    cap = {"project": P, "surface": {}}
    cap["surface"]["version"] = c.tool("resolve_control", "get_version", {})
    cap["surface"]["timeline_names"] = sorted(
        t["name"] for t in c.tool("timeline", "list").get("timelines", []))
    for tl in ("_T1", "_base", "_f1s1", "_f2r1"):
        name = f"{P}{tl}"
        tid = next(t["id"] for t in c.tool("timeline", "list").get("timelines", []) if t["name"] == name)
        cap["surface"][f"probe{name}"] = scrub(
            c.tool("timeline", "probe_timeline_structure", {"timeline_id": tid}))
        cap["surface"][f"gaps{name}"] = scrub(
            c.tool("timeline", "detect_gaps_overlaps", {"timeline_id": tid}))
    f2 = next(t["id"] for t in c.tool("timeline", "list").get("timelines", []) if t["name"] == f"{P}_f2r1")
    f1 = next(t["id"] for t in c.tool("timeline", "list").get("timelines", []) if t["name"] == f"{P}_f1s1")
    cap["surface"]["nodegraph_f2r1_item4"] = scrub(c.tool(
        "timeline_item_color", "probe_node_graph",
        {"source": "item", "track_type": "video", "track_index": 1, "item_index": 4, "timeline_id": f2}))
    cap["surface"]["links_f2r1_item4"] = scrub(c.tool(
        "timeline_item", "get_linked_items",
        {"track_type": "video", "track_index": 1, "item_index": 4, "timeline_id": f2}))
    cap["surface"]["grade_f1s1_item0"] = scrub(c.tool(
        "timeline_item_color", "grade_evidence_base",
        {"track_type": "video", "track_index": 1, "item_index": 0, "timeline_id": f1}))
    pathlib.Path(a.out).write_text(json.dumps(cap, indent=1, sort_keys=True, default=str) + "\n")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
