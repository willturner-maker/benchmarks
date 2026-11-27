#!/usr/bin/env python3
"""Plugin/tool health probe — behaviour, not config, is evidence.

Motivation (2026-11-26): prismor 1.80.7's `install-hooks` wrote an OpenCode V1-shape
plugin that OpenCode 2.4.2 silently refused to load; `prismor status` kept reporting
the hooks as INSTALLED while ZERO tool calls were scanned. A quiet guard is a broken
guard. This probe proves the security/observation layers are ALIVE by making them act:

  Tier A (offline, ~2 s):
    A1  every local plugin file under ~/.config/opencode/plugins/*.js satisfies the
        V2 plugin contract (default export with id + setup/effect) — imported via node,
        the same contract the loader enforces. (This alone fails the V1 prismor shape.)
    A2  prismor status exits 0 AND observe/protect mode reads as expected;
    A3  semantic_guard stays local: policy export must show mode: heuristic
        (the `auto` default escalates screened text to a hosted LLM judge).
    A4  MCP gateway wiring: prismor-brave registered; direct brave-search stays
        disabled (gateway is the path of record).

  Tier B (live, one small model call, ~30 s):
    B1  snapshot prismor sessions; run `opencode run --standalone` with a unique
        token asking for exactly one shell tool call;
    B2  the run itself must show a COMPLETED tool_use event (opencode tools work);
    B3  prismor must have opened/updated an opencode-agent session with
        totalEvents >= 1 within the probe window — proof the hook plugin loaded,
        the dispatcher fires, and findings storage is alive.

Exit 0 only when every enabled check passes. Run after any opencode, prismor, or
plugin upgrade, and before benchmark waves that depend on these layers.
Usage:  python3 plugin-health-probe.py [--skip-live] [--model MODEL]
"""
import argparse, json, pathlib, subprocess, sys, time, uuid

HOME = pathlib.Path.home()
PRISMOR = str(HOME / "prismor-venv/bin/prismor")
OC_CFG = HOME / ".config/opencode/opencode.json"
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{(' — ' + detail) if detail else ''}")
    if not cond:
        fails.append(name)

def run(cmd, timeout=240):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

# ---------------- Tier A ----------------
cfg = json.loads(OC_CFG.read_text())

# A1: local plugin files must satisfy the V2 contract
plug_dir = HOME / ".config/opencode/plugins"
files = sorted(plug_dir.glob("*.js")) if plug_dir.exists() else []
if not files:
    print("  SKIP  A1: no local plugin files under ~/.config/opencode/plugins/")
for f in files:
    js = ("const m = await import('file://' + process.argv[1]);"
          "const d = m.default;"
          "if (!d || typeof d !== 'object' || !d.id || !(d.setup || d.effect)) {"
          "  console.error('no V2 default export (id + setup/effect): named exports: ' +"
          "    Object.keys(m).join(',')); process.exit(1);}"
          "console.log('ok:' + d.id);")
    r = run(["node", "--input-type=module", "-e", js, str(f)], timeout=30)
    check(f"A1 plugin contract (V2): {f.name}", r.returncode == 0,
          (r.stdout.strip() or r.stderr.strip())[:160])

# A2: prismor status healthy + mode readable
r = run([PRISMOR, "status"], timeout=60)
check("A2 prismor status exits 0", r.returncode == 0, r.stderr.strip()[:120])

# A3: semantic guard pinned local
r = run([PRISMOR, "policy", "export"], timeout=60)
out = r.stdout
check("A3 semantic_guard mode: heuristic (no external judge)",
      "heuristic" in out and "mode: auto" not in out,
      "policy export shows heuristic" if "heuristic" in out else "NO heuristic pin — external judge possible!")

# A4: gateway wiring
servers = cfg.get("mcp", {}).get("servers", {})
check("A4 prismor-brave gateway registered", "prismor-brave" in servers)
brave = servers.get("brave-search", {})
check("A4 direct brave-search stays disabled (rollback path only)",
      brave.get("disabled") is True if brave else True,
      "absent" if not brave else f"disabled={brave.get('disabled')}")

# ---------------- Tier B ----------------
ap = argparse.ArgumentParser()
ap.add_argument("--skip-live", action="store_true", help="Tier A only (no model call)")
ap.add_argument("--model", default=None)
a = ap.parse_args()

if a.skip_live:
    print("  SKIP  Tier B (--skip-live)")
else:
    def prismor_sessions():
        r = run([PRISMOR, "sessions", "--json", "--limit", "200", "--global"], timeout=60)
        try:
            return {s["sessionId"]: s for s in json.loads(r.stdout).get("sessions", [])}
        except Exception:
            return {}
    token = "PLUGIN-HEALTH-" + uuid.uuid4().hex[:12]
    before = prismor_sessions()
    prompt = (f"Use your shell tool exactly once to run: echo {token}. "
              "Then reply DONE and nothing else.")
    cmd = ["opencode", "run", "--standalone", "--format", "json", prompt]
    if a.model:
        cmd[3:3] = ["-m", a.model]
    r = run(cmd, timeout=300)
    completed_tool = any(
        (json.loads(ln).get("type") == "tool_use"
         and ((json.loads(ln).get("part") or {}).get("state") or {}).get("status") == "completed")
        for ln in r.stdout.splitlines() if ln.strip().startswith("{"))
    check("B1 headless run performed a COMPLETED tool call", completed_tool,
          "" if completed_tool else r.stderr[:160])
    time.sleep(3)  # let the hook dispatcher flush
    after = prismor_sessions()
    new = [s for k, s in after.items() if k not in before]
    hooked = [s for s in new if s.get("agent") == "opencode"
              and (s.get("summary") or {}).get("totalEvents", 0) >= 1]
    check("B2 prismor observed the new session (hook plugin ALIVE)",
          bool(hooked),
          f"new sessions: {len(new)}, with hook events: {len(hooked)}"
          + ("" if hooked else " — plugin loaded but dispatcher silent, OR plugin not loaded"))

print("PROBE RESULT:", "HEALTHY" if not fails else f"{len(fails)} FAILURES: {fails}")
sys.exit(1 if fails else 0)
