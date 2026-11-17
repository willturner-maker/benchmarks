# PLAN — 2026-11-17h baseline wave (fixed fixtures, daily config)

Goal: re-establish a clean measured ceiling after the 17g wave's operator-side flaws voided
three cells per arm. This is NOT a new A/B — effort A/B is closed; the wave runs the **daily
config only** (effort medium since the 17g operator flip, no proxy), so its result is the
baseline every future optimization is measured against. Ceiling becomes **21/21** (T8 and the
F2 grade dimension become measurable again); 18/18 stops being the working denominator.

## The three fixes (all trace to 17g VALIDITY.md)

1. **Single scratch project** — `_mcp_AGBench-2026-11-17h`, one project for the whole wave.
   The 17g two-arm design armed one project per arm; Resolve's current project is host-global
   and concurrent sessions raced on it (flaws 1+2: 8 misplaced NEW timelines, 2 mutated
   wrong-arm timelines). With one project the whole class is gone; trial copies keep
   trial-suffixed names (`_f1s1..3`, `_f2r1..3`, per-brief T naming), which already exist.
2. **F2 arming order fixed + verified** — CDLs land on the clean 3-item timeline BEFORE the
   transition exists; the builder now runs an ARM CHECK (exactly one 24-f transition, grade
   tools on items 1 and 2) and **aborts** rather than arming a wrong pre-state (flaw 4).
   The F2 grade dimension returns to scoring; spec reverts from `tracked: [transition, link]`.
3. **T8 in-trial snapshot grading** — the comp-persistence mechanism is proven (attached comps
   don't survive project close/load churn), so the grader may not be the last reader: after
   each T8r* session ends, the driver takes an immediate stdio-MCP read-back of the timeline's
   comp list and grades THAT. The post-wave read-back is still recorded — it is now
   product-behavior data (measuring Resolve, not the agent) and is disclosed alongside, never
   deciding the cell.

## Wave shape

- 7 briefs (T1 T2 T3 T7 T8 F1 F2) × 3 trials = **21 sealed sessions**, single arm (daily).
- No proxies; OpenCode sends no `reasoning_effort` → engine's daily medium applies (banner
  proof `effort absent → medium` captured, same as the start.sh flip record).
- Engine: Splash 1.7.0, never restarted mid-wave; warmth gate recorded as in the 1.7.0 waves.
- Seal: the v2.3.0 channel (OPENCODE_CONFIG + permissions + policies), global AGENTS.md hidden,
  allowed-MCP-trio census re-run with the 17g `seal_audit_reclass` semantics (errored
  mangled-name attempts ≠ breaches).
- Grading: read-backs only vs sealed prestate + ground truth, `grader_selftest.py` green
  immediately before grading; T1 honesty from operator-extracted claim maps (fail-closed).

## Pre-wave checklist (all before any session is armed)

- [x] Builder run (UNRECORDED probe first, 2026-11-17): ARM CHECK fired its first catch —
      against ITSELF: v1 of the check probed pre-shift indices (1,2) and a probe key that
      does not exist, and ABORTed an arming that verification then proved CORRECT
      (template + all 3 copies: exactly one 24-f transition row, graded clips at post-shift
      indices 2 and 3 — the docstring's own "items 2 and 3"). Check fixed; state kept.
      Lesson: an arming check must encode the POST-operation layout, not the intent-time one.
- [x] prestate + ground truth sealed for `…17h` — exactly the 10 armed timelines. Required
      cleanup the probe exposed: MCP auto-versioning left six `<tl>_archived_vNN` copies in
      the project (17g's sealed gt never had them); deleted, and the gt stage now excludes
      `_archived_` names and reports them at build time instead of letting an agent meet them.
- [x] grader_selftest green: 58/58 (2026-11-17, current count).
- [x] T8 snapshot hook present in the driver and unit-checked against a known comp (arm a
      throwaway comp, snapshot it, delete it — the hook must see exactly it). DONE 2026-11-17.
- [ ] harness.json captured (opencode build, engine banner line, MCP versions).

## Known residual risks (disclosed in advance, not discovered after)

- Single project removes the project race; the CURRENT-TIMELINE host state is still global.
  Briefs' pin rules target named timelines and most MCP actions take `timeline_name`, but the
  driver's per-trial placement audit from 17g is kept: any NEW timeline found under the wrong
  trial suffix is disclosed the same way.
- Tenancy: like the published 17g wave this runs beside an operator session unless a clean
  window is chosen — the choice is recorded, not assumed.
- T8 measures agent behavior at session end; post-hoc Resolve behavior (comp eviction under
  churn) is recorded as a product finding every time it appears.

Status: **all pre-wave checklist items done (2026-11-17). Wave not yet run** — one decision
open: tenancy (alongside an operator session, disclosed, as the published 17g was; or
tenancy-free detached like the 11-13/16 co-runs) and the start. Recommended first move at
wave time: one `--smoke T1r1` session to a scratch `--out` to prove the driver end-to-end
(snapshot writes, seal audit, summary lines) before arming the 21.
