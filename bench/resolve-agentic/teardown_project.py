#!/usr/bin/env python3
"""Teardown a bench scratch project and append the evidence line to results/teardown-2026-11-17h.jsonl.

Same client (scrubbed MCP log) as the fixture builder. Refuses names that don't match the
_mcp_ scratch convention so the operator's own projects can never be targeted by accident.
"""
import argparse, json, pathlib, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_fixture_effort_ab import Client  # noqa: E402

LOG = HERE / "results" / "teardown-2026-11-17h.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    a = ap.parse_args()
    if not re.match(r"^_mcp_[A-Za-z0-9._-]+$", a.project):
        sys.exit(f"refusing teardown of {a.project!r}: scratch projects are named _mcp_*")
    c = Client(HERE / "results" / "teardown-mcp-calls.jsonl")
    try:
        def plist():
            r = c.tool("project_manager", "list")
            items = r.get("projects") or r.get("project_names") or []
            return [x if isinstance(x, str) else x.get("name") or x.get("project")
                    for x in items]
        names = [n for n in plist() if n]
        other = next((n for n in names if n != a.project), "_MCP_DefaultProject")
        print("leave current-first: load", other)
        c.tool("project_manager", "load", {"name": other})
        r = c.tool("project_manager", "delete", {"name": a.project})
        ok = bool((r.get("delete_detail") or {}).get("success", r.get("success")))
        gone = a.project not in [n for n in plist() if n]
        with open(LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                "project": a.project, "result": str(r)[:600],
                                "confirmed_absent_after": gone}) + "\n")
        print("deleted:", ok, "| confirmed absent:", gone)
        if not (ok and gone):
            sys.exit("TEARDOWN NOT CONFIRMED — inspect before publishing")
    finally:
        c.close()


if __name__ == "__main__":
    main()
