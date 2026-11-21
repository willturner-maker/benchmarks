# Drafter-off arm — attempt 1 failure postmortem (2026-11-21)

## Timeline (UTC)

| time | event |
|---|---|
| 14:54:43 | chain started phase 1 (retail-40 ENV closure) on engine `627c2f53` |
| 16:19:43 | phase 1 exit=0; phase 2 killed the engine to launch the farm |
| 16:19:45 | farm launch **rejected**: `...IQ3_S-nodraft is not a model directory Splash prepared` |
| 16:19–16:25 | ~5 min with **no engine on port 8000** (the operator started one by hand in this window) |
| 16:24:52 | chain's pin-restore relaunch came up ready: instance `08d662f6ada5b1b1ae93fff5` |
| 16:25:05 | drafter probe on the restored pin: delta 288 > 0 → "pin restored, drafter ON again" |
| 16:25:05 | phase 3 (pass^3 replay) launched on `08d662f6` — **still running as of this note** |

`drafted_tokens delta over probe: 49` logged before "DRAFTER STILL ON" was measured on the
**partially started** farm attempt (the supervisor accepted HTTP before the model load was
rejected); it is not evidence about the drafter. The arm was correctly declared invalid and
not measured.

## Root cause: farm directory layout

`server.server` positional model path goes through `install/assembly.py` `hold()`: the path must
resolve to a directory whose **parent is named `.resolved`** (an assembly). The attempt-1 farm
was a plain directory at `models/ISTA-DASLab/<id>-nodraft` — rejected.

Second constraint (fixed up front, would have bitten later): `assembly.collect_garbage()`
removes `.resolved` assemblies that "no selection links and no server holds". A farm with no
named link would be garbage-collected by the next normal `splash serve`.

## Fix (committed with this note)

`drafter_farm.py` (rewritten) builds:
- assembly: `models/.resolved/nodraft-f073087d1dff7edaf96fe2f5ee568630/` — model.json with all
  `draft/*` file entries and the `draft` source dropped (8 files, sources `['target']`, verified
  0 draft entries), config/target/tokenizer/vision symlinked to the live assembly (target weights
  byte-identical by construction; the live assembly is never touched);
- selection link: `models/ISTA-DASLab/<id>-nodraft -> that assembly` (also keeps GC off it).

Built and verified after the failure; the stale attempt-1 directory was removed.

## Second bug found while re-running (not yet triggered)

The chain's `kill_engine`/`pkill` matched **any** supervisor — during the 16:19–16:25 gap it
would have (and the restore's pkill sequence did race with) whatever the operator started by
hand. The rerun script `run_drafter_arm.sh` gates every kill on the `/status` **instance pid**
(verified equal to the launched supervisor's pid): it only kills instances it launched itself,
except one logged deliberate kill of the current engine at arm start.

## Status of the other phases

- Phase 1 (retail-40 ENV): completed 16:19:43Z, exit=0 — record pending summarizing.
- Phase 3 (pass^3 replay): running on `08d662f6` since 16:25:05Z.
- Drafter-off arm: **to be rerun standalone** via `run_drafter_arm.sh` (detached, sleep-gated)
  only after phase 3 lands, so it never restarts the engine mid-measurement.
