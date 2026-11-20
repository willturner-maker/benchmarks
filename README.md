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
| Machine-readable results schema | [`docs/schema.md`](docs/schema.md) |
| Community runs (class B / other hosts) | [`docs/leaderboard.md#community-runs--your-numbers`](docs/leaderboard.md#community-runs--your-numbers) |
| Self-contained HTML scorecards (GitHub Pages) | [index.html](https://willturner-maker.github.io/benchmarks/) or the `reports/` directory |
| Newest wave | [Splash `--queue-size 64` — the KV ceiling was a request count, 2026-11-19](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-splash-queue-size.html) |
| Newest suite (debut) | [τ²-bench — 2026-11-19](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-tau2-bench.html) · environment-graded agent tasks, reproducible on any OpenAI-compatible endpoint, no containers · (also new: [the width control that refuted its own first mechanism claim](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-tau2-width-control.html), and the [Tool-loop gate](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-tool-loop-gate.html), same day) |
| Latest combined (multi-suite) results | [All-suites day, 2026-11-18](https://willturner-maker.github.io/benchmarks/reports/2026-11-18-all-suites-day.html) |

## Suites

| Suite | Doc | Scripts / raw data | Latest standing |
|---|---|---|---|
| DaVinci Resolve MCP | [`docs/resolve-agentic-benchmark-results.md`](docs/resolve-agentic-benchmark-results.md) | **[`bench/resolve-agentic/`](bench/resolve-agentic/)** — briefs, runbook, `wave_driver.py`, and `check_media.py` so you can run it on **your own footage** | Newest wave **`2026-11-18m`** on Resolve **21.2.0.6 + MCP 5.3.4** (footnote ¹⁸): single-tenant warm render **1174 ms — best on host** (probe timeline 1651 ms, 24 operations on the 4-item geometry), and the F3 frontier cell at **6/6 geometry with 0 preserved-native / 6 repaired** (the repair path is what makes it 6/6, not the model getting it right unaided). The **scored class-A ladder** record is still `2026-11-13i` (MCP 5.2.7): **18/18 verified, 18/18 honest — fifth consecutive clean wave, 90/90 aggregate**, single-tenant warm 1192 ms at the time; the frontier ladder's ceiling row is `17h → 17h2` **20/21 → 21/21**. Earlier rows and every multi-factor caveat stay in the leaderboard table |
| Splash engine + Qwen | [`docs/splash-engine-benchmark-results.md`](docs/splash-engine-benchmark-results.md) | `bench/splash-concurrency/` — sealed entry point `ladder_kv.py` (width ladder + KV-pressure probe in one run, widths ≤32); `kv_bracket_2026-11-19b.py` for work past the concurrency cap (queue-size guard, refusals-as-data, fresh seed namespace, `cache_served` validation); `run_clean_detached.sh` for waves that must prove their window was single-tenant; full clean-window driver at `bench/clean-run-2026-11-13/` | Splash **1.7.0** on the **`--queue-size 64`** stack. Reference wave is now **`2026-11-19c-clean`** — detached, operator idle, tenancy proven by request attribution: ladder w1 **308.75 tok/s** (rounds 305.7 / 311.8, spread 1.020 = tightest pair on record), plateau w12–32 mean **695.6**, stop rule never fired, admission ceiling 12. **KV never trips by summed volume: 17.04× the 155,648-token budget, 11.77 M tokens of fresh prefill, zero refusals / suspensions / spill / demotions**, and the reason is now visible — `pages_active` pins at **0.39× budget** while `queued` climbs 11→47, so **extra width becomes queue depth, not KV residency**, and the wall is the flat **~3,470–3,500 tok/s** prefill rate set by `maximum_batch_width = 4`. That retires the token-threshold reading of the 16b "first trip at 3.89×"; *why* 16b tripped stays open. `2026-11-19b` keeps the **w4 724.6** aggregate-peak record but its w1 cell carries the tenancy tax it disclosed. The ceiling that once looked like KV at w40 was the `--queue-size` **default of 32** (fixed 2026-11-19; KV rows are not comparable across that boundary). Earlier rows (1.6.0 / 1.6.1 / the 11-13 single-tenant pass at w1 209.5, TTFT 159/229) stay in the leaderboard table |
| Tool-loop gate (tool hygiene) | [`docs/tool-loop-gate-benchmark-results.md`](docs/tool-loop-gate-benchmark-results.md) | **[`bench/tool-loop-gate/`](bench/tool-loop-gate/)** — `run_gate.sh` (pins endpoint, model id and the two sampling axes; reads stack pins from the live supervisor) and `summarize.py` (per-task rows, re-derives the harness's own summary, computes the stub confound and the determinism band). Instrument is **third-party and unmodified**: `vcruz305/hermes-agentic-bench` `hermes_loop_gate.py` @ `6dc6f0e` (MIT), kept outside this repo | Wave `2026-11-19a`, 6 passes / 120 task-runs on the queue-size 64 engine: **14–15 of 20** (band, not a single number), mean 2.0–2.8 tools, **0 parse failures**, 1 duplicate-call task-run, **3 cap hits** — loop hygiene clean, stop discipline not. 13 tasks pass every axis, 4 fail every time (2 of them **grader shape**: a correct refusal scored as over-work, a task solved in one command scored as a wrong tool), 3 unstable. Disclosed confound: **91/301 calls (30 %) got the scripted world's stub reply**, and the split is near-perfect (always-pass tasks hold 6 stubs, always-fail 68). **`temperature 0` does not pin agent behavior**: 14/20 traces bit-identical across four greedy passes while task 06 escalated 7 → 16 → 20 → 20 calls |
| τ²-bench (environment-graded agent tasks) | [`docs/tau2-bench-benchmark-results.md`](docs/tau2-bench-benchmark-results.md) | **[`bench/tau2-bench/`](bench/tau2-bench/)** — `run_wave.sh` (pins the tag, the endpoint and the judge-free task scope; reads stack pins from the live supervisor), `summarize.py` (per-simulation rows, re-derives τ²'s own `pass^1`/`pass^2` and action counts, `--from-rows` re-derivation, engine-sample join) and `sample_engine.py`. Instrument is **third-party and unmodified**: `sierra-research/tau2-bench` @ tag `v1.0.1` = `fc0055dc` (MIT), kept outside this repo, not on PyPI | Wave `2026-11-19a`, **238 tasks × 2 trials = 476 simulations, all scored, 0 infra errors** in 2 h 26 m: **airline pass^1 0.870 / pass^2 0.820**, **retail (74 of 114, judge-free) 0.791 / 0.676**, **telecom 0.873 / 0.772**, self-play. **45 of 238 tasks flipped between two `temperature 0` trials** — and τ²'s `pass^k` is `C(n_pass,k)/C(n_trials,k)`, so pass^1 − pass^2 *is* that flip count. A **width control** (`results/2026-11-19b-width-control/`) then refuted this row's first mechanism claim: at `--max-concurrency 1` the engine produced **19,439 width-1 decode batches and none wider**, yet still flipped 3 of 8 sampled tasks — the same count as the width-3 replication, so batching is excluded and the surviving candidate is long-context prefix-cache state. **Batching excluded by control** (`2026-11-19b-width-control`): at `--max-concurrency 1` the engine ran **19,439 width-1 decode batches and none wider**, and still flipped 3 of 8 sampled tasks — same count as the width-3 replication. Scope deviation stated: the 40 retail tasks needing the `gpt-4.1-2025-04-14` judge are excluded (v1.0.1 gives no local override); `train`/`test` is **not** the judge boundary. Engine finding: **97.3 % of 78.25 M prompt tokens served from cached KV** (2.79 M rows prefilled), decode width **b3 dominant**, and the **first non-zero `admission.*` counters** this engine has shown |
| Visual venv (OpenCV) | [`bench/visual-venv/README.md`](bench/visual-venv/README.md) | `bench/visual-venv/` — bench script, cold-run probe, run1/run2/run4/run5/**run6** JSON (run3 lives with its window at `bench/splash-concurrency/results/clean-2026-11-13/run3.json`; **fixtures withheld**: real face frames; hashes in the JSONs) | opencv-python **5.1.0.95** (upgraded at run5, opencv + contrib together, numpy 2.5.5, FFmpeg 9.0.2): canonical **91 faces / 0.227 s** (run5) → **0.268 s** (run6, 2026-11-18) with **PNG counts bit-identical across all six runs** (48/48 detect rows, whole-frame raw 92, match-probe, cosine stats, surface markers, fixture hashes); H.264 counts are **bit-identical within each wheel generation but 9 of 48 rows shifted ±1 at run5**, traced to the bundled FFmpeg 9.0.2 decoder changing decoded pixels, and run6 reproduces that shift exactly; run5 measured **×0.853** median across timing rows vs 5.0.0.93, run6 **×1.18** vs run5 on the same wheel (host state, not the library); the same-build run2 pair fixes **×1.15 as the ceiling** for calling a timing change real. Marker watch: `FaceRecognizerSF.match()` **still mutates its input vectors** in the shipped wheels (upstream fix not in the release) |

(Superseded drafts live in [`archive/`](archive/) — including the never-run 2026-09
concurrency spec the Splash ladder later implemented.)

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

- [τ²-bench — an agent benchmark you can actually reproduce — 2026-11-19](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-tau2-bench.html)
- [Tool-loop gate — the model stops using tools, it just doesn't stop early — 2026-11-19](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-tool-loop-gate.html)
- [Splash engine · `--queue-size 64` — the KV ceiling was a request count — 2026-11-19](https://willturner-maker.github.io/benchmarks/reports/2026-11-19-splash-queue-size.html)
- [All-suites day — Resolve MCP 5.3.4 · opencode 2.3.2 · Splash 1.7.0 · OpenCV 5.1.0.95 — 2026-11-18](https://willturner-maker.github.io/benchmarks/reports/2026-11-18-all-suites-day.html)
- [Blender benchmark finals — 2026-11-18](https://willturner-maker.github.io/benchmarks/reports/2026-11-18-blender-benchmark.html)
- [Splash engine 1.7.0 — three passes + clean-window batches — 2026-11-17](https://willturner-maker.github.io/benchmarks/reports/2026-11-17-splash-1-7-0.html)
- [Agentic frontier (F-series) — 2026-11-16](https://willturner-maker.github.io/benchmarks/reports/2026-11-16-agentic-frontier.html)
- [Splash concurrency + KV pressure — 2026-11-12](https://willturner-maker.github.io/benchmarks/reports/2026-11-12-splash-concurrency.html)
- [Clean-window suites, all three live suites — 2026-11-13](https://willturner-maker.github.io/benchmarks/reports/2026-11-13-clean-window.html)
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
- `archive/` — superseded design docs kept for provenance, each banner-marked at the top;
  not suites, not runnable.
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
