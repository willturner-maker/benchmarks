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

Moved out of `willturner-maker/splash-dashboard` on 2026-11-06 (the dashboard repo's git
history still holds the pre-move commits).
