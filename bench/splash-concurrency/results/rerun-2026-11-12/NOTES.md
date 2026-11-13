# Rerun 2026-11-12 — terminal launch, engine unchanged (schema 8)

Trigger: user re-ran `python3 -I engine_probe.py && python3 -I ladder_kv.py` from a fresh
terminal; engine_probe.py crashed because /tmp/splash-bench-2026-11-06/ had been wiped by
macOS (it never created the dir). Fix: os.makedirs + SPLASH_BENCH_OUT override in
engine_probe.py. Same command then ran end-to-end (exit 0). Engine version not exposed by
/status (schema_version 8, as in the 1.6.0/1.6.1 waves); assumed still 1.6.1 — no update
reported between waves.

**Ladder medians:** w1 205.2 / w2 334.5 / w3 393.4 / w4 464.3 / w6 417.6 / w8 522.7 /
w12 487.1 / w16 505.7 / w24 493.1 / w32 500.5; stop rule never fired (min post-w1 ratio
1.63x w1). w6 dip 0.900x of w4 (1.6.1: 0.928, 1.6.0: 0.872-0.875).

**vs 1.6.1 rerun (NOTES in splash-1.6.1-rerun-2026-11-11h):**
- w1 +9.8% (186.9 -> 205.2); w4 +8.6%. Plateau w12-w32 mean 496.6 vs 518.3 -> -4.2%,
  i.e. plateau shifted down ~4 pts and got noisier (487-506 vs 510-525).
- Peak back at w8 (522.7) instead of w12 (524.8); within instance-to-instance scatter
  ("instance-dependence" lesson from the 10s rerun), not a claimed shape change.

**TTFT open flag from 1.6.1 notes RESOLVED:** cold 355 ms / warm 151 ms. Warm TTFT now
better than both prior waves (1.6.1: 442/294; 1.6.0: 430/174). The 294 ms "warm
regression" looks like contention contamination, not a real regression — warm TTFT has
ladder corroboration this wave (w1 205.2 is the highest w1 seen).

**Probe rows (clean this time — no external traffic except caveat below):** decode_w1
152.8/167.0/148.4, median 152.8, flat walls (1.96/1.80/2.02 s), no monotonic warm needed.
probe/ladder-w1 ratio 0.745.

**KV:** no trip through w12; 611,244 tok total in 171.5 s (1.6.1: 170.5-171.1 s —
near-identical prefill walls, consistent with decode-side-only change). demote deltas:
w6 +382, w10 +645, w12 +97 — demote path now engaged in 3 rounds (1.6.1: w10 only; 1.6.0
baseline: w10 +645 only, 10s rerun: all zeros). One waiting_memory + waiting hold at w10
(1.6.1 held at w10; 1.6.0 at w12). susp_peak 0 and susp_delta 0 every round.
pages_active peak 1,847 at w10/w12. Resident KV budget reported 131,072 tok (baseline
recorded 139,264 — budget value itself is instance-variable; 611k = 4.66x).

**Single-tenant caveat:** the benchmark engine on :8000 also serves this Claude session
(same model id). Only inter-message turns hit it, but lifetime cache.resource_suspensions
was 16 at wave end (0 delta during every round — all pre-existing). Strictly this
violates the suite's single-tenant hygiene; numbers unaffected per per-round deltas.

Files: engine_probe.jsonl, ladder_kv.jsonl (copies of the /tmp originals),
combined_stdout.txt. Not committed — awaiting user call (bench dir has its own git history).
