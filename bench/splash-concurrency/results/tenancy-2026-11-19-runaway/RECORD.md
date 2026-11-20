# INVALIDATION RECORD — tenancy repro runaway, 2026-11-19/20 (engine counters carry the footprint)

**Not a measurement.** This run produced no publishable arms: its "clean" arm was contaminated by the operator's
own agent session, and the co-tenanted arm never recorded a round because of an instrument deadlock that then
hammered the engine for **15 h 45 m**. This record exists because the run moved engine **lifetime counters**, and
every later wave on this instance inherits that carry-in.

**What ran.** `tenancy_repro.py` at commit `a04d78f`, wrapper started `02:52:08Z`. Arm A (clean) started after a
90 s lead-in; arm B started the 3 co-tenant sessions ~02:54:45 and then called `wait_idle()` before its first
round — but a co-tenant keeps the scheduler non-zero **by design**, so the wait never returned. The script had no
deadline. It was killed at ~18:37 local (`15:45:37` elapsed) after the sampler's hour had already ended.

## The two failures

1. **The clean arm was not clean.** The wave's own 10 s sampler caught the operator's agent session decoding
   **79,493 → 82,972 token** requests at `02:53:38`/`02:53:48`, and an `82,972` request still decoding at
   `02:54:08` — inside arm A's only recorded round (2 × 22,906 tok at `02:53:58`). The 90 s lead-in protects only
   the message sent *before* launch; the operator kept working, and every operator turn is an engine request.
2. **Deadlock by construction + no watchdog.** `run_arm()` opens every round with `wait_idle()`; under a
   continuous co-tenant that is unsatisfiable. First recorded (and only) arm-B phase: 3 co-tenant requests of
   **128,126 tokens** each, prefilling/queued from `02:54:28` to the kill.

## Confounded observation, stated as observation only

Arm A round w2 r1: 45,812 prompt tok = **0.30× the resident budget**, fresh prefill confirmed (49,321 rows), and
**`resource_suspensions` +1** — no spill, no `waiting_memory`. Taken alone this is noise-level; taken with the
sampler it is a *hint*: combined in-flight demand ≈ 128,784 tok ≈ **0.83× budget** — i.e. a suspension appeared
below the resident line while an **operator context was co-resident**, which is the direction the 16b trip points
and the 19c-clean single-tenant wave never produced. n = 1, uncontrolled co-tenant size, one suspension: **not
evidence**, and this record publishes it nowhere but here.

## Engine footprint (why later records must cite it)

Lifetime counters, this instance, never restarted:

| edge | resource_suspensions | spill_moves | disk.kv_demotions |
|---|---|---|---|
| at tenancy start `02:52:08Z` | 4 | 32,625 | 9,045 |
| after kill (post-mortem read) | **7** | **3,135,729** | **9,209** |
| runaway footprint | +3 | +3,103,104 | +164 |

The 15 h 45 m of unintended steady state was 3 × 128,126-tok contexts (≈ 2.47× the resident budget) continuously
present. Qualitatively the engine shrugged it off: **no refusals, no capacity failures, no collapse**, ~3.1 M spill
moves absorbing it in memory and only 164 disk demotions. It was idle and responsive immediately after the kill.
That is a survivability observation, not a benchmark.

## Fixes that went in with this record (see commits after `a04d78f`)

- `run_arm` skips `wait_idle()` whenever a co-tenant is running (a co-tenanted engine never idles by design).
- Hard `--deadline-minutes` (default 25) checked by `run_arm` and by each co-tenant worker.
- Co-tenant workers get a 2 s duty gap so rounds can actually start.
- `run_tenancy_detached.sh`: wrapper with pins, status edges, 10 s sampler, 90 s lead-in, deadline, and an
  attribution read-back that flags **both** request families and calls anything else (including the operator)
  foreign.
- Suite **rule 11**: zero operator engine calls for the whole window — end the turn, wait for the completion
  notification, then analyse.

## Files

Raw artifacts stayed at `~/splash-tenancy-2026-11-19/` (out of repo: `tenancy_repro.jsonl` one round + header,
`run.out`, 360 engine samples covering 02:53→03:53, `status_before.json`; no `status_after.json` — the wrapper
was killed before it ran).
