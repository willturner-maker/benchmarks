# tau2-bench — a scored agent benchmark another machine can reproduce

Third-party instrument: [`sierra-research/tau2-bench`](https://github.com/sierra-research/tau2-bench) (MIT).
We pin the tag in every record (**`v1.0.1` = `fc0055dc4e0a316c3f83133267fbd6faaa770992`**), keep the clone
**outside this repo** at `~/tau2-bench`, and run it **unmodified**. What we own is the runner, the
summarizer, the task-selection rule, and the confounds.

Unlike the Resolve suites, this one needs no footage, no Resolve, no MCP, no container, no VM, no GPU
toolchain: it talks to an OpenAI-compatible `/v1/chat/completions` endpoint. If your server returns
`message.tool_calls`, you can produce a diffable row.

## What τ² measures

A customer-service **agent** driven by a **user simulator**, both LLMs, inside a scripted environment
(airline / retail / telecom) with real tool schemas and a real database state. A run ends when the
simulator ends the conversation; the reward comes from the **environment**, not from an opinion:

| domain | `reward_basis` on v1.0.1 | how it is graded |
|---|---|---|
| airline | `[DB, COMMUNICATE]` | hash of the final DB state + substring check on what the agent told the user |
| retail | `[DB, NL_ASSERTION]` (112/114) | DB hash + a natural-language assertion judge **only if the task declares assertions** |
| telecom | `[ENV_ASSERTION]` | assertions replayed in-process against the environment; DB is *informational* |

Two rules that come from the instrument and are not ours to relax:

- **`DB Match` is not a score.** For telecom it is not in `reward_basis`, so a wave can show
  `db_match 57/227` and still score `pass^1 0.8728`. `summarize.py` labels which components are scored.
- **`pass^k` is per task `C(n_pass,k)/C(n_trials,k)`, averaged over tasks** — with 2 trials, "both trials
  passed". So `pass^1 − pass^2` *is* the disagreement count, not extra information. The looser
  independent-trials variant (`mean p^k`) is printed alongside so a reader can tell which number they are
  reading.

## Judge-free scope (the one deviation, stated up front)

A fully local run cannot judge the 40 retail tasks that declare NL assertions: on v1.0.1 the judge model is
`DEFAULT_LLM_NL_ASSERTIONS = "gpt-4.1-2025-04-14"` in `src/tau2/config.py`, with **no env override and no CLI
flag**, and the engine takes a single `--model` (no alias). A smoke run showed the failure mode before wave
time was spent on it: those tasks retry 3× and land as `termination_reason: infrastructure_error`,
`reward: null`, **0 messages** — the completed dialogue is discarded.

So the published set is **airline 50 + retail 74 + telecom 114 = 238 tasks**, selected with upstream's own
`--task-ids` (**no benchmark data is edited**). The 74/40 split is *not* the `train`/`test` split — set
compared, the counts coincide but the sets differ, so `--task-split-name train` is not a judge-free switch.
The excluded ids are listed in `run_wave.sh` and `RECORD.md`, which makes the subset reconstructible.

## Rules for publishing a row here

1. **Name the pin** (tag + commit) and prove it: every τ² record carries `info.git_commit`, and the runner
   writes `supervisor_pins.txt` from `git rev-parse` **plus the running supervisor's flags** — never from a
   config file on disk.
2. **`--num-trials ≥ 2` and publish `pass^1` *and* `pass^2` plus the per-task structure** (both-pass /
   disagree / all-fail). One trial is not publishable: 45 of 238 tasks flipped between two greedy trials
   (18.9 %), so `temperature 0` does not pin agent behaviour.
3. **Never pool domains.** Different task counts, different graded components.
4. **State self-play.** The engine under test also plays the user. τ²'s own leaderboard rows are cross-model;
   a self-play row is comparable to another self-play row, nothing else.
5. **State tenancy** and attribute it: engine counters are window deltas (the engine is not restarted for
   these waves), and `summarize.py` separates benchmark from co-tenant traffic by `prompt_tokens` size
   (τ² sessions ≤ ~16 k tokens; an operator chat session sits at 10⁵).
6. **Keep transcripts local.** `tasks.jsonl` publishes per-simulation rows — ids, seeds, reward
   decomposition, action/DB/assertion counts, tool-call counts, depth, durations — but **no message content,
   no tool arguments, no model free text**. Reviewers recompute every headline with
   `summarize.py --from-rows`.

## Run it

```bash
git clone https://github.com/sierra-research/tau2-bench ~/tau2-bench
cd ~/tau2-bench && git checkout v1.0.1 && uv sync
~/benchmarks/bench/tau2-bench/run_wave.sh ~/my-wave                    # all three domains
python3 ~/benchmarks/bench/tau2-bench/summarize.py \
  --wave-dir ~/my-wave --domains "airline retail telecom"
```

Defaults in the runner: `--num-trials 2 --max-concurrency 3 --seed 300`, upstream's own `--max-steps 200
--max-errors 10`, and `--agent-llm-args/--user-llm-args`
`{"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":4096}`. Override with
`TAU2_MODEL` / `TAU2_LLM_ARGS` / `TAU2_TRIALS` / `TAU2_CONCURRENCY` / `TAU2_SEED`. LiteLLM splits the model
string at the **first** `/`, so a registry-style id containing `/` and `:` (ours does) reaches the engine
intact.

## Wave directory layout

| file | what it is |
|---|---|
| `tasks.jsonl` | one row per simulation, no free text — the reviewer's input |
| `summary.json` | per-domain `pass^1`/`pass^2`, task structure, tokens, depth |
| `upstream_summaries.txt` | the metric block τ² printed itself (what re-derivation is checked against) |
| `supervisor_pins.txt` | pinned commit + dirty state + the live engine's flags |
| `status_before.json` / `status_after.json` | engine `/status` at the window edges (deltas, not totals) |
| `engine_samples.jsonl` | 10 s `/status` samples: KV residency, scheduler queue, admission counters |
| `engine_config.json` | pin, harness env, stack flags, τ² scoring config, wall clock |
| `<domain>.log` | τ²'s stdout for that domain (kept local; contains task text) |
| `RECORD.md` | the human-readable record: scores, exclusions, confounds, engine behaviour |

## What τ² is *not* good for on this machine

It is not a KV-stress test. Per-call context tops out at **16,341 tokens = 0.105× the KV budget**, and their
`--max-concurrency 3` keeps decode width under our `maximum_batch_width = 4`. What it does measure is
**prefix-cache behaviour and turn-count cost**: τ² re-sends a session's context every turn, which is exactly
the shape persistent KV caching exists for — see the engine findings in
`docs/tau2-bench-benchmark-results.md`.
