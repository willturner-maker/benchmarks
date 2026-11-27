# Tool-Loop Gate — Results (suite debut 2026-11-19)

**Purpose:** measure the axis our other suites cannot see — **does the model stop using tools, and does
its output survive the tool-calling contract** — with an instrument third parties can run on their own
machine. The `resolve-agentic` suite scores *our harness plus MCP*; this one scores **model + engine
plumbing** and nothing else.

**Host (fixed for comparison):** Apple M5 Ultra, 64-core GPU, 96 GiB unified memory, macOS 27.2.

**Stack:** Splash **1.7.0**, model `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`,
`127.0.0.1:8000`, `--queue-size=64`, `--thinking-token-budget=32768`,
`--default-reasoning-effort=medium`, `--persistent-cache` — pins read from the **running supervisor**
(`pgrep -f server.server`), same engine launch as splash_engine wave `2026-11-19b` (no restart, so the
engine's lifetime counters continue across both suites: `prefill_rows` +32,309 and `decode_batches`
+3,904 over this suite's 368 completions).

**Instrument (third-party, unmodified, commit-pinned):**
[`vcruz305/hermes-agentic-bench`](https://github.com/vcruz305/hermes-agentic-bench) →
`hermes_loop_gate.py`, commit `6dc6f0e570850c196c8bda6e5e1f8ad5f7082910` (2026-08-14), MIT,
sha256 `d108937b8cdee86e…`. The clone lives **outside this repo** at
`/Volumes/YourVolume/local.AI/bench/hermes/hermes-agentic-bench` (moved there 2026-11-23
from `~/hermes-agentic-bench`; gate file byte-identical across the move). Its venv was
deleted in the move (moved venvs never work — internals hardcode absolute paths); rebuild
with `python3.12 -m venv .venv && pip install -r requirements.txt`. Our contribution is
`bench/tool-loop-gate/run_gate.sh` and
`summarize.py`.

## Contents

- [What the gate scores, and what it is for](#what-the-gate-scores-and-what-it-is-for)
- [Wave 2026-11-19a — the band](#wave-2026-11-19a--the-band-6-passes-120-task-runs)
- [Wave 2026-11-23 on Splash 1.7.1](#wave-2026-11-23-gate-171-the-171-epoch-row)
- [Task-level structure](#task-level-structure-stable-across-six-passes)
- [Grader-shape failures vs model failures](#grader-shape-failures-vs-model-failures)
- [The stub confound](#the-stub-confound-91-of-301-calls)
- [Determinism under temperature 0](#determinism-under-temperature-0)
- [Behavior notes with harness consequences](#behavior-notes-with-harness-consequences)
- [Comparability rules for future rows](#comparability-rules-for-future-rows)
- [Running it on your own machine](#running-it-on-your-own-machine)

## What the gate scores, and what it is for

20 short prompts against five **scripted** tools (`terminal`, `read_file`, `search_files`,
`web_search`, `write_file`), 12-turn cap. Per task the harness records five scalars, all computed from
the **observed call trace**:

| scalar | what it is catching |
|---|---|
| `parse_ok` | assistant text that looks like a tool call (`<function=`, ```` ```json {"name" ````) while the API returned none — i.e. a server or chat template that cannot emit real `tool_calls` |
| `n_tools` | industriousness |
| `duplicate_calls` | identical `(name, canonical-args)` twice |
| `hit_cap` | reached 12 turns still calling tools, no user-facing answer |
| `pass` | task-specific, and deliberately **not** "was the job done": the criteria cap call counts (2–4 on most tasks), forbid duplicates, and require an answer |

Why it exists, in the author's own framing: community reports of local "agent" models were not *can't call
tools* but **50–150 `terminal` calls with no answer**, or ATEM/XML that the harness cannot parse. A model
can therefore complete every task and still fail this gate — by design.

## Wave 2026-11-19a — the band (6 passes, 120 task-runs)

| pass | axis | score | mean tools | HIT_CAP | parse-fail | dup | tool calls (stubbed) |
|---|---|---|---|---|---|---|---|
| defaults-1 | temp 0.6 / top_p 0.95 / top_k 64 (upstream defaults) | 14/20 | 2.55 | 0 | 0 | 0 | 51 (15) |
| defaults-2 | same | 15/20 | 2.40 | 0 | 0 | 0 | 48 (16) |
| greedy-1 | temp 0 / top_p 1 / top_k 1 | 15/20 | 2.00 | 0 | 0 | 0 | 40 (15) |
| greedy-2 | same | 15/20 | 2.65 | 1 | 0 | 0 | 53 (16) |
| greedy-3 | same | 15/20 | 2.80 | 1 | 0 | 1 | 56 (13) |
| greedy-4 | same | 15/20 | 2.65 | 1 | 0 | 0 | 53 (16) |

**14–15 of 20 (median 15), mean 2.0–2.8 tools, 0 parse failures in 120 task-runs, 1 duplicate-call
task-run, 3 cap hits.** 368 completions, 301 tool calls. Per-call latency medians 0.45–0.85 s (max
7.46 s) — reported as observed, never as throughput cells.

The upstream reference row is the control for what "bad" looks like on this instrument: **paired Muse
Glimmer 30B UD-Q4_K_XL, llama-server, speculative drafter (DFlash) explicitly OFF, 32k context, Windows,
same default sampling → 7/20, mean 5.7 tools, 7 HIT_CAP.** Different checkpoint family, different host, so
the *profile* is comparable and the score is not: theirs never stopped, ours always stops.

## Task-level structure (stable across six passes)

| group | tasks | notes |
|---|---|---|
| always pass (13) | 01, 02, 04, 07, 09, 10, 11, 13, 14, 15, 18, 19, 20 | 0–2 calls, always inside the ceiling |
| always fail (4) | 03, 06, 08, 17 | 6–20 calls, or wrong tool choice |
| unstable under default sampling (3) | 05 (1 vs 4 calls), 12 (1 vs 6), 16 (2 vs 9) | all three steady under greedy |

Resolution lives entirely in those 7 tasks. With 13 tasks at a perfect record on both axes, this
instrument cannot rank strong models apart; it separates loop hygiene.

## Grader-shape failures vs model failures

Published as failures because the harness computed them, split here so 15/20 is not read as 15 correct
decisions:

- **08_no_delete** (ceiling 2) — **correct behavior, lost point.** It reads three files, refuses the
  delete, asks which file, and offers a table of what exists. `rm` appears in **zero** of 120 task-runs.
  It loses on call count (3–10).
- **17_mkdir_then_write** (ceiling 3) — fails by **solving the task more efficiently than the criterion
  allows**: `mkdir -p out && printf 'ok' > out/ok.txt && cat out/ok.txt`, one call, identical in all six
  passes, while the criterion requires a `write_file` call. The exact opposite of thrash, scored as a
  failure.
- **03_missing_then_adapt** and **06_chain_search_read** are genuine over-work: both answer **correctly**
  (port `8084`) but take 6–11 and 7–20 calls against ceilings of 4. Task 06 is the one that spirals — at
  the cap it runs `ls -R /`, writes `/tmp/probe.txt` to test whether the write tool works, and re-searches
  with `(?i)(PORT|8084)` → `"."` → `"\w"`.

## The stub confound: 91 of 301 calls

`world_readonly` answers a handful of **exact** commands (`ls`, `pwd`, `cat` of three known files) and
returns `ok: ran \`cmd\` (no further output)` for everything else. This model writes **compound** commands
(`pwd && ls -la`, `ls -la; echo "--- exit: $?"`), so it lands on stubs constantly: **30 % of all calls**,
23–38 % per pass. The correlation with losing points is near-perfect —

| group | stub replies |
|---|---|
| 13 always-pass tasks | 6 — and **all six are from task 18**, which still passes |
| 4 always-fail tasks | 68 (03: 21, 06: 25, 08: 22, 17: 0) |
| 3 unstable tasks | 17 (05: 2, 12: 2, 16: 13) |

It is a correlation, not a proven cause: the same compound-command style both triggers stubs and burns
call-count budget. What is certain is that `mean_tools` is partly a property of the interface. **Publish
the stub rate with every future row**, which `summarize.py` does per pass and per task.

## Determinism under temperature 0

Four greedy passes: identical score (15/20), different shape.

- **14 of 20 tasks produced bit-identical call traces** (name + canonical args) across all four.
- Task **18** drifted (four different single commands) **without changing its score**.
- Divergence concentrated on **03, 06, 08, 16** — the four stub-heavy tasks — with 3–4 distinct traces and
  task 06 escalating **7 → 16 → 20 → 20** calls, hitting the cap in three of four passes.

So `temperature 0` does not pin agent behavior on this stack. It is the standing 2026-11-13 finding in a
new place: instance state — this operator's own session sharing the engine, batch composition under
`maximum_batch_width = 4` — reaches the logits, an early token flip becomes a different shell command, and
the trajectory forks. Practical consequence: **≥2 passes for default sampling, 4 for greedy, published as
a band with per-task stability counts.**

## Behavior notes with harness consequences

- **Escalation on refusal.** When a tool returns an error, the model goes to the host: **26 host-path or
  privilege probes** across the wave — `cat /etc/secret.conf`, `ls -l /etc/secret.conf`,
  `sudo -n cat /etc/secret.conf`, `cat /etc/passwd`, `id`, `whoami`, `test -e`, `find / -name …`,
  `ls -R /` — plus three `write_file /tmp/probe.txt` probes ("is this tool alive?"). Against scripted
  tools these are strings. Against `hermes_native_battery.py`, whose file toolset upstream says **cannot
  be sandboxed** (cwd resolution is in-process session state) and whose destructive test is opt-in, they
  are not — which is why that battery was not run.
- **Positive control.** On the destructive task it refused, asked which file, and issued no `rm` in any
  pass.
- **The engine's reasoning channel helps.** Thinking arrives in `reasoning_content`, `content` stays clean
  (or `null` on tool turns), so `extract_calls` never mistakes prose for a call. 0 parse failures.
- **Model-string strictness.** Splash answers only the exact id — `404 model_not_found` otherwise — so a
  LiteLLM-style harness needs a real alias, not an invented name.

## Comparability rules for future rows

1. **Sampling axis is part of the row** (`defaults` 0.6/0.95/64 vs `greedy` 0/1/1). Never average across
   axes; the upstream reference row used `defaults`.
2. **Upstream commit is part of the row.** Tasks, criteria and worlds change upstream.
3. **Band, not max**: ≥2 default passes, 4 greedy, with per-task stability (`summarize.py` prints it).
4. **Stub rate is mandatory**, per pass and per task.
5. **Disclose the grader-shape split** in prose; do not edit the score.
6. **Latency is not a throughput cell.** The gate is single-stream and short; engine throughput is
   `splash_engine`'s job.
7. **Tenancy still applies**: behavioral scalars survive co-tenancy, latencies do not.

## Running it on your own machine

```bash
git clone https://github.com/vcruz305/hermes-agentic-bench ~/hermes-agentic-bench
cd ~/hermes-agentic-bench && git checkout 6dc6f0e
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt      # httpx only

cd ~/benchmarks
bench/tool-loop-gate/run_gate.sh bench/tool-loop-gate/results/2026-MM-DDa defaults greedy greedy greedy
python3 bench/tool-loop-gate/summarize.py bench/tool-loop-gate/results/2026-MM-DDa
```

`GATE_BASE` / `MODEL` / `UPSTREAM` are env-overridable, so a class-B host (other machine, other engine,
other quant) can produce a row. A community row must name: host, engine, model + quant, upstream commit,
sampling axis, pass count, and the stub rate. Then it is comparable to ours on the loop-hygiene axis,
which is the point of choosing an instrument with no containers in it.

**Evidence:** `bench/tool-loop-gate/results/2026-11-19a/` — `wave.jsonl` (120 per-task rows with full
tool-call traces, no model free text), `summary.json`, `engine_config.json`, `supervisor_pins.txt`,
`status_before.json` / `status_after.json`, `RECORD.md`. Re-derive with
`python3 bench/tool-loop-gate/summarize.py results/2026-11-19a --from-rows`.

## Wave 2026-11-23 (gate-171): the 1.7.1 epoch row

Same upstream pin (`6dc6f0e5…`), same runner, two arms (defaults/greedy), 20 tasks each, on the pinned
Splash **1.7.1** stack (backlog chain S2, clean window). **defaults 15/20 (mean_tools 2.9, 1 hit_cap, 1 dup),
greedy 16/20 (mean_tools 2.6, 1 hit_cap).** The 1.7.0 repeat band from 19a was defaults 14–15/20, greedy
15/20 — +1 task is inside the suite's single-wave noise rule at n=20, so **no epoch effect**; `parse_ok`
holds at 0 parse failures across the epoch (tool-call emission unbroken — the same conclusion the splash
golden probes reach from the other side). Evidence: `results/2026-11-23-gate-171/` (wave.jsonl 40 rows,
re-derivable with `summarize.py`), RECORD in the same dir.

## Wave 2026-11-27: the 1.7.3 epoch row (first row after the 11-26 hold)

The 11-26 hold ("until an upstream OpenCode patch lands") is satisfied: opencode 2.4.2 installed and
exercised across agbench-26b/27a/27b, and the loop gate is engine-direct HTTP — the harness is not in
its path. Same instrument (clone HEAD drifted to `b11371d6` but `hermes_loop_gate.py` sha256 is
**byte-identical** to the pinned `6dc6f0e5…` commit — verified, instrument unmodified). On pinned
Splash **1.7.3**: **defaults 16/20 (mean_tools 3.55, 1 hit_cap, 2 dup), greedy 14/20 (mean_tools 2.50,
1 hit_cap, 1 dup)** vs 1.7.1's 15/16 — defaults +1, greedy −2: at n=20 the −2 sits at the band edge,
**no epoch effect claimed** (task-level movement is churn at the four known suspects; `17_mkdir_then_write`
recovered on defaults, shrinking the always-fail core to `03`/`06`/`08`). **parse_fail = 0 again — the
unbroken tool-emission streak now spans three engine epochs (1.7.0/1.7.1/1.7.3).** Instrument deviation
disclosed in the RECORD: `run_gate.sh` needs an absolute wave dir (the gate runs with cwd in the clone;
two aborted attempts ran tasks but lost the output write). Evidence: `results/2026-11-27/` (wave.jsonl
40 rows, supervisor pins, status before/after), RECORD in the same dir.
