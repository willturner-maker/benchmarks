# splash-1.7.0-2026-11-19c-clean — the single-tenant rerun of the queue-size 64 stack

**Window:** `2026-11-20T01:10:19Z → 02:15:19Z` (65 m), one detached invocation via `../../run_clean_detached.sh`,
operator idle. **Engine:** Splash **1.7.0**, the **same instance as the 19b wave, NOT restarted** — lifetime
counters therefore start non-zero and every figure below is a **window delta**.
**Stack (read from the running supervisor, `pins.txt` / `engine_config.json`):** `--max-memory=60129542144
--max-cache-disk=274877906944 --persistent-cache --default-reasoning-effort=medium
--thinking-token-budget=32768 --queue-size=64`; KV budget **155,648 tokens** (4,864 pages × 32),
`memory_plan.budget.maximum_batch_width = 4`.
**Instrument:** `kv_bracket_2026-11-19b.py`, unchanged, widths `12,33,36,40,44,48`, fresh seed namespace.

## Tenancy: proven by read-back, not asserted

390 `/status` samples at 10 s, and every in-flight request attributed. **7,034 samples carry this wave's own
prompt sizes** (55,265 tok KV, 29 tok ladder). **One foreign request** appears — 98,779 tokens, `prefill`, at
`01:10:19`, i.e. **93 s before the first timed stage**, the operator's last message before going idle. Inside
the timed stages: zero co-tenant traffic. This is the window the 16b and 19b waves could not claim.

**A bug worth recording, because it nearly buried a good wave.** The runner's first tenancy check counted
"requests over 20,000 prompt tokens" as operator traffic and printed **`NOT single-tenant`, 6,851 samples**.
Those were this wave's own KV prompts (55,265 tokens each). A size threshold cannot tell co-tenant traffic from
a long-context benchmark's own traffic; attribution has to use the prompt sizes the wave itself recorded. The
check in `run_clean_detached.sh` was rewritten accordingly before this wave was published.

## Stage 0 — warmth gate: soft again, same value as 19b

decode w1 on `LADDER_PROMPT` @512 = **274.5 / 314.1 / 307.7 tok/s**, spread **1.144** → gate "soft"
(pass ≤ 1.10). 19b measured 1.138 on the same primitive. Two waves, same instrument, same soft band: this
engine's own w1 run-to-run spread sits just above the pass threshold, so treat the gate as a **1.13–1.15
band**, not a defect of the wave that reports it.

## Stage 1 — sealed width ladder in a clean window

| width | 1 | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 24 | 32 |
|---|---|---|---|---|---|---|---|---|---|---|
| **19c median tok/s** | **308.75** | 487.05 | 564.2 | 690.9 | 627.35 | **700.55** | 694.4 | 698.95 | 692.0 | 697.15 |
| 19b median (for diff) | 307.1 | 417.0 | 581.2 | 724.6 | 613.3 | 698.9 | 647.5 | 700.7 | 698.0 | 699.5 |

- **w1 = 308.75** (rounds 305.7 / 311.8 — the tightest w1 pair in the 1.7.0 series). This replaces the
  tenancy-taxed w1 cell as the clean-window reference for queue-size 64. 19b read 307.1, so w1 **did not**
  depend on the tenancy that wave lacked.
- **Plateau w12–w32 mean 695.6** (19b: 686.4): the plateau is a stable engine-instance property across two
  waves on the same launch. Peak **700.55 at w8**; the w6 dip (627.35) reproduces from 19b (613.3).
- Stop rule never fired. `peak_admission_waiting` is now clean and monotone: 0 / 0 / 0 / 0 / 2 / 4 / 8 / 12 /
  12 / 12 at w1…w32 — 12 is the standing ceiling on this build.
- w2 differs most between the waves (487.05 here vs 417.0 there). With clean tenancy here, the 19b w2 cell is
  the suspect one; **do not diff individual mid-width cells across these two waves** — the plateau and w1 agree,
  and that agreement is the comparable part.

## Stage 2 — KV pressure: **no trip at 17.04× the resident budget**

