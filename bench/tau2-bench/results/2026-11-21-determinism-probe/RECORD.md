# Same-request determinism probe (2026-11-21/22) — the engine is a per-request coin flip at temperature 0

> **CORRECTION (2026-11-22, same day) — supersedes the action-identity numbers below.** The published
> "identical action 15–40 %" figures used an action metric that included **tool-call `id` fields**, which
> this engine mints **random per request** (`call_<random-hex>_<idx>`; measured: function+arguments byte-
> stable across repeats, ids never). Every tool-call message was therefore a false "action change".
> Re-run with the corrected metric (ids excluded; bug-trail files `*_idbug` kept):
>
> | arm / stratum (n=40) | identical action (corrected) | identical full message | matched original action |
> |---|---|---|---|
> | seq · agent | **20/40 = 50.0 %** | 4/40 = 10.0 % | 27/40 = 67.5 % |
> | seq · user | **12/40 = 30.0 %** | 7/40 = 17.5 % | 13/40 = 32.5 % |
> | mix · agent | **22/40 = 55.0 %** | 6/40 = 15.0 % | 24/40 = 60.0 % |
> | mix · user | **12/40 = 30.0 %** | 8/40 = 20.0 % | 14/40 = 35.0 % |
>
> What SURVIVES: per-request nondeterminism is real and immediate (first-diff median 27 chars; thinking
> text almost never repeats — full-message identity only 10–20 %), batch width is irrelevant (agent 50 vs
> 55 %), and conversation transcripts will never reproduce (message-level instability compounds over turns).
> What DIES: the "~85 % action coin flip" phrasing — the true action-level flip is ~45–50 % for agent
> calls, and telecom reads *more* stable at user level (see the telecom record). The task-level 15.1 %
> reward-flip floor is now read as the environment absorbing a ~50 % call-level action lottery, not an
> 85 % one. Everything below this box is kept as the measurement of the *message* level plus the bug trail.


The same-seed pair (see `../2026-11-21-sameseed-pair/RECORD.md`) established that τ² flips are
engine-side, not user-resampling, and left the mechanism question open: is the nondeterminism
**per request** (an identical prompt alone on the engine re-decodes differently) or only
**cumulative at conversation depth** (single requests are stable, drift emerges as context grows)?
This probe answers it at the request level, and the answer is **per request, overwhelmingly**.

## Method (disclosed deviation: instrument unmodified, network path instrumented)

- **Phase A — capture.** A normal τ² wave (airline, 25/50 tasks via every-other id, 1 trial,
  seed 300, max_concurrency 3, all published args) with `api_base` pointed through a
  **transparent logging proxy** (`proxy_capture.py`, port 8011 → engine 8000). Every
  `/v1/chat/completions` wire body + engine message recorded verbatim: **430 requests
  (276 agent-with-tools, 154 user-sim)**. Wave exit=0 (23:33:41Z → 23:43:49Z). No tau2 code changed;
  only the api_base value deviates for the capture wave (it is a harness knob, not an instrument edit).
- **Phase B — re-query.** Sampled bodies (40 agent + 40 user, stratified by prompt-size quartile;
  sampled range 2.3 k–40.6 k chars) re-POSTed **verbatim, engine-direct** (proxy out of the path),
  two arms:
  - `seq`: 3 repeats back-to-back, nothing else in flight (repeats 2–3 reuse the prefix cache
    repeat 1 created — cache state between repeats is *similar*, not identical);
  - `mix`: 3 repeats, each concurrent with 2 other distinct requests (decode-batch width ≈ 3,
    fresh mates each repeat).
- Identity axes: **action identity** (content + tool_calls only — thinking text can churn while the
  chosen action does not change) and **full-message identity** (incl. `reasoning_content`), plus
  match-against-the-original-wave-output.
- Two earlier runs are kept as evidence of the tooling's own bug trail: `*_run1` (metric conflated
  thinking churn; mix arm recorded each repeat alone, so its 100 % "agree" was vacuous) and
  `*_run2` (fixed metrics but quartile-slicing bug capped the sample at 16/18). **Published numbers
  are run3 only** (full 40/40 sample, exit=0, 22-min window).
