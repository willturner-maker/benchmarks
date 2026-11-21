# τ² pass^3 replay on the new engine epoch — 2026-11-21

Purpose: the same-seed pair (see `../2026-11-21-sameseed-pair/RECORD.md`) showed telecom running
elevated on the new epoch, and the old-epoch pass^3 baseline (`../2026-11-20-pass3/`) predates
the 05:03Z engine restart. The old epoch is unrecoverable, so the epoch question can only be
answered one way: rerun the exact old-epoch wave on the new epoch and compare distributions.

## Pin and protocol

- Instrument: τ²-bench `v1.0.1` @ `fc0055dc4e0a316c3f83133267fbd6faaa770992`, judge-free subset
  (airline 50 + retail 74/114 judge-free + telecom 114 = 238 tasks), self-play, temperature 0.
- Model: Qwen3.8-Flash-Next-GSQ-RCO-GGUF IQ3_S, served by Splash 1.7.0, medium effort.
- Engine instance: `08d662f6ada5b1b1ae93fff5`, started 2026-11-21T16:24:52Z (the new epoch's
  second instance; the first, `627c2f53`, closed when the drafter-off arm attempt needed a
  restart — see `../../splash-concurrency/results/backlog-chain-2026-11-21/ARM1-FAILURE.md`).
  Launch argv byte-identical to the pin (verified against `supervisor_pins.txt`).
- 3 trials, seed 300 → trial seeds 626729/373753/361454 (identical draws to the old-epoch wave;
  transcripts are not byte-reproducible — that was the same-seed pair's finding).
- `run_wave.sh` standard; wave 16:25:05Z → 20:12:34Z (227 min), all three domains exit=0.

## Tenancy (from engine_samples.jsonl + status edges)

- 1364 samples / 227 min; benchmark concurrency histogram {3: 1296} — nominal 3-way self-play.
- co-tenant request-samples 45 (the operator's session + this agent's surviving turn), max
  220,559 tokens, 27 of them in spill mode: light but not zero — cleaner than the old-epoch
  pass^3 window, noisier than the same-seed pair.
- spill_moves Δ261, kv_demotions Δ9,057, suspensions Δ10 over the window; admission peaked at
  1 waiting / 1 suspended. KV pages high-water 7,439 (1.53× budget) with cache hit rate 0.9994.

## Scores (re-derivable: `summarize.py --from-rows tasks.jsonl`; 714/714 scored)

| scope | pass^1 | pass^2 | pass^3 | vs old-epoch pass^3 (Δ pts) |
|---|---|---|---|---|
| airline (50) | 0.8933 | 0.8533 | 0.8200 | +2.7 / +3.3 / +4.0 |
| retail (74) | 0.7703 | 0.6396 | 0.5541 | −5.4 / −7.7 / −8.1 |
| telecom (114) | 0.8713 | 0.8041 | 0.7544 | +1.2 / +4.4 / +6.1 |
| **aggregate (238)** | **0.8445** | **0.7633** | **0.7059** | **−0.6 / +0.4 / +1.3** |

(upstream printed rewards agree with re-derivation in every domain, rule 6 check)

## Verdict: no epoch effect

- Telecom lands at pass^1 0.8713 — statistically indistinguishable from the old-epoch 0.8596
  (and from the 2-trial medium 0.860), and far below the same-seed pair's telecom arms
  (~0.92). The pair's telecom elevation was arm-level sampling noise, not the epoch.
- Aggregate deltas (−0.6/+0.4/+1.3 pts) sit well inside the known run-to-run noise: single-sim
  flip rates on this engine are 15–27 % (same-seed floor 15.1 %).
- The retail −5.4/−8.1/−8.1 swing is the largest single-domain movement but is the same
  magnitude as old-epoch retail's own trial-to-trial disagreement (29/74 tasks disagree here);
  retail is the suite's noisiest domain in every wave.
- Conclusion: the published pass^3 headline (0.8501/0.7591/0.6933, old epoch) stays as the
  headline; this replay brackets it — the new epoch reproduces it to within ±1.3 pts at the
  aggregate. No epoch adjustment is needed for future waves.

## Deviations / confounds

- One co-tenant presence window (45 request-samples) — disclosed above; no suspension-driven
  invalidation (Δ10 suspensions, all restored; admission never hit refusal).
- This wave ran on instance `08d662f6`, not the epoch's first instance `627c2f53`; both share
  identical argv and machine state (persistent cache warm), and the same-seed pair had already
  shown instance-level reward floor behavior to be the decode nondeterminism, not instance identity.

Files: `tasks.jsonl` (714 rows), `summary.json`, engine `engine_samples.jsonl`, status edges
`status_before.json`/`status_after.json`, per-domain logs. Transcripts stay local
(tau2 `data/simulations/wave-2026-11-21-pass3-replay-*`) per suite policy.
