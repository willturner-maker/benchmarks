# τ² pass^3 wave 2026-11-20 — three trials on all 238 judge-free tasks

**Purpose.** Upgrade the published τ² record (`../2026-11-19a/`) from 2 trials to 3, which turns `pass^3` from
unmeasured into published, and tests whether the flip story replicates.

**Config (identical to 19a):** judge-free subset only — airline 50 + retail 74/114 + telecom 114 = **238
tasks**; `--num-trials 3` × 238 = **714 sims**, seed 300 (per-trial seeds derived by upstream as designed),
self-play user simulator, model `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S` on Splash **1.7.0**, not
restarted. Window: airline 18:57:39Z→19:46:07Z, telecom 19:46:08Z→21:51:02Z, retail (rerun, see incidents)
21:53:08Z→22:44:53Z. Totals: **119,767,224 prompt / 3,223,954 completion tokens**; all 714 scored, 0
infrastructure errors; upstream-vs-re-derivation agreement on every domain.

## The published numbers

| domain | tasks | mean reward | pass^1 | pass^2 | **pass^3** |
|---|---|---|---|---|---|
| airline | 50 | 0.8667 | 0.8667 | 0.8200 | **0.7800** |
| retail | 74 | 0.8243 | 0.8243 | 0.7162 | **0.6351** |
| telecom | 114 | 0.8596 | 0.8596 | 0.7602 | **0.6930** |
| **all** | **238** | **0.8501** | **0.8501** | **0.7591** | **0.6933** |

Against 19a (2 trials): pass^1 moves −0.0033 (airline), **+0.0338** (retail), −0.0132 (telecom) — same task
set, same wave seed, but trial 3 changes the mix. `pass^1 − pass^2` gap widens for retail (0.1081 → matches
its 24 flipping tasks), narrows for airline.

## Stability: the rate replicates, the task list does not

- Per-task `n_pass/3` over 238 tasks: **165 always pass, 47 pass 2/3, 18 pass 1/3, 8 never**.
- **65/238 (27.3 %) flip at least once** in this wave (airline 7, retail 24, telecom 34).
- 19a's unstable set was 45 tasks (19.3 % of 238 over 2 trials). **Overlap with this wave's 65: only 24.**
  21 tasks flipped in 19a but not here; 41 flipped only here. **152 tasks (64 %) are stable across all five
  trials** from the two waves combined.
  → the correct published claim: instability is **widespread as a rate** (~19 % of tasks at 2 trials, 27 % at
  3, 36 % at 5) and **task-level as a label only weakly** — which task you catch flipping is a sampling
  event. Any statement of the form "task X is unstable" needs several passes to survive;
  `retail/90` (unstable in all three width-control passes on 19b) flips again here: trials `[1,0]` (19a) +
  `[0,1,1]` → 3/5 across five — the one task whose label is holding up.
- **First-mover triage** (`triage_flips.py --wave 2026-11-20-pass3 --pairs all`, 130 flipping trial-pairs):
  user-simulator-first **96 (74 %)**, agent-first **34 (26 %)**, median onset 0.02–0.06 of the conversation —
  same direction as 19a's 37/8 (82 %/18 %). The seed note stands: each trial gets a fresh user-simulator
  seed by design, so this remains *user-sampling variance vs engine nondeterminism*, not engine
  nondeterminism alone.

## Engine context and tenancy (what this wave's own records can and cannot prove)

- **Retail rerun window sampled fully**: 311 samples @ 10 s; 917 benchmark request-samples, all `kv_mode
  resident`, concurrency histogram at width 3 for 298/311 samples. τ² per-call depth max **19,035 tok =
  0.122× KV budget** — the benchmark itself never pressures the pool.
- **One foreign sample in that window, and it is informative**: the operator's relaunch message at wave
  start, **133,473 tokens, `kv_mode spill`** — a real agent session. With it in flight `pages_active` peaked
  at **133,504 tok = 0.86× the 155,648-token pool on its own**, `kv_demotions` moved **+5,301** and
  `admission.restoring` peaked 1. That independently corroborates the
  [tenancy A/B](../../splash-concurrency/results/tenancy-2026-11-20/RECORD.md) at real session scale: one
  ~130k-token context nearly fills the pool. Reward-level impact on retail: nil expected (it landed in the
  first seconds; sims were not yet deep), and disclosed rather than hidden.
- **airline + telecom windows: tenancy by protocol, not by samples.** Their 10 s sampler file was truncated
  by the retail continuation (instrument bug below), so those windows rest on operator-idle discipline
  (no operator calls after launch) rather than read-back. Recorded as a gap, not papered over.

## Incidents in this wave's run (all disclosed, none silent)

1. **First launch died on a wrapper path bug**: relative wave dir + `cd $TAU2` → all redirects missing; zero
   engine load, zero sims. Fixed (`WAVE` normalized absolute).
2. **Retail attempt 1 died in 1 s**: `zsh` does not word-split `$RETAIL_FREE`, so 74 ids arrived as one
   bogus task id → "Not all tasks were found", before any sim. Fixed: `RETAIL_FREE` is an array now.
3. **Retail attempt 2 killed by us**: its window was contaminated by this session's repair turns; 1 partial
   sim quarantined (`wave-QUARANTINE-pass3-retail-contaminated`, out of all analysis).
4. **Sampler truncation**: `sample_engine.py` opens with `w` and `run_wave.sh` re-tee's `wave.log` without
   `-a`, so the continuation clobbered the main wave's samples/logs/status edges. Artifacts renamed
   `*.retail-continuation.*`; `wave.log` reconstructed verbatim from the completion transcript (header says
   so). A proper multi-continuation sampler is owed if this suite grows more resumable waves.
5. **`build_rows.py` domain parse**: took `split("-")[1]`, which returns `2026` for the current
   `wave-<wave>-<dom>` save naming. Fixed to prefer recognized trailing domain tokens; the 714-row
   `tasks.jsonl` here was rebuilt with the fix, and 19a's byte-identical re-derivation still passes.

## Files

`tasks.jsonl` — 714 published rows (same schema as 19a; free text withheld by design).
`supervisor_pins.txt` — tag `v1.0.1` = `fc0055dc4e0a316c3f83133267fbd6faaa770992` + running-supervisor flags.
`status_before.json` / `status_after.json`, `engine_samples.jsonl` — retail rerun window (see gap note).
`airline.log`, `retail.log`, `telecom.log`, `wave.log` (reconstructed), `sampler.log`.
Transcripts stay local: `~/tau2-bench/data/simulations/wave-2026-11-20-pass3-*`.
