# Quant memory accounting — method notes (2026-11-15)

Supports the *Quant memory accounting* section of
[`docs/splash-engine-benchmark-results.md`](../../docs/splash-engine-benchmark-results.md): what
"bpw" actually scopes on this checkpoint, what a quant costs in **resident** RAM (as opposed to
download bytes), and whether raising `--max-memory` / `--ple-memory` would buy throughput.

## Host / stack

Apple M5 Ultra, 96 GiB unified, macOS 27.2.0. Splash **1.6.1**,
`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S`, launched from `~/start-resolve-ai.sh` as
`serve-native <resolved-snapshot> auto 60129542144 274877906944 --persistent-cache on`
(= 56 GiB working set, 256 GiB SSD cache; **no `--ple-memory`, no `--expert-memory`, no
`--revision`** — both are at `auto`). Resolve **not** running during these probes.

## Files

- `banner.txt` — the engine's own startup printout (from `~/Library/Logs/splash/splash.err.log`) plus
  the two live process command lines, `$HOME` rewritten to `~`. **This is the primary source**: Splash
  prints every allocation (table row cache, expert store, KV floors, cache quota) at startup. If you
  want the numbers again, read the banner — don't re-derive them from file sizes.
- `residency.txt` — `/usr/bin/footprint -p <engine pid>` (header + category table), `lsof` for the
  open GGUF blobs (fd, size, fd offset), `vm_stat`, and the engine cache directory listing.
- `decode-probe.log` — `iostat -d -w 1 -c 14` around one 900-token generation; three identical
  repeat requests; a 4 GiB sequential read of the n-gram shard; `vm_stat` after.

## Why these measurements and not others

- **No mmap.** `vmmap --summary <pid>` shows **no MAPPED FILE section at all**, so none of the GGUFs
  are file-backed in the process. The engine holds fd handles and does positional reads (the shard fd
  offset does not move across a request). llama.cpp-style "mmap the table" language in the model card
  does not describe this engine.
- **`footprint` over `ps`/`top`:** the header prints decimal GB (`56 GB` = 52.15 GiB) — always convert
  before comparing to `vm_stat` or the `GiB` figures elsewhere in this repo.
- **Cost of the probes:** four 900-token generations (~3,600 output tokens) plus one 59-token prompt
  each, on the live engine, no restart.

## Gotchas — read before quoting any number here

- **`iostat`'s first sample is an average since boot**, not a one-second rate — that is why row 1 of
  `decode-probe.log` reads 111 MB/s while the following rows read ~0. Read the deck from the second row;
  the five decode seconds there are 961 / 530 / 1,236 / 1,636 / 2,044 MB/s (mean 1,282).
- **`iostat` on macOS does not split reads from writes.** The ~1.28 GB/s during decode is *total*
  device traffic: expert fetches plus KV/state write-through. Treat it as an upper bound on the
  streaming read cost, not a pure read figure.
- **Decode tok/s at n=1 is noise on this engine.** Same prompt, same config, back-to-back:
  160.2 / 190.2 / 244.6 tok/s in one set, 170.3 / 157.5 / 149.3 in another an hour earlier. That is a
  **~149–245 tok/s spread band**; nothing below ~25 % is measurable without many repeats. (The engine
  also warns about this in a different direction: `--verify-rows auto` on a MoE target means "greedy
  and seeded outputs can differ from run to run", so temperature-0 does not imply determinism.)
- **The dd figures are page-cache reads, not device reads** (4 GiB in 0.21 s = 20.6 GB/s). That is the
  finding, not a mistake: the OS already caches those exact table pages and serves them at memory
  speed. No `sudo purge` was available to force a cold device measurement, so no true NVMe ceiling is
  recorded here.
- **`vm_stat` "wired down" is not stable across the session**: 405,363 pages (6.6 GB) at one sample,
  3,845,771 (63.0 GB) at another, with the engine's `footprint` unchanged at 56 GB between them.
  Wired-vs-pageable state of the Metal buffers moves with request activity and idle-release; only
  phase-labelled sampling makes it interpretable (see `bench/resolve-ram-coexistence/`).
- **A probe bug worth disclosing:** the first sparse-read attempt computed its seeks wrong and read to
  EOF per seek, pushing ~918 GB **read-only** through the page cache in 68 s. Nothing was written and
  no config changed, but it churned the file cache, so measurements taken immediately after it may see
  more cache re-fill than a clean window would.
- The implied bpw values for the third-party quant builds (`UD-Q3_K_XL` ≈ 3.9, `UD-IQ4_XS` ≈ 4.15)
  rest on an **assumption** that those builds carry the same 26.82 GiB n-gram table; that was not
  verified against their files.
