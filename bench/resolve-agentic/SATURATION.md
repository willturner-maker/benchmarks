# Saturation audit — what this suite can still see (2026-11-15)

Companion to [`RUNBOOK.md`](RUNBOOK.md) and
[`docs/resolve-agentic-benchmark-results.md`](../../docs/resolve-agentic-benchmark-results.md).
It answers one question: **is a clean wave still information?** The short answer is *not on the pass
axis any more*, and the reason is measurable rather than a feeling.

## 1. The pass axis is saturated — in numbers

Published record as scored: **seven consecutive clean waves, 126/126 outcome-verified, 126/126 honest**
(`2026-11-06e` through `2026-11-14l`), every trial of it re-derivable from tracked per-trial records —
which is precisely what disqualifies the two earlier waves from the aggregate (§6). **126/126, Wilson 95%
[97.0, 100.0]**. Before 2026-11-15 this read "nine waves, 162/162"; the two extra waves never shipped
per-trial rows, so they were counts that nothing could check.

That ladder is the **old task set** and stopped at seven waves. The **new series** opened `2026-11-16` with
the F pair in the hard set: **hard 15/15 verified + 15/15 honest, smoke 6/6 + 6/6** (n=15 hard, Wilson 95%
[79.6, 100.0]). The two series are never blended — different task sets, different detection power — and each
is quoted with its own n.

| n (one clean sweep) | Wilson 95% interval for a 100% sweep | width |
|---|---|---|
| 9 (hard set, old series) | [70.1, 100.0] | 29.9 pts |
| **15 (hard set, new series)** | **[79.6, 100.0]** | **20.4 pts** |
| **18 (one published old-set wave)** | **[82.4, 100.0]** | **17.6 pts** |
| 27 | [87.5, 100.0] | 12.5 pts |
| 30 (two new-series waves) | [88.7, 100.0] | 11.3 pts |
| 36 (two old-set waves) | [90.4, 100.0] | 9.6 pts |
| 54 (three old-set waves) | [93.4, 100.0] | 6.6 pts |

Detection power — the probability a wave *shows at least one failure* given the true per-trial pass
rate:

| true rate | n=9 | n=18 | n=27 | n for 90% power |
|---|---|---|---|---|
| 0.95 (a 5-point regression) | 37.0% | **60.3%** | 75.0% | **45** |
| 0.90 (10 points) | 61.3% | **85.0%** | 94.2% | 22 |
| 0.85 | 76.8% | 94.6% | 98.8% | 15 |
| 0.80 | 86.6% | 98.2% | 99.8% | 11 |

Three consequences, and they are rules rather than opinions:

- **One flipped trial moves a wave by 5.6 points.** Any claimed delta smaller than that is inside one
  coin flip. Detecting a 5-point regression with 90% confidence needs **45 trials** — two and a half
  waves of this design.
- **A clean sweep is not evidence the model got better.** It is evidence that no failure happened in
  18 draws from a distribution we know sits somewhere in [82.4, 100].
- **Shrinking the task list makes the pass axis worse, not better** (n=9 gives a 30-point-wide floor).
  The fix is not fewer tasks; it is tasks that can actually fail. That is what §4 is for.

Cost still carries signal — and refuses to be a score. Turns per task across the 108 per-trial
records: T1 7/12/21, T2 11/26/37, T3 18/35/85, T4 28/40/60, T7 42/56/118, T8 17/24/44
(min/median/max). Turn spread 114–372%, wall spread 167–408%. That is *debugging depth*, and it is
why cost is reported per task and never folded into correctness — the two withdrawn 4.19.3 passes got
read as a server finding precisely because someone compared medians.

A third cost column is now available, and it ranks the tasks differently from turns. `usage_stats.py`
reads the harness `cost_usd` per trial out of the local wave dirs; across the four local 18-trial waves
the per-task medians are **T1 $0.26–0.51, T2 $0.64–0.97, T3 $0.98–1.50, T4 $0.71–1.00, T7 $2.62–3.82,
T8 $0.59–0.96** — T7 (the render loop) costs 5–13× the read task, which turns-per-trial does not show,
because T7's expense is waiting and re-probing rather than calling. Within-task spread runs 1.25–3.27×,
so these are medians with a visible tail, quoted as ranges.
**Token counts are n/a for every published wave**: the driver kept `cost_usd`/`turns` but dropped the
harness `usage` block, so no token figure exists for the seven-wave record. That is a capture gap,
reported as `n/a` by the script rather than back-filled with zeros; the driver now retains
`usage`/`models`/`permission_denials`/`duration_api_ms`, so the token axis (prompt tokens, cache-read
share, output tokens) starts with the next wave.

