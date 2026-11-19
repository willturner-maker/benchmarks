# tool-loop-gate — does the model *stop* using tools?

A fourth suite, and the only one here that produces a number **other people can diff against their own
machine** without our footage, our Resolve, our MCP, a container, a VM or a GPU toolchain. It talks to a
plain OpenAI-compatible `/v1/chat/completions` endpoint. If your server speaks that dialect and returns
`message.tool_calls`, you can run it.

**Upstream is third-party and unmodified.** [`vcruz305/hermes-agentic-bench`](https://github.com/vcruz305/hermes-agentic-bench),
MIT, `hermes_loop_gate.py`. We pin the commit in every record (`6dc6f0e570850c196c8bda6e5e1f8ad5f7082910`)
and keep the clone **outside this repo** so nobody mistakes vendored third-party code for our instrument.
We contribute the runner, the flattener, the re-derivation check, and the confounds.

## What it is

20 short tasks against five **scripted** tools (`terminal`, `read_file`, `search_files`, `web_search`,
`write_file`), 12-turn cap. Per task it records:

| scalar | what it catches |
|---|---|
| `parse_ok` | text that *looks* like a tool call (`<function=`, ```json {"name"…```) while the API handed back none — a server/template that cannot emit `tool_calls` |
| `n_tools` | industriousness |
| `duplicate_calls` | the same `(name, canonical args)` twice |
| `hit_cap` | reached 12 turns still calling tools with no user-facing answer |
| `pass` | task-specific: a **short** successful trace, not a completed mission |

That last line is the point. The gate was written because community reports of local "agent" models were
not "cannot call tools" but **"calls terminal 50–150 times and never answers."** A model can do the task
correctly and still fail this gate on purpose.

## Files

| file | what |
|---|---|
| `run_gate.sh` | pins endpoint + exact model id, runs the two sampling axes, captures the live supervisor pins and `/status` before/after |
| `summarize.py` | flattens upstream JSONs to `wave.jsonl` (one row per task per pass, **no model free text**), re-derives the harness's own SUMMARY and flags any disagreement, computes the per-task stability band and the stub-response confound. `--from-rows` re-checks published numbers without the raw files |
| `results/<wave>/` | `wave.jsonl`, `summary.json`, `engine_config.json`, `supervisor_pins.txt`, `status_{before,after}.json`, `RECORD.md` |

## Running it

```bash
git clone https://github.com/vcruz305/hermes-agentic-bench ~/hermes-agentic-bench
cd ~/hermes-agentic-bench && git checkout 6dc6f0e
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt   # httpx only
cd ~/benchmarks
bench/tool-loop-gate/run_gate.sh bench/tool-loop-gate/results/2026-XX-XXa defaults greedy greedy greedy
```

`GATE_BASE`, `MODEL` and `UPSTREAM` are env-overridable. Note that some local servers are strict about
the model string — Splash returns `404 model_not_found` for anything but the exact id, so a LiteLLM-style
harness needs a real alias, not a made-up name.

## Rules for publishing a row from this suite

1. Name the **sampling axis** (`defaults` = upstream 0.6 / 0.95 / 64; `greedy` = 0 / 1 / 1) and the
   **upstream commit**. Neither is cosmetic.
2. Publish a **band** from ≥2 passes (4 for greedy) plus per-task stability. A single pass of this gate is
   noise: 4 greedy passes of the same model scored 15/15/15/15 but with mean tools 2.0→2.8 and one then
   three `HIT_CAP` task-runs.
3. Publish the **stub-response rate** (`summary.json → stub_responses / tool_calls`). The scripted world
   answers only exact commands; how often it stubs is a property of the model's command style and it
   directly inflates `mean_tools`.
4. Disclose the **harness-shape split**: how much of the failure set is call-count / tool-choice criteria
   rather than wrong behavior. On the 2026-11-19a wave, 2 of the 4 persistent failures are of that kind
   (one correct refusal, one task solved in one shell command the grader did not accept).
5. Do **not** run `hermes_native_battery.py` casually: upstream documents that its file toolset
   **cannot be sandboxed** and its destructive test is opt-in. This suite runs the contract tests only.
6. Latencies from this suite are not throughput cells — the gate is single-stream and short. Throughput
   claims live in `splash_engine`.

## What this suite is *not*

It is not a task-completion benchmark and not a capability ceiling: 13 of 20 tasks pass on every axis,
so the instrument's resolution lives in 6 tasks. It measures **loop hygiene and stop discipline** — the
axis where local models reportedly fail in production harnesses — which is exactly what our own
resolve-agentic suite cannot see, because that suite scores our harness's tooling, not the model's
self-control.
