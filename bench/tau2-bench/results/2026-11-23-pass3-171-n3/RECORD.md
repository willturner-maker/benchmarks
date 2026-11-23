# n=3 tiebreaker wave — 238×3 medium on 1.7.1 (third draw; closes the pass^1 question)

Third 1.7.1 three-trial medium wave, 14:27→18:16Z, cold-chain P5 (see `../2026-11-23-coldchain/RECORD.md`
for the runner, cold-boot provenance, and the pre-registered gate). 714/714 scored, 0 infrastructure_error,
tenancy clean (0 co-tenant / 0 spill / 0 suspensions).

| domain | pass^1 / pass^2 / pass^3 | flips |
|---|---|---|
| airline | 0.880 / 0.820 / 0.740 | 11 |
| retail | 0.851 / 0.770 / 0.608 | 27 |
| telecom | 0.860 / 0.781 / 0.711 | 33 |
| **AGGREGATE** | **0.8613 / 0.7857 / 0.6849** | **71 (29.8 %)** |

**Gate: pass^1 0.8613 ≥ 0.85 → the 2–4 pt 1.7.1 pass^1 dip is CLOSED AS NOISE.** This draw tops the
1.7.0 range; the six-draw per-epoch picture is one overlapping distribution (band 0.81–0.87 across both
epochs). pass^2 0.7857 is the highest draw on record; pass^3 0.6849 and flips 29.8 % are ~1 SE wobbles
in the same direction. Rows re-derivable from `tasks.jsonl` (714 rows) via `build_rows.py`.
