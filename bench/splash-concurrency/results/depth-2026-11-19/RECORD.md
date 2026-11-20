# splash depth probe — 2026-11-19 (one context, walked across the resident line)

**Why this exists.** Every wave in this suite pushes prompt **volume** (many long requests at once) and none could
trip the KV pool; `2026-11-19c-clean` explained why — width becomes scheduler queue depth, and `pages_active`
pinned at 0.39× budget at 17.04× offered volume. The 19b record named the untested axis as **depth**: one context
walking toward the resident line **while held across turns**, which is what real agent sessions do. This is that
probe.

**Window:** `2026-11-20T02:24:58Z → 02:28:37Z` (3 m 39 s), detached via `../../run_depth_detached.sh`, operator
idle, `/status` sampled at 10 s. **Engine:** Splash **1.7.0**, the same instance as the 19b/19c waves, **not
restarted** — lifetime counters carried in at `resource_suspensions 4 / spill_moves 22,560 / kv_demotions 9,045 /
kv_demotions_refused 1,287`; all figures below are window deltas.
**Instrument:** `../../depth_probe.py`, unmodified after this run. One chat conversation, turns added one at a
time, `max_tokens 8` so decode is irrelevant, every block unique (`depth-2026-11-19-tN-wI`) so the persistent
prefix cache cannot serve it back. Turn size **calibrated from the engine's own tokenizer**, not assumed: a
200-word probe came back at **3,510 prompt tokens → 15.95 tok/word**, so a ~20 k-token turn is **1,253 words**.

**Tenancy:** 22 status samples; 9 in-flight samples attributed to this run; **one foreign sample** (178,359 tok,
`spill/decode`) at `02:24:58`, the window's first sample, i.e. the operator's last message during the 90 s
lead-in. Zero co-tenant traffic inside the turns.

## The run

| turn | prompt tokens (engine-reported) | × resident budget | wall s | `prefill_rows` Δ | `spill_moves` Δ | susp Δ | demote Δ |
|---|---|---|---|---|---|---|---|
| 1 | 26,222 | 0.17× | 6.42 | 26,244 | 0 | 0 | 0 |
| 2 | 48,944 | 0.31× | 6.73 | 22,736 | 0 | 0 | 0 |
| 3 | 71,666 | 0.46× | 6.94 | 22,738 | 0 | 0 | 0 |
| 4 | 94,388 | 0.61× | 7.14 | 22,740 | 0 | 0 | 0 |
| 5 | 117,110 | 0.75× | 7.01 | 22,742 | 0 | 0 | 0 |
| 6 | 139,832 | 0.90× | 7.21 | 22,744 | 0 | 0 | 0 |
| **7** | **162,554** | **1.04×** | 7.35 | 22,746 | **+2,176** | 0 | 0 |
| 8 | 185,276 | 1.19× | 7.36 | 22,748 | +798 | 0 | 0 |
| 9 | 207,998 | 1.34× | 7.77 | 22,750 | +512 | 0 | 0 |
| 10 | 231,973 | 1.49× | 8.35 | 24,005 | +709 | 0 | 0 |
| **11** | **255,948** | **1.64×** | 8.61 | 23,980 | +750 | 0 | 0 |
| 12 | — | — | — | **0** | 0 | 0 | 0 |

Turn 12 was **refused before admission**: `HTTP 400` / `context_length_exceeded` /
`"prompt exceeds the context window"`, with `prefill_rows` unmoved — the check is in front of the engine, not
inside it. Totals: **256,173 prefill rows**, **4,945 spill moves**, `resource_suspensions` **0**,
`priority_suspensions` **0**, `disk.kv_demotions` **0**, `kv_demotions_refused` **0**,
`capacity_failures` **0**.

## What it establishes

1. **The depth wall is the context window (262,144), not the KV pool.** A single held context reached
   **255,948 tokens = 1.64× the 155,648-token resident budget** and was served normally. Resident KV is **not**
   the ceiling for one conversation; the model's context window is. Any claim of the form "the KV budget caps
   session length on this box" is wrong for this build.
2. **Spill switches on exactly at the resident line, and nothing else does.** Turns 1–6 (0.17× → 0.90×): spill
   **0**. From turn 7 (**1.04×**) onward: **+2,176 / +798 / +512 / +709 / +750**. Across the whole probe,
   `resource_suspensions`, `priority_suspensions`, `disk.kv_demotions` and `capacity_failures` never moved. Depth
   past residency is answered by **in-memory spill**, not by suspension and not by disk demotion — the same
   governor behaviour 19-ext saw under volume, now pinned to the crossing point.
3. **A deep session is cheap per turn, because only the new turn is prefilled.** Every turn after the first added
   ~**22.7 k** `prefill_rows` while the context grew to 256 k, and wall time went **6.42 s → 8.61 s** across a
   9.8× context increase (+34 %). Per-turn cost tracks the **new** tokens, so the persistent prefix cache is doing
   the cross-turn reuse; `kv.pages_cache` climbed 5,718 → 7,998 pages along the way (above the 4,864-page resident
   KV capacity — the cache pool is not the resident pool).
4. **Host headroom was thin the whole time and the KV path never used it.** `memory_governor.headroom_bytes`
   stayed between **10 MB and 79 MB** across all eleven served turns (weights are pinned by
   `--max-memory=60129542144`). So the near-full host was *not* what forced spill — the resident-line crossing was,
   which is why the spill onset tracks turn 7 rather than the headroom dips.
5. **Refusal is a pre-admission input check, so it is free.** Turn 12 moved no engine counters at all. Contrast
   the 19-ext 503 at `--queue-size` (a *capacity* refusal) — this 400 is a request-validation refusal. Two
   different failure modes, distinguishable by whether `prefill_rows` moved.

## Limits

- n = 1 conversation, one day, one engine instance (11 turns served). The spill-onset step is one observation
  at the crossing; the step location between turn 6 (0.90×) and turn 7 (1.04×) is bounded to that interval, not
  resolved inside it.
- `pages_active` read **0** at every sample: each turn completes in ~7 s and sampling runs at 10 s, so the
  in-flight residency was not caught in a sample. `spill_moves` deltas are the residency evidence here; a rerun
  that wants the occupancy curve should sample at 1–2 s.
- `spill_moves` units are the engine's own counter; this record reports movement, not bytes.
- The conversation is synthetic filler text. It has the shape (held context, growing) but not the retrieval
  behaviour of a real agent session; a real `opencode` session's request sizes would also change the picture.
- **Not comparable to volume waves.** Same launch as 19b/19c (not restarted), but the axis and prompt sizes
  differ; nothing here bears on throughput numbers.

## Files

`depth_probe.jsonl` (setup row, 12 turn rows, summary row), `run.out`, `run.err` (empty), `run.log`,
`engine_samples.jsonl`, `status_before.json` / `status_after.json`, `pins.txt`. Local absolute paths scrubbed
to `~`.
