# Telecom determinism probe (2026-11-22) — the action lottery is ~50/50 in both domains; depth does NOT deepen it

The airline probe (`../2026-11-21-determinism-probe/RECORD.md`) predicted from its size gradient that
telecom — the longest-conversation domain (median agent prompt **21.9 k chars**, max 46.5 k, vs airline's
2.3–40.6 k) — would be *more* unstable. Measured with the corrected metric, that prediction **fails at the
action level** and holds only at the message level.

## Method

Identical to the airline probe: proxy-capture wave (telecom base split, every-4th task = 29 of 114,
1 trial, seed 300, max_concurrency 3, standard evaluation) → **1,049 wire requests recorded**
(434 agent + 615 user-sim by system-prompt classification) → 40+40 sampled bodies re-POSTed verbatim,
engine-direct, 3 reps in `seq` (solo) and `mix` (batched with 2 fresh mates). Same engine instance
throughout: capture 06:45Z and all re-queries on `19a70e8c777ce1a5b69b138b` (no restart across both
domains — single-instance, single-epoch comparison).

**Metric corrections discovered in this domain (both apply to the airline record too):**
1. **Role classification by tool presence was wrong for telecom** — telecom's user simulator *has its own
   tools*, so every telecom body classified as "agent" and the user cell ran empty. Fixed to system-prompt
   classification (`e39566b`). Run-1 artifacts kept as `*_run1-mixedroles`.
2. **Tool-call `id` fields are engine-random per request** (`call_<random-hex>_<idx>`; measured:
   function+arguments byte-stable across repeats, ids never). Counting them in "action identity" made
   every tool call a false action change — this had *depressed the airline numbers published first*
   (15–40 % → corrected below). Fixed (`f496bd1`); run-2 kept as `*_run2_idbug`.

## Result (corrected metric, reps=3, n=40 per cell)

| arm / stratum | identical action | identical full message | matched original action |
|---|---|---|---|
| seq · agent | **21/40 = 52.5 %** | 6/40 = 15.0 % | 24/40 = 60.0 % |
| seq · user | **25/40 = 62.5 %** | 6/40 = 15.0 % | 25/40 = 62.5 % |
| mix · agent | **18/40 = 45.0 %** | 5/40 = 12.5 % | 25/40 = 62.5 % |
| mix · user | **23/40 = 57.5 %** | 4/40 = 10.0 % | 24/40 = 60.0 % |

Airline corrected (same day, same instance, from the airline record): seq agent 50.0 %, mix agent 55.0 %,
user cells 30.0 %; full messages 10–20 %.

## What this establishes

- **Agent action identity ≈ coin flip in BOTH domains**: airline 50–55 %, telecom 45–52.5 %. The depth
  gradient (small-prompt half 62.5 % vs large 52.5 % within telecom) survives weakly *within* a domain,
  but across domains the much longer telecom prompts are **no worse** than airline's — the earlier
  "depth makes it worse" reading was inflated by the id bug.
- **Full-message identity stays terrible everywhere (10–20 %)** — with thinking text counted, byte-identical
  requests almost never reproduce in either domain. This is the level that compounds over a 40-turn
  telecom conversation, and it is why transcripts are one-off documents (suite rule 6).
- **User-sim calls are more reproducible in telecom (57.5–62.5 %) than airline (30 %)** — telecom user
  turns are more templated (device-state confirmations); airline user turns are freer text. Role, not
  domain length, drives that gap.
- **Batch width still irrelevant** (agent seq 52.5 vs mix 45.0 at n=40 — within noise; airline was
  50 vs 55). Consistent with the 19b width control: three independent exclusions now.
- **Divergence stays early**: first-difference median 17 chars (19/73 within 2 chars).

**Revised suite-wide headline (replaces the "~85 % action coin flip"):** a byte-identical request at
temperature 0 reproduces its own **action** ~45–55 % of the time for agent calls (30–62 % for user-sim
calls), and its **full message** (thinking included) only 10–20 %. Task-level reward flips (15.1 % same-seed
floor) are the environment absorbing a ~50 % agent-call action lottery, not an 85 % one. The effort A/B
conclusion is untouched: xhigh did not change flip rates, and the probe explains why — the lottery is
decode-side.

## Caveats

- n=40 per cell per domain: agent-vs-agent airline/telecom parity is solid (overlapping Wilson CIs);
  the airline-user (30 %) vs telecom-user (57.5–62.5 %) gap is real but unexplained beyond the
  templating story.
- Engine-internal cause still NOT named (int8 cached-KV vs bf16 prefill; drafter verify path; drafter
  acceptance 64 % in the xhigh window, in-line).
- Captures (1,049 wire records) stay local per suite policy; `probe_rows.jsonl` published.
- Tenancy: capture wave single-tenant (right after the xhigh2 wave closed at 06:41Z); corrected re-queries
  bracketed by the airline run4 sampler (`../2026-11-21-determinism-probe/engine_samples_run4.jsonl`).

Files: `probe_rows.jsonl` (+ `*_run1-mixedroles`, `*_run2_idbug` bug trail), `requery_summary.txt`
(+ superseded summaries), `probe.log`, sampler/status files, `captures.jsonl` (local), capture wave log;
scripts one level up (`run_telecom_probe.sh`, `run_probe_capture.py` — now domain-parameterized).
