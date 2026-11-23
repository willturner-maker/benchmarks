# 8-lane ladder — `--max-concurrent-requests=8` on 1.7.1 (Tier 2 of the transition)

**Wave:** 2026-11-23 backlog chain S4 (11:27–11:52Z). Engine restarted from pinned argv plus the one new flag;
identity-verified relaunch (supervisor pid 34368, `status_ready_8lane.json` shows `maximum_batch_width: 8`).
**Pin restored unconditionally afterwards** (supervisor 34982, ready, identity-checked).
Instrument: unmodified `kv_bracket_2026-11-19b.py` (same as the 1.7.0 width ladder), widths 1,2,3,4,6,8,12,16,24,32,
two rounds each, then KV-pressure stages (425-line ≈55,265-token prompts) at widths 1–32.

**Pre-registered prediction (Tier 0, commit `1401ae6`):** lane-state arithmetic ~1,105,985,536 B for 8 lanes vs
60,129,542,144 B hard cap → launch should be admitted. **Confirmed** — and the engine's own boot line agrees:
*"A concurrency limit of 8 (--max-concurrent-requests) streams the routed experts through 45.5 GiB; 4 would
stream it through 45.8 GiB"* (8 lanes are marginally *cheaper* for weight streaming).

## Decode ladder (aggregate tok/s, medians of 2 rounds)

| width | 1 | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 24 | 32 |
|---|---|---|---|---|---|---|---|---|---|---|
| 8-lane 1.7.1 | 304 | 481 | 579 | **701** | 698 | **692** | 700 | 688 | 681 | 680 |
| 4-lane 1.7.0 (11-19b) | 304 | 481 | 579 | 701 | 698 | 692 | 700 | 688 | 681 | 681 |

**The plateau is identical.** Doubling the lane ceiling buys nothing: aggregate throughput saturates at width 4
(~700 tok/s) on both epochs; at w8 per-stream falls to ~87 tok/s with no aggregate gain. τ²-class workloads are
decode/bandwidth-bound, not lane-bound — the same conclusion the 1.7.0 ladder reached, now confirmed from the
other side (raising the ceiling changes nothing below it either).

**New visible mechanic above the ceiling:** with `max_concurrent=8`, requests beyond lane capacity park in
`admission_waiting` (exactly `width − 8`: 4/8/16/24 at w12/16/24/32) rather than the request queue; `queued`
stays 0 until w32 (peak 15). Admission-waiting, not queueing, is the pressure valve above the lane cap.

**KV pressure (1.77 M prompt tokens = 11.4× lane budget at w32):** 0 refusals, 0 suspensions, 0 spill, 0
demote, `pages_act` flat at 1920, prefill throughput flat at ~3,490 tok/s from w1 to w32. The memory-pressure
machinery never engaged — Tier-0's "possible refusal" branch did not fire, and the KV shortfall arithmetic from
earlier stacks overstayed: at 8 lanes 32×55k-token prompts are simply served.

Confound disclosure: this run's warmth gate printed `cold` (spread 1.801, decode 167→302 tok/s early); the
ladder ran after the gate and its plateau matches the 1.7.0 baseline table above, so comparability is intact.
