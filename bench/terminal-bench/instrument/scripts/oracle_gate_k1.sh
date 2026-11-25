#!/bin/bash
# Gate 2, phase A — oracle triage sweep over the FULL pinned 4.1.0 task tree.
#
# Purpose: map which tasks run clean on THIS runtime (OrbStack/Docker, arm64) and which
# error, before any model token is spent. This doubles as the root-cause report for the
# 2026-11-05 attempt that ended "66/66 errored" on the same runtime.
#
# What "run clean" means here: the oracle solution is applied and the task's own verifier
# writes a reward file. A reward of 0.0 from the oracle is a *verifier/task* signal, not an
# environment error, and is recorded as such.
#
# Pins this depends on (see PLAN-2026-11-25.md):
#   task tree   git tag v4.1.0 = 4070d6cef56a7d20cb5dc98d5e10ada88a6b9440 (local `-p tasks`,
#               i.e. dataset.toml in-tree, NOT the moving Hub pointer)
#   runner      harbor 0.27.0 + patches/tb-log-dirs-sticky.patch (required: without it,
#               sandboxed rewardkit verifiers die with RewardFileNotFoundError)
#   runtime     OrbStack 2.2.5 / Docker 29.8.2, VM cap 30 CPU / 15.66 GiB
#
# Concurrency: -n 2 by design. Several tasks declare memory_mb = 8192; the 15.66 GiB cap
# cannot host 4 such containers plus the serving engine's resident footprint. Upstream's
# own --n-concurrent 500 is a Modal-cloud number, not a local one.
# Retries: -r 0 so first-attempt outcomes are what get recorded.
#
# Phase B (only after phase A's map is reviewed): the upstream gate itself, `-k 5`, over
# the tasks that ran clean here.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-gate2-oracle-k1-2026-11-25}"
JOBS="${OUT}"

echo "== preflight"
docker info 2>/dev/null | grep -E "Server Version|CPUs|Total Memory"
grep -c "chmod 1777" tb-venv/lib/python3.12/site-packages/harbor/environments/base.py \
  | sed 's/^/patched chmod-1777 sites: /'
git -C . rev-parse HEAD | sed 's/^/task tree: /'

echo "== sweep (68 tasks, k=1, n=2, no retries)"
./tb-venv/bin/harbor run \
  -p tasks \
  --agent oracle \
  -k 1 \
  -n 2 \
  -r 0 \
  -o "$JOBS"
