#!/usr/bin/env python3
"""2026-11-22 thinking-token-budget chain analyzer: per-arm outcome + request-level readout.

The chain (run_thinkbudget_chain.sh) varied the ENGINE-level --thinking-token-budget across three
arms (8192, 65536, and the pinned 32768 relaunched last as a same-session control), one wave of the
238 judge-free tasks per arm, trials=1. This produces the readout that design promised: outcomes,
and the request-level token behaviour that the outcome alone cannot show.

Two measurement notes that matter for honesty:

  * tau2 stores per-message `usage` with completion_tokens ONLY (no reasoning breakdown), and the
    engine counts thinking tokens INSIDE completion_tokens (measured directly on this stack:
    max_tokens=16 -> completion_tokens=16 with reasoning_tokens=16 and content=null). So thinking
    is DERIVED here as completion_tokens minus an estimate of the visible tokens, and the estimate
    is labelled as an estimate. What is NOT estimated: the crowd-out signature - a message with
    completion_tokens > 0 and empty/null visible content is a thinking-budget truncation, plain.
  * role split by message role, per the earlier lesson in this suite (probe_requery): assistant =
    agent, user = the user-simulator LLM. Both are model calls on the same engine, so per-arm
    request stats are reported for the agent stream separately from the simulator stream.

Usage: python3 thinkbudget_summary.py [--arms 8192 65536 32768] [--json out.json]
No engine traffic: it reads the tau2 records and each wave's own samples.
"""
from __future__ import annotations
import argparse, glob, json, math, os, re, statistics as st, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TAU2 = os.path.expanduser(os.environ.get("TAU2_DIR", "~/tau2-bench"))
DOMS = ("airline", "retail", "telecom")
CHARS_PER_TOKEN = 4.0          # disclosed heuristic for the visible-token estimate


def sims_for(arm, dom):
    p = os.path.join(TAU2, "data", "simulations", f"wave-2026-11-22-thinkbudget-{arm}-{dom}", "results.json")
    if not os.path.exists(p):
        return None, p
    return json.load(open(p, encoding="utf-8")), p


def tok_stats(vals):
    if not vals:
        return None
    return {"n": len(vals), "mean": round(st.mean(vals), 1), "median": round(st.median(vals), 1),
            "p90": round(sorted(vals)[int(0.9 * (len(vals) - 1))], 1), "max": max(vals),
            "total": sum(vals)}


