#!/usr/bin/env python3
"""Build the benchmark scene: "a pretty woman in a red dress sitting at a
table with a computer and a lamp".

Stylized but structurally honest: a seated figure with skin/dress/hair
materials, a table, an open laptop (emissive screen) and a desk lamp with a
real emissive bulb — the render is graded on exactly those features
(verify_render.py), so a scene that misrepresents the brief fails the suite.

Run inside Blender:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python build_scene.py -- --out <dir>
Writes <dir>/woman_red_dress.blend and prints the scene fingerprint.
"""
import argparse
import bpy
import math
import sys
from mathutils import Euler, Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--fixture", default=None,
                help="path to a woman-in-red-dress GLB; replaces the procedural stand-in")
ap.add_argument("--composite", action="store_true",
                help="fixture already contains woman+table; skip procedural furniture, "
                     "add only lamp + emissive-screen assist on the fixture's table")
py_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = ap.parse_args(py_args)


def clean():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras, bpy.data.curves):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def mat(name, color, rough=0.5, metallic=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    return m


def add_mesh(obj, name, material, location=None, rotation=None, scale=None):
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if location:
        obj.location = location
    if rotation:
        obj.rotation_euler = rotation
    if scale:
        obj.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    return obj


def primitive(kind, name, material, **kw):
    if kind == "cube":
        obj = bpy.ops.mesh.primitive_cube_add(size=1)
    elif kind == "sphere":
        obj = bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.5)
    elif kind == "cyl":
        obj = bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.5, depth=1)
    elif kind == "cone":
        obj = bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.5, radius2=0.15, depth=1)
    obj = bpy.context.active_object
    return add_mesh(obj, name, material, **kw)


