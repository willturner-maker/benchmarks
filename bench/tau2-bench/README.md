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
   (18.9 %).
3. **Attribute your flips, don't just count them.** Report **where each flip first appears** — who produces
   the first differing message (`triage_flips.py` does this from any wave's transcripts). In our wave 37 of
   45 flips surface in the **user-simulator's** turn (33 at the opening turn) and only **8 of 238 tasks
   (3.4 %) diverge in the agent's own turn** under an identical prefix. Under self-play both roles are the
   engine under test, so this locates the flip rather than excusing it. Note also that τ² sends a per-trial
   `seed` which this engine shows no reaction to at `temperature 0` — do not credit reseeding for the
   variance, and do not claim a seeded replay you do not have.
4. **Do not blame batching without running the width control.** `width_control.sh` re-runs flipping tasks at
   `--max-concurrency 1` and `3` with the operator idle and `/status` sampled. On this stack the flip count
   was **identical in both arms (3 of 8) even though the c1 arm never batched once** (b1 19,439, b2/b3/b4 =
   0), so batching is excluded here — the surviving candidate is long-context KV/prefix-cache state. Record
   the decode-width deltas, not the flag you passed: our first attempt at this control was discarded because
   its own "concurrency 1" window contained 8,599 batches wider than b1 (b2 8,190 · b3 409) from operator
   traffic, and it carried no sampler at all, so the only evidence it left is a pair of `/status` snapshots.
   **A control that never samples the engine cannot prove its own condition** — attach `sample_engine.py` to
   any run whose claim is about engine state.
5. **Never pool domains.** Different task counts, different graded components.
6. **State self-play.** The engine under test also plays the user. τ²'s own leaderboard rows are cross-model;
   a self-play row is comparable to another self-play row, nothing else.
7. **State tenancy** and attribute it: engine counters are window deltas (the engine is not restarted for
   these waves), and `summarize.py` separates benchmark from co-tenant traffic by `prompt_tokens` size
   (τ² sessions ≤ ~16 k tokens; an operator chat session sits at 10⁵).
8. **Keep transcripts local.** `tasks.jsonl` publishes per-simulation rows — ids, seeds, reward
   decomposition, action/DB/assertion counts, tool-call counts, depth, durations — but **no message content,
   no tool arguments, no model free text**. Reviewers recompute every headline with
   `summarize.py --from-rows`.
9. **Quote flip RATES, not flip LISTS, across waves.** The 2026-11-20 pass^3 wave found 65/238 tasks flipping
over 3 trials where 19a found 45/238 over 2 — but only 24 tasks are in both sets, and 152 tasks stayed clean
across all five trials. Which task you catch flipping is a sampling event; the rate (~19 % at 2 trials, 27 %
at 3) and the first-mover split (user-simulator-first 82 %, then 74 %) are what replicate. A per-task
"unstable" label needs several passes before it can be published.
   **Mechanism (2026-11-21 same-seed pair):** at temperature 0 with an identical seed, 0/238 transcripts are
   byte-identical, yet only 15.1 % of pairs flip reward — micro-divergence is engine decode nondeterminism,
   reward flips are the lottery. Do not attribute flips to user resampling without a same-seed control.
   **Per-request floor (2026-11-22 determinism probe):** byte-identical single requests re-queried at
   temperature 0 reproduce their own action only 15 % (agent) / 27.5 % (user) of the time — instability is
   per-request and immediate (median first difference ~25 chars), not cumulative-only, and batch-width-
   independent. Quote determinism at request level; `results/2026-11-21-determinism-probe/RECORD.md`.

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

To publish your own record: `python3 build_rows.py --out tasks.jsonl <save-dir> …` turns τ²'s own
`results.json` files into the per-simulation row file (no transcripts). The field set is fixed by that
script, and running it on wave 2026-11-19a regenerates the published 476-row `tasks.jsonl`
**byte-identically** — that check is how a reviewer confirms the published rows came from these rules.

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
| `flip_triage.json` | (optional) per-flip first-difference location + component, from `triage_flips.py` |
| `RECORD.md` | the human-readable record: scores, exclusions, confounds, engine behaviour |

## Published records in this directory

| dir | what it is |
|---|---|
| `results/2026-11-19a/` | the scored wave: 238 tasks × 2 trials, `tasks.jsonl` (476 rows), `summary.json`, `flip_triage.json`, engine samples, `RECORD.md` |
| `results/2026-11-19b-width-control/` | the control experiment on flipping tasks at `--max-concurrency 1` vs `3` (32 rows, per-arm engine decode widths, RECORD.md) — the record behind "batching is not the mechanism" |
| `results/2026-11-19-smoke/` | the pre-wave smoke run (mock 4 + airline 5 + retail 5 + telecom 3, one task per component). This is the record behind the "3 of 5 retail tasks die as `infrastructure_error`" claim, and behind the co-tenancy counter-example (the operator session was 94 % of peak residency there). No transcripts |

## What τ² is *not* good for on this machine

It is not a KV-stress test. Per-call context tops out at **16,341 tokens = 0.105× the KV budget**, and their
`--max-concurrency 3` keeps decode width under our `maximum_batch_width = 4`. What it does measure is
**prefix-cache behaviour and turn-count cost**: τ² re-sends a session's context every turn, which is exactly
the shape persistent KV caching exists for — see the engine findings in
`docs/tau2-bench-benchmark-results.md`.
