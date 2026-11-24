# Wave RECORD — bfcl-24a-2026-11-23 (repeat wave: the temp-0 noise band)

**Purpose:** second full wave at the *identical* build as bfcl-23a (same pin `6ea5797`,
same venv, same wrapper, same flags). The product is not a score — it's the **per-category
wave-to-wave delta table**, which converts our "single-wave deltas under ~5 pts are noise"
caveat into a measured band.

**Window:** launched 2026-11-23T06:15:07Z; generate done 2026-11-24T09:42:20Z (3 h 27 m),
evaluate 09:42:22Z. `GENERATE_EXIT=0 EVALUATE_EXIT=0` in driver.out. 4,441 task-runs,
0 infrastructure errors, 1 empty-response entry (same count as 23a). Fully fresh results —
23a carried 14 smoke entries, 24a none (minor confound noted).

**Headline:** overall 40.12 vs 23a 40.85 → **-0.73**. Groups: non-live 86.58 (-0.30),
live 77.50 (-0.29), multi-turn 53.25 (-2.25).

**Band (the product):**
- 15/17 categories moved ≤2.0 pts; exact-zero moves: simple_python 94.5, simple_java 60.0,
  multiple 92.5, parallel_multiple 89.0, live_parallel 68.75, live_relevance 81.25.
- Worst n≥200 movers: multi_turn_miss_func **-3.5**, multi_turn_base **-3.0**,
  multi_turn_long_context -1.5, miss_param -1.0 — the whole multi-turn block drifted down
  together (-2.25), i.e. stateful-env variance is correlated within a wave, not per-task.
- live_parallel_multiple +4.17: n=24 — expected tiny-n swing, excluded from the band claim.
- **Adopted band: single-wave category noise ~±3.5 pts at n≥200; composite overall ~±1 pt**
  (one wave pair — preliminary, treat as order-of-magnitude until a third wave).

**Tenancy note:** 415 samples all normal/nominal, but 13 showed admission waiting>0
(23a had zero). No established effect on scores; recorded as drift.

**Interpretation guard:** deltas here are NOISE samples, never capability changes — same
build by construction. Any future wave's category delta must clear ±3.5 to count as real.
This retroactively qualifies the 23a language-axis claim (py 94.5 / js 66 / java 60:
js moved -2.0, java 0.0 — axis structure is stable inside the band).

**How to reproduce:** identical to 23a relaunch block, plus: archive the clone's
result/score dirs for the model out of the way first (BFCL resumes/skips existing entries —
that's how 23a carried smoke entries; a fresh-band wave must start from empty).
Driver: `waves/bfcl-24a-2026-11-23/run_wave.sh` (archive → generate → evaluate, tenancy
sampler every 30 s).
