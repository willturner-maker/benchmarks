# Splash 1.6.1 rerun — corrected reading (post-audit, 2026-11-11)

Commit fe02001's summary contained two shape/statements that the review audit corrected. Raw jsonl in this dir is the record; this note supersedes the commit message's prose.

**Ladder (confirmed):** medians w1 186.9 / w2 301.0 / w3 378.5 / w4 427.5 / w6 396.9 / w8 488.4 / w12 524.8 / w16 510.0 / w24 518.5 / w32 519.8; stop rule never fired (min post-w1 ratio 1.61× w1); w6 dip 0.928× of w4 (1.6.0 waves: 0.872–0.875×).

**Shape change vs 1.6.0 (correction):** "peak at w4, flat from 8" no longer describes the curve. In 1.6.1 w8 (488.4) already exceeds w4 (427.5); the aggregate peak is w12 (524.8) and the flat band is w12–w32 (510–525) with w8 transitional. "w4 peak 427.5" in the commit message is the old signature, not the new one.

**Plateau delta:** plateau-vs-plateau mean ratio 512.3/367.9 = **+39.2%** (per-width +32.5…+42.7%). Not all of it is scheduling: w1 alone rose +23.4% (151.4→186.9), far outside the ~2% band; concurrency-normalized (plateau/w1) is only +12.8%. Prefill walls are near-identical between waves (611,244 tok in 170.5 s vs 171.1 s) — the gain is decode-side, consistent with (not proven by) the INT8 activations default.

**KV pressure (correction):** suspensions and spill stayed 0 at 611,244 tokens (4.4× the 139,264-token budget — budget value itself is not recorded in these rows; it comes from the combined script's stdout, which was not committed). But `disk.kv_demotions` delta is **+645 at w10** (other rounds 0) — exactly the 2026-11-06 baseline's w10 figure, while the 1.6.0 rerun had all zeros. So 1.6.1 partially re-engaged the demote path; the instance-dependence lesson from the 10s rerun stands. Secondary signals also differ: one waiting_memory hold at w10 (59.6 ms oldest-wait; baseline held at w12/265 ms, the 10s rerun none), admission.restoring peaked at 1 (w6–w12) with no actual suspension, pages_active peaked 1,847 (≈59k tok) — the 4,352-page ring was NOT touched (baseline touched it at w6). Governor headroom floor 26.38 MB, same graze as the rerun.

**Probe rows:** decode_w1 81.6/80.7/149.6 tok/s are contention-contaminated (probe ran 09:17–09:20 under external engine traffic; classic transient shape — the two slow passes' 3.7 s walls vs 2.0 s for pass 3; 1.6.0 waves warmed monotonically). Ladder w1 clean row (186.9) is the comparable figure; probe/ladder ratios on the two 1.6.0 waves imply a clean 1.6.1 decode ~158–168 before the +23% rise is attributed anywhere. **Open flag:** warm TTFT 294 ms vs rerun 174 ms (cold 442 vs 430 ≈ unchanged) — TTFT has no ladder corroboration, so the exclusion might mask a real warm-TTFT regression; unresolved, revisit on next run.

**Housekeeping:** commit fe02001 was made while the agentic driver was still running (09:38 vs finish 09:42) — harmless overlap (engine rows were already final) but against the single-tenant hygiene the suite prescribes.
