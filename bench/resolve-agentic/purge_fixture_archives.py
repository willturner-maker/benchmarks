#!/usr/bin/env python3
"""Purge the builder's `_archived_vNN` sibling timelines from a wave fixture, pre-dispatch.

Why: build_fixture_effort_ab.py's own mutation/versioning hooks leave `_X_archived_v01`
copies of every prebuilt timeline (base/T1/f1m/f2m). The grader's archive-sibling mutation
check can read those as in-wave artifacts — the census artifact that cost 1.5 grading rounds
in agbench-171 (proved benign via builder-log census there). Designing it out: fresh fixtures
get their archive siblings deleted BEFORE dispatch, with the log as the census evidence.
First used on _mcp_AGBench-2026-11-23c (14 -> 10 timelines).

Uses the builder's own confirm-gated Client (destructive actions issue a one-shot token;
both calls are logged). Log: <LOGDIR>/fixture-purge-<project>.jsonl

Usage: python3 purge_fixture_archives.py <project> [--dry]
"""
import argparse, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_fixture_effort_ab import Client, LOGDIR  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    LOGDIR.mkdir(parents=True, exist_ok=True)
    c = Client(LOGDIR / f"fixture-purge-{a.project}.jsonl")
    c.tool("project_manager", "load", {"name": a.project})
    tls = c.tool("timeline", "list").get("timelines", [])
    pat = re.compile(r"_archived_v\d+$")
    doomed = [t for t in tls if pat.search(t["name"] or "")]
    print(f"{a.project}: {len(tls)} timelines, {len(doomed)} archive siblings")
    for t in doomed:
        print("  -", t["name"])
    if a.dry or not doomed:
        c.close()
        return
    r = c.confirm("media_pool", "delete_timelines",
                  {"timeline_ids": [t["id"] for t in doomed]})
    print("delete result:", json.dumps(r)[:300])
    after = c.tool("timeline", "list").get("timelines", [])
    left = [t["name"] for t in after if pat.search(t["name"] or "")]
    print(f"after: {len(after)} timelines, remaining archive siblings: {left}")
    c.close()
    if left:
        raise SystemExit("purge incomplete")


if __name__ == "__main__":
    main()
