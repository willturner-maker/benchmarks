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
4. **An agentic cell is admissible only if the wave ships per-trial records** (one row per
   trial: `trial`, `verified`, `honest`, `turns`, `wall_s`, `cost_usd`). A wave that reports only
   `18/18` as prose cannot be re-derived, intervalled or audited later, so it does not enter the
   aggregate. Enforced by `python3 -I stats.py --check`. Two early waves (`2026-11-03`,
   `2026-11-06`) were removed from the agentic record on 2026-11-15 under this rule — see footnote ⁸.

## Resolve MCP — class A media, reference host

Reference host for all rows: Apple M5 Ultra (64-core GPU), 96 GiB unified memory,
macOS 27.2, render output and scratch on external volumes.

| Date | Resolve | MCP | cold render | warm median | warm fps | prepare | verify | set_current | probe | agentic outcomes | honest |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-03 | 21.1.2.10 | 4.18.5 | 3436 ms | 1414 ms | ~85 | 243 | 61 | 127 | 7 | n/a⁸ | n/a⁸ |
| 2026-11-06 | 21.2.0.6 | 4.19.0 | 3090 ms | 1296 ms | 93.4 | 126 | 39 | 98 | 11 | n/a⁸ | n/a⁸ |
| 2026-11-06b | 21.2.0.6 | 4.19.2 | 1668 ms¹ | **1196 ms** | 101 | 162 | 50 | 97 | 11 | n/a² | n/a |
| **2026-11-06e** | 21.2.0.6 | **4.19.3** | 1670 ms | **1191 ms** | **101.6** | 174 | 41 | 109.5 | 18³ | **18/18** | 18/18 |
| **2026-11-10f** | 21.2.0.6 | **5.1.0** | 3116 ms¹ | **1198 ms** | 101.0 | 183 | 47.5 | 112 | 20³ | **18/18** | 18/18 |
| **2026-11-10g** | 21.2.0.6 | **5.2.0** | 1700 ms¹ | **1296 ms** | 93.4 | 162 | 59 | 112 | 268³⁴ | **18/18** | 18/18 |
| **2026-11-11h** | 21.2.0.6 | **5.2.2** | 3129 ms¹ | **1205 ms**⁵ | 100.4 | n/a⁵ | n/a | n/a | n/a³⁴ | **18/18** | 18/18 |
| **2026-11-13i** | 21.2.0.6 | **5.2.7**⁶ | 1303 ms¹ | **1192 ms**⁶ | **101.5** | 155⁶ | 35 | 80 | 13³⁶ | **18/18** | 18/18 |
| **2026-11-14k** | 21.2.0.6 **headless**⁷ | **5.2.10** | —⁷ | **1310 ms**⁷ | 92.4 | 116 | 44 | 83 | 11³⁷ | **18/18** | 18/18 |
| **2026-11-14l** | 21.2.0.6 **headless**⁷ | **5.2.11** | —⁷ | **1207 ms**⁷ | **100.2** | 117 | 46 | 84.5 | 12³⁷ | **18/18** | 18/18 |
| **2026-11-16** | 21.2.0.6 **headless**⁷ | **5.2.11** | —⁹ | —⁹ | —⁹ | —⁹ | —⁹ | —⁹ | —⁹ | **15/15 hard⁹** | 15/15⁹ |
| **2026-11-16b** | 21.2.0.6 **GUI**¹⁰ | **5.2.11** | —¹⁰ | —¹⁰ | —¹⁰ | —¹⁰ | —¹⁰ | —¹⁰ | —¹⁰ | **14/15 hard¹⁰** | 14/15¹⁰ |
| **2026-11-16f** | 21.2.0.6 | **5.3.0** | —¹⁴ | —¹⁴ | —¹⁴ | —¹⁴ | —¹⁴ | —¹⁴ | —¹⁴ | **21/21¹⁴** (hard 15/15 + smoke 6/6) | 21/21¹⁴ |
| **2026-11-17g** | 21.2.0.6 | **5.3.0** | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | **16/18 both arms¹⁵** (xhigh vs injected medium) | 16/18 both arms¹⁵ |
| **2026-11-17h → 17h2** | 21.2.0.6 | **5.3.0** | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | —¹⁵ | **20/21 → 21/21¹⁵** — the new working ceiling | matched¹⁵ |
| **2026-11-18k** | 21.2.0.6 | **5.3.3** | —¹⁶ | —¹⁶ | —¹⁶ | —¹⁶ | —¹⁶ | —¹⁶ | —¹⁶ | **40/42¹⁶** (friction wave — the naming rule did not ship) | **42/42¹⁶** |
| **2026-11-18l** | 21.2.0.6 | **5.3.3** | —¹⁷ | —¹⁷ | —¹⁷ | —¹⁷ | —¹⁷ | —¹⁷ | —¹⁷ | **F3 n=6: 6/6 geometry; split 0 preserved-native / 6 repaired¹⁷** | 6/6¹⁷ |
| **2026-11-18m** | 21.2.0.6 | **5.3.4**¹⁸ | 1651 ms¹ | **1174 ms**¹⁸ (best on host) | 103.1 | 168 | 45 | 135 | 24 (4-item)¹⁸ | **F3 n=6: 6/6 geometry; split 0 preserved-native / 6 repaired¹⁸** | 6/6¹⁸ |

Render probe: 121 frames, 3840×1520, mov/H.264, queue time excluded
(`TimeTakenToRenderInMs`, file verified with ffprobe). Op columns are server-side
operation medians in ms.

¹ Cold ms is **host state, not an MCP signal** — the community server never touches the
render path, and the cold column has swung 3436 / 3090 / 1668 / 1670 / 3116 / 1700 across six
waves of identical media and settings. Read only the warm column. Warm 1196 (4.19.2)
equals the best prior mark; 5.1.0's 3116 ms cold is the same host-state caveat.
² No agentic n=3 for 4.19.2: the bump was behaviour-free (upstream fix of the CLAP
audio-embedding bug we filed, verified by direct probe the day it shipped).
³ The `probe` column is measured on **base geometry (4 items)**, and `probe_timeline_structure` is
item-count sensitive: quantified by the 2026-11-13 sweep as `ms ≈ 3.0·items + 1` on 5.1.0/5.2.7 and
`ms ≈ 2.0·items + 5` on 4.19.3 (4 items → 13/13/14.5 ms; 8 → 25/26/24; 16 → 49/49/34). Comparisons
across rows are only valid at the same item count.
⁴ The probe column can also pick up a **context-switch cost**: consecutive pinned calls that *alternate*
timelines trigger a baseline_reset/restore lifecycle — 265–1113 ms measured in the 5.2.0 wave, and
**~120 ms on every build tested in the 2026-11-13 sweep (4.19.3 / 5.1.0 / 5.2.7)**, so this is not a 5.2.0
introduction; the 5.2.0 cell just happened to sit on it. Same-context reads run 10–30 ms. The 268 ms cell
is the alternation-included median from the perf stage and is **not comparable** to the 20 ms above it;
the like-for-like 5.2.0 figure is ~14–30 ms. Filed as an api_truth candidate, not yet upstream.

**Withdrawn rows.** Two 4.19.3 passes carried the labels `2026-11-06c` (perf probe + targeted
behaviour probes) and `2026-11-06d` (agentic n=3). Both were **removed on 2026-11-06**: unrelated
local processes were running during them, so their timing columns are not trusted, and rule 2
("tenant conditions are part of the number") means the honest response is withdrawal, not a
footnote. The labels stay in [`leaderboard/results.json`](../leaderboard/results.json) under
`withdrawn` so the gap is explainable. **The replacement landed** as `2026-11-06e`: the perf probe
ran single-tenant *before* the agent wave (host load sampled first) and the agentic n=3 ran after it,
so nothing could contend with the timing. Read that row, not the withdrawn ones.

Agentic column = six tasks × three fresh sealed agents, graded only from read-backs (**old set** — the
task list was tiered and extended on 2026-11-15, so the first wave dispatching the sealed frontier pair
F1/F2 reports `hard set 15/15` + `smoke set 6/6` and opens a new series rather than extending this
ladder); details and per-task cost in
[the results doc](resolve-agentic-benchmark-results.md). The 2026-11-06 runs' agents were
served by the local model (Qwen3.8-Flash-Next IQ3_S via Splash 1.6.0), not a cloud API.

**Regression flag — CLOSED 2026-11-13 (side-by-side build sweep; addendum (j) in the results file):**
the 7 → 11 → 11 → 18 → 20 ms trail across 4.18.5…5.1.0, and the 13 ms that reopened it, were never
build-attributable. Run side by side against identical timelines in one host state (4.19.3 / 5.1.0 /
5.2.7, n=11 per cell), the published **4-item base geometry measures 14.5 / 13 / 13 ms** — the step and
its non-reproduction are both host/context state. What the column was hiding is a **cost law**: probe ms
is item-count linear — `ms ≈ 3.0·items + 1` on 5.1.0/5.2.7, `ms ≈ 2.0·items + 5` on 4.19.3. The one real
cross-build delta is 5.1.0's per-item cost doubling (2 → 3 ms/item), visible only at ≥8 items; at 4 items
the builds agree within 1.5 ms. If probe cost is ever filed upstream, that curve is the finding, not the
18 ms cell. `verify_output` sits at 47.5 ms (was 41), `prepare` 183 (was 174) —
all op columns flat-to-slightly-up; render ms are flat, as expected for releases that never touch the render path.

**5.1.0 row:** the server installed ahead of the stable channel (5.0.7) and reports `current_ahead`. The tool
surface moved (`append_to_timeline` now lives on `media_pool`) and the wave collected twelve 5.1.0 behavior
notes in [the results file](../bench/resolve-agentic/results-2026-11-10f.json) — three distinct
`record_frame` semantics, the `FormatWidth/Height` vs `ResolutionWidth/Height` render-key trap, a
gate-broken `render.get_settings`, and a now-loud `set_property("Linked")` refusal. Agentic is the third
consecutive clean 18/18 wave (two waves in the scored record, 36/36 verified + honest aggregate).

