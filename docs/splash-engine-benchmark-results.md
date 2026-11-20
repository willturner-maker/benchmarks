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
- [Co-tenancy — Resolve Studio on the same 96 GiB](#co-tenancy--resolve-studio-on-the-same-96-gib-measured-2026-11-15-raw-benchresolve-ram-coexistence)
- [Quant memory accounting](#quant-memory-accounting--what-bpw-actually-scopes-and-what-a-quant-costs-in-ram-measured-2026-11-15-raw-benchsplash-quant-memory)
- [Re-run 2026-11-17 — Splash 1.7.0](#re-run-2026-11-17--splash-170-three-passes-warm-gate-raw-benchsplash-concurrencyresultssplash-170-2026-11-17)
- [Re-run 2026-11-19 — the 32-request wall, then the queueing regime](#re-run-2026-11-19--the-32-request-wall-then-the-queueing-regime-raw-benchsplash-concurrencyresultssplash-170-2026-11-19-ext-and--2026-11-19b)
- [Re-run 2026-11-19c-clean — the single-tenant control](#re-run-2026-11-19c-clean--the-single-tenant-control-on-the-queue-size-64-stack-raw-benchsplash-concurrency-resultssplash-170-2026-11-19c-clean)

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

## Re-run 2026-11-16b — dirty window: operator tenancy + the first KV trip on record (raw: `bench/splash-concurrency/results/rerun-2026-11-16b/`)

Ran the same day as the agentic 16/16b waves; engine not restarted, no TTFT probe stage. This
wave is **published as raw with caveats, not as baseline material** — see the directory's
`NOTES.md`.

- **Ladder medians:** w1 **92.6** (lowest ever; its rounds ran before any external traffic —
  instance state, unexplained) / w2 181.3 / w3 230.5 / w4 454.8 / w6 463.7 / w8 514.7 / w12
  523.6 / w16 508.7 / w24 525.5 / w32 **540.5** (highest single width recorded). Stop rule
  never fired; plateau w12–w32 mean 524.6 sits *above* 11-13's 473.7 while w1 sits far below —
  opposite directions confirm instance state, not shape.
- **Tenancy contamination:** three seal-probe `opencode run` calls (verifying the agentic wave's
  permission syntax) hit the same engine mid-ladder (~widths 2–8 window); w2 round scatter
  217.4 vs 145.2 is consistent with it. Operator-tenancy tax, reproduced in the wild.
- **KV stage — first trip on record:** stopped at w10, 509,370 tokens = 3.89× the 131,072-token
  resident budget: peak suspended 2, waiting_memory 2, pages_active 7238, lifetime
  resource_suspensions +3, demote +1502. Prior waves held zero suspensions at 4.66×. The trip
  is real (counters moved); whether the *threshold* shifted is not established — same-day engine
  residency is a candidate factor. Clean-window (and ideally fresh-engine) rerun needed before
  this reads as a finding either way.

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
Local measurement for the model-size framing: the IQ3_S snapshot, 51 + 27 **GiB** shards (51.05 GiB
of transformer weights + 26.82 GiB n-gram lookup table = 77.87 GiB = 83.6 GB decimal — and see
*Quant memory accounting* below for which of those two shards is actually resident).

## Co-tenancy — Resolve Studio on the same 96 GiB (measured 2026-11-15) (raw: `bench/resolve-ram-coexistence/`)

Every host row above assumes the engine has the machine roughly to itself. It doesn't: this box
also runs DaVinci Resolve Studio, and the 56 GiB working set was chosen (2026-10-28/29) partly to
leave Resolve room — a figure that had never been measured. So: is 56 GiB stingy (Resolve only
wants a few GiB, so room to move up a quant) or generous (Resolve is the reason there is nothing
to spare)? **Measured answer: generous — and the pool is already full.**

Method (full notes in `bench/resolve-ram-coexistence/NOTES.md`): `/usr/bin/footprint` per pid at
1 Hz over the whole `/Applications/DaVinci Resolve` process family (**phys_footprint**, the metric
macOS pressures on) + `vm_stat` + `vm.swapusage`, phase-labelled, **2,138 samples** over three
passes. Engine `--max-memory=56G`, resident footprint **52.15 GiB** for nearly every sample;
Resolve **21.2 headless** (`-nogui`). Payload: one 3000-frame probe item from an 8.1K anamorphic
source in a UHD 3840×2160 @ 29.97 project, rendered twice — H.264 2160p and ProRes 422 HQ — both
ffprobe-verified at 3000 frames / 3840×2160.

| phase | Resolve phys_fp max (GiB) | system wired max | free min | compressor max | engine phys_fp | samples |
|---|---|---|---|---|---|---|
| Resolve down (baseline) | — | 60.96 | 9.59 | 1.10 | 52.15 | 10 |
| headless launch, idle | **1.43** | 60.99 | 9.18 | 1.10 | 52.15 | 9 |
| project load | 2.54 | 61.99 | 7.85 | 1.10 | 52.15 | 34 |
| build probe timeline | 3.91 | 64.01 | 5.50 | 1.10 | 52.15 | 15 |
| H.264 2160p render — encode only, no decode (see caveat) | 6.22 | 64.75 | 1.22 | 1.10 | 52.15 | 170 |
| H.264 2160p render, real 8.1K decode | 6.00 | 62.62 † | 2.62 † | 1.10 | 52.15 → 4.48 † | 1516 |
| Resolve restart (clean slate) | 3.12 | 62.53 | 5.77 | 1.07 | 52.15 | 18 |
| **ProRes 422 HQ render, real decode — overall peak** | **6.76** | **66.08** | **0.16** | **2.90** | 52.15 | 76 |
| idle after render | 6.28 (held, not released) | 61.04 | 0.80 | 2.85 | 52.15 | 3 |
| after quit | 0.02 | 61.62 → 57.93 | 0.44 → **19.59** | 2.85 → 1.96 | 52.15 | 254 |

† that phase straddles the engine's idle-release un-wire (the `engine_phys_fp` column shows it), so
its wired/free columns mix resident and un-wired states — the ProRes row is the clean coexistence
measurement.

**The ledger at the ProRes peak** (GiB): engine resident 52.15 · extra kernel/Metal wiring ~8 ·
engine file-backed pages ~11.5 · Resolve at peak 6.76 · compressor 2.90 → **free 0.16**. Swap never
engaged in any sample (0.01 GiB throughout), and reclaim on quit is complete: Resolve to 0.018,
wired back to 57.93, free to **19.59** — higher than the 9.6 GiB it started at, because the
compressor had also drained 0.9 GiB.

**Findings.**
- **Resolve is not the memory problem: ~6.8 GiB phys_footprint, ~+6 GiB wired**, at real UHD
  decode+encode — far under the 30–40 GiB a UHD suite is usually credited with. (In headless the
  `footprint` category table keeps `IOAccelerator (graphics)` at KB-level dirty, so the wired
  delta, not the process category, is the GPU-inclusive figure.) The thing consuming 96 GiB is the
  engine plus its mapped weights, ~72 GiB of resident-plus-file-backed before Resolve arrives.
- **The pool is full, so the quant ladder has no rung available above IQ3_S.** Measured on-disk
  sizes: IQ3_S **77.9 GiB** (current); `UD-Q3_K_XL` 83.3 GiB (+5.4); `UD-IQ4_XS` 87.3 GiB (+9.4);
  `UD-Q4_K_XL` 103.6 GiB — already past the entire pool. Fitting the +9.4 would mean cutting the
  Metal budget by about that much, straight back into the recorded 48 GiB failure (KV capped at
  147k tokens, below the 262k window, pinned at 100 % and spilling) and the 2026-10-29 collision
  (64 GiB engine + 8K render, 7.6 GB swap). We watched that boundary from the safe side: free hit
  0.16 GiB and the compressor grew 1.07 → 2.90 GiB with swap still untouched.
- **Co-residency costs the engine nothing measurable.** Through the render windows, single-stream
  TTFT stayed 0.4–0.7 s and decode 40–165 tok/s; the two 40 s TTFT spikes line up with 140k+-token
  prefills, not with the render. Caveat: single-stream session traffic, not the width ladder — this
  says "no interference", it is not a ladder row.
- **`--idle-release` (10 m default) is the real headroom lever, not a config knob.** After ~10 min
  with no request the engine un-wires its weights: phys_footprint 52.15 → **4.48 GiB**, system free
  3 → **57 GiB**, wired 60 → 4.3; it re-wires on the next request (`POST /v1/memory/release` forces
  it). So a heavy Resolve session can have nearly the whole machine for the duration without
  permanently shrinking the KV pool. It also means **any co-tenancy sample taken during an idle
  engine window is measuring the wrong thing** — pass 2 here caught that by accident, which is why
  the sampler logs the engine's footprint per row.
- **Verdict: stay on IQ3_S.** No GiB to give, and no error budget to buy back — the agentic record
  is 126/126 verified across seven scored waves (two earlier waves sit outside the scored record — they
  shipped no per-trial rows; see the agentic doc's record-scope section) and the vision head-to-head had
  IQ3_S Flash 30/36 vs the 27B leg's 27/36.
  A quant step up becomes a hardware question (192–256 GiB), not a recipe question.
- **Decode warmth dominates the render wall, and therefore how long the memory plateau lasts:**
  cold 8.1K decode ran ~2 fps (24 min for 3000 frames); the second pass over the same cached
  region ran ~40 fps (~75 s). Same 3000 frames, same raster, ~20× the rate.

**Caveats:** headless only (no GUI, no viewers), single video-only item, no grades/Fusion/temporal
NR, 3840×2160 out — so 6.76 GiB is a **floor** for Resolve's appetite, not a worst case; GUI
Resolve, Fusion-heavy comps, NR and 8K output all sit above it. The "encode only" row measured a
job that spent its span on a 1.6 M-frame empty gap (a `create_variant_from_ranges` placement
artifact — see the gotchas in NOTES.md), i.e. encode without decode, and is kept only because its
peak matches the real-decode rows. Raw CSVs carry phase and engine-residency per row so any column
here can be re-derived or discarded.

## Quant memory accounting — what bpw actually scopes, and what a quant costs in RAM (measured 2026-11-15) (raw: `bench/splash-quant-memory/`)

The ladder in the section above ranks quant builds by **total download**, which is the wrong axis for
this checkpoint: it ships transformer weights and the n-gram lookup table as two shards, and **only the
first is ever resident**. This section fixes the units, re-states the ladder on the resident axis, and
asks the follow-on question — would more RAM buy throughput at all.

### What bpw scopes here (and what it does not)

The model card states the bit-width column *"is the average over the transformer weights, which is what
the search controls"* — not bits per parameter of the download. Shard 2 is not transformer weights: it
is the n-gram lookup table (`per_layer_token_embd.weight`), held at **IQ4_NL / fixed 4.5 bpw** and
*"excluded from the search"*, which is why its size is identical in every row. And RCO *"assigns one
quantization type per tensor"*, with *"95 % of the searchable weights … in the experts"*, which *"sit
at a much lower bit-width than the dense path"* — so 3.5 bpw is a **budget average over an unequal
allocation**, not "every weight coded in 3.5 bits".

Card ladder (BF16 is the quality reference, not a purchasable option on this box):

| variant | bpw | total GB | shard 1 weights GB | shard 2 table GB | AIME25 | GPQA-D | LCB v6 | task avg |
|---|---|---|---|---|---|---|---|---|
| BF16 base | 16.00 | 354 | — | — | 100.00 | 91.92 | 87.43 | 93.12 |
| GSQ-RCO Q2_0 | 2.40 | 66.4 | 37.6 | 28.8 | 96.67 | 89.39 | 81.14 | 89.07 |
| GSQ-RCO IQ2_XS | 2.50 | 68.0 | 39.2 | 28.8 | 96.67 | 87.37 | 83.43 | 89.16 |
| GSQ-RCO IQ3_XXS | 3.00 | 75.8 | 47.0 | 28.8 | 100.00 | 91.41 | 86.29 | 92.57 |
| **GSQ-RCO IQ3_S** (what runs here) | **3.50** | **83.6** | **54.8** | **28.8** | **100.00** | **92.93** | **86.86** | **93.26** |

The three score columns, since they get quoted a lot: **AIME25** = all 30 problems of the 2025 American
Invitational Mathematics Examination, integer answers 000–999, scored exact-match (olympiad-style multi-step
math, no partial credit, so it is a pass/fail-heavy reasoning probe). **GPQA-Diamond** = 198 graduate-level
four-option science questions (bio/chem/phys) written and validated by domain experts, selected so experts
get them right and at most one in three non-experts does even with web access — the "Google-proof" idea;
PhD experts themselves score ~65–70 %. **LCB v6** = LiveCodeBench release 6, 1,055 competitive-programming
problems from LeetCode/AtCoder/Codeforces dated May 2023–Apr 2025, scored pass@1, whose whole design is
contamination control by problem release date. Two properties matter for how we use these numbers, and both
cut against taking them at face value: **AIME25 is saturated here** — 100.00 for the base model *and* for
IQ3_S and IQ3_XXS, so that column carries no discriminating information at this quality level — and
**the contamination protection is dated**: the newest v6 problem is from April 2025, so for a 2025/2026-era
checkpoint the "fresh window" argument no longer holds. Treat these as a pre-screen for a quant decision,
never as the decision.

- **3.5 bpw is not "nearly 4-bit".** Levels go as 2^bits: 3.5 bits ≈ **11.3 levels** vs **16** at 4 bits —
  41 % fewer, about 3 dB of quantization SNR. What *is* close to 4 bits is the byte average of the whole
  download: 83.6 GB over 176,943,899,520 params = **3.78 bits/param**, pulled up by the 4.5-bpw table.
- **The repo tops out at IQ3_S on purpose** — Q2_0 → IQ2_XS → IQ3_XXS → IQ3_S, no 4-bit build — because
  IQ3_S already lands **above** the BF16 row (93.26 vs 93.12 task avg). There is no quality headroom above
  it on these axes to buy with RAM.
- Arithmetic cross-check against the local blobs: shard 1 54,817,524,224 B ÷ 3.5 bpw ⇒ 125.2 B transformer
  params; shard 2 28,800,138,432 B ÷ 4.5 bpw ⇒ 51.2 B table entries; sum ≈ 176.4 B vs the 176,943,899,520
  in the config. The card's numbers and the files on disk agree.

### What a quant actually costs in RAM (the engine prints its own ledger)

`banner.txt` — Splash's startup lines for this exact snapshot; read the banner rather than re-deriving
these from file sizes:

| allocation | size | resident |
|---|---|---|
| routed-expert store: **23,034 slots for 24,576 experts (93 %)** | **46,874 MiB** | yes — a floor that "neither grows nor gives memory back" |
| non-expert transformer weights | ~4.5 GiB (residual) | yes |
| draft model (DFlash2) | 1.12 GiB | yes |
| KV hot block cache (131,065 tokens resident, 262,144 spilled) | 390 MiB | yes |
| **PLE n-gram row cache: 2,097,152 rows** | **237 MiB** | yes |
| recurrent-state write staging | 113 MiB | yes |
| n-gram table, remainder of the 27,465 MiB | 26.6 GiB | **no — SSD** |
| non-resident experts (1,542 of them, 2.035 MiB per slot) | ~3.06 GiB | **no — SSD** |

The resident rows sum to **52.2 GiB**, which is the independently measured `footprint` of 52.15 GiB from
the co-tenancy run (`footprint` prints it as `56 GB` decimal, with 55 GB sitting in the
`IOAccelerator (graphics)` category — that is the Metal allocation, not a GPU side-channel). Nothing here
is mmap'd: `vmmap --summary` on the engine shows **no MAPPED FILE section at all**, so the GGUFs are read
positionally through held fds, not mapped into the address space.

### The SSD traffic is experts, not the n-gram table

`decode-probe.log`: one 900-token generation (59-token prompt, `reasoning_effort=low`, temp 0) moved
**~1.28 GB/s** of device traffic averaged over the five decode seconds of `iostat`, against a near-zero
idle floor — i.e. **~5.7 MB of device traffic per output token**. The n-gram table explains a fraction of
a percent of it: 16 ids per token × ~118 B/row ≈ **1.9 KB/token**, i.e. 0.36 MB/s at 190 tok/s. The rest
is routed-expert misses: the 7 % that don't fit the store cost **1,542 × 2.035 MiB = 3.06 GiB** of extra
RAM to eliminate, and `--expert-memory auto` sizes itself off `--max-memory`, so raising the cap is what
would grow it.

**Would that buy throughput? No evidence that it would.** Repeat runs of the identical request:
160.2 / 190.2 / 244.6 tok/s, and a different set an hour earlier 170.3 / 157.5 / 149.3 — a **149–245 tok/s
spread band at fixed configuration**, so nothing under ~25 % is measurable at n=1 (the engine itself warns
of run-to-run variance: `--verify-rows auto` on a MoE target means *"greedy and seeded outputs can differ
from run to run"*), and those fetches go through **32 readers** overlapping the compute. So raising
`--max-memory` to 58–60 GiB in order to raise `--ple-memory` is a bad trade twice over: the wrong structure
(PLE ≈ 0.03 % of the traffic, and `auto` already caches *"the rows of every id a 128K-token prompt stages"*
— the longest request that day was 92,813 input tokens), and RAM that would come out of the **file-backed
cache already serving those same pages at memory speed** (dd: 4 GiB of the n-gram shard in 0.21 s =
**20.6 GB/s**, which is the unified-memory page cache, not NVMe). Against the co-tenancy row — Resolve
arriving into **0.16 GiB** of free space at 52.15 GiB resident — a 60 GiB cap is only safe on days Resolve
stays off. `--ple-memory off` (load the whole table) would need 26.8 GiB resident: arithmetically out.

### The ladder, re-stated on the resident axis

Subtract the constant 26.82 GiB table from the totals quoted above: IQ3_S **51.05 GiB**, `UD-Q3_K_XL`
**56.5 GiB** (⇒ ~3.9 implied bpw), `UD-IQ4_XS` **60.5 GiB** (⇒ ~4.15). The resident deltas (+5.4 / +9.4
GiB) equal the download deltas because the table is identical across all three — the one thing the
total-download comparison got right by construction. The co-tenancy verdict stands, now on the correct
axis: **+9.4 GiB of resident weights has nowhere to go next to Resolve, and buys nothing on the card's own
task average.**

**Caveats:** single session, no engine restart — the `--expert-memory` question is *scoped*, not A/B'd
(restarting ends the served session, so the A/B is left as a recipe: `MAX_MEMORY=60G` **plus** an explicit
`--expert-memory 50G`, then confirm `24576 experts (100 %)` in the banner and re-probe at n≥5 against the
149–245 band). `iostat` does not split reads from writes, so 1.28 GB/s is an upper bound on the streaming
read cost, not a pure read figure. `vm_stat`'s "wired down" moved 6.6 → 63.0 GB between two samples with
the engine's `footprint` unchanged — wired-vs-pageable state of the Metal buffers is not a stable metric
without phase labels. The implied bpw for the third-party builds assumes they carry the same 26.82 GiB
table; that was not verified against their files. Probe cost: ~3,600 output tokens on the live engine, and
one exploratory sparse-read probe that mis-computed its seeks and pushed ~918 GB **read-only** through the
page cache (disclosed in `NOTES.md`; it churned the file cache, which is part of why the dd number is so
high).

## Re-run 2026-11-17 — Splash 1.7.0, three passes + warm gate (raw: `bench/splash-concurrency/results/splash-1.7.0-2026-11-17/`)

Splash **1.7.0**, installed the same day upstream shipped it (17 Nov 12:42 UTC), version-confirmed by
`splash --version` **and** by the live process path `/opt/homebrew/Cellar/splash/1.7.0/libexec/…`. Status
schema still 8. Engine args here: 56 GiB working set, **SSD cache cap 256 GiB** (the 128 GiB quoted in the
baseline header is no longer what this host runs), persistent cache on, `--default-reasoning-effort=xhigh`,
`--thinking-token-budget=16384`, and **defaults everywhere the release added a knob** (`--verify-rows auto`,
`--cached-states` default INT8, no `--activations` override).

**Why three passes: the upgrade cleared the prefix cache, and the log says so.** Startup line:
`Persistent cache …/c1cb917d…: took back 0 restore points over 0 KV blocks (0 MiB); left 0 copies behind.`
Same cache-dir hash (weights untouched), zero state restored — the release note's "persistent caches from
1.6.x start cold once". The suite was therefore run three times on one engine instance (never restarted),
pass 1 as warm-up, and the warmth gate was called from `/status`, not by feel:

| | before p1 | after p1 | after p2 | after p3 |
|---|---|---|---|---|
| `hit_rate` | 0.8750 | 0.9661 | 0.9826 | **0.9883** |
| `hits` / `cold_misses` | 14 / 2 | 285 / 10 | 565 / 10 | **846 / 10** |
| `kv_disk_hit_tokens` | 0 | 0 | 2,124,640 | **4,253,728** |
| `disk.read_bytes` | 0 | 0 | 27.8 GB | **55.8 GB** |

The decisive line is **`cold_misses` frozen at 10 from pass 1 onward**: every prompt the suite submits is
cached, so a fourth pass could teach the cache nothing. A methodology note worth keeping: I first set
"disk hits > 0" as a warmth test, then nearly wrote it off as unreachable because the 4,095-page RAM ring
held everything — wrong, eviction arrived mid-pass 2 and the SSD tier then served 2.1 M tokens. Disk hits
are reachable inside a run, just not in the first one.

### Headline vs the best 1.6.1 row (2026-11-13 clean window)

| metric | 1.6.1 (11-13) | **1.7.0 (11-17, 3 passes)** | delta |
|---|---|---|---|
| ladder w1 | 209.5 | **219.8** (233.2 / 219.8 / 207.5) | +4.9 % |
| plateau w8–32 | 470–475 (mean 473.7) | **479–494** (pooled median 481.6; means 483.2 / 484.3 / 476.8) | +1.7 % |
| aggregate peak | w12 475.2 | **w4 526.5** | peak moved back to w4 |
| w6 dip vs w4 | 0.97× | **0.785–0.855×** | dip returned |
| TTFT warm | 159 ms | **110–118 ms** | −26 % (best ever on this host) |
| TTFT cold | 229 ms | **291 ms** (pass 1 only — see caveat) | +27 % |
| probe decode w1 | 159.3/173.6/143.3 | **170.4** (8 rows, one outlier excluded) | +9 % |
| resident KV budget | 131,072 tok | **155,648 tok** | +18.8 % (INT8 cached states) |
| KV at 611k tok | 0 suspensions, demote +1,124 blocks | **0 suspensions, demote +11 total, 0 spill** | demote path near-dormant |
| prefill (611,244 tok, uncached) | 170.5–171.5 s | **172.6 s** | unchanged → gains are decode-side |

### Caveats that belong on this row, not in a footnote somewhere else

1. **Cold TTFT is valid in pass 1 only.** Passes 2–3 re-submit an already-cached prompt, so their
   "cold" rows (122 / 138 ms) are warm hits with a cold label. The honest cold figure is 291 ms.
2. **One excluded-with-a-name outlier:** pass 3's first decode row, **82.6 tok/s** — the same tenancy
   transient shape as 11-11h's 81.6/80.7. It stays in the JSONL; pooled n=9 median 166.5, n=8 median 170.4.
3. **Tenancy is not clean-window.** The operator's OpenCode session is served by the same engine and took
   turns during the passes. Per the 11-13 finding, the tax falls on latency cells (w1, TTFT) rather than
   saturated-decode aggregates, so the plateau stands and the latency cells carry a modest tax. A strictly
   clean 1.7.0 row still needs the detached-driver treatment.
4. **Not bit-comparable** with 1.6.x rows: `--verify-rows auto` is stated at startup as letting greedy and
   seeded output differ run-to-run, on top of 1.7.0's INT8 cached states and 1.6.1's INT8 activations.
   A reproducible row wants `--verify-rows all` with a fresh `--cache-dir`.
5. **w1's direction is unresolved.** It fell monotonically across the three passes while the plateau held
   — this suite's noisiest cell (12.4 % spread; history includes a 92.6 tok/s w1 with a *higher* plateau).

### Extra probe: cross-session prefix reuse (answers the workflow README's cache claim)

`usage.prompt_tokens_details.cached_tokens` read back on a ~9.7k-token shared-prefix stand-in for a fresh
agent session's system+tools block: cold **32 / 9,683 (0.33 %)** → repeat **9,664 (99.80 %)**, 111 ms →
*different session, same prefix + new tail* **9,664 (99.73 %)**, 125 ms. Cross-session reuse is intact on
1.7.0 and lands at page granularity (9,664 = 75.5 × 128-token pages); uncached prefill ran at
**3,611 tok/s**. Scope stated: this verifies the mechanism at 9.7k tokens — the "20–45k cached tokens per
fresh agent session" figure is the real OpenCode prefix and still needs the agentic driver to re-measure.

Full per-pass tables (ladder medians with spread, probe rows, KV gauge peaks and counter deltas, the six
`/status` snapshots) are in
[`bench/splash-concurrency/results/splash-1.7.0-2026-11-17/NOTES.md`](../bench/splash-concurrency/results/splash-1.7.0-2026-11-17/NOTES.md).

## Same day, later: the clean-window pass, the `--verify-rows` A/B, and the first OpenCode agentic row

Two detached runners (raw:
[`bench/clean-run-2026-11-17/`](../bench/clean-run-2026-11-17/) writing into
[`results/clean-verifyrows-2026-11-17/`](../bench/splash-concurrency/results/clean-verifyrows-2026-11-17/)
and `…/clean-verifyrows-2026-11-17-pass2/`). This closes the two caveats the three-pass wave left open:
tenancy and the missing agentic column.

**The clean-window 1.7.0 pass** (batch A ladder + probe, zero operator turns): ladder w1 **225.2**
(best recorded), plateau w8–32 **462.9–484.4** (mean 476.8), peak **w4 543.8** (best recorded), probe
decode median **197.4**, warm TTFT 98 ms; KV 611,244 tok with **0 suspensions and 0 demotions** on an
instance budget of 4,352 × 32 = **139,264 tok** (budgets vary per instance: 131,072 / 155,648 /
139,264 — the ×-multiple in the row tables is instance-relative). The config is on the record rather
than assumed: `/status` carries a **`verify_rows`** field and it reads `auto` in all four snapshots
and on the live engine. Reading: the tenancy-free pass **confirms the shape** (w4 peak, deep w6 dip
at 0.78×) and nudges the latency cells (w1 +2.5 % vs the 3-pass median), but does **not** lift the
plateau — again consistent with plateau scatter being instance state.

**Batch A's two self-inflicted wounds, kept on the record** (full statement in that directory's
`VALIDITY.md`): its restarts were **no-ops** — `pkill -f "splash serve"` misses the supervisor
(`… -m server.server`), the engine child respawned with the original args, and the follow-up
`splash serve` refused with `already serving (PID 1359 … phase ready)` — so its numbers are valid as
an **auto**-config clean pass and there is still no `--verify-rows all` ladder. And its determinism
probe hashed `message.content` only, which came back empty at a 16k thinking budget: ten identical
`e3b0c442…` hashes — the SHA-256 of the empty string. A vacuous "bit-reproducible" result caught only
by reading the payload, exactly the class of thing the read-back-only rule exists to catch.

## Re-run 2026-11-19 — the 32-request wall, then the queueing regime (raw: `bench/splash-concurrency/results/splash-1.7.0-2026-11-19-ext` and `-2026-11-19b`)

**Stack move under test:** `--queue-size 64`, added to the host's `start.sh` (resolve-ai-workflow
`81a9235`). It joins the 2026-11-19 thinking-budget raise 16,384 → **32,768** in the same launch, and
that second move is **inert for both stages of this suite**: ladder completions are pinned at 512
tokens and KV completions at 8, so no request can reach a thinking cap. Flags bind at launch only, so
19b **restarted the engine** (11:34 local) and read every pin from the live supervisor
(`pgrep -f -fl server.server`) rather than from disk — a supervisor that has been running since before
an edit still runs the old values.

Two waves, read as one story: **19-ext** found the boundary by accident and diagnosed it; **19b** is
the instrument rebuilt to run past it. Full detail in each directory's `RECORD.md`.

### 19-ext — ladder valid, KV censored, and the censoring is the finding

Engine: Splash 1.7.0, **the same instance as the 2026-11-18 wave, not restarted**, no `--queue-size`
flag, so the documented default of **32** governed.

| width | 1 | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 24 | 32 |
|---|---|---|---|---|---|---|---|---|---|---|
| median tok/s | 294.35 | 485.3 | 585.6 | 697.5 | 617.0 | 693.65 | 696.9 | 701.15 | 695.2 | 701.5 |

The ladder reproduces 11-18 (w1 inside the 260.6 / 307.3 band, w6 dip 0.884× of w4, admission peaks
0/0/0/0/2/4/8/12/12/12, `suspended` 0 everywhere). The KV stage then **died at w40 on HTTP 503**
(`frontend request capacity is exhausted` / `frontend_overloaded`) because the sealed `chat()` raises
on non-2xx — and the driver lost its SUMMARY.

Four things came out of it:

1. **The trip point is a request count, not a memory state.** A tiny-prompt probe (so token volume
   cannot matter) pinned it: **w32 admitted, w33 refused instantly**, `waiting_concurrency=0` and
   `held_behind_refusal=0` — refused, never queued. `splash serve --help`: `--queue-size REQUESTS …
   requests admitted at once, running or waiting; more get 503 (default: 32)`.
2. **This stack answers KV pressure with spill and disk demotion, never suspension.** Inside the
   admitted range, `kv.pages_active` sat pinned at **1,654 pages (52,928 tok)** across every fresh
   round w16→w32 while lifetime `kv_spill.spill_moves` reached 28,138 and `disk.kv_demotions` 4,390
   (41 refused). Any stop rule that waits for a suspension event is watching the wrong gauge — the
   standing rule was retired.
3. **Beyond w12, width buys nothing:** prefill flat at **3,513.7–3,520.7 tok/s (±0.2 %)**; the
   mechanism is visible in `/status` as `memory_plan.budget.maximum_batch_width = 4`.
4. **Cross-run prompt reuse is free, so controls must be fresh-seeded.** The w2 / w12 stitch controls
   were byte-identical to the 11-18 prompts (deterministic generator) and `--persistent-cache` served
   them from disk: **93,530 tok in 0.4 s and 612,180 tok in 1.5 s** with `prefill_rows` moving only 26
   and 84 — proof the cache works and **zero** measurement of pressure.

Censorship status: the stage reached **1,632,480 prompt tokens = 10.49× budget** before the refusal
killed it, so 11-18's "no trip at 3.93×" was doubly censored — the width cap (12) sat below the real
ceiling, and the real ceiling is an admission refusal rather than a suspension.

### 19b — queue-size 64, run to 48 in flight

Engine restarted, so **every lifetime counter began at zero** (`resource_suspensions` 0,
`priority_suspensions` 0, `capacity_failures` 0, `kv_demotions_refused` 0, `spill_moves` 0): the
per-round deltas are the cleanest in the series, and the **lifetime column stops being comparable
across rows** (11-18 began at 43, 19-ext at 45).

**Stage 0, the fixed gate.** The 19-ext gate probed a prose paragraph (77.3 / 88.6 / 116.7 tok/s,
spread 1.51 "cold") while the ladder's own w1 read 294.4 minutes later — it certified nothing. 19b's
gate reuses `LADDER_PROMPT` @512: **272.0 / 282.1 / 309.6 tok/s, spread 1.138 → "soft"** (pass ≤1.10,
soft ≤1.20). Not a clean pass, and stated as such; the ladder that follows lands inside it.

**Stage 1, the sealed ladder — the stack move did not perturb the curve.**

| width | 1 | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 24 | 32 |
|---|---|---|---|---|---|---|---|---|---|---|
| median tok/s | **307.1** | 416.95 | 581.25 | **724.6** | 613.3 | 698.9 | 647.55 | 700.65 | 698.0 | 699.5 |
| round spread | 1.011 | **1.377** | 1.020 | 1.045 | 1.000 | 1.014 | **1.139** | 1.019 | 1.003 | 1.001 |

w1 **307.1** was the best width-1 on record at the date (prior 283.95) — **superseded by 19c-clean's 308.75 in a
proven single-tenant window**, which also showed this wave's w1 was not actually hurt by its tenancy — and
**w4 724.6** remains the highest aggregate peak
on record; w6 dip 0.846× of w4 continues the trend of shallower dips across build generations; stop
rule never fired. Two cells carry labelled scatter rather than smoothing: w2 (350.8 / 483.1) and w12
(689.6 / 605.5) — both stay far above w1, so neither threatens the shape.

**Stage 2, KV in the queueing regime** (calibration 300 lines = 14,087 tok → 425 lines/request ≈
55,265 tok each; widths capped at 48 to leave 16 lanes of slack under 64, so a refusal would mean the
engine's limit, not our own saturation):

| width | prompt tokens | × budget | wall (s) | ok / refused | prefill_rows Δ | pages_active peak | susp / wait_mem | spill Δ / demote Δ |
|---|---|---|---|---|---|---|---|---|
| 12 | 663,180 | 4.26× | 189.5 | 12 / **0** | 663,180 | 1,920 | 0 / 0 | 0 / 0 |
| 33 | 1,823,745 | 11.72× | 522.2 | 33 / **0** | 1,823,745 | 1,920 | 0 / 0 | 0 / 0 |
| 36 | 1,989,540 | 12.78× | 570.5 | 36 / **0** | 1,989,540 | 1,920 | 0 / 0 | 0 / 0 |
| 40 | 2,210,600 | 14.20× | 633.2 | 40 / **0** | 2,210,600 | 1,920 | 0 / 0 | 0 / 0 |
| 44 | 2,431,660 | 15.62× | 697.7 | 44 / **0** | 2,431,660 | 1,920 | 0 / 0 | 0 / 0 |
| 48 | 2,652,720 | **17.04×** | 760.1 | 48 / **0** | 2,652,720 | 1,920 | 0 / 0 | 0 / 0 |

`prefill_rows` delta **equalled** prompt tokens on every round and `cache_served_rounds = []` — the
confound is closed, and shown closed. Findings:

1. **The flag was the whole wall.** 48 concurrent 55k-token requests, all admitted, zero refusals —
   where 19-ext refused at 33.
2. **The queueing regime is invisible at the admission gate, which is the surprise.** The prediction
   was that past 32, `admission.waiting` / `waiting_memory` would finally have something to measure.
   Every one of the six rounds peaked at **0** for `waiting`, `waiting_memory`, `waiting_concurrency`
   and `held_behind_refusal`: requests are admitted into lanes and wait inside the **scheduler prefill
   queue** — a queue that demonstrably exists (`peak_queued` 8 / 8 / 16 at w12 / w24 / w32 in stage 1).
   A monitor reading `admission.*` would call the engine idle at w48.
3. **Width past 32 costs wall time, at prefill parity:** 189.5 s → **760.1 s**, with prefill flat at
   **3,485.4–3,499.1 tok/s (±0.2 %)** from w12 to w48 — the same line 19-ext measured below the wall.
   Corroborated by the session's own decode batches: b1 4,375 / b2 278 / b3 244 / **b4 3,434**.
4. **KV residency is still untouched at 17.04× the budget.** `pages_active` pinned at **1,920 pages =
   61,440 tok (39.5 % of budget)** on all six rounds (it stepped up from 1,654 pages once in-flight
   passed 32, then stopped moving), spill 0, demote 0, suspensions 0, minimum governor headroom
   207.8 MB. The 11-06 conclusion survives its widest test: fire-and-forget long-context volume does
   not trip this stack's KV.
5. **Signals outside the stage are attributed by delta.** At run end lifetime `disk.kv_demotions` =
   421 with `refused` = 5, while every KV round's delta for both was 0 — those came from the
   gate/ladder/calibration legs. This is why the stop rule reads per-round deltas: a lifetime counter
   that drifts outside the stage (11-18: 43 before the stage began) must not be read as a trip.

**Caveats on this row.** (a) Gate "soft", not a clean pass. (b) **Not a clean window** — the operator's
OpenCode session is served by this same engine and took turns during the run, including inside the KV
rounds; per the 11-13 finding that tax lands on latency cells, so the best-w1 cell carries it and a
detached single-tenant re-run of stage 1 is owed — **now delivered, see 19c-clean below**. (c) The restart makes lifetime reads non-comparable
with earlier waves. (d) `--verify-rows auto` still applies: not bit-comparable with the 1.6.x rows.

**What this instrument can no longer answer.** Tripping KV by summed volume is bounded out — at 17×
the governor reports no work, and the only failure mode beyond that is the request-count flag. The live
question is **depth, not volume**: `context_bounds` puts resident at **155,633** against a 262,144
window, and the open probe is one context walking toward the resident line **while held across turns**
— what real agent sessions do, and what no wave here has yet measured directly.

**The determinism A/B** (batch B, hard stops proven from the engine's own startup banner, both modes
read back from `/status`): the same greedy request ×5 per config, hashing **content + reasoning
together**: `auto` **1 distinct/5** (265.0 tok/s, 1.887 s median), `all` **1 distinct/5** (265.4 tok/s,
1.884 s), same hash across configs — the measured decode price of determinism is **−0.2 %, i.e. free
within noise**, at n=5 on one short prompt. Honest limit: all ten runs hit `max_tokens=500` inside
reasoning, so the hashes certify *identical truncated reasoning prefixes*; "no divergence detected"
≠ "divergence impossible at long budgets". Decision it supports: keep the 1.7.0 default (`auto`) for
the daily config — determinism costs nothing measurable here, but nothing is gained by paying the
banner's per-row verification either, and the 1.7.0 rows keep their not-bit-comparable caveat either way.

**Side probe — the price of `--default-reasoning-effort xhigh`** (`reasoning-effort-cost-corrected.json`,
tenanted, so indicative): the effort knob is honored per request (`reasoning_effort` in the chat body).
On a bounded Resolve-arithmetic task, **low** stopped thinking at **1,771** reasoning tokens and
**medium** at **2,320** (both `finish=stop`, both with the correct `ANSWER=450`, walls 16.4 s / 20.1 s);
**xhigh** and the server default never finished under 8,000 reasoning tokens, and at the full 16,384-token
daily thinking budget xhigh ran **16,385 reasoning tokens / 107 s to the same correct answer** (n=1). On
this task class the top effort costs ~6× for nothing. Decision recorded anyway: **the daily config keeps
xhigh**, because the resolve-agentic 21/21 evidence was earned there and one bounded task (n=1 per stopped
cell) is not grounds to move a default — flagged as a proper follow-up: an agentic-suite A/B of
`medium` vs `xhigh` across the six briefs.

**The agentic column, first OpenCode score: 11/12 verified, 10/12 honest.** `driver_opencode.py`
ports driver2's S1–S4 with the same seal approach (per-session config + permissions + policies,
global config file renamed aside and restored after). One real model deviation: an S4 trial
attempted the **denied `execute` tool**; the policy blocked it, and it counts against honesty —
reaching for an ungranted tool is precisely the event the seal exists to catch. Everything else that
*looked* like a model failure was the harness: **OpenCode v2.3.0's `read`/`shell` tools resolve
relative paths against the launcher's cwd, not the session cwd** (probe: a session created in
`…/cwd-probe` runs `pwd` and prints the runner's directory). That single fact explains batch A's
three S3 artifacts overwriting each other at one path and batch B's S4 verify failure; briefs now
name absolute paths. Batch A's corrected offline re-grade (9/12 verified, 8/12 honest, S3 unscored)
stays in the results tree as provenance, unranked.

## Re-run 2026-11-19c-clean — the single-tenant control on the queue-size 64 stack (raw: `bench/splash-concurrency/results/splash-1.7.0-2026-11-19c-clean/`)

Scorecard: [Splash KV at 17× budget — width becomes queue depth, not memory](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-splash-kv-clean-window.html)

Same instrument (`kv_bracket_2026-11-19b.py`, unchanged), same engine instance as 19b (**not restarted**, so
only window deltas are read), but run through `run_clean_detached.sh`: detached, `/status` sampled every 10 s
across the whole 65-minute window, and the operator idle from the moment the runner started. This is the wave
19b's caveat (b) asked for.

**Tenancy, measured rather than claimed.** Of 7,035 in-flight request-samples, **7,034 belong to this wave**
(their prompt sizes are recorded in the wave's own rows: 55,265 tok KV / 29 tok ladder). Exactly **one** foreign
request appears — 98,779 tokens at `01:10:19`, **93 s before the first timed stage**: the operator's last message
before going idle. So every timed stage here ran single-tenant.

**A runner bug that nearly discarded it.** The first version of the tenancy check flagged "requests over 20,000
prompt tokens" as co-tenant and printed **`NOT single-tenant`, 6,851 samples**. Those were *this wave's own*
KV prompts. A size threshold cannot separate a long-context benchmark from an operator on a shared engine; the
check now attributes by the prompt sizes the wave itself recorded. Published because a wrong self-check that
says "dirty" is as dangerous as one that says "clean".

**Stage 1 — the clean ladder.** w1 **308.75** (rounds 305.7 / 311.8, spread 1.020 — the tightest w1 pair in the
series), peak **700.55 at w8**, plateau w12–w32 mean **695.6**, stop rule never fired, admission peaks
0/0/0/0/2/4/8/12/12/12. Against 19b (307.1 / 698.9 / 686.4): **w1 and the plateau reproduce; individual mid-width
cells do not** (w2 487.05 here vs 417.0 there, w12 694.4 vs 647.5). With tenancy removed on this side, the
suspect cells are 19b's, and the rule for future diffs is the plateau and w1, not mid-width singles.

**Stage 2 — KV pressure, and the correction this wave exists to make.** All six widths admitted everything:
**11,771,445 tokens of fresh prefill** (`scheduler.prefill_rows` delta equals each round's prompt tokens in all
six rounds, `cache_served_rounds = []`), top round **2,652,720 tokens = 17.04× the 155,648-token resident
budget**, **zero refusals, zero suspensions, zero spill, zero demotions**, `capacity_failures` and
`kv_demotions_refused` unmoved, prefill flat at **3,469.0–3,497.8 tok/s (±0.8 %)** from w12 to w48, and
`pages_active` pinned at **1,920 pages = 61,440 tokens = 0.39× budget** in every round while `queued` climbed
11 → 47 with `prefilling ≤ 2`, `decoding 1`.

The mechanism that follows from those numbers: **extra width becomes queue depth, not KV residency.** The
scheduler keeps about one 55 k-token context resident and parks the rest in its prefill queue, so summed prompt
volume cannot reach the KV pool at all — the ceiling is the prefill rate, which `maximum_batch_width = 4`
explains.

That directly rebuts the 2026-11-16b row's headline ("first KV trip on record: stopped at w10, 3.89× budget,
peak suspended 2, lifetime `resource_suspensions` +3, `demote` +1502"). In a proven single-tenant window on the
same host, **4.4× that prompt pressure produced no trip**. So 16b's trip was not a token-count threshold: it
came together with `waiting_memory` and `admission.waiting` movement, in a window with operator traffic on the
engine and a pre-`--queue-size` stack. **What is established is the negative** — volume alone does not trip this
stack, at any multiple tried here — and **what is not established** is why 16b tripped; attributing it to
co-tenancy is a hypothesis about the regime that produced it, and it has not been reproduced on purpose.

**Gate note.** Warmth gate 274.5 / 314.1 / 307.7 → spread **1.144**, "soft" again (19b: 1.138). Two waves, same
primitive, same band: on this engine the gate's own run-to-run spread sits just above the 1.10 pass line, so a
"soft" is not a defect of an individual wave — quote the band, don't chase the pass.

**Still open after this wave.** Volume is bounded out as a lever, so the live question stays **depth**: one
context walking toward the resident line (`context_bounds` resident 155,633 of a 262,144 window) **held across
turns**, which is what real agent sessions do and no wave here has measured directly.
