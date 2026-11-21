# Splash engine restart, 2026-11-21 — closed epoch archived, restart succeeded only after operator intervention

**Why.** The τ² same-seed repeat is an engine-determinism experiment, and the restart decision (open since
the drafter-off A/B was proposed) was taken: give the pair a fresh process epoch with lifetime counters at
zero. The pre-restart counters here are the **closing numbers of the closed epoch** — every record published
before this moment quotes that epoch's counter windows, and everything after quotes windows from this restart.

## Timeline (UTC)

| when | what |
|---|---|
| epoch start 2026-11-19T18:14:09Z | supervisor instance `a8bc9e5800db4d719af9a478` (pid 54916) — the instance that served τ² 19a, the width control, depth fine, tenancy A/B, pass^3 and the xhigh effort wave |
| 05:03:33Z | `restart_then_sameseed.sh` archived `status_final_pre_restart.json` and killed 54916 (argv gate had passed: running argv byte-identical to the pin) |
| 05:03:34Z | scripted relaunch **died instantly**: `ModuleNotFoundError: No module named 'server'` |
| 05:03–05:20Z | **engine down ~17 min**; the driver's ready-poll (6 min budget) exhausted and exited 1; no waves started |
| ~05:20:26Z | **operator relaunched manually** — new instance `627c2f53ab5e256c5e7898f9` (pid 67940), argv verified **byte-identical** to the pin by diff |

## Root cause of the failed relaunch (fixed the same evening)

`python -u -P -m server.server` resolves the `server` package (which lives under
`…/splash/1.7.0/libexec/server`) via **PYTHONPATH or CWD**. Every historical launch — original *and* the
manual one — inherited that path from an interactive shell environment; neither supervisor's CWD was
libexec. The driver relaunches from `$HOME`, where the module is unreachable, and `-P` does **not** strip
PYTHONPATH (that is `-I`), which is why inherited-env launches worked at all. Driver fix, committed with
this record: relaunch `cd`s to libexec **and** exports `PYTHONPATH=$LIBEXEC` explicitly; ready-poll raised
to 15 min with an empty-body guard (a down engine returns nothing — the old poll spewed 1368 traceback
lines and misread valid-empty as garbage); an engine down for >17 min also warns the harness's own session.

## Closing counters of the closed epoch (`status_final_pre_restart.json`)

`kv_spill.spill_moves` **3,155,422** · `kv_spill.requests.spill` 1,727 · `disk.kv_demotions` **26,400** ·
`disk.kv_demotions_refused` 4,350 · `disk.kv_restores` 129,280 · `cache.resource_suspensions` **8** ·
`admission.suspended` 0 · weights.restores 4. Window: 2026-11-19T18:14:09Z → 2026-11-21T05:03:33Z.

## Post-restart state

New epoch pins verified identical: argv diff clean, window 262,144 tok, KV 32-tok pages, model
`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, `--queue-size=64`,
`--thinking-token-budget=32768`, `--default-reasoning-effort=medium`, `--persistent-cache` (so the **disk**
KV cache survived the restart — the new epoch is memory-cold, disk-warm; `pages_cache` was ~4,130 right
after start). Snapshot: `status_post_restart_manual.json` (taken minutes after start, after the operator's
own session had served a few requests — not a perfectly idle first read, disclosed).

**Known fragility, unfixed by choice:** the manual supervisor's parent is an `opencode` process (pid chain
`-zsh → opencode → splash supervisor`) — exactly how the previous epoch was parented. Quitting that
terminal/opencode risks taking the engine down mid-wave. Fixing it would mean *another* restart (killing
this session's own serving engine), so it waits; the fixed driver uses `nohup … & disown` and is safe for
the next restart.

## Consequences for later records

- Lifetime counters are **zero-based from 2026-11-21T05:20:26Z**; waves after this point must quote deltas
  against post-restart snapshots, and cross-epoch comparisons use per-wave windows, never raw counters.
- The same-seed pair (`bench/tau2-bench/results/2026-11-21-sameseed-{a,b}/`) is the first pair on the new
  epoch, and wave A is the closest thing to a cold-memory-cache wave on this engine since the epoch began.

Artifacts: `restart.log`, `launch_argv.raw.txt`, `serve_stdout.log`, `status_final_pre_restart.json`,
`status_post_restart_manual.json` (home paths scrubbed to `~` on commit). Tooling:
`bench/splash-concurrency/restart_then_sameseed.sh`.
