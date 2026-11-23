#!/usr/bin/env python3
"""Engine fingerprint: the committed method for Splash version transitions.

Why this exists (precedent: bench/resolve-agentic/mcp_fingerprint.py, MCP 5.3.3 -> 5.3.4): the
5.3.1 -> 5.3.3 pair was captured with ad-hoc greps whose method was never committed, so the record
could state a diff but nobody could re-run it. This pins the METHOD.

Read-only against the engine: it reads /status, /metrics and /v1/models. It generates no inference.

Modes
  capture  -> JSON fingerprint to stdout or --out
  diff     -> field-level delta between two fingerprints (the changed hash demands the diff,
              not the release notes' claim)

What is hashed, and why that set:
  engine binary          the native engine (`libexec/engine/splash`) - everything numerical lives here
  server tree            the Python server, hashed file-by-file into one digest - scheduling, admission,
                         cache policy, /status schema
  release.json           upstream's own build record
  INSTALL_RECEIPT.json   Homebrew's record: source url + sha, so the bottle itself is identified
  live identity          /status identity.cache: the model-layout and cache-build hashes, which is how
                         you tell whether the persistent cache survived the upgrade or started cold
  pinned argv            what the RUNNING supervisor was actually started with, not what a script says
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

CELLAR_RE = re.compile(r"/opt/homebrew/Cellar/splash/([^/]+)")
TREE_ROOTS = ("libexec/server",)
FILES = ("libexec/engine/splash", "libexec/release.json", "INSTALL_RECEIPT.json", "sbom.spdx.json")
STATUS_KEYS = (
    "schema_version", "ready", "maximum_context_tokens", "verify_rows", "reasoning_switch",
    "identity", "instance", "capabilities", "memory_plan", "ane_ffn", "streamed_experts",
    "streamed_table", "cache", "disk", "kv", "kv_spill", "scheduler", "admission", "frontend",
    "latency", "metrics", "requests", "weights", "metal", "memory_governor", "warmup",
    "constraint_masks", "draft_context", "tokenizer_cache",
)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(root):
    """Order-independent-per-file but deterministic: sha256 over sorted 'relpath\\0sha\\n' lines."""
    if not os.path.isdir(root):
        return None
    agg = hashlib.sha256()
    files = []
    for dirpath, _dirs, names in os.walk(root):
        for n in names:
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, root)
            if rel.endswith((".pyc",)) or "__pycache__" in rel:
                continue
            files.append((rel, sha256_file(p)))
    for rel, d in sorted(files):
        agg.update(f"{rel}\0{d}\n".encode())
    return {"digest": agg.hexdigest(), "files": len(files)}


def find_cellar():
    """Locate the Cellar dir of the splash the CLI actually resolves to."""
    try:
        cli = subprocess.run(["which", "splash"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        cli = ""
    cands = []
    for p in (cli, "/opt/homebrew/opt/splash"):
        try:
            real = os.path.realpath(p)
            m = CELLAR_RE.search(real)
            if m:
                cands.append(f"/opt/homebrew/Cellar/splash/{m.group(1)}")
        except Exception:
            pass
    for c in sorted(set(cands)):
        if os.path.isdir(c):
            return c
    base = "/opt/homebrew/Cellar/splash"
    if os.path.isdir(base):
        vs = sorted(os.listdir(base))
        if vs:
            return os.path.join(base, vs[-1])
    return None


def http_json(url, timeout=15):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def live_argv():
    try:
        out = subprocess.run(["pgrep", "-f", "-fl", "server.server"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return []
    lines = []
    for ln in out.splitlines():
        ln = ln.replace(os.path.expanduser("~"), "~")
        lines.append(ln)
    return lines


def capture(port):
    cellar = find_cellar()
    fp: dict = {"captured_at_utc": subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip()}
    fp["cellar"] = cellar.replace(os.path.expanduser("~"), "~") if cellar else None
    try:
        fp["splash_version"] = subprocess.run(["splash", "--version"], capture_output=True, text=True,
                                              timeout=30).stdout.strip()
    except Exception as e:
        fp["splash_version"] = f"error: {e}"
    if cellar:
        fp["files_sha256"] = {}
        for rel in FILES:
            p = os.path.join(cellar, rel)
            fp["files_sha256"][rel] = sha256_file(p) if os.path.exists(p) else None
        fp["server_tree"] = {}
        for rel in TREE_ROOTS:
            fp["server_tree"][rel] = tree_digest(os.path.join(cellar, rel))
        receipt = os.path.join(cellar, "INSTALL_RECEIPT.json")
        if os.path.exists(receipt):
            try:
                r = json.load(open(receipt))
                fp["install_receipt"] = {"version": r.get("version"), "time": r.get("time"),
                                         "source": r.get("source")}
            except Exception as e:
                fp["install_receipt"] = f"error: {e}"
    st = http_json(f"http://127.0.0.1:{port}/status")
    fp["status"] = {k: st.get(k) for k in STATUS_KEYS if k in st}
    # /metrics is Prometheus text, not JSON: fingerprint it by digest + the set of series names and
    # types, which is the part a version transition can move. Values would be noise.
    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=20).read().decode()
        names = sorted({ln.split("{")[0].split(" ")[0] for ln in raw.splitlines()
                        if ln and not ln.startswith("#")})
        types = {}
        for ln in raw.splitlines():
            if ln.startswith("# TYPE") and len(ln.split()) >= 3:
                types[ln.split()[2]] = ln.split()[1]
        fp["metrics"] = {"format": "prometheus-text", "bytes": len(raw),
                         "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                         "series": len(names), "series_names": names, "types": types}
    except Exception as e:
        fp["metrics"] = f"unavailable: {type(e).__name__}: {e}"
    try:
        fp["models"] = http_json(f"http://127.0.0.1:{port}/v1/models")
    except Exception as e:
        fp["models"] = f"unavailable: {e}"
    fp["live_argv"] = live_argv()
    return fp


def flat(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flat(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        out[prefix] = f"<list len {len(obj)}>"
    else:
        out[prefix] = obj
    return out


def diff(a_path, b_path):
    a, b = json.load(open(a_path)), json.load(open(b_path))
    fa, fb = flat(a), flat(b)
    keys = sorted(set(fa) | set(fb))
    # counters that only ever grow, and clock/instance fields, are not deltas of the instrument:
    # they are excluded so a version delta is visible without squinting.
    volatile = re.compile(r"(\.t$|started_at|pid|instance\.id|lifetime|_seconds$|captured_at)")
    noisy_prefix = ("status.metrics.", "status.latency.", "status.disk.", "status.cache.hits",
                    "status.cache.misses", "status.scheduler.", "status.requests.", "status.kv.",
                    "status.kv_spill.", "status.admission.", "status.warmup.", "status.tokenizer_cache.",
                    "status.weights.", "status.memory_actual", "metrics")
    changed, only_a, only_b, noise = [], [], [], 0
    for k in keys:
        if volatile.search(k):
            continue
        if k not in fa:
            only_b.append((k, fb[k]))
        elif k not in fb:
            only_a.append((k, fa[k]))
        elif fa[k] != fb[k]:
            if any(k.startswith(p) or k == p for p in noisy_prefix):
                noise += 1
            else:
                changed.append((k, fa[k], fb[k]))
    print(f"== structural delta ({len(changed)} fields, plus {noise} runtime-counter fields suppressed)")
    for k, x, y in changed:
        print(f"  {k}\n    - {x}\n    + {y}")
    if only_b:
        print(f"== fields only in the SECOND fingerprint ({len(only_b)}) - new API surface")
        for k, y in only_b:
            print(f"  + {k} = {y}")
    if only_a:
        print(f"== fields only in the FIRST fingerprint ({len(only_a)}) - removed API surface")
        for k, x in only_a:
            print(f"  - {k} = {x}")
    for label, key in (("version", "splash_version"), ("engine binary", "files_sha256/libexec/engine/splash"),
                       ("server tree", "server_tree/libexec/server"), ("release.json", "files_sha256/libexec/release.json"),
                       ("model layout", "status.identity.cache.loaded_model_layout_sha256"),
                       ("cache build", "status.identity.cache.build_id"),
                       ("maximum context", "status.maximum_context_tokens"),
                       ("batch width", "status.memory_plan.budget.maximum_batch_width"),
                       ("ANE FFN state", "status.ane_ffn.state")):
        x, y = fa.get(key), fb.get(key)
        print(f"  anchor {label:<15}: {'SAME' if x == y else 'MOVED'}  {str(x)[:48]} -> {str(y)[:48]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["capture", "diff"])
    ap.add_argument("--port", default=os.environ.get("SPLASH_PORT", "8000"))
    ap.add_argument("--out", default=None)
    ap.add_argument("files", nargs="*", help="for diff: two fingerprint JSON files")
    a = ap.parse_args()
    if a.mode == "capture":
        fp = capture(a.port)
        text = json.dumps(fp, indent=1, sort_keys=True, default=str)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print(f"wrote {a.out} ({len(text):,} chars)")
        else:
            print(text)
    else:
        if len(a.files) != 2:
            sys.exit("diff needs exactly two fingerprint files")
        diff(*a.files)


if __name__ == "__main__":
    main()
