#!/usr/bin/env python3
"""Write the width-control record: per-arm engine widths + per-task agreement across three passes.

Three passes over the SAME 8 tasks that flipped in wave 2026-11-19a:
  wave   --max-concurrency 3 (the published wave, 2 trials)
  c1     --max-concurrency 1, detached, operator idle (2 trials)
  c3     --max-concurrency 3, detached, operator idle (2 trials, same-condition replication)
"""
import calendar
import glob
import json
import os
import re
import time
from collections import Counter

CTL = os.path.expanduser("~/tau2-width-control-detached-2026-11-19")
SIM = os.path.expanduser("~/tau2-bench/data/simulations")
OUT = os.path.expanduser("~/benchmarks/bench/tau2-bench/results/2026-11-19b-width-control")


def norm(s):
    return " ".join((s or "").split())


def load(path):
    out = {}
    if not os.path.exists(path):
        return out
    for s in json.load(open(path)).get("simulations") or []:
        out.setdefault(s["task_id"], {})[s.get("trial")] = s
    return out


def rw(s):
    return (s.get("reward_info") or {}).get("reward")


def user_identical(a, b):
    ua = [norm(m.get("content")) for m in a["messages"] if m["role"] == "user"]
    ub = [norm(m.get("content")) for m in b["messages"] if m["role"] == "user"]
    return sum(1 for x, y in zip(ua, ub) if x == y), min(len(ua), len(ub))


def first_diff(a, b):
    n = min(len(a["messages"]), len(b["messages"]))
    for i in range(n):
        ma, mb = a["messages"][i], b["messages"][i]
        if ma.get("role") != mb.get("role"):
            return i, "role-split"
        if ma.get("role") == "assistant":
            ta = [(tc["name"], norm(json.dumps(tc.get("arguments")))) for tc in (ma.get("tool_calls") or [])]
            tb = [(tc["name"], norm(json.dumps(tc.get("arguments")))) for tc in (mb.get("tool_calls") or [])]
            if ta != tb or norm(ma.get("content")) != norm(mb.get("content")):
                return i, "assistant"
        elif norm(ma.get("content")) != norm(mb.get("content")):
            return i, ma.get("role")
    return n, "identical-through"


# ---- engine side: per-arm decode widths from the 10 s samples -------------------------------
rows = [json.loads(l) for l in open(os.path.join(CTL, "engine_samples.jsonl")) if l.strip()]
log = open(os.path.join(CTL, "control.log")).read()


def ep(hms):
    return calendar.timegm(time.strptime("2026-11-20 " + hms.rstrip("Z"), "%Y-%m-%d %H:%M:%S"))


arms = {}
for c, dom, n, t0, t1 in re.findall(r"== arm c(\d) (\w+) n=(\d+) (\d\d:\d\d:\d\dZ)\n   exit=0 (\d\d:\d\d:\d\dZ)", log):
    w = [r for r in rows if ep(t0) <= float(r["t"]) <= ep(t1)]
    if not w:
        continue
    a, b = w[0], w[-1]
    key = f"c{c}"
    d = arms.setdefault(key, {"widths": Counter(), "peak_inflight": 0, "co_tenant": 0,
                              "max_inflight_prompt_tokens": 0,
                              "peak_kv_tokens": 0, "domains": {}})
    for k, v in b["decode_batches_by_width"].items():
        d["widths"][k] += int(v) - int(a["decode_batches_by_width"].get(k, 0))
    d["peak_inflight"] = max(d["peak_inflight"], max(len(r["active_requests"]) for r in w))
    d["max_inflight_prompt_tokens"] = max([d.get("max_inflight_prompt_tokens", 0)] +
                                          [int(q.get("prompt_tokens") or 0) for r in w
                                           for q in r["active_requests"]])
    d["co_tenant"] += sum(1 for r in w for q in r["active_requests"]
                          if int(q.get("prompt_tokens") or 0) > 20000)
    d["peak_kv_tokens"] = max(d["peak_kv_tokens"], max(int(r["kv_tokens_active"]) for r in w))
    d["domains"][dom] = {k: int(b["decode_batches_by_width"].get(k, 0)) -
                         int(a["decode_batches_by_width"].get(k, 0))
                         for k in ("b1", "b2", "b3", "b4")}

