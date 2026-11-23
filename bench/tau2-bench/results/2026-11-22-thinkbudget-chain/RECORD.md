# 2026-11-22 thinking-token-budget chain (8192 / 65536 / 32768 control)

Engine stack: Splash 1.7.0, `--max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache
--default-reasoning-effort=medium --queue-size=64`, with `--thinking-token-budget` varied per arm.
tau2-bench pin `fc0055dc4e0a316c3f83133267fbd6faaa770992` (v1.0.1), judge-free scope: 50 airline +
74 retail + 114 telecom = **238 tasks**, `--num-trials 1 --max-concurrency 3 --seed 300`, temperature 0.
Readout produced by `bench/tau2-bench/thinkbudget_summary.py` from the tau2 store plus each wave's own
`engine_samples.jsonl`. No engine traffic was used to produce any number here.

## Headline: the manipulation was inert, so this chain is a noise-floor measurement, not a budget A/B

The harness caps completion at `max_tokens: 4096` (`run_wave.sh`, LLM_ARGS), and **thinking tokens count
inside `completion_tokens`** on this stack — measured directly the same day: `max_tokens=16` →
`completion_tokens=16` with `reasoning_tokens=16` and `content=null`; the same prompt at 200 → answered
with 23 reasoning tokens. Therefore completion can never exceed 4096, and **every arm's budget
(8192, 32768, 65536) sat above the ceiling the harness allowed the model to reach**. The flag was set
differently in three engine launches and could not change any behaviour.

| arm | arm budget (from `supervisor_pins.txt`, read off the live supervisor) | harness cap | largest agent completion | messages at cap | verdict |
|---|---|---|---|---|---|
| 8192 | 8,192 | 4,096 | 3,106 | 0 | inert — budget > cap |
| 65536 | 65,536 | 4,096 | 2,781 | 0 | inert — budget > cap |
| 32768 (control) | 32,768 | 4,096 | **4,096** | 1 | inert — the *cap* bound, once |

Derived thinking (estimate, see method notes): mean 153.4 / 162.5 / 157.6 tokens, max 2,688 / 2,768 /
3,562; thinking share of agent completion 0.646 / 0.664 / 0.657. The at-cap count covers **agent turns
only** (8,986 of them across the three arms, of which exactly **1** hit 4,096); the 8,900 user-simulator
turns are reported separately and were not cap-checked.

## Outcomes

| arm | pass^1 = mean reward | airline | retail | telecom | tasks any-pass | agent tool calls | agent messages |
|---|---|---|---|---|---|---|---|
| 8192 | **0.8782** | 0.9000 | 0.8108 | 0.9123 | 209 | 1,531 | 2,988 |
| 65536 | 0.8697 | 0.8600 | 0.8243 | 0.9035 | 207 | 1,518 | 2,988 |
| 32768 control | 0.8403 | 0.8600 | 0.7838 | 0.8684 | 200 | 1,480 | 3,010 |

238 sims scored per arm, 0 unscored, `termination_reason = user_stop` for all 714 sims.

Spread across three arms that cannot differ: **3.8 points of pass^1**.

## Per-task agreement — this is the number worth keeping

With `--num-trials 1` the only thing that can differ between two arms on a task is pass/fail, so the
flip counts *are* the noise floor of an inert manipulation. Exact two-sided sign test on the discordants.

| pair | tasks | both pass | both fail | only first | only second | flip rate | p |
|---|---|---|---|---|---|---|---|
| 32768 vs 8192 | 238 | 183 | 12 | 17 | 26 | 18.1% | 0.222 |
| 32768 vs 65536 | 238 | 180 | 11 | 20 | 27 | 19.7% | 0.382 |
| 8192 vs 65536 | 238 | 187 | 9 | 22 | 20 | 17.6% | 0.878 |

Independent corroboration from this suite's earlier `2026-11-21-sameseed-pair`: engine-only reward-flip
floor 15.1%, 2-trial flip rate 18.9%. The inert-arm flips here land at 17.6–19.7% — the same band.

