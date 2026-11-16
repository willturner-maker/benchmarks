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

## F1/F2 shapes, captured sealing the frontier pair (same day, project `_mcp_AGBench-F1F2-1115`)

| Probe / action | Shape returned | What the grader must not assume |
|---|---|---|
| `timeline_item.get_speed` | `{speed:{"Percentage":80,"PitchCorrection":true}}` | stability of the key set. After a rebuild the read-back is `{"Percentage":100}` — **`PitchCorrection` vanishes**, so a grader diffing whole dicts reports "shape changed" instead of "speed lost". Diff the scalars |
| `timeline_item.get_retime` | `{process:3, motion_estimation:2}` (ints; `optical_flow` = 3) | that a successful `set_retime` stuck — re-read it, it is cheap |
| `timeline_item_color.probe_node_graph` | `{available, num_nodes, nodes:[{node_index,lut,cache_mode,label,tools:[…]}]}` | that grade state is readable as numbers. **It is not**: `tools` is `[]` on an ungraded node and `["Primary Balance","Saturation, Hue & Lum Mix"]` once a CDL is applied. That presence/signature is the whole grade read-back available off the Color page |
| `timeline_item_color.probe_grade_item` / `grade_evidence_base` | the same node block plus `versions`, `color_group`, `cache`, `methods` | that `evidence_base`'s word "graded" is independent proof — it is built from the same `tools` list |
| `timeline.replace_source_range` (dry run) | `{plan:{record, source_before, source_after:{start,end_exclusive}, carried:[…], not_carried:[…], linked_audio:[…], blockers:[…]}}` | that a `carried` list is a promise. It is a claim; grade the post-state read-backs. `blockers` is why `ignore_linked=true` is needed on linked pairs, and taking it **deliberately desyncs the audio** |
| `timeline.ripple_insert` (dry run) | `{plan:{insert_frame_absolute, shift_frames, inserts, head_item_count, tail_item_count, tail_items, straddlers, blockers, subtitle_items_after_insert_point, gap_frames_by_track, warnings}}` | that a timeline holding a transition can be rippled across it — the plan returns `RIPPLE_PLAN_BLOCKED` and names the transition item as a blocker with `reason.code UNSPECIFIED` |
| `timeline.probe_timeline_structure` on a transition timeline | the transition appears as a **video-track item**: `{name:"Cross Dissolve", start, end, duration, source_start:null, media_pool_item_id:null, item_index:1}` | that item_index counts clips. It counts transitions too, so "video item 2" is the transition. `_is_transition()` keys on the two nulls |
| `timeline.detect_gaps_overlaps` on that timeline | `gap_count:0, overlap_count:2` — a centred 24-f dissolve yields two 12-frame overlap rows | that a correct ripple-insert result has `overlap_count 0`. On a transition-bearing timeline **2 is correct**, and the `rule-overlap-count-0-refused` case pins it |
| `timeline_item.add_transition` | `{success, transition:{id,name,start,end,duration}}` | that this needs the UI. It does not, on 21.2.0.6 |
| `timeline_item.add_keyframe` | **error `KEYFRAME_API_UNAVAILABLE`** | that Inspector keyframes can be armed from a fixture recipe at all |
| `timeline_item.get_linked_items` | `{items:[]}` after a shift (was 1) | that links survive a rebuild — they do not, silently |

### Fixture-build rules this capture produced

- `project_settings.set_setting` wants **string** values for `timelineResolutionWidth/Height`
  (`"3840"` wrote; `safe_set_project_settings` with the int `3840` reported `write:false` and restored
  the old value). Read each key back individually.
- `timeline_item_color.safe_set_cdl` with lowercase `slope/offset/power/saturation` →
  `set_cdl_returned_false` (diagnosis blames the item, not the payload). The raw `set_cdl` with
  PascalCase **string** values (`"Slope":"1.06 1 0.94"`, `"NodeIndex":"1"`) applied, and the effect is
  visible in `GetToolsInNode`.
- `timeline.duplicate` copies the **current** timeline — there is no pinned duplicate. An F1/F2 fixture
  copy must `set_current` to the armed timeline first; the first `_f1probe` came out an un-armed copy of
  the base and had to be deleted. (The server does report `DuplicateTimeline`'s silent current-pointer
  move as a `known_limitation` and restores the pointer itself.)
- A transition consumes 12 source frames either side, so the flanking clips' source spans grow (221→233)
  and their windows overlap: capture ground truth **after** arming, never before.
- `append_to_timeline` on 5.2.11 **requires** `track_index` per row, and its readback counts a transition
  in `item_count` (a 3-clip + 1-transition video track reports `item_count: 4`).

## Reproduce (frontier pair)

```
resolve_control.launch(headless=true)
project_manager.safe_project_create(name="_mcp_AGBench-F1F2-1115")
project_settings.set_setting(timelineResolutionWidth="3840")   # strings; read back each key
… Height="1520" ; timelineFrameRate="29.97"
media_pool.create_timeline(name="…_base") ; media_pool.safe_import_media([clip])
media_pool.append_to_timeline(clip_infos=[{clip_id, start_frame, end_frame, record_frame, track_index} ×2])
# F1: timeline_item set_speed/set_retime/set_transform/set_crop + set_cdl (PascalCase) + fusion add_comp
# F2: append a 3rd item, timeline_item.add_transition({Cross Dissolve, simple, start, center, 24}), set_cdl ×2
timeline.probe_timeline_structure / detect_gaps_overlaps ; per-item get_speed/get_retime/get_transform/get_crop
timeline_item_color.probe_node_graph ; timeline_item_fusion.get_comp_count ; timeline_item.get_linked_items
# measure the op on a copy: timeline.set_current(<armed id>) → timeline.duplicate → the op (dry_run, then confirm_token)
# teardown: project_manager.safe_project_delete(name, close_current=true) — no SaveProject anywhere, headless
```

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
