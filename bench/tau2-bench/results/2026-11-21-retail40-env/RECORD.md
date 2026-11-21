# τ² retail judge-dependent 40 — ENV-component closure wave (2026-11-21)

Closes the suite's only scope gap: the 40 retail tasks whose published `reward_basis` includes
`NL_ASSERTION` were excluded from every scored row because the v1.0.1 judge (`gpt-4.1-2025-04-14`)
has no local override and no key exists here. This wave runs **exactly those 40 tasks** and scores
them on the **environment components only** — the published number below is a *component score*,
not a pass^k row.

## Method (disclosed deviation, unmodified source)

- Seam: `tau2.runner.run_tasks(cfg, tasks, ..., evaluation_type=EvaluationType.ENV)` called as a
  library (`run_retail40_env.py`), mirroring `run_domain`'s task loading and save paths exactly.
  `run_domain` itself **cannot** do this — it never forwards `evaluation_type` (that omission is
  what killed attempt 1; see `FAILURE-attempt1.md` in this dir: 80/80 infrastructure_error,
  judge fired despite the ENV request, quarantined locally at tau2
  `data/simulations/wave-QUARANTINE-retail40-env-attempt1/`).
- ENV scoring = DB end-state checks + env assertions only. **No judge is called anywhere**: the
  NL evaluator is never entered at `EvaluationType.ENV` (evaluator.py:171). No COMMUNICATE
  component either — both are simply absent from these rewards.
- What the row is for: it replaces "no number at all for the 40" with the DB-component result.
  It is **not comparable** to the published retail pass^k (different 74 tasks, and those scores
  include the COMMUNICATE component).

## Protocol

- Instrument pin: `v1.0.1` = `fc0055dc4e0a316c3f83133267fbd6faaa770992`; task scope = all 114
  retail ids minus the `RETAIL_FREE` array (74) — computed from `run_wave.sh`, asserted 40.
- 2 trials, seed 300 (trial seeds 626729/373753), self-play, temperature 0, max_concurrency 3,
  model/args identical to every published wave.
- Engine: Splash 1.7.0, instance `08d662f6ada5b1b1ae93fff5` (same instance as the pass^3 replay
  above), pinned argv. Wave 20:17:08Z → 20:38:34Z (21.5 min), 80/80 scored, 0 infrastructure errors,
  all terminations `user_stop`.

## Result (ENV component only)

| measure | value |
|---|---|
| **ENV-component pass^1 (40 tasks)** | **0.6625** (mean reward 0.6625, DB-component) |
| ENV-component pass^2 (adjacent trials) | 0.5500 |
| trial split | both-pass 22 · disagree 9 · never 9 |
| flip rate | 9/40 = **22.5 %** — inside the known 15–27 % band, another replication |
| tool calls | 623 (7.79/sim) · completions 1,402 · prompt 7.64 M tok · completion 304 k tok |
| max call depth | 14,094 tok (0.091× KV budget) |

Context, not a comparison: judge-free retail pass^1 on the same day's replay was 0.7703 with
DB+COMMUNICATE scoring. The 40 are plausibly harder (they carry qualitative assertions), and the
DB-only reading strips the COMMUNICATE credit the 74 get — the two numbers bracket a gap, not a delta.

## Tenancy

Same-window as the tail of the replay-era instance: Δprefill 540,103 tok, Δdrafted 332,715
(drafter acceptance active — this was NOT the drafter-off window), sampler 129 samples/10 s.
No status-edge anomalies; no co-tenant wave overlap beyond this agent's own session.

## Follow-ups this wave settles

1. The 40 are no longer an unmeasured scope: their DB-component behavior is on the record and
   their flip rate replicates the suite's noise finding.
2. If a gpt-4.1-class judge ever becomes available, the published transcripts-local sims can be
   rescored with `ALL_WITH_NL_ASSERTIONS` without rerunning conversations.
3. Attempt-1's seam bug is now documented for anyone reusing this runner: in v1.0.1,
   `evaluation_type` is a `run_tasks` parameter only — never put it in `TextRunConfig`.

Files: `tasks.jsonl` (80 rows, re-derivable), `retail40_rerun.log` (the good run),
`retail40.log` + `FAILURE-attempt1.md` (the failed attempt, kept as evidence),
`engine_samples_rerun.jsonl`, `status_rerun_{before,after}.json`. Transcripts local only.
