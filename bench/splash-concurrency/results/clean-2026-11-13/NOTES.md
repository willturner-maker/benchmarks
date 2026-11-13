# Clean-window run — 2026-11-13 (standalone driver, engine single-tenant)

Driver: `bench/clean-run-2026-11-13/run_clean.py`, launched from a terminal with `nohup`;
the operator Claude session (itself served by this engine) made **zero turns** during timed
stages — the first engine-suite run with true single-tenancy. Stage walls: engine_probe 286 s,
ladder_kv 484 s, vis_bench 18 s, agentic 232 s; every stage rc=0.

- `header.json` — engine cache state at start (hit-rate 0.996), `splash --version` 1.6.1,
  cv2 5.0.0 (wheel 5.0.0.93), repo HEAD 31715d9.
- `engine_probe.jsonl` — decode w1 159.3/173.6/143.3 tok/s; TTFT 229 cold / 159 warm.
- `ladder_kv.jsonl` + `ladder_kv.stdout.txt` — ladder medians (summary in the SUMMARY line:
  w1 209.5, peak w12 475.2, no collapse, stop rule never fired) and KV pressure
  (611,244 tok = 4.66× the 131,072 budget; suspensions 0, spill +0, demote +0).
- `run3.json` — visual-venv baseline run3 (same 5.0.0.93 build; bit-identical determinism; see
  the leaderboard Visual venv section). The cold stage was dropped (cold_run fixture moved; run2
  had no cold section either).
- `agentic/` — driver2 n=3 outputs; `sessions/summary.jsonl` is the per-trial record,
  `S3/out.json` is the agent-written file that passes the exact-match check.

Harness note: the runner's intended warm-up completion 404'd (Splash does not serve
`/v1/chat/completions`) — harmless, the probe's first passes warmed the engine (see the decode
trend). Redaction: the two stage stdout files were scrubbed of repo-absolute `/Users/...`
prefixes (logs are otherwise verbatim). The Resolve-suite wave that followed in the same window
is recorded separately: `bench/resolve-agentic/results-2026-11-13i.json`.
