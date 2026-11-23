# splash-concurrency — the engine suite (ladder · KV volume · depth)

What this suite measures on the local Splash engine, and the rules each wave follows. Every published number here
comes from one of these entry points; if a claim is not produced by a script in this directory, it does not belong
in the leaderboard.

## Entry points

| script | what it answers | published waves |
|---|---|---|
| `ladder_kv.py` | the sealed two-stage run: width ladder (1→32, 512-token outputs, 2 rounds/width, stop within 10 % of w1) + KV pressure by summed volume (widths 2→12, ~20 k-token prompts, 8-token outputs) | 11-06 · 11-10s · 11-13 · 16b · 11-17 · 11-18 · 19-ext |
| `kv_bracket_2026-11-19b.py` | the same two stages **past the 32-request cap**: reads the live `--queue-size` and refuses to start if the top width would self-saturate; refusals are recorded as data, not raised; prompts in a fresh seed namespace with per-round cache-served validation; stage 0 warmth gate on the ladder's own primitive | 19b · 19c-clean |
| `depth_probe.py` | the other axis: **one** conversation grown turn over turn across the resident KV line toward the context window, `max_tokens 8`, unique blocks per turn; `--sample-interval` adds an intra-turn occupancy sampler (the fine pass) | depth-2026-11-19 · depth-fine-2026-11-19 |
| `tenancy_repro.py` | the 16b open-cause test: same KV ladder twice, arm B adds 3 continuous ~128k-tok co-tenant sessions; both arms deadline-bounded, stop-on-trip | tenancy-2026-11-20 |
| `run_tenancy_detached.sh` | the tenancy A/B in a bounded, attributed window | tenancy-2026-11-20 |
| `run_clean_detached.sh` | runs `kv_bracket` in a window the operator can claim is single-tenant, then **proves** it by request attribution | 19c-clean |
| `run_depth_detached.sh` | the same discipline around `depth_probe.py` | depth-2026-11-19 |
| `engine_probe.py` · `width_ladder.py` · `width512.py` · `kv_pressure_v4.py` | the sealed primitives, kept for provenance | — |
| `engine_fingerprint.py` | **version transitions**: hash the install tree + `/status` + `/metrics` series + the running supervisor's argv, then `diff` two captures with runtime counters suppressed. The method, committed — the 5.3.1→5.3.3 MCP pair was captured with ad-hoc greps nobody could re-run | 1.7.0 pre / 1.7.1 post, Tier 0+1 complete (2026-11-23) |
| `golden_probes.py` | did a version move the engine's **behaviour**: 13 fixed requests, `kind`-typed (`byte` byte-compared, `grammar` payload-compared, `timing` usage-only), each run twice so the within-build floor is measured before any cross-build claim | both epochs: epoch behaviourally silent on byte/grammar probes (2026-11-23) |

## Rules (each one is here because a wave broke it)

1. **Flags bind at launch, so pins come from the running supervisor.** `pgrep -f -fl server.server`, never the
   `start.sh` on disk — a supervisor older than the edit still runs the old values. Restarting to make a flag bind
   **zeroes every lifetime counter**, which makes a row's per-round deltas pristine but makes its lifetime column
   non-comparable to earlier waves. Say which case you are in.
2. **Report window deltas, never lifetime reads.** A counter can drift outside the stage you are measuring (11-18
   entered its KV stage with 43 suspensions already banked). Every stop rule here reads deltas.
3. **A prompt reused from an earlier wave is not a measurement.** Deterministic prompts plus `--persistent-cache`
   means a "pressure" round can be served from disk: 612,180 tokens in 1.5 s with `prefill_rows` moving 84. Each
   round must show `scheduler.prefill_rows` delta **equal to** its prompt tokens, or it is marked `cache_served`
   and excluded (19-ext lost two stitch controls this way).
4. **Refusals are data, and there are two kinds.** The old `chat()` raised on non-2xx and killed a driver mid-wave.
   Record the code and body. Then tell them apart with one gauge: `400 context_length_exceeded` with
   `prefill_rows` unmoved is **request validation** (never admitted); `503 frontend_overloaded` is **capacity**
   (`--queue-size`). Fixing the first is the caller's job; the second is the stack's.
5. **Volume and depth are different subsystems.** Pushing many long requests at once never touches the KV pool:
   width becomes scheduler queue depth and `pages_active` pins at 0.39× budget at 17.04× offered volume
   (19c-clean). Growing **one** context crosses the resident line and spill switches on immediately, while the
   real wall turns out to be the context window (1.64× resident served fine; depth-2026-11-19). A wave that
   reports only one axis cannot answer questions about the other.