def analyze_arm(arm):
    out = {"arm": arm, "domains": {}, "messages": {}}
    rewards, per_task = [], defaultdict(list)
    agent_comp, agent_vis, sim_comp, trunc = [], [], [], 0
    toolcall_empty = 0
    term, tool_calls, durations = Counter(), 0, []
    seen_sigs = set()
    for dom in DOMS:
        d, path = sims_for(arm, dom)
        if d is None:
            out["domains"][dom] = {"missing": True}
            continue
        rs = d.get("simulations") or []
        # reward lives under reward_info (build_rows.py maps it the same way); reading s["reward"]
        # yields None and would silently score every arm at zero.
        rw = [((r.get("reward_info") or {}).get("reward")) for r in rs]
        rw_present = [r for r in rw if r is not None]
        # key by (domain, task_id): task ids are numeric PER DOMAIN, so keying by task_id alone
        # merged airline task 3 with retail task 3 and invented "trials [1,2]" for 31 tasks.
        for r in rs:
            per_task[(dom, r.get("task_id"))].append((r.get("reward_info") or {}).get("reward"))
        basis = Counter(b for r in rs for b in ((r.get("reward_info") or {}).get("reward_basis") or []))
        out["domains"][dom] = {
            "sims": len(rs),
            "rewards_present": len(rw_present),
            "reward_basis_counts": dict(basis),
            "mean_reward": round(st.mean(rw_present), 4) if rw_present else None,
            "pass1": round(sum(1 for x in rw_present if x == 1) / len(rw_present), 4) if rw_present else None,
            "info_keys": sorted(set((d.get("info") or {}).keys()))[:6],
        }
        for s in rs:
            term[s.get("termination_reason")] += 1
            if s.get("duration") is not None:
                durations.append(s["duration"])
            for m in s.get("messages") or []:
                u = m.get("usage") or {}
                comp = u.get("completion_tokens")
                if comp is None:
                    continue
                vis_chars = len(m.get("content") or "")
                vis_est = vis_chars / CHARS_PER_TOKEN
                if m.get("role") == "assistant":
                    tcs = m.get("tool_calls") or []
                    agent_comp.append(comp)
                    agent_vis.append(max(0, round(vis_est)))
                    # Crowd-out = thinking ate the whole completion budget and nothing visible came
                    # out. A tool-call turn ALSO has empty content, so requiring no tool calls here is
                    # not a refinement, it is the difference between a real signal and 642 false ones:
                    # the first version counted every tool-call turn as a truncation.
                    if vis_chars == 0 and comp > 0 and not tcs:
                        trunc += 1
                    tool_calls += len(tcs)
                    if vis_chars == 0 and comp > 0 and tcs:
                        toolcall_empty += 1
                else:
                    sim_comp.append(comp)
    rewards = [x for v in per_task.values() for x in v if x is not None]
    both = [task for task, v in per_task.items() if len(v) > 1]
    out["outcome"] = {
        "sims_total": len(rewards),
        "tasks": len(per_task),
        "trials_per_task": sorted({len(v) for v in per_task.values()}),
        "mean_reward": round(st.mean(rewards), 4) if rewards else None,
        "pass1": round(sum(1 for x in rewards if x == 1) / len(rewards), 4) if rewards else None,
        "tasks_with_any_pass": sum(1 for v in per_task.values() if any(x == 1 for x in v if x is not None)),
        "multi_trial_tasks": len(both),
        "termination": dict(term),
        "tool_calls_total": tool_calls,
        "sim_duration_s": tok_stats([round(x, 1) for x in durations]) if durations else None,
    }
    est_thinking = [max(0, c - v) for c, v in zip(agent_comp, agent_vis)]
    cap = harness_cap()
    out["messages"] = {
        "agent_completion_tokens_incl_thinking": tok_stats(agent_comp),
        "agent_messages_at_harness_cap": (sum(1 for c in agent_comp if c >= cap) if cap else None),
        "agent_visible_tokens_estimated": tok_stats(agent_vis),
        "agent_thinking_tokens_derived": tok_stats(est_thinking),
        "simulator_completion_tokens": tok_stats(sim_comp),
        "thinking_crowdout_empty_visible_messages": trunc,
        "toolcall_turns_with_empty_content": toolcall_empty,
        "agent_messages": len(agent_comp),
        "thinking_share_of_agent_completion": (round(sum(est_thinking) / max(1, sum(agent_comp)), 3)),
    }
    return out


