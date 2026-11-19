# splash-1.7.0-2026-11-19-ext — KV trip-point extension (ladder valid, KV censored then diagnosed)

**Instrument:** `ladder_kv_ext_2026-11-19.py` (benchmarks `eafc9c1`), superseded same day by
`kv_bracket_2026-11-19b.py` (`6f97678`).
**Engine:** Splash 1.7.0, same process as the 2026-11-18 run — **not restarted**. Supervisor args
recorded in `engine_config.json`: `--max-memory=60129542144 --max-cache-disk=274877906944
--persistent-cache --default-reasoning-effort=medium --thinking-token-budget=16384`, no
`--queue-size` (so the splash default of 32 governed — see Finding 1).
**Why 16384 rather than 32768:** the host `start.sh` raised the thinking budget to 32,768 on
2026-11-19, but this engine predates that and keeping the sealed args intact keeps the series
comparable. It is also structurally inert here: ladder completions are pinned at 512 tokens and KV
completions at 8, so neither stage can exercise a thinking cap.
**Path placeholders:** absolute local paths in `engine_config.json`, `run.log` and `run.err` were
replaced with `~` for publication. Nothing else was edited.

## Stage 0 — warmth gate (flawed, disclosed in full)

decode w1 = **77.3 / 88.6 / 116.7 tok/s**, spread ratio **1.51 → gate "cold"**;
TTFT cold **209 ms** vs warm-prefix **95 ms**.

The gate is **not** a valid certification of the ladder baseline: it probed a prose paragraph
prompt, while the ladder's own w1 measured **294.4 tok/s** minutes later. A gate must use the same
primitive as the baseline it certifies. Recorded anyway, because "the gate said cold and the ladder
was fine" is the honest description of this run. Fixed in 19b (`LADDER_PROMPT`, 512 tokens).

## Stage 1 — width ladder: valid, and it reproduces 2026-11-18

| width | 1 | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 24 | 32 |
|---|---|---|---|---|---|---|---|---|---|---|
| median tok/s | 294.4 | 485.3 | 585.6 | 697.5 | 617.0 | 693.7 | 696.9 | 701.1 | 695.2 | 701.5 |

Shape and level match 11-18 (plateau 692–699, w1 260.6/307.3, best-ever w1 283.95): **no ×1.4
instance shift today**, so this run's KV numbers are read against a same-state ladder. Stop rule
(< 1.10× w1) never fired; all ten sealed widths ran, 2 rounds each.

## Stage 2 — KV pressure

Per-request calibration identical to the sealed stage (300 lines = 14,087 prompt tokens →
425 lines/request, ~51k tokens in practice).

| w | prompt tokens | wall | prefill tok/s | ×155,648 budget | pages_active peak | suspended | spill+ | demote+ |
|---|---|---|---|---|---|---|---|---|
| 2 | 93,530 | **0.4 s** | — | 0.60 | 0 | 0 | 0 | 0 |
| 12 | 612,180 | **1.5 s** | — | 3.93 | 3,190 | 0 | 0 | 1 |
| 16 | 816,240 | 232.3 s | 3,513.7 | 5.24 | 1,654 | 0 | 0 | 0 |
| 20 | 1,020,300 | 289.8 s | 3,520.7 | 6.56 | 1,654 | 0 | 0 | 0 |
| 24 | 1,224,360 | 348.1 s | 3,517.0 | 7.87 | 1,654 | 0 | 0 | 0 |
| 28 | 1,428,420 | 406.0 s | 3,518.3 | 9.18 | 1,654 | 0 | 0 | 0 |
| 32 | 1,632,480 | 464.1 s | 3,517.5 | 10.49 | 1,654 | 0 | 0 | 0 |
| 40 | — | — | — | — | — | — | — | **driver died: HTTP 503** |

**No suspension anywhere.** Lifetime `resource_suspensions` was **45 at start and 45 at end**
(11-18 recorded 43, so the counter drifts outside our runs — per-round deltas remain the binding
signal). The run ended uncaught at w40; `run.err` holds the traceback, and the intended w40–w64
widths are simply missing.

## Finding 1 — the trip point exists, and it is a request-count ceiling, not KV

Follow-up probe (same day, tiny prompts so token volume cannot matter; 1.4–1.5 s per round):

```
w31: OK=31 refused=0     w33: OK=32 refused=1
w32: OK=32 refused=0     w34: OK=32 refused=2
w40: 32 OK / 8 refused   w64: 32 OK / 32 refused   w96: 32 OK / 64 refused
refusal body: {"error":{"message":"frontend request capacity is exhausted",
                        "type":"server_error","code":"frontend_overloaded"}}
```

Exactly **32 in-flight requests**, refused instantly with `admission.waiting_concurrency=0` and
`held_behind_refusal=0` — refused, never queued. `splash serve --help` documents it:
`--queue-size REQUESTS … requests admitted at once, running or waiting; more get 503 (default: 32)`.

## Finding 2 — this stack answers KV pressure with spill/demote, not suspension

Within 32 streams, `kv.pages_active` sat pinned at **1,654 pages = 52,928 tokens** (32 tokens/page)
for every fresh round from w16 through w32 — 34 % of the 155,648-token resident budget — while
lifetime `kv_spill.spill_moves` reached 28,138 and `disk.kv_demotions` 4,390 with **41 demotions
refused**. So the standing stop rule (`admission.suspended > 0` or a suspension-counter delta) is
watching a gauge this stack does not move. Revised in 19b to refusals, `kv_demotions_refused`,
`capacity_failures`, and spill/demote deltas.

## Finding 3 — beyond w12, width buys nothing

Prefill held at **3,513.7–3,520.7 tok/s (±0.2 %)** from w16 to w32; wall time is tokens ÷ ~3,517.
The mechanism is visible in `/status`: `memory_plan.budget.maximum_batch_width = 4`, corroborated by
`decode_batches_by_width` b4 = 6,986 — which is also what caps the ladder plateau near 700 tok/s.

## Finding 4 — cross-run prompt reuse is free, so controls must be fresh-seeded

The w2 and w12 "stitch controls" were byte-identical to the 11-18 prompts (the generator is
deterministic), and `--persistent-cache` + 256 G cache disk served them from disk: 93,530 tokens in
0.4 s and 612,180 in 1.5 s, with `scheduler.prefill_rows` moving only 26 and 84 — versus the fresh
rounds, where `prefill_rows` equals prompt tokens exactly. **Those two rows prove the cache works;
they measure no KV pressure at all.** 19b seeds a fresh namespace and marks any round
`cache_served` when `prefill_rows < 0.5 × prompt_tokens`.

## Censorship status

2026-11-18's "no trip at 3.93× budget" was doubly censored: the stage's width cap (12) sat below the
real ceiling, and the real ceiling is an admission refusal rather than a suspension. This run
extends the admitted range to **1,632,480 prompt tokens (10.49× budget)** at w32 and shows what
happens past it. The genuine KV-residency question is now out of scope for this instrument and
moves to context-depth probes (toward `context_bounds`: resident 155,633 / window 262,144) on the
queue-size 64 stack.

## Followed by

Stack move: `--queue-size 64` in `start.sh` (resolve-ai-workflow `81a9235`), taking effect at the
next engine launch, and `kv_bracket_2026-11-19b.py` to run the KV stage in the queueing regime.
