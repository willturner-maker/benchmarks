# Thinking-token-budget A/B (2026-11-22) — on our traffic the budget is a dead knob; pass^1 spread is noise

Engine-level experiment: three complete 238×1 judge-free medium waves, each on its own identity-gated
engine relaunch with `--thinking-token-budget` = **8192 / 65536 / 32768 (the suite pin, run last as the
same-session control)**. Everything else is the published configuration (τ² v1.0.1 @ fc0055d, seed 300,
conc 3, effort medium, drafter ON, `1.7.0` Cellar paths — all three arms ran on Splash 1.7.0, instances
launched and argv-verified by `../run_thinkbudget_chain.sh`, logged in `../2026-11-22-thinkbudget-chain/chain.log`).

## Scores (pass^1, n=238 each; single trial — 95 % CI ≈ ±4.4 pts per arm)

| arm | airline | retail | telecom | aggregate |
|---|---|---|---|---|
| budget 8192 | 0.900 | 0.811 | 0.912 | 0.8782 |
| budget 65536 | 0.860 | 0.824 | 0.904 | 0.8697 |
| budget 32768 (pin/control) | 0.860 | 0.784 | 0.868 | 0.8403 |

All three land inside or near the published medium wave band (0.8445–0.8824); the control arm sits at the
band's bottom edge, the 8192 arm near its top. **The arm ordering is not established and should not be
read as a budget effect** — with n=1 wave per arm the CIs overlap heavily, and the ordering isn't even
monotone in budget (8192 > 65536 > 32768).

## Request-level readout (the primary measure, and it is decisive)

| arm | prefill Δ | decode Δ | drafted Δ | accepted Δ | drafter accept | wave wall |
|---|---|---|---|---|---|---|
| 8192 | 1,442,053 | 1,044,603 | 1,175,639 | 747,113 | 63.5 % | 74 min |
| 65536 | 1,376,793 | 1,063,903 | 1,188,478 | 763,796 | 64.3 % | 73 min |
| 32768 | 1,363,375 | 1,043,398 | 1,170,159 | 746,451 | 63.8 % | 73 min |

The three arms are **indistinguishable at token level** (spread < 6 % on prefill, < 2 % on decode,
acceptance flat). Mechanism: at `reasoning_effort: medium` the engine's thinking rarely reaches even the
8192-token cap, so none of the budgets binds on τ² traffic — the knob changes nothing that reaches the
wire. (τ² transcripts do not store `reasoning_content`, but unchanged decode totals across arms already
rule out any material thinking-length cut at 8192.)

**Verdict published:** `--thinking-token-budget` is a no-op for this stack's medium-effort agent traffic —
keep the pin at 32768; do not spend wave time on budget arms unless an effort class is raised that
actually produces >8k-token thinking. To establish any pass^1 difference one would need 238×2 per arm
(~2× wave time each); the request-level fingerprint says that experiment would very likely find nothing.

## Chain honesty log (all in chain.log)

- **Run 0** aborted on a phantom argv check: the engine child (`serve-native`) carries NO option flags
  (259-char argv) and `/status` does not expose the budget — verification must target the supervisor
  argv (fixed; both run-0 relaunches were actually healthy).
- **Run 1** completed the 8192 arm (17:37→18:51Z, exit=0), then its own engine kill tripped
  `wait_idle`'s dead-port trap (closed port ≠ busy), aborting before pin restore — the operator
  restarted the pinned engine manually (argv-confirmed). Fixed: dead port = idle.
- **Run 2** completed all remaining arms (65536 19:41→20:54Z; 32768 control 20:55→22:08Z),
  "chain complete: pin restored".
- **Run 3** (22:42Z, duplicate re-invocation during the operator's 1.7.1 upgrade) launched a second
  65536 engine, contaminated nothing: its airline leg exit=1 with zero writes (first-wave results.json
  mtime + counts 50/74/114 verified), retail leg died with the process tree, no processes remain.

## Scope notes

All arms ran on 1.7.0 — this closed the 1.7.0-era experiment queue before the 1.7.1 epoch the operator
opened at 22:3xZ (instance 38c7a88c, pin argv confirmed on 1.7.1). Tenancy: co-tenant agent traffic
(operator's sessions) shared the engine during all three waves — light, no spill/suspension flags in
the samplers; wave counters are lifetime-per-instance, and each arm ran on its own fresh instance so
the Δ columns are clean.

Files: per-arm dirs `results/2026-11-22-thinkbudget-{8192,65536,32768}/` (wave.log, per-domain logs,
status edges, engine samples, serve.log); `results/2026-11-22-thinkbudget-chain/` (chain.log,
run-0 log kept); runner `bench/tau2-bench/run_thinkbudget_chain.sh`.
