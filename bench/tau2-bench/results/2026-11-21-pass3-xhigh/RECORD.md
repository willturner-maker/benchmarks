# τ² effort A/B wave 2026-11-21 — agent at `reasoning_effort: xhigh`, user simulator unchanged

**Purpose.** The published τ² rows run at engine-default (medium) reasoning. Frontier leaderboard rows run at
high/xhigh. This wave answers whether effort explains any of our gap — and tests the triage prediction that
extra effort should attack the 26 % agent-first flips and *not* the pass^k decay, which is user-sampling.

**Paired design.** Identical to `../2026-11-20-pass3/` (pin `v1.0.1 = fc0055dc…`, 238 judge-free tasks, seed
300, temperature 0, self-play, max-concurrency 3, max_tokens 4096) with **exactly one change**:
`--agent-llm-args` gains `"reasoning_effort":"xhigh"`. The **user-simulator args are untouched**, so the user
stream keeps the same seed and style as the baseline and the pass^k delta is agent-attributable.

**Effort actually rode through (verified, not assumed):**
- idle-engine probe on the same OpenAI-compatible path: `reasoning_effort:"medium"` returned a 3,084-char
  reasoning block, `"xhigh"` a 3,790-char one (same 1,024-token budget); `"none"` returned none.
- inside the wave: per-sim completion tokens shift materially vs the baseline on the same task+seed
  (airline task 0 seed 373753: 1,377 → 2,751 tok; seed 361454: 1,408 → 1,924), in both directions.
- honest caveat: tau2 does not persist `reasoning_content` in its sim records, so the engine-side block
  itself is not in the raw artifacts; the token-distribution shift is the in-wave proof.

## The published numbers

| domain | pass^1 med → xh | pass^2 med → xh | pass^3 med → xh | Δ pass^3 |
|---|---|---|---|---|
| airline | 0.8667 → **0.8867** | 0.8200 → **0.8333** | 0.7800 → **0.8000** | +2.00 |
| retail (74) | 0.8243 → **0.8153** | 0.7162 → **0.7117** | 0.6351 → **0.6486** | −0.90 / −0.45 / **+1.35** |
| telecom | 0.8596 → **0.8860** | 0.7602 → **0.7924** | 0.6930 → **0.7193** | +2.64 / +3.22 / +2.63 |
| **all 238** | 0.8501 → **0.8641** | 0.7591 → **0.7759** | 0.6933 → **0.7143** | **+1.40 / +1.68 / +2.10** |

714 sims, **0 unscored**, upstream re-derivation agrees per domain after the scoping fix below. Window
2026-11-20T23:14:29Z → 2026-11-21T02:56:48Z (**3 h 42 m 19 s**): airline 47 m 02 s, retail 53 m 05 s,
telecom 2 h 02 m 09 s. Totals **117,887,136 prompt / 3,189,224 completion tokens**.

Reading the deltas honestly: airline and telecom move +2 to +3.2 points — several whole tasks apiece, above
the per-wave sampling noise. **Retail is a wash** (−0.9 at pass^1 is under one task's worth on 74 tasks, and
retail carries the highest flip rate at 31 %); do not claim an effort effect there in either direction.

## Stability: effort did **not** change the flip rate — the headline negative result

- xhigh flip rates: airline **8/50 (16.0 %)**, retail **23/74 (31.1 %)**, telecom **32/114 (28.1 %)**,
  all **63/238 (26.5 %)** — statistically the same as medium's 65/238 (27.3 %) and 19a's ~19 % at 2 trials.
- n_pass/3 xhigh: **170 always pass, 63 disagree, 5 never** (medium: 165/65/8 — fewer never-pass tasks).
- Across the two 3-trial waves: **146 tasks stable in both, 56 stable in exactly one, 36 flip in both.**
  The *rate* replicates wave-to-wave again; the roster only partly (36-of-65 overlap, better than 19a's
  24-of-65 — expected, since that compared 2 trials against 3).
- This is consistent with suite rule 9 and the first-mover triage: most flips are born at user-simulator
  turns, and we deliberately did **not** raise the user simulator's effort. Effort buys agent-side quality
  (+2 pts airline/telecom, plausibly the agent-first flip share) without touching the sampling floor.