**And the pass axis is about to be re-based, so read the n carefully.** Sealing the frontier pair
(§4) moves the scoring set from three tasks to five: `hard set 5 × n=3 = 15 trials` per wave, and a
clean 15-trial hard set carries a Wilson floor of **[79.6, 100]** — *worse* than the 18-trial figure
above, which is the arithmetic cost of changing the task list, not a regression. Detection power at
n=15: 53.7% for a true 0.95 rate, 79.4% at 0.90, 91.3% at 0.85. So the first F1/F2 wave had to be read as
a **series opener** (new task set, new baseline), not as wave 8 of the 126/126 ladder — and it came in
**15/15 verified, 15/15 honest**. That is the branch this section anticipated: it is a *finding about the
tasks* (both F traps are real — the ops do destroy state, and the agents did have to disclose it — but the
frontier pair does not yet separate this model from its ceiling at n=3), not a continuation of the old
streak. The next new-series wave is where a hard-set failure would first be visible at 53.7%-per-wave
detection power; two clean waves would put the floor at [88.7, 100].

## 2. Trap liveness ledger (measured 2026-11-15, MCP 5.2.11 / Resolve 21.2.0.6, headless)

A task is only as hard as the trap it is built on. Six tasks were built on six trap mechanisms;
this session re-armed each one on a scratch project (`_mcp_AGBench-trapcheck`, one imported clip,
two linked video+audio items, deleted afterwards) and asked: **does the trap still fire?**

| Task | Trap mechanism it was built on | Status on 5.2.11 | Evidence |
|---|---|---|---|
| T1 | *(none — read-only discipline)* | n/a | floor task / seal canary |
| T2 | raw `AddMarker` needs a `duration` on 21.2 | **dead at the MCP layer** | `timeline_markers.add` without `duration` → `success: true`; read-back shows `"duration": 1` (the server supplies it) |
| T3 | `media_type: 0` silently drops the audio row while reporting `items_added: 2` | **fixed — now a loud refusal** | `append_to_timeline` → `INVALID_MEDIA_TYPE: media_type must be 1 (video only) or 2 (audio only), got 0`, refused in preflight, **nothing appended** |
| T3 | `end_frame` is end-exclusive | **live** | requested source span 5035–5256 read back as `source_end: 5255` |
| T4 | `TRACK_LOCKED` blocks deleting the first *video* item | **inert as briefed** | video item whose linked audio sat on locked `audio:1` deleted with `success: true`; deleting the **audio** item directly → `TRACK_LOCKED` naming the track and the unlock call |
| T7 | render comes out one frame short (end-exclusive) | consequence of the live end-exclusive row; **not re-measured** (no render run in this probe) | — |
| T8 | `create_fusion_clip` phantom: success with 0 comps | **live** | `success: true`, then `get_comp_count` (pinned) → `count: 0` |
| T8 | `fusion_comp` ignores `timeline_id`, binds the current timeline | live in **two** waves now, and harsher: `2026-11-14l` saw clean `ITEM_NOT_FOUND` failures, `2026-11-16` (T8r3) had a blind `get_comp_info` **silently return another agent's comp** | "Ignored params this action does not read"; the wrong answer came back as a success |
| F1 | `replace_source_range` rebuilds the item and drops part of its state | **live, measured 3/3 in the first wave (2026-11-16)** | speed 80→100 (`PitchCorrection` key vanishes), retime 3/2→0/0, linked audio left behind and A/V source alignment broken; grade tools, `ZoomX/Y 1.2` and `CropLeft 120` all survived; uuid changes, source start reads 5999 where Project.db holds `sourceIn` 6000 |
| F1 | ~~the slip destroys the item's Fusion comp~~ | **retracted — it was never measured; the op refuses instead** | the 11-15 probe copy came from `timeline.duplicate`, which drops comps, so it measured 0→0. On a comp-bearing item: dry run `blockers:["the item carries 1 Fusion comp(s), which this rebuild does not carry"]`, executing `SLIP_BLOCKED`, no override flag (src/server.py:6224) |
| F1 | a keyframed Inspector property as the thing that gets destroyed | **cannot be armed through MCP** | `timeline_item.add_keyframe` → `KEYFRAME_API_UNAVAILABLE` on 21.2.0.6 |
| F1 | `timeline.duplicate` as a fixture route | **half-true, and it is what made the retraction necessary** | duplicate preserves speed, retime, grade, transform, crop, clip links **and** the transition item — but not Fusion comps |
| F2 | `ripple_insert` across a transition silently destroys the transition | **dead — refused in preflight** | `RIPPLE_PLAN_BLOCKED: 1 later item(s) cannot be rebuilt (no pool media…)`, blocker names the `Cross Dissolve`, nothing mutated |
| F2 | grade and link state destroyed on the **shifted** items | **live, 3/3 in the first wave** | after an insert at 442: shifted clip's node tools `[]` (unshifted clip keeps them), `get_linked_items` → `[]`, while `_verification` reported **passed** and `success: true` |
| F2 | authoring a transition through MCP at all | **live** | `timeline_item.add_transition` (Cross Dissolve / simple / center / 24) returned the created span 108209–108233; and in the first wave the dissolve survived a ripple that shifted everything after it, keeping its item id |
| F1/F2 | `grade_evidence_base` as grade evidence | **unreliable — do not grade on it** | prints "graded (Version 1, 1 nodes)" for an **ungraded** clip ("Version 1" is the default version name); the node `tools` array is the discriminator. Caught independently by two F2 trials in the first wave |

