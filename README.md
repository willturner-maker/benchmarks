# Benchmarks

Version-to-version benchmark baselines for the local AI/editing stack, kept separate from
the dashboards they instrument. Each suite is a fixed-condition measurement meant to be
re-run and diffed after an upgrade — grading is always from independent read-backs, never
from the model's own claims.

**Host (fixed for all baselines):** Apple M5 Ultra, 64-core GPU, 96 GiB unified memory,
macOS 27.2.0.

## Suites

| Suite | Doc | Scripts / raw data | Baseline headline |
|---|---|---|---|
| Splash engine + Qwen | [`docs/splash-engine-benchmark-results.md`](docs/splash-engine-benchmark-results.md) | `bench/2026-11-06/` | Splash 1.6.0 warm: TTFT 201 ms / 380 ms cold; width ladder plateaus 372–383 tok/s (2.5–2.6× w1) from width 4 through 32, no collapse; KV-pressure probe never suspends, even at 4.4× the KV budget; agentic suite 11/12 verified, 12/12 honest |
| DaVinci Resolve MCP | [`docs/resolve-agentic-benchmark-results.md`](docs/resolve-agentic-benchmark-results.md) | **[`bench/resolve-agentic/`](bench/resolve-agentic/)** — briefs, runbook, and `check_media.py` so you can run it on **your own footage** | 21.2.0.6 + MCP 4.19.0: warm render 1296 ms, cold 3090 ms; 18/18 verified, 18/18 honest across n=3 |
| Concurrency spec (draft, 2026-09) | [`docs/concurrency-scaling-test.md`](docs/concurrency-scaling-test.md) | — | the never-run design the Splash ladder later implemented |

## Leaderboard & reports

Standings across versions live in [`docs/leaderboard.md`](docs/leaderboard.md)
(machine-readable: [`leaderboard/results.json`](leaderboard/results.json)) — including the
rules about which rows are comparable at all. Your own run comes in through the
[**Leaderboard row issue form**](https://github.com/willturner-maker/benchmarks/issues/new?labels=leaderboard&template=leaderboard-row.yml),
which asks for media class, tenant conditions, exact builds and a read-back attestation
before a row can be ranked. The full scorecards are self-contained HTML
(no external assets, no build step). GitHub's file view shows their source; **view them
rendered** through GitHub Pages:

| Report | What's in it | Rendered |
|---|---|---|
| [Resolve MCP, 21.1.2.10](https://willturner-maker.github.io/benchmarks/reports/2026-11-03-resolve-21-1-2.html) | perf cold/warm render probes, agentic n=3 scorecard, concurrency sweep | `reports/2026-11-03-resolve-21-1-2.html` |
| [Resolve MCP, 21.2.0.6](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-resolve-21-2.html) | the 21.2 + MCP 4.19.0 run: render probes, op medians, n=3 agentic | `reports/2026-11-06-resolve-21-2.html` |
| [Splash engine, 1.6.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-splash-engine.html) | engine probe, width-ladder plateau, KV-pressure chase for the first suspension | `reports/2026-11-06-splash-engine.html` |

If Pages is ever disabled, the same files are readable through any raw viewer — e.g.
`https://raw.githubusercontent.com/willturner-maker/benchmarks/main/reports/<name>.html`
served by a browser, or just `open reports/<name>.html` after a clone.

## Layout convention

- `docs/` — the results write-ups; each carries its own re-run recipe.
- `bench/<suite-date>/` — runnable scripts + raw JSONL for that run, so future reruns
  compare against committed raw data, not summaries. Splash reruns go through the single
  entry point `bench/2026-11-06/ladder_kv.py` (width ladder + KV-pressure probe in one run,
  one combined summary).

- `bench/resolve-agentic/` — the Resolve suite is **not** tied to my media: `MEDIA.md` is
  the media contract (what kind of clip you need, and which published numbers survive a
  media swap), `check_media.py` validates a candidate clip and derives every frame number
  the briefs use, `tasks.md` + `RUNBOOK.md` are the six briefs and the procedure.

- `tools/precommit-scan.sh` — pre-commit guard: refuses staged content containing local
  paths, camera/reel filenames, credential shapes, emails, or repo-local **deny terms**
  (client/project/event names kept in `.git/info/precommit-terms`, which is never
  committed). `bash tools/precommit-scan.sh --install` to wire it up, `--all` to audit
  the whole tree. This repo went public carrying a camera filename and a home path, so
  the guard exists; both are scrubbed from history now.

Moved out of `willturner-maker/splash-dashboard` on 2026-11-06 (the dashboard repo's git
history still holds the pre-move commits).
