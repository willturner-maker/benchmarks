# τ² same-seed pair 2026-11-21 — every identical-seed transcript diverged; the flip floor is the engine

**Question (the last open τ² mechanism experiment):** the published flip story said instability is
user-simulator sampling (each trial gets a fresh seed) and the engine-nondeterminism share needed a
same-seed repeat. This is that repeat.

**Design.** Two waves, `2026-11-21-sameseed-a` (05:23:32Z→06:37:14Z) and `-b` (06:37:14Z→07:53:06Z),
identical in every way: all 238 judge-free tasks, `--num-trials 1`, seed 300 → tau2's draw yields trial
seed **626729 for every sim in both arms** (verified from the rows), same model/args (medium), self-play,
temperature 0, `--max-concurrency 3`, same pin `v1.0.1 = fc0055d…`. First runs on the **new engine epoch**
(restarted 05:20:26Z, see `../../../splash-concurrency/results/restart-2026-11-21/`); arm A ran memory-cold
(`pages_active` peak 4,456 while the pool allocated), arm B warm (peak 917).

## The number: seed removed, instability remains

| measure | value |
|---|---|
| task pairs (A vs B) | 238 |
| **byte-identical transcripts** | **0 / 238 (0.0 %)** |
| transcripts diverging somewhere | 238 / 238 (100 %) |
| first divergence role | **user 174 (73 %) · agent 64 (27 %)** |
| first-divergence onset | median 0.045 of the conversation (often turn 1–2) |
| **reward-diverging tasks** | **36 / 238 (15.1 %)** — airline 4 (8.0 %), retail 17 (23.0 %), telecom 15 (13.2 %) |
| reward direction | 21 up (A→B), 15 down — near-symmetric |

Re-derivation agrees with upstream for both arms; per-arm pass^1 (one trial each): airline 0.880 / 0.920,
retail 0.784 / 0.824, telecom 0.895 / 0.904. **Disclosed:** both telecom arms sit 3.5–4.4 points above the
medium pass^3 wave's 0.8596 — single-trial waves, and the epoch boundary is a confound that a pair on the
old epoch would be needed to separate; no epoch effect is claimed.

## The correction (this refutes a claim published twice)

Published before: *"fresh user-simulator seed per trial, so this is user-sampling variance, not engine
nondeterminism."* At **temperature 0 with an identical seed and identical starting prompts, all 238
transcripts still diverged**, median onset 4.5 % — and τ²/this stack passes temperature 0 everywhere, so
"resampling" is not generating the micro-divergence. The surviving mechanism is what the 19b width control
saw at `--max-concurrency 1` with no co-tenant: **greedy decode nondeterminism at conversation depth**
(long-context KV/prefix-cache state), amplified turn-over-turn through the multi-agent loop.

Corrected decomposition (same pin, same scope, mind the different trial counts):

- reward flip with **different seeds**, 2 trials (19a): 18.9 %
- reward flip with **different seeds**, 3 trials (pass^3): 27.3 %
- reward flip with **identical seeds**, 1×1 (this pair): **15.1 %** ← the engine-only floor
- so ~80 % of the 2-trial flip rate survives with the seed held constant; changing seeds adds roughly the
  rest (and more trials add more draws). "User-first" (73–82 % across all triages) still marks **where the
  divergence surfaces first** — at user-simulator turns — but under identical seeds the *cause* of that
  divergence is decode nondeterminism, not user resampling. The asymmetry itself (why user turns move first
  ~3:1) is now an open question.
- Rule 9 gains its mechanism: micro-divergence is near-universal (0/238 identical), but *reward* flips are
  a per-task lottery, so **rates replicate and rosters don't** — exactly as measured.

## Engine side (new-epoch counters, window deltas)

Both windows tenancy-clean: **0 co-tenant samples** (operator idle per rule 10), **0 spill moves**,
**0 suspensions**; `disk.kv_demotions` +3,345 / +2,726 (persistent-cache churn, informational);
`cache.reused_tokens` +38.35 M / +39.90 M (prefix cache doing its usual ~97 %). Sampler 442/455 samples at
10 s. The 100 % divergence happened with the *quietest* tenancy any τ² wave here has seen — co-tenancy is
not required for instability (it only amplifies it, per the tenancy A/B).

## Reproduce

```
TAU2_TRIALS=1 bash run_wave.sh "$PWD/results/my-sameseed-a"   # run twice, same seed 300
```
Compare per-task rewards and first-diff roles; per-pair analysis: `same_seed_pairs.json` (238 rows:
task, rewards, first-diff index/role, onset, transcript hashes — scalars only, no free text).
Raw records: `../2026-11-21-sameseed-a/` and `../2026-11-21-sameseed-b/` (tasks.jsonl 238 rows each,
logs, engine samples, status edges). Transcripts stay local.
