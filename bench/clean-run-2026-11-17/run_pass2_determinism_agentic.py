#!/usr/bin/env python3
"""Corrected clean-window run #2 — determinism A/B done properly, plus the agentic row.

Why a second runner: run #1 (10:14) silently NO-OPped both restarts. `pkill -f "splash serve"`
does not match the supervisor, whose command line is
`…/libexec/python/bin/python3 -u -P -m server.server …`; it only matched the `serve-native` child,
which the supervisor respawned with the original args, and the follow-up `splash serve` refused with
"already serving (PID 1359 … phase ready)". So stage B/C of run #1 measured the SAME auto config
(its ladder numbers remain valid as a clean-window auto pass; its verify-rows claim does not).
And its determinism probe hashed `message.content` only, which is EMPTY when the whole budget goes
to reasoning tokens — every hash was e3b0c442…, the SHA-256 of an empty string. Both bugs fixed here.

What this run does, in order:
  0. settle 60 s so the operator's turn ends before the engine is restarted
  1. shell-cwd probe: one sealed session runs `pwd` (proves the shell-tool cwd inheritance that
     made three S3 artifacts collide in one path)
  2. determinism probe, current DAILY config (--verify-rows auto), hashing content + reasoning
  3. reasoning-effort cost probe (low / medium / xhigh x3) — the knob the daily config sets to xhigh
  4. HARD stop (supervisor + child) and start with --verify-rows all; PROVE the mode from the
     engine's own startup banner, not from the args we passed
  5. determinism probe again under verify-rows all
  6. HARD stop and restore the DAILY config; prove banner=auto, re-check /health and cache restore
  7. agentic suite, 4 tasks x 3 trials, through the fixed driver_opencode.py (on the daily config)
  8. write records
"""
import hashlib, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.request

HOME = pathlib.Path.home()
BENCH = HOME / "benchmarks" / "bench" / "splash-concurrency"
OUT = pathlib.Path(os.environ.get("CLEAN_RUN_OUT",
                                  BENCH / "results" / "clean-verifyrows-2026-11-17-pass2"))
LOGDIR = HOME / "Library" / "Logs" / "splash"
MODEL = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
BASE = "http://127.0.0.1:8000"
PY = "/opt/homebrew/opt/python@3.12/bin/python3.12"

DAILY_ARGS = ["serve", "--model", MODEL, "--port", "8000",
              "--max-cache-disk", "256G", "--max-memory", "56G", "--expert-memory", "auto",
              "--default-reasoning-effort", "xhigh", "--thinking-token-budget", "16384",
              "--persistent-cache"]
VERIFY_ARGS = DAILY_ARGS + ["--verify-rows", "all"]

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
def status():
    try:
        with urllib.request.urlopen(BASE + "/status", timeout=10) as r: return json.load(r)
    except Exception: return {}

def health_ok():
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
            return json.load(r).get("status") == "ok"
    except Exception: return False

def pids(pat):
    r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]

def hard_stop():
    """Stop the supervisor AND the engine child, then wait for the port to actually refuse."""
    sup, eng = pids("server.server"), pids("serve-native")
    log(f"stopping: supervisor {sup} engine {eng}")
    for p in sup: subprocess.run(["kill", "-TERM", str(p)])
    time.sleep(3)
    for p in sup + eng:
        if pids(str(p)) and p in pids("server.server") + pids("serve-native"):
            subprocess.run(["kill", "-KILL", str(p)])
    for p in pids("serve-native") + pids("server.server"):
        subprocess.run(["kill", "-KILL", str(p)])
    t0 = time.time()
    while health_ok() and time.time() - t0 < 90: time.sleep(2)
    down = not health_ok()
    log(f"engine down: {down} (waited {round(time.time()-t0,1)}s)")
    return {"supervisor": sup, "engine": eng, "port_refused": down, "stop_s": round(time.time()-t0, 1)}

def start(args, tag):
    out, err = LOGDIR / f"splash-{tag}.out.log", LOGDIR / f"splash-{tag}.err.log"
    t0 = time.time()
    with open(out, "w") as fo, open(err, "w") as fe:
        subprocess.Popen(["splash"] + args, stdout=fo, stderr=fe, start_new_session=True)
    t_ready = None
    while time.time() - t0 < 300:
        if health_ok() and status().get("ready"): t_ready = round(time.time() - t0, 1); break
        time.sleep(3)
    txt = err.read_text(errors="ignore")
    mode = "unknown"
    m = re.search(r"--verify-rows (auto|all)", txt)
    if m: mode = m.group(1)
    restore = re.search(r"took back (\d+) restore points over (\d+) KV blocks \(([\d.]+ \w+)\)", txt)
    log(f"started ({tag}) ready in {t_ready}s | verify-rows banner: {mode} | "
        f"cache restore: {restore.group(0) if restore else 'no restore line in log'}")
    return {"tag": tag, "ready_in_s": t_ready, "verify_rows_in_banner": mode,
            "cache_restore_line": restore.group(0) if restore else None,
            "startup_err_head": txt[:600]}

