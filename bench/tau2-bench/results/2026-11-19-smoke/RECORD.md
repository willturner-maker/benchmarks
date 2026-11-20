# tau2-bench v1.0.1 smoke — 2026-11-19 (diagnostic, NOT a score)

Engine: Splash 1.7.0, `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, `127.0.0.1:8000`, the **same
launch** as Splash wave 19b (`--queue-size=64`, `--thinking-token-budget=32768`,
`--default-reasoning-effort=medium`, `--persistent-cache`). No restart. Supervisor line captured in
`supervisor_pins.txt`; `/status` snapshots in `status_before.json` / `status_after.json`.

Instrument: `sierra-research/tau2-bench` @ **`v1.0.1`** = `fc0055dc4e0a316c3f83133267fbd6faaa770992`, cloned
at `~/tau2-bench`, unmodified, `uv sync` env (Python 3.12, litellm 1.81.11). Each record echoes
`info.git_commit` = the pin, so the pin is verifiable from the artifact.
Tree state: **no source files edited**; `uv sync` rewrote 2 lines of `uv.lock` (`revision 3→5`,
`version "1.0.0"→"1.0.1"`), which is tool drift, not a patch, and is left in place.

## What ran

`tau2 run --domain <d> --agent-llm "$M" --user-llm "$M" --agent-llm-args "$A" --user-llm-args "$A"
--num-tasks 5 --num-trials 1 --seed 300 --max-concurrency 3 --max-steps 60`
with `M=openai/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S` and
`A={"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":2048}`.
Self-play: the engine is both agent and user simulator.

| domain | sims | scored | mean reward (scored) | completions | tool calls | tool errors | max depth (prompt tok) | sim wall | termination |
|---|---|---|---|---|---|---|---|---|---|
| mock | 4 | 4 | 1.0000 | 25 | 9 | 0 | 1,225 | 23 s | 4 user_stop |
| airline | 5 | 5 | **1.0000** | 75 | 50 | 0 | 10,531 | 324 s | 5 user_stop |
| retail | 5 | **2** | 1.0000 | 29 | 11 | 0 | 10,349 | 97 s | 2 user_stop, **3 infrastructure_error** |
| telecom | 5 | 5 | **0.6000** | 137 | 71 | 1 | 10,810 | 271 s | 3 user_stop, **2 max_steps** |

Totals: 19 sims, 16 scored, 266 completions, 141 tool calls, 1 tool error. τ²'s own printed summaries
agree with the recomputed values. The per-simulation rows are in `tasks.jsonl` (19 rows, built by
`../../build_rows.py`, so this table is re-derivable by a reader); `smoke_summary.txt` is the aggregate
printed by the pre-wave analyzer, whose logic now lives in the published `summarize.py`.

- **No truncation**: max `completion_tokens` 1,162 vs the 2,048 cap — 0 sims at the cap, so the `max_tokens`
  I passed never bit (engine thinking counts inside completion tokens: the probe call showed
  `reasoning_tokens: 48` of 85).
- telecom's 2 failures were `max_steps` at my `--max-steps 60`; upstream default is 200, so a real wave uses
  the default and those 2 are not evidence of task failure.
- retail's 3 failures are **instrument**, not model: `litellm.NotFoundError: model gpt-4.1-2025-04-14 not
  found`, 3 retries each, recorded as `termination_reason: infrastructure_error`, `reward: null`.

## The reward-path census (this corrects what I said before running it)

I earlier stated that on 1.x airline/retail/telecom default to `reward_basis = [DB, COMMUNICATE]`. **That is
only true for airline.** Census of the pinned task files (`data/tau2/domains/<d>/tasks.json`, default
`base` split; splits: airline 50, retail 114, telecom 114 base / 2,285 full / 20 small):

| domain | tasks | `reward_basis` | LLM judge in the reward path? |
|---|---|---|---|
| airline | 50 | `[DB, COMMUNICATE]` ×50 | **No** — DB end-state hash + substring. All 50 do *define* `nl_assertions`, but `ALL` only runs the NL evaluator when `NL_ASSERTION ∈ reward_basis`, so they are never judged |
| retail | 114 | `[DB, NL_ASSERTION]` ×112, `[DB]` ×2 | **40 of 114 yes** — the NL evaluator short-circuits ("No nl_assertions to evaluate") for the other 74 |
| telecom | 114 (base) | `[ENV_ASSERTION]` ×112, `[ENV_ASSERTION, ACTION]` ×2 | **No** — in-process env assertions replayed; no DB, no judge |
| mock | 10 | mixed, no NL basis | No |

So a **fully local, judge-free** τ² run covers airline (all 50), telecom (all of them), and **74 of 114**
retail tasks. The 40 retail judge tasks cannot run locally on 1.0.1 as shipped: `DEFAULT_LLM_NL_ASSERTIONS
= "gpt-4.1-2025-04-14"` is a plain constant in `src/tau2/config.py` with **no env override and no CLI flag**
in v1.0.1 (checked: no `getenv` in config.py, no `--*-llm` judge flag in `cli.py`).

Note the split counts are a coincidence, not the boundary: retail `train`=74 / `test`=40 is **not** the same
set as the 74 judge-free / 40 judged tasks (verified by set comparison). So `--task-split-name train` is not
a judge-free switch.

Options for a real wave (decision pending): (a) publish the **judge-free subset** — airline 50 + telecom
114 + retail 74, with the 40 excluded and the reason stated; (b) front the engine with a local LiteLLM proxy
whose `model_map` resolves `gpt-4.1-2025-04-14` → our engine id (tau2 stays unmodified; **self-judged**, must
be disclosed); (c) engine-side model alias — not available here: the supervisor accepts a single `--model`
(`--binary --model --port --relaunch-context --serve-record` are the only flags) and `/v1/models` lists one
id, so this would need a relaunch, which we are avoiding.

## KV depth: the answer this suite was partly meant to produce

Per-call `prompt_tokens` from τ²'s own records (clean; not affected by co-tenancy): median 5,955 (airline) /
5,341 (retail) / 6,607 (telecom), **max 10,810 = 0.07× the 155,648-token KV budget, 0.04× the 262,144
window**. τ² is a turn-count/latency workload, not a KV-stress workload.

Engine side, with **attribution** (`engine_samples.jsonl`, 51 samples at 10 s over 500 s, joined by
`prompt_tokens` size):

- τ² traffic: 116 in-flight request-samples, **all `kv_mode: resident`**, 397–11,377 prompt tokens,
  concurrency reached their `--max-concurrency 3` cap in 31/51 samples (never more).
- Co-tenant = **the operator session (this chat)**, 27 request-samples, up to **221,058 prompt tokens**
  (0.84× the window), 6 samples in `kv_mode: spill`.
- Peak residency 7,339 pages = 234,848 tokens = **1.51× KV budget**, of which the operator request alone
  accounts for 6,908 pages (**94 %**); τ²'s share is ≈431 pages ≈ **13.8 k tokens = 0.09× budget**.
  Spill +1,792 and KV demotions +150 in the window belong to the operator request, **not** to τ².
- `admission.{waiting,waiting_memory,waiting_concurrency,held_behind_refusal,suspended,restoring}` peaked
  at **0** throughout — the wave-19b finding (no admission queueing; waiting lives in the scheduler
  prefill queue) reproduces on a real agentic workload. `queued` max 1, `prefilling` max 3.

Any published τ² row therefore needs the **detached, operator-idle** protocol before making residency
claims; the smoke's engine-side numbers are usable only as the attribution above.

## Instrument notes for a future suite page

- LiteLLM splits the model string at the **first** `/`; the engine receives
  `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S` intact and echoes it. `tool_calls` and
  `finish_reason: tool_calls` arrive correctly; `litellm.drop_params = True` is already set in their
  `llm_utils`, so extra args don't break; `completion_cost` raises for an unmapped model but τ² catches it
  and records `agent_cost/user_cost = 0.0`.
- `src/tau2/config.py: API_PORT = 8000` is only used by `tau2/api_service/simulation_service.py` (uvicorn);
  `tau2 run` runs environments in-process and binds nothing, so it does not collide with the engine.
- τ² seeds each sim from `--seed`: this wave recorded `seed: 626729` per sim (airline), i.e. derived per
  task/trial, not 300.
