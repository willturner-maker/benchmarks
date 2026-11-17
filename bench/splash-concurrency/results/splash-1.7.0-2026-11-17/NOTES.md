# Splash 1.7.0 rerun — 2026-11-17 (three passes; pass 1 warm-up, passes 2–3 scored)

**Engine (version-confirmed, not assumed):** `splash --version` → **Splash 1.7.0**; corroborated by the
live process path `/opt/homebrew/Cellar/splash/1.7.0/libexec/…` (PID 1359, started 09:10:50 local,
weights loaded in 2.90 s). `/status` schema **8** (unchanged since 1.6.0, so `splash-dashboard` keeps
parsing it). Release 1.7.0 published upstream 2026-11-17 12:42 UTC — same-day install.

**Engine args at run:** `--max-memory=60129542144` (56 GiB) · `--max-cache-disk=274877906944` (**256 GiB**,
not the 128 GiB the results doc header has been quoting) · `--persistent-cache` ·
`--default-reasoning-effort=xhigh` · `--thinking-token-budget=16384`. No `--activations`, no
`--cached-states`, no `--verify-rows` override → all engine defaults (`--verify-rows auto` is stated in
the startup log).

**The upgrade reset, recorded not inferred.** Startup log line 8:

```
09:10:58 Persistent cache ~/Library/Caches/Splash/prefix-cache/c1cb917d9d464d6595b9c2db5a834158:
         took back 0 restore points over 0 KV blocks (0 MiB); left 0 copies behind.
```

Same cache-dir hash as the 1.6.x era (model identity unchanged, weights not re-downloaded) but zero
restore points — the release note's "persistent caches from 1.6.x start cold once" is what happened.
This is why the suite is run more than once here, and why a single pass would have understated 1.7.0.

## Warmth (the gate before any number is read)

| | before pass 1 (cold) | after pass 1 | before pass 2 | after pass 2 | before pass 3 | after pass 3 |
|---|---|---|---|---|---|---|
| `cache.hit_rate` | 0.8750 | 0.9661 | 0.9662 | 0.9826 | 0.9826 | **0.9883** |
| `cache.hits` / `cold_misses` | 14 / 2 | 285 / 10 | 286 / 10 | 565 / 10 | 566 / 10 | **846 / 10** |
| `cache.kv_disk_hit_tokens` | 0 | 0 | 58,080 | 2,124,640 | 2,186,816 | **4,253,728** |
| `disk.read_bytes` | 0 | 0 | 0.8 GB | 27.8 GB | 28.6 GB | **55.8 GB** |
| `disk` cache on disk | 0.7 GB | 29.8 GB | 29.8 GB | 30.1 GB | — | 30.1 GB |
| `kv.pages_cache` | 1,766 | 4,095 | 4,094 | 4,095 | 4,606 | 4,094 |

**Warm, declared after pass 3.** Decisive signal: `cold_misses` is **frozen at 10 from pass 1 onward** —
every prompt the suite submits is cached, so nothing new can be learned from another pass. Corroborated
by plateau mean drift +0.2 % (pass 1 → 2) and −1.5 % (pass 2 → 3), `thermal_state: nominal`,
`memory_pressure: normal`, and the SSD tier serving (4.25 M tokens, 55.8 GB read back).

Note for future runs: my first pass of this suite set a criterion "disk hits > 0" and then nearly
dismissed it as unreachable, because the RAM prefix cache (4,095 pages) was holding everything. That was
wrong — eviction did occur mid-pass 2 and the disk tier then carried 2.1 M tokens. Disk hits appear once
the working set exceeds the RAM ring; they are reachable inside a run, just not in the first pass.

## Ladder (v3 spec: 512-token rounds, 2 rounds/width, median)

| width | pass 1 | pass 2 | pass 3 | **median** | spread |
|---|---|---|---|---|---|
| 1 | 233.2 | 219.8 | 207.5 | **219.8** | 12.4 % |
| 2 | 320.9 | 312.0 | 343.2 | **320.9** | 10.0 % |
| 3 | 405.5 | 429.4 | 394.1 | **405.5** | 9.0 % |
| 4 | 525.3 | 548.1 | 526.5 | **526.5** ← peak | 4.3 % |
| 6 | 419.9 | 430.4 | 450.1 | **430.4** (0.82× of w4) | 7.2 % |
| 8 | 485.3 | 486.2 | 452.4 | **485.3** | 7.5 % |
| 12 | 485.9 | 494.2 | 495.1 | **494.2** | 1.9 % |
| 16 | 471.2 | 481.6 | 481.8 | **481.6** | 2.2 % |
| 24 | 494.6 | 479.2 | 478.1 | **479.2** | 3.5 % |
| 32 | 479.2 | 480.4 | 476.8 | **479.2** | 0.8 % |

