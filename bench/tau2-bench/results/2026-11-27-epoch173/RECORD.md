# Splash 1.7.3 replay (2026-11-27) — a band-top epoch row: all three pass^k consistent with the unified band, flips in band, and the 1.7.3 engine bracketed quiet by three instruments

Published protocol on the 1.7.3 pin: **238 judge-free tasks x 3 trials (714 sims), seed 300,
conc 3, pinned argv** — identical to the 1.7.1 epoch171 replay except the engine version.
`run_wave.sh` 20:58:33Z -> 00:43:58Z (**3 h 45 m 25 s**; airline 48 min, retail 54 min,
telecom 2 h 03 m). 714/714 scored, 0 unscored, upstream printed rewards re-derived and AGREED
(domain sections in `summary.txt`).

## Pins
- Engine: Splash **1.7.3** single instance, pinned argv verified from the running supervisor
  (`supervisor_pins.txt`): max-memory 60129542144, persistent-cache, medium effort,
  32768 thinking budget, queue-size 64. Model pin `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`.
- tau2 clone: v1.0.1, uv venv (litellm 1.81.11) at `<bench volume>/local.AI/bench/tau2/tau2-bench`;
  venv rebuilt 2026-11-27 (fresh `uv sync --frozen`; same lockfile).
- Suite scope unchanged: airline 50 / retail 74-of-114 (40 NL-assertion judge tasks excluded) /
  telecom 114; judge-free reward bases; same seeds and user-sim args as the epoch171 wave.

## Results vs the published series (AGG = task-weighted over 238)

| configuration | airline p1/p2/p3 | retail p1/p2/p3 | telecom p1/p2/p3 | AGG p1/p2/p3 | flips |
|---|---|---|---|---|---|
| medium 20-pass3 (1.7.0 old epoch) | 0.860/0.800/0.780 | 0.838/0.757/0.635 | 0.877/0.754/0.693 | 0.8613/0.7647/0.6933 | 65 |
| medium 21 replay (1.7.0 new epoch) | 0.920/0.840/0.820 | 0.770/0.676/0.554 | 0.904/0.807/0.754 | 0.8655/0.7731/0.7059 | 58 |
| epoch171 replay (1.7.1) | 0.840/0.760/0.740 | 0.757/0.716/0.622 | 0.833/0.772/0.711 | 0.8109/0.7521/0.6891 | 64 |
| **this wave (1.7.3)** | **0.8733/0.8200/0.7800** | **0.7703/0.6306/0.5405** | **0.9240/0.8567/0.7982** | **0.8656/0.7787/0.7143** | **62 (26.1 %)** |

- **No open question was tested — 1.7.1's pass^1 dip was already closed** (11-23
  pre-registered n=3 tiebreaker: 0.8613, closed as noise; per-epoch draws now read as one
  overlapping 0.81-0.87 band). Today's **0.8656** sits at the top of that unified band, and
  the 1.7.3 Tier-1 transition probes (same day, `splash-1.7.3-transition/RECORD.md`) showed
  the 1.7.1->1.7.3 move behaviourally quiet — so this epoch row needed no tiebreaker and
  none was pre-registered.
- **Distribution-shape statistics are stationary**: flip rate 62/238 = 26.1 % (band: 24-27 %,
  all four waves); pass^2 0.7787 and pass^3 0.7143 are the **best aggregates published on this
  suite**, but only +0.6/+0.8 pts over the 1.7.0 replay — inside single-wave noise; claimed as
  "band-consistent at the top of the band", not as an improvement.
- **Domain roster churn (rule 9: rosters do not replicate, and they did not)**: telecom p1
  0.9240 is telecom's best ever (prior best 0.904); airline p1 0.8733 recovers from 1.7.1's
  0.840; retail p2 0.6306 / p3 0.5405 are retail's *worst* published (prior worst 0.676/0.554)
  while retail p1 0.7703 ties the 21-replay exactly. Domains swing opposite directions at
  n=50-114 while the aggregate and flip rate sit in band — the expected lottery signature.

## Engine window (sampler, `engine_samples.jsonl` 1352 samples over 225 min)
- Benchmark traffic separable: 3,961 benchmark request-samples (prompt 379-18,637 tok, all
  resident) at the intended concurrency (histogram mode 3: 1,272/1,352 samples).
- **Not a zero-co-tenant window** (unlike epoch171's record-clean one): 45 co-tenant request
  samples, max **173,458 tokens** — almost certainly the operator's own agent-session context
  (the benchmark's own prompts never exceed 18.6k, so the size separation attributes them
  unambiguously). Co-tenant samples show spill (39/45); wave deltas: spill_moves 9,365,
  kv_demotions 8,962, suspensions 8, pages_active peak 190,272 tok = 1.22x KV budget,
  admission waited max 2. Effect on scores: none expected (speed/KV churn does not enter the
  reward path; the trial lottery is seeded upstream) — disclosed as a window-quality delta
  from epoch171's clean-window standard.
- Cache: lifetime hit rate 0.967 -> 0.997 over the wave; drafted 3.56 M / accepted 2.25 M
  tokens (63 % acceptance), prefill +4.47 M, decode +3.15 M tokens.

## Verdict
1.7.3 joins the series at the top of the historical band on all three pass^k, flip rate in
band, 714/714 clean, rewards re-derived — no epoch effect on any measured statistic, fully
consistent with the splash-side finding that 1.7.1->1.7.3 is behaviourally quiet. The engine
side of this epoch is now bracketed three ways: fingerprint/byte probes (quiet), hermes parse
streak (unbroken), and this 714-run replay (band-consistent).

## Files (committed: RECORD.md + summary.txt + supervisor_pins.txt — force-added derived/evidence
files; the tau2 .gitignore rule targets the raw per-run bulk, not the ~5 KB distilled summary)
`summary.txt` (per-domain re-derivation + engine sections), `wave.log`, `supervisor_pins.txt`,
`status_before.json`, `engine_samples.jsonl` + `sampler.log` live in this dir (raw simulations
stay in `$TAU2/data/simulations/wave-2026-11-27-epoch173-*`, untracked by house rule).
