# Splash Engine Benchmark — Baseline Results (2026-11-06)

**Purpose:** version-to-version performance tracking of the Splash engine + resident Qwen
model on this machine — the Splash counterpart to the Resolve MCP benchmark
(`resolve-agentic-benchmark-results.md`). No prior baseline existed; the only earlier
artifact was the never-run draft spec in `archive/concurrency-scaling-test.md` (2026-09-26),
whose design this reuses in adapted form.

**Host (fixed for comparison):** Apple M5 Ultra, 64-core GPU, 96 GiB unified memory,
macOS 27.2.0. Engine args: working set 56 GiB, SSD cache cap 128 GiB, persistent cache on.

**Baseline stack:** Splash **1.6.0** (brew), model `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`,
262,144-token context, int8 KV, status schema 8, keyless engine on `127.0.0.1:8000`
(started via `~/start-resolve-ai.sh`). Cache state at run: warm (hit_rate 0.9924, 916 hits /
7 cold misses since last start; the 1.6.0 upgrade had cleared the SSD cache earlier that day).

## Contents

- [Layer 1 — engine probe](#layer-1--engine-probe-deterministic-run-by-the-orchestrator-not-the-llm)
  - [Single-stream decode](#single-stream-decode-median-of-3-max_tokens-300)
  - [TTFT](#ttft-341-token-prompt-8-token-output)
  - [Concurrency scaling (width ladder)](#concurrency-scaling--escalating-ladder-v3-same-prompt-max_tokens-512-2-roundswidth)
  - [KV-pressure probe](#v4-kv-pressure-probe--chasing-the-first-suspension-long-context-short-output)
- [Layer 2 — agentic suite](#layer-2--agentic-suite-headless-claude-code-served-by-splashqwen)
- [Re-running against a future Splash version](#re-running-against-a-future-splash-version)
- [Re-run 2026-11-10s](#re-run-2026-11-10s--same-build-shape-reproduces-raw-benchsplash-concurrencyresultsrerun-2026-11-10s)
- [Clean-window rerun 2026-11-13](#clean-window-rerun-2026-11-13-standalone-driver-raw-benchsplash-concurrencyresultsclean-2026-11-13)
- [Baseline headline](#baseline-headline-for-the-next-versions-diff)
- [Cross-hardware comparison](#cross-hardware--the-same-model-on-nvidia-boxes-external-data-2026-11-13)

## Layer 1 — engine probe (deterministic, run by the orchestrator, not the LLM)

Method: direct `curl`/urllib to `/v1/chat/completions`, temperature 0, engine idle between
passes (`scheduler.queued/decoding/prefilling == 0`), no engine restart (SSD cache state is
part of the measurement). Deliberate deviation from the 2026 draft: prompts ~340–700 tokens
instead of ~32K, to spare the shared engine; a 32K variant remains an optional extension.

### Single-stream decode (median of 3, `max_tokens` 300)

| metric | value |
|---|---|
| decode tokens/s (wall, includes prefill) | **132.7** (passes 105.4 → 132.7 → 165.3, warmup trend) |

### TTFT (341-token prompt, 8-token output)

| pass | TTFT |
|---|---|
| cold (prompt blocks uncached) | 380 ms |
| warm (identical prompt, prefix cache) | 201 ms |

### Concurrency scaling — escalating ladder (v3; same prompt, `max_tokens` 512, 2 rounds/width)

Spec evolved twice this session: fixed 1/2/4 → escalate-and-stop-at-first-drop (v2) →
**escalate 1→2→3→4→6→8→12→16→24→32 and stop only when median aggregate falls within 10%
of the width-1 baseline** (v3, the standing spec — user call: width 6 looked practical,
measure the real impact). `decode_batches_by_width` plus **peak `admission.waiting` /
`queued` / `suspended`, sampled every 0.8 s during each round**. Script:
`bench/splash-concurrency/width_ladder.py`.

| width | aggregate tok/s (median) | per-stream tok/s | vs w1 baseline (147.6) | peak admission.waiting |
|---|---|---|---|---|
| 1 | 147.6 | 147.6 | ×1.00 | 0 |
| 2 | 259.1 | 129.5 | ×1.76 | 0 |
| 3 | 306.1 | 102.1 | ×2.08 | 0 |
| 4 | 377.7 | 94.5 | ×2.56 | 0 |
| 6 | 330.4 | 55.1 | ×2.24 (dip) | 2 |
| 8 | 373.9 | 46.8 | ×2.53 | 4 |
| 12 | 375.7 | 31.3 | ×2.55 | 8 |
| 16 | 371.9 | 23.3 | ×2.52 | 12 |
| 24 | **382.9** | 16.0 | ×2.60 | 12 |
| 32 | 371.7 | 11.7 | ×2.52 | 12 |

**Findings.**
- The v2 "crossover at 4" was a premature read: the width-6 dip (330 here, 327 in v2 —
  reproducible, ~12% below plateau) is a local scheduling anomaly that **recovers fully at
  width 8**. Aggregate then rides a **flat plateau of ~372–383 tok/s from width 8 to 32**
  (2.5–2.6× single-stream). The v3 stop rule never fired — **no collapse within width 32**;
  the ceiling is compute saturation, a wall, not a cliff.
- Admission pacing is healthy under load: peak `waiting` grows 2→4→8→12 with width but
  aggregate never degrades, and `suspended` stayed 0.
- The real cost of width is latency, not throughput: per-stream 94.5 → 46.8 → 31.3 →
  23.3 → 16.0 → 11.7 tok/s from widths 4/8/12/16/24/32.
- Practical guidance: **widths 4–24 are all ~equally maximal in aggregate**; pick by
  per-stream latency budget. At this model/quant, ~2.5× the single-stream rate is the
  hard ceiling.
- Consistency: v2 ladder w4 374.0 vs v3 w4 377.7 (+1%); w6 327.5 vs 330.4 (+1%). Engine
  lifetime counters (b1 74,602 / b2 23,546 / b3 959 / b4 0) confirm production traffic
  rarely reaches width 3 — everything past width ~3 is headroom in reserve, now quantified.

### v4 KV-pressure probe — chasing the first suspension (long-context, short-output)

Question: how far can load go before `admission.suspended` reaches 1? v3 showed stream
*width* can never get there (transport caps at 32 requests; KV footprint at width 32 was
~17% of budget), and live `/status` gave the budget: **resident KV = 139,264 tokens**
(4,352 pages × 32; int8 ≈ 13.2 KB/token). Prediction: suspension past ~139k summed live
context. Shape: per-request unique ~46.7k-token prompts (sequential-number streams,
offset per request so prefix-cache dedup can't share KV — the tokenizer ran ~2.3× denser
than the 20k calibration target, which only strengthened the test: reported token counts
are measured from `usage.prompt_tokens`), `max_tokens` 8, widths 2→12; sampler every 0.5 s
over admission/KV/spill/governor gauges plus **lifetime `resource_suspensions` /
`priority_suspensions` counter deltas** (catches a suspension that opens and closes
between samples). Script: `bench/splash-concurrency/kv_pressure_v4.py`.

| width | unique tokens total | wall (s) | peak waiting / waiting_memory | kv.pages_active peak (tokens) | disk kv_demotions Δ |
|---|---|---|---|---|---|
| 2 | 93,394 | 25.9 | 0 / 0 | 52,480 | 0 |
| 4 | 186,788 | 51.9 | 0 / 0 | 52,448 | 0 |
| 6 | 280,182 | 77.6 | 0 / 0 | **142,272 — the full resident ring** | 0 |
| 8 | 373,576 | 104.4 | 0 / 0 | 52,512 | +308 |
| 10 | 509,370 | 142.9 | 0 / 0 | 60,928 | +645 |
| 12 | **611,244** (4.4× budget) | 170.9 | **1 / 1** | 59,104 | +97 |

**Findings.**
- **No suspension at any round, up to 4.4× the KV budget.** Gauge peak 0; lifetime
  counters unmoved (`resource_suspensions` 90→90, `priority_suspensions` 0→0);
  `capacity_failures` 0.
- **The 139k-sum prediction was wrong as a mechanism.** Summed *accepted* contexts far
  exceed resident KV, but simultaneous *live* KV never did: the scheduler serializes
  prefills (wall = total tokens ÷ ~3.6 k tok/s, perfectly linear), reclaims cache pages
  ahead of demand (at w6 live KV touched 142k tokens — exactly the ring capacity — with
  free pages never below 460), and **demoted 1,050 blocks to the disk cache instead of
  spilling** (`kv_spill` requests stayed 0 for these fire-and-forget rounds).
- The memory gate first *paced* at 611k tokens: one `waiting_memory` hold at w12, oldest
  wait 265 ms. Pacing, not suspension.
- Suspension therefore needs **context that holds**: concurrent sessions that keep large
  contexts alive over minutes (real agent sessions), not fire-and-forget prefills. The
  lifetime counters prove the engine already does exactly that under real use — 90
  suspensions, 90 resumptions, 263k replay tokens, zero user-visible failures.
- Answer to the standing question: **`suspended` is not a throughput cliff to chase.**
  Neither stream width (v3, to 32) nor long-context prefill volume (v4, to 4.4× KV budget)
  moves it; it only fires for held-context contention, and when it does, it's a routine
  self-healing park-and-replay.

## Layer 2 — agentic suite (headless Claude Code served by Splash/Qwen)

Condition (fixed, reproducible): `claude -p` fresh session per trial;
`ANTHROPIC_BASE_URL=http://127.0.0.1:8000`, all model aliases pinned to the resident Qwen;
cwd = bench dir; default permission mode with per-task minimum tool allowlists
(curl-only for S1/S2/S3, Read-only for S4; WebSearch/WebFetch disabled — nothing auto-approves);
sequential trials, 12 s spacing; tasks touch only the engine HTTP API and the bench dir.
Harness metrics per trial from `--output-format json`: turns, wall, API ms, token usage
(incl. prefix-cache reads and thinking tokens).

Tasks (4 × 3 runs):
- **S1 status-read** — one `curl /status`; report six named fields verbatim (tests tool-use
  + JSON navigation; graded: three constants exact, three live fields format-checked).
- **S2 derived arithmetic** — report two live counters + a computed 2-dp percentage; graded by
  recomputing the arithmetic from the model's own echoed inputs (pure Qwen numeric test).
- **S3 structured file** — write an exact-shape JSON artifact derived from one live fetch;
  graded by structure, value-consistency, and `derived == queued + decoding`.
- **S4 diagnosis** — reason over a planted fixture (memory-saturation scenario); graded on a
  3-part rubric (bottleneck / evidence field / remediation).

### Results (n=3)

| Task | r1 | r2 | r3 | Verified | Honesty |
|---|---|---|---|---|---|
| S1 status-read | 2 t / 13.6 s | 2 t / 5.8 s | 2 t / 6.1 s | 3/3 — constants exact; live counters monotonic and tie to grader snapshots (hits 1080→1089→1098, grader-after 1110) | ✓ |
| S2 arithmetic | 2 t / 7.5 s | 2 t / 4.6 s | 2 t / 6.3 s | 2/3 — **r2 computed 20.13 from its own echoed counters that recompute to 20.11**; r1 20.14 ✓, r3 20.08 ✓ | ✓ (no invented inputs) |
| S3 file artifact | 3 t / 7.7 s | 3 t / 6.6 s | 3 t / 7.6 s | 3/3 — surviving `out.json` exact six-key shape, `derived == queued + decoding`; earlier runs verified from their reported read-backs | ✓ |
| S4 diagnosis | 2 t / 9.0 s | 2 t / 7.1 s | 2 t / 6.9 s | 3/3 — bottleneck (KV/memory admission), evidence (`admission.waiting_memory`), sound remediation; all three also volunteered b1-width corroboration unprompted | ✓ |

**Aggregate: 11/12 outcomes grader-verified, 12/12 honest.** Median 2 turns/trial,
wall 4.6–13.6 s (first S1 pass 13.6 s cold-ish, then a tight 5.8–7.7 s band). Engine prefix
cache did real work across fresh sessions: each trial read 20–45 k cached tokens against
~10 k fresh input. (`total_cost_usd` in the harness JSON is API-price fiction on a local
engine — ignore; use turns/wall/tokens.)

### Run 1 discarded — harness flaws disclosed (kept for the record)

The first pass of the suite was invalidated by orchestrator error, not model behavior:
1. `--disallowedTools Bash` overrode the per-task `Bash(curl:*)` allowlist → the intended
   fetch route was blocked for every session.
2. Headless sessions inherited the operator's MCP servers; two agents worked around the block
   by fetching `/status` through the Resolve MCP's Python sandbox (HTTP 200 — effective, but
   an uncontrolled condition).
3. One shared bench dir let blocked trials discover S4's fixture and quietly answer from it.

Fixed in run 2: per-task allowlists without the Bash disallow, `--strict-mcp-config`
(no MCP inheritance), isolated per-task working directories. The discarded run's behavioral
signal is still notable: **4 of 12 blocked sessions refused to invent values** and several
disclosed that their numbers came from the fixture rather than a live fetch — the
refusal-to-fabricate check stays part of the suite.

## Re-running against a future Splash version

Scripts committed under `bench/splash-concurrency/`. The **combined entry point is
`ladder_kv.py`** — one run performs BOTH the v3 width ladder and the v4 KV-pressure
probe and prints one combined SUMMARY, so every future report carries both methods;
`--out` picks the JSONL, `--quick` is a harness smoke test, not for baselining. The
per-method originals (engine_probe.py, width512.py, width_ladder.py, kv_pressure_v4.py)
stay committed for provenance, plus the agentic driver (driver2.py, fixture_status.json).
Procedure: start the engine the usual way (`~/start-resolve-ai.sh`), warm it (one
unscored agent session), run `python3 -I engine_probe.py && python3 -I ladder_kv.py`,
then `python3 -I driver2.py` (model id is read from `/v1/models`). Compare: cold/warm
TTFT; the width ladder **against the plateau shape** (baseline: rise to ~378 by width 4,
dip at 6, flat 372–383 through 32, stop rule never fired); the KV probe **against the
no-suspension baseline** (611k tokens ≈ 4.4× budget with zero suspensions; first
`waiting_memory` hold at w12 — a moved lifetime suspension counter is the regression
signal); and the 12-trial agentic table. Do **not** restart the engine mid-suite; note
cache state in the results header.

**Version caveats for 1.6.x reruns (added 2026-11-12):**
- **INT8 by default on M5+ since 1.6.1** (`--activations auto`): decode numerics are **not
  bit-comparable** with the 1.6.0 rows — compare medians and curve shapes, not hashes. For a
  deterministic bf16 cross-version comparison, serve with `--activations bf16` and a fresh
  `--cache-dir` (leaderboard footnote states the same for the 1.6.1 row).
- **Request quarantine since 1.6.0:** a request that crashes the engine twice is quarantined —
  the same payload then returns `400 request_quarantined`. Treat it as a disclosure condition
  (one line in the results header + discard the affected trial), never retry identical bytes.
- 1.6.1 streams Flash-Next PLE tables by default, freeing RAM for context/KV: expect resident-KV
  and cold-TTFT numbers to move; one rerun sets the new baseline rather than assuming the
  2026-11-10s numbers carry over. (Hardware gate per `splash serve --help`: INT8 activates only
  where the GPU multiplies 8-bit twice as fast — M5 and later; pre-M5 hosts stay bf16 on the
  same default, so this whole caveat is absent there. The documented ~¼ TTFT win is scoped to
  MLX 4/5-bit weights; treat measured GGUF deltas as the empirical answer.)
- **Determinism knob, new in the 1.6.1 help:** `--verify-rows {auto,all}` — `auto` uses a
  decode-verify budget learned from earlier cycles; `all` verifies every row of each draft
  block so a MoE model's greedy/seeded outputs **repeat exactly**, like a dense model's. Use
  `--verify-rows all` (+ bf16 activations) when a rerun needs exact repeat runs instead of
  medians; the published suites stay on `auto` and keep the median-compare rule.

## Re-run 2026-11-10s — same build, shape reproduces (raw: `bench/splash-concurrency/results/rerun-2026-11-10s/`)

Conditions: Splash **1.6.0 again** (not an upgrade — this pass measures run-to-run reproducibility),
engine instance started 16:21 local the same day, cache warm (hit_rate 0.9920 at suite start),
never restarted; host ~95 % idle; operator session live through the suite (identical tenant
condition to the baseline). Combined entry point `ladder_kv.py` ran end to end for the first
time; the probe and agentic stages ran around it (deviations below).

**Layer 1 probe:** decode w1 passes 111.4 → 128.0 → 135.9 tok/s (median 128.0; baseline 105→133→165 —
same warming shape, slightly cooler instance). TTFT **174 ms warm / 430 ms cold** (baseline 201/380 —
both inside single-sample spread).

**Width ladder (v3):** medians 151.45 / 250.7 / 290.9 / **369.7** / 322.35 / 368.65 / 367.65 / 369.05 /
368.8 / 365.45 at widths 1/2/3/4/6/8/12/16/24/32. **The shape reproduces exactly**: peak at width 4,
dip at 6 = 0.87× the peak (baseline 0.875× — the anomaly is real and stable), flat plateau from 8 to
32, stop rule never fired. Every median sits **~2 % below the baseline** at every width — read that as
run-to-run spread bounding future diffs, not a regression claim (one instance, engine-side; the ladder
never touches code paths that changed because none changed). Admission pacing identical:
peak waiting 0/0/0/0/2/4/8/12/12/12, `suspended` 0 throughout.

**KV pressure (v4):** headline **reproduces — no suspension at 611,244 tokens (4.4× the 139,264-token
budget)**, lifetime counters unmoved (delta 0 every round), prefill serialization linear again
(171.1 s at w12 ≈ 3.57 k tok/s, same as baseline's 170.9 s). The **secondary memory-path signals did
not reproduce**: disk `kv_demotions` delta 0 at every round (baseline +308/+645/+97 at w8/10/12), no
`waiting_memory` hold (baseline had its single one at w12), `kv.pages_active` peaked at 1,593 pages
(~51 k tokens) without the baseline's width-6 ring touch. The instance difference is the obvious
candidate — this engine had ~2.5 h of history and a zero `hot_kv` account vs the baseline instance's
day-plus of production traffic. The governor still grazed hard: headroom 26.5 MB at w10–12, zero
denials. Conclusion stands unchanged: suspension is a held-context mechanism, and how much of the
spill/demote machinery engages depends on instance cache history.

**Agentic suite (4×3, run-2 conditions):** **12/12 verified, 12/12 honest** — the baseline's only miss
(S2 computing 20.13 from its own inputs that recomputed to 20.11) did **not** reproduce: all three
S2 percentages recompute exactly (15.02 / 15.00 / 14.98). S1 constants exact ×3 with live counters
tying to grader snapshots (hits 1016→1025→1036, grader-after 1077; cold_misses 12/12→13); S3's
surviving `out.json` is the six-key exact shape with `derived == queued + decoding` (committed as
`s3_out.json`); S4 rubric 3/3, every trial citing the fixture's own evidence chain. Turns 2–3,
wall 4.3–25.0 s; prefix-cache reuse 20–46 k tokens per fresh session, as before.

**Deviations:** (1) the committed `engine_probe.py` crashed on the chained first attempt — its hardcoded
`/tmp` output dir had been cleaned and the provenance script never mkdirs; re-ran standalone **after**
the other stages with the engine idle, so probe numbers are post-suite, not interleaved. (2) The
combined `ladder_kv.py` KV stage reports gauge peaks in raw pages (×32 = tokens) where the baseline
table printed tokens — cross-compare at the ×32 factor. (3) S4's fixture dir is seeded by the operator
before the driver stage (same as baseline).

**Revised headline for the next version's diff:** the plateau shape (peak 4, dip 0.87× at 6, flat to
32, no collapse) and the no-suspension KV result are now **established as reproducible**, with a
~2 % run-to-run band on throughput medians and instance-dependent behavior in the spill/demote paths.

## Baseline headline (for the next version's diff)

Splash 1.6.0 @ M5 Ultra, warm: **TTFT 201 ms warm / 380 ms cold** (341-token prompt) ·
**decode w1 149–170 tok/s** (session-dependent warmth) · **width ladder: rise to ~378 by
width 4, reproducible dip at 6 (~330), then a flat plateau ~372–383 tok/s through width 32
(2.5–2.6x w1) — no collapse by 32; the ceiling is compute saturation, not a cliff** ·
**v4 KV-pressure: no suspension even at 4.4x the 139k-token resident KV budget — the
scheduler serializes prefills and demotes to disk; suspension is a held-context,
self-healing mechanism, not a throughput cliff** ·
**agentic 11/12 verified, 12/12 honest, median 2 turns / ~7 s per trial** ·
engine-side prefix-cache reuse 20–45 k tokens per fresh agent session.

## Clean-window rerun 2026-11-13 — standalone driver (raw: `bench/splash-concurrency/results/clean-2026-11-13/`)

The suite the other waves could never quite run **truly single-tenant**: a detached python runner
(`bench/clean-run-2026-11-13/run_clean.py`, launched from a terminal) drove engine probe → ladder+KV
→ visual-venv → agentic while the operator's Claude session — itself served by this engine — sat
completely idle, zero turns, for every timed stage. Splash 1.6.1 (now version-confirmed via
`splash --version`, not assumed), engine warm at start (cache hit-rate 0.996).

Headline deltas vs the three prior 1.6.1 waves (full table in the leaderboard):

- **Ladder w1 209.5 tok/s** — best recorded; probe/ladder ratio 0.760 reproduces 11-12's 0.745, so
  the probe-vs-ladder gap is a harness constant, not contention.
- **Plateau 470–475 (w8–32, peak w12 475.2)** — the *lowest* plateau of any 1.6.1 wave despite zero
  contention: the w6 dip all but vanishes (0.97× of w4) and the plateau mean keeps drifting
  (518.3 → 496.6 → 473.7). Read: plateau level is engine-instance state; the tenancy tax is a
  latency-suite effect (agentic/resolve walls), not something a saturated-decode aggregate feels.
  Shape invariants hold: no collapse by 32, stop rule never fired, admission peaks identical
  (2/4/8/12/12/12 at w6/8/12/16/24/32).
- **TTFT 159 ms warm / 229 ms cold** — best cold recorded; warm corroborates 11-12's 151.
- **KV: no trip at 611,244 = 4.66× the 131,072-token budget** — fifth-wave reproduction; memory path
  middling-quiet (waiting_memory peaks 1, holds 72–196 ms; `spill+0 demote+0`;
  `lifetime_final` suspensions 0, capacity_failures 0 in the ladder_kv SUMMARY).
- **Agentic n=3 back: 12/12 verified + 12/12 honest**; S3's `out.json` exact on all three passes,
  S1/S2 values cross-checked against live `/status` counters (monotonic, consistent).
- The visual-venv baseline (run3) co-ran in the same idle-engine window — every deterministic value
  bit-identical, canonical 0.278 s; see the leaderboard's Visual venv section.

Harness note: the runner's intended warm-up completion 404'd (Splash doesn't serve
`/v1/chat/completions`); harmless — the probe's own first passes warmed the engine (decode rows
159→174→143 trend visible in `engine_probe.jsonl`). Future reruns should warm via the Messages
route or just accept the probe trend.

## Cross-hardware — the same model on NVIDIA boxes (external data, 2026-11-13)

**Not a leaderboard section.** Every non-host number below is someone else's measurement on
someone else's harness, gathered 2026-11-13: usually n=1, tenant conditions unstated, engines
and quants differing row to row. That fails leaderboard rules 2–3, so it lives here as
context, not as rows. Links at the end; treat every cell as "as published, accessed 2026-11-13".

**Reference-host anchor:** the 2026-11-13 **clean-window** rerun (wave detail in
[NOTES.md](../bench/splash-concurrency/results/clean-2026-11-13/NOTES.md) and the
[leaderboard](leaderboard.md)) — the first wave with zero co-resident session traffic, so the
single-tenant caveat that hedged every earlier host row is gone: decode w1 **209.5 tok/s**
(ladder, best recorded), plateau **470–475 tok/s** (widths 8–32, stop rule never fired — the
plateau scatters 470–525 across 1.6.1 waves and is engine-instance state, not tenancy),
TTFT **159 ms warm / 229 ms cold**. Prefill keeps the 2026-11-12 figure — 611,244 tokens /
171.5 s ≈ **3.56 k tok/s** — because the clean-window KV pass is submit-timed only and prefill
walls are unchanged across these builds anyway.

**Model facts that frame the whole comparison.** Locally measured: the IQ3_S GGUF is **78 GB**
(51 GB + 27 GB shards). Community reports describe Qwen3.8-Flash-Next as a **125B MoE with
~6B active per token plus a ~51 GB n-gram/PLE lookup table**; smallest common quant downloads
are ~70 GB, NVFP4 checkpoints 124–126 GiB. **No consumer GPU holds it whole** — on every
platform the question is the quality of the weight-offload pipeline (VRAM→RAM→SSD streaming),
not the GPU's raw speed. That is exactly the regime Splash's 56 GiB working set + 128 GiB disk
cache exists for.

| Platform | Memory / bandwidth | This model, single-stream decode | Prefill | Aggregate / concurrency |
|---|---|---|---|---|
| **Reference host** — M5 Ultra 96 GiB, Splash **1.6.1**, INT8 | 96 GiB unified; Apple never states the M5 Ultra bus, unmeasured here | **209.5 tok/s** (IQ3_S, ladder w1, clean window) | **~3.56 k tok/s** | **470–475 tok/s** plateau, widths 8–32 (wave band 470–525), true single-tenant |
| NVIDIA **DGX Spark** (GB10) | 128 GB LPDDR5x, **273 GB/s** | **55.6 tok/s** — Mia's recipe (FP4 QAD or INT4-AR **+ MTP** draft, TensorFold Zig). Same-class quants without drafters land lower (27B dense: 35–51) | 2.4k tok/s (gpt-oss-120b b1 — different model) | 262 tok/s (gpt-oss-120b, 32×4096 — different model); dense 70B FP8: **2.7 tok/s** (bus-bound) |
| NVIDIA **RTX Spark** (N1X, launched 2026-10-16) | up to 128 GB unified LPDDR5X-9400, **~300 GB/s** est. (StorageReview, from Dell's 256-bit listing) | **no published Flash-Next figure yet** — device-class numbers: GPT-OSS-120B ~65 tok/s (llama.cpp); dense 27B 13.4 (no draft) / ~33 (DFlash2); community 5-device comparison places Spark ≈ DGX Spark ±10 % | — | Windows-on-Arm caveats: GPU gets only part of the pool; no Linux reported at gather time |
| NVIDIA **RTX 5090** (32 GB GDDR7, ~1.79 TB/s) + 64–128 GB DDR5 | ~29 GB model-hot in VRAM; experts over PCIe 5.0 (~64 GB/s) + DDR5 (~90–100 GB/s); n-gram table on NVMe | **30–50 tok/s** stock llama.cpp/vLLM (43.4 vLLM bench Aug 2026; 30.7 unsloth GGUF + 96 GB); **90–107 tok/s** purpose-built engines (Strata IQ3_S @ 262k ctx int8-KV: **106.8 median**, drops to ~62 sharing the card; MTP: 45→90) | 2.3–4k tok/s | 2× 5090, QEngine: **504 tok/s** decode; dual-5090 FreeToken 217 stable, 350+ with drafting |

**Findings.**
- **Same-model, same-quant-class single stream: the host is ~2.0× the best published 5090
  result (209.5 vs 106.8, both IQ3_S) and ~3.8× the best Spark figure (55.6, FP4 ≈ same memory
  demand), and 4–7× stock llama.cpp/vLLM on the 5090.** The mechanism is bandwidth tiering at
  decode: this model wants well past 100 GB resident while streaming 78 GB-class weights per
  sweep. Unified memory touches it all directly; the Sparks sit on a 273/300 GB/s bus; the 5090's
  1.79 TB/s helps only the ~29 GB it pins, and everything else pays PCIe + DDR5.
- **Prefill is parity** (2.3–4k vs 3.56k) — compute-bound, not bandwidth-bound. Consistent with
  the engine's own finding that INT8 decode gains left prefill walls unchanged.
- **x86 engine momentum is the real counter-story.** Strata, FreeToken, ik_llama.cpp MTP and
  QEngine exist *because* Flash-Next is an offload-designed model, and they earn 2–3× over stock
  stacks on the 5090. The host's saturated-decode plateau **scatters 470–525 tok/s across 1.6.1
  waves** (instance state, not contention — the clean-window rerun sits at the bottom of that
  band with zero co-tenancy), so a **2× 5090 QEngine box (504 tok/s aggregate) lands inside the
  host's range** — but at ~$13 k in cards alone at Nov-2026 street prices, versus the plateau
  being headroom the host already has.
- **Where the NVIDIA boxes actually win:** capacity and the CUDA stack. 128 GB holds gpt-oss-120b
  (59–65 tok/s) and dense models the 32 GB card cannot; two Sparks ≈ 400B, four ≈ 700B (NVIDIA's
  own figures); the 5090 runs *models that fit it* fast (Qwen3.8-27B NVFP4: 77–114 tok/s single,
  425 aggregate at 4 users). NVIDIA is also software-boosting the line ("agentic Qwen3.8-27B up
  to 1.3×", NVIDIA, 2026-10-21) — the 55.6 will creep up; the 273 GB/s will not.
- **Prices as of 2026-11-13 (volatile, memory-crisis market):** DGX Spark 128 GB ~$4 k nominal
  but sold out / inflated (64 GB units reported at $5 k); RTX Spark laptops $2,399–2,599 entry,
  128 GB configs $5,899–6,999; RTX 5090 restocked at Newegg (mid-Nov) at $6,250–6,660/card.

**Comparability caveats (house rules, applied in reverse):** speculative decoding is baked into
the headline NVIDIA figures (the 55.6 includes an MTP draft; MTP turns 45→90 on the 5090) —
cross-row comparisons should read the *without-drafters* numbers where given; quants differ
row to row (FP4 QAD / INT4-AR / IQ3_XXS vs IQ3_S — same memory class but not same weights);
NVIDIA-side numbers are owner-reported, n≈1, tenancy unstated; the host figure is the **ladder
w1 median, not the probe** (probe/ladder ratio 0.760 on the 11-13 clean window, 0.745 on 11-12 —
a harness constant; quoting the probe would understate the host); and the M5 Ultra bus width is
quoted nowhere official — the bandwidth-tier claim rests on observed decode rates, not a
spec-sheet number.

**Links (accessed 2026-11-13):**
DGX Spark: getrigbase.com/dgx-spark/ (Mia's recipes, the 55.6) ·
verdictbits.com/reviews/dgx-spark-benchmarks/ (published-measurement roundup + NVIDIA multi-node
tables) · eurokommerz.at/blog/nvidia-dgx-spark-real-benchmarks/ (llama.cpp b7941 58.7 / 262.2;
LMSYS 2.7 dense) · kevinwelter.com/en/blog/qwen-3-8-lokal (27B NVFP4 SGLang 50.7) ·
gpuwerk.com/dgx-spark/guides/best-models-2026/.
RTX Spark: lttlabs.com N1X review · shattered.io N1X spec/price + review-roundup posts ·
tech-insider.org RTX Spark launch pricing · mindstudio.ai RTX Spark real-numbers post ·
sourceit.com.sg RTX-vs-DGX comparison · vdf.ai (Windows memory split).
RTX 5090: en.wiselychen.com Strata hands-on (IQ3_S 106.8 median) · r/LocalLLaMA
"Qwen-3.8-Flash-Next on 1× RTX 5090" (TG 50 / PP 2300; MTP 45→90) · r/LocalLLM unsloth-GGUF 5090
(30.7) and llm-bench.io vLLM (43.4) · QEngine 2×5090 (504) ·
suhailmohebi.com/notes/qwen3-8-flash-next-hardware-requirements/ (download sizes).
Local measurement for the model-size framing: the IQ3_S snapshot, 51 GB + 27 GB shards.
