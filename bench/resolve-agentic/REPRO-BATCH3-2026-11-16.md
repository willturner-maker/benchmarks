# Batch-3 live repros — #376 / #377 / #378 — 2026-11-16

Verified against: MCP **5.3.0** (current), Resolve Studio 21.2.0.6 (GUI session), harness OpenCode v2.3.0 (operator session), scratch project `_mcp_ReproB3-1116`, timeline `_mcp_ReproB3_base` (3840x1520@29.97, the wave's fixture clip (camera name redacted), two linked 221-f segments at 108000/108221, Cross Dissolve 108209–108233, pin `0d6da5af`).
All three upstream releases self-report **"Offline tests only — no live Resolve run"**. This file is the live verification.

## #376 ripple_insert blocker — FIXED, live-confirmed
Dry-run plan on transition-bearing tail (record_frame 100 rel, 101-f linked pair):
- blocker.reason.code: **`NO_MEDIA_POOL_ITEM`** (was `UNSPECIFIED`)
- blocker.reason.category: **`unsupported`** (was `resolve_api_failed`)
- blocker.reason.retryable: **`false`** — consistent with error-level `retryable:false` (was `true`)
- message: "…(transitions / generators / titles / Fusion comps without pool media cannot be rebuilt)" — **transitions named** (was "titles/generators")
- plan exposes `tail_items` incl. the transition by name; `subtitle_items_after_insert_point: 0`, `locked_tracks_with_tail: []`
Fix shipped in **v5.2.14** (PR #381, adapted from #376).

## #377 safe_set_project_settings ints — FIXED, live-confirmed
Two calls, `dry_run:false`:
- `{timelineResolutionWidth: 3840, timelineResolutionHeight: 1520, timelineFrameRate: "29.97"}` → all `write:true`
- discriminating: `{timelineResolutionWidth: 2000}` (int) → `write:true`, `readback:"2000"`, `restore:true`, `restored_value:"3840"`
Numeric→string coercion lands; silence-on-refuse is gone. Fix in **v5.2.13** (PR #380).

## #378 safe_set_cdl lowercase payload — FIXED, live-confirmed (no release note names it!)
Issue closed `completed` 2026-11-16 20:55Z but **no release body (5.2.13/5.2.14/5.3.0) mentions #378** — worth a docs nudge upstream.
- `safe_set_cdl` with `{slope:[1.06,1,0.94], offset:[0.01,0,0], power:[1,1,1], saturation:1.15}` (item 0, node 1) → `success:true`
- normalized payload: PascalCase keys carry the REQUESTED values (`Slope "1.06 1.0 0.94"`, `Offset "0.01 0.0 0.0"`, `Saturation "1.15"`) — lowercase-duplication-with-identity-defaults is gone
- read-back `probe_node_graph`: `tools:["Primary Balance","Saturation, Hue & Lum Mix"]` — issue's exact proof signature

## Bonus observations (5.3.0, live)
- New append pin works: `media_pool.append_to_timeline` honored `timeline_id` (fresh 5.3.0 feature, exercised live for the first time here).
- ripple_insert frame guard: absolute frames < timeline start now REFUSE with an explanatory, actionable error (record_frame_mode guidance) — good; my first call tripped it.
- `knowledge` actions: topics/get/search/capabilities (no `api_truth` action; ledger lives in topic bodies).
- Timeline start = 108000 (hour TC): wave drivers must use `record_frame_mode:"relative"` or absolute ≥108000.

Repro project left in place (`_mcp_ReproB3-1116`) for audit; safe wrappers restored settings as graded.