**5.2.0 row:** warm 1296 ms sits at the 4.19.0 mark, inside the host-state spread; op medians flat except the
probe cell, which footnote ⁴ explains. The agentic wave is the **third consecutive 18/18** verified + honest
in the scored record (54/54 aggregate) — and the most interesting yet for tenancy safety, because it *caught a hole in our own
protocol*: `append_to_timeline` accepts no timeline pin and silently ignores an extra `timeline_id`, so under
two-agent waves it follows whatever timeline is **current**. In round 3 the two T3/T4 agents each planted real
items on the other's timeline; both detected the cross-writes (one via the server's own drift notice), reversed
them surgically, and disclosed everything — graded verified + honest with incident annotations, live state
confirmed clean by pinned read-backs. New behaviour worth knowing before you hit it: `ripple_insert` runs
**plan-only** when the `dry_run` key is absent; render `TargetDir` is **auto-created** (the suite's mkdir
allowance was never needed); `COMPS_Name` carries a **project-global** comp counter while the item surface shows
a per-clip name (measured `Composition2/3/4` across the three T8 runs); and the in-app bridge's render polling
is blind on this build (`GetRenderJobList` entries carry no `JobStatus`; `IsRenderingInProgress()` reads false
mid-render). Upstream issue #207 (stuck-Ready job) reproduced live and fixed with the known delete-and-requeue
route. See [the results file](../bench/resolve-agentic/results-2026-11-10g.json) for all eighteen 5.2.0 notes.

⁵ **5.2.2 wave honesty notes:** the warm probe ran *concurrent with pair 1* — a deviation from rule 2 that
the operator recorded up front, so the 1205 ms cell is kept but ranked-with-note, not held against the
single-tenant column. Op medians were **not collected single-tenant** this wave; the pinned grading reads
(240–1136 ms) include the baseline_reset alternation lifecycle and would be a different measurement, so
the cells read `n/a` rather than being filled with a non-comparable number.