def samples_for(arm):
    p = os.path.join(HERE, "results", f"2026-11-22-thinkbudget-{arm}", "engine_samples.jsonl")
    if not os.path.exists(p):
        return None
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    if not rows:
        return None
    def mx(k): return max((r.get(k) or 0) for r in rows)
    first, last = rows[0], rows[-1]
    life = {}
    for k in ("spill_moves", "kv_demotions", "suspensions"):
        life[k] = (last.get(k, 0) or 0) - (first.get(k, 0) or 0)
    widths = Counter()
    for r in rows:
        for k, v in (r.get("decode_batches_by_width") or {}).items():
            widths[k] = max(widths.get(k, 0), v or 0)
    busy = sum(1 for r in rows if r.get("active_requests"))
    modes = Counter(a.get("kv_mode") for r in rows for a in (r.get("active_requests") or []))
    caps = sorted({a.get("max_new_tokens") for r in rows for a in (r.get("active_requests") or [])
                   if a.get("max_new_tokens")})
    out = {"samples": len(rows), "window_s": round(rows[-1]["t"] - rows[0]["t"], 1),
           "kv_budget_tokens": mx("kv_budget_tokens"),
           "harness_max_new_tokens_observed": caps,
           "samples_with_live_requests": busy,
           "kv_mode_observations": dict(modes),
           "pages_active_max": mx("pages_active"), "pages_active_max_tokens": mx("pages_active") * 32,
           "queued_max": mx("queued"), "prefilling_max": mx("prefilling"), "decoding_max": mx("decoding"),
           "decode_batch_width_high_water": dict(sorted(widths.items())),
           "counter_deltas_over_window": life}
    # Provenance guard, threshold disclosed rather than tuned per arm: a wave that is really serving
    # requests shows nearly all samples with live requests (measured: 8192 441/443, 32768 436/438).
    # Anything far below that is not a serving wave. This catches the 65536 arm exactly: its dir was
    # re-entered by a stalled re-run, so its samples are 30/552 live over 92 min and must NOT be read
    # as the 65536 wave's engine record. See that dir's TENANCY.md.
    frac = busy / len(rows)
    if frac < 0.25:
        out["provenance_warning"] = (f"only {busy}/{len(rows)} samples show live requests: this file is "
                                     "not a serving wave's record and its engine numbers must not be "
                                     "compared with the other arms (see the arm dir's TENANCY.md)")
    return out


def harness_cap():
    """The cap the harness sends, read from run_wave.sh's own LLM_ARGS (declared, applies to every arm).
    This is the primary source: the engine-side max_new_tokens in each arm's samples is corroboration,
    and for the 65536 arm it is NOT usable evidence at all - its samples belong to a stalled re-run and
    show cap 8, which is foreign probe traffic, not this suite's 4096."""
    p = os.path.join(HERE, "run_wave.sh")
    if not os.path.exists(p):
        return None
    m = re.search(r'"max_tokens"\s*:\s*(\d+)', open(p, encoding="utf-8").read())
    return int(m.group(1)) if m else None


def arm_budget_from_record(arm):
    """The arm's --thinking-token-budget as recorded at wave start (supervisor_pins.txt is written by
    run_wave.sh from the RUNNING supervisor's ps line), not from the chain script's intent."""
    p = os.path.join(HERE, "results", f"2026-11-22-thinkbudget-{arm}", "supervisor_pins.txt")
    if not os.path.exists(p):
        return None
    m = re.search(r"--thinking-token-budget=(\d+)", open(p, encoding="utf-8", errors="replace").read())
    return int(m.group(1)) if m else None


def reachability(arm, r):
    """Can this arm's budget bind at all? Not an estimate: thinking tokens count INSIDE
    completion_tokens (measured on this stack), and the harness caps completion at max_new_tokens.
    So a budget above the cap is unreachable - the wave cannot produce a completion long enough to
    hit it - and the arm is inert by construction, whatever the flag says."""
    budget = arm_budget_from_record(arm)
    declared = harness_cap()
    caps = (r.get("engine_samples") or {}).get("harness_max_new_tokens_observed") or []
    cap = declared or (min(caps) if caps else None)
    obs_max = r["messages"]["agent_completion_tokens_incl_thinking"]
    obs_max = obs_max["max"] if obs_max else None
    verdict, why = "unknown", "missing budget or cap evidence"
    if budget and cap:
        if budget > cap:
            verdict, why = "inert", (f"budget {budget} > harness cap {cap}: completion cannot exceed the "
                                     f"cap, and thinking counts inside the cap, so the budget cannot bind")
        elif obs_max is not None and obs_max < budget:
            verdict, why = "never bound", (f"largest completion observed {obs_max} < budget {budget}")
        else:
            verdict, why = "possibly bound", f"largest completion {obs_max} vs budget {budget}"
    out = {"arm_budget_from_supervisor_pins": budget, "harness_cap_declared_in_run_wave": declared,
           "harness_cap_observed_in_samples": caps, "largest_agent_completion": obs_max,
           "messages_at_cap": r["messages"]["agent_messages_at_harness_cap"],
           "verdict": verdict, "why": why}
    if caps and declared and min(caps) != declared:
        out["samples_cap_disagreement"] = (f"samples show max_new_tokens {caps}, but the harness declares "
                                           f"{declared}: those samples are not this wave's traffic")
    return out


