#!/usr/bin/env python3
"""Resolve-vs-Splash RAM sampler for the 96 GB headroom question.

Per-process number comes from /usr/bin/footprint (phys_footprint - the metric
macOS uses for memory pressure; 41 ms per call, unlike vmmap's ~1 s). RSS from
ps complements it (RSS excludes compressed pages). System counters from vm_stat
and vm.swapusage. No third-party deps, no ctypes (a ctypes proc_pid_rusage call
segfaulted - exit 139).

Usage: ram_sampler.py [seconds] [interval]      default 900 1.0
Phase labels are read each tick from phase.txt beside this script.
Writes ram.csv, ram.log, gpu_snapshots.log.
"""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PHASE = os.path.join(HERE, "phase.txt")
FOOT = "/usr/bin/footprint"
MB = 1e6
GiB = 1 << 30

FP_RE = re.compile(r"Footprint:\s*([0-9.]+)\s*([KMGT]?B)")
CAT_RE = re.compile(r"^\s*([0-9.]+)\s*([KMGT]?B)\s+.*\s+(IOAccelerator \(graphics\)|Metal|IOSurface|IOKit)$")


def to_bytes(value, unit):
    mult = {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}.get(unit, 1)
    return float(value) * mult


def footprint(pid):
    """(phys_footprint_bytes, {category: bytes}) or (None, {})."""
    try:
        out = subprocess.run([FOOT, "-p", str(pid)], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None, {}
    total = None
    cats = {}
    for line in out.splitlines():
        if "per page" in line:  # the summary header is the only line with both
            m = FP_RE.search(line)
            if m:
                total = to_bytes(m.group(1), m.group(2))
        c = CAT_RE.match(line)
        if c:
            cats[c.group(2)] = cats.get(c.group(2), 0) + to_bytes(c.group(1), c.group(2))
    return total, cats


def rss(pids):
    if not pids:
        return 0
    out = subprocess.run(["ps", "-o", "rss=", "-p", ",".join(str(p) for p in pids)],
                         capture_output=True, text=True)
    return sum(int(x) * 1024 for x in out.stdout.split() if x.isdigit())


def pids_of(pattern, exact=False):
    out = subprocess.run(["pgrep", "-x" if exact else "-f", pattern], capture_output=True, text=True)
    return [int(x) for x in out.stdout.split()]


def sys_counters():
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    page = 4096
    vals = {}
    wanted = ("Pages free", "Pages active", "Pages inactive", "Pages speculative",
              "Pages wired down", "Pages occupied by compressor", "File-backed pages",
              "Pages decompressed", "Pages compressed")
    for line in out.splitlines():
        if "page size of" in line:
            page = int(line.split("page size of")[1].split()[0])
        key = line.split(":")[0].strip().strip('"')  # vm_stat quotes some keys
        if key in wanted:
            try:
                vals[key] = int(line.split()[-1].rstrip("."))
            except ValueError:
                pass
    g = {k: vals.get(k, 0) * page for k in wanted}
    sw = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    m = re.search(r"used\s*=\s*([0-9.]+)([MG])", sw)
    g["swap"] = float(m.group(1)) * (1e6 if m.group(2) == "M" else 1e9) if m else 0
    return g


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 900.0
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    t0 = time.time()
    resolve, engine, server, dash = [], [], [], []
    last_scan, last_gpu = 0.0, 0.0
    peaks = {}
    with open(os.path.join(HERE, "ram.csv"), "w") as f, \
         open(os.path.join(HERE, "ram.log"), "a", buffering=1), \
         open(os.path.join(HERE, "gpu_snapshots.log"), "a", buffering=1) as glog:
        f.write("t,phase,resolve_fp,resolve_rss,engine_fp,server_fp,dash_fp,gpu_cat,"
                "wire,active,inactive,free,filebacked,compressor,decompressed,swap,nres\n")
        log = open(os.path.join(HERE, "ram.log"), "a", buffering=1)
        log.write(f"\n=== sampler start {time.strftime('%Y-%m-%d %H:%M:%S')} "
                  f"(interval {interval}s, {duration}s window) ===\n")
        prev_phase = None
        while time.time() - t0 < duration:
            now = time.time()
            tick = now
            t = now - t0
            if now - last_scan > 3.0:
                last_scan = now
                resolve = pids_of("/Applications/DaVinci Resolve")
                engine = pids_of("engine/splash serve-native")
                server = pids_of(r"server\.server")
                dash = pids_of("dash.py")
            r_fp, r_cats = 0, {}
            for p in resolve:
                fp, cats = footprint(p)
                r_fp += fp or 0
                for k, v in cats.items():
                    r_cats[k] = r_cats.get(k, 0) + v
            e_fp = sum(footprint(p)[0] or 0 for p in engine)
            s_fp = sum(footprint(p)[0] or 0 for p in server)
            d_fp = sum(footprint(p)[0] or 0 for p in dash)
            g = sys_counters()
            phase = "n/a"
            try:
                phase = open(PHASE).read().strip() or "n/a"
            except OSError:
                pass
            gpu = r_cats.get("IOAccelerator (graphics)", 0) + r_cats.get("Metal", 0) + r_cats.get("IOSurface", 0)
            gpu_mib = gpu / (1 << 20)
            f.write(f"{t:.1f},{phase},{r_fp/GiB:.3f},{rss(resolve)/GiB:.3f},{e_fp/GiB:.2f},"
                    f"{s_fp/GiB:.2f},{d_fp/GiB:.2f},{gpu_mib:.0f},"
                    f"{g['Pages wired down']/GiB:.2f},{g['Pages active']/GiB:.2f},"
                    f"{g['Pages inactive']/GiB:.2f},{g['Pages free']/GiB:.2f},"
                    f"{g['File-backed pages']/GiB:.2f},{g['Pages occupied by compressor']/GiB:.2f},"
                    f"{g['Pages decompressed']/GiB:.2f},{g['swap']/GiB:.2f},{len(resolve)}\n")
            f.flush()
            if phase != prev_phase:
                log.write(f"  phase -> {phase} at t={t:.1f}s\n")
                prev_phase = phase
            for key, val in (("resolve_fp", r_fp), ("wire", g["Pages wired down"]),
                             ("compressor", g["Pages occupied by compressor"]),
                             ("swap", g["swap"]), ("gpu_cat", gpu)):
                if val > peaks.get(key, (0, 0))[0]:
                    peaks[key] = (val, t)
                    log.write(f"  NEW PEAK {key} = {val/GiB:.2f} GiB at t={t:.1f}s phase={phase} "
                              f"(wire={g['Pages wired down']/GiB:.1f} inactive={g['Pages inactive']/GiB:.1f} "
                              f"free={g['Pages free']/GiB:.2f} engine={e_fp/GiB:.1f})\n")
            if now - last_gpu > 20 and resolve:
                last_gpu = now
                glog.write(f"--- t={t:.0f}s phase={phase}\n")
                for p in resolve:
                    try:
                        out = subprocess.run([FOOT, "-p", str(p)], capture_output=True, text=True, timeout=10).stdout
                    except Exception:
                        continue
                    keep = [ln for ln in out.splitlines()
                            if "Footprint:" in ln or re.search(r"(IOAccelerator|Metal|IOSurface|Malloc Large|MALLOC)", ln)]
                    glog.write("\n".join(keep[:12]) + "\n")
                glog.flush()
            time.sleep(max(0.0, interval - (time.time() - tick)))
        log.write("=== peaks: " + ", ".join(f"{k}={v[0]/GiB:.2f}GiB@{v[1]:.0f}s" for k, v in peaks.items()) + " ===\n")


if __name__ == "__main__":
    main()
