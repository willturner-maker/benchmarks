#!/bin/bash
# probe: rewardkit log-dir parent trust vs Harbor's chmod of its log mounts
#
# Reproduces, without any task or model token, the verifier failure that errored the
# html-js-filter oracle run (and is the leading explanation for the 2026-11-05
# "66/66 errored" attempt):
#
#   rewardkit.sandbox.WorkerSetupError: Invalid private path:
#   Untrusted parent directory of /logs/verifier
#   -> Harbor then reports RewardFileNotFoundError.
#
# Rule under test: harbor-rewardkit 0.2.4 `sandbox.py::_secure_directory` walks the
# parent chain of its private paths (/tests, /logs/verifier) with trusted=True and
# requires each parent to be root-owned and not group/other writable, *or sticky*.
# Harbor 0.27.0 `environments/base.py` prepares those mounts with `chmod 777`
# (no sticky bit).
#
# Source pins for this probe: harbor-rewardkit==0.2.4 sdist
#   sha256 3e8db9a5cd0dace49a3f0dbad7b52ad4edb4baca3b20446b421af2e34cad87ab
#   (pinned by each task's tests/pyproject.toml as harbor-rewardkit==0.2.4)
# Extracted tree lives in the droppable scratch dir; re-fetch with:
#   pip download harbor-rewardkit==0.2.4 --no-deps --no-binary :all: -d <scratch>
set -euo pipefail

RK_SRC="${1:-${TMPDIR:-/tmp}/rk-inspect/harbor_rewardkit-0.2.4/src/rewardkit}"
[ -f "$RK_SRC/sandbox.py" ] || { echo "rewardkit source tree not found at $RK_SRC (see header to re-fetch)"; exit 2; }

docker run --rm -v "$RK_SRC:/rk:ro" python:3.12-slim sh -c '
mkdir -p /logs/verifier
python - <<PY
import importlib.util, sys, subprocess
from pathlib import Path
spec = importlib.util.spec_from_file_location("rk_sandbox", "/rk/sandbox.py")
rk = importlib.util.module_from_spec(spec)
sys.modules["rk_sandbox"] = rk
spec.loader.exec_module(rk)
# _secure_directory(/logs/verifier, 0o700) is exactly what rewardkit calls before
# running a sandboxed programmatic worker; only the parent mode varies below.
for label, mode in [("harbor 777", "777"), ("patch 1777", "1777"), ("default 755", "755")]:
    subprocess.run(["chmod", mode, "/logs"], check=True)
    try:
        rk._secure_directory(Path("/logs/verifier"), 0o700)
        print(f"{label:12} -> ACCEPTED")
    except Exception as e:
        print(f"{label:12} -> {type(e).__name__}: {e}")
PY'
# measured here 2026-11-25 (OrbStack 2.2.5 / Docker 29.8.2):
#   harbor 777   -> PermissionError: Untrusted parent directory of /logs/verifier
#   patch 1777   -> ACCEPTED
#   default 755  -> ACCEPTED
