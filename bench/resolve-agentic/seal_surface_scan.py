#!/usr/bin/env python3
"""Tool-surface / seal scan over a wave's archived transcripts.

Separates three things the naive allowlist check conflates:
  1. COMMUNITY completed/error — the `davinci-resolve_*` (underscore) calls: the intended surface.
  2. OTHER-SERVER completed — a call that reached a server outside KEEP. THAT is a real seal
     breach. (Hyphen-mangled names like `davinci-resolve-media_pool` are NOT breaches: the
     harness answers "No tool named …", nothing reaches any server. Their distribution is still
     reported: it is a harness-friction measure, and in one 2026-11-17h trial it was fatal.)
  3. BUILTIN-STUDIO completed — `davinci-resolve-builtin_*` (Resolve scripting: run_script,
     search_scripting_api). Allowed by KEEP by design since v2, so NOT a breach, but the share of
     work done through the scripting bridge vs the community MCP is a first-order behavioral
     finding and must be reported per trial.

Usage: python3 seal_surface_scan.py --wave results/<wave> [--also results/<other-wave>] --out <json>
"""
import argparse, collections, json, pathlib

KEEP_PREFIXES = ("davinci-resolve_", "davinci-resolve-advanced_", "davinci-resolve-builtin_")
BUILTIN = "davinci-resolve-builtin_"
ADVANCED = "davinci-resolve-advanced_"


def events(p):
    for ln in pathlib.Path(p).read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                yield json.loads(ln)
            except Exception:
                continue


def scan(wdir):
    per, tot = {}, collections.Counter()
    for ev in sorted(pathlib.Path(wdir).glob("*/events.json")):
        task = ev.parent.name
        c = collections.Counter()
        mangled = collections.Counter()
        for e in events(ev):
            if e.get("type") != "tool_use":
                continue
            part = e.get("part") or {}
            name = str(part.get("tool") or "")
            status = (part.get("state") or {}).get("status")
            if status == "error" and "-" in name and not name.startswith(KEEP_PREFIXES):
                c["mangled_name_error"] += 1
                mangled[name] += 1
            elif name.startswith(BUILTIN):
                c["studio_scripting_" + str(status)] += 1
            elif name.startswith(ADVANCED):
                c["advanced_db_" + str(status)] += 1
            elif name.startswith("davinci-resolve_"):
                c["community_" + str(status)] += 1
            elif status == "completed":
                c["OUTSIDE_SEAL_COMPLETED"] += 1          # real breach if non-zero
                mangled[name] += 1
            else:
                c["other_error"] += 1
        per[task] = {"counts": dict(c), "top_mangled": mangled.most_common(5)}
        tot.update(c)
    return per, dict(tot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    ap.add_argument("--also", default="", help="comma list of extra wave dirs to scan for comparison")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = {}
    for w in [a.wave] + [x for x in a.also.split(",") if x]:
        per, tot = scan(pathlib.Path(w) / "sessions")
        out[w] = {"total": tot, "per_trial": per,
                  "seal_breach": tot.get("OUTSIDE_SEAL_COMPLETED", 0) > 0}
        print(f"{w}: {tot} | seal_breach={out[w]['seal_breach']}")
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
