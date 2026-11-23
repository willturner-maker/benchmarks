# tool-loop-gate on Splash 1.7.1 — standard two-arm wave (2026-11-23)

**Suite/upstream:** `hermes_loop_gate.py` from `vcruz305/hermes-agentic-bench` (MIT), unmodified, commit
`6dc6f0e570850c196c8bda6e5e1f8ad5f7082910`, file sha256 `d108937b8cdee86e…` — same pin as `2026-11-19a`.
**Runner:** `../run_gate.sh` (ours); arms = harness defaults (temp 0.6 / top_p 0.95 / top_k 64) and greedy;
20 scripted-tool tasks, 12-turn cap. **Stack:** Splash 1.7.1, supervisor pid 6987 pinned argv
(supervisor_pins.txt), status before/after captured; chain S2, 11:25–11:27Z, right after the 238×3
confirmation wave — clean window (no co-tenant sampler hits).

| epoch/arm | pass | mean_tools | hit_cap | parse_fail | dup_tasks |
|---|---|---|---|---|---|
| 1.7.1 defaults | 15/20 | 2.9 | 1 | 0 | 1 |
| 1.7.1 greedy | **16/20** | 2.6 | 1 | 0 | 0 |
| 1.7.0 defaults (19a, 2 passes) | 14–15/20 | 2.4–2.55 | 0 | 0 | 0 |
| 1.7.0 greedy (19a, 3 passes) | 15/20 | 2.0–2.8 | 0–1 | 0 | 0–1 |

**Reading:** 1.7.1 greedy 16/20 sits one task above the 1.7.0 greedy repeat band (15/20 every pass); at
n=20 tasks one task = 5 pts and the suite's single-wave noise rule puts sub-5-pt deltas inside noise —
**no epoch effect established.** `parse_ok` holds at 0 parse failures (tool-call emission unbroken across
the epoch, corroborating the golden-probe byte identity); industriousness (mean_tools) drifts upward
slightly, also within the 1.7.0 repeat range. The one `hit_cap` per arm and one duplicate-call task in
defaults are task-level flips already seen in 1.7.0 repeats (cap/dup both appeared in 19a greedy passes).

Rows re-derivable from `wave.jsonl` (40 rows) via `../summarize.py`; `summary.json` agrees with the
per-file harness summaries.
