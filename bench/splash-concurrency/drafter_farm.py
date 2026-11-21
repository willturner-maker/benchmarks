#!/usr/bin/env python3
"""Build a draft-free manifest directory for the Splash drafter-off A/B.

The drafter (incoai/Qwen3.8-Flash-Next-DFlash2) is resolved into the model directory as `draft/`
plus `draft/*` entries in model.json. The engine auto-loads it from there. To serve the SAME target
weights WITHOUT the drafter, this builds a sibling named-model directory whose model.json manifest
drops every draft entry, with config/target/tokenizer/vision symlinked to the originals - target
weights stay byte-identical by construction (same files), and the live model directory is never
touched.

Prints the farm path on success.
"""
import json, os, sys
from pathlib import Path

MODELS = Path.home() / "Library/Application Support/Splash/models"
NAME = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
FARM_NAME = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S-nodraft"

src = MODELS / NAME            # symlink into .resolved/<hash>
src_res = src.resolve()
farm = MODELS / FARM_NAME
if farm.exists():
    print(str(farm)); sys.exit(0)

manifest = json.loads((src_res / "model.json").read_text())
files = {k: v for k, v in manifest.get("files", {}).items() if not k.startswith("draft/")}
sources = {k: v for k, v in manifest.get("sources", {}).items() if k != "draft"}
assert "draft" not in sources and not any(k.startswith("draft/") for k in files)
farm.mkdir(parents=True)
(farm / "model.json").write_text(json.dumps({"files": files, "sources": sources}, indent=2))
for entry in ("config.json", "target", "tokenizer", "vision"):
    if (src_res / entry).exists():
        os.symlink(src_res / entry, farm / entry)
print(str(farm))
