#!/usr/bin/env python3
import json, os, time, urllib.request
import concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
# engine_probe helpers used to live in wiped /tmp; exec the sibling in this dir.
# Redirect its emit (this script's rows) to our own results file — set SPLASH_BENCH_OUT before
# the exec so engine_probe's module-level OUT/makedirs land there too.
os.environ.setdefault("SPLASH_BENCH_OUT", os.path.join(HERE, "results", "width512.jsonl"))
exec(open(os.path.join(HERE, "engine_probe.py")).read().split('if __name__')[0])
for width in (1, 2, 4):
    for rnd in (1, 2, 3):
        wait_idle(); a = snap(status())
        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=width) as ex:
            rs = list(ex.map(lambda _: chat(P_DECODE, 512), range(width)))
        wall = time.time() - t0
        b = snap(status())
        comp = sum(x["completion_tokens"] or 0 for x in rs)
        emit("width512", {"width": width, "round": rnd, "wall_s": round(wall, 2),
                          "completion_each": [x["completion_tokens"] for x in rs],
                          "aggregate_tok_s": round(comp / wall, 1),
                          "per_stream_tok_s": round(comp / width / wall, 1),
                          "decode_batch_delta": b["decode_batches"] - a["decode_batches"]})
        time.sleep(8)
