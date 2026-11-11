# Benchmarks

Version-to-version benchmark baselines for a fully local DaVinci Resolve Studio + AI
workstation (Splash inference engine + Resolve MCP server + supporting vision tools),
kept separate from the dashboards they instrument. Each suite is a fixed-condition
measurement meant to be re-run and diffed after an upgrade. Grading is always from
independent read-backs (ffprobe, timeline geometry, engine status, operation logs),
never from a model's own claims.

**Reference host for all published baselines:** Apple M5 Ultra, 64-core GPU, 96 GiB
unified memory, macOS 27.2.0.

## Start here

| What you want | Go to |
|---|---|
| High-level explanation of the stack and why these suites exist | [`docs/OVERVIEW.md`](docs/OVERVIEW.md) |
| Current standings, comparability rules, and score tables | [`docs/leaderboard.md`](docs/leaderboard.md) |
| How to run a suite on your own machine / submit a row | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Self-contained HTML scorecards (GitHub Pages) | [index.html](https://willturner-maker.github.io/benchmarks/) or the `reports/` directory |
| Latest combined results | [2026-11-11 reruns](https://willturner-maker.github.io/benchmarks/reports/2026-11-11-reruns.html) |

## Suites

| Suite | Doc | Scripts / raw data | Latest standing |
|---|---|---|---|
| DaVinci Resolve MCP | [`docs/resolve-agentic-benchmark-results.md`](docs/resolve-agentic-benchmark-results.md) | **[`bench/resolve-agentic/`](bench/resolve-agentic/)** — briefs, runbook, and `check_media.py` so you can run it on **your own footage** | 21.2.0.6 + MCP 5.2.2 (wave `2026-11-11h`): **18/18 verified, 18/18 honest — sixth consecutive clean wave, 108/108 aggregate**; walls down 23–38 % vs the 5.2.0 wave with zero cross-agent write incidents; warm render 1205 ms (ran concurrent — ranked with note, see leaderboard rule 2) |
| Splash engine + Qwen | [`docs/splash-engine-benchmark-results.md`](docs/splash-engine-benchmark-results.md) | `bench/splash-concurrency/` — single entry point `ladder_kv.py` (width ladder + KV-pressure probe in one run) | Splash 1.6.1 (2026-11-11): plateau **510–525 tok/s, +39 %** over 1.6.0, aggregate peak moves width 4→12, KV probe still never suspends at 4.4× budget (demote path partially re-engaged at w10 — instance-dependent); agentic suite 12/12 + 12/12 |
| Visual venv (OpenCV) | [`bench/visual-venv/README.md`](bench/visual-venv/README.md) | `bench/visual-venv/` — bench script, cold-run probe, run1/run2 JSON (**fixtures withheld**: real face frames; hashes in the JSONs) | opencv-python 5.0.0.93 baseline + same-build rerun: every deterministic value bit-identical, uniform ~11 % timing drift band (×1.15 ceiling for the future 5.1.x diff); watched for 5.1.x wheels by a launchd agent |
| Concurrency spec (draft, 2026-09) | [`docs/concurrency-scaling-test.md`](docs/concurrency-scaling-test.md) | — | the never-run design the Splash ladder later implemented |

## Leaderboard & reports

Standings across versions live in [`docs/leaderboard.md`](docs/leaderboard.md)
(machine-readable: [`leaderboard/results.json`](leaderboard/results.json)) — including the
comparability rules, the withdrawn-row history, the **width-ladder score table**, the
**visual-venv table**, and a section describing **what's in each report**. Your own run
comes in through the
[**Leaderboard row issue form**](https://github.com/willturner-maker/benchmarks/issues/new?labels=leaderboard&template=leaderboard-row.yml),
which asks for media class, tenant conditions, exact builds and a read-back attestation
before a row can be ranked.

The scorecards themselves are self-contained HTML (no external assets, no build step) and
render on Pages:

- [Benchmark reruns, all four suites — 2026-11-11](https://willturner-maker.github.io/benchmarks/reports/2026-11-11-reruns.html)
- [Resolve MCP · MCP 5.2.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-10g-resolve-21-2-mcp-520.html)
- [Splash engine 1.6.0 rerun](https://willturner-maker.github.io/benchmarks/reports/2026-11-10s-splash-160-rerun.html)
- [Resolve MCP · MCP 5.1.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-10f-resolve-21-2-mcp-510.html)
- [Resolve MCP · MCP 4.19.3](https://willturner-maker.github.io/benchmarks/reports/2026-11-06e-resolve-21-2-mcp-4193.html)
- [Splash engine 1.6.0 baseline](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-splash-engine.html)
- [Resolve MCP · MCP 4.19.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-resolve-21-2.html)
- [Resolve MCP 21.1.2.10 · MCP 4.18.5](https://willturner-maker.github.io/benchmarks/reports/2026-11-03-resolve-21-1-2.html)

If Pages is ever disabled, the same files are readable through any raw viewer — e.g.
`https://raw.githubusercontent.com/willturner-maker/benchmarks/main/reports/<name>.html`
served by a browser, or just `open reports/<name>.html` after a clone.

## Layout convention

- `docs/` — the results write-ups; each carries its own re-run recipe. Start with
  [`docs/OVERVIEW.md`](docs/OVERVIEW.md) if you are new.
- `bench/<suite>/` — runnable scripts + raw JSONL for that suite, named **by what the
  suite measures**, not by its first run date: `splash-concurrency`, `resolve-agentic`,
  `visual-venv`. Individual waves get dated labels inside (`results/<wave>/`), so future
  reruns compare against committed raw data, not summaries.
- `bench/resolve-agentic/` — the Resolve suite is **not** tied to my media: `MEDIA.md` is
  the media contract (what kind of clip you need, and which published numbers survive a
  media swap), `check_media.py` validates a candidate clip and derives every frame number
  the briefs use, `tasks.md` + `RUNBOOK.md` are the six briefs and the procedure.
- `reports/` — the rendered scorecards, one self-contained HTML per wave, front-doored by
  the Pages `index.html`.
- `tools/precommit-scan.sh` — pre-commit guard: refuses staged content containing local
  paths, camera/reel filenames, credential shapes, emails, or repo-local **deny terms**
  (client/project/event names kept in `.git/info/precommit-terms`, which is never
  committed). `bash tools/precommit-scan.sh --install` to wire it up, `--all` to audit
  the whole tree. This repo went public carrying a camera filename and a home path, so
  the guard exists; both are scrubbed from history now.

Media-bearing assets (bench fixtures with identifiable faces, concert frames) are never
committed in this repo, anywhere — only their SHA-256s and regeneration recipes.

Moved out of `willturner-maker/splash-dashboard` on 2026-11-06 (the dashboard repo's git
history still holds the pre-move commits).

See also [`CONTRIBUTING.md`](CONTRIBUTING.md).
