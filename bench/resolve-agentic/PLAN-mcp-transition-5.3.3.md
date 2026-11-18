# PLAN — harness transitions before Tier 3: MCP 5.3.1 → 5.3.3, opencode 2.3.0 → 2.3.1

## Transition executed — 2026-11-18 (later): MCP 5.3.3 → 5.3.4 (user-flagged, cheap-diff path)

- **Instrument sealed first**: `mcp_fingerprint.py` v1 (the 5.3.1→5.3.3 pair was captured with
  ad-hoc greps whose method was never committed — the METHOD is now pinned: sha256 anchors on
  `src/server.py`, the vendor tree and the advanced-server executable tree, regex-pinned counts).
- **Pre-sync fingerprint** (`mcp-fingerprint-pre5.3.4.json`): installed tree byte-identical to the
  pinned post-5.3.3 record (server.py sha `73d706f3…`) — the Python half was exactly the last
  benched state (Tier 3/4 ran on it).
- **Sync**: `npx -y davinci-resolve-mcp@latest sync` → 5.3.4 (marker `updatedAt` 22:53 UTC).
- **Post-fingerprint diff**: exactly TWO fields moved — `package_version`, and `server_py_sha256`
  (`73d706f3…` → `1d061c96…`). The release notes claimed "documentation only"; the changed hash
  demanded the diff rather than the claim: **full-tree audit against the v5.3.3 tag
  (byte-identical to the pinned 5.3.3 record) shows the ENTIRE executable delta is the `VERSION`
  string in `src/server.py` plus the same in `src/granular/common.py`** (4 diff lines total).
  `bin/` and `resolve-advanced/` identical; the tool-name set (256 FastMCP defs), action-branch
  counts (788), vendor tree hash and executable tree hash all unmoved.
- **Skill-docs containment check**: `SKILL.md`/house-style content appears nowhere in
  `src/server.py` — the new conventions never enter the agent tool surface, so trial contexts
  are unaffected.