def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def main():
    clean()
    S = bpy.context.scene

    skin = mat("skin", (0.83, 0.60, 0.48), rough=0.45)
    hair = mat("hair", (0.06, 0.04, 0.03), rough=0.35)
    dress = mat("red_dress", (0.62, 0.02, 0.05), rough=0.4)
    wood = mat("wood", (0.28, 0.17, 0.09), rough=0.6)
    metal = mat("metal", (0.55, 0.56, 0.58), rough=0.3, metallic=1.0)
    plastic = mat("plastic", (0.12, 0.12, 0.13), rough=0.4)
    screen = mat("screen", (0.05, 0.06, 0.08), rough=0.2,
                 emit=(0.35, 0.55, 0.9), emit_strength=6.0)
    bulb = mat("bulb", (1, 0.75, 0.45), emit=(1.0, 0.72, 0.42), emit_strength=120.0)
    shade = mat("shade", (0.9, 0.85, 0.75), rough=0.5,
                emit=(1.0, 0.7, 0.4), emit_strength=1.5)

    # ── Seated woman, facing +Y toward the table ────────────────────────
    seat_h = 0.45
    # dress skirt: cone flaring over hips on the seat
    skirt = primitive("cone", "dress_skirt", dress,
                      location=(0, 0.05, seat_h + 0.02), scale=(0.34, 0.38, 0.28))
    smooth(skirt)
    # bodice: tapered cylinder torso in the dress
    bodice = primitive("cyl", "dress_bodice", dress,
                       location=(0, 0.02, seat_h + 0.28), rotation=(math.radians(-6), 0, 0),
                       scale=(0.22, 0.17, 0.36))
    smooth(bodice)
    # neck + head
    primitive("cyl", "neck", skin, location=(0, 0.03, seat_h + 0.50), scale=(0.05, 0.05, 0.08))
    head = primitive("sphere", "head", skin, location=(0, 0.04, seat_h + 0.62),
                     scale=(0.13, 0.135, 0.16))
    smooth(head)
    # simple eyes (front of the face, +Y side)
    for ex in (-1, 1):
        primitive("sphere", f"eye_{'L' if ex<0 else 'R'}", hair,
                  location=(0.045 * ex, 0.150, seat_h + 0.64), scale=0.014)
    # hair: slightly larger shell, back-biased
    hhair = primitive("sphere", "hair", hair, location=(0, 0.015, seat_h + 0.635),
                      scale=(0.148, 0.148, 0.168))
    smooth(hhair)
    hhair.scale.y *= 0.95
    # arms reaching to the table (upper + forearm each side)
    for sx in (-1, 1):
        x = 0.16 * sx
        primitive("cyl", f"upper_arm_{'L' if sx<0 else 'R'}", skin,
                  location=(x, 0.10, seat_h + 0.38),
                  rotation=(math.radians(60), 0, math.radians(-12 * sx)),
                  scale=(0.045, 0.045, 0.26))
        primitive("cyl", f"forearm_{'L' if sx<0 else 'R'}", skin,
                  location=(x, 0.28, seat_h + 0.30),
                  rotation=(math.radians(80), 0, math.radians(-8 * sx)),
                  scale=(0.04, 0.04, 0.24))
    # legs under the table (thigh horizontal, shin down)
    for sx in (-1, 1):
        x = 0.11 * sx
        primitive("cyl", f"thigh_{'L' if sx<0 else 'R'}", skin,
                  location=(x, 0.22, seat_h - 0.03),
                  rotation=(math.radians(90), 0, 0), scale=(0.07, 0.07, 0.30))
        primitive("cyl", f"shin_{'L' if sx<0 else 'R'}", skin,
                  location=(x, 0.36, 0.21), scale=(0.055, 0.055, 0.42))
    # stool
    primitive("cyl", "stool", wood, location=(0, 0, seat_h / 2), scale=(0.18, 0.18, seat_h))

    # ── Table ───────────────────────────────────────────────────────────
    top_z = 0.74
    primitive("cube", "table_top", wood, location=(0, 0.62, top_z), scale=(1.10, 0.55, 0.05))
    for i, (lx, ly) in enumerate([(-0.50, 0.38), (0.50, 0.38), (-0.50, 0.85), (0.50, 0.85)]):
        primitive("cube", f"table_leg_{i}", wood, location=(lx, ly, top_z / 2),
                  scale=(0.05, 0.05, top_z))

    # ── Laptop (open) at table center, screen toward the woman ──────────
    primitive("cube", "laptop_base", plastic, location=(0, 0.58, top_z + 0.022),
              scale=(0.33, 0.23, 0.016))
    scr = primitive("cube", "laptop_screen", plastic,
                    location=(0, 0.69, top_z + 0.16), rotation=(math.radians(-105), 0, 0),
                    scale=(0.33, 0.22, 0.012))
    # emissive display panel on the screen's inner face
    panel = primitive("cube", "laptop_display", screen,
                      location=(0, 0.683, top_z + 0.16), rotation=(math.radians(-105), 0, 0),
                      scale=(0.30, 0.19, 0.004))

    # ── Desk lamp at the table's right side: post, shade, real bulb ─────
    lamp_x, lamp_y = 0.42, 0.80
    primitive("cyl", "lamp_base", metal, location=(lamp_x, lamp_y, top_z + 0.02),
              scale=(0.14, 0.14, 0.03))
    primitive("cyl", "lamp_post", metal, location=(lamp_x, lamp_y, top_z + 0.20),
              scale=(0.015, 0.015, 0.36))
    arm = primitive("cyl", "lamp_arm", metal,
                    location=(lamp_x - 0.08, lamp_y - 0.02, top_z + 0.38),
                    rotation=(0, math.radians(65), 0), scale=(0.015, 0.015, 0.18))
    cone = primitive("cone", "lamp_shade", shade,
                     location=(lamp_x - 0.17, lamp_y - 0.02, top_z + 0.40),
                     rotation=(0, math.radians(15), 0),
                     scale=(0.16, 0.16, 0.14))
    smooth(cone)
    primitive("sphere", "lamp_bulb", bulb,
              location=(lamp_x - 0.17, lamp_y - 0.02, top_z + 0.355), scale=0.035)

    # ── Fixture path: generated composite (woman+table) ────────────────
    if opts.composite:
        TOP_Z = 0.79  # measured tabletop height of the fixture model
        for nm in (["dress_skirt", "dress_bodice", "neck", "head", "eye_L", "eye_R",
                    "hair", "upper_arm_L", "upper_arm_R", "forearm_L", "forearm_R",
                    "thigh_L", "thigh_R", "shin_L", "shin_R", "stool", "table_top",
                    "table_leg_0", "table_leg_1", "table_leg_2", "table_leg_3",
                    "laptop_base", "laptop_screen", "laptop_display"]):
            o = S.objects.get(nm)
            if o:
                bpy.data.objects.remove(o, do_unlink=True)
        bpy.ops.import_scene.gltf(filepath=opts.fixture)
        # lamp staged on the fixture's table, right side
        lamp_x, lamp_y = 0.42, -0.30
        primitive("cyl", "lamp_base", metal, location=(lamp_x, lamp_y, TOP_Z + 0.02),
                  scale=(0.14, 0.14, 0.03))
        primitive("cyl", "lamp_post", metal, location=(lamp_x, lamp_y, TOP_Z + 0.20),
                  scale=(0.015, 0.015, 0.36))
        primitive("cyl", "lamp_arm", metal,
                  location=(lamp_x - 0.08, lamp_y - 0.02, TOP_Z + 0.38),
                  rotation=(0, math.radians(65), 0), scale=(0.015, 0.015, 0.18))
        cone = primitive("cone", "lamp_shade", shade,
                         location=(lamp_x - 0.17, lamp_y - 0.02, TOP_Z + 0.40),
                         rotation=(0, math.radians(15), 0), scale=(0.16, 0.16, 0.14))
        smooth(cone)
        primitive("sphere", "lamp_bulb", bulb,
                  location=(lamp_x - 0.17, lamp_y - 0.02, TOP_Z + 0.355), scale=0.035)
        # assist: slim laptop with emissive display staged on the same table
        primitive("cube", "laptop_base", plastic, location=(0.05, -0.15, TOP_Z + 0.012),
                  scale=(0.33, 0.23, 0.016))
        primitive("cube", "laptop_screen", plastic,
                  location=(0.05, -0.04, TOP_Z + 0.15), rotation=(math.radians(-105), 0, 0),
                  scale=(0.33, 0.22, 0.012))
        primitive("cube", "laptop_display", screen,
                  location=(0.05, -0.047, TOP_Z + 0.15), rotation=(math.radians(-105), 0, 0),
                  scale=(0.30, 0.19, 0.004))

    # ── Optional generated fixture replaces the procedural stand-in ────
    elif opts.fixture:
        # fixture is a cross-legged seated figure (origin at floor, faces -Y).
        # She replaces the stand-in AND the stool; the scene keeps its table
        # lowered to low-table height so the seated geometry reads true.
        standins = {"dress_skirt", "dress_bodice", "neck", "head", "eye_L", "eye_R",
                    "hair", "upper_arm_L", "upper_arm_R", "forearm_L", "forearm_R",
                    "thigh_L", "thigh_R", "shin_L", "shin_R", "stool"}
        for nm in standins:
            o = S.objects.get(nm)
            if o:
                bpy.data.objects.remove(o, do_unlink=True)
        # low table: 0.50 top instead of 0.74
        tt = S.objects.get("table_top")
        if tt:
            tt.location = (0, 0.10, 0.50)
            tt.scale = (1.10, 0.60, 0.05)
            for i, (lx, ly) in enumerate([(-0.50, -0.18), (0.50, -0.18),
                                          (-0.50, 0.38), (0.50, 0.38)]):
                leg = S.objects.get(f"table_leg_{i}")
                if leg:
                    leg.location = (lx, ly, 0.25)
                    leg.scale = (0.05, 0.05, 0.50)
            # laptop: base centered on the table, display facing +Y (toward her)
            lb = S.objects.get("laptop_base")
            if lb:
                lb.location = (0, 0.02, 0.522)
            ls = S.objects.get("laptop_screen")
            lp = S.objects.get("laptop_display")
            if ls:
                ls.location = (-0.08, 0.30, 0.66)
                ls.rotation_euler = (math.radians(-105), 0, math.radians(-42))
            if ls and lp:
                # mount the display flush on the panel's front face: offset along
                # the panel's own normal by half each thickness (0.006 + 0.002)
                n = Euler(ls.rotation_euler).to_matrix() @ Vector((0, 0, 1))
                if n.y < 0:
                    n = -n
                lp.location = ls.location + n * 0.008
                lp.rotation_euler = ls.rotation_euler
            # lamp on the table's right-front corner, canted to light her
            lamp_map = {"lamp_base": (0.52, -0.05, 0.52), "lamp_post": (0.52, -0.05, 0.68),
                        "lamp_shade": (0.35, -0.07, 0.83), "lamp_bulb": (0.35, -0.07, 0.785)}
            for nm, loc in lamp_map.items():
                o2 = S.objects.get(nm)
                if o2:
                    o2.location = loc
            # elbow joint + arm rebuilt to actually connect post to shade
            elbow = primitive("sphere", "lamp_elbow", metal,
                              location=(0.52, -0.05, 0.86), scale=0.03)
            smooth(elbow)
            arm = S.objects.get("lamp_arm")
            if arm:
                start = Vector((0.52, -0.05, 0.86))
                end = Vector((0.36, -0.07, 0.90))
                d = end - start
                arm.location = (start + end) / 2
                arm.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
                arm.scale = (0.015, 0.015, d.length + 0.03)
        # screen as a key light on her face: brighter, cooler display
        scr = bpy.data.materials.get("screen")
        if scr:
            b = next(n for n in scr.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            b.inputs["Emission Strength"].default_value = 14.0
        shd = bpy.data.materials.get("shade")
        if shd:
            b = next(n for n in shd.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            b.inputs["Emission Strength"].default_value = 2.5
        import mathutils as _mu
        existing_before = {o.name for o in S.objects}
        existing_meshes_before = {o.name for o in S.objects if o.type == "MESH"}
        bpy.ops.import_scene.gltf(filepath=opts.fixture)
        imported = [o for o in S.objects if o.name not in existing_before]
        fix_roots = [o for o in imported if o.parent is None or
                     o.parent.name not in {x.name for x in imported}]
        pts = []
        for o in S.objects:
            if o.type == "MESH" and o.name not in existing_meshes_before:
                ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
                for c in ev.bound_box:
                    pts.append(ev.matrix_world @ _mu.Vector(c))
        if pts:
            xs = [v.x for v in pts]; ys = [v.y for v in pts]; zs = [v.z for v in pts]
            h = max(zs) - min(zs)
            scale = 1.15 / h if h > 0 else 1.0
            for root_obj in fix_roots:
                root_obj.scale = (scale, scale, scale)
                root_obj.rotation_euler = (0, 0, 0)  # v3 faces -Y, straight at the laptop
            bpy.context.view_layer.update()
            pts2 = []
            for o in S.objects:
                if o.type == "MESH" and o.name not in existing_meshes_before:
                    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    for c in ev.bound_box:
                        pts2.append(ev.matrix_world @ _mu.Vector(c))
            xs = [v.x for v in pts2]; ys = [v.y for v in pts2]; zs = [v.z for v in pts2]
            dx = -(min(xs) + max(xs)) / 2
            dy = 0.65 - (min(ys) + max(ys)) / 2
            dz = -min(zs)
            for root_obj in fix_roots:
                root_obj.location = (root_obj.location.x + dx,
                                     root_obj.location.y + dy,
                                     root_obj.location.z + dz)
        bpy.context.view_layer.update()

    # ── World + camera ──────────────────────────────────────────────────
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    S.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.02, 0.02, 0.03, 1)
    bg.inputs[1].default_value = 1.0

    # soft cool key from the camera side: lifts the figure out of the gloom
    key_data = bpy.data.lights.new("key", type="AREA")
    key_data.energy = 18 if opts.fixture else 60
    key_data.size = 1.4
    key = bpy.data.objects.new("key", key_data)
    S.collection.objects.link(key)
    key.location = (-1.6, -0.6, 1.9)
    kd = (Vector((0, 0.3, 0.8)) - key.location).normalized()
    key.rotation_euler = kd.to_track_quat("-Z", "Y").to_euler()

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 40
    cam = bpy.data.objects.new("Camera", cam_data)
    S.collection.objects.link(cam)
    if opts.composite:
        cam.location = (1.70, -1.15, 1.50)
        target = Vector((0.0, 0.15, 0.95))
    elif opts.fixture:
        cam.location = (1.25, -0.95, 1.65)
        target = Vector((0.0, 0.55, 0.92))
    else:
        cam.location = (2.30, 0.60, 1.45)
        target = Vector((-0.05, 0.40, 0.75))
    d = (target - cam.location).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    S.camera = cam

    # ── Render settings (deterministic defaults; run_bench.py overrides) ─
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = 128
    S.cycles.use_denoising = False
    S.render.resolution_x = 1920
    S.render.resolution_y = 1080
    S.render.image_settings.file_format = "PNG"

    # enable Metal GPU on Apple Silicon
    prefs = bpy.context.preferences.addons.get("cycles")
    if prefs:
        cp = prefs.preferences
        for ctype in ("OPTIX", "CUDA", "METAL", "HIP", "ONEAPI"):
            try:
                cp.compute_device_type = ctype
            except TypeError:
                continue
            cp.get_devices()
            if any(t.type == ctype for t in cp.devices):
                for dev in cp.devices:
                    dev.use = True
                break

    bpy.ops.wm.save_as_mainfile(filepath=f"{opts.out}/woman_red_dress.blend")
    verts = sum(len(o.data.vertices) for o in S.objects if o.type == "MESH")
    print(f"SCENE_OK objects={len(S.objects)} verts={verts} "
          f"emissive={'screen' if screen else ''},bulb saved={opts.out}/woman_red_dress.blend")


main()
