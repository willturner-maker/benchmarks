#!/usr/bin/env python3
"""Capture wave for the determinism probe: a stratified task subset x 1 trial, seed 300,
identical args to published waves, EXCEPT api_base -> logging proxy (port 8011) for both
roles so every agent AND user-simulator request body is recorded verbatim.
Judge-free domains only (airline: DB+COMMUNICATE; telecom base: ENV_ASSERTION - no judge).
Standard evaluation_type=ALL (run_domain default) - capture must be a normal wave.
"""
import argparse
import sys
from pathlib import Path

TAU2 = Path.home() / "tau2-bench"
sys.path.insert(0, str(TAU2 / "src"))

from tau2.runner import run_domain                       # noqa: E402
from tau2.data_model.simulation import TextRunConfig     # noqa: E402

MODEL = "openai/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
LLM_ARGS = {"temperature": 0, "api_base": "http://127.0.0.1:8011/v1", "api_key": "local", "max_tokens": 4096}

ap = argparse.ArgumentParser()
ap.add_argument("--domain", default="airline")
ap.add_argument("--step", type=int, default=2, help="every Nth task in the registry's wave order (airline 2 -> 25 of 50; telecom 4 -> 29 of 114)")
ap.add_argument("--save-to", required=True)
a = ap.parse_args()

from tau2.runner.helpers import get_tasks   # noqa: E402
all_ids = [t.id for t in get_tasks(task_set_name=a.domain, task_split_name="base", task_ids=None, num_tasks=None)]  # "base" = the config default the published waves ran
ids = all_ids[::a.step]                     # fixed rule over the registry's own order, no cherry-picking
cfg = TextRunConfig(
    domain=a.domain,
    task_ids=ids,                          # every Nth task id: fixed rule, no cherry-picking
    num_trials=1, max_concurrency=3, seed=300,
    llm_agent=MODEL, llm_args_agent=dict(LLM_ARGS),
    llm_user=MODEL, llm_args_user=dict(LLM_ARGS),
    save_to=a.save_to,
)
run_domain(cfg)
sys.exit(0)