**Rule of thumb this establishes for the suite:** at 238 tasks / 1 trial, treat roughly **±4 points of
pass^1** (≈19 task flips) as noise. A single-wave difference smaller than that is not a finding — which
is how it should be read against the flat effort A/B (16/18 in both arms) and against any one-wave
stack comparison in this directory.

## Engine-side join (arms that were actually serving)

| arm | samples | window | `pages_active` max | queued max | prefilling max | decoding max | width high-water | spill / demote / susp deltas |
|---|---|---|---|---|---|---|---|---|
| 8192 | 443 | 4,424 s | 752 pages = 24,064 tok (**0.155×** of the 155,648-token KV budget) | 1 | 2 | 3 | b1 2,702 · b2 12,674 · **b3 87,684** · b4 0 | 0 / +3,164 / 0 |
| 32768 | 438 | 4,374 s | 816 pages = 26,112 tok (**0.168×**) | 1 | 2 | 3 | b1 3,383 · b2 11,717 · **b3 88,028** · b4 0 | 0 / +2,595 / 0 |

- The wave's own `--max-concurrency 3` is visible in the engine's decode-batch width counters: width 3
  dominates by an order of magnitude and **width 4 is never reached**, consistent with
  `maximum_batch_width: 4` never being filled by this suite.
- `queued` never exceeded 1: single-tenant waves do not exercise the queue at all, which is why the
  `--queue-size 64` move (19b) is invisible here.
- Demotion churn without pressure: +3,164 / +2,595 `kv_demotions` (persistent-cache bookkeeping) with
  **0 spill moves and 0 suspensions** — matches the 19b/19c-clean KV findings.

**Excluded from the comparison: the 65536 arm's engine samples.** That arm's directory was re-entered
by a stalled re-run, so its `engine_samples.jsonl` is that run's record, not the wave's: only 30/552
samples show live requests, `queued` max 32 and `pages_active` max 4,533 come from foreign probe
traffic, and the samples' `max_new_tokens` are `[8, 32768]` where the harness declares 4096. The
analyzer prints this as a provenance warning rather than letting it enter the table. The arm's *outcome*
data is sound (all three `results.json` files in the tau2 store verified untouched); only its console
and engine evidence is degraded. Full detail: `../2026-11-22-thinkbudget-65536/TENANCY.md`.

## Chain provenance, including its failures

`chain.log` and `chain_run0_argvcheckfail.log` record five launches:

```
17:34:45Z  run 0  ARGV CHECK FAILED at arm 8192, then again at the 32768 pin-restore arm
                "FATAL: pin restore arm failed - manual restore required"
17:37:45Z  run 1  arm 8192 wave 17:37:55Z -> 18:51:50Z exit=0
19:01:59Z          aborted: "engine still busy after 10 min before arm 65536 - aborting, engine untouched"
19:16:22Z  run 2  aborted at the same guard before arm 8192 (19:26:29Z), engine untouched
19:41:00Z  run 3  arm 65536 wave 19:41:10Z -> 20:54:57Z exit=0; arm 32768 wave 20:55:08Z -> 22:08:04Z
                exit=0; "thinkbudget chain complete: pin restored (32768) and control wave done"
22:42:49Z  run 4  arm 65536 again -> parked on tau2's resume prompt, cleared next day; see TENANCY.md
```

Run 0's failure was the instrument, not the engine: `verify_argv` was checking the **engine child**,
whose argv carries no flags at all (measured: 259 chars, no options), and `/status` does not expose the
budget either. The guard now reads the supervisor line, which is where the options live; every arm's
budget in the table above comes from that supervisor line, captured at wave start.

The live pin after all this was re-verified from the running supervisor, not from the script:
`--thinking-token-budget=32768 --queue-size=64`, `ready true`, ctx 262,144.

## Method notes and the corrections made while building this readout

Published openly because each one would have produced plausible-looking wrong numbers:

