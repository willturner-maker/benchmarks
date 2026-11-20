#!/usr/bin/env python3
"""tau2-bench wave summarizer: re-derive upstream's metrics, audit stability, join the engine samples.

Modes
  --tau2-dir/--wave-dir : read the raw tau2 records + the wave's own logs (full re-derivation, checks
                          our numbers against the Average Reward / Pass^1 / Pass^2 lines tau2 printed)
  --from-rows ROWS      : recompute every headline from the PUBLISHED per-simulation rows only
                          (tasks.jsonl) and diff against summary.json -- the reviewer's path

Metric definition note: tau2's pass^k is per task C(n_pass, k) / C(n_trials, k), averaged over tasks.
With 2 trials that is exactly "both trials passed", so pass^1 - pass^2 IS the disagreement count. The
independent-trials variant (mean p^k) is strictly looser; both are printed.

Engine join attribute traffic by prompt_tokens size: benchmark sessions in these waves never exceeded
~16k prompt tokens, while an operator (chat) session sits in the 10^5 range, so the two are separable.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

KV_BUDGET = 155_648
WINDOW = 262_144
CO_TENANT_MIN_TOKENS = 20_000


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def passk(groups, k):
    """groups: list of (n_trials, n_pass) per task. Upstream's definition."""
    vals = [math.comb(np_, k) / math.comb(n, k) for n, np_ in groups if n >= k]
    return statistics.mean(vals) if vals else float("nan")


def groups_from_rows(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["domain"], r["task_id"])].append(1 if r["reward"] == 1.0 else 0)
    return [(len(v), sum(v)) for v in g.values()], g


def upstream_lines(log_path):
    out = {}
    if not os.path.exists(log_path):
        return out
    text = open(log_path, encoding="utf-8").read()
    for key, pat in (("reward", r"Average Reward\s+([\d.]+)"),
                     ("pass1", r"Pass\^1\s+([\d.]+)"),
                     ("pass2", r"Pass\^2\s+([\d.]+)"),
                     ("pass3", r"Pass\^3\s+([\d.]+)"),
                     ("pass4", r"Pass\^4\s+([\d.]+)"),
                     ("db", r"DB Match\s+✓ (\d+) / ✗ (\d+)"),
                     ("read_actions", r"📖 Read Actions\s+(\d+)/(\d+)"),
                     ("write_actions", r"✏️\s+Write Actions\s+(\d+)/(\d+)"),
                     ("sims", r"Total Simulations\s+(\d+)"),
                     ("tasks", r"Total Tasks\s+(\d+)")):
        m = re.search(pat, text)
        if m:
            out[key] = m.groups() if len(m.groups()) > 1 else m.group(1)
    return out


