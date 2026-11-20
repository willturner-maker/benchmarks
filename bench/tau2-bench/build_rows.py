#!/usr/bin/env python3
"""Build the published per-simulation rows (`tasks.jsonl`) from a tau2 wave's own results.json.

Why this is published rather than kept local: the row file is what makes a tau2 record reviewable.
Transcripts stay on the machine that ran them; the rows carry the reward decomposition and the cost
shape. If a community run wants a comparable record, run THIS and diff the field set.

Row rules (the same ones wave 2026-11-19a was built with, so the published file is reproducible):
  * one row per simulation; no message content, no tool arguments, no model free text, no file paths;
  * `reward` is passed through as tau2 computed it (a null means infrastructure_error — see README:
    unscored sims are excluded from means, never zero-filled);
  * depth/completions come from per-message `usage.prompt_tokens`, i.e. what the engine was actually
    asked per call, not the final context length.

Usage:
  python3 build_rows.py --out rows.jsonl <sim-dir> [<sim-dir> ...]
where a sim dir is tau2's `--save-to` directory containing results.json.
"""
import argparse
import json
import os
import sys

ROW_KEYS = ("domain", "task_id", "trial", "seed", "termination", "reward", "reward_basis",
            "reward_breakdown", "db_reward", "db_match", "env_assertions", "nl_assertions_checked",
            "communicate_checks", "actions_annotated", "actions_matched", "actions_read",
            "actions_write", "messages", "tool_calls", "completions", "prompt_tokens",
            "completion_tokens", "depth_first", "depth_max", "duration_s", "cost_usd")


def rows_from(res_path, domain):
    res = json.load(open(res_path, encoding="utf-8"))
    out = []
    for s in res.get("simulations") or []:
        ri = s.get("reward_info") or {}
        dbc = ri.get("db_check") or {}
        msgs = s.get("messages") or []
        depth = [m["usage"]["prompt_tokens"] for m in msgs if (m.get("usage") or {}).get("prompt_tokens")]
        comp = [m["usage"].get("completion_tokens") or 0 for m in msgs
                if (m.get("usage") or {}).get("prompt_tokens")]
        acs = ri.get("action_checks") or []
        out.append({
            "domain": domain, "task_id": s.get("task_id"), "trial": s.get("trial"),
            "seed": s.get("seed"), "termination": s.get("termination_reason"),
            "reward": ri.get("reward"),
            "reward_basis": ri.get("reward_basis"),
            "reward_breakdown": ri.get("reward_breakdown"),
            "db_reward": dbc.get("db_reward"), "db_match": dbc.get("db_match"),
            "env_assertions": len(ri.get("env_assertions") or []),
            "nl_assertions_checked": len(ri.get("nl_assertions") or []),
            "communicate_checks": len(ri.get("communicate_checks") or []),
            "actions_annotated": len(acs),
            "actions_matched": sum(1 for c in acs if c.get("action_match")),
            "actions_read": sum(1 for c in acs if c.get("tool_type") == "read"),
            "actions_write": sum(1 for c in acs if c.get("tool_type") == "write"),
            "messages": len(msgs),
            "tool_calls": sum(len(m.get("tool_calls") or []) for m in msgs),
            "completions": len(depth),
            "prompt_tokens": sum(depth), "completion_tokens": sum(comp),
            "depth_first": depth[0] if depth else None, "depth_max": max(depth) if depth else None,
            "duration_s": s.get("duration"),
            "cost_usd": (s.get("agent_cost") or 0) + (s.get("user_cost") or 0),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("dirs", nargs="+")
    args = ap.parse_args()

    rows = []
    for d in args.dirs:
        res = os.path.join(d, "results.json")
        if not os.path.exists(res):
            sys.exit(f"no results.json in {d}")
        # domain = the leading token of tau2's save name (wave-retail-... / smoke-airline-...), else the dir
        base = os.path.basename(d.rstrip("/"))
        domain = base.split("-")[1] if len(base.split("-")) > 1 else base
        rows += rows_from(res, domain)

    leak = [k for r in rows for k in r if k not in ROW_KEYS]
    if leak:
        sys.exit(f"row field set drifted: {sorted(set(leak))}")
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    scored = sum(1 for r in rows if r["reward"] is not None)
    print(f"{args.out}: {len(rows)} rows ({scored} scored, {len(rows) - scored} unscored/"
          f"infrastructure_error — excluded from means, never zero-filled)")


if __name__ == "__main__":
    sys.exit(main())