| width | tokens (× budget) | wall s | ok / refused | prefill tok/s | Δ suspensions | Δ spill | Δ demote | peak pages_active |
|---|---|---|---|---|---|---|---|---|
| 12 | 663,180 (4.26×) | 189.6 | 12 / 0 | 3,497.8 | 0 | 0 | 0 | 1,920 |
| 33 | 1,823,745 (11.72×) | 522.5 | 33 / 0 | 3,490.6 | 0 | 0 | 0 | 1,920 |
| 36 | 1,989,540 (12.78×) | 570.9 | 36 / 0 | 3,485.1 | 0 | 0 | 0 | 1,920 |
| 40 | 2,210,600 (14.20×) | 633.3 | 40 / 0 | 3,490.8 | 0 | 0 | 0 | 1,920 |
| 44 | 2,431,660 (15.62×) | 700.5 | 44 / 0 | 3,471.5 | 0 | 0 | 0 | 1,920 |
| **48** | **2,652,720 (17.04×)** | 764.7 | 48 / 0 | 3,469.0 | **0** | **0** | **0** | **1,920** |

Every round is **fresh prefill** (`scheduler.prefill_rows` delta equals the round's prompt tokens in all six;
no cache-served round), **11,771,445 tokens of prefill** total. No refusals, no suspension, no spill, no
demotion, `capacity_failures` and `kv_demotions_refused` unmoved. Stage wall 3,381 s ≈ 11.77 M / ~3,480 tok/s,
i.e. the stage is entirely prefill-bound.

**Why it never trips — and this corrects the earlier framing.** `pages_active` peaks at **1,920 pages = 61,440
tokens = 0.39× the budget** in every round, while queued goes 11 → 47 and `prefilling` never exceeds 2 with
`decoding` 1. The scheduler does not admit width into KV: extra width becomes **queue depth**, and the resident
set stays around **one 55 k-token context**. So "KV pressure" is unreachable by raising concurrency on this
build at this prompt size — the wall is the **~3,470–3,500 tok/s prefill ceiling**, which is flat from w12 to
w48 (+0.8 % spread) exactly as `maximum_batch_width = 4` implies.

That reframes the 2026-11-16b entry, published as "first trip on record: stopped at w10, 509,370 tokens =
3.89× budget, peak suspended 2, +3 lifetime resource_suspensions, demote +1502". In a clean window on a later
engine state, **4.4× that pressure produced no trip at all**. So the 16b trip was not a token-count threshold:
it came with `waiting_memory` and `admission.waiting` movement, i.e. a different admission regime, in a window
with operator traffic on the engine. **The 19b caveat "clean-window rerun needed before reading the threshold
as a finding" is now discharged, and the reading is: no threshold at 17×.** Reproducing 16b's trip would need
its admission regime (co-tenant residency), not more prompt tokens — which is a claim about how it was produced,
not a measured mechanism.

## Comparability

- Same launch as 19b (not restarted): lifetime counters at window start were `resource_suspensions 4`,
  `kv_demotions_refused 1287`, `spill_moves 18445`; all deltas in this wave are zero, and none of those
  counters moved by the end (`resource_suspensions 4`, `spill_moves 18445`).
- The 12-request KV width here (4.26×) overlaps the 16b stop width, so the two are directly comparable at the
  low end, and they disagree: same magnitude of prompt volume, trip vs no trip. Tenancy and engine state are
  the difference.
- Do not compare the ladder's absolute plateau to pre-1.7.0 waves (1.6.1 sat 470–525); queue-size 64 and the
  thinking-budget raise bind at launch, and this instance carries them.

## Files

`ladder_kv.jsonl` (stage 1 + 2 rows), `warmth_gate.jsonl`, `run.out` (the wave's own stdout incl. the
`SUMMARY`), `run.err` (empty), `run.log` (window edges), `engine_samples.jsonl` (10 s samples, the tenancy
read-back), `status_before.json` / `status_after.json`, `pins.txt`, `engine_config.json` (supervisor flags,
`~`-scrubbed, lifetime-at-start). Absolute local paths in `engine_config.json` are replaced with `~`.
