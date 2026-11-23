# 2026-11-22 thinkbudget arm 65536 — tenancy event, stall, and dir-reuse hazard

Written during the run, not after, so the record is timestamped by the same clock as the samples.
No engine traffic was used to produce any number below: everything is read from `engine_samples.jsonl`,
process table and file mtimes.

## 1. Tenancy event — foreign load inside this arm's window (operator-caused)

A concurrency-ceiling probe run from a different session touched this engine mid-wave.

```
15:49:03   active=36  queued=32  prefilling=4  decoding=0  kv_tokens_active=128
           spill=0  demote=0  suspensions=0
```

- **1 sample out of 501** in this arm's window (14:42:58 → 16:06:24) exceeds the wave's own footprint
  (`run_wave.sh` → `tau2 run … --max-concurrency 3`).
- Max active in the whole window: 36. Max queued: 32. Both come from that single sample.
- The burst was tiny-prompt (≤32 completion tokens) and short: one round every ~4 s, ~3 s per round,
  4 rounds — so prefill-side contention for on the order of 10–15 s, nothing held after that.
- **No memory-path engagement at all, before or after**: `spill_moves`, `kv_demotions` and
  `suspensions` read 0 at that sample and 0 at the last sample (16:06:24).

**Assessment.** Any tau2 turn in flight at 15:49:03 paid a latency tax of a few seconds. tau2 scoring
here is outcome-level at `temperature 0`, and the wave's decode path was never oversubscribed
(`decoding` 0 in the event sample, `prefilling` ≤ 4), so the plausible mechanism for a score change is
batch-composition numerics at the sampled token, which cannot be excluded but is not evidenced.

**Disposition.** Do not void the arm: characterise it with this row. If a pristine arm is wanted, the
chain supports `TB_ARMS="65536"` resume and one arm costs ~75 min. Prevention: before any probe
against port 8000, check `scheduler.{queued,prefilling,decoding}` and `admission.waiting` for foreign
activity — the ceiling numbers themselves were already published by
`splash-1.7.0-2026-11-19b` (48 admitted, zero refusals), so this probe was unnecessary.

## 2. The arm is not running — it is blocked on an interactive prompt

`chain.log` ends at `arm 65536: engine ready, identity + argv verified` (22:42:58Z = 14:42:58 local)
with no `wave exit` line, and `airline.log` ends with:

```
File ~/tau2-bench/data/simulations/wave-2026-11-22-thinkbudget-65536-airline/results.json
already exists. Do you want to resume the run? (y/n)
```

Evidence it is stalled rather than slow:

| signal | value |
|---|---|
| tau2 pids 93565 / 93566 elapsed | 1 h 24 m |
| their CPU time, two readings 12 s apart | `0:00.02` / `0:00.88` — **identical, no progress** |
| engine `/status` | queued 0, prefilling 0, decoding 0, admission.waiting 0 (idle since well before) |
| the blocking `results.json` mtime | **11:58** — written by the *earlier* run of this same arm (11:41→12:54, which logged `arm 65536 wave exit=0`) |

`tau2 run` prompts when `--save-to` already exists; `--auto-resume` suppresses the prompt. The
chain's guard is upstream of this and behaved correctly: it aborted twice earlier today rather than
killing a busy engine (`engine still busy after 10 min … engine untouched`).

**Consequence worth acting on:** because `run_arm` never returns, the chain cannot reach its final
step, so **the 32768 pin is not restored** and the engine stays on the 65536 arm indefinitely. The
sampler and `serve.log` keep writing (16:06), which makes a stalled wave look like a live one.

## 3. Dir reuse mixes two runs of the same arm, silently

The resumed arm reuses `results/2026-11-22-thinkbudget-65536/`, so files from the completed 11:41→12:54
run and the stalled 14:42→ run coexist with no marker:

| file | mtime | belongs to |
|---|---|---|
| `retail.log` | 12:15:23 | earlier run |
| `telecom.log` | 12:54:57 | earlier run |
| `status_after.json` | 12:54:57 | earlier run — **will be overwritten** if this wave ever completes |
| `airline.log`, `wave.log`, `sampler.log`, `status_before.json`, `supervisor_pins.txt` | 14:42:58–14:43:02 | current run |
| `engine_samples.jsonl` | 16:06:24 | current run (starts at 14:42:58, earlier samples gone) |
| `wave.log` | — | appended: `wave started` and `===== airline =====` lines appear **twice**, once per run |

So `retail.log`/`telecom.log` in this directory are **not** from the wave that is nominally running.

## 4. What the fix is (deliberately not applied yet)

`run_wave.sh` must not be edited while it is executing: bash reads a script as it runs, so an in-place
patch can corrupt the live wave. Once the chain is stopped, the changes to make are:

1. stdin for the `tau2 run` call → `/dev/null`, so an unexpected prompt fails fast instead of parking
   the chain indefinitely (this is what hid the stall).
2. pre-flight check on `--save-to`: if the target exists, either add `--auto-resume` deliberately
   (`TB_RESUME=1`) or record a skip with the existing dir's mtime — never let the two runs blend.
3. tag `--save-to` (and the wave dir) per attempt, so a resumed arm cannot land on a completed arm's
   data.
4. have `wait_ready`/`run_arm` treat a wave with a zero-CPU-delta tau2 process as failed, so a blocked
   wave cannot masquerade as a running one behind a live sampler.
