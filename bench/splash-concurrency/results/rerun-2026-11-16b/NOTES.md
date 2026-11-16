# Rerun 2026-11-16b — same build (assumed 1.6.1), DIRTY window: operator tenancy + first KV trip

Trigger: standing re-run entry point (`python3 -I ladder_kv.py`) as part of the 2026-11-16
suite refresh. Engine not restarted (SSD cache state is part of the measurement); the engine
had served the 21-trial agentic wave earlier the same day. No separate TTFT probe this run
(`engine_probe.py` not invoked), so no TTFT cells.

**Ladder medians:** w1 92.6 / w2 181.3 / w3 230.5 / w4 454.8 / w6 463.7 / w8 514.7 /
w12 523.6 / w16 508.7 / w24 525.5 / w32 540.5; stop rule never fired (min post-w1 ratio
1.96x w1 — the ratio floor is meaningless when w1 itself is the outlier).

**Why this wave is NOT shape-comparable:**
- **w1 92.6 is the lowest w1 ever recorded** (prior waves: 186.9–209.5) and its rounds ran
  BEFORE any external traffic — unexplained by tenancy; instance/cache state is the standing
  explanation per the 11-10s lesson.
- **Operator tenancy contaminated mid-widths:** three seal-probe `opencode run` calls against
  the same engine (permission-syntax verification for the agentic wave) landed ~11:51–11:58,
  overlapping roughly widths 2–8. w2 round-to-round scatter (217.4 vs 145.2) is consistent
  with that.
- Plateau w12–w32 mean 524.6 is ABOVE 11-13's 470–475 while w1 sits far below — opposite
  directions confirm instance state, not a shape change. Do not read a "+11 % plateau" claim
  into this row.

**KV stage — first admission-suspension TRIP on record:** stopped at w10, total 509,370
tokens = 3.89x the 131,072-token resident budget (peak suspended 2, waiting_memory 2,
admission waiting 2, pages_active 7238, lifetime resource_suspensions +3, demotions +1502).
Prior waves: zero suspensions through w12 at 611k (4.66x). Caveat: same-day engine
residency state may be a factor — the trip is real (counters moved) but the *threshold shift*
is not established. Needs a clean-window rerun (and ideally a fresh-engine one) before this
goes anywhere as a finding.

**Action:** re-run `ladder_kv.py` in a zero-tenancy window before treating any 16b cell as
baseline material. Raw rows kept regardless (per wave hygiene, raw first, claims after).
