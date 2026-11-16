# Live MCP payload shapes used by `grader_selftest.py`

Captured **2026-11-15** from a scratch project on the same host the waves run on, so the grading
predicates can be checked against what the probes *actually* return rather than against what the
RUNBOOK prose remembers. Re-capture this file whenever the MCP build or the Resolve build moves,
then re-run `grader_selftest.py` — a predicate written against a stale shape can silently stop
reading anything.

Capture environment (identical to the wave convention): headless Resolve `-nogui`,
`resolve_control.launch(headless=true)`; throwaway project `_mcp_AGBench-selftest`; throwaway
timeline `selftest_shape` created via `media_pool.create_timeline` (see the gotcha below), set
current via `timeline.set_current(id=…)`. Nothing from an operator project was read or touched;
the project and timeline were deleted and Resolve quit without saving afterwards.

## The five probes that grade waves

| Probe | Shape returned | What the grader must not assume |
|---|---|---|
| `timeline_markers.get_all` | **`{"markers": {"60": {"color","duration","note","name","customData"}}}`** — a dict keyed by the frame **string**; entries carry **no `frame` key** | iterating a list, or reading `entry["frame"]`. `normalize_markers()` handles both and a lost frame key fails closed |
| `timeline.probe_timeline_structure` | `{name, id, start_frame, end_frame, start_timecode, item_count, tracks:{video,audio,subtitle:{track_count, tracks:[{track_index, item_count, items:[…]}]}}, markers:{}}` | a flat `items` list. `grade_t3` is handed one track's `items` array by the caller; the nesting is the caller's job to flatten, and `markers` here is the same dict shape as `get_all` |
| `timeline.detect_gaps_overlaps` | `{gaps:[], overlaps:[], gap_count:0, overlap_count:0}` | nothing — lists are lists. Prefer `gap_count`/`overlap_count` when you only need the verdict |
| `render.list_jobs` | `{jobs:[]}` | a dict. Empty queue is `[]`, not `null` |
| `timeline_markers.add` | `{success, frame, _versioning:{archived, archived_version}, _operation:{…,"timeline":{name,id}}}` | that a `success:true` means the marker exists. The read-back (`get_all`) is the grade; `_versioning.archived:true` is what a mutation trial shows even on a *read-only* task — see the T1 note |

Two things that only the live capture showed:

1. **Markers are keyed by frame, not listed.** `get_all` on the scratch timeline after
   `add(frame=60, color="Green", name="bench-hit", duration=1)` returned the entry under the string
   key `"60"`, with `duration` and `customData` present and no frame field inside. This is Resolve's
   own shape passed through, not the MCP server's invention: upstream
   `Timeline.GetMarkers()` is documented as *"Returns a dict (frameId -> {information})"* with the
   example `{96.0: {'color': 'Green', 'duration': 1.0, 'note': '', 'name': 'Marker 1',
   'customData': ''}}` — i.e. the key can be a **float**, and after a JSON round-trip it becomes the
   string `"96.0"`. `_frame_of()` therefore parses through `float()`: a bare `int("60.0")` raises,
   which would read as "no marker at frame 60" and fail a correct wave. Pinned by the
   `rule-upstream-float-frame-key` case. `AddMarker` on 21.2 requires `duration` (without it the call
   returns a bare `False`), which is why the captured entry has `"duration": 1`.
2. **`timeline.create_timeline` fails with "No current timeline" in a freshly created empty
   project.** The working route is `media_pool.create_timeline(name)` → then
   `timeline.set_current(id=…)`. Any harness that seeds a scratch timeline must use the media_pool
   route or it will die before the first trial.

## T1 caveat this capture also settles

`_versioning.archived: true` appears on **any** marker/mutation-family operation, including ones the
agent never intended as its own. For T1 (read-only fidelity) the mutation check must therefore be
"did an `_archived_vNN` sibling appear on *the fixture timeline* during the trial window", read from
the timeline list, not "did some response somewhere mention `archived`". The `trap-mutation-sibling`
case in the self-test covers the grading decision; the *collection* rule belongs to the driver.

## Two envelope behaviours the same capture settled

- **`media_pool.delete_timelines` does not cascade to the auto-archive.** Deleting `selftest_shape`
  reported `timelines_before: 2 → timelines_after: 1`: the `_archived_v01` sibling the marker `add`
  created stayed behind and needed its own delete (its own `confirm_token`). This is why §5 of the
  RUNBOOK lists archive deletion separately from timeline deletion — the count check in §5 is what
  catches it.
- **A dry run's `ignored_params` warning is not proof a param is unused.**
  `safe_project_delete(name, close_current=true, dry_run=true)` answered `would_delete: true` plus
  `Ignored params this action does not read: close_current`; the *executing* call then refused with
  "Refusing to delete the currently open project; pass close_current=True". Same build, same params,
  opposite verdict. Checked the upstream tracker on 2026-11-15: nothing filed.

## Reproduce

```
resolve_control.launch(headless=true)
project_manager.safe_project_create(name="_mcp_AGBench-selftest")
media_pool.create_timeline(name="selftest_shape")            # NOT timeline.create_timeline
timeline.set_current(id=<returned id>)
timeline_markers.add(frame=60, color="Green", name="bench-hit", duration=1)
timeline_markers.get_all()                                    # dict keyed "60"
timeline.probe_timeline_structure() ; timeline.detect_gaps_overlaps() ; render.list_jobs()
# teardown, in order: media_pool/timeline delete_timelines → project_manager.safe_project_delete
# → resolve_control.quit  (never save: an unsaved project blocks forever headless)
```
