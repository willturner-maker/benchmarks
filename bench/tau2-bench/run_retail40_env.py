#!/usr/bin/env python3
"""tau2 retail judge-dependent 40: closure run WITHOUT the LLM judge.

Deviation (disclosed in the wave RECORD, and the reason the 40 were excluded in the first place):
v1.0.1 has no CLI/env override for the NL-assertion judge (gpt-4.1-2025-04-14) and no key for it exists
here. Instead of calling a judge at all, this runs the instrument AS A LIBRARY (unmodified source,
`tau2.run.run_domain`) with evaluation_type=EvaluationType.ENV - DB checks + env assertions only. The
resulting per-task env reward is NOT comparable to the published pass^k rows (no COMMUNICATE, no
NL_ASSERTION component) and is published as an informational component score that closes the
"we have no number for these 40 at all" gap.

Task scope: the 40 judge-dependent retail tasks = all 114 minus the RETAIL_FREE array pinned in
run_wave.sh (the 74 judge-free ids). Same model args, seed 300, self-play, 2 trials, temperature 0.
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAU2 = Path.home() / "tau2-bench"
sys.path.insert(0, str(TAU2 / "src"))

from tau2.run import run_domain                      # noqa: E402
from tau2.data_model.simulation import TextRunConfig # noqa: E402
from tau2.evaluator.evaluator import EvaluationType  # noqa: E402

MODEL = "openai/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
LLM_ARGS = {"temperature": 0, "api_base": "http://127.0.0.1:8000/v1", "api_key": "local", "max_tokens": 4096}


def judge_dependent_ids():
    tasks = json.loads((TAU2 / "data/tau2/domains/retail/tasks.json").read_text())
    tasks = tasks if isinstance(tasks, list) else (tasks.get("tasks") or list(tasks.values()))
    all_ids = [str(t["id"]) for t in tasks]
    m = re.search(r"RETAIL_FREE=\(([^)]*)\)", (HERE / "run_wave.sh").read_text())
    free = set(m.group(1).split())
    judged = [t for t in all_ids if t not in free]
    assert len(all_ids) == 114 and len(free) == 74 and len(judged) == 40, (len(all_ids), len(free), len(judged))
    return judged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-to", required=True)
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--seed", type=int, default=300)
    a = ap.parse_args()

    ids = judge_dependent_ids()
    cfg = TextRunConfig(
        domain="retail", task_ids=ids, num_trials=a.trials, max_concurrency=3, seed=a.seed,
        llm_agent=MODEL, llm_args_agent=dict(LLM_ARGS), llm_user=MODEL, llm_args_user=dict(LLM_ARGS),
        evaluation_type=EvaluationType.ENV, save_to=a.save_to,
    )
    print(f"retail40 ENV run: {len(ids)} tasks x {a.trials} trials = {len(ids)*a.trials} sims, seed {a.seed}")
    print(f"ids: {','.join(ids)}")
    run_domain(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