- **First-mover mix unchanged under xhigh**: 126 flipping trial-pairs → user-first **91 (72 %)**,
  agent-first **35 (28 %)** — vs medium's 74/26. Raising agent effort did not rebalance where flips are born
  (`flip_triage.json`).

## Cost accounting — xhigh was ~free on this stack

| | medium pass^3 | xhigh | Δ |
|---|---|---|---|
| wall clock | 3 h 47 m 14 s | 3 h 42 m 19 s | −5 m |
| prompt tokens | 119,767,224 | 117,887,136 | **−1.6 %** |
| completion tokens | 3,223,954 | 3,189,224 | −1.1 % (airline −3 %, retail +4 %, telecom −2 %) |
| airline prompt | 13,195,244 | 12,616,144 | −4.4 % |

Deeper per-decision thinking is paid back by fewer wrong turns and shorter conversations: the decode
bandwidth (width-3, ~same completions/s) sets wall time, and xhigh didn't add enough output to matter at
max_tokens 4096. This is a workload-shaped result, not a general law.

## Engine tenancy over the xhigh window (10 s sampler, 1,333 samples / 222 min)

- benchmark request-samples **3,919, all `kv_mode=resident`** (prompt 379–18,660 tok); concurrency 3 held in
  1,262 of 1,332 in-flight samples; queued max 2, prefilling max 2, decoding max 3.
- co-tenant: **2 samples, max 214,460 tok, `kv_mode=spill`** — the operator's own session again. It pushed
  lifetime `pages_active` to a peak of **7,039 pages = 225,248 tok = 1.45× the resident KV pool** while the
  wave ran; window deltas spill +2,496, `kv_demotions` +7,839, **suspensions 0, refusals 0**.
- reading: at this demand profile the scheduler demoted the *oversized co-tenant's* pages while every
  benchmark-sized request stayed resident — the benign side of the tenancy A/B story (arm B showed what
  happens when several large co-tenants arrive; here one large one absorbed its own spill). Attribution by
  prompt_tokens size as usual.

## Incidents (disclosed)

1. **`summarize.py` fallback glob was unscoped** — with no `tasks.jsonl` built at wave time, its
   `wave-*-{dom}` fallback matched *both* waves' sim dirs and silently scored airline/telecom off the
   medium baseline's records (airline printed the medium values verbatim). Caught the same minute because
   the tool's own "upstream printed" re-derivation check disagreed (0.887/0.833 printed by tau2 vs
   0.8667/0.8200 re-derived — a 2-point gap that should never open on identical records). Fixed in the same
   commit: the fallback is now scoped to `wave-<wave-dir-basename>-<dom>`, with an explicit warning on any
   multi-match. Post-fix, the raw-sims path reproduces the rows re-derivation exactly for all three domains,
   and the published-wave stats gate (`stats.py --check`) still passes byte-identically.
2. `tasks.jsonl` (714 rows) was built **post-wave** via `build_rows.py` pointed at the three explicit
   xhigh sim dirs — not via the fallback glob. Rows and raw `results.json` agree.
3. Sampler ended on its scheduled window (`Terminated: 15` after 10 h cap was never reached — the wave
   finished at 3 h 42 m and the wrapper killed it; normal path).
4. Tooling, same commit: `triage_flips.py` still wrote its JSON to a hardcoded 2026-11-19 path — now scoped
   to `results/<wave>/flip_triage.json`. (The published 19a triage in this repo was never touched.)

## Reproduce

```
TAU2_TRIALS=3 \
TAU2_AGENT_LLM_ARGS='{"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":4096,"reasoning_effort":"xhigh"}' \
bash run_wave.sh "$PWD/results/my-xhigh"
python3 summarize.py --wave-dir results/my-xhigh --from-rows results/my-xhigh/tasks.jsonl
```

Pin: `tau2-bench v1.0.1 = fc0055dc4e0a316c3f83133267fbd6faaa770992`; model
`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S` on Splash 1.7.0, not restarted (lifetime counters
reported as window deltas). Transcripts stay local (`~/tau2-bench/data/simulations/wave-2026-11-21-pass3-xhigh-*`);
`tasks.jsonl` publishes per-sim scalars only.