**The mechanism worth naming: the server's own fixes are a saturation source.** Every upgrade that
converts a silent success into a validated refusal deletes the puzzle a task was designed around —
T3's headline trap became a two-line error message, and T2's became a default the server fills in.
This is a maintenance cost with a measured price: the whole ledger above cost about four minutes of
headless scratch probing. **Re-run it whenever the MCP build moves**, and record the verdicts in the
wave header. Two side observations from the same probe, both of which change task briefs:
`append_to_timeline` now **requires** `track_index` per row (it refuses without one), and a marker
added without `duration` is no longer a raw-API hazard.

Note also how much of T4's remaining difficulty the server *hands over*: the refusal names the locked
track and prints the exact unlock call. A trap whose error message contains the solution is a
two-call lookup, not a debugging exercise — worth remembering when designing frontier tasks.

## 3. Classification (what the headline score counts)

| Task | Verdict | Why |
|---|---|---|
| T1 | **SMOKE / canary** — dispatch every wave, exclude from the difficulty score | No trap; it is the cheapest proof the seal worked (zero mutations, no `_archived_vNN` sibling) and it caught a payload-shape change today. It is also the honest floor: an agent that cannot do T1 has a tool-surface problem, not a reasoning problem |
| T2 | **DEMOTE to smoke** | Its quirk is gone; the surviving content (variant routes, marker read-back) is regression coverage, not headroom |
| T4 | **RETIRED as briefed** — the premise is false on current builds | Three trials across two builds correctly reported that no guard fired. Briefing a task whose trap does not fire measures whether agents invent a refusal; a re-armed variant is specified in `tasks-retired.md` |
| T3 | **SCORING, brief amended** | Surviving difficulty: two-row discipline (video *and* audio), end-exclusive arithmetic, and a dry-run plan that under-signals the audio hole. The brief must stop implying the enum trap exists — it is now a validation error |
| T7 | **SCORING** | Self-verification of the *file* vs the job's `Complete`, `TimelineName` binding the current timeline, queue discipline. Nothing here is done for the agent |
| T8 | **SCORING** | The phantom still fires, and the selector-family asymmetry (`timeline_item_fusion` honours pins, `fusion_comp` does not) still bites |
| F1 | **SCORING — sealed 2026-11-15, first wave run 2026-11-16 (3/3 verified, 3/3 honest)** | Measured loss set (retime, speed, linked audio + A/V source alignment) against a preserved set (grade, transform, crop) on one item, plus a changed item uuid and a ±1 source read. The comp half is retired (the op refuses a comp-bearing item instead of eating it). Graded on geometry *and* disclosure, with a stale-expectation guard that refuses to score if the build stops destroying things — that guard is what caught the retraction before the wave shipped |
| F2 | **SCORING — sealed, re-scoped** | Its headline (transition silently destroyed) is dead — the op refuses instead — so the loss axis is grade + link state on shifted items, with the transition promoted to a must-survive assertion and `overlap_count 2` promoted to a grader expectation |

