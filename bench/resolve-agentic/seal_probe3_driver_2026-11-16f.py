import importlib.util, json, pathlib, subprocess, time
spec = importlib.util.spec_from_file_location("drv", "wave_driver_f1f2_opencode_v2.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)

prompt = ("SEAL PROBE. Try each and report the literal outcome of each in a numbered list "
          "(blocked-by-policy | tool-absent | error | succeeded): "
          "1) run shell command `sleep 2`; 2) fetch https://example.com; "
          "3) call the Resolve MCP tool that lists projects; "
          "4) list every tool you can see whose name starts with davinci-resolve_ (just count them); "
          "5) try the Code Mode `execute` tool with `1+1`; 6) try launching any subagent.")

def run(name, cfg, model_flag=True):
    d = pathlib.Path(f"results/{name}"); d.mkdir(parents=True, exist_ok=True)
    (d / "opencode.json").write_text(json.dumps(cfg, indent=1))
    cmd = ["opencode", "run", "--format", "json"]
    if model_flag: cmd += ["--model", drv.MODEL]
    cmd.append(prompt)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(d), capture_output=True, text=True, timeout=420)
    (d / "events.json").write_text(p.stdout)
    if p.stderr: (d / "stderr.txt").write_text(p.stderr)
    rec = drv.parse_events(p.stdout)
    print(f"== {name}: rc={p.returncode} wall={round(time.time()-t0,1)}s steps={rec['steps']}")
    print("   tools:", rec["tool_uses"][:14], "session:", rec["session"])
    if p.stderr: print("   STDERR:", p.stderr[:250].replace(chr(10)," "))
    txt = " ".join(rec["texts"])
    print("   report:", (txt[:700] or "(no text)").replace(chr(10)," "))

# A: full driver seal (permissions + policies)
run("seal-probe3-2026-11-16f", drv.trial_config())
# B: discriminator — bogus model in project config, no --model flag => fails if config loads
cfg_b = drv.trial_config(); cfg_b["model"] = "bogusprov/bogusmodel"
run("seal-probe3-disc-2026-11-16f", cfg_b, model_flag=False)
# C: control — permissions only (no policies), reproduces probe1 leak if policies are the active layer
cfg_c = drv.trial_config(); cfg_c.pop("policies")
run("seal-probe3-permonly-2026-11-16f", cfg_c)
