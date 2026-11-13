import json, statistics, itertools
recs=[json.loads(l) for l in open('results/probe-flag-2026-11-13/sweep.jsonl') if '"kind": "sample"' in l]
ok=[r for r in recs if r['success'] and r['duration_ms'] is not None]
print(f"samples: {len(recs)} total, {len(ok)} usable, {len(recs)-len(ok)} error-path")
counts={}
for r in ok:
    if r['variant']!='C': counts.setdefault(r['timeline'],set()).add(r['items'])
print("item counts per timeline:", {k:sorted(v) for k,v in sorted(counts.items())})
print()
hdr=f"{'cell':16s}"+"".join(f"{b:>16s}" for b in ["4.19.3","5.1.0","5.2.7"])
print(hdr)
cells=sorted({(r['timeline'],r['variant']) for r in ok})
for (tl,var) in cells:
    row=f"{tl+'/'+var:16s}"
    for b in ["4.19.3","5.1.0","5.2.7"]:
        v=[r['duration_ms'] for r in ok if r['timeline']==tl and r['variant']==var and r['build']==b]
        row+=f"{statistics.median(v):>8.0f}±{(max(v)-min(v)):3d}" if v else f"{'-':>16s}"
    print(row)
