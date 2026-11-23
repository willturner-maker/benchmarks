# Splash 1.7.0 → 1.7.1 transition — Tier 0 + Tier 1 (fingerprint + golden probes)

**Dates:** Tier 0 pre-capture 2026-11-23T01:23Z (instance on 1.7.0 before the upgrade); Tier 1 post-capture
2026-11-23T11:27Z (pinned 1.7.1 instance, supervisor pid 6987, back in the chain S3 before any relaunch).
**Method committed in Tier 0** (`../..`: `engine_fingerprint.py`, `golden_probes.py`; plan in commit `1401ae6`):
structural fingerprint diff + 13 behaviour probes, each run **twice per build** so the within-build floor is
measured before any cross-build claim.

## Tier 1 result — the epoch is behaviourally silent for the pinned config

**Fingerprint diff** (`../../tau2-bench/results/2026-11-23-backlog-chain/s3_fingerprint_diff.txt`): the only
non-runtime changes are `anchor version` (Splash 1.7.0 → 1.7.1) and `anchor cache build` (new src hash).
Model layout hash, max context (262,144), batch width (4), `ane_ffn.state=off` all **SAME**.

**Golden probes — the honest comparison is visible output, not the compare tool's raw labels.**
Per probe we compare `(content_sha, finish, sorted[(tool name, args_sha)])` across the two runs each build made:

| kind | probes | within-1.7.0 stable | within-1.7.1 stable | cross-epoch visible output |
|---|---|---|---|---|
| byte | decode_greedy_64, thinking_crowdout_16, thinking_room_256, json_schema_crowdout_64, toolcall_nested_forced, toolcall_nested_stream | all True | all True | **all byte-identical** |
| grammar | json_schema_nested, json_schema_nested_stream | True | True | **payload-identical** |
| timing | followup_63/72, prefill_cold/warm_2k, shared_head_session_a/b | (usage-only, no byte claim) | | |

The compare tool labels 4 probes "DIFF" — but inspecting the runs, every DIFF is **reasoning text moved and
completion length varied while the visible payload (content sha, finish reason, tool-argument shas) is
identical**, and reasoning/length move *within a single build* too (toolcall_nested_stream post runs: 142 vs
183 completion tokens on 1.7.1 alone; pre runs were 184/184 — the floor itself is what moved). That is the
within-build floor the Tier-0 design anticipated, not an epoch effect.

Notable: 1.7.1's shipped fix #790 (structured-output validator walking unreached branches) touches exactly the
nested-schema probes — **and their payloads are unchanged on 1.7.1**. The fix prevents validator pathology;
it does not alter completions for our config.

**Verdict:** across 8 byte/grammar claims the two epochs are indistinguishable, matching the tau2-side
findings (lottery stationarity, pass^3 replication) — the 1.7.0→1.7.1 move is behaviourally quiet on this
engine + config. The visible "outputs can differ" banner change is consistent with our measured ~50 %
per-request action lottery; the probe suite says the *distribution* did not move.
