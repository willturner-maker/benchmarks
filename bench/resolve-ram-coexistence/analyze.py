#!/usr/bin/env python3
"""Summarize ram.csv by phase: Resolve footprint, system wired, free, swap, GPU category."""
import csv
import sys
from collections import OrderedDict

GiB = 1 << 30
ROWS = 0
COLS = ("resolve_fp", "resolve_rss", "engine_fp", "gpu_cat", "wire", "active",
        "inactive", "free", "filebacked", "compressor", "swap", "nres")


def main(path):
    per = OrderedDict()
    with open(path) as f:
        for row in csv.DictReader(f):
            ph = row["phase"]
            d = per.setdefault(ph, {c: [] for c in COLS})
            for c in COLS:
                try:
                    d[c].append(float(row[c]))
                except (ValueError, KeyError):
                    pass
    hdr = f"{'phase':24s} {'res_fp max':>10s} {'res_fp end':>10s} {'wire max':>9s} {'free min':>9s} {'inact min':>10s} {'cmprsst':>8s} {'gpu MB max':>10s} {'n':>4s}"
    print(hdr)
    print("-" * len(hdr))
    for ph, d in per.items():
        if not d["resolve_fp"]:
            continue
        print(f"{ph:24s} {max(d['resolve_fp']):10.2f} {d['resolve_fp'][-1]:10.2f} "
              f"{max(d['wire']):9.2f} {min(d['free']):9.2f} {min(d['inactive']):10.2f} "
              f"{max(d['compressor']):8.2f} {max(d['gpu_cat']):10.0f} {len(d['resolve_fp']):4d}")
    with open(path) as f:
        rows = list(csv.DictReader(f))
    peak = max(rows, key=lambda r: float(r["resolve_fp"]))
    peak_wire = max(rows, key=lambda r: float(r["wire"]))
    print(f"\ntotal samples: {len(rows)}")
    print(f"Resolve footprint peak: {peak['resolve_fp']} GiB at t={peak['t']}s phase={peak['phase']} "
          f"(wire {peak['wire']}, free {peak['free']}, engine {peak['engine_fp']})")
    print(f"system wired peak:    {peak_wire['wire']} GiB at t={peak_wire['t']}s phase={peak_wire['phase']} "
          f"(Resolve {peak_wire['resolve_fp']}, engine {peak_wire['engine_fp']}, free {peak_wire['free']})")
    print(f"swap peak: {max(float(r['swap']) for r in rows):.2f} GiB; "
          f"compressor peak: {max(float(r['compressor']) for r in rows):.2f} GiB")
    print(f"min free during any phase: {min(float(r['free']) for r in rows):.2f} GiB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "merged.csv")  # run from this directory
