#!/usr/bin/env python3
"""Triage the tasks whose two trials disagreed in tau2-bench wave 2026-11-19a.

The question this answers: WHEN a flip happens, what actually changed between the two trials?

Measured, not assumed:
  component    which reward_basis component changed (DB / COMMUNICATE / ENV_ASSERTION / ACTION)
  first_diff   the first message index at which the two trials differ, and WHO produced it
               ('user' = the user simulator said something different; 'assistant' = the agent did)
  onset        first_diff / min(len) as a fraction of the conversation
  user_var     whether the two trials' user turns differ at all
  direction    1->0 or 0->1

Context that matters: tau2 derives a DIFFERENT seed per trial (wave records show 626729 / 373753 for
--seed 300), so the two trials of a task are not the same conversation replayed -- the user simulator is a
fresh sample. A flip whose first difference is a user message is user-sampling variance; a flip whose first
difference is an agent message under identical prior context is engine nondeterminism. Those are different
findings and must not be pooled.
"""
import json
import os
import sys
from collections import Counter, defaultdict

SIM = os.path.expanduser("~/tau2-bench/data/simulations")
DOMAINS = ("airline", "retail", "telecom")
BASES = ("DB", "COMMUNICATE", "ENV_ASSERTION", "ACTION", "NL_ASSERTION")


def norm(s):
    return " ".join((s or "").split())


def first_diff(a, b):
    """(index, role) of the first differing message, by role-aligned index."""
    n = min(len(a), len(b))
    for i in range(n):
        ma, mb = a[i], b[i]
        if ma.get("role") != mb.get("role"):
            return i, "role-split"
        if ma.get("role") == "assistant":
            ta = [(tc["name"], norm(json.dumps(tc.get("arguments")))) for tc in (ma.get("tool_calls") or [])]
            tb = [(tc["name"], norm(json.dumps(tc.get("arguments")))) for tc in (mb.get("tool_calls") or [])]
            if ta != tb or norm(ma.get("content")) != norm(mb.get("content")):
                return i, "assistant"
        else:
            if norm(ma.get("content")) != norm(mb.get("content")):
                return i, ma.get("role")
    return n, "length-only"


def comp_flip(ra, rb):
    ca, cb = (ra or {}).get("reward_breakdown") or {}, (rb or {}).get("reward_breakdown") or {}
    return [f"{k}:{ca.get(k)}->{cb.get(k)}" for k in BASES if k in ca or k in cb
            if ca.get(k) != cb.get(k)]


def main():
    import argparse
    from itertools import combinations
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", default="2026-11-19",
                    help="wave token in the tau2 save name; both orderings (wave-<dom>-<w> / wave-<w>-<dom>) are tried")
    ap.add_argument("--pairs", default="adjacent", choices=["adjacent", "all"],
                    help="which trial pairs to triage for tasks with >=3 trials")
    args = ap.parse_args()
    rows = []
    for d in DOMAINS:
        path = next((f"{SIM}/wave-{w}/results.json"
                     for w in (f"{d}-{args.wave}", f"{args.wave}-{d}")
                     if os.path.exists(f"{SIM}/wave-{w}/results.json")), None)
        if not path:
            sys.exit(f"no results.json for wave {args.wave} domain {d}")
        res = json.load(open(path))
        by = defaultdict(list)
        for s in res["simulations"]:
            by[s["task_id"]].append(s)
        for t, tr in by.items():
            if len(tr) < 2:
                continue
            tr.sort(key=lambda x: x.get("trial") or 0)
            pairs = list(combinations(tr, 2)) if args.pairs == "all" \
                else [(tr[i], tr[i + 1]) for i in range(len(tr) - 1)]
            for a, b in pairs:
                ra, rb = a.get("reward_info") or {}, b.get("reward_info") or {}
                if (ra.get("reward") == 1.0) == (rb.get("reward") == 1.0):
                    continue
                idx, who = first_diff(a["messages"], b["messages"])
                ua = [norm(m.get("content")) for m in a["messages"] if m["role"] == "user"]
                ub = [norm(m.get("content")) for m in b["messages"] if m["role"] == "user"]
                n = min(len(a["messages"]), len(b["messages"]))
                tc = lambda s: sum(len(m.get("tool_calls") or []) for m in s["messages"])
                rows.append({
                    "domain": d, "task": t,
                    "dir": f"{ra.get('reward')}->{rb.get('reward')}",
                    "comp": comp_flip(ra, rb),
                    "db": f"{(ra.get('db_check') or {}).get('db_match')}->{(rb.get('db_check') or {}).get('db_match')}",
                "who": who, "idx": idx, "onset": round(idx / max(1, n), 2), "turns": n,
                "user_var": sum(1 for x, y in zip(ua, ub) if x != y), "user_turns": min(len(ua), len(ub)),
                "tools": f"{tc(a)}->{tc(b)}",
                "seeds": f"{a.get('seed')}|{b.get('seed')}",
            })
    rows.sort(key=lambda r: (r["domain"], -r["onset"]))
    print(f"flipping tasks: {len(rows)}\n")
    print(f"{'domain':9s} {'task':34s} {'dir':11s} {'who@idx/onset':17s} {'user turns differing':21s} {'tools':10s} components")
    for r in rows:
        t = str(r["task"])[:33]
        print(f"{r['domain']:9s} {t:34s} {r['dir']:11s} {r['who']+'@'+str(r['idx'])+'/'+str(r['onset']):17s} "
              f"{str(r['user_var'])+'/'+str(r['user_turns']):21s} {r['tools']:10s} {';'.join(r['comp'])}")

    print("\n--- classification (first difference is the discriminator) ---")
    c = Counter(r["who"] for r in rows)
    print("first differing turn produced by:", dict(c))
    early = sum(1 for r in rows if r["who"] == "user" and r["idx"] <= 1)
    print(f"user diverges at turn 0-1 (a different opening): {early}")
    print(f"agent is the first to diverge: {c.get('assistant',0)}")
    print(f"length-only (identical prefix, one conversation just runs longer): {c.get('length-only',0)}")
    print("\ncomponents that flipped:")
    cc = Counter(x.split(':')[0] for r in rows for x in r["comp"])
    print(" ", dict(cc))
    print("\nDB end-state changed:", sum(1 for r in rows if r["db"] != f"{r['db'].split('->')[0]}->{r['db'].split('->')[0]}"))
    print("direction 1->0:", sum(1 for r in rows if r["dir"].startswith("1.0->0")),
          " 0->1:", sum(1 for r in rows if r["dir"].startswith("0.0->1")))
    print("\nper domain:")
    for d in DOMAINS:
        rs = [r for r in rows if r["domain"] == d]
        print(f"  {d:8s} flips {len(rs):2d}  agent-first {sum(1 for r in rs if r['who']=='assistant')}  "
              f"user-first {sum(1 for r in rs if r['who']=='user')}  len-only {sum(1 for r in rs if r['who']=='length-only')}  "
              f"median onset {sorted(r['onset'] for r in rs)[len(rs)//2] if rs else '-'}")
    print("\nNOTE seeds per trial differ by design (626729 vs 373753 for --seed 300), so pass^k samples a")
    print("fresh user simulator per trial. Engine-nondeterminism share needs a same-seed repeat, not this table.")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", args.wave, "flip_triage.json")
    json.dump(rows, open(out, "w"), indent=1)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
