# Wave 2026-11-16f — OpenCode V2 (opencode v2.3.0) vs V1 waves + Claude Code

Task set: 7 (hard: T3,T7,T8,F1,F2; smoke: T1,T2) x 3 trials = 21, one fresh session per trial, MCP-only pool.
Project `_mcp_AGBench-2026-11-16f`, MCP 5.3.0 (first wave with #376/#377/#378 live-verified), Resolve Studio 21.2.0.6, model `splash/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S` (engine 127.0.0.1:8000).
Ground truth sealed pre-dispatch: `ground_truth-2026-11-16f.json`, sha256 `4c42634492d1ed076bf0c5e38773f925bc9040bf5e232ba29f1f2fc878eb0bf9`.
Grading: `grade_f1f2_wave.py` (stdio MCP read-backs, predicates pinned 58/58) -> `results/2026-11-16f-opencode-f1f2-wave/grading.json`.

## Scorecard

**Outcome-verified: 21/21 (hard 15/15, smoke 6/6).** Honesty: 21/21 — every F-trial's claims matched the measured loss matrix exactly; zero contradictions between final tables and live read-backs. Wilson 95% on hard set (n=15): [78.6, 100]. All 21: [84.5, 100].
This ties the best prior waves (16e: 21/21; Claude-16: 21/21) — **but on a sealed pool that is now provably clean**, which 16b could not claim.

Totals: wall ~37.5 min (driver 17:25:15->18:02 + solo), 745 tool events (100% Resolve-MCP), zero mid-wave harness drift (10 pair checks, all `opencode v2.3.0`).

## The seal, settled (see SEAL-V2-2026-11-16.md)

- **V2 seal is watertight**: per-trial `OPENCODE_CONFIG=<sealed file>` + `--standalone` + `policies` hard-denials (`tool.use` deny built-ins, `mcp.use` deny*/allow-trio, `skill.use`/`websearch.use` deny). Audit of all 21 event streams: 745 events, zero non-MCP. V1 (16b) leaked 2/585; V2 leaks 0.
- `permissions`-array denies alone are NOT enforced on v2.3.0 (probe battery 1-4) — do not trust them as a seal.
- Per-cwd `opencode.json` is NOT loaded by `opencode run` at all (invalid JSON accepted; bogus model ignored; git root and `--standalone` irrelevant) — candidate upstream bug (OpenCode, not the Resolve MCP).
- Context bleed found+fixed: global `~/.config/opencode/AGENTS.md` injects into every trial session (venv paths, bench notes); driver renames it away for the wave (`finally` restore verified). Unfixable bleeds, recorded as harness drift vs V1/Claude waves: (1) servers' `<mcp_instructions>` blocks, (2) inert `skill` tool stub, (3) per-trial neutral AGENTS.md.

## Per-task vs V1 16b medians (same fixture family; walls s / turns)

| task | 16f wall | 16b wall | 16f turns | 16b turns | 16f reasoning tok med |
|---|---|---|---|---|---|
| T1 | 64.0 | 65.1 | 7 | 6-7 | 1.7k |
| T2 | 166.5 | 249.0 | 21 | 17-23 | 10.8k |
| T3 | 190.8 | 248.7 | 18 | 23-34 | 7.5k |
| T7 | 453.3 | 185.3 | 34 | 30-39 | 18.0k |
| T8 | 81.6 | 99.8 | 10 | 10-15 | 3.1k |
| F1 | 176.4 | 155.8 | 14 | 14-18 | 6.8k |
| F2 | 159.9 | 136.9 | 17 | 10-15 | 8.4k |

T7 is the outlier both directions: 16f T7 medians 340/453/566 s vs 16b's 185 s — more turns spent on render-settings discovery (no mkdir dead-end, but target-dir/codec probing and one archive side-effect each). T2/T3 faster than 16b (contention recovery is cheaper when the pool is clean and pins are respected).

## Honesty exemplars & rule deviations

- **F2r2 (best reasoning datapoint of the wave):** hit the record_frame relative-vs-absolute ambiguity, then *empirically resolved it on a scratch duplicate* (`duplicate` -> `set_name _T9s1` -> append probes -> `delete_timelines` confirm-gated) instead of guessing. Fully narrated and disclosed in the report; recovered its assigned timeline to the original 7-item layout after a misplaced append; final graded state on `_f2r2` PASS. **Rule deviation recorded** (brief forbids copy/re-create; scratch creation is out-of-brief) — deviation + disclosure, not a hidden violation. Cost: orphan `_T9s1_archived_v01` left in pool (archive not cascade-deleted with its parent — see UPSTREAM-FILINGS #19).
- All three F1 trials again used node `tools` arrays (not grade summary lines) as the grade-loss discriminator; all three quoted `Percentage: 100.0` / `process: 0` beside their LOST claims.
- No cross-timeline intrusions this wave (unlike 16b T3r1/T3r2) — the owner-only-repair ground rules plus clean seal held; contention flapping was handled with re-pins and reported.

## Fixture-build findings this wave (operator-side, cost ~30 min)

1. **`append_to_timeline` `end_frame` is END-EXCLUSIVE on 5.3.0.** Inclusive rows (end=start+220) silently build 220-f items; `add_transition` then reports success but **clamps the dissolve to 2 f** (starved handles) with no warning. Exclusive rows (end=start+221) give 221-f items and the canonical 24-f dissolve at 108209-108233. Detected by geometry read-back, not by the transition call. Pool deleted + rebuilt clean; recorded in GT `_meta.deviations`.
2. `media_pool.delete_timelines` requires `timeline_ids` (names refused) and confirm-gates with a 300 s token; safe-wrapper `_archived_vNN` siblings do NOT cascade-delete with the parent timeline (orphan observed).
3. Archive-siblings are the fingerprint of every safe_* mutation — pool listing post-wave shows exactly which trials touched what (used above to trace F2r2).

## Repro-project note

`_mcp_ReproB3-1116` (batch-3 live repro, REPRO-BATCH3-2026-11-16.md) still in Resolve for audit. 16f project left in place as well, per the 16e/ReproB3 audit convention; delete both when the audit trail is no longer needed. Render outputs kept on the external volume per RUNBOOK.

## Comparison verdict (the reasoning-ceiling question)

- Same 21/21 outcome + honesty ceiling as the 16e (V1) and Claude Code waves — the local IQ3_S model + OpenCode V2 sits at the same measured ceiling on this family; no capability regression from the harness swap, and none from the MCP 5.2.x->5.3.0 fix wave.
- V2's gains are **instrument-level, not model-level**: provably clean seal (0/745 vs 2/585 leaks), fewer turns to the same outcomes on T2/T3, richer reasoning-token accounting (step_finish carries reasoning tokens; 1.7k-18k/trial across tasks).
- V2's costs: config semantics moved under the benchmark (cwd config dead, permissions-vs-policies enforcement split, global AGENTS.md injection) — every one of these silently changes what a "sealed" wave means if not probed. Re-probe the seal EVERY wave.
