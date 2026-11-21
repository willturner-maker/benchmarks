#!/usr/bin/env python3
"""Build a draft-free assembly for the Splash drafter-off A/B.

The drafter (incoai/Qwen3.8-Flash-Next-DFlash2) is resolved into the model assembly as `draft/`
plus `draft/*` entries in model.json; the engine auto-loads it from there. To serve the SAME target
weights WITHOUT the drafter, build a sibling assembly whose model.json drops every draft entry,
with config/target/tokenizer/vision symlinked - target weights stay byte-identical by construction.

Why the first attempt failed (attempt 1 rejected at serve time): the supervisor's hold()
(install/assembly.py) requires the model path to resolve to a directory whose PARENT is named
`.resolved` - a named dir under models/ISTA-DASLab/ is not an assembly. And collect_garbage()
removes .resolved assemblies that "no selection links and no server holds" - so the farm also
gets a selection link (a named model-ID symlink pointing at it), which is also how every real
install is referenced.

Never touches the live assembly. Prints the selection-link path (what the supervisor is launched
with) on success.
"""
import json, os, sys
from pathlib import Path

MODELS = Path.home() / "Library/Application Support/Splash/models"
NAME = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S"
ASM = MODELS / ".resolved" / "nodraft-f073087d1dff7edaf96fe2f5ee568630"
LINK = MODELS / "ISTA-DASLab" / "Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S-nodraft"

src = MODELS / NAME
if not src.is_symlink():
    sys.exit("live named model dir missing/unexpected")
src_res = src.resolve()

# clean the rejected attempt-1 layout if present
stale = MODELS / "ISTA-DASLab" / "Qwen3.8-Flash-Next-GSQ-RCO-GGUF:IQ3_S-nodraft"
if stale.is_symlink():
    pass                                    # this is our LINK below, not the stale attempt-1 dir
elif stale.is_dir():                        # attempt 1 built a plain DIR where the LINK now goes
    import shutil
    shutil.rmtree(stale)

if True:  # (re)write the manifest every run: attempt 3 failed because the first builder copied
    # ONLY files/sources and the supervisor's family check needs family/model/metadata/... intact.
    manifest = json.loads((src_res / "model.json").read_text())
    stripped = {k: v for k, v in manifest.items() if k not in ("files", "sources")}
    files = {k: v for k, v in manifest.get("files", {}).items() if not k.startswith("draft/")}
    sources = {k: v for k, v in manifest.get("sources", {}).items() if k != "draft"}
    assert sources and files and not any(k.startswith("draft/") for k in files)
    assert all(k in stripped for k in ("family", "model", "version", "metadata", "target_format")), stripped.keys()
    ASM.mkdir(parents=True, exist_ok=True)
    (ASM / "model.json").write_text(json.dumps({**stripped, "files": files, "sources": sources}, indent=2))
    for entry in ("config.json", "target", "tokenizer", "vision"):
        if (src_res / entry).exists() and not (ASM / entry).exists():
            os.symlink(src_res / entry, ASM / entry)
if LINK.is_symlink():
    LINK.unlink()
os.symlink(ASM, LINK)
print(str(LINK))
