# BFCL v4 — Results (suite debut 2026-11-24, wave bfcl-23a-2026-11-23)

**Purpose:** put the tool-calling axis that the [tool-loop gate](tool-loop-gate-benchmark-results.md)
measures privately onto the live public scoreboard — BFCL v4
([`ShishirPatil/gorilla`](https://github.com/ShishirPatil/gorilla),
`berkeley-function-call-leaderboard/`), the longest-running function-calling leaderboard, with an
explicit path for self-hosted OpenAI-compatible endpoints.

**Instrument:** pinned **commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`** (2026-03-23). The repo
publishes no tags, so the commit is the pin and clone-side drift is impossible to hide behind a
version string. The clone is **unmodified**: our model is registered at runtime
(`bench/bfcl/bfcl_splash.py` injects one `ModelConfig` entry into their mapping and calls their own
CLI) — the only inference-side addition; scoring code and all test data are theirs.

**Engine:** Splash 1.7.1, pinned argv unchanged, warm cache, served at `127.0.0.1:8000` over the
OpenAI-compatible API. `temperature 0`, `--num-threads 3` (inside the engine's
`maximum_batch_width = 4`). FC-mode build series: native `tools=` calls (the engine serves them
natively; reasoning stays on its separate stream, `content` is clean).

## The score (4,441 task-runs, 17 categories, 3 h 37 m)

**Overall 40.85%** — their scorer's composite **over the categories run** (non-live AST + live +
multi-turn + irrelevance/relevance). Note the live board's *Overall* column additionally folds in
**Web Search + Memory** (the two groups excluded here) — see board context below; 40.85 is not the
board's Overall formula.

| group | categories (acc %) | group acc |
|---|---|---|
| non-live AST | simple_python 94.5 · simple_java 60.0 · simple_javascript 66.0 · multiple 92.5 · parallel 92.5 · parallel_multiple 89.0 · irrelevance 79.2 | **86.88** |
| live (user-contributed) | simple 79.5 · multiple 78.0 · parallel 68.8 · parallel_multiple 58.3 (n=24) · irrelevance 75.6 · relevance 81.3 | **77.79** |
| multi-turn (state-graded envs) | base 64.0 · miss_func 53.0 · miss_param 47.5 · long_context 57.5 | **55.50** |

Infrastructure: **0 errors** across 4,441 entries (one empty model response counted as a miss);
engine samples normal/nominal with zero admission waits. Latency: their per-request mean 2.77 s /
p95 6.6 s; entry-level, multi-turn entries (20–30 env steps) run 16–60 s typical.

## What it says

1. **The tool-loop gate's predictions held at board scale.** The gate's two fixed weaknesses —
   error recovery after a failed call, and nested/multi-arg schema fill — are exactly the weakest
   board categories: `multi_turn_miss_param` 47.5 and `multi_turn_miss_func` 53.0. And the gate's
   clean abstention result shows as the *irrelevance* miss rate: the model still calls *something*
   ~23% of the time when the correct answer is no call at all.
2. **A clean language axis.** The same single-shot calling skill scores 94.5 in Python, 66 in
   JavaScript, 60 in Java — argument-type conventions (`int` literals, enum strings) are where the
   small quant trips, not call structure.
3. **Long-context cost at IQ3_S is mild:** long_context 57.5 vs base 64.0 — the multi-turn drop is
   mostly task difficulty, not context length.
4. **Board context (verified against live board data, fetched 2026-11-24; corrects our earlier
   secondary-source claim):** the live board (snapshot 2026-04-12, rows evaluated at their commit
   `f7cf735` = `bfcl-eval==2025.12.17` — a slightly older checkpoint than our pin `6ea5797`, so
   treat as approximate) is led by **Claude-Opus-4-5 at 77.47 overall**. Our earlier "~88.5%
   leader" line was wrong — that number is the leader's *non-live AST column*, not its overall.
   Apples-to-apples on the groups we share: **Non-Live AST (board def, `simple` pooled across
   languages n-weighted) 89.50 → ~7th of 109**, above the current leader's 88.58; **Multi-Turn
   55.50 → ~13th**; **Live 71.15 (4-AST-sub average; the board's column also folds live
   irrelevance/relevance case-weighted, which lifts us into the mid-70s → rank ~45–54)** — our
   genuinely weak board axis. Shared-three-group average **72.05 → ~15th of 110**, sitting between
   Claude-Haiku-4-5 (72.93) and Qwen3-32B (72.88). The 40.85-vs-77.47 gap is mostly *structural*:
   board Overall is a 5-way average including Web Search + Memory, which crush small models
   (Qwen3-8B: WS 12.0 / MEM 14.6 drag a ~70 profile to 42.6 overall). If we ever run those groups
   at Qwen3-8B class, our estimated board Overall ~48.6 (~rank 35).

## Comparability rules

- **Pin the commit, not a version** (no tags upstream). A wave's row carries: instrument commit,
  engine build + argv, venv note, handler class, FC-vs-prompt mode.
- **FC-mode and prompt-mode are different build series** — never compare rows across them.
- **Harness delta is one runtime registry entry** (documented in `bfcl_splash.py`); if upstream
  ever ships a custom-model path, retire the wrapper and record the series break.
- **Exclusions are standing:** `web_search_*` (external engine → not reproducible here),
  `format_sensitivity` (non-scoring); `memory_*` deferred, not excluded — if ever run, they join as
  extra columns, never inside the official overall.
- **Decode-regime disclosure travels with the row:** hosted rows decode near-deterministically at
  temp 0; our engine's temp-0 action lottery (documented in the
  [tau2 determinism probe](tau2-bench-benchmark-results.md)) means repeated waves would spread;
  single-wave deltas inside a category are noise: **measured band from the bfcl-24a repeat
  wave is ~±3.5 pts at n≥200** (multi-turn moves are block-correlated, not per-task), with
  the composite overall moving only ~±1 pt wave-to-wave. A future category delta must clear
  ~3.5 pts to count as real.
- **Their cost column is synthetic** for price=None rows; ours is self-hosted (marginal ≈ 0).

## Reproduce

See `bench/bfcl/RECORD-bfcl-23a-2026-11-23.md` relaunch block — clone, venv rebuild, one generate +
one evaluate command. The whole instrument (clone, venv, wrapper, smoke evidence) lives at
`<volume>/local.AI/bench/BFCL/` (layout and pins: that volume's `bench/README.md`).

## Wave index

| wave | date | scope | overall | notes |
|---|---|---|---|---|
| bfcl-23a | 2026-11-24 (launched 2026-11-23) | full v4 scoring set (17 cats, 4,441 runs) | **40.85%** | debut; memory cats deferred |
| bfcl-24a | 2026-11-24 | repeat of 23a, identical build — temp-0 band measurement | 40.12% (Δ-0.73 vs 23a) | band: ±3.5 pts/category at n≥200, ±1 overall; RECORD-bfcl-24a |

Row submission to the public board filed: **gorilla issue [#1400](https://github.com/ShishirPatil/gorilla/issues/1400)**
(artifacts gist + repro block; open questions on checkpoint `f7cf735` vs our pin, partial-row rendering,
handler form). If a re-run at their checkpoint is required, it's the same scripted ~4 h wave.
