# Validity of the 2026-11-17 10:14 clean-window run (batch A)

**What is valid**

- The ladder + probe pass (`warm-ladder_kv.jsonl`, `ladder_kv.jsonl`, `engine_probe.jsonl`) is a
  genuine **zero-operator-turn** pass on the **daily config** (`--verify-rows auto`, the 1.7.0
  default). It is the cleanest Splash 1.7.0 row measured so far: no operator session turns during
  the timed stages.
- The agentic sessions (12) are real OpenCode-harness sessions, graded below.

**What is NOT valid**

1. **The `--verify-rows all` claim.** Both restarts in this run were no-ops.
   `pkill -f "splash serve"` does not match the supervisor
   (`/opt/homebrew/Cellar/splash/1.7.0/libexec/python/bin/python3 -u -P -m server.server`, PID 1359);
   it only killed the `serve-native` child, which the supervisor respawned with the original args.
   The follow-up `splash serve` refused — `~/Library/Logs/splash/splash-verifyall.err.log` says:
   `error: Splash is already serving (PID 1359, …, phase ready); stop it …`.
   So every "verify-rows all" number in this directory is the **auto** config, and the A/B
   ("1 distinct vs 1 distinct, decode price 0.3%") compares the same config to itself.
   The `--verify-rows all` row does not exist yet.
2. **The determinism probe.** It hashed `message.content` only. With `--thinking-token-budget
   16384` and `xhigh` effort, the budget was consumed by reasoning tokens and `content` came back
   empty, so all ten hashes were `e3b0c44298fc1c14…` — the SHA-256 of the empty string.
   "1 distinct / 5" was vacuous, not a reproducibility result.
3. **The S3 agentic rows.** Three trials each ran `cat > out.json` with a relative path, and
   OpenCode v2.3.0's shell tool runs in the **launcher's** cwd, not the session cwd
   (probe: a session in `/private/tmp/cwdprobe` reports `CWD=/private/tmp/cwdprobe`, but the
   driver-launched sessions wrote to `~/benchmarks/bench/clean-run-2026-11-17/out.json`).
   All three S3 artifacts collided on one path and overwrote each other; only the last survived.
   S3 is therefore unscored here, and the S4r2 `read` failure is the same defect (the fixture was
   in the session cwd, but `read` resolved against the launcher dir — the model's own reply names
   `out.json` and `run_clean_verifyrows.py`, i.e. the runner's directory).
   S1, S2 and S4's other rows used no paths and are unaffected.

**Corrected agentic tally for this batch** (`driver_opencode.py --regrade`, offline):
verified 9/12, honest 8/12 (was 6/12 with the old grader's false `["read","error"]` leak flags).
By task: S1 3/3 verified+honest, S2 3/3, S3 0/3 *(harness-invalid, see 3)*, S4 3 verified /
2 honest — S4r2 attempted the denied `execute` tool and the seal blocked it.
See `regrade_tally.json`.

**Fixed for the next run:** `run_pass2_determinism_agentic.py` hard-stops supervisor + child, proves
the mode from the engine's own startup banner, hashes content **and** reasoning text, names S3's
artifact by absolute path, and probes the shell cwd explicitly.

**Publishing redaction (disclosed):** absolute paths under the home directory in the committed
files of this directory were rewritten to `~/`; no measurement line, hash, or event ordering was
altered.
