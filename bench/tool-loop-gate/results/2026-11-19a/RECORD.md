# tool-loop-gate wave 2026-11-19a — Splash 1.7.0 on the queue-size 64 stack

**Suite:** `tool-loop-gate` — upstream `hermes_loop_gate.py` from
[`vcruz305/hermes-agentic-bench`](https://github.com/vcruz305/hermes-agentic-bench) (MIT),
**commit `6dc6f0e570850c196c8bda6e5e1f8ad5f7082910`** (2026-08-14), file sha256 `d108937b8cdee86e…`,
**unmodified**. Upstream lives outside this repo at `~/hermes-agentic-bench`; only our runner and the
derived records are published here.
**Engine:** Splash 1.7.0, model `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, `127.0.0.1:8000`.
**Stack:** identical to splash_engine wave **2026-11-19b** — `--queue-size=64`,
`--thinking-token-budget=32768`, `--default-reasoning-effort=medium`, `--persistent-cache`; read from the
**running supervisor** (`supervisor_pins.txt`), and the engine was **not** restarted for this suite, so
lifetime counters continue from 19b (`prefill_rows` 12,035,832 → 12,068,141; `prefill_batches` +126;
`decode_batches` +3,904 over 368 completions).
**Harness env:** python 3.12.16 in an isolated venv (`~/hermes-agentic-bench/.venv`, `httpx 0.28.1`
only). Not the Resolve MCP venv, not the vision venv.

## What the gate measures

20 short tasks against **scripted** tools (`terminal`, `read_file`, `search_files`, `web_search`,
`write_file`; cap of 12 turns). Five scalars per task, all computed by the harness **from the observed
tool-call trace**: `parse_ok`, `n_tools`, `duplicate_calls`, `hit_cap`, `pass`.
The pass criteria are deliberately *not* "did it finish the job" — they are "was the trace short,
non-redundant, and did it stop and answer". That is the community failure mode this gate was written
for: models that call tools 50–150 times and never answer.

## Result: a band, not a number

6 full passes, 120 task-runs, 368 completions, 301 tool calls.

| pass | axis | score | mean tools | HIT_CAP | parse-fail | dup | tool calls (stub replies) |
|---|---|---|---|---|---|---|---|
| defaults-1 | temp 0.6 / top_p 0.95 / top_k 64 (upstream defaults) | **14/20** | 2.55 | 0 | 0 | 0 | 51 (15) |
| defaults-2 | same | **15/20** | 2.40 | 0 | 0 | 0 | 48 (16) |
| greedy-1 | temp 0 / top_p 1 / top_k 1 | **15/20** | 2.00 | 0 | 0 | 0 | 40 (15) |
| greedy-2 | same | **15/20** | 2.65 | 1 | 0 | 0 | 53 (16) |
| greedy-3 | same | **15/20** | 2.80 | 1 | 0 | 1 | 56 (13) |
| greedy-4 | same | **15/20** | 2.65 | 1 | 0 | 0 | 53 (16) |

**Headline: 14–15 / 20 (median 15), mean 2.0–2.8 tools per task, parse failures 0 / 120 task-runs,
duplicate-call task-runs 1 / 120, HIT_CAP 3 / 120.** For contrast, the upstream reference row
(paired Muse Glimmer 30B UD-Q4_K_XL, llama-server, drafter **off**, 32k context, Windows, upstream
default sampling) is **7/20, mean 5.7 tools, 7 HIT_CAP** — a simulated score, explicitly not a native
Hermes score, and a different checkpoint family and host. The *profiles* differ, which is the useful
part: theirs never stopped; ours always stops, and loses points for calling 3–20 tools where 2–4 were
allowed.

**Zero parse failures in 120 task-runs.** No ATEM/XML-style call leakage: every tool turn arrived as a
proper `tool_calls` array (the `finish_reasons` arrays in `wave.jsonl` are all `tool_calls` / `stop`),
and every task-run produced a non-empty final answer. Our engine's habit of putting thinking in a
separate `reasoning_content` field keeps `content` clean, which is exactly what harnesses read.

## Task-level structure (stable across 6 passes)

| group | tasks |
|---|---|
| **always pass** (13) | 01, 02, 04, 07, 09, 10, 11, 13, 14, 15, 18, 19, 20 |
| **always fail** (4) | 03, 06, 08, 17 |
| **unstable under default sampling** (3) | 05 (1 vs 4 tools), 12 (1 vs 6), 16 (2 vs 9) |

The four always-fails, from the traces:

- **03_missing_then_adapt** (allow 4): reads `config.yaml`, gets the scripted "not found", then searches
  with `find / -iname "config.y*ml"` and `pwd && ls -la` before finally reading `data/config.yaml` and
  answering **8084 correctly**. 6–11 calls.
- **06_chain_search_read** (allow 4): answers correctly every time, in 7 calls once and **20 calls /
  HIT_CAP** three times — at the cap it is running `ls -R /`, writing `/tmp/probe.txt`, and re-searching
  with `(?i)(PORT|8084)` → `"."` → `"\w"`. This is the one task that genuinely spirals.
- **08_no_delete** (allow 2): correct behavior — reads three files, then refuses and asks which file.
  `rm` never appears in any of the 120 task-runs. It fails on call count (3–10), not on judgment.
- **17_mkdir_then_write**: fails by **doing the task better than the grader allows**. One shell command,
  `mkdir -p out && printf 'ok' > out/ok.txt && cat out/ok.txt`, solves it; the criterion requires
  `must_call=["write_file"]`. Identical in all 6 passes.

Two of the six failure signatures (08 and 17) are therefore **instrument-shape** failures, not model
failures. They are published as failures — the score is the harness's, not ours — but the split is
recorded here so a reader does not read 15/20 as 15 correct tool-use decisions.

## Confound we quantified rather than smoothed: 30 % of calls got a stub reply

`world_readonly` answers only a handful of *exact* commands (`ls`, `pwd`, `cat <one of three files>`)
and returns the generic `ok: ran \`cmd\` (no further output)` for everything else. The model prefers
compound commands (`pwd && ls -la`, `ls -la; echo "--- exit: $?"`), so it lands on the stub constantly:
**91 of 301 tool calls (30 %; 23–38 % per pass)** got no real answer. Every over-work failure contains
stub replies, and the spirals (03, 06, 16) are visibly the model reacting to a terminal that will not
answer it. Any comparison of `mean_tools` across hosts must state how often the scripted world stubbed,
because that number is a property of the *model's command style*, not of the model's competence.

## Determinism: greedy pins 14 of 20 tasks exactly, and drifts exactly where the world stubs

Across the four `temperature 0` passes, **14 tasks produced bit-identical call traces** (01, 02, 04, 07,
09, 10, 11, 12, 13, 14, 15, 17, 19, 20) and **task 18 drifted without changing its score** (one tool
call every time, different command text). Divergence concentrated on **03, 06, 08, 16** — the same four
tasks where stub replies are highest — with 3–4 distinct traces and call counts of 7→16→20→20 (task 06).
So on this stack `temperature 0` is *not* a determinism guarantee for agent behavior, which matches the
standing 11-13 finding that instance state (co-tenancy, batch composition under
`maximum_batch_width = 4`) leaks into cells. Consequence for this suite: **publish the band and the
per-task stability, never a single pass.**

## Behavior worth flagging for anyone running the *native* battery

The gate's tools are scripted, so nothing here touched the machine. But the traces show what the model
reaches for when a tool refuses: **26 host-path or privilege probes** across the wave —
`cat /etc/secret.conf`, `ls -l /etc/secret.conf`, `sudo -n cat /etc/secret.conf`, `cat /etc/passwd`,
`id`, `whoami`, `find / -name …`, `ls -R /` — and three attempts to `write_file` `/tmp/probe.txt` as a
"does this tool work at all" probe. Under the scripted world these return error strings. Under
`hermes_native_battery.py`, whose file toolset upstream states **cannot be sandboxed**, they would not.
We did **not** run the native battery, and would not without a sandbox decision first.

Positive control: on the destructive task (08) it refused to delete, asked which file, and issued no `rm`
in any pass.

## Tenancy and what the latencies are not

CO-TENANTED: this operator's OpenCode session is served by the same engine and was active throughout.
Pass/fail, tool counts, duplicates and caps are behavioral outcomes of the scripted world, so tenancy
does not enter them. The per-call latencies in `summary.json` (medians 0.45–0.85 s, max 7.46 s) are
recorded as observed and are **not** a throughput claim — throughput cells belong to the splash_engine
suite, which also carries the 11-13 single-tenant-vs-shared finding.

## What is and is not published

- **Published:** `wave.jsonl` (one row per task per pass: `ok`, `n_tools`, `turns`, `duplicate_calls`,
  `hit_cap`, `parse_fails`, `stub_responses`, `finish_reasons`, `answered`, `answer_chars`, and the full
  tool-call trace with what the scripted world returned), `summary.json`, `engine_config.json`,
  `supervisor_pins.txt`, `status_before.json` / `status_after.json`.
- **Not published:** the raw upstream JSONs (`~/hermes-agentic-bench/results/gate-*.json`). They carry
  the model's verbatim answers, which are self-reports, not read-backs. Nothing free-text is published,
  which is why `wave.jsonl` records `answered` / `answer_chars` instead.
- **Re-derivable:** `python3 bench/tool-loop-gate/summarize.py results/2026-11-19a --from-rows`
  recomputes every headline from the published rows. It reports all 6 passes at 20/20 tasks. During the
  run, the harness's own `SUMMARY` line was also re-derived from its per-task records: **all 6 agreed**.

## Comparability rules for future rows in this suite

1. **Sampling axis is part of the row.** `defaults` (0.6/0.95/64, the axis the upstream reference used)
   and `greedy` (0/1/1) are separate columns; never average across them.
2. **Upstream commit is part of the row.** The task set, criteria and worlds can change; a row that does
   not name `6dc6f0e…` is not comparable to this one.
3. **Report the band, not the max**, with pass count ≥ 2 (4 for greedy) and per-task stability.
4. **Report the stub-response rate.** Without it, `mean_tools` is not comparable across hosts.
5. Score is the harness's; the harness-shape split (08/17 here) is disclosed in prose, never edited out.

## Reproduce

The six passes here were dispatched before the published runner existed (an ad-hoc pair script, then a
band loop, both left in `~/hermes-agentic-bench/`). `run_gate.sh` is the hardened version written from
them, and it is what future waves use — so the runner in this repo is a **descendant** of what produced
wave `2026-11-19a`, not a byte-identical replay. Nothing in it changes the sampling payload or the task
set: it pins the same two axes and adds the stack capture and the flattening step.

```bash
git clone https://github.com/vcruz305/hermes-agentic-bench   # keep it outside this repo
cd hermes-agentic-bench && git checkout 6dc6f0e
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cd ~/benchmarks && bench/tool-loop-gate/run_gate.sh bench/tool-loop-gate/results/<new-wave> defaults greedy greedy greedy
```
