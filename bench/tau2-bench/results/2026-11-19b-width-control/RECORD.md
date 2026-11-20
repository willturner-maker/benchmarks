# tau2 width control — 2026-11-19b (control experiment, not a scored row)

**Question.** Wave `2026-11-19a` flipped 45 of 238 tasks between two `temperature 0` trials. The row first
attributed that to batching (`maximum_batch_width = 4` at `--max-concurrency 3`). Does removing batching
actually remove the flips?

**Sample.** 8 of the 45 flipping tasks, chosen from the published `flip_triage.json` (3 airline, 3 retail,
2 telecom — the two telecom tasks are the agent-first flips at index 2 and 6). Each task then ran **two
trials per arm**, same seed 300, `temperature 0`, `max_tokens 4096`, upstream `--max-steps 200`.

| arm | τ² flag | decode batches observed (engine lifetime deltas) | peak in flight | co-tenant samples |
|---|---|---|---|---|
| **c1** | `--max-concurrency 1` | **b1 19,439 · b2 0 · b3 0 · b4 0** | **1** | **0** |
| **c3** | `--max-concurrency 3` | b1 1,757 · b2 1,347 · **b3 5,115** | 3 | 0 |

The arms are proven from `/status` sampled at 10 s (`engine_samples.jsonl`), not from the flag we passed:
**the c1 arm never batched at all** — every decode batch in the window was width 1, one request in flight,
zero co-tenant request-samples. c3 reproduces the published wave's shape (b3 dominant). Peak KV: 12,160 tok
(c1) / 19,424 tok (c3) against a 155,648-token budget.

**Result — batching is excluded as the mechanism.**

| condition | flips among the 8 | which ones |
|---|---|---|
| wave `2026-11-19a` (c3, co-tenanted) | 8 / 8 | all |
| control **c1** (never batched, operator idle) | **3 / 8** | retail 66, retail 90, telecom `mms_issue…both_permissions` |
| control **c3** (b3-dominant, operator idle) | **3 / 8** | airline 12, retail 90, retail 91 |

Same flip count under conditions that differ completely in batching, and **only one task (retail 90) is
unstable in all three passes**. So `pass^k` instability here is not a batching artifact; and "which task
flips" is not a stable task property either — per task across all 6 simulations the `reward == 1` counts
range from 2/6 to 5/6 (airline 12 4/6 · 29 3/6 · 33 5/6 · retail 66 2/6 · 90 3/6 · 91 2/6 · telecom 2/6 · 5/6).

**What still moves.** Even in the never-batched, single-tenant arm, the two trials' **user-simulator turns
are essentially never byte-identical**: airline 0/4, 0/4, 0/7 identical; retail 0/6, 1/5, 1/7. (Telecom
scores higher — 14/28 and 10/25 — only because its scripted confirmations repeat verbatim.) Same input,
`temperature 0`, nothing else on the engine, engine never batched → different greedy output, and it first
shows up in the user role. **The candidate that survives** is long-context numerical state — the same
persistent prefix cache that served 97.3 % of the wave's prompt volume — not batch composition. That is a
candidate, not a proven cause: the 2026-11-17 `verify_rows` A/B found no divergence on a short greedy prompt
(1/5 distinct = all identical), so the effect is visible at 10–16 k-token contexts and not at ~100-token ones.

**First attempt, invalidated and kept.** An earlier same-day run of this control (`width1-*` saves, status
edges published in this directory as `discarded_attempt_status_{before,after}.json`) was discarded before
analysis: the decode-width **delta across its own window is b1 14,329 · b2 8,190 · b3 409 · b4 0**, i.e.
**8,599 batches wider than b1 during a run we had passed `--max-concurrency 1` to**. Inline `/status` reads
during that window also showed operator-size requests in `spill` mode (my own session on the same engine),
though that run had no 10 s sampler, so that second observation has no saved sample series behind it — the
status-edge delta above is the citable evidence. "Concurrency 1" held for the τ² runner only. It reported 5/8
pairs agreeing; that number is not used anywhere, and the reason it is not used is recorded here rather than
the files deleted.

**Limits.** n = 8 sampled from 45 flips, one day, one engine launch (not restarted, so cache state carries
in from the wave — which is exactly the variable the surviving candidate points at). Behavioural outcomes
only: this control says nothing about throughput. Telecom at c3 reached peak KV 19,424 tok (0.12× budget),
so neither arm is a memory-pressure condition.

**Files.** `tasks.jsonl` (32 rows, `build_rows.py` field set, no transcripts), `width_control.json`
(per-arm engine widths + per-task agreement across the three passes), `engine_samples.jsonl` (10 s samples),
`status_before.json` / `status_after.json`, `control.log`, `pins.txt`. τ²'s own per-domain stdout
(`c{1,3}-{domain}.log`) contains task text and stays local, same rule as the wave's logs.
Runner: `../../width_control.sh`; the summary above is written by `build_control_record.py` in this directory
from tau2's own `results.json` files plus the engine samples, so the numbers here are re-derivable.