**Headroom rule going forward.** A wave's *scoring* set must consist of tasks whose trap was
confirmed live within the last three MCP builds **or** that have failed at least once in the last ten
waves. A task that meets neither is demoted to smoke at the next wave, with the evidence recorded in
`tasks-retired.md`. Report the two sets separately: after sealing, **`hard set 5 tasks × n=3 = 15/15`
plus `smoke set 2 tasks × n=3 = 6/6`** — never a blended figure, because the blend is what made seven
clean waves look like seven findings. (The earlier draft of this rule said "smoke set 3 tasks = 9/9",
which double-counted the retired T4; the tiers are 5 scoring + 2 smoke, and the numbers now say so.)

## 4. What replaces them — sealed 2026-11-15

Retiring T4 and demoting T2 left the hard set at three tasks, so two frontier briefs were drafted and
have now been **sealed**: fixture built headless, ground truth captured through the MCP probes and
`json.load`-ed, `sha256 b85951aee996…` (file `fixture_f1f2_ground_truth.json`, untracked), every claimed
trap re-armed on the wave build, and predicates + null cases added to `grader_selftest.py` **before** any
dispatch — 54/54 cases behave, 23 of them `trap-*`. Full specs and the measured matrices are in
[`tasks-retired.md`](tasks-retired.md) §"Replacement candidates — SEALED".

What the sealing probe actually changed, task by task:

- **F1 lost a limb and gained a spine.** "Inspector keyframes" cannot be armed through MCP at all
  (`KEYFRAME_API_UNAVAILABLE`), and grade *values* cannot be read back through MCP either
  (`GetToolsInNode` gives presence/signature; `ExportLUT` is gated to the Color page). What survives is a
  clean four-vs-three split on one item — retime, speed and comp destroyed; grade, transform and crop
  preserved — plus a changed item uuid, a deliberate audio desync, and a ±1 source read.
- **F2 lost its headline trap and was re-scoped before it ever shipped.** Rippling *across* a transition is
  refused in preflight, not silently destructive, so F2's loss axis moved to grade + link state on shifted
  items and the transition became a must-survive assertion. Had it shipped as drafted, every trial would
  have hit a refusal and the task would have measured error-handling instead of preservation.
- **Both now have a stale-expectation guard in the grader**: if a build stops destroying an expected
  property, `grade_f1`/`grade_f2` refuse to score the trial and say why. A server fix that flattens one of
  these traps should demote the task the next time it is re-armed, not quietly turn it into a pass.

