# tenancy A/B 2026-11-20 — co-tenant residency trips the KV pool; offered volume does not

**Question.** `2026-11-19c-clean` retired the token-threshold reading of the 2026-11-16b KV trip (no trip at
17.04× single-tenant) and published the cause of 16b's trip as open. This is the controlled attack on that
open half: the same KV ladder run twice on one engine launch, the only difference being whether something else
holds long contexts resident. If the co-tenanted arm trips where the clean arm does not, the 16b regime is
reproducible and residency contention — not prompt volume — is the mechanism.

**Answer: it does, by a factor of ~50.** The clean arm survived 12/12 rounds up to **1.90× the resident
budget per round**; the co-tenanted arm tripped on its **first round, at 0.33× bench volume**, with exactly
16b's signature (spill + disk demotion + suspension + cache eviction).

**Window:** `2026-11-20T18:40:53Z → 18:55:01Z` (14 m 08 s), detached via `../../run_tenancy_detached.sh`,
hard deadline 25 min (unused: exit 0). Operator idle per suite rule 10. **Engine:** Splash **1.7.0**, same
instance as 19b/19c/depth/depth-fine, never restarted; lifetime counters carried in at
`susp 7 / spill 3,135,729 / demotions 9,209 / refused 1,287` (the +3.10 M spill is the
[`../tenancy-2026-11-19-runaway/`](../tenancy-2026-11-19-runaway/RECORD.md) footprint) — all figures below
are window deltas. **Instrument:** `../../tenancy_repro.py` (post-runaway fixes: no idle-wait under co-tenants,
deadline enforced in rounds and workers, 2 s duty gaps).

**Tenancy:** 85 status samples; 275 attributed in-flight samples; the only foreign request in the whole window
is **one 99,721-tok operator decode at 18:40:53**, inside the 90 s lead-in. (The wrapper's read-back also
flagged 34 co-tenant samples as "foreign" — matcher bug: it compared against the 120,000-tok *target* instead
of the 128,126-tok *actual*; fixed after this run, affects no measurement.)

## Arm A — clean, 12/12 rounds, zero pressure

| width | prompt tok / round | wall s | tok/s | susp / spill / demote Δ |
|---|---|---|---|---|
| 2 | 45,812 (0.30×) | 12.79 / 12.86 | 3,582 | 0 / 0 / 0 |
| 6 | 137,436 (0.88×) | 38.21 / 38.23 | 3,597 | 0 / 0 / 0 |
| 10 | 244,060 (1.57×) | 67.06 / 67.11 | 3,639 | 0 / 0 / 0 |
| 12 | 295,872 (**1.90×**) | 81.55 / 81.68 | 3,623 | 0 / 0 / 0 |

All 24 requests fresh prefill (`prefill_rows` ≈ prompt tokens, suite rule 3). Wall scales linearly with width:
the same **flat ~3,580–3,640 tok/s plateau** as 19c-clean. Peak *sampled* residency for the entire arm:
**99,744 tok = 0.64× capacity**, even while summed in-flight contexts hit 295,872 (1.90×) — admission
throttling (`prefilling ≤ 2`) never lets offered volume become residency. Zero spill moves across the arm.

## Arm B — one co-tenant shape, first round, trip

3 synthetic operator sessions: 128,126-tok prompts (target 120 k), 512-token decode, continuous. One round ran
before the stop rule fired:

- bench load: width 2, **51,812 tok = 0.33× budget** (vs 1.90× survived minutes earlier)
- co-tenant: 1 completed (128,126 tok, 55 tok out, 50.04 s) + 2 queued/prefilling at 18:53:04
- engine: **`resource_suspensions` +1 · `spill_moves` +3,275 · `disk.kv_demotions` +555 ·
  `kv_demotions_refused` +7**, `pages_cache` 4,096 → **1,612** (the prefix cache is evicted to make room),
  peak residency 140,416 tok = 0.90×, peak `prefilling` 3

One 128,126-tok context is **4,004 pages = 0.82× of the 4,864-page pool on its own**. Add two 22.9k bench
rounds and any cache prefixes and the pool crosses — the governor answers with spill, demotion (some refused)
and a cache suspension. That is 16b's recorded signature, produced on demand.

## What this establishes, and what it doesn't

1. **Co-tenant residency is *sufficient* to produce 16b's trip signature at trivial bench volume.** The
   16b-style trip needs ~0.33× bench load when long sessions are co-resident; the same stack shrugs off 1.90×
   per-round / multi-million-token cumulative volume when it isn't.
2. **The volume side now has a quantitative explanation.** KV trips when the *residency* of admitted-concurrent
   contexts plus cache prefixes crosses the 4,864-page pool; on this instance admission caps residency
   (`prefilling ≤ 2`, batch width 4), so offered volume cannot force that crossing — 22.9k prompts cap
   residency at 0.64× even at width 12. The "trip" question is entirely about what is admitted *at once*, not
   what is offered in total.
3. **Not established:** that 16b's actual window contained ~100k+-tok co-resident sessions. Sufficiency +
   matching signature ≠ historical proof; 16b stays honestly attributed to "co-tenancy regime", still not to a
   named tenant. n = 1 trip round (stop-on-trip by design), one instance, and yesterday's confounded hint
   (operator 83k co-resident → +1 suspension below the line) is the second observation of the same direction.

## Files

`tenancy_repro.jsonl` (setup, 13 round rows, summary incl. co-tenant stats), `run.out`, `run.err` (empty),
`run.log`, `engine_samples.jsonl` (85 samples @ 10 s), `status_before.json` / `status_after.json`, `pins.txt`.
Local absolute paths scrubbed to `~`.