def pairwise(report):
    """Per-task agreement between arms, with an exact sign test. With trials=1 the only thing that can
    differ between two arms on the same task is pass/fail, so the flip counts (b, c) ARE the noise floor
    of an inert manipulation - which is what makes a null chain worth publishing."""
    def outcomes(arm):
        d, path = {}, None
        for dom in DOMS:
            d2, path = sims_for(arm, dom)
            if d2 is None:
                return {}
            for s in d2.get("simulations") or []:
                d[(dom, s.get("task_id"))] = (s.get("reward_info") or {}).get("reward")
        return d

    def sign_test(b, c):
        n = b + c
        if n == 0:
            return 1.0
        k = min(b, c)
        tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
        return min(1.0, 2 * tail)

    out = {}
    for x, y in (("32768", "8192"), ("32768", "65536"), ("8192", "65536")):
        ox, oy = outcomes(x), outcomes(y)
        common = sorted(set(ox) & set(oy))
        both_pass = sum(1 for t in common if ox[t] == 1 and oy[t] == 1)
        both_fail = sum(1 for t in common if ox[t] == 0 and oy[t] == 0)
        b = sum(1 for t in common if ox[t] == 1 and oy[t] == 0)   # only x passed
        c = sum(1 for t in common if ox[t] == 0 and oy[t] == 1)   # only y passed
        out[f"{x} vs {y}"] = {"tasks_compared": len(common), "both_pass": both_pass,
                              "both_fail": both_fail, "only_first_passes": b, "only_second_passes": c,
                              "flip_rate": round((b + c) / len(common), 4) if common else None,
                              "sign_test_p": round(sign_test(b, c), 4)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["8192", "65536", "32768"])
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    report = {}
    for arm in a.arms:
        r = analyze_arm(arm)
        r["engine_samples"] = samples_for(arm)
        r["budget_reachability"] = reachability(arm, r)
        report[arm] = r
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"arms": report, "pairwise": pairwise(report),
                       "harness_cap_declared_in_run_wave": harness_cap()}, f, indent=1)
    for arm, r in report.items():
        o, m = r["outcome"], r["messages"]
        print(f"\n=== arm {arm} ===")
        print(f"  outcome: sims {o['sims_total']} over {o['tasks']} tasks, trials {o['trials_per_task']}, "
              f"mean reward {o['mean_reward']}, pass^1 {o['pass1']}, any-pass tasks {o['tasks_with_any_pass']}")
        print(f"  termination {o['termination']}  tool calls {o['tool_calls_total']}")
        print(f"  per-domain: " + "; ".join(f"{d}={v.get('sims')} sims pass1={v.get('pass1')}"
                                            for d, v in r["domains"].items()))
        ac, th, vis = m["agent_completion_tokens_incl_thinking"], m["agent_thinking_tokens_derived"], m["agent_visible_tokens_estimated"]
        print(f"  agent msgs {m['agent_messages']}: completion(incl thinking) mean {ac['mean']} med {ac['median']} "
              f"max {ac['max']} total {ac['total']:,}; derived thinking mean {th['mean']} max {th['max']} "
              f"(share {m['thinking_share_of_agent_completion']}); visible est mean {vis['mean']}")
        print(f"  crowd-out (completion>0, no visible content, NO tool calls): "
              f"{m['thinking_crowdout_empty_visible_messages']}   "
              f"[tool-call turns with empty content, excluded: {m['toolcall_turns_with_empty_content']}]")
        sc = m["simulator_completion_tokens"]
        print(f"  simulator msgs: completion mean {sc['mean']} max {sc['max']}")
        br = r["budget_reachability"]
        print(f"  messages at the harness cap ({br['harness_cap_declared_in_run_wave']}): "
              f"{m['agent_messages_at_harness_cap']}   (the cap binds; the arm budget does not)")
        print(f"  budget reachability: arm budget {br['arm_budget_from_supervisor_pins']}, harness cap "
              f"{br['harness_cap_declared_in_run_wave']}, largest agent completion {br['largest_agent_completion']} "
              f"-> {br['verdict']}: {br['why']}")
        if br.get("samples_cap_disagreement"):
            print(f"  !! {br['samples_cap_disagreement']}")
        e = r.get("engine_samples")
        if e:
            print(f"  engine samples {e['samples']} over {e['window_s']}s "
                  f"({e['samples_with_live_requests']} with live requests): pages_active max {e['pages_active_max']} "
                  f"({e['pages_active_max_tokens']:,} tok), queued max {e['queued_max']}, prefilling max "
                  f"{e['prefilling_max']}, decoding max {e['decoding_max']}, widths {e['decode_batch_width_high_water']}, "
                  f"counters {e['counter_deltas_over_window']}, kv modes {e['kv_mode_observations']}")
            if e.get("provenance_warning"):
                print(f"  !! {e['provenance_warning']}")
        else:
            print("  engine samples: none")

    # arm-to-arm comparison against the control (the pinned 32768 arm, relaunched last in the chain)
    if all(x in report for x in ("8192", "65536", "32768")):
        ctl = report["32768"]
        print("\n=== vs the 32768 control (same-session, relaunched last) ===")
        hdr = f"{'metric':<38}{'32768 ctl':>12}{'8192':>12}{'d':>10}{'65536':>12}{'d':>10}"
        print(hdr)
        rows = [
            ("mean reward", lambda r: r["outcome"]["mean_reward"]),
            ("pass^1", lambda r: r["outcome"]["pass1"]),
            ("tasks with any pass", lambda r: r["outcome"]["tasks_with_any_pass"]),
            ("agent tool calls", lambda r: r["outcome"]["tool_calls_total"]),
            ("agent completion tok (mean)", lambda r: r["messages"]["agent_completion_tokens_incl_thinking"]["mean"]),
            ("agent completion tok (max)", lambda r: r["messages"]["agent_completion_tokens_incl_thinking"]["max"]),
            ("derived thinking tok (mean)", lambda r: r["messages"]["agent_thinking_tokens_derived"]["mean"]),
            ("derived thinking tok (max)", lambda r: r["messages"]["agent_thinking_tokens_derived"]["max"]),
            ("thinking share of completion", lambda r: r["messages"]["thinking_share_of_agent_completion"]),
            ("crowd-out messages", lambda r: r["messages"]["thinking_crowdout_empty_visible_messages"]),
            ("messages at harness cap", lambda r: r["messages"]["agent_messages_at_harness_cap"]),
            ("queued max", lambda r: (r["engine_samples"] or {}).get("queued_max")),
            ("pages_active max", lambda r: (r["engine_samples"] or {}).get("pages_active_max")),
        ]
        for label, f in rows:
            c, a, b = f(ctl), f(report["8192"]), f(report["65536"])
            def num(x):
                return "n/a" if x is None else f"{x:,}" if isinstance(x, int) else f"{x}"
            da = "" if a is None or c is None else f"{a - c:+g}"
            db = "" if b is None or c is None else f"{b - c:+g}"
            print(f"{label:<38}{num(c):>12}{num(a):>12}{da:>10}{num(b):>12}{db:>10}")
        print("\n  budget reachability per arm (computed, not asserted):")
        for x in ("8192", "65536", "32768"):
            b = report[x]["budget_reachability"]
            print(f"    {x}: {b['verdict']} - {b['why']}")
        print("\n  per-task agreement (trials=1, so flips are the whole story):")
        for label, v in pairwise(report).items():
            print(f"    {label}: {v['tasks_compared']} tasks | both pass {v['both_pass']}, both fail "
                  f"{v['both_fail']}, only-first {v['only_first_passes']}, only-second "
                  f"{v['only_second_passes']} | flip rate {v['flip_rate']} | sign test p={v['sign_test_p']}")
    return report


if __name__ == "__main__":
    main()
