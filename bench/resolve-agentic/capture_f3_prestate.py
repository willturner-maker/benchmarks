#!/usr/bin/env python3
"""Capture the F3 pre-dispatch STATE_FIELDS bundles (the trap-liveness arm check).

Runs immediately BEFORE dispatch, after the sealed build: for each _f3r1..N, take the rearm-style
state bundle for the item that WILL be shifted (probe row 3 on the armed pre-state: clip0,
transition, clip1, clip2). Fails loudly if any copy lacks grade or link — grade_f3's null case
refuses to score those, so capturing is also the final arming proof.

Writes results/<wave>/f3_prestate.json: {timeline: {item_probe_row: 3, state: <bundle>}}.
"""
import argparse, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_fixture_effort_ab import Client          # noqa: E402
from rearm_trap_533 import state                    # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--wave", required=True)
ap.add_argument("--reps", type=int, default=6)
a = ap.parse_args()

outp = pathlib.Path(a.wave)
outp.mkdir(parents=True, exist_ok=True)
mc = Client(outp / "f3-prestate-calls.jsonl")
mc.tool("project_manager", "load", {"name": a.project})
ids = {t["name"]: t["id"] for t in mc.tool("timeline", "list").get("timelines", [])}
out = {}
bad = []
for k in range(1, a.reps + 1):
    tl = f"{a.project}_f3r{k}"
    if tl not in ids:
        bad.append(f"{tl}: missing")
        continue
    st = state(mc, tl, ids[tl], 3)
    armed = bool(st["grade_tools"]) and st["linked_item_count"] >= 1
    out[tl] = {"item_probe_row": 3, "armed": armed, "state": st}
    print(f"{tl}: grade_tools={st['grade_tools']} links={st['linked_item_count']} "
          f"transition={st['transition_present']} -> armed={armed}")
    if not armed:
        bad.append(f"{tl}: un-armed")
mc.close()
(outp / "f3_prestate.json").write_text(json.dumps(out, indent=1, default=str))
if bad:
    sys.exit("!! F3 ARM CHECK FAILED: " + "; ".join(bad))
print("F3 ARM CHECK OK —", outp / "f3_prestate.json")
