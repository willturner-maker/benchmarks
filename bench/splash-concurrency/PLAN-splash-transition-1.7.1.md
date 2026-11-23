# PLAN — Splash 1.7.0 → 1.7.1 transition (Tier 0 executed 2026-11-22)

Method borrowed from `../resolve-agentic/PLAN-mcp-transition-5.3.3.md`: fingerprint the instrument with
a **committed method** before the sync, diff on read-back, and only then decide what deserves a replay —
including the option of running nothing and recording why.

Status: **Tier 0 done. Tier 1 blocked on the operator** (`brew upgrade splash` restarts the engine that
is serving this session, so it cannot be run from inside the session it hosts).

## Why this upgrade, and which of its claims apply here

1.7.1's headline is Neural-Engine prefill (14–24 % sooner to first token on some machines). For this
stack that claim **does not apply**, read off the live engine, not inferred:

```
ane_ffn: {"state": "off", "share": 0, "reason": "the target's FFN layers are not all dense"}
```

Qwen3.8-Flash-Next is a hybrid (GDN + attention, MoE FFN), so its FFN is not all dense and the split is
never armed. That also shrinks the numerics risk the notes raise (more FFN in ANE int8), and the int8
MoE prefill path is *resident MLX* models only — GGUF experts stay bf16, and the paged-attention note
says output bits are unchanged. What is left, in the order this repo can use it:

| 1.7.1 change | Relevance here |
|---|---|
| `--max-concurrent-requests` 1–8 (default 4) | **The reason to upgrade.** Every width ladder published since 1.6.1 plateaus near 700 tok/s and the explanation was always `memory_plan.budget.maximum_batch_width: 4`. Eight lanes is the first lever that axis has had. Upstream measured only 1.13× at 8 vs 4 on 35B and level on 27B — but that is their hardware and their model; this is a 30-core M5 Ultra with 96 GB. |
| Shared system+tools head cached across conversations (2.5–2.9× faster TTFT upstream), and `usage` gaining `prefix_tokens` / `state_source` / `lost_state` | This *is* the τ² and OpenCode workload: τ² re-sends an identical head every session (97.3 % reuse measured on the 11-19 wave). The three new usage fields are what this suite has been inferring from counter deltas. |
| `/status` + `/metrics` report SSD reads of spilled KV and streamed weights | KV records (19-ext, 19b, 19c) reason from `spill_moves`/`kv_demotions` deltas because no direct counter existed. |
| Decode **level** with 1.7.0, and 0.10–1.01 % slower at the default 4 lanes | At today's config the upgrade is neutral-to-slightly-negative. It only pays if the lane count moves. |
| Known issue: Flash-Next with a **starved expert store** costs 20–30 % more time/token | Our store is not starved: `streamed_experts` cap 49,095,050,000 B, 23,007 of 24,576 experts resident. Worth one read after the upgrade, not a blocker. |

## Tier 0 — what was captured, 2026-11-22

Two committed instruments, both read-only against the live engine:

- `engine_fingerprint.py capture` → `results/splash-1.7.1-transition/fingerprint-1.7.0-pre.json`
  (engine binary sha256, server tree digest, `release.json`, Homebrew receipt, `/status`, `/metrics`
  series set, and the argv of the **running supervisor**, not of a start script).
  `engine_fingerprint.py diff PRE CUR` prints the structural delta with runtime counters suppressed.
- `golden_probes.py` → `results/splash-1.7.1-transition/golden-probes-1.7.0-pre.json`
  13 fixed requests, each run twice (single-run where the state matters), byte-hashed.
  `golden_probes.py compare PRE CUR` prints the per-probe delta.

### The 1.7.0 anchor (all read back, none assumed)

