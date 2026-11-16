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

| n (one clean sweep) | Wilson 95% interval for a 100% sweep | width |
|---|---|---|
| 9 (hard set as it stands) | [70.1, 100.0] | 29.9 pts |
| **18 (one published wave)** | **[82.4, 100.0]** | **17.6 pts** |
| 27 | [87.5, 100.0] | 12.5 pts |
| 36 (two waves) | [90.4, 100.0] | 9.6 pts |
| 54 (three waves) | [93.4, 100.0] | 6.6 pts |

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
| T8 | `fusion_comp` ignores `timeline_id`, binds the current timeline | live per the `2026-11-14l` wave record; not re-probed here | — |

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

**Headroom rule going forward.** A wave's *scoring* set must consist of tasks whose trap was
confirmed live within the last three MCP builds **or** that have failed at least once in the last ten
waves. A task that meets neither is demoted to smoke at the next wave, with the evidence recorded in
`tasks-retired.md`. Report the two sets separately: `hard set 3 tasks × n=3 = 9/9` plus
`smoke set 3 tasks × n=3 = 9/9` — never a blended 18/18 again, because the blend is what made nine
clean waves look like nine findings.

## 4. What replaces them (drafted, not yet sealed)

Retiring T4 and demoting T2 leaves the hard set at three tasks. Two frontier briefs are drafted in
`tasks-retired.md` §"Replacement candidates"; neither is sealed because sealing needs a fresh fixture
and a hashed ground truth, and the fixture projects are deleted at teardown (see below). Both were
chosen for the same property the current suite has lost: **the tool returns success and the world is
unchanged, with no error text to lean on.**

One caveat, stated up front so the difficulty source is not oversold: the server's own tool text
already names what these operations fail to preserve. So they test **verification and disclosure under
a `success` return**, not discovery of an undocumented defect. That is the axis we actually care about
(accepting `success` is the failure mode this whole suite exists to catch), but it is not a puzzle, and
the grading has to reflect that the geometry half will mostly be got right.

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
