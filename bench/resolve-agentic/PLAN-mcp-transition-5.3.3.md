# PLAN — harness transitions before Tier 3: MCP 5.3.1 → 5.3.3, opencode 2.3.0 → 2.3.1

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