| Field | Value |
|---|---|
| version / Cellar | Splash 1.7.0, `/opt/homebrew/Cellar/splash/1.7.0` |
| engine binary sha256 | `57925acb13dc8a3d…e72ca874` |
| server tree digest (45 files) | `9dce967409535e24…67cd30c0` |
| model layout sha256 | `aed100ae7c222db3…a0d548bf` |
| cache build id | `src-90952b2ba4d49c04…8975ac7` |
| context | 262,144 (`context_bounds`: resident 155,633 · spilled/disk/window 262,144) |
| KV budget | `kv_capacity_pages` 4,864 = `kv_capacity_tokens` 155,648 @ 423,936 B/page |
| batch width | `maximum_batch_width: 4`, `lane_state_bytes` 276,496,384 (263.7 MiB/lane) |
| memory | hard budget 60,129,542,144 · weights 53,055,603,472 · `minimum_required_bytes` 58,145,268,496 · dynamic 2,370,026,736 |
| ANE FFN | **off** — "the target's FFN layers are not all dense" |
| verify_rows | `auto` |
| pinned argv | `--max-memory=60129542144 --max-cache-disk=274877906944 --persistent-cache --default-reasoning-effort=medium --thinking-token-budget=32768 --queue-size=64` |
| `/metrics` | 168 series, text sha `89b86464f9dc92d0…` |

**The lane-count arithmetic, stated before the upgrade so it can be checked after it.** Four more lanes
cost 4 × 276,496,384 = 1,105,985,536 B. Against a hard budget of 60,129,542,144 that leaves ~878 MB of
room once `minimum_required_bytes` rises — less than the 2,062,024,704 B the current KV capacity needs.
Prediction: with 8 lanes the engine must shrink KV capacity (`kv_capacity_tokens` below 155,648) or
refuse the lane count. Tier 2 reads that number first.

### Instrument bugs found while building it (published, not hidden)

Each of these would have printed plausible numbers:

1. `/metrics` is Prometheus text, not JSON — the first fingerprint stored `unavailable: Expecting
   value: line 1 column 1`. Now digested as text plus the series-name/type sets.
2. The long-prompt probes were sized by character count: the "2K" prefill measured **934** tokens and
   the 63-vs-72 follow-up pair measured **381 vs 387**. Both probes were testing something else. Now
   1,894 tokens, and follow-up messages calibrated to their named cost by measuring the message alone
   (63 and 71 measured).
3. Calibrating against *total* `prompt_tokens` was a logic error — with a 2K head the total can never be
   63, so the padding loop went negative and appended empty strings. Fixed by calibrating the message.
4. Streaming responses carry no `usage` unless `stream_options.include_usage` is sent, so the streaming
   probes could not report what they prompted or cached.
5. Design flaw, not a typo: a single combined hash per response was the wrong comparison. The first
   capture showed probes whose **visible output was byte-identical across repeats while the reasoning
   stream differed**, and 1.7.1 explicitly shifts reasoning length — a combined hash would flag every
   probe as changed. Probes are now `kind`-typed: `byte`, `grammar` (compared as parsed payload),
   `timing` (usage/latency, no byte claim).

Also kept as evidence rather than deleted: `golden-probes-1.7.0-pre.attempt1-harness-bugs.json` is the
first, flawed capture, so the fixes above can be checked against what they fixed.

### Baseline findings from the 1.7.0 capture

- **Grammar crowd-out.** `json_schema_crowdout_64` (a `response_format: json_schema` request capped at
  64 completion tokens) spent **64/64 tokens on reasoning and emitted nothing**, twice of two,
  `finish=length`, `content=null`. Thinking is billed inside the completion cap here too, so a tight cap
  under a grammar yields an empty result rather than a short one. Byte-stable, so it is a useful
  cross-version anchor.
- **The prefix cache already reuses a shared head**: both shared-head sessions reported
  `cached_tokens 800` of 818. So the *token* side of 1.7.1's shared-head claim is already partly served
  on 1.7.0; what 1.7.1 adds is the cached *state*, which should show up as `state_source` and a TTFT
  move, not as a bigger `cached_tokens`.
- Cold vs warm 2K prefill (same engine, different nonce per capture): cold `prompt 1894 / cached 0 /
  719.7 ms`; warm `prompt 1894 / cached 1888 / 227.2 ms`.
- **Prose at temperature 0 is not byte-stable on this build.** The shared-head sessions produced
  different visible answers run to run (`finish=stop`, completions 114 and 146). This is the same floor
  the τ² same-seed pair measured (0/238 transcripts identical), now visible at probe scale — which is
  why byte comparison here is limited to short greedy and grammar-constrained outputs.
- Grammar payload variance is real and harmless: two runs of the same streamed `json_schema` request were
  both valid, differing only by an empty `"flags": []`. Compared as bytes that reads as a version
  effect; compared as parsed payload it is not.
