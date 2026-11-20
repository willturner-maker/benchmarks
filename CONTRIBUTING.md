# Contributing

Thank you for wanting to add a data point or improve the suites. This repository is
deliberately strict about comparability; the rules exist so a number published here
can be trusted by someone who was not in the room when it was measured.

## Adding a leaderboard row

The preferred path is the issue form:

https://github.com/willturner-maker/benchmarks/issues/new?labels=leaderboard&template=leaderboard-row.yml

It asks for:

- Media class (run `python3 -I bench/resolve-agentic/check_media.py yourclip.mov` first)
- Tenant conditions (single-tenant vs concurrent agents)
- Exact builds (Resolve, MCP server, Splash, model)
- Independent read-back attestation

A row with a clear footnote is more valuable than a clean-looking number that cannot
be reproduced.

## Running the suites locally

### Resolve agentic suite

```bash
# Validate your media and generate the frame numbers the briefs need
python3 -I bench/resolve-agentic/check_media.py path/to/yourclip.mov

# Then follow
#   bench/resolve-agentic/MEDIA.md
#   bench/resolve-agentic/tasks.md
#   bench/resolve-agentic/RUNBOOK.md
```

The suite is designed so you can run it on your own footage. Published class-A numbers
are tied to a specific media equivalence class; other media goes in the community table.

### Splash concurrency / KV ladder

```bash
python3 -I bench/splash-concurrency/ladder_kv.py --out my-run.jsonl
```

See `docs/splash-engine-benchmark-results.md` for interpretation notes.

### Tool-loop gate — the suite that runs on **your** hardware

The instrument is third-party and must stay unmodified, so clone it outside this repo and pin the commit:

```bash
git clone https://github.com/vcruz305/hermes-agentic-bench ~/hermes-agentic-bench
cd ~/hermes-agentic-bench && git checkout 6dc6f0e           # the commit our rows are comparable to
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt  # httpx only
```

Then, from this repo (point it at any OpenAI-compatible endpoint that returns `message.tool_calls`):

```bash
GATE_BASE=http://127.0.0.1:8000/v1 MODEL='your-model-id' \
  bench/tool-loop-gate/run_gate.sh bench/tool-loop-gate/results/2026-MM-DDa defaults greedy greedy greedy
python3 bench/tool-loop-gate/summarize.py bench/tool-loop-gate/results/2026-MM-DDa
```

A community row must state: host, engine, model + quant, **upstream commit**, **sampling axis**
(`defaults` = 0.6/0.95/64, `greedy` = 0/1/1 — never averaged together), **pass count** (≥2 default,
4 greedy: this gate's variance is real), the **stub-response rate** `summarize.py` prints, and the
**grader-shape split** (how many failures were call-count/tool-choice criteria rather than wrong
behavior). No footage, no container, no GPU toolchain — which is why these rows land in the community
table with those fields present. Do **not** run `hermes_native_battery.py` without reading upstream's
warning that its file toolset cannot be sandboxed.

### τ²-bench — full agent tasks, graded by the environment

Also third-party and tag-pinned, and also reproducible on your hardware — but harder: an agent and a user
simulator converse over scripted tools with a real database, and the reward comes from the **end state**
(DB-state hash, in-process env-assertion replay, substring check).

```bash
git clone https://github.com/sierra-research/tau2-bench ~/tau2-bench
cd ~/tau2-bench && git checkout v1.0.1 && uv sync     # NOT on PyPI; python >=3.12,<3.14
```

Then, from this repo:

```bash
TAU2_MODEL='openai/your-model-id' \
TAU2_LLM_ARGS='{"temperature":0,"api_base":"http://127.0.0.1:8000/v1","api_key":"local","max_tokens":4096}' \
  bench/tau2-bench/run_wave.sh bench/tau2-bench/results/2026-MM-DDa
python3 bench/tau2-bench/summarize.py --wave-dir bench/tau2-bench/results/2026-MM-DDa \
  --domains "airline retail telecom"
```

A community row must state: host, engine, model + quant, **tag and commit** (`v1.0.1` = `fc0055dc…` — never a
version string, because `main` declares `2.0.0` while carrying an `[Unreleased]` section), **trial count**
(≥ 2: our wave flipped 45 of 238 tasks between greedy trials), **which `pass^k` definition** it quotes
(upstream `C(n_pass,k)/C(n_trials,k)` vs the looser `mean p^k` — they differ by 2.5–5.7 points), **self-play
or cross-model** user simulator, **task scope** (airline 50 + retail 74 judge-free + telecom 114 is our set;
the 40 judged retail tasks need `gpt-4.1-2025-04-14` and have no local override on 1.0.1 — if you judged them
with a cloud model, say so and your row is **not** comparable to ours), and `--max-concurrency`. Publish
`pass^1` **and** `pass^2` **and** the flip count, never a pooled cross-domain mean, and label which graded
components each domain scores (telecom's `DB Match` is informational only). Run detached if you want the
engine-side figures: our sampler attributes traffic by `prompt_tokens` size, so an operator chat session on
the same engine is visible and separable — the smoke run showed it accounting for 94 % of peak residency.

### Visual venv

```bash
~/resolve-vision-venv312/bin/python -I bench/visual-venv/bench_visvenv.py \
  --out runN.json --png yourframe.png --mp4 yourclip.mp4
```

The `--png`/`--mp4` defaults name fixture frames that are **not committed** (they hold
real faces) — `bench/visual-venv/README.md` says how to substitute any face-dense frame
of your own. `--models` defaults to the two opencv_zoo ONNX files.

## Pre-commit guard

```bash
bash tools/precommit-scan.sh --install
```

This refuses commits that contain local paths, camera filenames, credential-shaped
strings, or other deny terms. Run `--all` to audit the tree.

## Release tags

Tags here are **dated record snapshots**, not semver — waves are records, not software.
Convention: tag the commit that publishes a wave's distilled record
(`results-<wave>.json` + findings + rationale docs) using the wave label as the tag
(`2026-11-16f`), and let the release notes say what the snapshot pins: seal verdict,
headline results, and any decision of record (e.g. the 16f tag also pins Claude Code's
removal from the rotation). Tags are never moved after publication; a corrected record
gets a new dated tag, same as a corrected wave does.

## Style notes

- Prefer dated wave directories under `bench/<suite>/results/<wave>/` rather than
  overwriting previous raw data.
- Self-contained HTML scorecards go in `reports/`. They must not depend on external
  assets.
- Machine-readable standings live in `leaderboard/results.json`; `docs/leaderboard.md`
  is the human view and should stay in sync.

## Questions

Open an issue. The repository is public and the measurement methodology is meant to
be inspectable.
