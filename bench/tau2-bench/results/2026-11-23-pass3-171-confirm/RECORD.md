# 1.7.1 confirmation wave — second 238×3 medium on the 1.7.1 epoch (n=2)

**Purpose (pre-registered in `../2026-11-23-epoch171/RECORD.md`):** settle whether pass^1 0.8109 in the first
1.7.1 replay was a bad draw or an epoch effect. Gate as written: repeat ≈0.81 or lower ⇒ epoch effect;
≈0.86 ⇒ closed as noise.

**Wave:** 2026-11-23 backlog chain S1, 03:41→11:25Z, same pinned 1.7.1 instance (supervisor 6987), no restarts,
`tau2-bench v1.0.1` @ `fc0055dc…`, instrument unmodified. **714/714 scored, 0 infrastructure_error**;
re-derivation via `build_rows.py` agrees; tenancy clean: 0 co-tenant request-samples, 0 spill moves,
0 suspension deltas (summarize.py).

| domain | pass^1 / pass^2 / pass^3 |
|---|---|
| airline | 0.840 / 0.840 / 0.760 |
| retail | 0.770 / 0.676 / 0.568 |
| telecom | 0.886 / 0.807 / 0.746 |
| **AGGREGATE (238 tasks)** | **0.8403 / 0.7731 / 0.6933** |
| mixed-outcome tasks (flips) | 64 / 238 (26.9 %) |

**Verdict:** pass^3 **0.6933 exactly equals the 1.7.0 headline anchor**, flips 64 in both 1.7.1 waves — the
consistency layer is epoch-stationary. pass^1: both 1.7.1 draws (0.8109, 0.8403) below both 1.7.0 draws
(0.8613, 0.8655); epoch means 0.8256 vs 0.8634 = −3.8 pts ≈ 1.2 SE at n=2/epoch. **Neither pre-registered
branch fires cleanly**: it is not ≈0.81 again, but not ≈0.86 either. Published as the epoch RECORD states —
no distribution-shape change; a possible 2–4 pt pass^1 dip unresolved at n=2, disclosed, not adjusted away.
Further tiebreaking (n=3 per epoch) is possible but the honest statement doesn't change materially; deprioritized.
