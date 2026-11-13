#!/usr/bin/env python3
"""Clean-window runner, 2026-11-13 — Splash engine suite + visual-venv baseline, run
from a standalone process with the operator session idle (tenancy lesson from the
11-12 rerun and the Resolve waves' +51% tax: the operator's own turns are engine
traffic). Resolve-agentic wave is driven separately (needs MCP grading after).

Stages (strictly serial; every timed stage single-tenant):
  0  header: date, engine /status cache state, splash/cv2 versions, repo HEAD
  1  engine warm: one unscored chat completion, then wait idle
  2  engine_probe.py   -> <run>/engine_probe.jsonl
  3  ladder_kv.py      -> <run>/ladder_kv.jsonl   (width ladder v3 + KV pressure v4)
  4  bench_visvenv.py  -> <run>/run3.json ; cold_run.py -> <run>/cold_run.txt
  5  driver2.py        -> <run>/agentic/          (4 tasks x 3, Qwen-served)
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
RUN = REPO / "bench" / "splash-concurrency" / "results" / "clean-2026-11-13"
SPLASH_DIR = REPO / "bench" / "splash-concurrency"
VIS_DIR = REPO / "bench" / "visual-venv"
VIS_PY = pathlib.Path(os.environ.get("VIS_VENV_PY", str(pathlib.Path.home() / "resolve-vision-venv312" / "bin" / "python")))
# Reruns on this host: export VIS_FIXTURES="/Volumes/<your-volume>/vision-detector-compare/bench-20261111"
# (the 2026-11-11 visual-venv bench fixtures — fixture_f240.png + fixture_f240_h264.mp4).
VIS_FIXTURES = pathlib.Path(os.environ.get("VIS_FIXTURES", "/Volumes/YourVolume/vision-detector-compare/bench-20261111"))
VIS_MODELS = pathlib.Path(os.environ.get("VIS_MODELS", str(pathlib.Path.home() / "resolve-vision-models")))
ENG = "http://127.0.0.1:8000"

def log(msg):
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def engine_status():
    with urllib.request.urlopen(f"{ENG}/status", timeout=10) as r:
        return json.load(r)

def wait_idle(max_s=120):
    t0 = time.time()
    while time.time() - t0 < max_s:
        s = engine_status()
        sched = s.get("scheduler", {})
        if all(sched.get(k, 0) == 0 for k in ("queued", "decoding", "prefilling")):
            return True
        time.sleep(2)
    return False

def stage(name, cmd, env=None, timeout=None):
    log(f"STAGE {name}: {' '.join(str(c) for c in cmd)}")
    t0 = time.time()
    p = subprocess.run(cmd, env={**os.environ, **(env or {})},
                       capture_output=True, text=True, timeout=timeout)
    (RUN / f"{name}.stdout.txt").write_text(p.stdout)
    (RUN / f"{name}.stderr.txt").write_text(p.stderr)
    log(f"STAGE {name}: rc={p.returncode} wall={time.time()-t0:.0f}s")
    return p.returncode

def main():
    RUN.mkdir(parents=True, exist_ok=True)
    # 0 header
    header = {"date": str(dt.date.today()),
              "note": "clean-window run: operator session idle during timed stages; driver is a standalone python process"}
    try:
        st = engine_status()
        header["engine_cache"] = {"hits": st["cache"]["hits"], "cold_misses": st["cache"]["cold_misses"],
                                  "hit_rate": round(st["cache"]["hit_rate"], 4)}
        header["engine_model"] = st["memory_plan"]["model"]["model_name"]
        header["kv_budget_tokens"] = st.get("kv", {}).get("budget_tokens") or st.get("kv")
    except Exception as e:
        header["engine_status_error"] = str(e)
    for k, cmd in (("splash_version", ["splash", "--version"]),
                   ("cv2_version", [str(VIS_PY), "-I", "-c", "import cv2;print(cv2.__version__)"]),
                   ("repo_head", ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"])):
        try:
            header[k] = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:
            header[k] = f"ERR {e}"
    (RUN / "header.json").write_text(json.dumps(header, indent=1))
    log(f"header: {header.get('splash_version')} | cv2 {header.get('cv2_version')} | HEAD {header.get('repo_head')}")

    # 1 warm (unscored)
    req = urllib.request.Request(f"{ENG}/v1/chat/completions", method="POST",
                                 headers={"Content-Type": "application/json"},
                                 data=json.dumps({"model": "warm", "messages": [{"role": "user", "content": "Reply OK."}],
                                                  "max_tokens": 16}).encode())
    try:
        urllib.request.urlopen(req, timeout=120).read()
        log("warm completion done")
    except Exception as e:
        log(f"warm completion failed: {e}")
    wait_idle()

    # 2 engine probe
    rc = stage("engine_probe", ["python3", "-I", str(SPLASH_DIR / "engine_probe.py")],
               env={"SPLASH_BENCH_OUT": str(RUN / "engine_probe.jsonl")}, timeout=600)
    wait_idle()

    # 3 ladder + KV
    rc = stage("ladder_kv", ["python3", "-I", str(SPLASH_DIR / "ladder_kv.py"),
                              "--out", str(RUN / "ladder_kv.jsonl")], timeout=3600)
    wait_idle()

    # 4 visual-venv
    if VIS_PY.exists() and (VIS_FIXTURES / "fixture_f240.png").exists():
        # cold_run.py reads a repo-local fixture that has since moved to the volume;
        # run2 (the noise-band reference) had no cold section either, so run3 stays comparable without it.
        rc = stage("vis_bench", [str(VIS_PY), "-I", str(VIS_DIR / "bench_visvenv.py"),
                                  "--out", str(RUN / "run3.json"),
                                  "--png", str(VIS_FIXTURES / "fixture_f240.png"),
                                  "--mp4", str(VIS_FIXTURES / "fixture_f240_h264.mp4"),
                                  "--models", str(VIS_MODELS)], timeout=900)
    else:
        log("visual fixtures or venv missing — stage skipped (see NOTES)")

    # 5 splash agentic (Qwen-served, fresh sessions)
    rc = stage("agentic", ["python3", "-I", str(SPLASH_DIR / "driver2.py")],
               env={"SPLASH_BENCH_DIR": str(RUN / "agentic")}, timeout=5400)

    log(f"ALL DONE — results in {RUN}")

if __name__ == "__main__":
    main()
