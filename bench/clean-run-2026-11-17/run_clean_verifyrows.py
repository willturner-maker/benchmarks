#!/usr/bin/env python3
"""Clean-window runner: Splash 1.7.0 with --verify-rows all, then back to the daily config.

Run detached (nohup from a terminal), and make NO engine turns while it runs — the operator's
session is served by the same engine, which is exactly the contamination the 2026-11-13 clean
window removed and the three 2026-11-17 passes still carried.

Order of business:
  0. settle (the operator's turn must finish before the engine is restarted)
  1. determinism probe on the DAILY config (verify-rows auto): 5 identical greedy requests
  2. restart the engine with --verify-rows all
  3. record whether the persistent prefix cache survived the restart (warmth gate again)
  4. one unscored warm pass IF cold, then one scored pass (engine_probe + ladder_kv, full spec)
  5. determinism probe again, same code path, under verify-rows all
  6. agentic suite, 4 tasks x 3 trials, through the OpenCode driver (bench/splash-concurrency/
     driver_opencode.py) — this is what fills the Splash leaderboard's agentic column
  7. ALWAYS restore the daily config (start.sh args, verify-rows default = auto) and re-verify
     health, even if a stage above failed. The user's daily DaVinci work runs on the fastest
     settings; this script must never leave the engine in the deterministic-but-slower config.

Nothing here restarts the engine twice by accident: exactly two restarts, both logged with args.
"""
import hashlib, json, os, pathlib, shutil, subprocess, sys, time, urllib.request, urllib.error

HOME = pathlib.Path.home()
BENCH = HOME / "benchmarks" / "bench" / "splash-concurrency"
OUT = pathlib.Path(os.environ.get("CLEAN_RUN_OUT",
                                  BENCH / "results" / "clean-verifyrows-2026-11-17"))
LOGDIR = HOME / "Library" / "Logs" / "splash"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
BASE = "http://127.0.0.1:8000"
PY = "/opt/homebrew/opt/python@3.12/bin/python3.12"

# start.sh defaults, verified against the live process args (max-cache-disk=274877906944 = 256G,
# max-memory=60129542144 = 56G). This list IS the daily/performance config.
DAILY_ARGS = ["serve", "--model", MODEL, "--port", "8000",
              "--max-cache-disk", "256G", "--max-memory", "56G",
              "--expert-memory", "auto", "--default-reasoning-effort", "xhigh",
              "--thinking-token-budget", "16384", "--persistent-cache"]
VERIFY_ARGS = DAILY_ARGS + ["--verify-rows", "all"]

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S%z")
def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def status():
    try:
        with urllib.request.urlopen(BASE + "/status", timeout=10) as r:
            return json.load(r)
    except Exception:
        return {}

def snapshot(name):
    s = status()
    (OUT / f"status-{name}.json").write_text(json.dumps(s, indent=1))
    c = s.get("cache") or {}
    return {"ts": now(), "ready": s.get("ready"),
            "hit_rate": c.get("hit_rate"), "hits": c.get("hits"), "cold_misses": c.get("cold_misses"),
            "kv_disk_hit_tokens": c.get("kv_disk_hit_tokens"),
            "pages_cache": (s.get("kv") or {}).get("pages_cache")}

def wait_ready(max_s=240):
    t0 = time.time()
    while time.time() - t0 < max_s:
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
                ok = json.load(r).get("status") == "ok"
        except Exception:
            ok = False
        if ok and (status().get("ready")):
            return round(time.time() - t0, 1)
        time.sleep(3)
    raise RuntimeError(f"engine not ready within {max_s}s")