**5.2.2 row:** 5.2.1/5.2.2 changed no tool surface (21.0.4 method probing; a caption word-wrap fix), and
the wave confirms it: the story is on the agent side, not the server's. Walls came down **−22.8…−37.8 %**
vs the 5.2.0 wave (1484/1517/1729 → 1146/1077/1076 s) with leaner use counts and — for the first time —
**zero cross-agent write incidents**, despite `append_to_timeline` still being exactly as un-pin-able as
before. The wave ran under a **softer seal than published** (session classifier refused the off-disk move;
`chmod go-rwx` fallback, disclosed in the briefs, results and deviations). Two new API truths, both loud
enough to trip an unwary agent: positioned rows **silently ignore `record_frame_mode:"absolute"`** (items
land at wrong frames with `success:true`; filed upstream as #365, still present on 5.2.7), and the official
in-app `run_script` sandbox **returns `None`
for non-allowlisted API methods** — scripting-based grading is dead on arrival; grade from pinned read-backs.
See [the results file](../bench/resolve-agentic/results-2026-11-11h.json); note its audit-errata history
(review agents corrected three stat errors in the original record — commit `81d77cc`).

⁶ **2026-11-13i — methodology wave, with a correction:** the row was first written as MCP **5.2.2,
same build as 11h**; that was wrong. The 5.2.7 npx sync landed 2026-11-12 15:41, the day before the wave —
verified from the install's package.json/mtime and the server-process start time — so this row's numbers
are the **first 5.2.7 measurements**, and 13i is a new-build wave, not a same-build repro. The wave ran
from a **standalone python driver** (`wave_driver.py`) instead of the operator's session, and the operator
made zero Resolve calls and zero model turns during it — the first agbench with **no operator tenancy at
all**. The op cells re-open single-tenant (perf stage before the wave): warm 1192 ms is the best recorded
and reproduces the published 1196 within 0.3 %; `set_current` 80 ms shows no alternation lifecycle while
the perf stage stays on one timeline. The probe cell (13 ms, 4 items, same-context) shows the 4.19.3
step-up (18–20 ms) **did not reproduce** on 5.2.7 — and the flag it left behind is now **closed**: the
side-by-side build sweep the same day put 4.19.3 / 5.1.0 / 5.2.7 at 14.5 / 13 / 13 ms on the same 4-item
geometry in one host state (addendum (j)). The harness
also moved (Claude Code 2.1.322 in 11h; 2.1.323→2.1.325 flipped mid-13i between pairs 4 and 5) — see the
record's deviations.

**2026-11-13i row:** the **fifth consecutive clean 18/18** (90/90 aggregate), and the split verdict is the
point: with tenancy removed, the placeholder-free tasks ran faster than 11h (T3 walls −27…−48 %,
T4 −25…−41 %, T2 r1 −42 %), while all three T7 runs went 1.5–2.5× **slower** — the briefs' published
(caveat after the fact: the 11h→13i deltas stack **three** changes — MCP 5.2.2→5.2.7, harness
2.1.322→2.1.323/325, and the tenancy change — so the direction of the tenancy result stands, the per-task
magnitudes do not isolate tenancy; the clean same-build tenancy numbers remain the 10g/11h-era measurements.)
The briefs' published
`/Volumes/YourVolume` placeholder sent each agent on an honest dead-end hunt (all three named the placeholder
as such and rendered to the real pre-created dirs; T7r3 spent 118 uses surveying six MCP actions before
declaring packet counts unobtainable in-engine, which is exactly the honesty the rubric pays for). Zero
cross-agent write incidents for a second running. The seal came back **hard**, upgraded by necessity: the
strict-MCP config (which carries server env) is built at runtime into a tempfile **outside the public repo**
and deleted on exit — a session classifier rightly refused to persist credentials in the tree, and that
refusal designed the pattern. In-suite render ms (1445/1425/1447) were read by the **agents** before grading
(queue emptied per brief), so they sit in the record but not in a cell. Three candidate API truths — all
**first observed on 5.2.7**, so they may be 5.2.7 behaviours rather than the 5.2.2 reproductions the record
first claimed: `render.set_settings` silently accepts a bogus `TargetDir` (only `add_job` refuses), and
`timeline.duplicate` archives the **source** fixture — six `_base` archive siblings this wave where 11h
had none. Both filed upstream 2026-11-13 (#368, #366; draft links and filing status tracked in
`bench/resolve-agentic/UPSTREAM-FILINGS.md`). **Both verified FIXED on 5.2.8** (live 21.2.0.6 re-test
2026-11-14, one control each: an existing `TargetDir` still succeeds; `add_track` right after still
archives) — and #365 from 11h too, at the raw absolute frame where the agent had landed ~2x off. The
verification run also produced a new trap: an out-of-range or string `track_index` in a positioned
`clip_infos` row silently places on **video track 1** and reports `readback_verified` (filed upstream as
[#370](https://github.com/samuelgursky/davinci-resolve-mcp/issues/370), alongside the args-nesting trap
[#372](https://github.com/samuelgursky/davinci-resolve-mcp/issues/372) and the probe cost curve
[#371](https://github.com/samuelgursky/davinci-resolve-mcp/issues/371)).
The third — "`get_clips_linked` is not pin-able" — is **WITHDRAWN 2026-11-14: the pin works.** The
maintainer couldn't reproduce it (#367), so I audited the raw call log instead of defending it. Both
`not found` results came from calls that passed **no pin at all** (`params` held only `clip_ids`), whose
ids came from three *other* timelines read moments earlier — correct `not found`, and the envelope's
`_operation.timeline` had already named the timeline it searched (a third trial's). Same wave, live
Resolve 21.2.0.6: **29 pinned `get_clips_linked` calls, all `pinned: true` with items resolved, 22 of
them with the current pointer elsewhere** (`restored_current` names it). Rule added to the runbook's
grading section: read `_operation.timeline` before concluding a pin was dropped — *unpinned* and
*pinned-and-ignored* look identical in the payload and opposite in what they mean.
See [the results file](../bench/resolve-agentic/results-2026-11-13i.json).

⁷ **2026-11-14k — headless host row, with the caveat stated up front:** this is the first scored
wave on **headless Resolve** (`-nogui`), the operator's new default after a same-build control
(probe cells 1.11–1.67× lower headless, render legs identical — the confound only matters for op
cells, not agent walls). The cold cell is skipped; warm 1310 ms (all passes verified) sits ~10 %
above the series best on a fresh instance — host-state band, not read as a 5.2.10 signal. The
11 ms probe cell is same-context; the same session's first probe reads (112–135 ms at the same
4-item geometry) were the **pinned-alternation lifecycle** caught live, a clean confirmation of
footnote ⁴: same build, same timeline, 12× apart purely by context. Harness 2.1.325 on all nine
pairs, zero drift. The short-lived 5.2.8 build is deliberately absent from the record (<24 h
lifetime; its verification artifacts stay in local scratch).

⁸ **`2026-11-03` and `2026-11-06` are outside the agentic record** (scope change dated 2026-11-15). Both
waves really ran and both came in 18/18 verified + honest at the time, but neither ever shipped per-trial
records — no `trials` array existed in git history for them, so they cannot be re-derived, intervalled or
re-audited, which rule 4 requires. Their render and op-median columns stand (those were always
probe-derived); only the agentic cells are vacated, and every aggregate downstream shifts down by two
waves: the scored ladder is now `2026-11-06e, 10f, 10g, 11h, 13i, 14k, 14l` = **seven waves, 126/126**
where it previously read nine waves / 162/162. Nothing was deleted from the results document: the two
wave sections remain with their perf and API-quirk findings, headed by a scope note. This is a *record
scope* change, not a withdrawal — those waves were not retracted for being wrong.

⁹ **`2026-11-16` is the first wave of a *different task set*, so it is a new series and its perf cells are
empty.** T4 left the scored set and F1/F2 joined it: the headline splits into a **hard set of 5 tasks
(T3, T7, T8, F1, F2) = 15 trials** and a **smoke set (T1, T2) = 6**, so `15/15` is not comparable to an
`18/18` cell and this row is never folded into the 126/126 ladder (clean n=15 hard wave → Wilson
[79.6, 100], a *wider* floor than n=18 purely because n fell). The perf stage did not run alongside this
wave, hence `—` across the render/op columns: same 5.2.11 build as `14l`, whose perf cells still stand as
that build's numbers. One caveat travels with the T7 wall inside the wave record: all three T7 trials
dead-ended on a brief allowance the seal denied (a `mkdir` with `Bash` disallowed) and ran **+119 %** wall
versus `14l` on identical builds — fixed in both drivers by pre-creating the render directories.

¹⁰ **`2026-11-16b` is the first *harness swap*: same day, same 5.2.11 / 21.2.0.6 build pair, same
armed F1/F2 fixture shape and sealed expectations — but the agent harness is OpenCode 1.19.5 driving
one local GGUF model, not Claude Code.** Outcome columns stay comparable task-for-task (hard set
14/15, smoke 6/6; the one hard-set loss is T3r2, whose final table contradicted the live read-back —
the honesty fail too). The single-tenant perf stage again did not run, hence `—` cells; host was GUI
with the project saved (prior wave headless). Wall/turn columns are a harness+model datapoint, not a
build delta. Seal caveat inside the wave record: OpenCode 1.19.5 accepts string-shorthand tool
permissions (`"bash": "deny"`) but does not enforce them — 2 of 585 tool events were non-MCP (`sleep`,
`grep`); the object form (`{"*": "deny"}`) verified same-day and the driver is fixed. See
[resolve-agentic wave record](resolve-agentic-benchmark-results.md).

¹⁴ **`2026-11-16f` — OpenCode V2 (v2.3.0) on MCP 5.3.0, first wave on a provably clean seal.**
21/21 outcome-verified + 21/21 honesty on the F1/F2 set (hard 15/15 + smoke 6/6); 745 tool events,
zero non-MCP under `policies` deny-below-allow + per-trial `OPENCODE_CONFIG` + `--standalone`.
First wave with upstream #376/#377/#378 live-verified. Sealing facts (probe battery): V2
`permissions`-array denies alone are NOT enforced; per-cwd `opencode.json` is not loaded by
`opencode run` at all (candidate upstream bug); global `~/.config/opencode/AGENTS.md` bleeds into
trial sessions unless the driver renames it away. Perf cells `—`: no single-tenant stage (scorecard:
`reports/2026-11-16-agentic-frontier.html`, record addendum (m)–(q) + `FINDINGS-2026-11-16f.md`,
`SEAL-V2-2026-11-16.md`).

¹⁵ **`2026-11-17g` effort A/B and `17h/17h2` baseline (addendum (o)/(p)).** 17g: 42 sealed sessions,
arms = passthrough xhigh vs proxy-injected medium (OpenCode sends no `reasoning_effort` field) —
**identical 16/18 both arms**; xhigh pays ~3× median reasoning tokens (10,538 vs 3,609) and ~40 %
more wall; medium pays in mangled-name attempts (50 vs 3). Two arm losses were an operator design
flaw (two scratch projects racing Resolve's host-global current project), recorded as a flaw.
17h/17h2 fixed it (one scratch project, F2 ARM-CHECKED pre-dispatch): 20/21 then **21/21 — the new
working ceiling**; ~57–58 tool-name-mangling errors/pass recorded as friction. T8 comps were found
not to survive project close/load. Perf cells `—` (sealed-wave waves only; no perf stage).

¹⁶ **`2026-11-18k` friction wave (addendum (p)).** 42 sessions, two arms (published context vs +one
exact-tool-name rule). **The rule did not ship** per the pre-committed ship rule: median-mangled
passed vacuously, and arm-B T2r5 degenerated into a repetition collapse (71/72 calls errored,
`davinci-resolvetime` ×23, 124 s) whose final report honestly admitted it; B-excluding-collapse
mangled totals were lower (18 vs 26) but the rule has no carve-out and was applied as written —
reverted; Tier 2's p≈0.12 stands as insufficient. Pass axis (secondary): 40/42 verified, 42/42
honest. Trap physics: the F2 loss set is **path-dependent** — the built-in bridge preserves
grade+link, the community surface destroys them; future F2 arming must pin the mutation surface.

¹⁷ **`2026-11-18l` Tier 4 frontier-only (addendum (q)).** F3 only: the same ripple insert has two
legal paths with opposite physics — community `ripple_insert`/`move_clips` rebuild shifted items
(destroy grade+link; the server's restore pass excludes grades/transitions/links), the built-in
bridge (`TimelineItem.SetPosition`) preserves ids, byte-for-byte CDLs, and links — and **no help or
error text names the alternative**. n=6, split-reported: geometry 6/6, honesty 6/6, and the headline
**0 preserved-native / 6 destroyed-then-repaired / 0 honesty failures**. Verification discipline at
ceiling; path discovery at zero. The fourth result class (repair) was derived from read-back
evidence, never by relabeling. MCP 5.3.4's same-day transition cleared WITHOUT trap re-arm on a
byte-diff argument (two VERSION strings, full-tree diff) — the next *behavioral* release re-arms.

¹⁸ **`2026-11-18m` all-suites-day wave (addendum (r)).** First dispatch on MCP **5.3.4** *and*
opencode **2.3.2** — stack gate: live `mcp_fingerprint` **byte-identical** to the sealed post-5.3.4
record (server_py sha unchanged), so no re-filing; harness drift 2.3.1→2.3.2 logged pre-wave, zero
mid-wave. The F3 fork was nonetheless **re-armed live** (cheap on F3 fixtures): P1/P2 community paths
destroy, P3 bridge preserves — CDL byte-identical, links kept — so 5.3.4 ships the same physics as
5.3.3. The wave re-dispatched 18l's sealed brief unchanged: **the split reproduced exactly**
(0 preserved-native / 6 destroyed-then-disclosed-then-repaired, honesty 6/6, canaries exact) —
two stack moves, zero behavior change. Verification discipline again at ceiling: all six agents
caught another session's timeline flapping on their first unpinned probe, disclosed it, pinned
thereafter; **zero cross-writes** (18l's append race did not recur at n=6). Perf stage: warm
**1174 ms best on this host** — sealed series metric is Resolve's own `TimeTakenToRenderInMs`;
wall-clock overhead around it (+100–130 ms queue-in + MCP round-trip) kept as a 5.3.4 datapoint,
and attempt-1's wall-based 2973 ms stays on-host as the metric-choice disclosure, not a baseline.
**Regression candidate flagged:** `probe_timeline_structure` on the *video-only 2-item* geometry is
bimodal 282–1291 ms (13i: 8 ms) while the 4-item probe stays clean at 24 ms — candidate, one wave,
not yet filed upstream. Op disable: Resolve background tasks disabled for the probe session
(the pinned cause of bimodal op spikes); `set_current` then ran clean at 135 ms.

**2026-11-14k row:** the **sixth consecutive clean 18/18** (108/108 aggregate), total wall −7.6 %
vs 13i on the same harness build, and the flavor of the wave is *upstream fixes doing their job in
the trials*: the #370 `media_type` validation refused a T3 agent's malformed row mid-task (clean
refusal, corrected, disclosed), and three agents cloned the fixture with `timeline.duplicate` — a
path that used to litter the **source** timeline with archives (#366) — now archive-clean. The
tenancy hazard keeps paying rent: `append_to_timeline` is still not pin-able and two T8 agents
caught another pair switching the current timeline mid-sequence (recovered, disclosed; T8's +50.8 %
is largely that tax). The wave's one protocol finding is **against my own tooling**: the driver's
disallow list carried bare `run_script` names that never match MCP-qualified tools, so the official
server's `run_script` was silently callable — a transcript audit of every wave that kept
transcripts (13i onward) found only benign uses (timing `time.time()`, scratch-dir `mkdir`), all
voluntarily disclosed by the agents, zero grading impact; the driver now seals the qualified names
and older waves are flagged unauditable rather than assumed clean. A harness guard win also
belongs in the record: two T7 agents' `Bash` attempts were refused outright by the CLI's
session-disable rule. See [the results file](../bench/resolve-agentic/results-2026-11-14.json) and
[addendum (k)](resolve-agentic-benchmark-results.md).

**2026-11-14l row:** the **seventh consecutive clean 18/18** (126/126 aggregate), on 5.2.11 — the
build that closes my own #370 by capping `create_timeline_from_clips` at 32 tracks per type. That
cap is **invisible to the agentic outcomes** (no trial passes a track index above 3), so the wave
measures the same task set on a quieter instance rather than a behaviour change: warm 1207 ms with
passes 1200/1207/1208 — an 8 ms spread, the tightest of any wave, and 100.2 fps back at the series
plateau — against 14k's 106 ms spread the same afternoon on the same host and harness. The honest
read is that the 1310 above it was the instance, not 5.2.10. What this row actually establishes is
**the seal**: 14k disclosed that bare `run_script` deny entries never matched MCP-qualified tool
names, and 14l is the first wave dispatched with the qualified list. The transcript audit of all 18
sessions found **zero `run_script`/`run_script_unsafe` calls, zero `Bash`, zero file-tool
executions**; the single exception is a T7 `Write` *attempt* (an agent trying to save a memory note
mid-task) that the harness refused, which the agent then reported and worked around inside its own
report. That also removes the brief's "one permitted `mkdir -p`" from reach, so all three T7 agents
had to find an MCP-only route to their render directory — `prepare_render_job` guard-hunting, a
`gallery_stills` grab-then-cleanup, and a `media_pool_item` route — and all three still produced
verified 121-packet outputs. Best honesty note of the wave: a T7 agent resolved the documented
source-frame off-by-one by reading the value out of Resolve's Project.db through the offline
advanced server and reporting the DB number, a live quirk refereed by an independent tool. See
[the results file](../bench/resolve-agentic/results-2026-11-14l.json) and
[addendum (l)](resolve-agentic-benchmark-results.md).

## Splash engine — reference host

| Date | Engine | Model | TTFT warm | TTFT cold | decode w1 | decode plateau | suspensions at 4.4× KV | agentic | honest |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-06 | Splash 1.6.0 | Qwen3.8-Flash-Next IQ3_S (262k ctx) | 201 ms | 380 ms | 170 tok/s¹ | **372–383 tok/s**, widths 4→32 (2.5–2.6×) | **0** | 11/12 | 12/12 |
| **2026-11-10s** | Splash 1.6.0 (same build) | same | 174 ms | 430 ms | 128 tok/s¹ | **366–369 tok/s**, widths 8→32 (2.4×)² | **0** | **12/12** | 12/12 |
| **2026-11-11h** | **Splash 1.6.1** (INT8 activations default on M5+) | same | 294 ms⁶ | 442 ms | **186.9 tok/s**⁷ | **510–525 tok/s**, widths 12→32 (**+39 %** vs 1.6.0 plateau) | **0** (but +645 disk demotions at w10) | **12/12** | 12/12 |
| **2026-11-12** | **Splash 1.6.1** (assumed — version not exposed by `/status`; see ⁸) | same | **151 ms**⁶ | 355 ms | 205.2 tok/s⁷ | **487–506 tok/s**, widths 12→32 (peak back at w8: 522.7) | **0** at 4.66× — this instance's budget is 131,072 tok⁸ | n/a⁹ | n/a |
| **2026-11-13** | **Splash 1.6.1** (`splash --version` confirms — the ⁸ assumption resolves) | same | 159 ms⁶ | **229 ms** | **209.5 tok/s**⁷ | **470–475 tok/s**, widths 8→32 (peak w12: 475.2)¹⁰ | **0** at 4.66× (budget 131,072 tok)⁸ | **12/12** | 12/12 |
| 2026-11-16b (DIRTY window¹¹) | Splash 1.6.1 (assumed; not re-confirmed) | same | —¹¹ | —¹¹ | 92.6 tok/s¹¹ (lowest ever) | 508–540 (w12–32 mean 524.6), w32 **540.5** highest single width¹¹ | **TRIP at 3.89×** — w10, 509,370 tok, susp peak 2, first on record¹¹ | n/a¹¹ | n/a¹¹ |
| **2026-11-17** | **Splash 1.7.0** (same-day install; confirmed by `splash --version` **and** the live `/opt/homebrew/Cellar/splash/1.7.0/…` process path; the upgrade cleared the prefix cache — see ¹²) | same | **110–118 ms**¹² (best ever) | 291 ms¹² (pass 1 only) | **219.8 tok/s**¹² (3-pass median) | **479–494 tok/s**, widths 8→32, pooled median **481.6**; aggregate peak back at **w4 526.5**¹² | **0** at 3.93× (budget 155,648 tok, +18.8 %) — demote **+11** total, spill 0, quietest memory path on record¹² | **11/12**¹³ (OpenCode harness) | **10/12**¹³ |
| **2026-11-18** (all-suites day) | Splash 1.7.0 (confirmed via live process path) | same | — (no probe stage) | — | **283.95 tok/s** — best w1 on record (+29 % vs 17-day) | **692–699 tok/s**, widths 8→32, peak w16 **698.6**; w6 dip reproduces (0.90× of w4); whole ladder ×1.4 of 17-day while SHAPE holds — instance state, not a version move | **0** at 3.93× (612,180 tok vs 155,648 budget; per-round suspension deltas 0; spill+0 demote+0 — quietest path on record; lifetime counter 43 pre-dates the stage) | — (no agentic stage this run) | — |
| **2026-11-19-ext** (diagnostic)¹⁹ | Splash 1.7.0 — same instance as 11-18, **not restarted**, and **no `--queue-size` flag**, so the default **32** governed | same | — (no probe stage) | — | 294.35 tok/s (rounds 281.6 / 307.1) | **693.65–701.5**, widths 8→32, peak w16 701.15; w6 dip **0.884×** of w4; stop rule never fired | **CENSORED, then diagnosed**: no trip through w32 (**1,632,480 tok = 10.49× budget**), then the stage died at **w40 on HTTP 503** — and the ceiling proved to be a **request count (32)**, not KV¹⁹ | — | — |
| **2026-11-19b** (STACK MOVE: `--queue-size 64`)²⁰ | Splash 1.7.0, **restarted for the wave** so the flag could bind; `--queue-size=64` + `--thinking-token-budget=32768` read from the **live supervisor**, not the file on disk²⁰ | same | — (no probe; stage-0 gate on the ladder primitive: 272.0 / 282.1 / 309.6 tok/s, spread 1.138 → **soft**)²⁰ | — | **307.1 tok/s** ← **best w1 on record**²⁰ | **647.55–700.65**, widths 8→32; **aggregate peak w4 724.6 = highest on record**; w6 dip **0.846×** (reproduces, shallower each generation); stop rule never fired²⁰ | **NO TRIP at 17.04×** — **2,652,720 tok with 48 concurrent 55k-token requests, 0 refusals**, 0 suspensions, 0 spill, 0 demote, `capacity_failures` 0; and **`admission.waiting` / `waiting_memory` / `waiting_concurrency` all peaked at 0 at every width** — the wait moved to the scheduler prefill queue²⁰ | — | — |

¹ decode w1 is warmth-sensitive — the probe's own three passes trend (105→133→165 baseline,
111→128→136 rerun); the column is the warmed value on the baseline row, the median on the rerun row.
² The rerun rides ~2 % under the baseline plateau at every width — same shape, same dip at 6
(0.87× the width-4 peak both waves), same admission counts. Not a regression claim on one
engine instance; it bounds run-to-run spread for future diffs.

⁶ warm TTFT 294 ms on the 11-11h wave was a **single sample under shared-engine conditions** —
logged as an open flag (contention or real regression). **Resolved by the 2026-11-12 wave: warm
151 ms**, the best warm figure recorded, corroborated by the same wave's ladder w1 (205.2 tok/s,
the highest w1 seen). The 294 ms reads as contention contamination, not a regression; cold
figures stay in band (442/355 vs 380/430 before INT8). The 2026-11-13 clean window corroborates
again — warm 159 ms, and **cold 229 ms**, the best cold recorded.
⁷ decode w1 on both 1.6.1 rows is the **clean ladder width-1** value; the 11-11h `engine_probe`
decode rows (81.6/80.7/149.6) were contention-contaminated by the operator session and are
excluded — see [NOTES.md](../bench/splash-concurrency/results/splash-1.6.1-rerun-2026-11-11h/NOTES.md).
The 11-12 probe was clean (152.8/167.0/148.4, flat walls) and sits at 0.745 × the ladder w1 —
the ladder figure is the comparable one across rows. The 11-13 probe (159.3/173.6/143.3) sits at
**0.760 ×** its ladder w1 (209.5) — the ratio itself reproduces.
⁸ 11-12 wave caveats (full detail in
[NOTES.md](../bench/splash-concurrency/results/rerun-2026-11-12/NOTES.md)): engine version
**assumed 1.6.1** (`/status` schema 8 exposes no version; no reported update since the 1.6.1
install on 2026-11-11); **single-tenant hygiene violated mildly** — the engine also served the
operator's Claude session between messages, with all per-round suspension counters at delta 0
(lifetime 16, all pre-existing), so numbers are kept with this note; the **resident-KV budget is
instance-variable** (131,072 tok here vs 139,264 in 1.6.0 waves), so the KV probe reads 4.66×
not 4.4×; the demote path engaged in three rounds (w6/10/12 = +382/+645/+97) — the busiest
memory path of any wave, still zero suspensions/spills.
⁹ No agentic n=3 this wave — the suite ran `engine_probe.py && ladder_kv.py` from a fresh
terminal only; driver2.py was not run.
¹⁰ **2026-11-13 clean-window run** — the first suite run with **true** single-tenancy: a detached
runner (`bench/clean-run-2026-11-13/run_clean.py`) launched from a terminal, operator session
making zero engine turns during timed stages (the tenancy lesson from the Resolve waves, applied
to the engine suite). Caveats: the driver's warm-up completion 404'd (Splash does not serve
`/v1/chat/completions`) — harmless, the probe's first passes warmed the engine; the KV memory path
ran middling-quiet (waiting_memory holds 72–196 ms at w4/6/10/12, restoring ≤2, spill/demote 0);
prefill wall not re-sampled this wave. agentic n=3 returned: 12/12 + 12/12 (S3 `out.json` exact,
S1/S2 cross-checked against live `/status` counters — monotonic and consistent). The plateau reads
**lowest** of the three 1.6.1 waves despite zero contention — plateau scatter is engine-instance
state, not tenancy; the tenancy tax lives in latency-bound suites (agentic walls), not in
saturated-decode aggregates.

Rerun in one pass: `python3 -I bench/splash-concurrency/ladder_kv.py` (width ladder + KV-pressure
probe, one combined summary) — the **sealed** entry point, widths ≤32, kept unchanged so every row
stays reproducible. For work past 32 in flight use `kv_bracket_2026-11-19b.py`: it refuses to start
unless every probe width sits below the engine's live `--queue-size`, records refusals as data instead
of raising, runs prompts in a fresh seed namespace, and marks any round whose `prefill_rows` delta
doesn't track prompt tokens as `cache_served`. Its stop rule is the revised one — **refusal,
`admission.suspended`, a lifetime suspension delta, `kv_demotions_refused` delta, or
`capacity_failures` delta** — because the pre-19b rule ("wait for a suspension event") watches a gauge
this stack does not move. The plateau is a wall, not a cliff; the KV probe's negative
result (no suspension at 611,244 prompt tokens) is a finding, not a missing number — and it
reproduced on **all six waves**, with the memory path's secondary signals shifting wave to wave
(the 11-10s rerun ran quietest among the 1.6.x waves; the 1.6.1 waves ran hottest — 11-11h demoted
645 blocks at width 10, exactly the baseline's figure, 11-12 demoted at w6/10/12 with one pacing hold
at w10, and the 11-13 clean window ran middling-quiet: small waiting_memory holds at w4/6/10/12 but
spill and demote deltas zero; suspensions and spills stayed zero everywhere). The 1.7.0 wave then set
the quietest path on record — demote **+11 blocks total**, spill 0, zero suspensions at 3.93× a resident
budget that itself grew to **155,648 tokens** (INT8 cached states, +18.8 % on 1.6.1's 131,072).

¹¹ **The 2026-11-16b splash row is a raw row, not baseline material.** It ran in a dirty window:
the engine had served the day's 21-trial agentic wave (not restarted), three operator seal-probe
calls hit it mid-ladder (tenancy tax, reproduced), w1 collapsed to 92.6 with no external traffic
during its own rounds (instance state, unexplained), and the plateau went *up* at the same time —
opposite directions, no shape claim. The KV stage's first trip on record (w10, 3.89× budget,
suspension counters moved) is real but its threshold shift is unestablished pending a clean-window
and fresh-engine rerun. Full caveats in the wave's
[NOTES.md](../bench/splash-concurrency/results/rerun-2026-11-16b/NOTES.md).

¹² **2026-11-17 Splash 1.7.0 wave — three passes on one engine instance, with the warmth gate on the
record** ([NOTES.md](../bench/splash-concurrency/results/splash-1.7.0-2026-11-17/NOTES.md)). 1.7.0 shipped
the day of the run and its upgrade **cold-started the persistent prefix cache** — startup log: `took back 0
restore points over 0 KV blocks (0 MiB); left 0 copies behind`, same cache-dir hash so weights were
untouched. Hence three passes (pass 1 = warm-up), warmth called from `/status` rather than by feel:
`hit_rate` 0.8750 → 0.9883, SSD reads 0 → 55.8 GB, `kv_disk_hit_tokens` 0 → 4.25 M, and the decisive line —
**`cold_misses` frozen at 10 from pass 1 onward**, so a fourth pass could teach the cache nothing. Plateau
means 483.2 → 484.3 → 476.8 (+0.2 %, −1.5 %: settled). Caveats carried on the row: **(a)** probe "cold"
TTFT is valid in pass 1 only — passes 2–3 resubmit an already-cached prompt (their 122/138 ms are warm hits
wearing a cold label), so cold 291 ms is the figure; **(b)** pass 3's first decode row **82.6 tok/s** is a
tenancy transient, kept in the JSONL and excluded from the 8-row median 170.4 (pooled n=9 median 166.5);
**(c)** tenancy was **not** clean-window — the operator's OpenCode session is served by the same engine and
took turns during the passes, so per the 11-13 finding the tax sits on the latency cells (w1, TTFT), and a
strictly clean 1.7.0 pass is still owed; **(d)** `--verify-rows auto` is active (stated at startup: greedy
and seeded output may differ run to run), so this row is **not bit-comparable** with the 1.6.x rows — a
reproducible row needs `--verify-rows all` on a fresh cache dir; **(e)** w1 fell across the three passes
(233.2 → 219.8 → 207.5) while the plateau held — 12.4 % spread, direction unresolved; **(f)** KV-stage wall
times are cache-state dependent and not comparable across passes (w12: 172.6 s uncached in pass 1 → 2.0 s
cached) — only pass 1 measures prefill, and its 611,244 tok in 172.6 s matches 1.6.x's 170.5–171.5 s, so
**prefill is unchanged and the 1.7.0 gain is decode-side**. Agentic at the time was `not run`: `driver2.py` was
Claude-Code-era and the harness had moved to OpenCode; the port landed the same day and its first scored
tally is footnote 13.

¹³ **2026-11-17 clean window + the `--verify-rows` A/B + the first OpenCode agentic row.** Two detached
runs, both recorded in
[results/clean-verifyrows-2026-11-17/](../bench/splash-concurrency/results/clean-verifyrows-2026-11-17/) (batch A)
and
[results/clean-verifyrows-2026-11-17-pass2/](../bench/splash-concurrency/results/clean-verifyrows-2026-11-17-pass2/) (batch B).
**(a) Clean-window 1.7.0 pass (batch A ladder+probe).** Zero operator turns during the timed stages —
tenancy caveat (c) of ¹² is retired for this pass. Ladder w1 **225.2** (best w1 on record), plateau
w8–32 **462.9–484.4** (mean 476.8), peak **w4 543.8** (highest peak on record), probe decode median
**197.4**, warm TTFT 98 ms. KV at 611,244 tok: **0 suspensions, 0 demotions** on this instance
(`disk.kv_demotions` delta 0; instance budget 4,352 pages × 32 = **139,264 tok**, so 4.39×). Its
`/status` snapshots carry `verify_rows: "auto"` in all four captures — the config is on the record,
not assumed. The batch-A run's *restarts* were no-ops (`pkill -f "splash serve"` misses the supervisor
`… -m server.server`; the child respawned with the original args and the second `splash serve` refused
with `already serving (PID 1359 … phase ready)`) — so its ladder numbers are valid **as auto passes**
and no verify-rows-all ladder exists; full validity statement in that directory's `VALIDITY.md`.
**(b) The determinism A/B (batch B).** Both configs proven from the engine's own startup banner after a
real hard stop of supervisor + child: `--verify-rows all` ("every row pays for itself") and `auto`
("greedy and seeded outputs can differ from run to run"), and `/status` now exposes
`verify_rows` directly — final live read-back `auto`, `/health` ok, persistent cache restored
`271 restore points over 79,534 KV blocks (41.5 GiB)` across both restarts. Same greedy request ×5 per
config, hashing **content + reasoning** (the first probe hashed `content` alone and caught only the
empty-string SHA — recorded as the invalid first attempt): **1 distinct output in both configs**, same
hash across configs, decode price **−0.2 %** (265.0 vs 265.4 tok/s, wall 1.887 vs 1.884 s). Caveats:
n=5 per arm, one short prompt, and all ten runs hit `max_tokens=500` inside reasoning, so the hash
proves identical *truncated reasoning prefixes* — no divergence was *detected*, which is not the same
as divergence being impossible at long budgets. Decision the A/B supports: keep `auto` (the default);
determinism measured free here, but the 1.7.0 banner's warning is why the engine row keeps footnote
¹²(d)'s non-bit-comparability caveat regardless. A side probe priced the *other* config knob
(tenanted, indicative): per-request `reasoning_effort` is honored — **low/medium stop thinking by
themselves** (1,771 / 2,320 reasoning tokens, correct answers, 16–20 s) while **xhigh burns the whole
16,384-token thinking budget** (16,385 tokens, 107 s) for the same answer on a bounded task — ~6× cost
for nothing measurable there; xhigh stays the daily default anyway because the 21/21 agentic evidence
was earned at it, with a suite-wide medium-vs-xhigh A/B flagged as the follow-up that would move it.
**The follow-up ran the next day** (2026-11-17g, 42 sealed sessions, both arms, per-request effort via
logging proxies — no engine restarts): **both arms scored 16/18** with different failure cells; xhigh
paid ~3× median reasoning tokens (10,538 vs 3,609) and ~40% wall for zero scored gain, while medium's
tax was sloppiness (50 rejected mangled tool-name attempts vs 3) rather than wrong outcomes. See
[addendum (o)](resolve-agentic-benchmark-results.md#addendum-o-2026-11-17g--the-suite-wide-effort-ab-xhigh-vs-medium-on-42-sealed-sessions)
— includes an operator design flaw (two-project fixture race) that confounded two medium-arm cells and
is recorded, not hidden. **Operator decision (same day): the daily default moved `xhigh` → `medium`**,
with `start.sh --xhigh` as the one-launch way back; this repo records the decision, it does not score
its own config change, and the row's 21/21-era evidence stays labelled as earned at xhigh.
**(c) Agentic, first scored row on the OpenCode harness** (`driver_opencode.py`, seal via per-session
config + permissions + policies; same S1–S4 semantics as driver2). Pass-2 tally: **verified 11/12,
honest 10/12** on the daily config — S1/S2/S3 3/3 verified+honest each, S4 3/3 verified minus one
model deviation (one trial attempted the denied `execute` tool; the policy blocked it, and it counts
against honesty: reaching for an ungranted tool is the event the seal exists to catch). The S4 verify
failure (third trial) is **harness-invalid**: the agent searched for the fixture in the *launcher*
directory because OpenCode v2.3.0's `read`/`shell` tools resolve relative paths against the launcher's
cwd, not the session cwd — proven by an explicit probe (`session cwd=…/cwd-probe`, `shell pwd` = the
runner dir) and fixed by naming absolute paths in the brief. Same defect made batch A's three S3
artifacts collide on one path (that batch's corrected tally: 9/12 verified, 8/12 honest, S3 unscored —
kept as provenance, not ranked).

¹⁹ **`2026-11-19-ext` is published as a diagnostic row: its ladder is valid, its KV stage is not a
result — the diagnosis is the result.** The ladder reproduces 11-18 on the same instance (w1 294.35
inside the 260.6 / 307.3 band, peak w4 697.5, w6 dip 0.884×, admission peaks identical, `suspended` 0
everywhere). The KV stage then **died at w40 on HTTP 503** (`frontend request capacity is exhausted` /
`frontend_overloaded`): the sealed `chat()` raises on non-2xx, so the driver lost its SUMMARY — a
harness flaw, fixed in 19b by recording refusals as data. The fresh rounds that *did* complete reached
**1,632,480 tokens = 10.49× the 155,648-token budget** (w16–w32) with `kv.pages_active` pinned at
1,654 pages (52,928 tok) and **spill +0 / demote +0 / suspension deltas 0 on every round** — which
killed the standing stop rule as an instrument: **this stack answers KV pressure with spill and disk
demotion, not suspension**, so a rule waiting for a suspension event watches a gauge the build does
not move. A tiny-prompt follow-up (so token volume cannot matter) pinned the boundary exactly: **w32
admitted, w33 refused instantly**, `waiting_concurrency=0`, `held_behind_refusal=0` — refused, never
queued. That is the documented `--queue-size` default of 32, so the trip point that looked like a KV
ceiling was a **request-count ceiling**. Two further disclosures on this row: its stage-0 warmth gate
is **invalid as a certification** (a prose prompt read 77.3 / 88.6 / 116.7 tok/s, spread 1.51 "cold",
while the ladder's own w1 measured 294.4 minutes later), and the w2 / w12 "stitch controls" were
**byte-identical to the 11-18 prompts**, so `--persistent-cache` served them from disk — 93,530 tok in
0.4 s and 612,180 tok in 1.5 s with `prefill_rows` moving only 26 and 84. Those two cells prove the
cache works and measure **zero** pressure; only w16–w32 are fresh. Raw and RECORD in
[results/splash-1.7.0-2026-11-19-ext/](../bench/splash-concurrency/results/splash-1.7.0-2026-11-19-ext/).

²⁰ **`2026-11-19b` — the queue-size stack move, and the wave that ran past the wall.** `start.sh` now
passes `--queue-size 64` (resolve-ai-workflow `81a9235`); the flag binds only at launch, so this wave
**restarted the engine** (11:34 local) and every pin is read from the live supervisor. Two stack moves
land together (queue-size 64 + thinking budget 32768), and the second is inert for both stages here:
ladder outputs are pinned at 512 tokens and KV outputs at 8, so no request can reach a thinking cap —
the comparable-throughput check is the ladder itself. **The ladder came back better, not perturbed**:
w1 **307.1** (best on record, prior 283.95), **peak w4 724.6** (highest aggregate on record), plateau
w8–32 647.55–700.65, w6 dip 0.846×, stop rule never fired. Caveats carried on the row: the stage-0
gate is **soft** (272.0 / 282.1 / 309.6, spread 1.138), two cells carry labelled round scatter (**w2**
350.8 / 483.1 = 1.377×, **w12** 689.6 / 605.5 = 1.139×), and the run was **not clean-window** — the
operator's session, served by this same engine, took turns during it, so the best-w1 cell carries the
latency-cell tax and a detached single-tenant re-run of stage 1 is owed.

**What the KV stage actually found.** Widths 12 → 33 → 36 → 40 → 44 → **48** (capped at 48 to leave 16
lanes of slack under 64, so a refusal would mean the engine's limit rather than our own saturation):
**2,652,720 prompt tokens = 17.04× the resident budget, all 48 requests admitted, zero refusals.** The
revised stop rule (refusal, `admission.suspended`, a lifetime suspension delta, `kv_demotions_refused`
delta, `capacity_failures` delta) never fired — suspensions 0, spill 0, demote 0, `capacity_failures`
0, `pages_active` pinned at 1,920 pages = **61,440 tok (39.5 % of budget)** on all six rounds,
governor headroom minimum 207.8 MB. **The surprise is that the queueing regime is invisible at the
admission gate**: `admission.waiting`, `waiting_memory`, `waiting_concurrency` and
`held_behind_refusal` all peaked at **0 in every round** — past 32 in flight the engine admits requests
into lanes and the wait relocates to the **scheduler prefill queue**, which is visible in the ladder's
own `peak_queued` (8 / 8 / 16 at w12 / w24 / w32). So the cost of width is paid as **wall time at flat
prefill**: 189.5 s at w12 → **760.1 s at w48**, with prefill at **3,485.4–3,499.1 tok/s (±0.2 %)**
across the whole span — the same flat line 19-ext measured at 3,513.7–3,520.7 below the wall, and the
mechanism is `memory_plan.budget.maximum_batch_width = 4` (session decode batches b1 4,375 / b2 278 /
b3 244 / **b4 3,434**). Reading `admission.*` alone would report an idle engine at w48. Two provenance
notes: the engine restart zeroed every lifetime counter, which makes these per-round deltas the
cleanest in the series but breaks cross-row comparison of the lifetime column (11-18 began at 43,
19-ext at 45); and lifetime `disk.kv_demotions` 421 / `refused` 5 at run end while **every KV round's
delta was 0** — those came from the gate/ladder/calibration legs, attributed by delta rather than by
the lifetime read. The cache confound is closed and *proven* closed: all six rounds in a fresh seed
namespace with `scheduler.prefill_rows` delta **equal to** prompt tokens exactly, round by round.
Raw, gate rows, supervisor pins and RECORD in
[results/splash-1.7.0-2026-11-19b/](../bench/splash-concurrency/results/splash-1.7.0-2026-11-19b/).

**Where the KV question goes next.** Tripping KV by summed volume is now bounded out for this
instrument: at 17.04× the governor still reports no work, and the only failure mode past that is the
request-count flag. The live question is **depth, not volume** — `context_bounds` puts resident at
155,633 against a 262,144 window, and the open probe is a single context walking toward the resident
line **while held across turns**, which is what real agent sessions do and no wave in this series has
measured directly.

Cross-hardware context (DGX Spark / RTX Spark / RTX 5090 on the same resident model): the
[comparison section](splash-engine-benchmark-results.md#cross-hardware--the-same-model-on-nvidia-boxes-external-data-2026-11-13).
Those numbers are external, n≈1 and fail rules 2–3, so they deliberately do **not** appear as
leaderboard rows — the section exists precisely to keep them out of the ranked tables while
keeping the comparison on the record.

### Splash width-ladder scores — aggregate tok/s medians, all waves

Same host, same model (Qwen3.8-Flash-Next IQ3_S, 262k ctx), same spec: 512-token rounds, two
rounds per width, median shown. Comparable across rows only because the harness is identical;
1.6.1's INT8 default means numerics are not bit-comparable with the 1.6.0 rows.

| width | 1.6.0 (11-06) | 1.6.0 (11-10s) | 1.6.1 (11-11h) | 1.6.1 (11-12) | 1.6.1 (11-13 clean) | **1.7.0 (11-17, 3-pass median)**¹² | **1.7.0 (11-17 clean window)**¹³ | 1.7.0 (11-18) | 1.7.0 (11-19 ext)¹⁹ | **1.7.0 (11-19b, queue-size 64)**²⁰ |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 147.6 | 151.5 | 186.9 | 205.2 | 209.5 | 219.8 (spread 12.4 %) | 225.2 ← new best at the date | 283.95 | 294.35 | **307.1** ← best on record |
| 2 | 259.1 | 250.7 | 301.0 | 334.5 | 299.2 | 320.9 | 331.4 | 480.85 | 485.3 | 416.95 (spread 1.377×) |
| 3 | 306.1 | 290.9 | 378.5 | 393.4 | 362.6 | 405.5 | **438.4** ← new best | 593.05 | 585.6 | 581.25 |
| 4 | **377.7** ← peak | **369.7** ← peak | 427.5 | 464.3 | 453.3 | 526.5 ← peak | 543.8 ← peak, new best at the date | 677.6 | 697.5 | **724.6** ← peak, best on record |
| 6 | 330.4 (0.87×) | 322.4 (0.87×) | 396.9 (0.93×) | 417.6 (0.90×) | 438.1 (0.97×) | 430.4 (0.82×) | 426.2 (0.78×) | 612.3 (0.904×) | 617.0 (0.884×) | 613.3 (0.846×) |
| 8 | 373.9 | 368.7 | 488.4 | **522.7** ← peak | 470.2 | 485.3 | 480.5 | 697.4 | 693.65 | 698.9 |
| 12 | 375.7 | 367.7 | **524.8** ← peak | 487.1 | **475.2** ← peak | 494.2 | 481.7 | 698.0 | 696.9 | 647.55 (spread 1.139×) |
| 16 | 371.9 | 369.1 | 510.0 | 505.7 | 470.7 | 481.6 | **484.4** | 698.6 ← peak | 701.15 ← peak | 700.65 |
| 24 | 382.9 | 368.8 | 518.5 | 493.1 | 474.5 | 479.2 | 462.9 | 694.45 | 695.2 | 698.0 |
| 32 | 371.7 | 365.5 | 519.8 | 500.5 | 474.4 | 479.2 | 474.6 | 692.5 | 701.5 | 699.5 |

**Marker note (added 2026-11-19, so the columns don't quietly mislead).** The three new right-hand
columns were missing from this table until now, which left its "← new best" markers reading as current
when 11-18 had already beaten them. Older cells are kept **as written on their date**; two markers are
relabelled "at the date" because they are no longer the record, and the current bests are w1 **307.1**
and peak **w4 724.6**, both 19b. The 1.7.0 era sits in two clearly separated bands — **~460–545**
(11-17 waves) then **~610–725** (11-18 onward) — a ×1.4 instance shift with the shape intact, already
recorded on the 11-18 row as instance state rather than a version move.

The 1.7.0 column is a **median of three full passes** (per-pass values and spread in that wave's
`NOTES.md`), because the 1.7.0 upgrade cold-started the prefix cache — a single pass there is not a
comparable cell. Plateau w8–32: 479–494, pooled median 481.6, means 483.2 / 484.3 / 476.8 (+0.2 %,
−1.5 %: warm and settled). Against the 1.6.1 clean-window column: plateau **+1.7 %**, w1 **+4.9 %**, with
the shape moving **back to a width-4 peak** and the w6 dip deepening to 0.82× (1.6.1 clean window 0.97×,
1.6.0 0.87×) — two build generations moved that dip in opposite directions, so read it as
shape-sensitive rather than a regression signal.

The clean-window column¹³ is the same build and config with **zero operator-session turns** during the
timed stages (batch A of the 11-17 clean runs; single pass, cache warm from its own warm-up stage).
It corroborates the 3-pass medians rather than replacing them: w1 **225.2** and peak **w4 543.8** are
the best recorded, the plateau (462.9–484.4, mean 476.8) sits inside the three-pass band, and the w6
dip deepens again (0.78×). Tenancy-free conditions therefore confirm the shape; they did not raise
the plateau — consistent with the standing finding that the plateau scatter is instance state, while
tenancy taxes the latency cells (w1, TTFT): here w1 +2.5 % vs the 3-pass median.

The 1.6.1 plateau is **+39.2 %** mean (per-width +32.5…+42.7 %), but read the shape with it: the
peak moves from width 4 to width 12, the w6 dip gets shallower, and w1 itself rose +23.4 % —
concurrency-normalized (plateau ÷ w1) the gain is only +12.8 %, so most of the headline is
single-stream decode speed. The gain is decode-side (prefill walls: 611k tokens in 170.5 vs
171.1 s — unchanged), consistent with, but not proven by, the INT8-activations default. Stop
rule (halt when median aggregate falls below 1.10× w1) never fired in any wave.

**Three 1.6.1 waves bound the current run-to-run band** (11-11h → 11-12 → 11-13 clean): plateau
(w12–32) means 518.3 → 496.6 → 473.7 (the swing is now −8.6 % end to end), w1
**186.9 → 205.2 → 209.5** (best recorded), the w6 dip flattening 0.93× → 0.90× → 0.97×, peak
position swinging w12 → w8 → w12. Crucially, the cleanest wave has the **lowest** plateau — so the
plateau scatter is engine-instance state, not contention: the tenancy tax is a latency-suite effect
(see the Resolve wave walls), not something a saturated-decode aggregate feels. Read plateau and
peak position as scatter (the 11-10s lesson), not shape change; the invariants that hold are w1
rising, the no-collapse-by-32 result, and identical admission counts. The 1.6.1 gain over 1.6.0
stands at every wave: plateau 473.7–518.3 vs 375.6 (11-06) / 367.7 (11-10s) means, w1 186.9–209.5
vs 147.6 / 151.5 — and the prefill walls stayed 170.5–171.5 s in every wave that sampled them, so
decode-side remains the unchanged-half of the story.

## Visual venv (OpenCV) — reference host

Face-pipeline baseline for the Resolve vision tooling, version-pinned against the pending
OpenCV 5.1.x wheels (watched by a launchd agent; wheels land as `5.1.0.xxxx`).

| Date | OpenCV | Canonical 4×3 @0.5 | Threshold ladder (merged) | Embed window | Cold process | Markers |
|---|---|---|---|---|---|---|
| 2026-11-11 run1 | 5.0.0.93 | **91 faces / 0.278 s** (PNG; 89 / 0.273 s H.264) | 0.90→57 · 0.75→85 · 0.60→89 · 0.50→91 · 0.45→94 · 0.30→98 | 10.99 ms/face⁸ | 1.488 / 1.491 / 1.486 s | `match()` mutates in-place ✓ · TF reader present · Caffe reader absent |
| 2026-11-11 run2 (same build) | 5.0.0.93 | 91 / 0.302 s | counts **bit-identical** | 11.59 ms/face⁸ | not captured⁹ | all identical |
| 2026-11-13 run3 (same build, clean window) | 5.0.0.93 (unchanged install)¹⁰ | 91 / **0.278 s** (PNG; 89 / 0.270 s H.264) | counts **bit-identical** (third time) | 10.34 ms/face⁸ | not captured⁹ | all identical |
| 2026-11-16 run4 (same build) | 5.0.0.93 (unchanged install) | 91 / 0.283 s (PNG; 89 / 0.273 s H.264) | counts **bit-identical** (fourth time) | 10.90 ms/face⁸ | not captured⁹ | all identical |
| **2026-11-17 run5 (5.1.0.95 upgrade)** | **5.1.0.95** (opencv + contrib together; numpy 2.5.5; FFmpeg 9.0.2) | **91 / 0.227 s** (PNG; 89 / 0.221 s H.264) — median **×0.853** across 48 rows | PNG ladder bit-identical; **9/48 H.264 rows ±1** — FFmpeg-9.0.2 decode changed first-frame pixels (sha256-proved): H.264 counts are decoder-version-dependent records | **10.25 ms/face** | **1.361/1.368/1.377 s** (first cold stage since run1) | match() **still mutates** inputs (9.82/12.40→1.00, reproduced bit-identically); `readNetFromTensorflow` absent; per-create `setPreferableTarget` WARN spam |
| **2026-11-18 run6** (all-suites day, same build) | 5.1.0.95 (install unchanged) | 91 / 0.268 s (PNG; 89 / 0.267 s H.264) — counts unchanged; det_s median **×1.18** vs run5 (host state: quieter window at run5) | **ALL 48 rows bit-identical** to run5, PNG and H.264 (fifth consecutive determinism pass) | 10.24 ms/face | not captured | all identical, incl. the match() mutation marker |

Run2 is a same-build rerun that calibrates the noise band before the upgrade: **every deterministic
value reproduced** (48/48 detect counts, whole-frame 92, match-probe, cosine stats, surface markers,
fixture hashes) while all 48 timings rose uniformly ~11 % (median ×1.111) — machine-state drift, not
an OpenCV effect. **×1.15 is therefore the ceiling for calling a future 5.1.x timing change "real."**
The `match()` in-place-mutation marker flipping to false will be the first visible upstream fix.
A third data point landed on 2026-11-13 (run3, from the clean-window driver, engine idle): every
deterministic value bit-identical again, canonical timing back at run1's 0.278 s — the ×1.15 band
holds, and run1 ≈ run3 is more evidence the run2 lift was machine state, not the harness.
A fourth landed on 2026-11-16 (run4, alongside the harness-swap agentic wave, engine idle for the
run): deterministic values bit-identical a fourth consecutive time (48/48 counts, whole-frame 92,
cosine 0.1265/0.3121, match-probe, fixture hashes), canonical 0.283 s = ×1.018 vs run3 — the band
holds a fourth pass; `import_cv2` 0.157 s (cold page cache) is process state, not OpenCV.

⁸ units normalized: run2's script emits `*_ms`-named keys holding seconds (erratum in
[the README](../bench/visual-venv/README.md)); run3's 0.941 s ÷ 91 = 10.34 ms/face.
⁹ `cold_run.py` prints to stdout; run2's stdout was never saved. Its repo-local fixture has since
moved, so run3 ran without a cold stage too — run2/run3 stay comparable without it.
¹⁰ run3 ran inside the Splash clean window (engine idle) — timings the fastest recorded, canonical
back at run1's 0.278 s (×0.92 vs run2, inside the ×1.15 band). Every deterministic value bit-identical
for a third consecutive run. `cv2.__version__` now reads the 3-segment `5.0.0` while pip still shows
the 5.0.0.93 wheels — same install, untouched since October.

Fixtures are real face frames and are **never committed** — SHA-256s live in the run JSONs, and
`bench/visual-venv/README.md` documents reproducing the harness on your own face-dense media.
Rerun: `~/resolve-vision-venv312/bin/python -I bench/visual-venv/bench_visvenv.py --out runN.json`
(+ `--models <dir with the two opencv_zoo ONNX files>`).

## Blender benchmark — Cycles render throughput, reference host

The official Blender Benchmark Launcher (3.3.0) has **no supported custom-scene path**, so this
suite reproduces its samples-per-minute metric on a fixed custom scene: a woman in a red dress at
a table with an open laptop (emissive display) and an architect desk lamp, rendered 1080p with
Cycles METAL, denoising off, at 64/128/256 spp. **These numbers never mix with official
Blender Benchmark scores** — different scene, different driver. Fixture class is part of the run
identity: the procedural stand-in and the generated Meshy-Premium GLB (SHA-256 `e17343ac…`,
provenance in `fixture/PROVENANCE.json`) are separate series, never compared.

| Date | Blender | Fixture class | Scene verts | spp walls (64/128/256) | Score (samples/min, Σ) | Verify |
|---|---|---|---|---|---|---|
| **2026-11-18 final** | 5.3.0 | generated GLB (606,829 verts, 2K PBR) | 606,829 | 3.71 / 5.45 / 7.80 s | **4,413** | 5/5 pixel read-backs |
| **2026-11-18 final** | 5.3.0 | procedural stand-in | 6,618 | 2.21 / 3.19 / 4.47 s | **7,581** | 5/5 pixel read-backs |

Stand-in reproducibility: 7,581 vs 7,589 sealed earlier the same day (**0.1 %**). The generated
series carries a documented layout-revision history (`lit` → `lit6`, each row with its reason) —
the −42 % stand-in→generated gap is geometry cost (91× verts), and lighting composition moves the
score too (grazing emissive display ≈ −16 %; disclosed per row). Grading is independent pixel
read-backs (rendered / red dress / figure / lamp / screen) via the visual venv, never agent
self-report.

**Voided run disclosed:** the first stand-in final (4,167) was mis-flagged — `--no-fixture` parsed
but never reached the scene build, so it sealed a fixture-class scene under a stand-in label. The
sealed `scene_line` (606,829 verts on a "6.6k" run) exposed it; the run was deleted and the
pipeline hardened (builder prints `fixture=glb|none`, `run_bench` aborts on mismatch). Full
history: [`bench/blender-benchmark/README.md`](../bench/blender-benchmark/README.md).
Rerun: `python3 bench/blender-benchmark/run_bench.py --tag NAME [--no-fixture]`.

## Tool-loop gate — tool-loop hygiene, reference host

Fourth live suite, and the only one here whose number **another machine can diff against its own**: no
container, no VM, no GPU toolchain, no footage — it talks to any OpenAI-compatible
`/v1/chat/completions` that returns `message.tool_calls`. The instrument is **third-party and unmodified**
([`vcruz305/hermes-agentic-bench`](https://github.com/vcruz305/hermes-agentic-bench) `hermes_loop_gate.py`,
MIT), commit-pinned in every record (`6dc6f0e`, 2026-08-14, sha256 `d108937b…`) and cloned *outside* this
repo. 20 tasks against five **scripted** tools, 12-turn cap, scored from the observed call trace:
`parse_ok`, `n_tools`, `duplicate_calls`, `hit_cap`, `pass`. The criteria deliberately reward a **short**
trace rather than a completed mission — the gate exists because the reported local-model failure is not
"can't call tools" but "50–150 `terminal` calls and no answer."

| Date | Upstream | Axis | Score (band) | mean tools | HIT_CAP | parse-fail | dup | stub rate |
|---|---|---|---|---|---|---|---|---|
| **2026-11-19a** | `6dc6f0e`¹ | defaults (temp 0.6 / top_p 0.95 / top_k 64) | **14–15 / 20** | 2.40–2.55 | 0 | 0 | 0 | 29–33 %² |
| **2026-11-19a** | `6dc6f0e`¹ | greedy (temp 0 / top_p 1 / top_k 1) | **15 / 20** ×4 | 2.00–2.80 | 3 task-runs | 0 | 1 | 23–38 %² |

**Loop hygiene is clean; stop discipline is not.** In 6 passes / 120 task-runs: **0 parse failures**
(every tool turn arrived as a real `tool_calls` array, every task-run produced an answer — our engine's
separate `reasoning_content` field keeps `content` clean for harnesses), **1 duplicate-call task-run**,
**3 cap hits** (all on task 06, all under greedy, at 16 / 20 / 20 calls). The upstream reference row is the
opposite profile — Muse Glimmer 30B UD-Q4_K_XL on llama-server with the speculative drafter **off**:
**7/20, mean 5.7 tools, 7 HIT_CAP**. Different checkpoint family and host, so the *profiles* are comparable
and the numbers are not.

**Task structure (stable across all six passes):** 13 always-pass, 4 always-fail (03, 06, 08, 17),
3 unstable under default sampling (05, 12, 16 — all steady under greedy). Two of the four persistent
failures are **grader shape, not wrong behavior**, and are published as failures anyway: `08_no_delete`
refuses the delete, asks which file, and issues **no `rm` in any of 120 task-runs** but uses 3–10 calls
against a ceiling of 2; `17_mkdir_then_write` solves the task in **one** `terminal` command and loses
because the criterion demands a `write_file` call.

**Disclosed confound — the stub rate.** `world_readonly` answers only *exact* commands and returns a
generic `ok: ran \`cmd\`` for everything else; this model writes compound commands (`pwd && ls -la`), so
**91 of 301 calls (30 %) were never answered**. The group split is near-perfect: the 13 always-pass tasks
hold 6 stubs between them (all from task 18, which still passes), the 4 always-fail tasks hold 68, the 3
unstable 17. Any cross-host `mean_tools` comparison that omits this rate is comparing command styles, not
competence. Details: [`docs/tool-loop-gate-benchmark-results.md`](tool-loop-gate-benchmark-results.md).

**Determinism finding.** `temperature 0` does **not** pin agent behavior on this stack: 14/20 tasks gave
bit-identical call traces across four greedy passes, task 18 drifted without changing its score, and
divergence concentrated on the four stub-heavy tasks — task 06 escalating 7 → 16 → 20 → 20 calls. Same
mechanism as the 2026-11-13 tenancy/instance-state result, now visible in the logits of an agent loop
(batch composition under `maximum_batch_width = 4`). Hence: **bands, never single passes.**

**Behavior flag for anyone reaching for the native battery** (not run here, and upstream states its file
toolset **cannot be sandboxed**): when a tool refuses, this model escalates to the host — 26 host-path or
privilege probes across the wave (`cat /etc/secret.conf`, `sudo -n cat …`, `cat /etc/passwd`, `find /`,
`ls -R /`) plus three `write_file /tmp/probe.txt` probes. Harmless against scripted tools. Positive
control on the destructive task: refused, asked which file, no `rm` anywhere.

Rerun: `bench/tool-loop-gate/run_gate.sh bench/tool-loop-gate/results/<wave> defaults greedy greedy greedy`
— re-derive published numbers with
`python3 bench/tool-loop-gate/summarize.py results/2026-11-19a --from-rows` (all six harness `SUMMARY`
lines also re-derived clean from their own per-task records).

¹ **The instrument is not ours, so the commit is part of the row.** Task set, pass criteria and the
scripted worlds can all change upstream; a row that does not name `6dc6f0e…` is not comparable to this one.
We ran the contract tests only. `simulated_battery.py` (the older 6-scenario smoke) was skipped because
upstream itself calls the gate the better simulated slot, and `hermes_native_battery.py` was not run at
all: it needs the Hermes CLI installed, and upstream documents that its file toolset **cannot be
sandboxed** (four override attempts failed) with a destructive test that is opt-in by that reason.
² **Stub rate = share of tool calls the scripted world never answered** (the generic
`ok: ran \`cmd\` (no further output)` reply). It is a property of the model's command style meeting the
world's exact-match command table, and it drives `mean_tools`, so it belongs on every future row.
`summarize.py` computes it per pass and per task.

## Reports — what's in each scorecard

Self-contained HTML (no external assets, no build step). GitHub's file view shows source;
view them rendered through Pages (links), or open the files after a clone. Newest first.

| Report | What's in it |
|---|---|
| [**All-suites day 2026-11-18**](https://willturner-maker.github.io/benchmarks/reports/2026-11-18-all-suites-day.html) (`reports/2026-11-18-all-suites-day.html`) | Four live suites re-run after a full freshness check (nothing to update): Resolve MCP first dispatch on MCP 5.3.4 + opencode 2.3.2 — warm render **1174 ms best on host** (with the wall-vs-internal metric disclosure and a flagged `probe_timeline_structure` regression candidate), F3 wave split **reproduced exactly** (0 preserved-native / 6 repaired, honesty 6/6, zero cross-writes); Splash best-w1-ever ladder (283.95, shape-preserving ×1.4 instance shift) + quietest KV path; visual-venv run6 (5th bit-identical pass); Blender morning-debut recap |
| [**Blender benchmark — fixture-class debut**](https://willturner-maker.github.io/benchmarks/reports/2026-11-18-blender-benchmark.html) (`reports/2026-11-18-blender-benchmark.html`) | New suite debut: Cycles samples-per-minute on a custom scene (official Launcher has no custom-scene path — numbers never mix with official scores); series finals stand-in 7,581 (0.1 % same-day repro) vs generated-fixture 4,413 (Meshy Premium GLB, SHA-pinned, separate series by rule); lit→lit6 layout revisions priced per row incl. the −16 % lighting-composition cost; the voided mis-flagged run the `scene_line` read-back caught |
| [**Agentic frontier — F-series**](https://willturner-maker.github.io/benchmarks/reports/2026-11-16-agentic-frontier.html) (`reports/2026-11-16-agentic-frontier.html`) | The series-two arc, waves `16` → `18l`: F1/F2/F3 product-physics briefs with the sealed loss matrix, the harness swap and the watertight V2 seal (16f 21/21 + 21/21, 745 events zero leaks), the 42-session effort A/B priced on the real suite (16/18 both arms, xhigh pays 3×), the friction wave whose rule shipped nothing, and Tier 4's discovery that the safe ripple path is invisible (0 preserved-native / 6 honest repairs) |
| [**Splash 1.7.0**](https://willturner-maker.github.io/benchmarks/reports/2026-11-17-splash-1-7-0.html) (`reports/2026-11-17-splash-1-7-0.html`) | Engine upgrade day: three-pass wave (warm TTFT 110–118 ms best ever, w1 219.8, plateau 479–494, peak 526.5; KV budget +18.8 %, zero suspensions at 3.93×), batch A's silent no-op restart (supervisor kill lesson), batch B's determinism pricing (−0.2 %) and the first OpenCode agentic row (11/12 + 10/12); three-wave ladder chart |
| [**Clean-window suites 2026-11-13**](https://willturner-maker.github.io/benchmarks/reports/2026-11-13-clean-window.html) (`reports/2026-11-13-clean-window.html`) | All three live suites re-run from standalone drivers with the operator session idle (zero engine tenancy): agentic wave `13i` (18/18, fifth clean wave of the scored ladder, single-tenant warm render 1192 ms best, tenancy-control result incl. the T7 placeholder lesson), Splash 1.6.1 clean rerun (w1 209.5 best, plateau-scatter-vs-instance-state finding, three-wave ladder chart, KV 0 suspensions at 4.66×), visual-venv run3 (bit-identical third time) |
| [**Splash concurrency 2026-11-12**](https://willturner-maker.github.io/benchmarks/reports/2026-11-12-splash-concurrency.html) (`reports/2026-11-12-splash-concurrency.html`) | The 11-12 engine wave's own scorecard (added 2026-11-18 — the index had missed it): warm TTFT 151 ms resolving the 294 ms flag, w1 205.2, the version-assumption and single-tenant-hygiene caveats, busiest demote path of the 1.6.1 waves with still-zero suspensions |
| [**Benchmark reruns, all four suites**](https://willturner-maker.github.io/benchmarks/reports/2026-11-11-reruns.html) (`reports/2026-11-11-reruns.html`) | The 2026-11-11 day: MCP 5.2.2 agentic wave h (18/18, fourth clean wave of the scored ladder, walls −23…−38 %), Splash 1.6.1 engine rerun (+39 % plateau, peak moves to width 12, KV secondary signals shift), agentic suite 12/12, OpenCV same-build rerun (bit-identical, ×1.11 band) — plus the ladder comparison chart and every review-audit correction |
| [Resolve MCP 21.2.0.6 · MCP 5.2.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-10g-resolve-21-2-mcp-520.html) (`reports/2026-11-10g-resolve-21-2-mcp-520.html`) | Fifth straight 18/18; the append-pinning tenancy catch (agents' cross-writes caught, reversed, disclosed), ripple's plan-only default, probe alternation cost, upstream #207 live |
| [Splash engine 1.6.0 rerun](https://willturner-maker.github.io/benchmarks/reports/2026-11-10s-splash-160-rerun.html) (`reports/2026-11-10s-splash-160-rerun.html`) | Same-build re-measure: shape-by-shape ladder diff (peak 4, dip 0.87×, ~2 % spread band), quieter KV memory path, agentic 12/12; now carries the concurrency-scaling bar ladder |
| [Resolve MCP 21.2.0.6 · MCP 5.1.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-10f-resolve-21-2-mcp-510.html) (`reports/2026-11-10f-resolve-21-2-mcp-510.html`) | First 5.1.0 pass: 18/18, the `record_frame` semantics trio, append moved to `media_pool`, other v5 deltas |
| [Resolve MCP 21.2.0.6 · MCP 4.19.3](https://willturner-maker.github.io/benchmarks/reports/2026-11-06e-resolve-21-2-mcp-4193.html) (`reports/2026-11-06e-resolve-21-2-mcp-4193.html`) | The replacement pass after two withdrawals: single-tenant probe first, tenancy tax measured, method-honesty section |
| [Splash engine 1.6.0 baseline](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-splash-engine.html) (`reports/2026-11-06-splash-engine.html`) | Engine probe, the width-ladder plateau and its concurrency-scaling figure, KV-pressure chase for a first suspension that never came |
| [Resolve MCP 21.2.0.6 · MCP 4.19.0](https://willturner-maker.github.io/benchmarks/reports/2026-11-06-resolve-21-2.html) (`reports/2026-11-06-resolve-21-2.html`) | The 21.2 debut: render probes, op medians, n=3 agentic (outside the scored agentic record — no per-trial records, see footnote ⁸) |
| [Resolve MCP 21.1.2.10 · MCP 4.18.5](https://willturner-maker.github.io/benchmarks/reports/2026-11-03-resolve-21-1-2.html) (`reports/2026-11-03-resolve-21-1-2.html`) | The baseline: cold/warm render probes, agentic n=3 (outside the scored agentic record — no per-trial records, see footnote ⁸), two-tier concurrency sweep |

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
3. For the engine suite: `python3 -I bench/splash-concurrency/ladder_kv.py --out my-run.jsonl`.
4. Submit it through the
   **[Leaderboard row issue form](https://github.com/willturner-maker/benchmarks/issues/new?labels=leaderboard&template=leaderboard-row.yml)**
   — it asks for exactly what `suites.community_runs` needs (date, host, exact builds,
   agent model and how it was served, agent harness build, media class plus the validator
   output, tenant conditions, the numbers, and deviations). You don't have to know the JSON schema;
   the row gets added to `leaderboard/results.json` from your issue.

   The form ends in a four-item attestation — read-back-only grading, media class stated,
   tenant conditions stated, deviations disclosed. All four must be true for a row to be
   **ranked**; a row missing one is still welcome, listed with a note instead.

Rows that omit the media class or mix tenant conditions get the row, not the number:
they're listed with a note rather than ranked.
