# tau2-bench v1.0.1 — scored wave 2026-11-19

**Wave wall clock:** 2026-11-19T21:34:10Z → 2026-11-20T00:00:34Z = **2 h 26 min 24 s**, detached
(`run_wave.sh`), no operator work on the engine inside the window (attribution below).

**Instrument:** `sierra-research/tau2-bench` @ `v1.0.1` = `fc0055dc4e0a316c3f83133267fbd6faaa770992`
(`supervisor_pins.txt` line 1; also echoed as `info.git_commit` inside every record). Clone `~/tau2-bench`
outside the published repo, **no source files edited** (only `uv.lock` drift: `revision 3→5`,
`version 1.0.0→1.0.1`, from `uv sync`).

**Engine:** Splash 1.7.0, `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, `127.0.0.1:8000`, the **same
launch** as Splash wave 19b — `--queue-size=64`, `--thinking-token-budget=32768`,
`--default-reasoning-effort=medium`, `--persistent-cache`, `--max-memory=60129542144`. No restart, so all
engine counters below are **deltas over the window**, never lifetime totals.

## Scores (per domain; never pooled)

238 tasks × 2 trials = **476 simulations, 476 scored, 0 unscored, 0 infrastructure errors, 0 refusals**.

| domain | tasks | pass^1 | pass^2 | both-pass | trials disagree | both-fail | tool calls | mean calls/sim | median sim |
|---|---|---|---|---|---|---|---|---|---|
| airline | 50 (base) | **0.8700** | **0.8200** | 41 | 5 | 4 | 746 | 7.46 | 48 s |
| retail (judge-free subset) | 74 of 114 | **0.7905** | **0.6757** | 50 | 17 | 7 | 1,030 | 6.96 | 39 s |
| telecom | 114 (base) | **0.8728** | **0.7719** | 88 | 23 | 3 | 3,553 | 15.58 | 58 s |
| **total** | 238 | — | — | 179 | **45 (18.9 %)** | 14 | 5,329 | — | — |

`pass^k` is upstream's definition — per task `C(n_pass, k) / C(n_trials, k)`, averaged over tasks. With 2
trials that is exactly "both trials passed", which is why `pass^1 − pass^2` **equals** the disagreement
count: the gap is the stability signal, not extra information. The independent-trials variant
(`mean p^k`) would print 0.845 / 0.733 / 0.822 — 2.5–5.7 points higher; both are printed by
`analyze_wave.py` so a reader can tell which number they are looking at.

Termination: 475 `user_stop`, 1 telecom `max_steps` (at upstream's default 200 steps). No `agent_error`.

**Re-derivation check (AGREES on all three domains):** `analyze_wave.py` recomputes mean reward, pass^1 and
pass^2 from the per-simulation records and compares against the `Average Reward / Pass^1 / Pass^2` lines
τ² itself printed in `airline.log`, `retail.log`, `telecom.log`: 0.8700/0.870/0.820, 0.7905/0.791/0.676,
0.8728/0.873/0.772. Mean reward over all sims also matches to 4 dp.

## What is in scope, and what is excluded (published, not hidden)

Only tasks whose **v1.0.1 reward path needs no LLM judge**:

| domain | `reward_basis` | in scope |
|---|---|---|
| airline | `[DB, COMMUNICATE]` ×50 | all 50 — DB end-state hash + substring communication check |
| retail | `[DB, NL_ASSERTION]` ×112, `[DB]` ×2 | **74** — the ones whose `nl_assertions` list is empty, so the NL evaluator short-circuits ("No nl_assertions to evaluate") |
| telecom | `[ENV_ASSERTION]` ×112, `[ENV_ASSERTION, ACTION]` ×2 | all 114 of the `base` split — in-process env-assertion replay, no DB, no judge |

The **40 excluded retail tasks** need `DEFAULT_LLM_NL_ASSERTIONS = "gpt-4.1-2025-04-14"`, a cloud model that
v1.0.1 gives no way to redirect: `src/tau2/config.py` has no `getenv`, `cli.py` has no judge flag, and the
engine takes a single `--model` (no alias), so this would need a relaunch. The smoke run demonstrated the
failure mode before wasting wave time: those tasks retry 3× then land as `termination_reason:
infrastructure_error`, `reward: null`, **0 messages** — i.e. the completed dialogue is discarded.
Task selection used upstream's own `--task-ids` (74 ids in `run_wave.sh`); **no task data was edited**, and
`train`/`test` splits are *not* the judge boundary (set-compared: different 74/40).

Not run: `banking_knowledge` (retrieval-heavy, its own 1.0.1 grading break), voice domains, `mock` as a
scored row (it is a plumbing check).

## Sampling and invocation

`--num-trials 2 --max-concurrency 3 --seed 300`, upstream defaults `--max-steps 200 --max-errors 10`,
`--agent-llm-args/--user-llm-args {"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":4096}`.
**Self-play:** the engine under test is both agent and user simulator; τ² leaderboard rows are cross-model.
Sequencing airline → retail → telecom, one invocation per domain (`--save-to wave-<domain>-2026-11-19`).
LiteLLM 1.81.11 splits the model string at the first `/`, so the engine receives the full
`ISTA-DASLab/…:IQ3_S` id, which it requires.

## Volume (τ²'s own per-call `usage`)

12,088 completions, **78,251,808 prompt tokens**, 2,086,415 completion tokens. τ²'s `usage` record does not
carry `completion_tokens_details`, so **thinking tokens are not separable in this record** — do not read
"reasoning_tokens = 0" as "no thinking"; the engine does think (`--default-reasoning-effort=medium`) and the
raw API does report `reasoning_tokens` (48/85 in the plumbing probe). Depth per call: median 5,702
(airline) / 5,420 (retail) / 7,075 (telecom); **max 16,341 = 0.105× the 155,648-token KV budget, 0.062× the
262,144-token window**.

## Engine behaviour during the window (deltas from `status_before.json` / `status_after.json`)

**The prefix cache is the headline.** 78.25 M prompt tokens were requested; the engine prefilled only
**2,790,208 rows** — `cache.reused_tokens` **+76,108,064** (97.3 % of the requested prompt volume),
`cache.kv_hit_tokens` +76,171,936, `cache.hits` +12,179, **hit rate 0.7223 → 0.9671**. τ² walks one context
per session and re-sends it every turn, which is the workload shape persistent prefix caching exists for.
Window prefill throughput from lifetime deltas (2.79 M rows / 1,900.3 s prefill wall ≈ **1,468 tok/s**) is
*not* comparable to wave 19b's flat 3,485–3,499 tok/s: this is cache-hit-dominated with tiny prefills and
block-probe overhead (`cache.probe_hashed_blocks` +2,572,508), and the operator's one spill request prefilled
inside the window too.

Decode cross-check: engine `decode_output_tokens` **+2,098,867** vs τ²'s 2,086,415 completion tokens =
**0.6 % agreement** between two independent instruments. Window decode rate 2,098,867 / 6,783.96 s decode
wall ≈ **310 tok/s**; `decode_tokens_per_second` lifetime 218.0 → 287.4. `itl_ms` p50 7.94 → 9.68;
`ttft_ms` p50 **172.5 ms**, p95 365.7 ms (before: p50 259 ms, p95 381 s — the old p95 was a 19-ext-era
queueing artifact).

Speculative decoding on a real agent loop: `drafted_tokens` +2,358,289, `accepted_draft_tokens` +1,506,035
→ **63.9 % acceptance in-window** (lifetime 0.6556 → 0.6418).

**First non-zero admission counters on this engine.** `admission.waiting` peaked at 1, `waiting_memory` 1,
`restoring` 2 (`held_behind_refusal`, `waiting_concurrency`, `suspended` stayed 0). Waves 19-ext/19b saw
`admission.* = 0` at every width; the synthetic ladder never engaged the admission path. A real agentic
workload did, once — 3 concurrent ~15 k-token contexts plus one spill-mode co-tenant. `queued` max 2,
`prefilling` max 2, `decoding` max 4.

**Width 3 is the dominant decode width for the first time:** `decode_batches_by_width` lifetime high-water
`b1 59,969 / b2 35,920 / b3 179,929 / b4 5,801` — τ²'s own `--max-concurrency 3` pins it under our
`maximum_batch_width = 4`. Benchmark concurrency histogram from the sampler: 831 of 878 samples at exactly 3.

KV/disk: `pages_active` peak 3,025 pages = **96,800 tokens = 0.62× KV budget**, benchmark traffic **100 %
`kv_mode: resident`** (2,575 request-samples, 376–15,629 prompt tokens). `disk.kv_demotions` **+6,156**,
`kv_demotions_refused` +1,009, `kv_restores` +15,988, spill moves +30, suspensions 0. Persistent cache store
churned hard: `disk.written_bytes` **+428.7 GB** in 2 h 26 m (last-hour counter 60.8 GB → 201.3 GB),
`disk.kv_blocks` 520,304 → 35,692 (**206.4 GB of KV blocks reclaimed**), `disk.read_bytes` +89.2 GB.
`capacity_failures` 0, `metal_failures` 0.

## Co-tenancy audit of this window

Sampler: 878 samples at 10 s over 146 min. Benchmark request-samples 2,575 (all resident, ≤15,629 tokens);
co-tenant request-samples **3** — the operator session, max 87,043 prompt tokens, `spill` mode, ≈30 s of
the window. So unlike the smoke, this window is effectively single-tenant; the one co-tenant is the
operator's own session at the window's edge and it is what a `spill` + demote signal appears in.

## Files

- `run_wave.sh` (shellcheck-clean) — the exact invocation, including the 74 retail ids
- `sample_engine.py` → `engine_samples.jsonl`; `airline.log` / `retail.log` / `telecom.log` (τ²'s own output)
- `analyze_wave.py` → `WAVE_SUMMARY.txt` (re-derivation + upstream agreement + engine join)
- `status_before.json`, `status_after.json`, `supervisor_pins.txt`, `wave.log`, `runner.log`, `DONE`
- τ² records (with full transcripts, kept local): `~/tau2-bench/data/simulations/wave-{airline,retail,telecom}-2026-11-19/results.json`

## Known weaknesses of this wave

1. **Self-play** (agent = user simulator = the engine under test). Not leaderboard-comparable.
2. **One wave, 2 trials.** `pass^2` here is "both trials passed" from 2 samples; the 18.9 % flip rate says a
   third trial would move `pass^2` materially. No `pass^3`.
3. **retail is a 74/114 subset**, chosen by a property of the grading path, not by difficulty. Excluded ids
   are listed in this record so the subset is reconstructible.
4. **No latency-per-domain** split from the engine side; the engine counters are window-level, and only τ²'s
   own records carry per-sim durations (medians above).
5. The 45 disagreeing tasks were **triaged on 2026-11-19** (see `flip_triage.json` and the addendum below):
   the triage locates where each flip first appears; it does not fully explain the cause.

## Addendum 2026-11-19 — flip triage, and one published claim corrected

`flip_triage.json` (45 rows, produced by `../triage_flips.py` from the local transcripts) splits the
disagreeing tasks by **who produces the first differing message**: 37 user-simulator turns (33 at the
opening sentence), 8 agent turns under an identical prefix, 0 length-only. Per domain: airline 0 agent-first
/ 5 user-first; retail 3 / 14; telecom 5 / 18. Components: `ENV_ASSERTION` 23, `DB` 21, `COMMUNICATE` 1;
direction 24 down / 21 up.

Two corrections to what this record first shipped:

1. The wave notes attributed the whole 18.9 % to greedy non-reproducibility under batching. Only the 8
   agent-first flips are visible in the agent's own turn; 37 become visible through the simulated user's
   wording. Under self-play both are engine output, so the split is a location, not an exoneration.
2. **The per-trial seed is not the mechanism.** τ² puts a per-trial seed (`626729` / `373753`) in the request
   body, but the engine returned byte-identical greedy output for both seeds in 3/3 unloaded probes, so
   reseeding cannot explain the divergence and no seeded replay is available on this stack.

The open question — batch-dependent numerics (`--max-concurrency 3`) vs greedy not reproducing even alone —
is being separated by a width-1 control over 8 of these tasks; whatever it shows, it will be recorded here
rather than used to rewrite the numbers above.