6. **Suspension is the wrong gauge on this stack.** The governor answers KV pressure with **spill and disk
   demotion**; a stop rule that waits for `admission.suspended` watches a gauge this build does not use. Watch
   refusals, `spill_moves`, `kv_demotions*`, `capacity_failures` — and `admission.*` only to prove what it does
   **not** show (past 32 in flight, all four admission queues peak at 0 while `queued` climbs to 47).
7. **Prove tenancy by attribution, not by size.** A >20k-prompt-token threshold labelled a clean wave "NOT
   single-tenant, 6,851 samples" — those were the wave's own 55k-token KV prompts. Attribute in-flight requests by
   the prompt sizes the run itself recorded, and print the verdict. Run detached, sample `/status` at 10 s, and
   leave a **90 s lead-in**: the operator's own last message is still being decoded on this engine when the run
   starts, because the operator session is served by that engine.
8. **Warm the engine on the primitive you are about to certify.** 19-ext's gate probed a prose paragraph
   (77–117 tok/s) while the ladder's own w1 read 294.4, so it licensed nothing. On this engine the gate's spread
   on the ladder primitive lands at **1.138 (19b)** and **1.144 (19c)** — quote the band and the "soft" label;
   do not chase the ≤1.10 pass.
9. **Diff across waves on w1 and the plateau only.** Mid-width singles do not reproduce even on the same launch
   (19b vs 19c-clean: w2 417.0 vs 487.05, w12 647.55 vs 694.4). Shape invariants that do reproduce: the w6 dip,
   the admission ceiling (12), and the flat prefill rate that `maximum_batch_width = 4` implies.
10. **Zero operator engine calls for the whole window.** The agent session is served by the engine being
measured: every operator message and tool call is co-tenant load. A 90 s lead-in protects only the pre-launch
message — after launching a detached wave, **end the turn and do not return until the completion notification**.
Earned the hard way: the 2026-11-19 tenancy run contaminated its own "clean" arm (operator requests of 79k–83k
tok decoded inside the only recorded round) and then deadlocked a continuous co-tenant against `wait_idle()`
for **15 h 45 m**, moving lifetime `spill_moves` by +3.1 M (`results/tenancy-2026-11-19-runaway/RECORD.md`). A
measurement script must carry a hard deadline; the harness must never assume the operator stayed idle.
11. **Match the sampling interval to the event.** The depth probe sampled at 10 s and caught `pages_active = 0` at
    every sample, because each turn completes in ~7 s. The spill deltas carried the residency finding; an occupancy
    curve needs 1–2 s sampling.
12. **A byte claim needs a byte-stable probe, and prose is not one.** The 1.7.1 transition baseline showed the same
    prose request at `temperature 0` answering differently run to run (`finish=stop`, 114 vs 146 completion tokens) —
    the same floor the τ² same-seed pair measured at 0/238 transcripts. So `golden_probes.py` types its probes:
    `byte` (short greedy / tool-call, byte-compared), `grammar` (compared as parsed payload, because a grammar leaves
    an optional `"flags": []` free and a byte hash calls that a version effect), `timing` (usage and latency, no byte
    claim). Reasoning is hashed separately everywhere: 1.7.1 shifts reasoning length by design, so a combined hash
    would report change on every probe.

## Records

`results/<wave>/` — each has the raw `.jsonl` rows plus whatever the runner captured (`pins.txt`,
`status_before/after.json`, `engine_samples.jsonl`, `run.out`/`run.err`, `RECORD.md`). Absolute local paths are
scrubbed to `~`. The engine is **not** restarted between waves unless a flag has to bind; that is stated in each
record because it changes what the lifetime column can mean.

## Reading order for a new engine version

`engine_fingerprint.py capture` **before the install** and again after it (`diff` prints the structural delta), then
`golden_probes.py` on both sides and `golden_probes.py compare` — that pair decides whether new rows may be compared
against published ones at all. Then:
`ladder_kv.py --quick` (harness smoke, never baselining) → `run_clean_detached.sh` (ladder + KV volume, provable
window) → `run_depth_detached.sh` (depth) → compare **w1, plateau, spill onset, refusal mode** against the newest
rows in `../../docs/splash-engine-benchmark-results.md`. Worked example: `PLAN-splash-transition-1.7.1.md`.
