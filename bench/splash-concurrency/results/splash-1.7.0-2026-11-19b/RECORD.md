# splash-1.7.0-2026-11-19b — the queue-size 64 stack move, run past the old ceiling

**Instrument:** `kv_bracket_2026-11-19b.py` (benchmarks `6f97678` + `5b37d51`).
**Run window:** 11:36:40 → 12:40:38 local, one invocation, three stages.
**Engine:** Splash **1.7.0**, **restarted for this wave at 11:34** so the stack move could bind —
`start.sh` added `--queue-size 64` (resolve-ai-workflow `81a9235`) the same morning, and every flag
here is read from the live supervisor (`pgrep -f -fl server.server`), not from disk. Full pin set in
`engine_config.json`: `--max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache
--default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64`.
**Path placeholders:** absolute local paths in `engine_config.json` were replaced with `~`; nothing
else edited.

Because the restart was required, this instance began with **every lifetime counter at zero**
(`resource_suspensions` 0, `priority_suspensions` 0, `capacity_failures` 0,
`kv_demotions_refused` 0, `spill_moves` 0). That makes the per-round deltas below the cleanest in the
series — but it also means the lifetime column is **not comparable across rows**: 11-18 quoted a
pre-existing 43 and 19-ext a pre-existing 45. A zero here is a fresh instance, not a drop.

## Stage 0 — warmth gate on the ladder's own primitive (soft, disclosed)

decode w1 on `LADDER_PROMPT` @512 = **272.0 / 282.1 / 309.6 tok/s**, spread **1.138 → gate "soft"**
(pass ≤1.10, soft ≤1.20, cold >1.20). This is the gate fixed after 19-ext's invalid one: the morning
gate probed a prose paragraph (77–117 tok/s) while the ladder's own w1 read 294.4, so it certified
nothing. Same primitive as the baseline here, and the result is in family with both prior waves
(19-ext ladder w1 294.4; 11-18 w1 rounds 260.6 / 307.3). **Soft, not a clean pass** — and the ladder
that follows it lands inside that band, so it licenses the ladder rows without being a clean pass.

## Stage 1 — sealed width ladder: queue-size 64 did not perturb the curve

Widths and spec unchanged from the sealed ladder (512-token outputs, 2 rounds/width).

