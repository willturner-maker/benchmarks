#!/usr/bin/env python3
"""MCP transition fingerprint — the sealed instrument for version moves.

Why this exists: the 5.3.1->5.3.3 fingerprints (mcp-fingerprint-{pre,post}5.3.3.json) were
captured with ad-hoc one-off greps whose exact rules were never committed, so the counts could
not be re-derived. This script pins the METHOD. Every field below is reproducible from the
installed tree alone, no Resolve connection needed.

Field definitions (v1, sealed 2026-11-18):
  package_version          package.json .version
  server_py_sha256         sha256 of src/server.py  -- the anchor: if this matches the pinned
                           post-5.3.3 record (73d706f3...), the Python tool/action surface is
                           byte-identical and NO count-based registry diff is needed.
  server_py_lines          len of that file
  fastmcp_tools            sorted names of functions decorated @mcp.tool* across src/**/*.py
  fastmcp_tool_count       len of the above
  action_branches          count of regex (if|elif) action == across src/**/*.py
  action_branch_server_py  same regex, src/server.py only
  df_mentions_server_py    count of regex drop.frame (case-insensitive) in src/server.py
  starttc_1                count of StartTC      (case-sensitive) in src/server.py
  starttc_2                count of start_tc     (case-sensitive) in src/server.py
  starttc_3                count of startTC      (case-sensitive) in src/server.py
  node_advanced_server     the other half (5.3.2/5.3.3 lived HERE):
      advanced_package_version  resolve-advanced/package.json .version (if present)
      vendor_dr{x,p,t}_files    *.mjs counts per vendor dir
      vendor_tree_hash          sha256 over sorted (relpath, sha256(bytes)) of resolve-advanced/vendor
      executable_tree_hash      sha256 over sorted (relpath, sha256) of resolve-advanced/server
      extractOFXTools_present   substring anywhere under resolve-advanced/vendor
      range_error_sites         RangeError occurrences in vendor/drp-format + vendor/drt-format
      drp_drt_starttc_sites     StartTC occurrences in those two dirs
      dropframe_guards          drop.frame (ci) occurrences in those two dirs
Any diff against a previous fingerprint is reported field-by-field.

Usage: python3 mcp_fingerprint.py --root "<installed tree>" --out FILE [--compare PREV.json]
"""
import argparse, hashlib, json, pathlib, re, sys, time


def sha256_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_hash(root: pathlib.Path):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(sha256_file(p).encode())
    return h.hexdigest()


def count(pattern, paths, flags=0):
    rx = re.compile(pattern, flags)
    return sum(len(rx.findall(p.read_text(errors="ignore"))) for p in paths)


def py_files(root):
    return sorted((root / "src").rglob("*.py"))


def tool_names(root):
    names = set()
    for p in py_files(root):
        txt = p.read_text(errors="ignore")
        for m in re.finditer(r'@mcp\.tool[^\n]*\n\s*(?:async\s+)?def\s+([A-Za-z_0-9]+)', txt):
            names.add(m.group(1))
    return sorted(names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare", default=None)
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    sp = root / "src" / "server.py"
    src = py_files(root)

    fp = {
        "instrument": "mcp_fingerprint.py v1",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "package_version": json.loads((root / "package.json").read_text()).get("version"),
        "server_py_sha256": sha256_file(sp),
        "server_py_lines": len(sp.read_text(errors="ignore").splitlines()),
        "fastmcp_tools": tool_names(root),
        "fastmcp_tool_count": len(tool_names(root)),
        "action_branches": count(r"(?:if|elif) action ==", src),
        "action_branch_server_py": count(r"(?:if|elif) action ==", [sp]),
        "df_mentions_server_py": count(r"drop\.frame", [sp], re.I),
        "starttc_1_StartTC": count(r"StartTC", [sp]),
        "starttc_2_start_tc": count(r"start_tc", [sp]),
        "starttc_3_startTC": count(r"startTC", [sp]),
    }

    adv = root / "resolve-advanced"
    if adv.exists():
        vend = adv / "vendor"
        two = sorted(list((vend / "drp-format").rglob("*"))) + sorted(list((vend / "drt-format").rglob("*")))
        two = [p for p in two if p.is_file()]
        fp["node_advanced_server"] = {
            "advanced_package_version": (json.loads((adv / "package.json").read_text()).get("version")
                                          if (adv / "package.json").exists() else None),
            "vendor_dr{x,p,t}_files": {d: len(list((vend / d).rglob("*.mjs")))
                                        for d in ("drx-codec", "drp-format", "drt-format")
                                        if (vend / d).exists()},
            "vendor_tree_hash": tree_hash(vend) if vend.exists() else None,
            "executable_tree_hash": tree_hash(adv / "server") if (adv / "server").exists() else None,
            "extractOFXTools_present": any("extractOFXTools" in p.read_text(errors="ignore")
                                            for p in vend.rglob("*") if p.is_file()),
            "range_error_sites": count(r"RangeError", two),
            "drp_drt_starttc_sites": count(r"StartTC", two),
            "dropframe_guards": count(r"drop\.frame", two, re.I),
        }

    out = pathlib.Path(a.out)
    out.write_text(json.dumps(fp, indent=1))
    print("wrote", out)

    if a.compare:
        prev = json.load(open(a.compare))
        diffs = []
        for k in sorted(set(prev) | set(fp)):
            if k in ("captured_at", "instrument"):
                continue
            if prev.get(k) != fp.get(k):
                pv, nv = prev.get(k), fp.get(k)
                if isinstance(pv, list) and isinstance(nv, list):
                    diffs.append({k: {"added": sorted(set(nv) - set(pv)),
                                       "removed": sorted(set(pv) - set(nv))}})
                elif isinstance(pv, dict) and isinstance(nv, dict):
                    inner = {ik: {"prev": pv.get(ik), "now": nv.get(ik)}
                             for ik in sorted(set(pv) | set(nv)) if pv.get(ik) != nv.get(ik)}
                    diffs.append({k: inner})
                else:
                    diffs.append({k: {"prev": pv, "now": nv}})
        verdict = {"compared_to": a.compare, "fields_differing": len(diffs), "diff": diffs,
                   "server_py_identical": prev.get("server_py_sha256") == fp["server_py_sha256"]}
        print(json.dumps(verdict, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
