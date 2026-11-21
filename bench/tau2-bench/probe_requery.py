#!/usr/bin/env python3
"""Same-request determinism probe: re-query byte-identical captured requests.

Two questions, two arms:
  seq : each captured request sent k times back-to-back, alone on the engine
        -> pure per-request engine determinism (cache state near-identical across repeats)
  mix : each request sent k times, each repeat concurrent with 2 OTHER distinct requests
        -> does batch width/lane interaction change the decoded choice for identical input?

Comparisons: repeat-to-repeat identity, and repeat vs the ORIGINAL response captured live
during the wave (the original ran under normal 3-way wave concurrency).

Model args, tools, prompts are the captured wire bodies verbatim - no reconstruction.
Engine is contacted DIRECTLY (proxy out of the path) for repeats; only the capture wave
went through the logging proxy.

Usage: probe_requery.py <captures.jsonl> <out.jsonl> [--reps 3] [--sample 40]
"""
import argparse, collections, json, random, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

ENGINE = "http://127.0.0.1:8000/v1/chat/completions"


def post(body, timeout=300):
    req = urllib.request.Request(ENGINE, data=json.dumps(body, ensure_ascii=False).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
    ch = (resp.get("choices") or [{}])[0]
    return ch.get("message"), ch.get("finish_reason")


def canon(msg):
    return json.dumps(msg, sort_keys=True, ensure_ascii=False) if msg is not None else "\x00none"


def canon_action(msg):
    """Engine-agnostic action identity: content + tool_calls only. reasoning_content is
    excluded - thinking text can differ while the acted choice does not."""
    if msg is None:
        return "\x00none"
    return json.dumps({"content": msg.get("content"),
                       "tool_calls": msg.get("tool_calls")}, sort_keys=True, ensure_ascii=False)


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b)) if len(a) != len(b) else -1


def content_of(msg):
    if not msg:
        return ""
    tc = msg.get("tool_calls") or []
    return (msg.get("content") or "") + "".join(json.dumps(t.get("function", {}), sort_keys=True) for t in tc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("captures")
    ap.add_argument("out")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--sample", type=int, default=40, help="per stratum (agent/user) per arm")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    recs = [json.loads(l) for l in open(a.captures)]
    bodies = [r for r in recs if isinstance(r.get("request"), dict) and r.get("message") is not None]
    agent = [r for r in bodies if r["request"].get("tools")]
    user = [r for r in bodies if not r["request"].get("tools")]
    rnd = random.Random(a.seed)
    # stratify each stratum by prompt-size quartile, then round-robin pick
    def stratified(pool, k):
        pool = sorted(pool, key=lambda r: len(json.dumps(r["request"].get("messages", []))))
        qs = [pool[i::max(1, len(pool) // 4)] for i in range(4)]
        picks, i = [], 0
        while len(picks) < k and any(qs):
            q = qs[i % 4]
            if q:
                picks.append(q.pop(rnd.randrange(len(q))))
            i += 1
        return picks

    sample = {"agent": stratified(agent, a.sample), "user": stratified(user, a.sample)}
    rows = []

    def record(stratum, arm, req, outs):
        full = [canon(m) for m, _ in outs]
        acts = [canon_action(m) for m, _ in outs]
        diffs = [first_diff(content_of(outs[i][0]), content_of(outs[j][0]))
                 for i in range(len(acts)) for j in range(i + 1, len(acts)) if acts[i] != acts[j]]
        rows.append({"stratum": stratum, "arm": arm, "reps": len(outs),
                     "agree_full": len(set(full)) == 1, "agree_action": len(set(acts)) == 1,
                     "n_distinct_actions": len(set(acts)),
                     "vs_original_action": canon_action(req["message"]) in acts,
                     "first_diff": min(diffs) if diffs else None,
                     "prompt_chars": len(json.dumps(req["request"].get("messages", [])))})

    # --- seq arm: reps back-to-back, nothing else in flight
    for stratum, picks in sample.items():
        for r in picks:
            outs = [post(r["request"]) for _ in range(a.reps)]
            record(stratum, "seq", r, outs)
            sys.stderr.write(f"seq {stratum} done\n")

    # --- mix arm: each repeat concurrent with 2 other distinct sampled requests (width-3 batch);
    #     the REPEATS of one request are compared to each other (each repeat has fresh mates)
    pool = [r for p in sample.values() for r in p]
    with ThreadPoolExecutor(max_workers=3) as ex:
        for stratum, picks in sample.items():
            for r in picks:
                outs = []
                for _ in range(a.reps):
                    mates = rnd.sample([p for p in pool if p is not r], 2)
                    res = list(ex.map(lambda b: post(b["request"]), [r] + mates))
                    outs.append(res[0])
                record(stratum, "mix", r, outs)

    with open(a.out, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    # summary
    stat = collections.defaultdict(lambda: [0, 0, 0, 0])  # agree_action, agree_full, vs_orig, n
    for row in rows:
        k = (row["arm"], row["stratum"])
        stat[k][0] += row["agree_action"]; stat[k][1] += row["agree_full"]
        stat[k][2] += row["vs_original_action"]; stat[k][3] += 1
    print(f"reps={a.reps}  sample per cell={a.sample}")
    for k in sorted(stat):
        aa, af, vo, n = stat[k]
        print(f"{k[0]:3s} {k[1]:5s}: identical-action {aa}/{n} ({100*aa/n:.1f} %)  "
              f"identical-message(incl thinking) {af}/{n} ({100*af/n:.1f} %)  "
              f"matched-original-action {vo}/{n} ({100*vo/n:.1f} %)")
    d = [row["first_diff"] for row in rows if row["first_diff"] is not None]
    if d:
        d.sort()
        print(f"first-difference offset when diverging: median {d[len(d)//2]} chars (n={len(d)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
