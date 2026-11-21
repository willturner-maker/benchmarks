#!/usr/bin/env python3
"""tau2 retail judge-dependent 40: closure run WITHOUT the LLM judge.

Deviation (disclosed in the wave RECORD, and the reason the 40 were excluded in the first place):
v1.0.1 has no CLI/env override for the NL-assertion judge (gpt-4.1-2025-04-14) and no key for it
exists here. Instead of calling a judge at all, this runs the instrument AS A LIBRARY (unmodified
source) with evaluation_type=EvaluationType.ENV - DB checks + env assertions only. The resulting
per-task env reward is NOT comparable to the published pass^k rows (no COMMUNICATE, no NL_ASSERTION
component) and is published as an informational component score that closes the "we have no number
for these 40 at all" gap.

Attempt 1 lesson (2026-11-21, all 80 sims infrastructure_error): evaluation_type is NOT a
TextRunConfig field - pydantic silently dropped it, and run_domain() (runner/batch.py:852)
delegates to run_tasks() WITHOUT an evaluation_type kwarg, so the default ALL re-engaged the
judge for every NL-basis task -> litellm NotFoundError 'model gpt-4.1-2025-04-14 not found'.
The only judge-free seam in unmodified source is runner.run_tasks(..., evaluation_type=ENV).
This mirrors run_domain's task loading and save-path logic exactly, and adds only that kwarg.

Task scope: the 40 judge-dependent retail tasks = all 114 minus the RETAIL_FREE array pinned in
run_wave.sh (the 74 judge-free ids). Same model args, seed 300, self-play, 2 trials, temperature 0.
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAU2 = Path.home() / "tau2-bench"
sys.path.insert(0, str(TAU2 / "src"))

from tau2.runner import run_tasks                          # noqa: E402
from tau2.runner.helpers import get_tasks                  # noqa: E402
from tau2.data_model.simulation import TextRunConfig       # noqa: E402
from tau2.evaluator.evaluator import EvaluationType        # noqa: E402
from tau2.utils.utils import DATA_DIR                      # noqa: E402

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
    ap.add_argument("--limit", type=int, default=0, help="smoke: only the first N of the 40")
    a = ap.parse_args()

    ids = judge_dependent_ids()
    if a.limit:
        ids = ids[: a.limit]
    cfg = TextRunConfig(
        domain="retail", task_ids=ids, num_trials=a.trials, max_concurrency=3, seed=a.seed,
        llm_agent=MODEL, llm_args_agent=dict(LLM_ARGS), llm_user=MODEL, llm_args_user=dict(LLM_ARGS),
        save_to=a.save_to,
    )
    cfg.validate()

    # mirror of run_domain (runner/batch.py:852): task load + save paths, plus the ONLY deviation:
    # run_tasks accepts evaluation_type; run_domain does not forward it.
    tasks = get_tasks(task_set_name=cfg.task_set_name or cfg.domain,
                      task_split_name=cfg.task_split_name, task_ids=ids, num_tasks=cfg.num_tasks)
    assert len(tasks) == len(ids), (len(tasks), len(ids))
    save_dir = DATA_DIR / "simulations" / a.save_to
    print(f"retail40 ENV run: {len(ids)} tasks x {a.trials} trials = {len(ids)*a.trials} sims, seed {a.seed}")
    print(f"ids: {','.join(ids)}")
    results = run_tasks(cfg, tasks, save_path=save_dir / "results.json", save_dir=save_dir,
                        evaluation_type=EvaluationType.ENV)
    bad = [s for s in results.simulations if getattr(s, "termination_reason", None) == "infrastructure_error"]
    print(f"infrastructure_error sims: {len(bad)}/{len(results.simulations)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
