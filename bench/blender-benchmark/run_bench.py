#!/usr/bin/env python3
"""run_bench.py — the blender-benchmark suite driver.

Stages
  1. build    headless Blender builds/loads the scene
              (fixture GLB if present, else the procedural stand-in)
  2. render   Cycles sample sweep at 1920x1080, GPU if available:
              spp in {64, 128, 256}; score = samples/minute per config,
              summed — the same metric the official Blender Benchmark uses.
  3. verify   the 256-spp frame is graded by verify_render.py (vision venv):
              independent read-backs of exactly the brief's features —
              red dress, figure, lit lamp, glowing screen.

Usage: python3 run_bench.py [--tag NAME] [--sweep 64,128,256]
Writes results/<date>[-tag]/ {run.json, environment.json, frame_*.png,
verify.json} and repoints results/latest.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender")
VISION_PY = os.path.expanduser("~/resolve-vision-venv312/bin/python")
RES_W, RES_H = 1920, 1080


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def blender_version():
    out = sh([BLENDER, "--version"]).stdout
    m = re.search(r"Blender (\S+)", out)
    return m.group(1) if m else "unknown"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cycles_devices():
    probe = (
        "import bpy\n"
        "a = bpy.context.preferences.addons.get('cycles')\n"
        "if a:\n"
        "    cp = a.preferences\n"
        "    for t in ('OPTIX','CUDA','METAL','HIP','ONEAPI'):\n"
        "        try:\n            cp.compute_device_type = t\n"
        "        except TypeError:\n            continue\n"
        "        cp.get_devices()\n"
        "        ds = [d.name for d in cp.devices if d.type == t]\n"
        "        if ds:\n            print('GPUDEVICE|' + t + '|' + ds[0] + '|' + str(len(ds))); break\n"
    )
    r = sh([BLENDER, "-b", "--factory-startup", "--python-expr", probe])
    for line in r.stdout.splitlines():
        if line.startswith("GPUDEVICE|"):
            _, ctype, name, n = line.split("|", 3)
            return {"type": ctype, "name": name, "count": int(n)}
    return {"type": "CPU", "name": "cpu", "count": 1}


def ensure_scene(run_dir, composite=False, no_fixture=False):
    blend = HERE / "woman_red_dress.blend"
    fixture = HERE / "fixture" / "woman_red_dress.glb"
    cmd = [BLENDER, "-b", "--factory-startup", "--python", str(HERE / "build_scene.py"),
           "--", "--out", str(HERE)]
    if fixture.exists() and not no_fixture:
        cmd += ["--fixture", str(fixture)]
        if composite:
            cmd += ["--composite"]
    used = fixture.exists() and not no_fixture
    t0 = time.perf_counter()
    r = sh(cmd)
    ok = "SCENE_OK" in r.stdout
    line = next((l for l in r.stdout.splitlines() if "SCENE_OK" in l), "")
    # integrity check: the builder's own fixture marker must match intent,
    # or the run is inadmissible (a mis-flagged build silently changes the
    # fixture class, and fixture class is part of the run identity)
    built_with = "fixture=glb" in line
    if built_with != used:
        raise SystemExit(f"SCENE BUILD MISMATCH: requested fixture="
                         f"{'glb' if used else 'none'}, builder reported: {line}")
    return {
        "ok": ok,
        "seconds": round(time.perf_counter() - t0, 2),
        "fixture_class": "generated" if used else "procedural-standin",
        "fixture_used": str(fixture) if used else None,
        "fixture_sha256": sha(fixture) if used else None,
        "blend": str(blend),
        "blend_sha256": sha(blend) if blend.exists() else None,
        "scene_line": line,
    }


def render_config(blend, spp, out_png):
    expr = (
        "import bpy\n"
        f"s = bpy.context.scene\n"
        f"s.cycles.samples = {spp}\n"
        "s.cycles.use_denoising = False\n"
        "s.render.resolution_x = 1920; s.render.resolution_y = 1080\n"
        "s.render.resolution_percentage = 100\n"
        f"s.render.filepath = {str(out_png)!r}\n"
    )
    t0 = time.perf_counter()
    r = sh([BLENDER, "-b", "--factory-startup", str(blend),
            "--python-expr", expr, "--render-frame", "1"])
    wall = time.perf_counter() - t0
    m = re.search(r"Time:.*?(\d+):(\d+):(\d+\.\d+)", r.stdout)
    render_s = None
    if m:
        h, mn, sec = m.groups()
        render_s = int(h) * 3600 + int(mn) * 60 + float(sec)
    saved = Path(str(out_png) + "0001.png")
    return {
        "spp": spp,
        "wall_seconds": round(wall, 2),
        "blender_reported_seconds": round(render_s, 2) if render_s else None,
        "frame": saved.name if saved.exists() else None,
        "ok": saved.exists(),
    }


def startup_overhead():
    t0 = time.perf_counter()
    sh([BLENDER, "-b", "--factory-startup", "--python-expr", "pass"])
    return round(time.perf_counter() - t0, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=None)
    ap.add_argument("--sweep", default="64,128,256")
    ap.add_argument("--composite", action="store_true",
                    help="fixture GLB includes table+furniture; scene stages only lamp/screen assist")
    ap.add_argument("--no-fixture", action="store_true",
                    help="force the procedural stand-in even when a fixture GLB exists")
    args = ap.parse_args()

    date = dt.date.today().isoformat()
    run_name = date + (f"-{args.tag}" if args.tag else "")
    run_dir = HERE / "results" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    env = {
        "date": date,
        "blender": blender_version(),
        "blender_bin": BLENDER,
        "gpu": cycles_devices(),
        "os": f"macOS {platform.mac_ver()[0]}",
        "machine": platform.machine(),
        "resolution": [RES_W, RES_H],
        "denoising": False,
        "startup_overhead_seconds": startup_overhead(),
    }
    def write_json(path, obj):
        # public-commit hygiene: absolute home paths in records become "~"
        Path(path).write_text(json.dumps(obj, indent=2)
                              .replace(str(Path.home()), "~"))

    write_json(run_dir / "environment.json", env)

    scene = ensure_scene(run_dir, args.composite, args.no_fixture)
    if not scene["ok"]:
        print(json.dumps({"error": "scene build failed", "stderr_tail":
                          (scene["scene_line"] or "")[-500:]}, indent=2))
        sys.exit(1)
    blend = scene["blend"]

    renders = []
    for spp in (int(x) for x in args.sweep.split(",")):
        out = run_dir / f"frame_{spp}spp"
        r = render_config(blend, spp, out)
        if r["ok"]:
            base = Path(str(out) + "0001.png")
            final = run_dir / f"frame_{spp}spp.png"
            base.rename(final)
            r["frame"] = final.name
        print(f"  spp={spp}: wall {r['wall_seconds']}s ok={r['ok']}")
        renders.append(r)

    # score, official-style: samples per minute per config, summed
    score = 0.0
    for r in renders:
        secs = r["blender_reported_seconds"] or r["wall_seconds"]
        r["samples_per_minute"] = round(r["spp"] / (secs / 60.0), 1)
        score += r["samples_per_minute"]

    result = {"suite": "blender-benchmark", "run": run_name, "environment": env,
              "scene": scene, "renders": renders, "score_samples_per_minute_total": round(score, 1)}

    # independent grading of the 256-spp frame
    frame = run_dir / "frame_256spp.png"
    if not frame.exists():
        frame = sorted(run_dir.glob("frame_*spp.png"))[-1]
    if Path(VISION_PY).exists():
        v = sh([VISION_PY, str(HERE / "verify_render.py"), str(frame),
                "--json", str(run_dir / "verify.json")])
        result["verify"] = json.loads((run_dir / "verify.json").read_text()) \
            if (run_dir / "verify.json").exists() else {"raw": v.stdout, "stderr": v.stderr[-400:]}
    else:
        result["verify"] = {"skipped": "vision venv missing"}

    write_json(run_dir / "run.json", result)
    latest = HERE / "results" / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(run_name)
    print(json.dumps({"run": run_name, "score_total_samples_per_minute": round(score, 1),
                      "verify_summary": {k: v for k, v in
                                         (result.get("verify") or {}).items()
                                         if k in ("PASS", "checks", "score")}}, indent=2))


main()