def restart(args, tag):
    """Stop the running engine and start it with `args`. Exactly one stop + one start."""
    subprocess.run(["pkill", "-f", "splash serve"], capture_output=True)
    for _ in range(30):
        try:
            urllib.request.urlopen(BASE + "/health", timeout=2); time.sleep(2)
        except Exception:
            break
    time.sleep(3)
    out = LOGDIR / f"splash-{tag}.out.log"; err = LOGDIR / f"splash-{tag}.err.log"
    with open(out, "w") as fo, open(err, "w") as fe:
        subprocess.Popen(["splash"] + args, stdout=fo, stderr=fe, start_new_session=True)
    ready_in = wait_ready()
    ps = subprocess.run(["bash", "-c", "ps -o command= -x -a | grep '[s]plash serve' | head -1"],
                        capture_output=True, text=True).stdout.strip()
    log(f"engine up ({tag}) in {ready_in}s; args: {ps[:200]}")
    return {"tag": tag, "ready_in_s": ready_in, "args": args, "ps": ps[:400]}

def chat(prompt, max_tokens=160, seed=7):
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "temperature": 0.0, "seed": seed,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"}), timeout=600) as r:
        d = json.loads(r.read())
    wall = time.time() - t0
    u = d.get("usage") or {}
    txt = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return {"wall_s": round(wall, 3), "completion_tokens": u.get("completion_tokens"),
            "prompt_tokens": u.get("prompt_tokens"),
            "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
            "sha256": hashlib.sha256(txt.encode()).hexdigest()[:16], "text_head": txt[:120]}

