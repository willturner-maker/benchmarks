# Splash Engine Benchmark — Baseline Results (2026-11-06)

**Purpose:** version-to-version performance tracking of the Splash engine + resident Qwen
model on this machine — the Splash counterpart to the Resolve MCP benchmark
(`resolve-agentic-benchmark-results.md`). No prior baseline existed; the only earlier
artifact was the never-run draft spec in `docs/concurrency-scaling-test.md` (2026-09-26),
whose design this reuses in adapted form.

**Host (fixed for comparison):** Apple M5 Ultra, 64-core GPU, 96 GiB unified memory,
macOS 27.2.0. Engine args: working set 56 GiB, SSD cache cap 128 GiB, persistent cache on.

**Baseline stack:** Splash **1.6.0** (brew), model `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`,
262,144-token context, int8 KV, status schema 8, keyless engine on `127.0.0.1:8000`
(started via `~/start-resolve-ai.sh`). Cache state at run: warm (hit_rate 0.9924, 916 hits /
7 cold misses since last start; the 1.6.0 upgrade had cleared the SSD cache earlier that day).

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
`bench/2026-11-06/width_ladder.py`.

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
between samples). Script: `bench/2026-11-06/kv_pressure_v4.py`.

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

Scripts committed under `bench/2026-11-06/`. The **combined entry point is
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
