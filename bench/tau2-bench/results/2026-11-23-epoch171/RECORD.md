# Splash 1.7.1 epoch (2026-11-23) — the request-level lottery is version-stationary; pass^3/flip reproduce; pass^1 draws the lowest value yet, unproven as an epoch effect

The operator upgraded the engine to **Splash 1.7.1** (2026-11-22, ~22:30Z) with the suite's pinned argv
verified on the replacement supervisor; the suite's 1.7.0-era queue (thinking-budget chain) had closed
first, so no published row straddles a version boundary mid-experiment. Everything here ran on ONE 1.7.1
instance, `38c7a88c9dd3694b249c637`, before and after — the chain performed **no engine restarts**
(`run_epoch171_chain.sh`; initial status banner had a script-only stdin bug, the curl status files are
intact and used for all counters).

Applicability audit that justified treating 1.7.1 as low-risk for our config (read off the live engine,
not the release notes): the "outputs can differ" clause attaches to the ANE int8 FFN split — our
`ane_ffn.state` is **off** ("the target's FFN layers are not all dense") — and the int8 MoE prefill
activations, scoped to *resident MLX* targets ("streamed experts, GGUF experts... keep bf16"; we are GGUF
with a streamed 46.9 GiB expert store). 1.7.1's own boot line now prints `--verify-rows auto ...: greedy
and seeded outputs can differ from run to run` — the engine documents our determinism finding in its
startup banner.

## 1) Determinism corpus re-run — the lottery survived the upgrade (same captured bodies, engine-direct)

The 2026-11-21/22 captured wire requests (airline 430, telecom 1,049) re-POSTed **verbatim** into 1.7.1
with the published probe (reps 3, n=40/cell, corrected action metric, seq + mix arms). Identical-action %,
1.7.0-published → 1.7.1-today:

| cell | airline | telecom |
|---|---|---|
| seq agent | 50.0 → **55.0** | 52.5 → **42.5** |
| mix agent | 55.0 → **57.5** | 45.0 → **37.5** |
| seq user | 30.0 → **25.0** | 62.5 → **55.0** |
| mix user | 30.0 → **20.0** | 57.5 → **50.0** |

Agent-cell mean delta **−2.5 pts** (n=40 cells, Wilson half-width ~15 pts — indistinguishable); user cells
−7.5 (telecom-user remains the most stable cell, as on 1.7.0). Cross-epoch **matched-original-action**
(repeat vs the *1.7.0-wave* recorded output) sits at 57.5–57.5 % (airline agent) and 57.5–60 % (telecom
agent) — the same plateau as the within-1.7.0 repeats, i.e. 1.7.1 does not drift away from 1.7.0 behavior:
both epochs draw from the same ~50/50 action distribution. Full-message identity 7.5–12.5 % (was 10–20 %):
still never reproducing. First-difference median 16 chars (airline) / 34 (telecom).

## 2) 238×3 medium replay — the stable statistics replicate; pass^1 is the open question

Published protocol on 1.7.1: 238 judge-free tasks × 3 trials, seed 300, conc 3, pin argv; 714/714 scored,
0 infrastructure errors, upstream re-derivation agrees; **cleanest window on record: 0 co-tenant samples,
0 spill, 0 suspensions**, all three waves (chain phases) on one instance.

| configuration | airline | retail | telecom | AGG p^1/p^2/p^3 | flips |
|---|---|---|---|---|---|
| medium 20-pass3 (1.7.0, old epoch) | 0.860/0.800/0.780 | 0.838/0.757/0.635 | 0.877/0.754/0.693 | 0.8613 / 0.7647 / 0.6933 | 65 |
| medium 21 replay (1.7.0, new epoch) | 0.920/0.840/0.820 | 0.770/0.676/0.554 | 0.904/0.807/0.754 | 0.8655 / 0.7731 / 0.7059 | 58 |
| **medium replay (1.7.1, this wave)** | 0.840/0.760/0.740 | 0.757/0.716/0.622 | 0.833/0.772/0.711 | **0.8109 / 0.7521 / 0.6891** | **64** |

- **pass^3 replicates**: 0.6891 vs 0.6933 (old epoch) and 0.7059 (new-epoch 1.7.0) — 0.4 pts from the old-epoch
  number, inside noise. pass^2 likewise (0.7521, within 2.1 pts of both). Flip rate: 64/238 = 26.9 %,
  dead in the replicated 24–27 % band.
- **pass^1 = 0.8109 is the lowest single draw this suite has recorded**, 5.0–5.5 pts below both 3-trial
  medium waves and just outside the ±4 pt single-wave band the thinking-budget chain established. **Not yet
  an established epoch effect**: the two contributing drops (airline −8 vs the 11-21 replay, telecom −7)
  are domain rosters, which rule 9 says do not replicate; the request-level lottery above is stationary;
  and 238-binomial CIs at n=238 overlap the band's edge. Honest published reading: *no change in any
  distribution-shape statistic; one pass^1 draw sitting at the band's outer edge.* A second 1.7.1 3-trial
  wave would settle it (a repeat at ≈0.81 or lower establishes the epoch effect; a return to ≈0.86 closes
  it as a bad draw).
- **Wall time: no τ² win from the shared-head cache** — 224 min vs 227 min for the 1.7.0 replay (prefill
  Δ4,220,604 tok vs 4,212,452 / 4,340,000-class; decode Δ3,202,500). τ² conversation heads were already
  covered by 1.7.0's persistent-cache restore points (1.7.1 boot: 6,985 restore points taken back); the
  2.5–2.9× TTFT gain targets *cold* shared heads, which our waves don't have. Decode-bound waves: unchanged.
- Drafter acceptance 63.7 % (Δdrafted 3,601,720 / Δaccepted 2,293,668) — in-line with every window ever
  recorded (61–64 %), the verify-rows restructure changed nothing observable.

## Consequences

1. Epoch bookkeeping: all rows published before 2026-11-22T22:30Z are 1.7.0-epoch; rows from this wave on
   are 1.7.1-epoch. No published score is retracted; comparability note added to the docs headline.
2. The determinism corpus is now a **cross-epoch instrument**: same bodies, two engines, same lottery.
   Any future engine upgrade gets this ~25-min re-run as its first measurement.
3. Open question queued: second 1.7.1 3-trial wave to settle the pass^1 question (and give n=2 for the
   1.7.1 epoch).

Files: `chain.log`, status edges (start/mid/end — same instance), `probe_rows_*.jsonl` + `requery_summary_*.txt`
(both corpora), samplers; replay dir `../2026-11-23-pass3-replay-171/` (`tasks.jsonl` 714 rows, wave logs,
status edges, samples). Captures remain local (`captures.jsonl` gitignored).
