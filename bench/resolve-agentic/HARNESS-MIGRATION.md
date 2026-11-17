# Harness migration: Claude Code out of the rotation (2026-11-16)

This bench has run two harnesses against the same local model: **Claude Code** (via
`splash claude`, harnesses `wave_driver.py` / `wave_driver_f1f2_opencode.py` era) and
**OpenCode**. The 2026-11-16 waves settled the comparison, and Claude Code has been
**uninstalled from the bench host** and dropped from the rotation. This document records
why, what survives for calibration, and what would reverse the decision.

## The evidence (same model, same tasks, same grading)

Seven tasks × 3 trials, model `Qwen3.8-Flash-Next IQ3_S` on a loopback Splash engine,
Resolve MCP trio, fail-closed grading against a pre-dispatch hash-sealed ground truth.

| wave | harness | MCP | outcome | honesty | seal audit | cost |
|---|---|---|---|---|---|---|
| 2026-11-16 | Claude Code 2.1.325 | 5.2.11 | 21/21 (hard 15/15) | 21/21 | 0 / 585 | $34.55 |
| 16b–16e | opencode 1.19.5 | 5.2.11→5.3.0 | up to 21/21 | 21/21 | leaked in 3 of 3 | $0 |
| **16f** | **opencode v2.3.0** | 5.3.0 | **21/21 (hard 15/15)** | **21/21** | **0 / 745** | **$0** |

Efficiency: 16f ran the wave in 3,743 s wall / 403 turns vs Claude's 4,983 s / 711 turns
(−25% wall, −38% turns, ~10× fewer generated tokens, $0 vs $34.55). Outcome is a
statistical tie — Wilson 95% on the hard set: Claude [79.6, 100] vs OpenCode V2
[78.6, 100]. **The case for removal is not capability.**

## Why that justifies removal *from this bench*

The prior verdict (`FINDINGS-2026-11-16.md`) kept exactly one differentiator: *"pick
Claude Code when the seal must be watertight."* Wave 16f eliminated it — the V2 `policies`
layer (hard denials, mechanism verified by the 10-probe battery in `SEAL-V2-2026-11-16.md`)
sealed 21/21 trials with zero leaks, a strictly stronger mechanism than the V1-era
permission config that leaked in every opencode wave before it. With the seal equalized,
Claude's remaining role was **calibration axis** — the reference point that proved
OpenCode's speed claims and localized its leaks. That role survives as **archived data**:
the Claude wave's 21 trials, walls, costs, and verdicts are in `results-2026-11-16.json` /
`FINDINGS-2026-11-16.md`, hash-comparable to future fixture families. Re-measuring Claude
would only be needed if the local stack's results became suspicious — and the local stack
now has a cleaner seal than the reference ever had.

## What changed on the bench host

- **Claude Code removed 2026-11-16** (binary, `~/.claude`, `~/.claude.json`, app-support and
  cache residue, ~2.4 GB; configs archived off-repo at mode 600 first).
- `wave_driver.py` (the Claude-era driver) reads `~/.claude.json` and is now **historical**:
  kept for reproducing the archived waves' record shape, not runnable on this host.
- The sealed pool is OpenCode-only: `wave_driver_f1f2_opencode_v2.py`, seal stack per
  `RUNBOOK.md` §2 (OPENCODE_CONFIG env channel + `policies` hard-denials + global-context
  rename + live per-trial audit), now including `plugin.use *` + `lsp` tool denies and a
  `seal_host_hygiene()` fail-closed check (LSP plugin added 2026-11-16, project-scoped only).

## Deliberately NOT claimed

This bench measures MCP-only tool use over 21-trial waves. It is **silent on long-horizon
coding work**, where an API-model harness may still be better; the removal decision covers
the benchmark rotation and the Resolve agent path (`resolve-ai-workflow`), nothing else.

## Tripwires that would reinstate a reference harness

- Any wave with a non-MCP `tool_use` event (the audit is cheap and automatic).
- An outcome cliff on a new fixture family that a reference harness passes.
- An honesty break (final table ≠ read-backs) at more than 1/21 trials.

## Pointers

- `FINDINGS-2026-11-16.md` — harness comparison + the "watertight seal" verdict being reversed
- `FINDINGS-2026-11-16f.md` — the closing wave
- `SEAL-V2-2026-11-16.md` — seal mechanism, probe battery, server-reuse caveat
- `RUNBOOK.md` §2 — the V2 seal stack operators must run
- Published analysis: *The Local Ceiling* (wave-16f writeup, on the publishing volume — off-repo by convention)
- Workflow-side companion: `willturner-maker/resolve-ai-workflow` → `HARNESS-MIGRATION.md`