| width | 1 | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 24 | 32 |
|---|---|---|---|---|---|---|---|---|---|---|
| median tok/s | 307.1 | 416.95 | 581.25 | **724.6** | 613.3 | 698.9 | 647.55 | 700.65 | 698.0 | 699.5 |
| round spread | 1.011 | **1.377** | 1.020 | 1.045 | 1.000 | 1.014 | **1.139** | 1.019 | 1.003 | 1.001 |
| peak admission.waiting | 0 | 0 | 0 | 0 | 2 | 4 | 9 | 12 | 12 | 12 |
| peak scheduler.queued | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 8 | 16 |
| peak suspended | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**Stop rule never fired.** `w1 = 307.1` is the **best width-1 on record** (prior 283.95 at 11-18,
+8.2 %; 19-ext's 294.4 minutes earlier the same day). `w4 724.6` is the **highest aggregate peak on
record** (prior best 19-ext w4 697.5, 11-18 peak w16 698.6). Plateau w8–32 = 647.55–700.65, and the
**w6 dip reproduces** at 613.3 = **0.846× of w4** (19-ext 0.884×, 11-18 0.904×).

Two cells carry round-level scatter and are labelled rather than smoothed: **w2** (350.8 vs 483.1,
1.377×) and **w12** (689.6 vs 605.5, 1.139×). Both stay far above their w1, so neither threatens the
stop rule or the shape; they sit in the same lane as 11-18's w1 pair (260.6 / 307.3, 1.18×).

## Stage 2 — KV in the queueing regime: 48 in flight, zero refusals

Calibration: 300 lines = 14,087 prompt tokens → **425 lines/request** (~55,265 tokens each). Widths
12 → 33 → 36 → 40 → 44 → 48, i.e. **past the 32-request wall that killed 19-ext at w40**, and capped
deliberately at 48 so 16 lanes stay in slack under queue-size 64 — a refusal here would mean the
engine's limit, not our own saturation.

| width | prompt tokens | × budget | wall (s) | ok / refused | prefill_rows Δ | cache-served | pages_active peak | susp / wait_mem | spill Δ / demote Δ |
|---|---|---|---|---|---|---|---|---|---|
| 12 | 663,180 | 4.26× | 189.5 | 12 / **0** | 663,180 | no | 1,920 | 0 / 0 | 0 / 0 |
| 33 | 1,823,745 | 11.72× | 522.2 | 33 / **0** | 1,823,745 | no | 1,920 | 0 / 0 | 0 / 0 |
| 36 | 1,989,540 | 12.78× | 570.5 | 36 / **0** | 1,989,540 | no | 1,920 | 0 / 0 | 0 / 0 |
| 40 | 2,210,600 | 14.20× | 633.2 | 40 / **0** | 2,210,600 | no | 1,920 | 0 / 0 | 0 / 0 |
| 44 | 2,431,660 | 15.62× | 697.7 | 44 / **0** | 2,431,660 | no | 1,920 | 0 / 0 | 0 / 0 |
| 48 | 2,652,720 | **17.04×** | 760.1 | 48 / **0** | 2,652,720 | no | 1,920 | 0 / 0 | 0 / 0 |

Budget = 155,648 resident KV tokens (4,864 pages × 32). **No trip at any width**: the revised stop
rule (refusal, `admission.suspended` > 0, a lifetime suspension-counter delta, `kv_demotions_refused`
delta, `capacity_failures` delta) never fired. Lifetime at run end: suspensions 0, priority 0,
`capacity_failures` 0, `spill_moves` 0.

## Findings

**1. The 32-request wall was exactly the flag, and `--queue-size 64` removes it.** 19-ext refused
instantly at w33 (`frontend_overloaded`, `waiting_concurrency=0`, `held_behind_refusal=0`). Here **48
concurrent 55k-token requests were all admitted with zero refusals**. The ceiling was never memory,
never KV, never compute admission: it was a documented request-count default.

**2. But the engine does not answer the extra width with admission-level queueing — and that is the
surprise.** The prediction was that past 32, `admission.waiting` and `waiting_memory` would finally
have something to measure. On every one of the six rounds, `admission.waiting`,
`waiting_memory`, `waiting_concurrency` and `held_behind_refusal` peaked at **0**. Requests past the
concurrency limit are not held at the gate at all — they are admitted into lanes and wait inside the
**scheduler's prefill queue** (`peak_queued` 8–16 in the ladder stage shows that queue existing). So
the gauge this stack uses to express "too much work" is *queue depth and wall time*, not admission
holds. Reading `admission.*` alone would report an idle engine at w48.

**3. The cost of width past 32 is wall time, paid in full, at prefill parity.** Prefill held
**3,485.4–3,499.1 tok/s (±0.2 %)** from w12 to w48 — the same flat line 19-ext measured at 3,513.7–
3,520.7 across w16–w32. Wall is tokens ÷ ~3,490, so 189.5 s at w12 became **760.1 s at w48**: width
buys nothing but latency. `memory_plan.budget.maximum_batch_width = 4` is the mechanism, corroborated
in the session's own scheduler counters (decode batches b1 4,375 / b2 278 / b3 244 / **b4 3,434**).

**4. KV residency stays untouched at 17× the budget, and the governor is never consulted.**
`kv.pages_active` pinned at **1,920 pages = 61,440 tokens (39.5 % of budget)** on every round — it
rose from 1,654 pages (52,928 tokens) once in-flight passed 32, then stopped moving, while summed
contexts reached 2.65 M tokens. Across the whole KV stage: **spill 0, demote 0, suspensions 0**,
minimum governor headroom 207.8 MB. The standing conclusion from 11-06 survives its widest test:
fire-and-forget long-context volume does not trip this stack's KV; the memory path engages on *held*
contexts (the 11-16b trip at 3.89× came from a loaded engine, and never reproduced from a fresh one).

**5. The cache confound is closed, and proven closed.** All six rounds ran in a fresh seed namespace
(900,000 + width×100 + i) and **`scheduler.prefill_rows` delta equalled prompt tokens exactly** on
every round (663,180 = 663,180 … 2,652,720 = 2,652,720). `cache_served_rounds = []`. Against 19-ext,
where the byte-identical control rounds moved 26 and 84 prefill rows for 93,530 and 612,180 tokens —
those rows proved the persistent cache works and measured no pressure at all.

**6. One memory-path signal appeared outside the KV stage, and it is attributed by delta, not by the
lifetime counter.** At run end the engine reports lifetime `disk.kv_demotions` **421** with
`kv_demotions_refused` **5**, while every KV round's delta for both was **0**. So those demotions —
and the 5 refusals — came from the gate/ladder/calibration legs, not from the KV probe. The stop rule
reads per-round deltas precisely so a lifetime counter that drifts outside the stage (11-18: 43
before the stage began) cannot be mistaken for a trip.

## Tenancy — stated, not hedged

This was **not** a clean-window wave. The operator's OpenCode session is served by this same engine
and **took turns during the run**, including inside the KV rounds. Per the standing 11-13 finding,
that tax falls on latency-bound cells (w1, TTFT) rather than saturated-decode aggregates, so the
ladder plateau and the KV gauge peaks carry it lightly and the w1 figure carries it most — which cuts
*against* the "best w1 on record" claim being a pure stack-move read. A detached single-tenant re-run
of stage 1 would settle that; it has not been done.

## What this instrument can no longer answer, and what's next

The summed-KV question is **bounded out**: at 17.04× the resident budget the governor still reports
zero work, and the only remaining failure mode at higher widths is the request-count flag. The live
KV question is now **depth, not volume** — `context_bounds` says resident 155,633 / window 262,144,
and the open probe is a single context walking toward the resident line while it is *held* across
turns, which is what real agent sessions do and no wave here has yet measured directly.