1. **Reward location.** tau2 stores reward under `reward_info.reward`; the first pass read
   `s["reward"]`, which is absent, and would have scored every arm at 0.0000.
2. **Task-key collision.** tau2 task ids are numeric *per domain*; keying on `task_id` alone merged
   airline task 3 with retail task 3, producing "207 tasks, trials [1, 2]". Keyed on
   `(domain, task_id)` it is correctly 238 tasks, trials [1].
3. **Crowd-out false positives.** The first version counted "completion > 0 with empty visible content"
   as a thinking-budget truncation: 642 / 655 / 689 messages. Every one of those is a **tool-call
   turn**, which has empty content by design. Requiring no tool calls: **0 crowd-out messages in all
   three arms** — consistent with the cap, not the budget, being the only truncation in play.
4. **Cap source.** Deriving the harness cap from engine samples is wrong for a contaminated arm (it
   reported 8 for the 65536 arm). The declared cap in `run_wave.sh` is authoritative, and a
   disagreement between the two is now reported as evidence of foreign traffic.
5. **Derived thinking is an estimate.** tau2 records per-message `usage` with `completion_tokens` only
   (no reasoning breakdown), so thinking = completion − (visible chars / 4). The estimate is labelled
   as such; the inertness conclusion does **not** depend on it — it follows from the cap arithmetic and
   the measured inside-the-cap behaviour.

## What a real thinking-budget A/B would require

- Raise the harness cap above the budget under test (e.g. `max_tokens: 70000` for a 65536 arm), the
  same opt-in pattern as `AGBENCH_OUTPUT_TOKENS` in the resolve-agentic suite: default stays sealed.
  Or go the other way and test budgets **below 4096** (1024 / 2048 / 4096), which do bind under the
  current harness — cheaper, and directly relevant to the pinned 32,768 decision, since the current
  waves show thinking topping out around 150–3,500 tokens.
- Get above the flip floor: paired waves with `--num-trials ≥ 2`, or state the ±4 pt band explicitly
  rather than reading 3.8 points of spread as an effect.
- Do not re-enter a completed arm's directory. Now enforced: the chain skips arms with a
  `status_after.json` unless `TB_RERUN_ARM=1`, and `run_wave.sh` moves an existing `--save-to` aside
  (or resumes deliberately with `TAU2_RESUME=1`).

## What each arm's directory contains, and what to distrust

| arm | outcome data | engine samples | console logs |
|---|---|---|---|
| 8192 | complete (`../2026-11-22-thinkbudget-8192/`) | its own wave: 443 samples 17:37:55Z→18:51Z, 441 with live requests | its own wave |
| 32768 control | complete | **its own wave: 438 samples 20:55:08Z→22:08:02Z, 436 live** — verified against `chain.log` | its own wave, all three domains `exit=0` |
| 65536 | complete and verified untouched | **the stalled re-run's, not the wave's** — 30/552 live, foreign `max_new_tokens` | airline belongs to the re-run, retail was overwritten, telecom is the wave's |

`wave.log` in the 8192 and 32768 dirs prints every line twice: the chain was appending its own stdout
into the same file the runner writes (two writers, one name). Fixed after this chain — the chain now
writes `wave.stdout.log`. Home paths in these logs are replaced with `~` per the publish rule, which also
rewrites their mtimes, so any timestamp quoted in this record is as-observed, not re-derivable.


## Files

- `arm_readout.json` / `arm_readout.txt` — this record's numbers, regenerated by `thinkbudget_summary.py`
- `chain.log`, `chain_run0_argvcheckfail.log`, `status_ready_{8192,65536,32768}.json` — launch evidence
- `../2026-11-22-thinkbudget-{8192,65536,32768}/` — per-arm waves: domain logs, `wave.log`,
  `engine_samples.jsonl`, `status_before/after.json`, `supervisor_pins.txt`
- `../2026-11-22-thinkbudget-65536/TENANCY.md` — the tenancy event, the stall, the teardown error, and
  the runner hardening that came out of it
