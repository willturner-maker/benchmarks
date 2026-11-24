# Wave RECORD — bfcl-23a-2026-11-23 (BFCL v4 debut full wave)

**What:** first full-wave run of the pinned **BFCL v4** instrument (gorilla clone @
`6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, repo has no tags — commit is the pin).
Engine: Splash **1.7.1**, pinned argv unchanged, warm cache. Harness: python 3.12 venv,
BFCL generate/evaluate, `temperature 0`, `--num-threads 3` (inside engine
`maximum_batch_width = 4` — same decode-width rule as tau2's default 3).

**Harness delta (the only one):** our model is registered at RUNTIME by
`bench/bfcl/bfcl_splash.py` — in-place `MODEL_CONFIG_MAPPING` injection using BFCL's own
`OpenAICompletionsHandler` (`is_fc_model=True`, `underscore_to_dot=True`), pointing at
`OPENAI_BASE_URL=http://127.0.0.1:8000/v1`. The clone stays byte-identical to the pin;
scoring code and test data untouched.

**FC-mode build series:** native OpenAI `tools=` path (Splash serves it natively; probe:
clean `tool_calls`, empty content — the engine's separate reasoning stream keeps `content`
clean, consistent with the tool-loop gate's 0/120 parse-fail). Prompt-mode would be a
separate series; never mix rows.

**Window:** 2026-11-24T01:03:32Z → 04:40:36Z generate (3 h 37 m), evaluate ~6 min.
4,441 task-runs across 17 categories. **0 infrastructure errors**; 1 empty-response entry
counted as a miss. Tenancy: engine sampled every 30 s — normal pressure, nominal thermal,
zero admission waits throughout.

**Result: 40.85% overall** (their weighted composite). Category table in
`results-bfcl-23a-2026-11-23.json`. Headline splits: non-live AST 86.88 / live 77.79 /
multi-turn 55.50.

**Deviations:**
1. `memory_*` categories not run this wave (kv/rec_sum deferred; vector needs an embedder
   dependency check first). `web_search_*` excluded by design (external engine = not
   reproducible here). `format_sensitivity` excluded (non-scoring, prompting-only).
2. 14 of the 4,441 entries came from the pre-wave **smoke gate** (same build, same day,
   gate passed) and were carried in by BFCL's native resume. Continuity check: smoke's
   small-n scores (100/100/75/50 on n=4/2/4/4) settled to (94.5/79.17/64/53) at full n —
   same shape, no plumbing surprise.

**Instrument gotchas learned (save the next operator time):**
- Pre-existing-endpoint path is `--skip-server-setup`-style via env for OSS handlers, but the
  native `tools=` FC path lives in the **api** handler (`OpenAICompletionsHandler`, reads
  `OPENAI_BASE_URL`); OSS handlers are prompt-mode. Register the model against the api handler.
- This pin has **no model-registration CLI** (older `bfcl models` path absent) — runtime
  injection is how to stay zero-delta.
- CLI lists categories **comma-separated**, one arg.
- `test_case_ids_to_generate.json` must be flat `{category: [ids]}` (the shipped example lies
  about nothing — but the old wrapped format elsewhere in the wild fails).
- Subset scoring needs `--partial-eval`; full waves don't.
- qwen_agent dep chain needs `soundfile` beyond `-e .` on py3.12.
- Their CSV "Total Cost" is a rate-card synthetic for price=None models; our real marginal
  cost is zero.

**How to relaunch / reproduce:**
```
# layout + pins: <volume>/local.AI/bench/README.md ; clone at bench/BFCL/gorilla
cd bench/BFCL/gorilla/berkeley-function-call-leaderboard
OPENAI_BASE_URL=http://127.0.0.1:8000/v1 OPENAI_API_KEY=local \
  ../../bfcl-venv/bin/python ../../bfcl_splash.py generate \
  --model splash-qwen3.8-flash-iq3s-FC \
  --test-category simple_python,simple_java,simple_javascript,parallel,multiple,parallel_multiple,irrelevance,live_simple,live_multiple,live_parallel,live_parallel_multiple,live_irrelevance,live_relevance,multi_turn_base,multi_turn_miss_func,multi_turn_miss_param,multi_turn_long_context \
  --temperature 0 --num-threads 3
# then evaluate with the same --model/--test-category (no --partial-eval on full coverage)
```
venv rebuild: `python3.12 -m venv bfcl-venv && pip install -e <clone>/berkeley-function-call-leaderboard soundfile`.

**Artifacts:** raw `result/` + `score/*.csv` inside the pinned clone (gitignored scratch);
wave scratch (launch.md, run_wave.sh, driver.out with GENERATE_EXIT, generate.log,
engine_samples.jsonl, score CSV copies) under `<volume>/local.AI/bench/waves/bfcl-23a-2026-11-23/`.
Published: this RECORD + `results-bfcl-23a-2026-11-23.json` + `docs/bfcl-benchmark-results.md`.