def chat(prompt, max_tokens=500, effort=None, seed=7):
    body = {"model": MODEL, "max_tokens": max_tokens, "temperature": 0.0, "seed": seed,
            "messages": [{"role": "user", "content": prompt}]}
    if effort: body["reasoning_effort"] = effort
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}), timeout=900) as r:
        d = json.loads(r.read())
    wall = time.time() - t0
    u = d.get("usage") or {}
    msg = (d.get("choices") or [{}])[0].get("message") or {}
    content, reasoning = msg.get("content") or "", msg.get("reasoning_content") or ""
    return {"wall_s": round(wall, 3), "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
            "content_len": len(content), "reasoning_len": len(reasoning),
            "sha256": hashlib.sha256((content + "\x1f" + reasoning).encode()).hexdigest()[:16],
            "content_head": content[:100], "finish": (d.get("choices") or [{}])[0].get("finish_reason")}

def determinism(tag, n=5):
    prompt = ("List the first 40 prime numbers, one per line, then write exactly one sentence "
              "explaining why 2 is unusual among primes. Nothing else.")
    rows = [chat(prompt, max_tokens=500) for _ in range(n)]
    blank = [r for r in rows if r["content_len"] + r["reasoning_len"] == 0]
    hs = {r["sha256"] for r in rows}
    rate = [round(r["completion_tokens"] / r["wall_s"], 1) for r in rows if r["completion_tokens"]]
    rec = {"tag": tag, "n": n, "blank_responses": len(blank), "distinct_outputs": len(hs),
           "hashes": sorted(hs), "bit_reproducible": len(hs) == 1 and not blank,
           "completion_tokens": [r["completion_tokens"] for r in rows],
           "reasoning_tokens": [r["reasoning_tokens"] for r in rows],
           "median_tok_s": sorted(rate)[len(rate)//2] if rate else None,
           "median_wall_s": sorted(r["wall_s"] for r in rows)[n//2]}
    (OUT / f"determinism-{tag}.json").write_text(json.dumps({"probe": rec, "rows": rows}, indent=1))
    log(f"determinism[{tag}]: {len(hs)} distinct / {n}, blank {len(blank)}, "
        f"median {rec['median_tok_s']} tok/s, wall {rec['median_wall_s']}s")
    return rec

def effort_probe():
    prompt = ("You are reviewing a DaVinci Resolve timeline. Timeline has 4 items: A (0-120), "
              "B (120-300), C (300-420), D (420-600). A 30-frame insert goes at frame 200 with a "
              "12-frame dissolve centred on the cut. State which items shift, by how much, and "
              "the resulting start frame of the last item. Finish with ANSWER=<number>.")
    rows = {}
    for eff in ("low", "medium", "xhigh"):
        runs = [chat(prompt, max_tokens=1200, effort=eff) for _ in range(3)]
        rows[eff] = {"wall_s": [r["wall_s"] for r in runs],
                     "completion_tokens": [r["completion_tokens"] for r in runs],
                     "reasoning_tokens": [r["reasoning_tokens"] for r in runs],
                     "median_wall_s": sorted(r["wall_s"] for r in runs)[1],
                     "answers": [re.findall(r"ANSWER=(-?\d+)", r["content_head"] + r["content_head"]) for r in runs]}
        log(f"effort {eff}: median wall {rows[eff]['median_wall_s']}s, "
            f"reasoning tokens {rows[eff]['reasoning_tokens']}")
    base = rows["xhigh"]["median_wall_s"]
    for e in rows:
        rows[e]["vs_xhigh_percent"] = round((rows[e]["median_wall_s"] - base) / base * 100, 1)
    (OUT / "reasoning-effort-cost.json").write_text(json.dumps(rows, indent=1))
    return rows

def shell_cwd_probe():
    """One sealed session runs `pwd`; proves the shell tool's cwd is the launcher's, not the
    session's — the reason three S3 artifacts wrote to one path in run #1."""
    cwd = OUT / "cwd-probe"; cwd.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((BENCH / "results" / "agentic-opencode-smoke3-2026-11-17" / "sessions" /
                      "S3r1" / "opencode.json").read_text())
    (cwd / "opencode.json").write_text(json.dumps(cfg, indent=1))
    env = os.environ.copy(); env["OPENCODE_CONFIG"] = str((cwd / "opencode.json").resolve())
    p = subprocess.run(["opencode", "run", "--standalone", "--format", "json",
                        "Run the shell command `pwd` and reply with exactly: PWD=<the output>"],
                       cwd=str(cwd), env=env, capture_output=True, text=True, timeout=300)
    m = re.search(r"PWD=(\S+)", p.stdout)
    log(f"shell-cwd probe: session cwd={cwd} | shell pwd={m.group(1) if m else 'n/a'}")
    return {"session_cwd": str(cwd), "shell_pwd": m.group(1) if m else None,
            "inherited_from_launcher": bool(m) and str(cwd) != m.group(1)}

def stage(script, extra, tag, env_extra=None):
    cmd = [PY, "-I", str(BENCH / script)] + extra
    env = os.environ.copy()
    if env_extra: env.update(env_extra)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(BENCH), capture_output=True, text=True, timeout=5400, env=env)
    (OUT / f"{tag}.stdout.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
    tail = [l for l in p.stdout.splitlines() if l.strip()][-3:]
    log(f"{tag}: rc={p.returncode} in {round(time.time()-t0)}s | {' | '.join(t[:110] for t in tail)}")
    return {"stage": tag, "rc": p.returncode, "wall_s": round(time.time()-t0, 1)}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "why_pass2": "run #1 no-op'd both restarts (pkill missed the supervisor) and its "
                        "determinism probe hashed empty content; both fixed here",
           "operator_tenancy": "detached; operator makes zero engine turns during the run"}
    (OUT / "header.json").write_text(json.dumps(rec, indent=1))
    log("settle 60 s, then start; the engine will be restarted twice")
    time.sleep(60)
    try:
        rec["shell_cwd_probe"] = shell_cwd_probe()
        det_auto = determinism("daily-auto")
        rec["effort_cost"] = effort_probe()

        log("hard stop, then start with --verify-rows all")
        rec["stop_1"] = hard_stop()
        rec["start_verify"] = start(VERIFY_ARGS, "verifyall2")
        det_all = determinism("verify-rows-all")

        log("hard stop, then restore the DAILY config")
        rec["stop_2"] = hard_stop()
        rec["start_daily"] = start(DAILY_ARGS, "daily2")
        price = (round((det_all["median_wall_s"] - det_auto["median_wall_s"]) /
                       det_auto["median_wall_s"] * 100, 1)
                 if det_auto["median_wall_s"] and det_all["median_wall_s"] else None)
        rec["determinism_A_B"] = {
            "auto": {"distinct": det_auto["distinct_outputs"], "blank": det_auto["blank_responses"],
                     "median_tok_s": det_auto["median_tok_s"], "median_wall_s": det_auto["median_wall_s"]},
            "all": {"distinct": det_all["distinct_outputs"], "blank": det_all["blank_responses"],
                    "median_tok_s": det_all["median_tok_s"], "median_wall_s": det_all["median_wall_s"]},
            "wall_time_price_of_determinism_percent": price}
        log(f"A/B: auto {det_auto['distinct_outputs']} distinct / all {det_all['distinct_outputs']} "
            f"distinct; wall-time price {price}%")

        log("agentic suite on the restored daily config: 4 tasks x 3 trials")
        rec["agentic"] = stage("driver_opencode.py",
                               ["--trials", "3", "--out", str(OUT / "agentic")], "agentic")
        s = OUT / "agentic" / "summary.jsonl"
        if s.exists():
            rows = [json.loads(l) for l in s.read_text().splitlines() if l.strip()]
            rec["agentic_tally"] = {"n": len(rows), "verified": sum(r.get("verified") for r in rows),
                                    "honest": sum(r.get("honest") for r in rows),
                                    "denied_attempts": sum(len(r.get("denied_tool_attempts") or []) for r in rows),
                                    "brief_deviations": sum(len(r.get("brief_deviations") or []) for r in rows)}
    except Exception as e:
        log(f"!! failed: {e}"); rec["error"] = str(e)[:400]
    finally:
        if not (rec.get("start_daily") or {}).get("ready_in_s"):
            log("engine may not be on the daily config — attempting restore")
            try:
                hard_stop(); rec["restore_attempt"] = start(DAILY_ARGS, "daily-final")
            except Exception as e: rec["restore_error"] = str(e)[:200]
        rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        (OUT / "header.json").write_text(json.dumps(rec, indent=1))
        log("done")
    return 0

if __name__ == "__main__":
    sys.exit(main())
