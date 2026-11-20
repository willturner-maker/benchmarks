# tau2-bench smoke — 2026-11-19

**Instrument:** `sierra-research/tau2-bench` **pinned at tag `v1.0.1`** = `fc0055dc4e0a316c3f83133267fbd6faaa770992`
(2026-07-16, "chore: prepare release v1.0.1 — banking_knowledge grading fixes (#408)"). Clone at
`~/tau2-bench`, **outside** the published repo, **unmodified** (`git status` clean). Env from
`uv sync` (uv-managed, Python 3.12, litellm 1.81.11). The pin is echoed inside every run's own record
(`info.git_commit`), so a reviewer can verify the pin from the artifact rather than from my word.

**Why v1.0.1 and not 2.x:** the reward path can be judge-free. Airline (50 tasks) scores as
`[DB, COMMUNICATE]` = end-state **DB hash** + **substring** check; telecom (114 base / 2,285 full) scores as
`[ENV_ASSERTION]`, replayed in-process; retail is `[DB, NL_ASSERTION]` but **74 of its 114 tasks carry no
`nl_assertions`** so their NL evaluation short-circuits — only 40 need an LLM judge. See `RECORD.md` for the
census and for why those 40 can't run locally on 1.0.1 as shipped. (I initially over-claimed that all three
domains were `[DB, COMMUNICATE]`; the census above is the corrected statement.) 2.x makes communication
checks semantic/LLM-judged by default and replaces 50 reviewed retail + 50 telecom tasks under the same ids,
so a 2.x row is not diffable against the 1.x leaderboard. Upstream: *"Scoring change — scores are not
comparable with 1.0.1"* and *"No flag combination reproduces 1.0.1 inputs exactly."*

## Engine under test

Splash 1.7.0, `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, `127.0.0.1:8000`, same launch as
Splash wave 19b (`--queue-size=64`, `--thinking-token-budget=32768`,
`--default-reasoning-effort=medium`, `--persistent-cache`). No restart for this smoke; lifetime counters
are shared with the operator session and are therefore reported as deltas + high-water, never as totals.

## Invocation (no patch to the instrument)

```
M='openai/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S'
A='{"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":2048}'
uv run tau2 run --domain mock --agent-llm "$M" --user-llm "$M" \
  --agent-llm-args "$A" --user-llm-args "$A" \
  --num-tasks 4 --num-trials 1 --seed 300 --max-concurrency 2 --save-to smoke-mock-2026-11-19
```

Then the same for `airline`, `retail`, `telecom` at `--num-tasks 5 --max-concurrency 3 --max-steps 60`.

LiteLLM splits the model string at the **first** `/`, so the engine receives the full
`ISTA-DASLab/…:IQ3_S` id (colon included), which is what the engine requires — verified directly
(`model` echoed back, `finish_reason: tool_calls`, real `tool_calls` array).

## Confounds stated up front

1. **Self-play.** The same local model plays both agent and user. τ² leaderboard rows are
   cross-model (their user simulator is a frontier model). This measures our engine's
   tool-and-dialogue behavior under a cooperative-but-weak user, not a leaderboard-comparable pass^k.
2. **Co-tenancy during this smoke.** The operator session (this chat) was live on the same engine, and
   one in-flight operator request carried **221,058 prompt tokens** in `kv_mode: spill`. Engine-side
   residency/spill/demote counters during this window are therefore **not attributable to τ²**; only the
   per-call `prompt_tokens` inside τ²'s own record are clean. A detached, operator-idle re-run is required
   before any KV-residency claim is published from this suite.
3. **Small sample.** 5 tasks/domain, 1 trial. Not pass^k, not a score.

## Files

- `sample_engine.py` — `/status` sampler (10 s cadence) → `engine_samples.jsonl`
- `analyze.py` — re-derives mean reward / DB match / termination from the τ² record, prints the per-call
  **depth** curve, and joins the engine samples (high-water widths, spill/demote deltas, admission peaks)
- `supervisor_pins.txt`, `status_before.json`, `status_after.json`
- τ² records stay in the clone: `~/tau2-bench/data/simulations/smoke-{mock,airline,retail,telecom}-2026-11-19/results.json`
