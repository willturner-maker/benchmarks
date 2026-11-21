# Drafter-off arm — final record: unsupported on Splash 1.7.0 (closed as a finding, not a measurement)

Four launch attempts, three fixed bugs, one dead end that IS the answer:
**the DFlash2 drafter cannot be disabled in Splash 1.7.0** — it is mandatory in the pinned
stack's model-assembly architecture. No A/B row is published because no honest way to run
"target without drafter" exists on this release without patching the engine binary (out of
scope: the whole point of these benchmarks is an unmodified pinned instrument).

## Attempt ladder (all UTC, engine restored after every failure)

| attempt | failure | fix |
|---|---|---|
| 1 (chain phase 2, 16:19Z) | farm was a plain dir → `hold()`: "not a model directory Splash prepared" | assembly under `.resolved/` + selection link (`drafter_farm.py` rewrite); ~5-min engine gap, operator restarted by hand |
| 2 (20:39Z) | builder crashed on its OWN selection symlink (`is_dir()` follows links, `rmtree` refuses); arm had already killed the engine | build+verify farm BEFORE any kill; symlink-aware cleanup (`c0edb6f`) |
| 3 (20:57Z) | serve rejected: "not prepared as a model of a family this release serves" — builder had written only `files`+`sources`, dropping `family/model/metadata/version/target_format/vision_format` | copy the whole manifest, strip only draft file entries (`e34d2f7`) |
| 4 (21:15Z) | engine binary itself: `MODEL_DIRECTORY must hold the model's target/ and draft/ directories` — the farm had no `draft/` dir | none possible; see below |

Between 3 and 4 a static pre-gate was added (call Splash's own `assembly.hold`/`family` before
any restart): it surfaced attempt 3's second layer — `install/assembly.py:_well_formed` requires
`sources == {target, draft}` — the record must *name* the draft repo even when no draft files are
linked (`63b2ef6`). Attempt 4 then passed every Python-layer gate and died in the native engine.

## Why there is no supported off-switch (architecture, from the pinned 1.7.0 files)

- `splash serve-native` (engine): hard requirement that MODEL_DIRECTORY contain BOTH `target/`
  and `draft/` — its own usage text shows no draft-related option; `strings` on the binary shows
  no `--*draft*` flag.
- `server/server.py::_native_command` passes only `model_root` + serve options — no draft knob.
- `install/assembly.py::_well_formed` refuses any record whose sources are not exactly
  `{target, draft}` — an assembly record for a draft-less model is invalid by construction.
- `install/local.py::_draft`: preparing a local model resolves the family's draft repo or
  refuses — the install pipeline can't build a draft-less assembly either.
- `--verify-rows {auto,all}` changes verification strictness, not speculation on/off.
- A dummy/worst-case draft would measure *a pathological drafter*, not *no drafter* — a fake arm,
  not run.

Consequence for planning: any future drafter-off comparison needs an upstream option; until then
the drafter's contribution stays observable only through telemetry (acceptance rate ~0.61–0.63
across today's windows: e.g. replay Δdrafted 3,649,921 → Δaccepted 2,327,412), not by ablation.

## Windows burned (disclosed)

Two aborted engine gaps from the arm: 16:19:43→16:24:52Z (attempt 1) and 20:39:34→20:54:43Z
(attempt 2 — kill happened before the builder crashed; fix landed same commit). Attempt 4's
restart cycle (21:15:41→21:30:49Z) was a legitimate launch attempt of a farm that passed every
supported gate; pin restored 21:30:50Z (`19a70e8c`, drafter re-probed ON, Δdrafted 62 > 0).
No τ² wave overlapped any gap; every wave this evening ran on verified pinned-argv instances.

## Farm artifacts

`drafter_farm.py` is kept as documentation of the assembly layout (and was used to build the
farm that got furthest); the farm assembly and its selection link were removed after the finding,
leaving the live model tree exactly as installed. `run_drafter_arm.sh` stays as the identity-gated
restart template — its kill-gating and build-before-kill ordering are reusable for any future
flag-change A/B (e.g. `--thinking-token-budget`), which remain supported restart-class knobs.
