# splash depth probe, fine pass — the occupancy curve the 10 s sampler could not see

**Why this rerun exists.** The first depth probe (`../depth-2026-11-19/`) proved spill onset at the resident
line but published an explicit gap: `pages_active` read **0** at every external sample because turns complete in
~7 s and the sampler ran at 10 s — the residency curve itself was never observed, and the onset was bounded only
to a 20 k-token step. This pass fixes both: `--turn-tokens 5000 --max-turns 44` (5.5 k-token steps) and an
**intra-turn 1 s sampler** inside each request, so occupancy is measured while the request is live.

**Window:** `2026-11-20T02:44:50Z → 02:51:02Z` (6 m 12 s), detached via `../../run_depth_detached.sh`, operator
idle. **Tenancy: clean by attribution** — 38 status samples, all 18 in-flight requests attributed to this run,
zero foreign. **Engine:** Splash **1.7.0**, same instance as 19b/19c/depth (not restarted); all figures are
window deltas. **Instrument:** `../../depth_probe.py` at the fine-pass commit (adds `intra_turn` peaks +
`t_start`/`t_end`); calibration unchanged (15.95 tok/word → 313 words per ~5 k-token turn).

## The curve

44 turns, **+5,549→5,862 prompt tokens each** (chatml overhead grows slightly), from 9,049 (0.058×) to
258,611 (**1.662×**) — no refusal (the walk stopped below the 262,144 window by design). Selected rows;
`peak*` columns are intra-turn maxima at 1 s:

| turn | prompt tokens | × resident | wall s | peak `pages_active` | peak `kv_tokens` | spill Δ | peak wait_mem / susp |
|---|---|---|---|---|---|---|---|
| 1 | 9,049 | 0.06× | 1.57 | 283 | 9,056 | 0 | 0 / 0 |
| 12 | 71,027 | 0.46× | 1.92 | 2,219 | 71,008 | 0 | 0 / 0 |
| 26 | 153,095 | **0.984×** | 2.01 | **4,784** | 153,088 | **0** | 0 / 0 |
| **27** | **158,957** | **1.021×** | 2.11 | **4,968** | 158,976 | **+2,048** | 0 / 0 |
| 28 | 164,819 | 1.06× | 1.99 | 5,151 | 164,832 | +256 | 0 / 0 |
| 36 | 211,715 | 1.36× | 2.02 | 6,617 | 211,744 | 0 | 0 / 0 |
| 44 | 258,611 | **1.662×** | 2.11 | **8,083** | 258,656 | +256 | 0 / 0 |

Lifetime deltas for the whole pass: `spill_moves` **+5,120**, `prefill_rows` +255,986, and
`resource_suspensions` / `priority_suspensions` / `disk.kv_demotions` / `kv_demotions_refused` /
`capacity_failures` **all zero** — corroborated by both samplers (the 1 s intra-turn peaks for
`admission.waiting_memory`, `admission.suspended` and `restoring` are zero on every one of the 44 turns).

## What the curve adds

1. **The spill trigger is the page capacity, exactly, and it resolves to one step.** Last clean turn 26: peak
   4,784 pages < the 4,864-page capacity, spill 0. First spilling turn 27: peak **4,968 > 4,864**, spill
   **+2,048** (64 pages moved). The onset bracket collapses from the coarse probe's (0.90×, 1.04×] to
   **(0.984×, 1.021×]** — i.e. within 5,862 tokens of `kv_capacity_pages × block_tokens`. The engine's native
   unit is pages; the "155,648-token resident line" is that same wall expressed in tokens.
2. **Residency is 1:1 with context while it fits.** `peak_kv_tokens` tracks `prompt_tokens` to within one page
   on every turn — the whole held context is resident, not a window of it. Past the line it keeps growing:
   peak reaches **8,083 pages = 1.66× capacity**, still served, with only a steady **~256-move/turn spill
   churn** (and 0 on every third turn) doing the eviction bookkeeping.
3. **The two probes now corroborate each other across different step sizes.** Coarse (20 k steps): onset
   between turns 6–7, 4,945 spill moves total, zero suspensions/demotions. Fine (5.5 k steps): onset at
   1.021×, 5,120 moves, same zeros. The mechanism is not a step-size artifact.
4. **"Cheap per turn" survives, with a measured slowdown.** Prefill *work* per turn stays ~the new tokens
   (255,986 rows for the whole pass ≈ 44 × 5.9 k — the prefix cache carries the history), and **wall time per
   turn barely moves**: 1.57 s at 9 k context → 2.01 s at 153 k → 2.11 s at 258 k. Effective service of the new
   turn slips from ~3,570 tok/s shallow to ~2,780 tok/s deep — **−22 % over a 28.6× context increase**. That
   top rate lands in the same band as the volume waves' flat prefill plateau (3,469–3,498 tok/s, 19c-clean):
   whether the context is 9 k or 258 k, this stack serves a fresh span at roughly the same flat rate, and the
   coarse probe's "+34 % over 9.8×" is consistent, not contradicted.
5. **Still no admission pressure at any depth.** `waiting_memory`, `suspended`, `restoring` peak 0 across all
   44 turns at 1 s sampling. On this stack, a single deep conversation earns **spill churn and slower turns**,
   never queueing — the queue/pressure machinery only engages with multiple concurrent requests, and even then
   19c-clean showed it engages as *queue depth*, not KV pressure.

## Limits

- n = 1 conversation again, one instance, one day. The 256-move steady state is an average of an alternating
  pattern (0 / 256 / 256 …), not a constant.
- Intra-turn sampling caught 2–3 samples per turn; a peak between samples could still be missed, but the
  1:1 tracking with prompt size on 44/44 turns makes a large miss implausible.
- Wall time includes HTTP and JSON overhead (~constant); the growth is in engine service time, but this probe
  cannot attribute it between attention cost and KV bookkeeping.
- Same synthetic-filler caveat as the coarse probe: right shape, not real agent retrieval behaviour.

## Files

`depth_probe.jsonl` (setup, 44 turns with `intra_turn` peaks and timestamps, summary), `run.out`, `run.err`
(empty), `run.log`, `engine_samples.jsonl` (external 10 s), `status_before.json` / `status_after.json`,
`pins.txt`. Local absolute paths scrubbed to `~`.
