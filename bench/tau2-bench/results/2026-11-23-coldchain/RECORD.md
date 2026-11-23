# Cold-state chain 2026-11-23 — cache-state probe + the n=3 pass^1 tiebreaker

Runner `../../run_coldchain_171.sh` (commit `d0363db`), 13:53→18:16Z. Sequence: supervisor-gated
stop (pid 34982) → prefix-cache **parked** by `mv` to `~/Library/Caches/Splash/prefix-cache-pre-cold-2026-11-23`
(256 G, reversible; weights untouched — they live in the Hugging Face cache) → pinned-argv cold
relaunch (pid 61044, ready in 6 s) → **cold** determinism-corpus re-POST → warm 238×3 tiebreaker.

## P4 — does cache state touch the action lottery? **No.**

Corpus re-POST (`probe_requery.py`, reps 3, sample 40) on the engine with an EMPTY prefix cache —
agent-cell identical-action rates, cold vs the warm 1.7.1 re-run vs the 1.7.0 original:

| corpus | 1.7.0 original | 1.7.1 warm re-run | **1.7.1 COLD** | match-to-original (cold) |
|---|---|---|---|---|
| airline | 50.0 / 55.0 % | 55.0 / 57.5 % | **50.0 / 55.0 %** | 67.5 / 67.5 % |
| telecom | 52.5 / 45.0 % | 42.5 / 37.5 % | **42.5 / 47.5 %** | 42.5 / 42.5 % |

Cold numbers sit inside the n=40 cell bands (1 SE ≈ 8 pts) of both warm columns — the lottery
distribution is **cache-state stationary**. Cross-check: the cold corpus window shows 0 spill moves,
0 suspensions, 0 waiting-memory (kv demotions ≤50 — the normal mechanism at work, not a trip), so the
cold boot did not even reproduce pressure conditions. The known 1.7.1 cold-cycle expert-store issue
left no measurable aggregate mark in this window. **The "something" behind the (now-closed, below)
pass^1 candidate is not cache state.**

## P5 — the pre-registered tiebreaker: **gate closes the dip as noise**

`../2026-11-23-pass3-171-n3/` (third 238×3 medium wave on 1.7.1; 714/714 scored, re-derivation agrees,
0 co-tenant/0 spill/0 suspensions; warmth provenance disclosed in the runner header: warm from the
corpus itself rather than prior waves). Gate as written: ≥0.85 ⇒ noise; ≤0.81 same-shape ⇒ dip.

**pass^1 = 0.8613** — at the top of the 1.7.0 draw range (0.8501/0.8613/0.8655). **Gate branch: noise.**

| epoch draws (238×3 medium) | pass^1 | pass^2 | pass^3 | flips |
|---|---|---|---|---|
| 1.7.0 | 0.8501 / 0.8613 / 0.8655 | 0.7591 / 0.7647 / 0.7731 | 0.6933 / 0.6933 / 0.7059 | 24–27 % |
| 1.7.1 | 0.8109 / 0.8403 / **0.8613** | 0.7521 / 0.7731 / **0.7857** | 0.6891 / 0.6933 / **0.6849** | 26.9 / 26.9 / 29.8 % |

Epoch means now: pass^1 0.8375 vs 0.8590 (−2.2 pts ≈ 0.7 SE — inside noise); pass^2 0.7703 vs 0.7656
(+0.5); pass^3 0.6891 vs 0.6975 (−0.8 ≈ 0.5 SE). Flips 71/238 (29.8 %) is the highest draw on record
(+1.1 SE above the old band) — single-wave band wobble, same direction as pass^3's small dip, consistent
with one slightly luckier trial-1 draw and slightly noisier per-task rollouts, not an epoch mechanism.

**Final epoch statement (supersedes the n=2 version in `../2026-11-23-epoch171/RECORD.md`):**
the Splash 1.7.0→1.7.1 move is **statistically quiet on every measured layer at n=3 per epoch** —
including the pass^1 candidate that stayed open through n=2. Nothing to report upstream; the published
pass^1 band for medium effort is now **0.81–0.87 across both epochs**, a single distribution.

Cleanup owed after this record (operator): delete the parked cache
(`rm -rf ~/Library/Caches/Splash/prefix-cache-pre-cold-2026-11-23`) — safety net no longer needed.
