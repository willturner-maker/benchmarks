# Stack Overview

This repository tracks version-to-version performance and correctness of a fully local
DaVinci Resolve Studio + AI workstation. Every published number comes from independent
read-backs (ffprobe, timeline geometry, engine status, operation logs), never from an
agent’s self-report.

## Components

| Component | Role | What we measure |
|-----------|------|-----------------|
| **Splash** | Local LLM inference engine (brew package). Serves GGUF models (currently Qwen3.8-Flash-Next IQ3_S) over an OpenAI-compatible HTTP API on `127.0.0.1:8000`. Manages KV cache, concurrency, and admission. | Decode throughput (tok/s), TTFT, concurrency scaling (width ladder), KV-pressure behaviour, agentic task success when Splash is the backend. |
| **DaVinci Resolve Studio + MCP** | Resolve itself plus a Model Context Protocol server that exposes timeline, media-pool, render, and Fusion operations as tools an LLM can call. | Agentic task outcome & honesty (six sealed tasks × three agents), render latency (cold/warm), server-side operation medians, concurrency effects. |
| **Visual venv** | Isolated Python 3.12 environment (`~/resolve-vision-venv312`) with OpenCV (+contrib) used for face detection, embedding, and related vision work that feeds Resolve workflows. | Import/init timing, YuNet detection ladder, SFace embed speed, API surface changes, determinism across runs. |
| **Tool-loop gate** | Third-party, commit-pinned, **unmodified** contract tests from [`vcruz305/hermes-agentic-bench`](https://github.com/vcruz305/hermes-agentic-bench) (`hermes_loop_gate.py`) driven by our own runner. 20 tasks against scripted tools over an OpenAI-compatible endpoint — no containers, no fixtures, nothing host-specific. | Tool-call contract survival (parse failures), loop hygiene (call counts, duplicate calls, hitting the turn cap), and whether the model **stops and answers**. The suite a community run can reproduce on any machine. |
| **τ²-bench** | Third-party, **tag-pinned** (`v1.0.1`), **unmodified** benchmark from [`sierra-research/tau2-bench`](https://github.com/sierra-research/tau2-bench): an agent and a user simulator converse over scripted tools with a real database. Clone lives outside this repo; not on PyPI (`uv sync` from the tag). | Environment-graded task completion: `pass^1`/`pass^2` from the **end state** (DB-state hash, in-process env-assertion replay, substring checks), plus the trial-to-trial flip rate, tool-call counts, per-call context depth, and what the engine's prefix cache does with a session that re-sends its own context every turn. |

## Why these benchmarks exist

- Splash and the Resolve MCP server are upgraded frequently. These suites give a fixed-condition baseline so a regression or improvement is visible immediately.
- Agentic work is graded only from ground-truth probes after the run. This catches both functional regressions and “the model claimed success but the timeline is unchanged” failures.
- Concurrency and KV behaviour on Apple Silicon unified memory are non-obvious; the width-ladder and KV-pressure probes quantify the practical headroom.
- The visual venv is watched for wheel updates; the suite exists so a 5.1.x change in face-detection behaviour or timing can be measured against a known baseline.
- The Resolve and Splash suites are host-bound (our footage, our engine state). The tool-loop gate and τ²-bench exist because an outside machine can run the identical instrument and produce a comparable agentic number — which is what turns a personal leaderboard into a benchmark. τ²-bench is the harder of the two: full multi-step tasks in scripted environments with a real database, graded from the **end state** (DB hash / env-assertion replay), so it measures task completion rather than tool-calling behavior alone.

## How the pieces interact

1. Splash loads the model and serves requests.
2. An orchestrator (or a human) launches sealed agents that talk to the Resolve MCP server.
3. The MCP server drives Resolve Studio (timeline edits, renders, Fusion comps).
4. After each task the harness probes Resolve and the filesystem independently and records the real outcome.
5. Separate suites measure Splash’s raw engine characteristics and the OpenCV environment used for vision-side work.

All published results are tied to a specific host configuration (Apple M5 Ultra, 64-core GPU, 96 GiB unified memory, macOS 27.2). Community submissions are welcome via the leaderboard issue form, provided media class, tenant conditions, and read-back attestation are stated.

## Privacy

Media-bearing fixtures (concert frames with identifiable faces, etc.) are never committed. Only SHA-256 hashes and regeneration recipes appear in the repository. The pre-commit scanner (`tools/precommit-scan.sh`) enforces this.

## Glossary

- **width** — number of concurrent decode streams issued to Splash in a ladder step.
- **wave** — a dated measurement pass (e.g. `2026-11-11h`); raw data lives under `bench/<suite>/results/<wave>/`.
- **class A** — the reference media equivalence class (HEVC Main 10 ≥ 8128×4288, ~29.97 fps, rendered to a 3840×1520 timeline). Other media is class B and goes in the community table.
- **tenant conditions** — whether a timing measurement ran single-tenant or while other agents shared the engine. Concurrent work inflates render times.
- **TTFT** — time to first token (Splash).
- **MCP** — Model Context Protocol server that exposes Resolve operations as tools an LLM can call.
- **read-back** — an independent probe (ffprobe, timeline item geometry, engine `/status`, server operation log) used for grading. Agent self-reports are never accepted as data.
- **honest** — the agent’s claims matched the independent read-backs (no silent failures or unacknowledged side effects).
