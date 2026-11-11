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