- **Trap re-arm: NOT run, with the evidence-based reason recorded** (this is the transition
  protocol's own escape clause, used on proof rather than on the release notes): every byte that
  could change trap physics — `server.py`, the granular handlers, `bin/`, the vendor codecs — is
  identical modulo two version strings. The F2/F1/F3 fork physics ran their last live probe on
  the byte-identical 5.3.3 tree the same day.
- **In-memory caveat**: both server processes (started 14:38 local, pre-sync) still run 5.3.3
  code; 5.3.4 binds at the next MCP reconnect/launch. Provenance: waves from the next dispatch
  on record MCP **5.3.4**; Tier 3 (`18k`) and Tier 4 (`18l`) stay labelled **5.3.3**.
- Evidence: `mcp-fingerprint-{pre,post}5.3.4.json`; instrument `mcp_fingerprint.py` (reusable for
  every future move).

---


## Transition executed — 2026-11-18, all steps green

- **Install**: `npx -y davinci-resolve-mcp@latest sync` → **5.3.3** (python `server.py` sha
  `73d706f3…`; registry unchanged at 341 tools / 662 action branches — correct, because 5.3.2/5.3.3
  live in the **Node advanced-server vendor codecs** (`drx-codec` extractOFXTools present; 35
  RangeError sites in `drp-format`/`drt-format`). The pre/post fingerprints cover both halves.
  `opencode upgrade` → **2.3.1** (binary sha `25b6895d…`).
- **opencode confirmations**: mangled-name error text byte-identical (Tier 2 premise holds);
  `CLAUDE.md` fallback live-probed ACTIVE; `seal_host_hygiene()` now fails closed on
  `~/.claude/CLAUDE.md` or any repo-tree `CLAUDE.md` while AGENTS.md is hidden.
- **Trap re-arm** (`rearm_trap_533.py`, fresh fixture `_mcp_17j_rearm`, direct MCP calls replaying
  the published 17h transcripts' exact params, n=3 per trap):
  F1 `replace_source_range` lost = {speed, retime, audio_in_step, link} **3/3 identical**, grade/
  transform/crop survive, source read-back 5999→6220 (the documented DF-off-by-one, inside the
  ±1 tolerance); F2 `ripple_insert` lost = {grade, link} **3/3 identical**; T8 comp_count 1; T2
  markers still frame-keyed dict with the pinned payload keys. **No fixture re-arm event.**
  Instrument lesson: `get_items` rows carry no source ranges — geometry must come from
  `probe_timeline_structure` (the channel every published grader already used); deriving
  `audio_in_step` from get_items rows silently degenerates to `None==None`.
- **5.3.3's own change** (`probe_drptime_533.cjs`, 11/11): StartFrame/StartTC agree at 29.97 DF
  (108000 → `01:00:00;00`-mode label `01:00:03;18`, matching an independent SMPTE 12M calc and
  round-tripping); label-only `01:00:00;00` → frame 107892; `;` at 24 fps raises (DF only at
  29.97/59.94); malformed/out-of-range/skipped-DF labels raise `RangeError` instead of writing a
  wrong start. One probe case was fixed, not the module: `00:00:00;15` is a VALID DF label
  (12M skips ;00/;01 at non-tenth minutes only).
- **Decision (step 5)**: all expectations hold → dated entry here, **no wave re-run**. The 17h
  21/21 and 20/21 records stay labelled MCP 5.3.1 / opencode 2.3.0; from the next wave on,
  provenance records MCP 5.3.3 / opencode 2.3.1 (+ Tier 2's adopted B-rule trial context).
- Teardown: `_mcp_17j_rearm` deleted (logged); evidence = `rearm-traps-_mcp_17j_rearm.json`.

---


## Addendum (2026-11-18): opencode 2.3.1 (user-flagged, https://github.com/anomalyco/opencode/releases/tag/v2.3.1)

Same rule as the MCP update: **no install mid-probe** — the Tier 2 probe launches `opencode run`
sessions continuously, and the harness binary is part of what those sessions measure. All published
17h/17g waves ran on **2.3.0** (binary sha256
`9f3147cae4ca323827d3ca39451b0d3431b2906e79a08e9b09d1eb34bb703f52`, 223 583 968 bytes).
Read of the release notes against this bench:

- **Seal hazard (the one that matters):** 2.3.1 re-enables `CLAUDE.md` fallback — a directory with
  no `AGENTS.md` reads `CLAUDE.md`, and a missing **global** `AGENTS.md` falls back to
  `~/.claude/CLAUDE.md`. Our probe/wave protocol *deliberately hides* the global `AGENTS.md`
  (rename to `.bench-hidden`) during runs — on 2.3.1 that rename would activate the fallback.
  Checked 2026-11-18: `~/.claude/CLAUDE.md` and every bench-dir `CLAUDE.md` **do not exist**, so
  today it is latent. Any future wave on 2.3.1 must extend `seal_host_hygiene()` to fail closed if
  `~/.claude/CLAUDE.md` or any `CLAUDE.md` in the tree exists while AGENTS.md is hidden.
- **Nothing about tool-name lookup changed** — no alias/suggestion mechanism appears in the notes,
  so the Tier 2 premise (fix must be prompt-side) holds on 2.3.1 too. Worth a 1-call confirmation
  after install (type a mangled name, check the error text is unchanged).
- Background compaction is now on by default. Trials are short, but a future wave should set
  `compaction.background: false` in the trial config to keep behaviour comparable to the 2.3.0 records.
- Removed config keys (`shell_timeout_background`, `experimental.background_compaction`) are absent
  from `trial_config()`, verified — configs keep loading regardless. Shell-timeout-to-background is
  a behavior change only for trials that use the shell tool, which ground rules forbid.
- Decision: install after Tier 2 closes (same window as the MCP sync), confirm the two probes above,
  and record the new binary sha in the next wave's provenance. Tier 1's ceiling stays labelled 2.3.0.

---


Trigger: user-flagged release https://github.com/samuelgursky/davinci-resolve-mcp/releases/tag/v5.3.3
(installed: **5.3.1**). Sequencing: **after** the Tier 2 naming probe finishes — the probe measures
the current surface, and upgrading mid-probe would confound its three variants.

## What actually changes (read from the release notes, not assumed)

- **5.3.2** — `extractOFXTools` decodes OFX choice menus (`{choice: index}`) and RGB colors
  (`{rgb:[r,g,b], alpha?}`) instead of returning `null`; measured by the author on Resolve 19.1.3
  stills only. Bench impact: our fixtures grade with built-in tools (`Primary Balance`,
  `Saturation, Hue & Lum Mix`), so `probe_node_graph` expectations should be unaffected — but that
  prediction is what step 3 tests.
- **5.3.3** — DRP/DRT timeline writer: `<StartTC>` label now agrees with `<StartFrame>` in the
  caller's counting mode; drop-frame applied only at 29.97/59.94 (SMPTE 12M); unparseable labels no
  longer become frame 0; out-of-range fields no longer counted as valid; **an invalid start
  timecode now throws `RangeError`** instead of writing a wrong start. Offline-tested only, no
  timeline imported into Resolve by the author.
  Bench impact: this is the drop-frame area our whole suite carries a caveat for (media is 29.97 DF;
  record starts are `01:00:00:00` = frame 108000). Fixtures use `create_timeline` +
  `append_to_timeline`, not the DRP writer — but an agent can reach the writer, and a silent-wrong
  value becoming a thrown error is exactly the class of change that flips a trial outcome.

## Pre-upgrade fingerprint (captured 2026-11-17, from disk — no live MCP call during the probe)

`mcp-fingerprint-pre5.3.3.json`: package 5.3.1, `src/server.py` sha256
`362e6a80944b9817013292e1956569a7686c761c4d5c727d6834a0b8b3af810d`, 36 542 lines, **341** registered
tool names, **662** action branches, 17 drop-frame mentions, 30 StartTC/startFrame mentions,
`extractOFXTools` **absent**, 19 ValueError/RangeError guards.

## Steps

1. **Install** with the safe-update recipe (resolve-ai-workflow README):
   `npx -y davinci-resolve-mcp@latest sync`, then reconnect **both** MCP servers and prove it by
   **tool count**, not the version string.
2. **Post-fingerprint + diff** → `mcp-fingerprint-post5.3.3.json`. Expect `extractOFXTools` present,
   more startTC guards, and no shrinkage in the tool/action counts (a shrink means actions moved or
   were removed: read the diff before trusting any grading run).
3. **Trap re-arm probe** (existing pattern: `probe_build_sweep.py`): re-measure the loss sets on a
   scratch project rather than trusting the comment in `grader_selftest.py`, which pins them to
   5.2.11/Resolve 21.2.0.6 while both 17h passes ran on 5.3.1. Must still hold:
   - F1 `replace_source_range`: speed, retime, audio-in-step (and link) destroyed;
     grade/transform/crop survive.
   - F2 ripple insert after a transition: grade **and** link of the shifted clip destroyed
     (measured 6/6 in 17h); transition survives.
   - T2 marker payload shape, T8 `add_comp` → `get_comp_count` 1.
   Any change is a **fixture re-arm event**: update the expectation with a dated note, and never let
   a new build quietly satisfy an old expectation.
4. **New-behavior probe for 5.3.3's own change** (the part no release test covered against Resolve):
   on a 29.97 DF scratch timeline with `startFrame 108000`, exercise the DRP/DRT path and check
   (a) `<StartTC>` reads `01:00:00:00` in DF counting, (b) a malformed or `;`-at-non-drop-frame
   label now **raises** instead of writing a wrong start, (c) `create_timeline`/`append_to_timeline`
   behavior the fixtures depend on is unchanged.
5. **Decide, don't assume:** if steps 3–4 all match, record a dated version-transition entry and
   keep the 17h 21/21 ceiling labelled 5.3.1 (no wave re-run). If any expectation moved, run a small
   re-baseline (2 reps of the affected briefs) before drawing any Tier 3 conclusion, and disclose
   which MCP version each number came from.

## Also fixed because this surfaced it

The published 17h aggregate did not record the community MCP server version — only Resolve 21.2 and
opencode v2.3.0. Added to `results-baseline-2026-11-17h.json` (with a dated `record_amendments`
entry: an addition, not a rewrite), so future version comparisons have something to compare against.
