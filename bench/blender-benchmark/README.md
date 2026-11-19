# blender-benchmark — timed scene-to-image suite

The brief under test, verbatim:

> **a pretty woman in a red dress sitting at a table with a computer and a lamp**

This suite measures Cycles throughput on Apple Silicon (the official
Blender-Benchmark samples-per-minute metric) on a scene that encodes that
sentence as geometry and lighting — and then **grades the finished pixels**
back against the same sentence, independent read-backs, house doctrine: a
frame only passes when the verifier can find the red dress, the figure,
the lit lamp, and the glowing screen in the actual output.

## Stages

1. **build** — `build_scene.py` (headless Blender) constructs the scene:
   seated figure with skin/dress/hair materials, table, open laptop with an
   emissive display, desk lamp with a real emissive bulb, area key, dark
   world. If `fixture/woman_red_dress.glb` exists it replaces the procedural
   stand-in figure (scale/grounding/centering handled by the builder; the
   fixture's SHA-256 is recorded in `run.json`).
2. **render** — `run_bench.py` sweeps Cycles samples {64, 128, 256} at
   1920×1080, denoising off (score purity), GPU via Metal when present.
   `samples_per_minute = spp / render_minutes` per config, summed = headline
   score — same metric family as the Blender Benchmark Launcher.
3. **verify** — `verify_render.py` on the vision venv
   (`~/resolve-vision-venv312/bin/python`) grades the 256-spp frame:
   `rendered / red_dress / figure / lamp / screen` (hard) + Haar face
   (soft). Exit code is part of the record.

```bash
python3 run_bench.py --sweep 64,128,256 [--tag NAME]
# results/<date>[-tag]/{run.json, environment.json, frame_*spp.png, verify.json}
# results/latest → newest run
```

## Results

| Run | Fixture | GPU | score (samples/min, Σ) | verify |
|---|---|---|---|---|
| `2026-11-18-standin` | procedural stand-in | M5 Ultra, METAL, 1 dev | **7,589** | 5/5 PASS (soft face: none — mannequin profile) |

Rough per-config wall (Blender incl. ~0.5 s startup): 64 spp 2.2 s,
128 spp 3.2 s, 256 spp 4.5 s. The scene is deliberately light on geometry
(~6.6k verts stand-in); the generated fixture (below) will raise it and the
score will move — **fixture class is part of the run identity**, so
stand-in and fixture scores are separate series, never compared.

## Fixture provenance policy

- The suite ships a procedural stand-in so it always runs, free and offline.
- A **generated fixture** (Meshy via Blender MCP `generate_3d`, seated woman,
  red dress) was the intended exact-fit subject: free-tier key pending
  enrollment (2026-11-18). When it lands: store as
  `fixture/woman_red_dress.glb`, record generator/prompt/date/license next to
  it; the builder swaps it in automatically.
- Library roulette was tried and rejected on this date: Sketchfab
  `Red Dress Female` (vrcityphoto, 913k faces) is a photo scan of **two
  figures on a cobblestone patch** — wrong subject, and its bake/hierarchy
  made it fight the harness; Poly Pizza's character sets (Quaternius CC0)
  are clean but not the red dress. Both searches left no single clean model
  matching the brief. Noted so the next person doesn't re-import that one.

## Interop with the Blender Benchmark Launcher

The official launcher (installed on this workstation) scores only its own
downloaded scenes; there is no supported custom-scene path in 3.3.0. This
suite reproduces its **metric**, not its scene set: same samples-per-minute
math, own scene, own fixtures — which is what makes the verify stage
possible. Do not mix numbers across the two.

## Gotchas paid for on day one

- glTF/Sketchfab imports arrive with baked delta transforms and animation
  data that silently override `rotation_euler` writes — clear
  `animation_data` before touching transforms (and the importer's
  normalization scale must be restored if you reset it).
- `look`/viewport framing is not trustworthy for tiny objects; set a temp
  camera and use the camera view when inspecting fixtures.
- mediapipe 1.2 has no legacy `solutions` API — the verifier uses
  OpenCV's bundled Haar cascade for the soft face check.
- Blender 5.3 still warns `Material.use_nodes` is deprecated (removal in
  6.0) — silence is fine today, schedule the node-graph update.
