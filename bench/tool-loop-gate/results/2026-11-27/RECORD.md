# Tool-loop gate — 2026-11-27 (Splash 1.7.3 epoch row)

First hermes-track row since the 11-26 hold note ("held until an upstream OpenCode patch
lands"): the patch (opencode 2.4.2) is installed and was exercised across agbench-26b/27a/27b,
and the loop gate itself is engine-direct HTTP — the OpenCode harness is not in its path —
so the hold condition is satisfied and does not bind this instrument.

## Pins & stack proof
- Engine pins read from the **running supervisor** (`supervisor_pins.txt`): Splash **1.7.3**
  (`/opt/homebrew/Cellar/splash/1.7.3/...`), model `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`,
  pinned argv (max-memory 60129542144, persistent-cache, default-reasoning-effort=medium,
  thinking-token-budget=32768, queue-size=64). First scored row on the 1.7.3 engine for this track.
- Instrument: `hermes_loop_gate.py` sha256 `d108937b8cdee86e849be60f18da119b8ee92ff91dfc6350b261f1a44b88eeb4`
  — **byte-identical to the pinned commit** `6dc6f0e5…` despite the clone sitting at a newer
  HEAD (`b11371d6`): the instrument is unmodified across the drift.
- venv: rebuilt 2026-11-27 at the clone (`python3.12` + httpx 0.29.0 only) — the 11-23 venv was gone.
- `status_before.json` / `status_after.json` captured around both passes.

## Result — 40 task-runs, band holds, parse-fail streak continues
| pass | score | mean_tools | hit_cap | parse_fail | dup | stub_pct | llm_calls | med latency |
|---|---|---|---|---|---|---|---|---|
| defaults (t0.6/top_p0.95/top_k64) | **16/20 (0.80)** | 3.55 | 1 | 0 | 2 | 21 % | 67 | 0.82 s |
| greedy (t0/top_p1/top_k1) | **14/20 (0.70)** | 2.50 | 1 | 0 | 1 | 38 % | 67 | 0.52 s |

- **Band**: 11-19a (1.7.0) defaults 0.70–0.75, greedy 0.75×4; 11-23 (1.7.1) defaults 0.75,
  greedy 0.80. Today: defaults +1 task, greedy −2 tasks. At n=20 the suite's single-wave noise
  rule covers ±1; the greedy −2 sits at the band edge — **no epoch effect claimed**, and the
  task-level view below shows movement is task churn, not capability shift.
- **parse_fail = 0 on both passes** — the tool-call-emission-unbroken streak holds across all
  three engine epochs (1.7.0 → 1.7.1 → 1.7.3).
- always-fail set shrinks 4 → 3: `17_mkdir_then_write` passed on defaults (2 tools) after
  failing every pass of both prior waves; it still fails on greedy (1 tool, wrong order).
  Still-always-fail: `03_missing_then_adapt`, `06_chain_search_read`, `08_no_delete` — the
  same three grader-shape/behavior suspects documented in the suite doc.
- Per-pass task flips vs the 11-23 always-fail set: defaults recovers 17; greedy loses
  13_schema_terminal (8 tools — it thrashed where it passed before), 16, 17. Consistent with
  the documented within-epoch trace churn at these tasks.
- Stub confound continues: 21 %/38 % of replies were tool stubs (11-23 comparison is in the
  suite doc's stub section); greedy's higher stub share tracks its higher failure count.

## Deviations
- **Runner path quirk (instrument, not measurement)**: `run_gate.sh` runs the gate with
  `cd "$UP"`, so a *relative* wave dir makes the gate's `--output` path dangle in the clone
  dir — all 20 tasks ran and the final JSON write crashed (exit 1, twice). Fix: pass an
  absolute wave dir (as done here). Candidate runner patch: absolutize `WAVE` at entry like
  tau2's `run_wave.sh` does. Two aborted runs ran tasks against the engine but produced no
  output files; they are disclosed here (engine counters were unaffected beyond those runs).

## Verdict
1.7.3 epoch row lands inside the historical band with zero parse failures; no epoch effect
claimed from a single n=20 pass pair. Evidence: this dir (`summary.json`, `wave.jsonl` 40 rows,
re-derivable with `summarize.py`, `supervisor_pins.txt`, status before/after).