def determinism(tag, n=5):
    """Same greedy request n times. Bit-reproducible config -> 1 distinct hash.
    verify-rows auto is documented to vary, which is what this A/B measures."""
    prompt = ("List the first 40 prime numbers, one per line, and after them write exactly one "
              "sentence explaining why 2 is unusual among primes. Nothing else.")
    rows = [chat(prompt) for _ in range(n)]
    hs = {r["sha256"] for r in rows}
    toks = [r["completion_tokens"] for r in rows]
    rate = [round(r["completion_tokens"] / r["wall_s"], 1) for r in rows if r["completion_tokens"]]
    rec = {"tag": tag, "n": n, "distinct_outputs": len(hs), "hashes": sorted(hs),
           "bit_reproducible": len(hs) == 1, "completion_tokens": toks,
           "tok_s_each": rate, "median_tok_s": sorted(rate)[len(rate) // 2] if rate else None,
           "min_wall_s": min(r["wall_s"] for r in rows), "max_wall_s": max(r["wall_s"] for r in rows)}
    (OUT / f"determinism-{tag}.json").write_text(json.dumps({"probe": rec, "rows": rows}, indent=1))
    log(f"determinism[{tag}]: {len(hs)} distinct / {n} runs, median {rec['median_tok_s']} tok/s")
    return rec

def run_stage(script, extra, tag, env_extra=None):
    cmd = [PY, "-I", str(BENCH / script)] + extra
    env = os.environ.copy()
    if env_extra: env.update(env_extra)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(BENCH), capture_output=True, text=True, timeout=5400, env=env)
    (OUT / f"{tag}.stdout.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
    tail = [l for l in p.stdout.splitlines() if l.strip()][-3:]
    log(f"{tag}: rc={p.returncode} in {round(time.time()-t0)}s | {' | '.join(t[:110] for t in tail)}")
    return {"stage": tag, "rc": p.returncode, "wall_s": round(time.time() - t0, 1), "cmd": cmd}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    header = {"started": now(), "purpose": "Splash 1.7.0 clean-window pass under --verify-rows all, "
                                          "plus determinism A/B and the OpenCode agentic suite",
              "operator_tenancy": "detached runner; operator session made zero engine turns during "
                                  "timed stages (enforced by the settle delay below and the operator "
                                  "not interacting)"}
    (OUT / "header.json").write_text(json.dumps(header, indent=1))
    log("settle: 90 s so the operator's turn finishes before the engine is restarted")
    time.sleep(90)

    stages = []
    try:
        log("stage A: determinism probe on the DAILY config (verify-rows auto)")
        stages.append({"snapshot_before": snapshot("A-before-daily-probe")})
        det_auto = determinism("verify-rows-auto")
        stages.append({"determinism_daily": det_auto})
        stages.append({"snapshot_after": snapshot("A-after-daily-probe")})

        log("stage B: restart with --verify-rows all")
        stages.append({"restart_verify": restart(VERIFY_ARGS, "verifyall")})
        warm = snapshot("B-after-verifyall-restart")
        stages.append({"cache_after_restart": warm})
        cold = (warm.get("hit_rate") or 0) < 0.90
        log(f"cache after restart: hit_rate {warm.get('hit_rate')} cold_misses {warm.get('cold_misses')} "
            f"-> {'COLD, warming' if cold else 'warm, no warm-up pass needed'}")
        if cold:
            stages.append(run_stage("engine_probe.py", [], "warm-engine_probe",
                                    {"SPLASH_BENCH_OUT": str(OUT / "warm-engine_probe.jsonl")}))
            stages.append(run_stage("ladder_kv.py", ["--out", str(OUT / "warm-ladder_kv.jsonl")], "warm-ladder_kv"))
        stages.append({"snapshot_before_scored": snapshot("B-before-scored")})
        stages.append(run_stage("engine_probe.py", [], "engine_probe",
                                {"SPLASH_BENCH_OUT": str(OUT / "engine_probe.jsonl")}))
        stages.append(run_stage("ladder_kv.py", ["--out", str(OUT / "ladder_kv.jsonl")], "ladder_kv"))
        stages.append({"snapshot_after_scored": snapshot("B-after-scored")})

        log("stage C: determinism probe under --verify-rows all")
        det_all = determinism("verify-rows-all")
        stages.append({"determinism_verifyall": det_all})

        log("stage D: agentic suite 4 tasks x 3 trials through the OpenCode driver")
        stages.append(run_stage("driver_opencode.py",
                                ["--trials", "3", "--out", str(OUT / "agentic")], "agentic"))
        ag = OUT / "agentic" / "summary.jsonl"
        if ag.exists():
            rows = [json.loads(l) for l in ag.read_text().splitlines() if l.strip()]
            stages.append({"agentic_tally": {"n": len(rows),
                                             "verified": sum(r.get("verified") for r in rows),
                                             "honest": sum(r.get("honest") for r in rows)}})

        price = None
        if det_auto.get("median_tok_s") and det_all.get("median_tok_s"):
            price = round((det_all["median_tok_s"] - det_auto["median_tok_s"]) / det_auto["median_tok_s"] * 100, 1)
        summary = {"determinism_A_B": {"verify_rows_auto": {"distinct_outputs": det_auto["distinct_outputs"],
                                                            "median_tok_s": det_auto["median_tok_s"]},
                                       "verify_rows_all": {"distinct_outputs": det_all["distinct_outputs"],
                                                           "median_tok_s": det_all["median_tok_s"]},
                                       "decode_price_of_determinism_percent": price}}
        (OUT / "determinism-summary.json").write_text(json.dumps(summary, indent=1))
        log(f"determinism A/B: auto {det_auto['distinct_outputs']} distinct vs all "
            f"{det_all['distinct_outputs']} distinct; decode price {price}%")
    except Exception as e:
        log(f"!! stage failed: {e}")
        stages.append({"error": str(e)[:400]})
    finally:
        log("restoring the DAILY (fastest) config — this always runs")
        try:
            stages.append({"restart_daily": restart(DAILY_ARGS, "daily-restore")})
            fin = snapshot("Z-final")
            log(f"engine restored: ready={fin.get('ready')} hit_rate={fin.get('hit_rate')}")
        except Exception as e:
            log(f"!! restore failed: {e}; stages.append error")
            stages.append({"restore_error": str(e)[:400]})
        header.update({"finished": now(), "stages": stages,
                       "daily_config_restored": any("restart_daily" in s for s in stages)})
        (OUT / "header.json").write_text(json.dumps(header, indent=1))
        log("done")
    return 0

if __name__ == "__main__":
    sys.exit(main())
