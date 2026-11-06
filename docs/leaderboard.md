# Leaderboard

Version-to-version standings for the local AI/editing stack. Machine-readable source:
[`leaderboard/results.json`](../leaderboard/results.json) — this page is its rendered view.

**Three rules before you read or add a row** (they're what keep a leaderboard honest):

1. **Same media class or different table.** Render ms from class B media (anything that
   isn't the [class A](../bench/resolve-agentic/MEDIA.md) equivalence class) go in the
   community table below, never alongside class A rows. A 1080p H.264 render being
   "faster" than an 8K HEVC one says nothing about the toolchain.
2. **Tenant conditions are part of the number.** Single-tenant renders only; two-agent
   waves inflate render ms (one published T7 render came in at 7285 ms because another
   agent was doing Fusion work on the same engine).
3. **Read-backs, not claims.** A row is admissible only if every value came from an
   independent probe — ffprobe on the output file, timeline item geometry, the server's
   operation log. Agent self-reports never enter a cell.

## Resolve MCP — class A media, reference host

Reference host for all rows: Apple M5 Ultra (64-core GPU), 96 GiB unified memory,
macOS 27.2, render output and scratch on external volumes.

| Date | Resolve | MCP | cold render | warm median | warm fps | prepare | verify | set_current | probe | agentic outcomes | honest |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-03 | 21.1.2.10 | 4.18.5 | 3436 ms | 1414 ms | ~85 | 243 | 61 | 127 | 7 | **18/18** | 18/18 |
| 2026-11-06 | 21.2.0.6 | 4.19.0 | 3090 ms | 1296 ms | 93.4 | 126 | 39 | 98 | 11 | **18/18** | 18/18 |
| 2026-11-06b | 21.2.0.6 | 4.19.2 | 1668 ms¹ | **1196 ms** | 101 | 162 | 50 | 97 | 11 | n/a² | n/a |

Render probe: 121 frames, 3840×1520, mov/H.264, queue time excluded
(`TimeTakenToRenderInMs`, file verified with ffprobe). Op columns are server-side
operation medians in ms.

¹ Cold 1668 ms is **host state, not an MCP win** — 4.19.x never touches the render path;
the same-source page cache was warm-ish. Warm 1196 ms equals the best prior mark.
² No agentic n=3 for 4.19.2: the bump was behaviour-free (upstream fix of the CLAP
audio-embedding bug we filed, verified by direct probe the day it shipped).

Agentic column = six tasks × three fresh sealed agents, graded only from read-backs;
details and per-task cost in
[the results doc](resolve-agentic-benchmark-results.md). The 2026-11-06 run's agents were
served by the local model (Qwen3.8-Flash-Next IQ3_S via Splash 1.6.0), not a cloud API.

**Regression worth watching:** `probe_timeline_structure` went 7 → 11 ms between
21.1.2 and 21.2. Everything else improved.

## Splash engine — reference host

| Date | Engine | Model | TTFT warm | TTFT cold | decode w1 | decode plateau | suspensions at 4.4× KV | agentic | honest |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-06 | Splash 1.6.0 | Qwen3.8-Flash-Next IQ3_S (262k ctx) | 201 ms | 380 ms | 170 tok/s | **372–383 tok/s**, widths 4→32 (2.5–2.6×) | **0** | 11/12 | 12/12 |

Rerun in one pass: `python3 -I bench/2026-11-06/ladder_kv.py` (width ladder + KV-pressure
probe, one combined summary). The plateau is a wall, not a cliff; the KV probe's negative
result (no suspension at 611,244 prompt tokens) is a finding, not a missing number.

## Community runs — your numbers

Empty by design. Add a row and you get credit *and* scrutiny: state the media class, the
stack versions, n, and whether runs were single-tenant.

| Date | Host | Resolve | MCP | media class | render probe ms | agentic outcomes | honest | notes |
|---|---|---|---|---|---|---|---|---|
| _open_ | | | | B expected | | | | |

### How to add a row

1. Validate your fixture clip: `python3 -I bench/resolve-agentic/check_media.py yourclip.mov`
   → it prints your **class** and derives the frame numbers.
2. Run the suite: [`bench/resolve-agentic/RUNBOOK.md`](../bench/resolve-agentic/RUNBOOK.md)
   (fixture setup → seal the conditions → six briefs in `tasks.md` → grade from read-backs).
3. For the engine suite: `python3 -I bench/2026-11-06/ladder_kv.py --out my-run.jsonl`.
4. Submit it through the
   **[Leaderboard row issue form](https://github.com/willturner-maker/benchmarks/issues/new?labels=leaderboard&template=leaderboard-row.yml)**
   — it asks for exactly what `suites.community_runs` needs (date, host, exact builds,
   agent model and how it was served, media class plus the validator output, tenant
   conditions, the numbers, and deviations). You don't have to know the JSON schema;
   the row gets added to `leaderboard/results.json` from your issue.

   The form ends in a four-item attestation — read-back-only grading, media class stated,
   tenant conditions stated, deviations disclosed. All four must be true for a row to be
   **ranked**; a row missing one is still welcome, listed with a note instead.

Rows that omit the media class or mix tenant conditions get the row, not the number:
they're listed with a note rather than ranked.