- Engine: Splash 1.7.0 instance `19a70e8c777ce1a5b69b138b` (same instance for capture and re-query),
  pinned argv, drafter ON, effort medium default. Sampler bracketed both windows
  (`engine_samples_capture.jsonl`, `engine_samples_run3.jsonl`).

## Result (run3, reps=3, n=40 per cell)

| arm / stratum | identical action | identical full message | matched original action |
|---|---|---|---|
| seq · agent | **6/40 = 15.0 %** | 5/40 = 12.5 % | 11/40 = 27.5 % |
| seq · user | **11/40 = 27.5 %** | 7/40 = 17.5 % | 20/40 = 50.0 % |
| mix · agent | **6/40 = 15.0 %** | 4/40 = 10.0 % | 10/40 = 25.0 % |
| mix · user | **16/40 = 40.0 %** | 12/40 = 30.0 % | 17/40 = 42.5 % |

Structure within the result:

- **Depth gradient:** small-prompt half agrees 30–45 %, large-prompt half 18–22 % — depth makes it
  worse, but shallow prompts are nowhere near deterministic either (30 % at best).
- **Batch width does not matter** (agent: seq 15.0 % = mix 15.0 %; n=40 each) — consistent with the
  19b width control at conversation level; the mechanism is not decode-lane batching.
- **Divergence is early:** among text-diverging pairs, the first difference sits at median char 25,
  and 17/85 within the first 2 characters — not late-decode drift.
- **User-sim calls are more reproducible than agent calls** (27.5–40 % vs 15 %) — shorter outputs,
  fewer chances to diverge. This sharpens rather than solves the same-seed pair's 3:1 user-first
  onset: user turns are the *first* turns, and per-request instability is already ~70 % at the very
  first exchanges.

## What this establishes, and what it does not

**Established:** at temperature 0, on one pinned engine instance, an *identical single request*
reproduces its own action only **15 % (agent) / 27.5 % (user)** of the time (6/40, 11/40; Wilson 95 % CIs
≈ 7–28 % and 16–44 % — the agent/user gap is within noise at n=40, so the safe published claim is
"15–40 %, agent calls at the low end"). The nondeterminism is
per-request, essentially immediate, and independent of batch width. Every pass^k on this stack is
therefore sampling an ~85 %-action-unstable call stream; task-level reward flips (15.1 % floor) are
the environment *absorbing* most call-level instability.

**Not established (candidate micro-mechanisms, untested here):** why a greedy decode is unstable —
int8 cached KV states vs bf16 fresh prefill precision differences (the seq arm's repeats 2–3 hit the
cache repeat 1 built and *still* disagree, which argues against a pure cache-vs-prefill story but
does not exclude graded cache-state effects); the drafter accept/verify path (drafter was ON
throughout; a drafter-on/off comparison is *impossible* on 1.7.0 — see
`../../splash-concurrency/results/backlog-chain-2026-11-21/ARM-FINAL.md`). Naming a micro-mechanism
would need engine telemetry we do not have.

**Scope caveats (disclosed):** airline only (user's decision — the depth gradient predicts telecom
is *worse*, untested); single engine instance, single epoch; the original-wave comparison mixes
cache states (that is the point of that column, not a flaw in the repeat-vs-repeat columns);
free-text transcripts/proxy bodies stay local (`captures.jsonl`, 430 records) per suite policy —
`probe_rows.jsonl` (240 rows) is the published evidence.

## Consequences for the suite

1. Rule 9 gains its per-request floor: quote determinism at the *request* level, not the
   conversation level; conversation-level "reproducibility" claims are downstream statistics.
2. Any future "did my change alter behavior" A/B must use action-identity probes at request level —
   conversation-level pass^k noise was always going to swamp small effects.
3. The τ² leaderboard rows stand as measured (they were never claimed deterministic), but the
   honest description of the engine underneath them is now: **per-request greedy decode at
   temperature 0 is ~85 % action-unstable on repeat** — the strongest single sentence this suite
   has produced about the stack.

Files: `probe_rows.jsonl` (+ `_run1/_run2` bug-trail evidence), `requery_summary.txt`,
`captures.jsonl` (local), `probe.log`, sampler files, status edges, scripts one level up
(`proxy_capture.py`, `run_probe_capture.py`, `probe_requery.py`, `run_probe_chain.sh`).