- Byte set reproduces: 8 of 8 byte/grammar probes identical within-build; reasoning identical in 6 of 8.

## Tier 1 — the upgrade (operator), then read-back (me)

```
brew upgrade splash                    # operator; this session's engine goes down
~/resolve-ai-workflow/stop.sh && ~/resolve-ai-workflow/start.sh    # operator
```

Then, before any benchmark traffic: `engine_fingerprint.py capture` → `fingerprint-1.7.1-post.json`, then
`diff` pre/post. Pass criteria, all by read-back:

1. version 1.7.1, engine binary + server tree hashes moved (they must).
2. context **still 262,144** and `kv_capacity_tokens` still 155,648 — the memory plan is the thing an
   upgrade can silently change, and every KV number in this repo is stated against those two.
3. pins intact: `--thinking-token-budget=32768 --queue-size=64 --persistent-cache`.
4. `ane_ffn.state` still `off`; `maximum_batch_width` still 4 (lanes are opt-in, see exclusions).
5. new surface present: `max_concurrent_requests` in the plan, `prefix_tokens`/`state_source` in `usage`,
   SSD-read series in `/metrics`. Record the series-name delta from the 168 baseline.
6. model layout sha unchanged (`aed100ae…`) — if the cache re-built, say so and treat `build_id` as new.

## Tier 2 — what gets measured, in value order

1. **Lane ladder, 1 → 8** (sealed spec: `width512.py` 512-token rounds, widths 1→8, one run each).
   Reads: does the ~700 tok/s plateau lift, do decode batches of width 5–8 appear in
   `scheduler.decode_batches_by_width`, and what does it cost — `memory_plan.budget.kv_capacity_tokens`,
   `context_bounds.resident`, `lane_state_bytes`. ~30 min. Run twice: once at the default (4) to confirm
   the 1.7.1-vs-1.7.0 plateau is unchanged, once at 8 to test the lever.
2. **Shared-head TTFT**: the 13-probe set is already the instrument; read `prefix_tokens`,
   `state_source`, `lost_state` and the `prefill_cold_2k`/`prefill_warm_2k` and `shared_head_*` timings
   against the 719.7 ms / 227.2 ms baseline. ~5 min. Directly predicts OpenCode cold-start latency.
3. **Golden-prompt byte/grammar diff** (`golden_probes.py compare`). If the 8 byte probes hold, 1.7.1
   rows may be compared against published 1.7.0 rows; if any moves, the epoch boundary is real and
   scored rows must be re-anchored, not spliced. ~2 min, already scripted.
4. **New SSD counters baselined** over one ordinary wave — replaces inference with measurement in the
   next KV record.
5. Only if (3) moves byte outputs: one τ² wave (238 × 1, ~75 min) to re-anchor the flip floor on the new
   epoch. If (3) holds, a single wave is still worth running for the same reason, and the ±4 pt noise
   rule is what makes the comparison honest either way.

## Explicitly excluded

- `--sampling-default`: it silently rewrites comparability for every sealed series in this repo.
- MLX model paths (`flint`, `qwen3.8-flash-next` from MLX checkpoints): a different weights format, so a
  different instrument, not a version step. Would need its own sealed series, not a splice.
- Raising lanes in `start.sh` as a default. Opt-in via `SPLASH_LANES`, exactly like `AGBENCH_OUTPUT_TOKENS`:
  changing lanes mid-series would break the ladder comparison the way the `--queue-size` move did, and
  the ladder is the longest-running series here.
- The thinking-budget A/B, closed as answered: budgets above the harness's 4,096 completion cap cannot
  bind, and observed thinking runs 150–3,500 tokens per agent turn. The 2026-11-22 chain record carries
  the null and the noise floor it produced.

## Tenancy note

The fingerprint and all three probe captures went to the engine that serves this OpenCode session
(port 8000, instance `4f4765b265d032ca1b57da58`), 17:19–17:24 local on 2026-11-22. No benchmark wave
was in flight (checked before each window). The probe traffic is itself tenancy for any wave that runs
against the same engine afterwards, so the window is recorded here and the scheduler counter deltas are
in both captures. Fingerprint diffs suppress runtime counters for this reason; lifetime counters reset
on relaunch, so only window deltas compare across the upgrade.
