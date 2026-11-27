# Splash 1.7.1 -> 1.7.3 transition (2026-11-27) — Tier-1: behaviourally quiet; one byte probe bimodal at an optional-field boundary

Tier-1 transition wave per the 1.7.1-transition protocol: engine fingerprint capture + diff
against `../splash-1.7.1-transition/fingerprint-1.7.1-post.json`, golden probes re-run and
compared against `golden-probes-1.7.1-post.json`. Engine is the single 1.7.3 instance
(pinned argv verified: max-memory 60129542144, persistent-cache, medium effort,
32768 thinking budget, queue-size 64); no restarts in this window.

## Tier-0 — fingerprint diff (`fingerprint_diff_1.7.1-to-1.7.3.txt`)
- Version, engine binary, server tree digest, install receipt: moved (expected for a release bump).
- **Same**: max context 262,144; batch width 4; `ane_ffn.state` off — the applicability
  surface that kept 1.7.1 low-risk is unchanged on 1.7.3.
- **Moved**: `loaded_model_layout_sha256` and `kv.target_model_sha256` — which on the
  1.7.0->1.7.1 transition stayed SAME, so this needs accounting (next bullet).
- **Model content is proven unchanged**: the resolved store's `model.json` digests
  (`4c1eb2ce…`, `316b46f3…` for the two GGUF shards) equal the HF blob content-hash names
  (content-addressed cache), whose snapshot links date to **Oct 24** — the model source has
  not moved since original download. The layout-hash move is therefore **engine-side**:
  it co-moves with `memory_plan.shared_prefill_bytes` (+22.8 MiB) and the changed server
  tree — the new engine computes/relabels the layout, the weights did not change.
- Runtime counters show the expected new-instance reset; no anomaly flags.

## Tier-1 — golden probes (`golden_compare_1.7.1-to-1.7.3.txt`)
8 byte/grammar-claim probes; **7/8 reproduce visible output** (content sha + finish +
tool-args shas) against 1.7.1. Reasoning text/length moved on all (same within-build floor
documented in the 1.7.1 record — reasoning moves inside one build too).

**`toolcall_nested_stream` — the one flagged byte probe — is bimodal at temperature 0:**
- Inside the 1.7.3 capture itself: run 0 deviated, run 1 reproduced the exact 1.7.1 args
  sha (`e4d3945c…`) — non-reproducible *within the epoch*, not an epoch shift.
- Ad-hoc quantification (probe-extension, disclosed): the captured request body re-POSTed
  8x direct at temp 0 — **7/8 canonical (= the 1.7.1-mode args), 1/8 the deviant variant**.
  The two variants differ *only* in whether station C1's optional `flags` field is emitted
  as `"flags":[]` or omitted — schema-valid, semantically identical.
- Disclosure: the 8x repeats ran `stream:false`; the bimodality itself was observed in the
  streaming capture (run 0 vs run 1), so the 7:1 split characterizes the mode, not the
  exact stream-path rate.
- Interpretation: this is exactly the request-level lottery the tau2 suite measured at
  ~50/50 (and which 1.7.1's own boot banner documents — "greedy and seeded outputs can
  differ from run to run"), here showing up as a 7:1 flip at a schema-optional-field
  boundary. The historical output remains the mode on 1.7.3.

## Verdict
1.7.3 is **behaviourally quiet for the pinned config**: 7/8 byte probes byte-identical to
the 1.7.1 epoch, the 8th bimodal with the 1.7.1 output as its mode (7/8), zero grammar or
tool-emission regressions, and the fingerprint's model-layout move fully attributed to the
engine memory plan (model content proven unchanged). This row plus the hermes gate's
0-parse-fail row bracket the engine-side change surface; the tau2 238x3 replay (same day)
is the behavioral-distribution test.

## Files
- `fingerprint-1.7.3.json`, `fingerprint_diff_1.7.1-to-1.7.3.txt`
- `golden-probes-1.7.3.json` (2 runs per probe, nonce `t173-20261127`), `golden_compare_1.7.1-to-1.7.3.txt`
- The 8x repeat probe-extension ran inline in this session (request body verbatim from the
  capture; variant split 7:1, args JSON quoted in this session's log) — no separate file.