Plateau (w8–32) means: 483.2 → 484.3 → 476.8; **pooled median 481.6, band 479–494**. Stop rule never
fired in any pass. `peak_admission_waiting` 0 at every width ≤ 4 (matches history).

Shape vs 1.6.1: **aggregate peak moves back to width 4** (1.6.1 waves peaked at w8/w12) and the **w6 dip
comes back** — 0.799 / 0.785 / 0.855 × of w4 across the three passes, where 1.6.1's clean-window wave had
it at 0.97× and 1.6.0 at 0.87×. Two consecutive build generations moved this shape in opposite
directions, so treat the w6 dip as instance/shape-sensitive, not a regression signal.

**w1 caution:** w1 declined monotonically across passes (233.2 → 219.8 → 207.5) while the plateau held.
With a 12.4 % spread this is the suite's noisiest cell, and history supports reading it as instance state
(the 2026-11-16b wave logged 92.6 tok/s at w1 with a *higher* plateau). Median 219.8 is still above the
209.5 best-on-record from 1.6.1, but the trend is the wrong direction and one more wave should confirm.

## engine_probe (single-stream decode + TTFT)

| pass | decode w1 passes (tok/s) | median | TTFT "cold" | TTFT warm-prefix |
|---|---|---|---|---|
| 1 | 149.0 / 189.5 / 166.5 | 166.5 | **291 ms** ✓ valid | **110 ms** |
| 2 | 186.1 / 185.8 / 174.3 | 185.8 | 122 ms ✗ invalid | 118 ms |
| 3 | 82.6 / 166.3 / 164.9 | 164.9 | 138 ms ✗ invalid | 118 ms |

- **The `cold` row is only meaningful in pass 1.** Passes 2–3 re-submit a prompt the previous pass already
  cached (122/138 ms are warm hits wearing a cold label). The comparable cold figure is **291 ms**
  (baseline 380, best prior 229). Warm **110–118 ms** is the best warm TTFT recorded on this host by a
  clear margin (prior best 151 ms).
- **Outlier, not discarded silently:** pass 3's first decode row, **82.6 tok/s**. Its shape is the classic
  tenancy transient seen in the 11-11h wave (81.6 / 80.7), and my own session was generating during pass 3.
  Pooled n=9 median is 166.5; excluding that one row the 8-pass median is **170.4** (mean 171.6). Both
  figures are recorded; the 82.6 row stays in `pass3-engine_probe.jsonl`.
