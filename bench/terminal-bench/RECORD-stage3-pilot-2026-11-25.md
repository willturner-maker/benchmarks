# Terminal-Bench stage 3 — model pilot on the local engine, 2026-11-25

First model-driven runs on this instrument. Two pilots: **A void** (never reached the model),
**B valid** (model reached, rewards 0.0 by capability), plus a **false negative in my own
plumbing guard** that had to be caught and fixed before anything was believed.

## Pins

| item | value |
|---|---|
| task tree | `4070d6cef56a7d20cb5dc98d5e10ada88a6b9440` = tag `v4.1.0`; dataset `probe-dataset-gate2c` (57 digest-pinned tasks) |
| runner | harbor 0.27.0 + the log-mount sticky-bit patch (required, harbor#4469) |
| agent | terminus-2 (host-side; it calls the engine directly, **not** from inside the trial container, so a loopback-bound engine needs no re-bind) |
| model | `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, asserted from `/v1/models` and echoed by the engine |
| horizon | `--agent-timeout-multiplier 0.05` → 1440 s per trial; `max_turns 40` |
| concurrency / retries | `-n 2` (same as the gate; `-n` is global per job) / `-r 0` |
| reasoning | engine default. `reasoning_effort` is honoured (`none` → 0 reasoning tokens, `minimal` → 19/23) but bounding thinking changes what is being measured, so pilots left it alone |

## Routing: why HF-style served ids break litellm through Harbor

`harbor/llms/utils.py::split_provider_model_name()` takes the **first `/`-separated component** as the
provider, so `ISTA-DASLab/Qwen3.8-…:IQ3_S` parses as provider `ista-daslab`:

```
litellm.BadRequestError: LLM Provider NOT provided. … You passed
model=ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S
```

Pilot A: **3/3 `BadRequestError` in 2m38s**, zero engine requests. The fix is
`--model openai/<served id>` — a **client-side label only**, proven by a one-request self-test in which
the engine reports back `model == "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"` exactly. That
self-test (`scripts/routing_selftest.py`) is now pre-flight for pilots and waves: exit 4 if the echoed
id ever differs from the pin. Note the earlier assumption that the **colon** in the served id was the
problem was wrong — it is the slash.

**A trap worth stating:** pilot A's trials all wrote reward files at **0.0 despite making no model
calls**. A run that scores against nothing still produces plausible reward files.

## Pilot B — valid: model reached, rewards 0.0 by capability

32m58s, 3 tasks, `-k 1 -n 2 -r 0`.

| task | wall | steps | output tokens | input (cached) | reward | exception |
|---|---|---|---|---|---|---|
| `fin-saccr-rwa` | 1481 s | 10 | 183,714 | 216,977 (163,936) | 0.0 | `AgentTimeoutError` |
| `music-harmony` | 1482 s | 22 | 84,791 | 483,963 (440,704) | 0.0 | `AgentTimeoutError` |
| `session-window-debug` | 497 s | 16 | 61,204 | 214,830 (186,656) | 0.0 | — |
| **total** | | **48** | **329,709** | **915,770 (791,296)** | | |

All 3 trials bill tokens to the pinned id in Harbor's own `agent_result.model_usage`, which is
attributable **by construction**. A corrected verdict sits in the run dir as `VERDICT-corrected.md`.

## The instrument error, kept in the record

The first guard (`model activity = engine requests in window − extrapolated idle-session baseline`)
printed **FATAL / void for a run that made 48 model calls**. It extrapolated a 120 s sample (5 requests
→ 87.5 predicted over 2101 s) while the operator session was actually idle for most of the run. The
window count itself was right: **47 engine requests vs 48 trajectory steps**.

Corrected rule, implemented as `scripts/pilot_verdict.py`: **per-trial `model_usage` billed to the
pinned id is the authority; engine counters are context.** Reason: this operator session is served by
the engine under benchmark, and its traffic is bursty and event-driven, so no sampled baseline
extrapolates across a long run. The fix is tested in both directions on real runs — pilot B →
"model reached, 329,709 output tokens over 48 steps" (exit 0); pilot A → "VOID, 0 tokens billed"
(exit 5).

## Cost model (this is what set the wave size)

* per trial: **~110k output tokens**, ~305k input (**86 % served from cache**), median wall ~1481 s
* **effective decode at `-n 2`: 62–133 tok/s**, below the 149–245 tok/s solo figure — container
  concurrency costs the engine real throughput
* **thinking dominates**: 183,714 output tokens across 10 steps ≈ 18k tokens of reasoning per step;
  at a 1440 s horizon **2 of 3 trials ended in `AgentTimeoutError`**, so those zeros are partly
  horizon-limited — a wave must state its horizon
* `max_tokens` below the thinking budget returns **`content: ''`** with the whole budget billed as
  reasoning (for an agent loop: an empty action). Reasoning text arrives in
  `message.reasoning_content`, `content` stays clean.

## Wave design (stage 4), fixed before the number exists

**57 tasks × k=1** at `-n 2`, horizon and `max_turns` as pinned above, reasoning at default → projected
**9–11 h**. Then **targeted k=3 repeats** for any task scoring non-zero plus a 6-task control sample,
which buys a stability estimate where it matters instead of paying 3× across the whole set. The
alternative of capping `reasoning_effort` was rejected for the primary wave: it would fit in ~4–6 h
but the thinking budget is part of what is being measured, so it would have to be published as a
capability-altering pin. Runner: `scripts/wave_tb41.sh`; it refuses to start unless the environment
gate is stamped, writes `pins.txt` and `exclusions.txt` into the run dir **before** launching, and
finishes by emitting `verdict.txt` and `wave-summary.json`.
