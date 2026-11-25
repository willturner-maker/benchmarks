#!/usr/bin/env python3
"""Build a subset dataset directory from the pinned v4.1.0 dataset.toml.

Keeps the upstream `digest = sha256:…` line for every selected task, so a subset run is
pinned by content hash exactly like the full-tree run — no hand-written task lists.

Usage: make_probe_dataset.py <out-dir> <task> [<task> …]
Task directories are symlinked into <out-dir> (the pinned tree stays the single source).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_MANIFEST = ROOT / "tasks" / "dataset.toml"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    out = Path(sys.argv[1])
    wanted = sys.argv[2:]

    text = SRC_MANIFEST.read_text()
    header = text.split("[[tasks]]", 1)[0]
    blocks = re.findall(r"\[\[tasks\]\]\nname = \"([^\"]+)\"\ndigest = \"([^\"]+)\"\n", text)
    by_name = {name.split("/")[-1]: (name, digest) for name, digest in blocks}

    missing = [t for t in wanted if t not in by_name]
    if missing:
        print(f"not in {SRC_MANIFEST.name}: {' '.join(missing)}")
        return 2

    out.mkdir(parents=True, exist_ok=True)
    lines = [header.rstrip(), "", "# Subset selected for this run; digests copied verbatim", ""]
    for task in wanted:
        name, digest = by_name[task]
        lines += ["[[tasks]]", f'name = "{name}"', f'digest = "{digest}"', ""]
        link = out / task
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to((ROOT / "tasks" / task).resolve())

    (out / "dataset.toml").write_text("\n".join(lines) + "\n")
    print(f"{out}/dataset.toml: {len(wanted)} tasks, digests pinned")
    for task in wanted:
        print(f"  {by_name[task][1][:23]}…  {task}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
