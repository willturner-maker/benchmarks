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

- **1 sample out of 501** in this arm's window (14:42:58 → 16:06:24 as read; the sampler's last write
  was 16:14:55) exceeds the wave's own footprint (`run_wave.sh` → `tau2 run … --max-concurrency 3`).
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
run and the stalled 14:42→ run coexist with no marker. As observed at note-writing time (before the
sanitizing below changed every mtime — the timestamps here are **as-observed, not re-derivable**):

| file | mtime then | belongs to |
|---|---|---|
| `telecom.log` | 12:54:57 (its run began 12:15:23) | **completed run** — the only one of its three domain logs still intact |
| `status_after.json` | 12:54:57 | **completed run** |
| `airline.log` | 14:43:02 | stalled run — it **replaced** the completed run's airline log |
| `retail.log` | 12:15:23 → rewritten 16:14:59 | completed run's log **lost** — see below |
| `wave.log`, `sampler.log`, `status_before.json`, `supervisor_pins.txt` | 14:42:58–14:43:02 | stalled run |
| `engine_samples.jsonl` | last write 16:14:55 | stalled run (starts 14:42:58; the completed run's samples are gone) |
| `wave.log` | — | appended: `wave started` and `===== airline =====` appear **twice**, once per run |

**How the retail log was lost, owned plainly.** The kill order was chain → wave → tau2 leaves → sampler,
but `run_wave.sh` survived its kill long enough that when the airline leaf died, the loop advanced:

```
  exit=1 00:14:59Z
===== retail 00:14:59Z =====        (16:14:59 local)
```

That retail attempt hit the same resume prompt and died with `OSError: [Errno 5] Input/output error`
in `tau2/runner/checkpoint.py:try_resume` → `rich/console.py:input` → `input()` — i.e. the
no-stdin failure mode the new `</dev/null` change makes explicit and fast. Its stdout went to
`retail.log`, overwriting the completed run's copy. The lesson is procedural: kill the **leaf processes
first**, then the loop, so a supervisor can't advance into the next domain while being torn down.

**What still exists.** The wave's own logs are partial, but the measured data is intact — all three
`results.json` files in `~/tau2-bench/data/simulations/wave-2026-11-22-thinkbudget-65536-{airline,
retail,telecom}/` are present and untouched after 16:00 (verified by mtime scan). The 65536 arm is
therefore still analysable; only its console evidence is degraded.


## 4. What the fix is (deliberately not applied yet)

`run_wave.sh` must not be edited while it is executing: bash reads a script as it runs, so an in-place
patch can corrupt the live wave. Once the chain is stopped, the changes to make are:

1. stdin for the `tau2 run` call → `/dev/null`, so an unexpected prompt fails fast instead of parking
   the chain indefinitely (this is what hid the stall).
2. pre-flight check on `--save-to`: if the target exists, either add `--auto-resume` deliberately
   (`TB_RESUME=1`) or record a skip with the existing dir's mtime — never let the two runs blend.
3. tag `--save-to` (and the wave dir) per attempt, so a resumed arm cannot land on a completed arm's
   data.
## 5. Disposition (same day, after the note above was written)

**The stalled chain was cleared.** Intended order: chain → wave → tau2 leaves → sampler, so the chain
could not advance to another arm while its children died. **That did not fully work**: `run_wave.sh`
outlived its kill signal, and when the airline leaf died the domain loop advanced to retail (see §3),
which cost the completed run's retail console log and added a second aborted attempt to the record.
Correct order for next time: leaves first, then the loop, then the chain.

```
killed 93454 (run_thinkbudget_chain.sh) → 93539 (run_wave.sh) → 93565/93566 (tau2 airline) → 93555 (sampler)
post-check: no run_thinkbudget_chain|run_wave|tau2 run|sample_engine processes
engine after: ready true, queued 0, prefilling 0, decoding 0, admission.waiting 0
```

Nothing useful was lost. The chain had **already completed in full earlier today**:

```
2026-11-22T20:54:57Z  arm 65536 wave exit=0
2026-11-22T22:08:04Z  arm 32768 wave exit=0
2026-11-22T22:08:05Z  thinkbudget chain complete: pin restored (32768) and control wave done
```

with all six arm/domain `tau2` save dirs present (8192 airline/retail/telecom, 65536 airline 11:58 /
retail 12:15 / telecom 12:54, 32768 airline 13:10 / retail 13:27 / telecom 14:08). The 14:42 run was a
redundant re-run of a completed arm — and it is what put the **live pin back on 65536**.

**Open item:** the pin restore is not automatic any more, because the chain is gone. The engine needs
one relaunch to get back to the pinned `--thinking-token-budget=32768`; that is deliberately left to
the operator, since `stop.sh`/`start.sh` also take OpenCode down and bring it back up, and running
`start.sh` from inside the session it serves would start a second instance inside the first.

**Closed 2026-11-22:** the operator relaunched the stack, and the live supervisor was read back rather
than assumed:

```
--max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache
--default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64
ready true · ctx 262144 · queued 0 · waiting 0 · lifetime suspensions 0
```

Both 2026-11-19 stack moves are now live together — the restored 32,768 thinking budget and
`--queue-size 64` — and the fresh instance reset the lifetime counters to 0, which is instance state,
not an improvement: any later wave in this directory must read counters as window deltas, as it always
has. A side observation from the verification probe, kept because it will mislead the next reader:
a `max_tokens=16` request came back with `content=null`, because all 16 completion tokens went to
`reasoning_tokens`. Same prompt at 200 tokens answered correctly with 23 reasoning tokens.

**The fixes from §4 are now applied** (after the processes were stopped, never mid-execution), with
`selftest_wave_hardening.sh` covering them — 8/8 pass, `shellcheck -S warning` clean on all three files:

| fix | where |
|---|---|
| `tau2 run` gets `< /dev/null`, so an unexpected prompt fails fast instead of parking the chain | `run_wave.sh` |
| pre-flight on `--save-to`: existing dir is moved to `<save>.pre-<UTC>` and the run starts clean, or `TAU2_RESUME=1` chooses `--auto-resume` deliberately — never a silent blend | `run_wave.sh` |
| stall watchdog on **engine progress** (`prefill_batches + decode_batches`, 20 s polls, `TAU2_STALL_SECONDS` default 420): kills a wave that serves nothing and logs `STALL KILL`, so the chain reaches its pin-restore step | `run_wave.sh` |
| the watchdog never kills on an unreachable `/status` (reads `-1`, resets) | `run_wave.sh` |
| chain's stdout goes to `wave.stdout.log`, ending the two-writers-one-file doubling and the cross-run appending of `wave.log` | `run_thinkbudget_chain.sh` |
| a completed arm is skipped with a logged timestamp unless `TB_RERUN_ARM=1` — and the guard never applies to the 32768 pin-restore arm | `run_thinkbudget_chain.sh` |

Two bugs surfaced while writing the test, both in the test rather than the runner: one `local` line
referencing its own earlier assignment (expansions resolve before the assignment lands, so `$save` was
unbound), and a `local` variable read from outside its function. Both fixed; recorded here because a
green test that tests nothing is the failure mode this whole suite exists to avoid.