- **probe/ladder ratio** per pass: 0.714 / 0.845 / 0.795. The historical constant is 0.745–0.760, so the
  harness relationship still holds within noise (pass 1's 0.714 is the cache-cold pass).

## KV pressure (v4) — invariants, not timings

`resident_kv_budget_tokens` **155,648** (1.6.0/1.6.1 waves: 139,264 / 131,072 — the INT8 cached-state work
raised the resident budget ~19 %). 611,244 prompt tokens at w12 = **3.93×** that budget.

- **No trip in any pass:** `admission.suspended` peak 0, lifetime `resource_suspensions` /
  `priority_suspensions` deltas 0 every round, `capacity_failures` 0, `kv_spill.spill_moves` 0.
  1.7.0's "free idle cache to admit a waiting session" behaviour did not regress the negative result.
- Memory path was **quieter than 1.6.1**: `disk.kv_demotions` +11 total (w4 +1, w10 +10, passes 2–3),
  **0 in pass 1** (uncached), 0 in pass 3 — against 1.6.1's +382/+645/+97 at w6/w10/w12.
- `waiting_memory` peak 1 appears from w6 upward in the *cached* passes (not in pass 1) with zero
  suspensions — a hold, never a suspension; `pages_active` peak 1,647 in pass 1, 3,184 in passes 2–3
  (cached rounds hold more pages because prefill is skipped, not because memory is tighter).
- **KV-stage wall times are NOT comparable across passes here:** w12 172.6 s (pass 1, uncached) → 2.1 s
  (pass 2, cached) → 2.0 s (pass 3). Only pass 1 measures prefill. That uncached wall — **611,244 tokens
  in 172.6 s** — matches 1.6.1's 170.5–171.5 s and 1.6.0's 171.1 s: **prefill is unchanged**, so the 1.7.0
  gains are decode-side, consistent with the release notes' draft-tree verification claim.

## Prefix-cache reuse (extra probe, 2026-11-17, to check the workflow README's cache claim)

A ~9.7k-token shared-prefix stand-in for a fresh agent session's system+tools block, submitted as three
"sessions" (`usage.prompt_tokens_details.cached_tokens` read back, never from a model's claim):

| request | prompt tokens | cached | reuse | wall (8-tok out) |
|---|---|---|---|---|
| session A, cold prefix | 9,683 | 32 | 0.33 % | 2,682 ms |
| session A, repeat | 9,683 | 9,664 | **99.80 %** | 111 ms |
| session B, same prefix + new tail | 9,690 | 9,664 | **99.73 %** | 125 ms |

Cross-session reuse is intact on 1.7.0 and works at page granularity (9,664 = 75.5 × 128-token pages).
Uncached prefill of 9,683 tokens in 2,682 ms = **3,611 tok/s**. Scope limit, stated plainly: this verifies
the *mechanism* at 9.7k tokens; it does **not** re-measure the "20–45k cached tokens per fresh agent
session" figure, which is the real OpenCode session prefix size and needs the agentic driver for that.

## Conditions, deviations, comparability

- **Tenancy (disclosed, this row's main weakness):** all three passes overlapped with the operator's
  OpenCode session, which is served by the same engine — turns were taken between and during passes
  (the pass-3 82.6 tok/s row is the visible cost). This is **not** the 2026-11-13 clean-window condition,
  where the driver ran detached and the operator session made zero turns. Per that wave's own finding the
  tenancy tax lands on latency figures, not saturated-decode aggregates, so the plateau is trustworthy
  while the w1/TTFT cells carry an overlap tax. A strictly clean 1.7.0 row still needs a detached pass.
- **Resolve Studio not running** (only the idle ResolvePython MCP helper), so no GPU/VRAM co-tenancy.
- **Determinism:** `--verify-rows auto` is active, stated at startup ("greedy and seeded outputs can
  differ from run to run"). Together with 1.7.0's INT8 cached states and 1.6.1's INT8 activations,
  **this row is not bit-comparable with the 1.6.0 or 1.6.1 rows.** A bit-reproducible 1.7.0 row needs
  `--verify-rows all` on a fresh cache dir.
- Engine never restarted mid-suite (three passes on one instance), per spec.
- Runner: `/opt/homebrew/opt/python@3.12/bin/python3.12 -I engine_probe.py` (via `SPLASH_BENCH_OUT`) then
  `… -I ladder_kv.py --out <jsonl>`; identical spec to prior waves.
- Files: `warmup-*` = pass 1, `engine_probe.jsonl`/`ladder_kv.jsonl` = pass 2, `pass3-*` = pass 3;
  `status-*.json` are the full `/status` snapshots behind the warmth table; `*.log` are the stage stdout.
- **Publishing redaction (disclosed):** the runner echoes its `--out` path, which under this repo's
  publish policy carries a home directory. In the committed `ladder.log`, `pass3-ladder.log` and
  `warmup-ladder.log` that one path per file is rewritten to `~/benchmarks/…`; nothing else in those
  logs was touched, and no measurement line changed. The `status-*.json` snapshots were checked — they
  contain no home paths.

## Headline for the next version's diff

Splash 1.7.0, warm, same host/model/spec: **ladder w1 219.8 · plateau 479–494 (pooled median 481.6, peak
w4 526.5) · warm TTFT 110–118 ms · cold TTFT 291 ms (pass 1 only) · probe decode 170.4 tok/s (8 rows,
outlier excluded) · KV budget 155,648 tokens with no suspension at 3.93× and near-zero demotions ·
prefill unchanged.** Vs the best 1.6.1 clean-window row: w1 +4.9 %, plateau +1.7 %, warm TTFT −26 %,
cold TTFT +27 %, KV budget +18.8 %, demote path quiet (was +1,124 blocks).