def report_rows(rows, wave_dir=None):
    by_dom = defaultdict(list)
    for r in rows:
        by_dom[r["domain"]].append(r)
    for dom in sorted(by_dom):
        rs = by_dom[dom]
        groups, g = groups_from_rows(rs)
        p1, p2 = passk(groups, 1), passk(groups, 2)
        maxtr = max(n for n, _ in groups)
        extra = "".join(f"  pass^{k} {passk(groups, k):.4f}" for k in range(3, maxtr + 1))
        naive = statistics.mean((np_ / n) ** 2 for n, np_ in groups)
        depths = [r["depth_max"] for r in rs if r["depth_max"]]
        print(f"\n### {dom}: {len(g)} tasks x {max(n for n, _ in groups)} trials = {len(rs)} sims "
              f"({sum(1 for r in rs if r['reward'] is not None)} scored, "
              f"{sum(1 for r in rs if r['reward'] is None)} unscored)")
        print(f"  mean reward {statistics.mean([r['reward'] or 0 for r in rs]):.4f}  "
              f"pass^1 {p1:.4f}  pass^2 {p2:.4f}{extra}   (independent-trials pass^2 would print {naive:.4f})")
        print(f"  tasks both-pass {sum(1 for n, np_ in groups if np_ == n)}  "
              f"trials disagree {sum(1 for n, np_ in groups if 0 < np_ < n)}  "
              f"all-trials-fail {sum(1 for n, np_ in groups if np_ == 0)}")
        print(f"  termination {dict(Counter(r['termination'] for r in rs))}")
        print(f"  tool calls {sum(r['tool_calls'] for r in rs)} "
              f"(mean {statistics.mean([r['tool_calls'] for r in rs]):.2f}/sim)  "
              f"completions {sum(r['completions'] for r in rs)}  "
              f"prompt {sum(r['prompt_tokens'] for r in rs):,} tok  "
              f"completion {sum(r['completion_tokens'] for r in rs):,} tok")
        print(f"  per-call depth max {max(depths):,} tok = {max(depths)/KV_BUDGET:.3f}x KV budget, "
              f"{max(depths)/WINDOW:.3f}x window")
        # the informational-only trap: telecom's DB Match row looks terrible and is irrelevant
        dbc = [r["db_match"] for r in rs if r["db_match"] is not None]
        basis = Counter(b for r in rs for b in (r.get("reward_basis") or []))
        print(f"  reward_basis present {dict(basis)}  |  db_match {dbc.count(True)}/{len(dbc)} "
              f"({'scored component' if 'DB' in basis else 'INFORMATIONAL ONLY - not in reward_basis'})")
        if wave_dir:
            up = upstream_lines(f"{wave_dir}/{dom}.log")
            if up:
                ok = (abs(float(up["reward"]) - statistics.mean([r["reward"] or 0 for r in rs])) < 5e-4
                      and abs(float(up["pass1"]) - p1) < 5e-4 and abs(float(up["pass2"]) - p2) < 5e-4)
                print(f"  upstream printed reward {up['reward']} pass^1 {up['pass1']} pass^2 {up['pass2']}"
                      f" -> re-derivation {'AGREES' if ok else 'CHECK'}")


def join_engine(path):
    samples = []
    if os.path.exists(path):
        samples = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if not samples:
        print("\n(no engine samples)")
        return
    bench = [r for s in samples for r in s["active_requests"] if (r.get("prompt_tokens") or 0) <= CO_TENANT_MIN_TOKENS]
    other = [r for s in samples for r in s["active_requests"] if (r.get("prompt_tokens") or 0) > CO_TENANT_MIN_TOKENS]
    conc = [sum(1 for r in s["active_requests"] if (r.get("prompt_tokens") or 0) <= CO_TENANT_MIN_TOKENS)
            for s in samples]
    print(f"\n### engine samples: {len(samples)} over "
          f"{(max(s['t'] for s in samples)-min(s['t'] for s in samples))/60:.0f} min")
    print(f"  benchmark request-samples {len(bench)}, prompt_tokens "
          f"{min(r['prompt_tokens'] for r in bench):,}..{max(r['prompt_tokens'] for r in bench):,}, "
          f"kv_mode {dict(Counter(r.get('kv_mode') for r in bench))}")
    print(f"  benchmark concurrency histogram {dict(sorted(Counter(conc).items()))}")
    print(f"  co-tenant request-samples {len(other)}"
          + (f", max {max(r['prompt_tokens'] for r in other):,} tokens, "
             f"kv_mode {dict(Counter(r.get('kv_mode') for r in other))}" if other else " (clean window)"))
    pa = [s["pages_active"] for s in samples]
    print(f"  pages_active {min(pa)}..{max(pa)} ({max(pa)*32:,} tok = {max(pa)*32/KV_BUDGET:.2f}x KV budget)")
    print(f"  queued max {max(s['queued'] for s in samples)}  prefilling max {max(s['prefilling'] for s in samples)}  "
          f"decoding max {max(s['decoding'] for s in samples)}")
    w = {}
    for s in samples:
        for k, v in (s["decode_batches_by_width"] or {}).items():
            w[k] = max(w.get(k, 0), v)
    print(f"  decode_batches_by_width lifetime high-water {w}")
    for k in ("spill_moves", "kv_demotions", "suspensions"):
        vals = [s[k] for s in samples if s.get(k) is not None]
        if vals:
            print(f"  {k}: delta {vals[-1]-vals[0]}")
    print("  admission peaks " + str({k: max((s['admission'][k] for s in samples), default=0)
                                      for k in ("waiting", "waiting_memory", "waiting_concurrency",
                                                "held_behind_refusal", "suspended", "restoring")}))