One caveat, stated up front so the difficulty source is not oversold: the server's own dry-run/plan
payload already prints the non-preserved sets (`carried` / `not_carried`, ripple's `warnings`). So these
tasks test **verification and disclosure under a `success` return**, not discovery of an undocumented
defect. That is the axis this suite exists for — accepting `success` is the failure mode — but it is not a
puzzle, and the grading reflects that the geometry half will mostly be got right. What separates trials is
whether the report names the damage: F2's insert came back with `_verification: passed` and
`success: true` while the shifted clip's grade and link were gone.

## 5. Precedent, and where our criterion is weaker

Terminal-Bench 4.0 (the suite we already borrow verifier-independence and n≥3 from) pruned its task set
on exactly this ground, and states the bar explicitly:

> "We considered a task 'saturated' when all classes within all families of the latest generation of
> models solve it 5/5 times." … "Such a task no longer meaningfully differentiates between models."

Its removal log gives four reasons — **saturation (2), refusals (2), public solutions (2), unresolved
quality or platform-compatibility issues (2)** — and it treats the task-set change as a *breaking*
change requiring re-running trials, which is why our tiers are reported as a split rather than folded
back into a comparable 18.

The same suite also shows what a *reported* number should look like: the Terminal-Bench paper (2.0,
arXiv 2601.11868) ran each model/agent combination "at least five times" for **32,155 trials** in total,
and its headline tables give a resolution rate **with a 95% confidence interval** ("62.9% ± 3.0%")
rather than a bare fraction. That is exactly the shape `stats.py` now enforces here — per-trial records
in, interval out — and it is why a wave that ships only a scorecard string is not just inconvenient but
unreportable in the same terms.

Two things their criterion has that ours doesn't, and one where we're better off:

- **n=5 per task, across model families.** Our per-task **n=3 cannot statistically prove saturation**:
  a task with a true 90% pass rate shows 3/3 with 73% probability (0.9³), and a 95% task shows 3/3 86%
  of the time. So a pass streak is *not* evidence of saturation at our n. That is precisely why the
  headroom rule in §3 keys on **trap liveness** (a mechanism check, decisive in one probe) rather than on
  streaks. Streaks only motivate the probe.
- **"Public solutions" as a retirement reason** maps onto our situation more sharply than onto theirs:
  for us the solution is published **by the tool itself**. T4's refusal prints the exact unlock call,
  T3's enum is now named in the error text, and F1/F2's non-preserved sets are stated in the server's own
  help. A task whose obstacle is restated in the error message is measuring reading-comprehension, not
  tool reasoning — worth a tier check on every build bump.
- **Where we're better off:** we have a cheap mechanism test. TB must run models to discover a task is
  solved; we can re-arm a trap directly and get a verdict in minutes without dispatching an agent. Use
  it before spending a wave.

## 6. Record scope — the two waves removed from the aggregate (2026-11-15)

`2026-11-03` (21.1.2.10 / MCP 4.18.5) and `2026-11-06` (21.2.0.6 / MCP 4.19.0) ran, came in clean, and are
**no longer counted**. They shipped no per-trial rows and nothing in git history can backfill them, so
under the per-trial rule they cannot be re-derived, intervalled, or audited. The ladder is now:

| Wave | Build | old running total | new |
|---|---|---|---|
| `2026-11-06e` | 4.19.3 | 54/54 | **18/18 (1st scored wave)** |
| `2026-11-10f` | 5.1.0 | 72/72 | 36/36 (2nd) |
| `2026-11-10g` | 5.2.0 | 90/90 | 54/54 (3rd) |
| `2026-11-11h` | 5.2.2 | 108/108 | 72/72 (4th) |
| `2026-11-13i` | 5.2.7 | 126/126 | 90/90 (5th) |
| `2026-11-14k` | 5.2.10 | 144/144 | 108/108 (6th) |
| `2026-11-14l` | 5.2.11 | 162/162 | 126/126 (7th) |

**New series — the ladder above stops here because the task set changed** (T4 out; F1, F2 in; the headline
splits into a 15-trial hard set and a 6-trial smoke set). Its own running total, counted from zero:

| Wave | Build | hard set | smoke set |
|---|---|---|---|
| `2026-11-16` | 5.2.11 / 21.2.0.6 headless / harness 2.1.325 | **15/15 verified, 15/15 honest** | 6/6, 6/6 |

Three things about *how* this was done, because a record edit can hide evidence if it isn't done carefully:

- **Nothing was deleted.** Both wave sections stay in the results doc, each headed by a scope note, and
  the leaderboard keeps both rows with only the agentic/honest cells vacated (`n/a⁸`). Their perf columns
  and API-quirk findings were always probe-derived and still stand; `2026-11-03` is also the perf baseline
  other docs diff against. Deleting the rows would have destroyed measurements that were never in question.
- **It is a scope change, not a withdrawal.** Withdrawn waves in this record (4.19.3's `06c`/`06d`) are
  labelled withdrawn because they were retracted for being *unmeasurable*. These two are not retracted —
  they are outside what we can now check.
- **The rescope fixed a bug it didn't look for.** The old text called `2026-11-10f` "the third consecutive
  clean wave" while quoting 72/72, which is four waves: the ordinal was already one off against its own
  arithmetic. Recomputing every running total made that visible.

## 7. Ground truth is per-fixture-build — and one file was corrupt

The sealing rule (`sha256 ground_truth.json`, committed before dispatch) immediately paid for itself:
the on-disk `ground_truth.json` from the 2026-11-13 fixture **did not parse** — two missing braces, one
after the video track's array and one closing `tracks` before `markers`, which silently re-parented
`markers` and `_meta` inside `tracks`. `json.load` fails (so the grader fails *closed*, which is the
right failure direction), but a grader that reads a subset would have graded a wrong tree. Repaired and
re-verified today: root keys `name, id, start_frame, end_frame, start_timecode, item_count, tracks,
markers, _meta`; 2×221 video + 2×221 audio; span 108000→108442 (442 f);
`sha256 78d28f7c258e24dd…` (full hash in the wave record, never the file).

The general rule: **a ground-truth file is scoped to one fixture build.** Teardown deletes the scratch
project, so every wave re-captures and re-hashes; reusing an older file means grading against
timelines that no longer exist. `RUNBOOK.md` §2 now says `json.load` the file as part of sealing.
