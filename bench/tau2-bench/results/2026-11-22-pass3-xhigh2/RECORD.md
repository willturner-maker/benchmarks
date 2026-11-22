# τ² xhigh replication wave (2026-11-22) — the second 238×3 `reasoning_effort: xhigh` wave

Purpose (pre-registered before launch): decide whether the effort A/B's aggregate gain survives the
uncertainty bands published after the determinism probe. Criteria fixed in the launch message:
**pass^1 > 0.8824** (above every medium wave seen) to establish a pass^1 effect; the pass^3 signal
stands if it reproduces at/above the first xhigh's 0.7143 against the medium pair (0.6933 / 0.7059).

## Protocol

Identical to `../2026-11-21-pass3-xhigh/` (RECORD there): τ² v1.0.1 @ `fc0055d…`, 238 judge-free tasks
(airline 50 + retail 74 + telecom 114), 3 trials, seed 300, self-play, temperature 0; agent args gain
`"reasoning_effort":"xhigh"`, **user-simulator args untouched**. Engine: Splash 1.7.0 pinned argv,
instance `19a70e8c777ce1a5b69b138b`, wave 02:41Z → 06:41:30Z (**220 min** — 4 h 20 m, cost ~free again:
vs the medium replay's 227 min; prefill Δ4.21 M tok vs 4.34 M, decode Δ3.17 M vs 3.25 M).
714/714 scored, 0 infrastructure errors, upstream re-derivation AGREES in every domain (rule 6).

## Scores

| scope | pass^1 | pass^2 | pass^3 | always-pass / disagree / never |
|---|---|---|---|---|
| airline (50) | 0.8733 | 0.8133 | 0.7600 | 38 / 9 / 3 |
| retail (74) | 0.8288 | 0.7252 | 0.6486 | 48 / 23 / 3 |
| telecom (114) | 0.9064 | 0.8333 | 0.7807 | 89 / 25 / 0 |
| **aggregate (238)** | **0.8753** | **0.7955** | **0.7311** | **175 / 57 / 6** |

The full four-wave picture (all 238-task 3-trial waves on this stack):

| configuration | pass^1 | pass^2 | pass^3 | disagree |
|---|---|---|---|---|
| medium (20-pass3, old epoch) | 0.8501 | 0.7591 | 0.6933 | 65 |
| medium (21 replay, new epoch) | 0.8445 | 0.7633 | 0.7059 | 58 |
| xhigh 1 (21, new epoch) | 0.8641 | 0.7759 | 0.7143 | 63 |
| **xhigh 2 (22, new epoch)** | **0.8753** | **0.7955** | **0.7311** | 57 |

## Verdict against the pre-registered criteria

- **pass^1: NOT established.** 0.8753 lands **inside** the medium band (0.8445–0.8824). Two xhigh waves
  (0.8641, 0.8753) sit above both medium waves (0.8501, 0.8445), a consistent +1.5 to +3 pts ordering,
  but single-wave pass^1 remains inside the band. Published claim: directional ordering, not established
  pass^1 superiority.
- **pass^3: REPLICATED.** Both xhigh waves (0.7143, 0.7311) exceed both medium waves (0.6933, 0.7059),
  and the same holds at pass^2 (0.7759/0.7955 vs 0.7591/0.7633). The pattern is 2-for-2 at higher-k,
  monotone in xhigh ordering — this is now the honest headline of the effort A/B:
  **xhigh does not raise the single-trial ceiling; it makes passing more consistent**
  (pass^3/pass^1 ratio: medium 0.815 / 0.836 → xhigh 0.827 / 0.835, and always-pass tasks rise
  165→170→175 while never-pass stays 5–8).
- **Flip rate unmoved again**: 57/238 (24.0 %) disagree vs 58 (replay), 63 (xhigh1), 65 (medium) —
  effort does not tame the engine lottery; consistent with the determinism probe (the instability is
  decode-side, not reasoning-budget-side).

## Caveats

- Both medium waves and both xhigh waves: n=2 each; the pass^3 ordering is 2-vs-2 clean separation, but
  per-domain movement is still roster-shuffle (airline pass^3 dipped 0.7143→0.7600→(medium replay 0.82) —
  domain rosters, as rule 9 says, do not replicate).
- Tenancy: co-tenant request-samples **4** (max 29,539 tok), spill moves Δ**0**, suspensions Δ**0** —
  the cleanest 3-trial window this suite has run; no confound flags. (`kv_demotions` Δ8,153 is
  persistent-cache churn, informational per prior records.)
- Drafter ON (Δdrafted 3,557,981 / Δaccepted 2,275,684 = 64.0 % acceptance, in-line with every other window).

Files: `tasks.jsonl` (714 rows), `summary.json` (if present via summarize), engine samples, status edges,
per-domain logs, `runner.log` (launch line + exit). Transcripts local.