# ---- behaviour side -----------------------------------------------------------------------
wave = {}
for dom, d in (("airline", "wave-airline-2026-11-19"), ("retail", "wave-retail-2026-11-19"),
               ("telecom", "wave-telecom-2026-11-19")):
    for t, pd in load(os.path.join(SIM, d, "results.json")).items():
        wave[(dom, t)] = pd

passes = {"c1": {}, "c3": {}}
for key in ("c1", "c3"):
    for dom in ("airline", "retail", "telecom"):
        for t, pd in load(os.path.join(SIM, f"ctl-{key}-{dom}", "results.json")).items():
            passes[key][(dom, t)] = pd

tasks = sorted({k for k in passes["c1"]}, key=lambda k: (k[0], str(k[1])))
out_tasks = []
for dom, t in tasks:
    rec = {"domain": dom, "task_id": t, "passes": {}, "agreement": {}}
    for label, src in (("wave_c3", wave), ("c1", passes["c1"]), ("c3", passes["c3"])):
        pd = src.get((dom, t), {})
        tr = sorted(pd)
        rs = [rw(pd[x]) for x in tr]
        rec["passes"][label] = rs
        rec["agreement"][label] = (len(rs) == 2 and rs[0] == rs[1])
    c1 = passes["c1"][(dom, t)]
    a, b = c1[sorted(c1)[0]], c1[sorted(c1)[1]]
    ui, un = user_identical(a, b)
    idx, who = first_diff(a, b)
    rec["c1_user_turns_identical"] = f"{ui}/{un}"
    rec["c1_first_diff"] = {"index": idx, "role": who}
    allrs = [x for lab in ("wave_c3", "c1", "c3") for x in rec["passes"][lab] if x is not None]
    rec["sims_total"] = len(allrs)
    rec["reward_1_count"] = sum(1 for x in allrs if x == 1.0)
    out_tasks.append(rec)

flip_sets = {}
for label in ("wave_c3", "c1", "c3"):
    flip_sets[label] = sorted(str(t["task_id"]) for t in out_tasks if not t["agreement"][label])

summary = {
    "date": "2026-11-19b",
    "kind": "control experiment on tasks that flipped in wave 2026-11-19a (not a scored row)",
    "question": "does removing batching remove the tau2 flips?",
    "sampled_tasks": [str(t) for t in tasks and [k[1] for k in tasks]],
    "engine_arms": {k: {"decode_batches_by_width_delta": dict(v["widths"]),
                        "peak_requests_in_flight": v["peak_inflight"],
                        "max_inflight_prompt_tokens": v["max_inflight_prompt_tokens"],
                        "co_tenant_request_samples": v["co_tenant"],
                        "peak_kv_tokens": v["peak_kv_tokens"],
                        "per_domain_widths": v["domains"]} for k, v in arms.items()},
    "flips_per_arm": {k: len(v) for k, v in flip_sets.items()},
    "flip_sets": flip_sets,
    "flips_common_c1_and_c3": sorted(set(flip_sets["c1"]) & set(flip_sets["c3"])),
    "tasks": out_tasks,
}
os.makedirs(OUT, exist_ok=True)
json.dump(summary, open(os.path.join(OUT, "width_control.json"), "w"), indent=1, ensure_ascii=False)
open(os.path.join(OUT, "width_control.json"), "a").write("\n")

print("arm widths (lifetime deltas):")
for k, v in arms.items():
    print(f"  {k}: {dict(v['widths'])}  peak in flight {v['peak_inflight']}  "
          f"co-tenant {v['co_tenant']}  peak KV {v['peak_kv_tokens']:,} tok")
print("flips: wave c3", flip_sets["wave_c3"], "\n     control c1", flip_sets["c1"],
      "\n     control c3", flip_sets["c3"])
print("common to both control arms:", summary["flips_common_c1_and_c3"])
print("\nper task across all 6 sims (reward==1 count / sims):")
for t in out_tasks:
    print(f"  {t['domain']:8s} {str(t['task_id'])[:34]:34s} {t['reward_1_count']}/{t['sims_total']}   "
          f"c1 user turns identical {t['c1_user_turns_identical']}  first diff {t['c1_first_diff']['role']}@{t['c1_first_diff']['index']}")
