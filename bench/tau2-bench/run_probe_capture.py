#!/usr/bin/env python3
"""Capture wave for the determinism probe: 25 airline tasks x 1 trial, seed 300,
identical args to published waves, EXCEPT api_base -> logging proxy (port 8011) for both
roles so every agent AND user-simulator request body is recorded verbatim.
Judge-free by domain (airline reward basis DB+COMMUNICATE - no judge in the path).
Standard evaluation_type=ALL (run_domain default) - capture must be a normal wave.
"""
import sys
from pathlib import Path

TAU2 = Path.home() / "tau2-bench"
sys.path.insert(0, str(TAU2 / "src"))

from tau2.runner import run_domain                       # noqa: E402
from tau2.data_model.simulation import TextRunConfig     # noqa: E402

MODEL = "openai/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
LLM_ARGS = {"temperature": 0, "api_base": "http://127.0.0.1:8011/v1", "api_key": "local", "max_tokens": 4096}

cfg = TextRunConfig(
    domain="airline",
    task_ids=[str(i) for i in range(0, 50, 2)],   # every other task: 25 of 50, no cherry-picking
    num_trials=1, max_concurrency=3, seed=300,
    llm_agent=MODEL, llm_args_agent=dict(LLM_ARGS),
    llm_user=MODEL, llm_args_user=dict(LLM_ARGS),
    save_to="wave-2026-11-21-probe-capture-airline",
)
sys.exit(0 if run_domain(cfg) else 0)