def engine_deltas(wave_dir):
    b, a = f"{wave_dir}/status_before.json", f"{wave_dir}/status_after.json"
    if not (os.path.exists(b) and os.path.exists(a)):
        return
    before, after = load(b), load(a)

    def g(d, *p):
        for k in p:
            d = d.get(k) if isinstance(d, dict) else None
        return d
    print("\n### engine lifetime-counter deltas over the wave")
    for sec, key in (("metrics", "prefill_input_tokens"), ("metrics", "decode_output_tokens"),
                     ("metrics", "drafted_tokens"), ("metrics", "accepted_draft_tokens"),
                     ("cache", "reused_tokens"), ("cache", "hits"), ("cache", "hit_rate"),
                     ("disk", "kv_demotions"), ("disk", "kv_restores"), ("disk", "written_bytes")):
        x, y = g(before, sec, key), g(after, sec, key)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            delta = y - x
            d = f"{delta:,}" if delta >= 1 else f"{delta:.4f}"
            print(f"  {sec}.{key:24s} {x if isinstance(x,float) else format(x,',')} -> "
                  f"{y if isinstance(y,float) else format(y,',')}  delta {d}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tau2-dir", default=os.path.expanduser("~/tau2-bench"))
    ap.add_argument("--wave-dir", required=True)
    ap.add_argument("--domains", default="airline retail telecom")
    ap.add_argument("--from-rows", help="recompute from published rows (tasks.jsonl) only")
    a = ap.parse_args()

    if a.from_rows:
        rows = load_rows(a.from_rows)
        print(f"re-derivation from published rows: {len(rows)} sims")
        report_rows(rows)
        sj = f"{a.wave_dir}/summary.json"
        if os.path.exists(sj):
            s = load(sj)
            print("\n### vs published summary.json")
            for dom, v in s["domains"].items():
                mine = [r for r in rows if r["domain"] == dom]
                g, _ = groups_from_rows(mine)
                print(f"  {dom:8s} sims {len(mine)}/{v['sims']}  pass^1 "
                      f"{passk(g,1):.4f}/{v['pass_1']}  pass^2 {passk(g,2):.4f}/{v['pass_2']}")
        join_engine(f"{a.wave_dir}/engine_samples.jsonl")
        return 0

    for dom in a.domains.split():
        rec = glob.glob(f"{a.tau2_dir}/data/simulations/wave-*-{dom}/results.json")
        if not rec:
            rec = sorted(glob.glob(f"{a.tau2_dir}/data/simulations/*{dom}*/results.json"))
        if not rec:
            print(f"### {dom}: no record found under {a.tau2_dir}/data/simulations")
            continue
        res = load(rec[-1])
        rows = []
        for s in res["simulations"]:
            ri = s.get("reward_info") or {}
            dbc = ri.get("db_check") or {}
            msgs = s.get("messages") or []
            depth = [m["usage"]["prompt_tokens"] for m in msgs if (m.get("usage") or {}).get("prompt_tokens")]
            acs = ri.get("action_checks") or []
            rows.append({"domain": dom, "task_id": s.get("task_id"), "trial": s.get("trial"),
                         "reward": ri.get("reward"), "reward_basis": ri.get("reward_basis"),
                         "db_match": dbc.get("db_match"), "termination": s.get("termination_reason"),
                         "tool_calls": sum(len(m.get("tool_calls") or []) for m in msgs),
                         "completions": len(depth), "prompt_tokens": sum(depth),
                         "completion_tokens": sum((m["usage"].get("completion_tokens") or 0) for m in msgs
                                                 if (m.get("usage") or {}).get("prompt_tokens")),
                         "depth_max": max(depth) if depth else None,
                         "actions_matched": sum(1 for c in acs if c.get("action_match"))})
        report_rows(rows, a.wave_dir)
    join_engine(f"{a.wave_dir}/engine_samples.jsonl")
    engine_deltas(a.wave_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
