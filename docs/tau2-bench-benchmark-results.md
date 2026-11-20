# τ²-bench — Results (suite debut 2026-11-19)

**Instrument:** `sierra-research/tau2-bench` @ **`v1.0.1`** = `fc0055dc4e0a316c3f83133267fbd6faaa770992`,
**unmodified**, cloned outside this repo. **Engine:** Splash 1.7.0 serving
`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, the same launch as splash wave `19b`
(`--queue-size=64`, `--thinking-token-budget=32768`, `--default-reasoning-effort=medium`,
`--persistent-cache`), **not restarted**. **Wave:** 2026-11-19a, 238 tasks × 2 trials = **476 simulations,
all scored, 0 infrastructure errors**, 2 h 26 min, effectively single-tenant.

Headline: **airline pass^1 0.870 / pass^2 0.820 · retail (74-task judge-free subset) 0.791 / 0.676 ·
telecom 0.873 / 0.772.** And the number that matters most for reading the others: **45 of 238 tasks
(18.9 %) flipped between two `temperature 0` trials.**

## Contents

- [Why this instrument, and why pinned at 1.0.1](#why-this-instrument-and-why-pinned-at-101)
- [The scores](#the-scores-238-tasks--476-simulations)
- [Judge-free scope: the one deviation](#judge-free-scope-the-one-deviation)
- [Stability: pass^1 − pass^2 *is* the flip count](#stability-pass1--pass2-is-the-flip-count)
- [Flip triage: what the 45 flips actually are](#flip-triage-what-the-45-flips-actually-are)
- [Width control: batching is not the mechanism](#width-control-batching-is-not-the-mechanism)
- [Reading tau2's own output correctly](#reading-tau2s-own-output-correctly)
- [Engine findings: a prefix-cache workload, not a KV-stress workload](#engine-findings-a-prefix-cache-workload-not-a-kv-stress-workload)
- [Comparability rules](#comparability-rules)
- [Running it on your own machine](#running-it-on-your-own-machine)

## Why this instrument, and why pinned at 1.0.1

τ² is an **environment-graded** agent benchmark: an agent and a user simulator talk over scripted tools with
a real database, and the reward comes from the end state, not from an opinion. That makes it the most
demanding thing this machine can run that **another machine can still reproduce** — no footage, no Resolve,
no container, no VM, no GPU toolchain.

Version discipline (the repo has 14 tags and `main` declares `version = "2.0.0"` while carrying an
`[Unreleased]` changelog section, so **pin a tag or commit, never a version string**):

| pin | why (not) this one |
|---|---|
| `v1.0.1` (2026-07-16) | **our pin.** Last 1.x tag. Airline/telecom grade with no LLM judge; retail mostly short-circuits the judge |
| `pre-v1.0.1` | the reproducibility pin for *old* `banking_knowledge` numbers only |
| `v2.0.0` / `main` | not comparable to 1.x by their own words: *"Scoring change — scores are not comparable with 1.0.1"*, *"No flag combination reproduces 1.0.1 inputs exactly."* 50 reviewed retail + 50 telecom task replacements **under the same ids**, communication checks LLM-judged by default, user-simulator prompts gain language/persona blocks. Leaderboard keeps separate 1.x and 2.0 tabs |

Within 1.x only `banking_knowledge` re-grades at 1.0.1 (upstream says moves are **upward**, up to ~9 points
pass^1, except `task_074`'s gold refund $8.00 → $14.50 which moves the other way). Airline / retail /
telecom are unaffected, and grading is identical at every `main` commit back to April 2026 — but most 1.0.1
fixes landed on `main` **without a version bump**, which is why the tag, not the string, is the pin.

## The scores (238 tasks × 476 simulations)

| domain | tasks | **pass^1** | **pass^2** | both-pass | trials disagree | all-trials-fail | tool calls | mean/sim | median sim | termination |
|---|---|---|---|---|---|---|---|---|---|---|
| airline | 50 | **0.8700** | **0.8200** | 41 | 5 | 4 | 746 | 7.46 | 48 s | 100 `user_stop` |
| retail (judge-free) | 74 of 114 | **0.7905** | **0.6757** | 50 | 17 | 7 | 1,030 | 6.96 | 39 s | 148 `user_stop` |
| telecom | 114 | **0.8728** | **0.7719** | 88 | 23 | 3 | 3,553 | 15.58 | 58 s | 227 `user_stop`, 1 `max_steps` |
| total | 238 | — | — | 179 | **45 (18.9 %)** | 14 | 5,329 | — | — | 0 `agent_error` |

Volume: 12,088 completions, **78,251,808 prompt tokens**, 2,086,415 completion tokens. Telecom is the heavy
one — 15.6 tool calls per session and 57.6 M prompt tokens (74 % of the wave).

**Re-derivation agrees on all three domains.** `summarize.py` recomputes mean reward, pass^1 and pass^2 and
matches the `Average Reward / Pass^1 / Pass^2` block τ² printed (0.8700/0.870/0.820, 0.7905/0.791/0.676,
0.8728/0.873/0.772), and independently reproduces τ²'s DB-match and annotated-action counts (airline
177/182 read, 78/98 write; retail 428/458, 193/228; telecom 956/988 write). `--from-rows` does the same from
the published `tasks.jsonl` alone.

## Judge-free scope: the one deviation

The reward path is judge-free only for part of the suite. Census of the pinned task files:

| domain | `reward_basis` | tasks needing an LLM judge |
|---|---|---|
| airline (50) | `[DB, COMMUNICATE]` ×50 | **0** — all 50 *define* `nl_assertions`, but the `ALL` evaluator runs the NL judge only when `NL_ASSERTION ∈ reward_basis` |
| retail (114) | `[DB, NL_ASSERTION]` ×112, `[DB]` ×2 | **40** — the other 74 have an empty `nl_assertions` list and short-circuit with *"No nl_assertions to evaluate"* |
| telecom (114 base) | `[ENV_ASSERTION]` ×112, `+ACTION` ×2 | **0** — in-process env-assertion replay |

Those 40 retail tasks are excluded, and the exclusion is a property of the grading path, not of difficulty.
On v1.0.1 there is no way to point the judge at a local model: `DEFAULT_LLM_NL_ASSERTIONS` is a constant in
`src/tau2/config.py` (no `getenv` anywhere in that file), `cli.py` has no judge flag, and the engine takes a
single `--model` with no alias — so an alias would mean a relaunch, which this suite deliberately avoids.
The smoke run (before the wave) showed what happens if you don't exclude them: `litellm.NotFoundError:
model gpt-4.1-2025-04-14 not found`, **3 retries each**, then `termination_reason: infrastructure_error`,
`reward: null`, **0 messages** — the finished dialogue is thrown away. 3 of 5 smoke retail tasks died that
way, which is why the wave was scoped rather than run whole.

Selection used upstream's own `--task-ids` (74 ids, listed in `run_wave.sh`); **no task data was edited**.
Warning against a tempting shortcut: retail's `train`/`test` split is also 74/40, but it is a **different**
74/40 (set-compared), so `--task-split-name train` is *not* a judge-free switch.

Not run: `banking_knowledge` (retrieval framework, its own 1.0.1 grading break), the voice domains, and
`mock` as a scored row (plumbing check only — 4/4, 13 s).

## Stability: pass^1 − pass^2 *is* the flip count

τ²'s `pass^k` is per task `C(n_pass, k) / C(n_trials, k)`, averaged over tasks. With 2 trials that reduces to
"both trials passed", so the gap between the two published numbers **is** the disagreement count and carries
no extra information:

| domain | pass^1 | pass^2 | flips / tasks |
|---|---|---|---|
| airline | 0.8700 | 0.8200 | 5 / 50 (10.0 %) |
| retail | 0.7905 | 0.6757 | 17 / 74 (23.0 %) |
| telecom | 0.8728 | 0.7719 | 23 / 114 (20.2 %) |

The looser **independent-trials** variant (`mean p^k`) would print **0.845 / 0.733 / 0.822** — 2.5 to 5.7
points higher. `summarize.py` prints both; a row that quotes one without saying which is defective.

Per-task structure is in `tasks.jsonl` (task id, trial, seed, reward, `reward_breakdown` per basis, DB match,
action/assertion counts, tool calls, depth, duration).

## Flip triage: where the 45 flips first appear

Triaged the day after publishing, with `bench/tau2-bench/triage_flips.py` over the local transcripts
(published aggregate: `results/2026-11-19a/flip_triage.json` — 45 rows: first-difference position and role,
component, tool-call counts, no dialogue). The discriminator is **who produces the first differing
message**: up to that point the two trials are identical by construction.

| first difference produced by | flips | share |
|---|---|---|
| **user simulator** (33 of them at the opening turn, message index 1) | **37** | 82 % |
| agent (identical prefix, then a different tool call or reply) | **8** | 18 % |
| length-only (identical prefix, one run just goes longer) | 0 | — |

| domain | flips | agent-first | user-first | median onset |
|---|---|---|---|---|
| airline | 5 | 0 | 5 | 0.04 |
| retail | 17 | 3 | 14 | 0.06 |
| telecom | 23 | 5 | 18 | 0.02 |

Component view: `ENV_ASSERTION` flipped 23 times, `DB` 21, `COMMUNICATE` 1 — and direction is near
symmetric (24 down, 21 up), which is what sampling looks like and not what drift looks like.

**A trap worth naming.** τ² does derive a different seed per trial (the records show `626729` for trial 0
and `373753` for trial 1 under `--seed 300`), and it puts that seed into the request body. The tempting
explanation — "the two trials replay different conversations because the user simulator was reseeded" —
**does not hold on this stack**: at `temperature 0` the engine produced byte-identical output for both
seeds (3/3 unloaded probes, `42` / same reasoning text), so the seed has no observable effect here and no
seeded replay exists. Since this wave is self-play, **both** roles are served by the engine under test, so
every flip traces back to an engine call either way. What the triage establishes is the *location*: the
majority become visible in the simulated user's wording, and only **8 of 238 tasks (3.4 %)** diverge in the
agent's own turn under an identical prefix.

**Corrected mechanism claim, and then the control that settled it.** The first version of this row
attributed the 18.9 % to greedy non-reproducibility under batching (`--max-concurrency 3`, decode width up
to 3 under `maximum_batch_width = 4`). That was tested and **did not survive**: see the width control below.

## Width control: batching is not the mechanism

Scorecard: [the width-control report](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-tau2-width-control.html)

`results/2026-11-19b-width-control/` — 8 of the 45 flipping tasks, two trials per arm, same seed, run
**detached with the operator idle** and sampled at 10 s so the condition is proven from the engine rather
than from the flag we passed.

| arm | τ² flag | decode batches in the window (lifetime deltas) | peak in flight | co-tenant samples | flips among the 8 |
|---|---|---|---|---|---|
| **c1** | `--max-concurrency 1` | **b1 19,439 · b2 0 · b3 0 · b4 0** | **1** | **0** | **3 / 8** |
| **c3** | `--max-concurrency 3` | b1 1,757 · b2 1,347 · **b3 5,115** | 3 | 0 | **3 / 8** |

The c1 arm is a real never-batched condition: every decode batch was width 1, one request in flight, nobody
else attached. "Co-tenant samples" counts in-flight requests over 20,000 prompt tokens: inside the arm windows
the largest in-flight prompt is **11,488 tokens** (τ² scale), while an operator session on this stack runs at
~200 k, and the only over-threshold sample in the whole 15-minute file is a **197,507-token prefill at
`00:47:04`, three seconds before the first arm started**. So zero co-tenant traffic inside the windows. It still flipped 3 of 8
— **the same count as the width-3 replication**, and only **one task (retail 90) is unstable in all three
passes**. Flip identity is not a stable task property either: across all six simulations of these tasks the
`reward == 1` counts run 2/6 to 5/6.

What does survive: in the never-batched arm the two trials' **user-simulator turns are still essentially
never byte-identical** (airline 0/4, 0/4, 0/7 identical; retail 0/6, 1/5, 1/7 — telecom higher only because
its scripted confirmations repeat verbatim). Same input, `temperature 0`, no batching, single tenant →
different greedy output, first visible in the user role. **The candidate that survives is long-context
numerical state** — the same persistent prefix cache that served 97.3 % of the wave's prompt volume — not
batch composition. Candidate, not proven: the 2026-11-17 `verify_rows` A/B saw no divergence on a short
greedy prompt (1/5 distinct = all identical), so the effect shows up at 10–16 k-token contexts and not at
~100-token ones. Isolating it further needs a fresh-cache-vs-warm-cache arm on the same tasks.

**A discarded attempt, recorded.** The first run of this control was thrown out before analysis: the
decode-width delta across its own window is **b1 14,329 · b2 8,190 · b3 409**, i.e. **8,599 batches wider
than b1 during a run we had passed `--max-concurrency 1` to** — the operator session was on the engine, so the
flag described the τ² runner, not the engine. That run had no 10 s sampler, which is itself part of why it is
unusable for engine claims; its status edges are published alongside this record
(`discarded_attempt_status_{before,after}.json`) so the 8,599 figure is checkable. Its 5/8-agree number is used
nowhere, and the reason is written down instead of the files being deleted.

## Reading tau2's own output correctly

Three traps we hit and now publish:

1. **`DB Match` is informational for telecom.** The wave prints `db_match 57/227` (25 %) for telecom while
   its reward is 0.8728 — because `DB` is not in telecom's `reward_basis`, only `ENV_ASSERTION`. Airline's
   90/100 and retail's 117/148 *are* scored components. `summarize.py` labels which is which; a row that
   quotes a bare "DB Match" across domains is wrong.
2. **`reward: null` ≠ `reward: 0`.** Unscored (infrastructure-error) sims must be excluded from the mean and
   counted separately. Our published wave has 0 of them; the smoke had 3 and says so.
3. τ²'s `usage` record does not carry `completion_tokens_details`, so **thinking tokens are not separable in
   τ²'s own records**. "reasoning_tokens = 0" derived from them means *not recorded*, not *no thinking* — the
   raw endpoint does report them (`reasoning_tokens: 48` of 85 in the plumbing probe).

## Engine findings: a prefix-cache workload, not a KV-stress workload

**Depth (the question this suite was partly meant to settle).** Per-call `prompt_tokens` — median 5,702
(airline) / 5,420 (retail) / 7,075 (telecom), **max 16,341 = 0.105× the 155,648-token KV budget, 0.062× the
262,144-token window.** τ² walks one context per session across 20–60 turns, which is genuine held-context
*depth*, but an order of magnitude below the wall. Their own `--max-concurrency 3` also keeps decode width
under our `maximum_batch_width = 4`. So τ² will not trip KV: it is a turn-count and cache-behaviour workload.

**The prefix cache is the story.** 78.25 M prompt tokens were requested; the engine prefilled
**2,790,208 rows**. `cache.reused_tokens` **+76,108,064** — **97.3 % of the requested prompt volume served
from KV state it already had** — with `cache.hits` +12,179 and **hit rate 0.7223 → 0.9671** over the window.
τ² re-sends a session's whole context every turn; persistent KV caching turns that into ~3.6 % real prefill.

Independent cross-check between two instruments: engine `decode_output_tokens` **+2,098,867** vs τ²'s own
2,086,415 completion tokens = **0.6 % agreement**.

Window rates (lifetime-counter deltas; the engine was not restarted): decode **≈310 tok/s** (2,098,867 /
6,783.96 s decode wall), `decode_tokens_per_second` 218.0 → 287.4, `itl_ms` p50 7.94 → 9.68,
**`ttft_ms` p50 172.5 ms / p95 365.7 ms**. Speculative decoding on a real agent loop: `drafted_tokens`
+2,358,289, `accepted_draft_tokens` +1,506,035 → **63.9 % acceptance in-window** (lifetime 0.6556 → 0.6418).
Do **not** read the window prefill figure (2,790,208 rows / 1,900.3 s prefill wall ≈ 1,468 tok/s) as a
prefill-throughput claim: it is cache-hit-dominated with tiny prefills and block-probe overhead
(`cache.probe_hashed_blocks` +2,572,508), and it is not comparable to wave 19b's flat 3,485–3,499 tok/s.

**First non-zero admission counters on this engine.** Waves 19-ext/19b showed `admission.* = 0` at every
width — the synthetic ladder never engaged the admission path, and the queue we measured was the scheduler
prefill queue. Here `admission.waiting` peaked at **1**, `waiting_memory` **1**, `restoring` **2**
(`waiting_concurrency`, `held_behind_refusal`, `suspended` stayed 0). A real agentic workload — 3 concurrent
~15 k-token sessions plus a spill-mode co-tenant — did what 48 concurrent 55 k-token synthetic requests did
not. `queued` max 2, `prefilling` max 2, `decoding` max 4.

**Width 3 is the dominant decode width for the first time:** `decode_batches_by_width` lifetime high-water
`b1 59,969 / b2 35,920 / b3 179,929 / b4 5,801`, with the sampler's benchmark-concurrency histogram at
exactly 3 in 831 of 878 samples.

**Spill/demote and disk churn.** Benchmark traffic was **100 % `kv_mode: resident`** (2,575 request-samples,
376–15,629 tokens); peak residency 3,025 pages = 96,800 tokens = **0.62× KV budget**. Yet
`disk.kv_demotions` +6,156, `kv_demotions_refused` +1,009, `kv_restores` +15,988, spill moves +30,
suspensions 0. The persistent cache store churned hard: `disk.written_bytes` **+428.7 GB in 2 h 26 m**
(last-hour counter 60.8 → 201.3 GB), `disk.read_bytes` +89.2 GB, and `disk.kv_blocks` fell 520,304 → 35,692
(**206.4 GB of KV blocks reclaimed**). `capacity_failures` 0, `metal_failures` 0. If you run this suite on a
laptop, that write volume is the thing to know about.

**Tenancy.** 878 samples at 10 s over 146 min. Benchmark request-samples 2,575 (all resident, ≤15,629
tokens); co-tenant request-samples **3** — the operator's own chat session at up to 87,043 tokens in `spill`
mode, ~30 s of the window. The smoke run two days earlier was the opposite case: there the operator session
(221,058 tokens) accounted for **94 % of peak residency and all the spill/demote deltas**, which is why every
engine-side claim in this row comes from the wave, not the smoke.

## Comparability rules

- **1.x vs 2.x is a hard boundary.** Upstream keeps separate leaderboard tabs; no flag combination reproduces
  1.0.1 inputs. Closest 2.0 text run is `--communicate-scorer substring`, still explicitly different.
- **Pin tag + commit in the row**, and name `uv sync` drift (ours: `uv.lock` `revision 3→5`,
  `version 1.0.0→1.0.1`) — tool drift, not a patch, but it should be named.
- **Same trial count** before comparing pass^2, and quote which pass^k definition you used.
- **Same task scope.** A 238-task judge-free row is not comparable to a row that judges the 40 retail tasks
  with a cloud model, nor to a `banking_knowledge` or voice row.
- **Self-play vs cross-model** must be stated; both exist on the leaderboard but not against each other.
- **Tenancy and `--max-concurrency`** travel with the row: τ²'s default 3 sits inside this engine's
  `maximum_batch_width = 4`; raising it changes the decode-width regime and the KV story.

## Running it on your own machine

```bash
git clone https://github.com/sierra-research/tau2-bench ~/tau2-bench
cd ~/tau2-bench && git checkout v1.0.1 && uv sync        # not on PyPI; uv-managed, python >=3.12,<3.14
~/benchmarks/bench/tau2-bench/run_wave.sh ~/my-wave
python3 ~/benchmarks/bench/tau2-bench/summarize.py --wave-dir ~/my-wave \
  --domains "airline retail telecom"
```

Point it at any OpenAI-compatible endpoint via `TAU2_LLM_ARGS`; LiteLLM splits the model string at the
**first** `/`, so ids containing `/` and `:` survive. `--max-steps 200` is the upstream default — the smoke's
2 telecom `max_steps` came from my `--max-steps 60`, not from the model. `tau2 run` binds no port, so
`src/tau2/config.py: API_PORT = 8000` (used only by `api_service/simulation_service.py`) does not collide
with an engine on 8000.

To publish a row, follow the six rules in `bench/tau2-bench/README.md` and send a PR — see
[Community runs](leaderboard.md#community-runs--your-numbers).
