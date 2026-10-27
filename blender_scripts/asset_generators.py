"""Procedural low-poly game props. Run inside Blender:
    blender -b --python asset_generators.py -- args.json
args.json: {"kind": "crate", "params": {...}, "seed": 1, "output_blend": "...", "output_glb": "...",
            "result_path": "..."}
Every generator returns a list of mesh objects; they are joined into one mesh with the origin at the
bottom-centre (Y-up after glTF export), +Z up in Blender, about 1 unit (metre) in size unless `scale` is given.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import clear_scene, export_model, load_args, make_material, write_result  # noqa: E402


def _active():
    return bpy.context.view_layer.objects.active


def _assign(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def _cube(loc, scale, mat, name="part"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = _active()
    o.scale = scale
    o.name = name
    return _assign(o, mat)


def _cylinder(loc, radius, depth, mat, verts=12, name="cyl", rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    o = _active()
    o.name = name
    return _assign(o, mat)


def _cone(loc, r1, r2, depth, mat, verts=8, name="cone", rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=depth, location=loc, rotation=rot)
    o = _active()
    o.name = name
    return _assign(o, mat)


def _sphere(loc, radius, mat, segments=12, rings=8, scale=(1, 1, 1), name="sphere"):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, ring_count=rings, location=loc)
    o = _active()
    o.scale = scale
    o.name = name
    return _assign(o, mat)


def _ico(loc, radius, mat, subdiv=2, scale=(1, 1, 1), name="ico"):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=radius, subdivisions=subdiv, location=loc)
    o = _active()
    o.scale = scale
    o.name = name
    return _assign(o, mat)


def _displace(obj, rng, amount):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co += v.normal * rng.uniform(-amount, amount)
    bm.to_mesh(obj.data)
    bm.free()


def _bevel(obj, width=0.03, segments=2):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"


# --------------------------------------------------------------------------- #
# generators
# --------------------------------------------------------------------------- #
def crate(p, rng):
    s = p.get("size", 1.0)
    wood = make_material("Wood", p.get("color", "#a8743c"), 0.85)
    trim = make_material("WoodTrim", p.get("trim_color", "#6b4423"), 0.9)
    parts = [_cube((0, 0, s / 2), (s * 0.94, s * 0.94, s * 0.94), wood, "body")]
    post = s * 0.1
    for x in (-1, 1):
        for y in (-1, 1):
            parts.append(_cube((x * s * 0.46, y * s * 0.46, s / 2), (post, post, s * 1.0), trim, "post"))
    for z in (0.04, 0.96):
        for axis in (0, 1):
            scale = (s * 1.0, post * 0.8, post * 0.8) if axis == 0 else (post * 0.8, s * 1.0, post * 0.8)
            for side in (-1, 1):
                loc = (0, side * s * 0.46, s * z) if axis == 0 else (side * s * 0.46, 0, s * z)
                parts.append(_cube(loc, scale, trim, "rail"))
    return parts


def barrel(p, rng):
    s = p.get("size", 1.0)
    wood = make_material("BarrelWood", p.get("color", "#8a5a2b"), 0.8)
    metal = make_material("Hoop", "#3d4148", 0.4, 0.8)
    body = _cylinder((0, 0, s * 0.5), s * 0.38, s, wood, 14, "barrel")
    bm = bmesh.new()
    bm.from_mesh(body.data)
    for v in bm.verts:
        t = abs(v.co.z) / (s * 0.5)
        k = 1.0 + 0.14 * (1.0 - t * t)
        v.co.x *= k
        v.co.y *= k
    bm.to_mesh(body.data)
    bm.free()
    parts = [body]
    for z in (0.22, 0.78):
        bpy.ops.mesh.primitive_torus_add(major_radius=s * 0.43, minor_radius=s * 0.025,
                                         major_segments=14, minor_segments=5, location=(0, 0, s * z))
        ring = _active()
        ring.name = "hoop"
        parts.append(_assign(ring, metal))
    return parts


def rock(p, rng):
    s = p.get("size", 1.0)
    stone = make_material("Stone", p.get("color", "#7d7f85"), 0.95)
    o = _ico((0, 0, s * 0.3), s * 0.5, stone, 2, (1.0, rng.uniform(0.8, 1.1), rng.uniform(0.55, 0.8)), "rock")
    _displace(o, rng, s * 0.09)
    return [o]


def pine_tree(p, rng):
    s = p.get("size", 2.0)
    bark = make_material("Bark", "#5b3a1e", 0.95)
    leaf = make_material("Pine", p.get("color", "#2f6b3a"), 0.9)
    parts = [_cylinder((0, 0, s * 0.12), s * 0.06, s * 0.24, bark, 8, "trunk")]
    layers = p.get("layers", 3)
    for i in range(layers):
        t = i / max(1, layers - 1)
        parts.append(_cone((0, 0, s * (0.28 + i * 0.22)), s * (0.36 - t * 0.17), 0.0, s * 0.42, leaf, 8, f"foliage{i}"))
    return parts


def round_tree(p, rng):
    s = p.get("size", 2.0)
    bark = make_material("Bark", "#6a4526", 0.95)
    leaf = make_material("Leaf", p.get("color", "#4a9a3f"), 0.9)
    parts = [_cylinder((0, 0, s * 0.2), s * 0.07, s * 0.4, bark, 8, "trunk")]
    crown = _ico((0, 0, s * 0.62), s * 0.32, leaf, 2, (1, 1, 0.9), "crown")
    _displace(crown, rng, s * 0.03)
    parts.append(crown)
    return parts


def house(p, rng):
    s = p.get("size", 2.0)
    wall = make_material("Wall", p.get("color", "#d9c7a0"), 0.9)
    roof = make_material("Roof", p.get("roof_color", "#a8432f"), 0.85)
    door = make_material("Door", "#5a3a1f", 0.9)
    glass = make_material("Window", "#9fd6ff", 0.2, emission="#bfe6ff", emission_strength=0.6)
    parts = [_cube((0, 0, s * 0.35), (s, s * 0.9, s * 0.7), wall, "walls")]
    parts.append(_cone((0, 0, s * 0.7 + s * 0.2), s * 0.85, 0.0, s * 0.4, roof, 4, "roof", rot=(0, 0, math.radians(45))))
    parts.append(_cube((0, -s * 0.46, s * 0.2), (s * 0.2, s * 0.04, s * 0.4), door, "door"))
    for x in (-1, 1):
        parts.append(_cube((x * s * 0.28, -s * 0.46, s * 0.42), (s * 0.16, s * 0.03, s * 0.16), glass, "window"))
    return parts


def tower(p, rng):
    s = p.get("size", 3.0)
    stone = make_material("TowerStone", p.get("color", "#8d8f94"), 0.95)
    roof = make_material("TowerRoof", p.get("roof_color", "#3b5ea8"), 0.8)
    parts = [_cylinder((0, 0, s * 0.4), s * 0.22, s * 0.8, stone, 10, "shaft")]
    parts.append(_cylinder((0, 0, s * 0.84), s * 0.27, s * 0.08, stone, 10, "ring"))
    parts.append(_cone((0, 0, s * 0.88 + s * 0.15), s * 0.3, 0.0, s * 0.3, roof, 10, "roof"))
    return parts


def coin(p, rng):
    s = p.get("size", 0.5)
    gold = make_material("Gold", p.get("color", "#f2c230"), 0.3, 1.0)
    o = _cylinder((0, 0, s * 0.5), s * 0.5, s * 0.1, gold, 24, "coin", rot=(math.radians(90), 0, 0))
    rim = _cylinder((0, 0, s * 0.5), s * 0.42, s * 0.14, gold, 24, "rim", rot=(math.radians(90), 0, 0))
    return [o, rim]


def gem(p, rng):
    s = p.get("size", 0.5)
    mat = make_material("Gem", p.get("color", "#35d4ee"), 0.15, 0.2, emission=p.get("color", "#35d4ee"), emission_strength=1.5)
    return [_ico((0, 0, s * 0.6), s * 0.4, mat, 1, (1, 1, 1.45), "gem")]


def sword(p, rng):
    s = p.get("size", 1.2)
    steel = make_material("Steel", p.get("color", "#c9d1d9"), 0.25, 0.9)
    gold = make_material("Guard", "#d4a017", 0.4, 0.8)
    leather = make_material("Grip", "#4a2f1b", 0.9)
    parts = [_cube((0, 0, s * 0.62), (s * 0.1, s * 0.02, s * 0.72), steel, "blade")]
    parts.append(_cone((0, 0, s * 0.98 + s * 0.04), s * 0.055, 0.0, s * 0.1, steel, 4, "tip", rot=(0, 0, math.radians(45))))
    parts.append(_cube((0, 0, s * 0.25), (s * 0.34, s * 0.06, s * 0.05), gold, "guard"))
    parts.append(_cylinder((0, 0, s * 0.14), s * 0.03, s * 0.22, leather, 8, "grip"))
    parts.append(_sphere((0, 0, s * 0.02), s * 0.045, gold, 8, 6, name="pommel"))
    return parts


def platform(p, rng):
    s = p.get("size", 2.0)
    stone = make_material("PlatStone", p.get("color", "#7b6b5b"), 0.95)
    grass = make_material("Grass", p.get("top_color", "#5fae48"), 0.9)
    body = _cube((0, 0, s * 0.14), (s, s * 0.5, s * 0.28), stone, "base")
    top = _cube((0, 0, s * 0.3), (s * 1.04, s * 0.54, s * 0.07), grass, "top")
    _bevel(body, s * 0.02)
    return [body, top]


def mushroom(p, rng):
    s = p.get("size", 0.8)
    stem = make_material("Stem", "#efe6d2", 0.9)
    cap = make_material("Cap", p.get("color", "#d23b3b"), 0.8)
    dots = make_material("Dots", "#ffffff", 0.9)
    parts = [_cylinder((0, 0, s * 0.2), s * 0.09, s * 0.4, stem, 10, "stem")]
    parts.append(_sphere((0, 0, s * 0.42), s * 0.32, cap, 14, 8, (1, 1, 0.62), "cap"))
    for _ in range(5):
        a = rng.uniform(0, math.tau)
        r = s * rng.uniform(0.08, 0.2)
        parts.append(_sphere((math.cos(a) * r, math.sin(a) * r, s * 0.6), s * 0.045, dots, 6, 4, (1, 1, 0.5), "dot"))
    return parts


def chest(p, rng):
    s = p.get("size", 1.0)
    wood = make_material("ChestWood", p.get("color", "#8b5a2b"), 0.85)
    metal = make_material("ChestMetal", "#c9a227", 0.4, 0.8)
    base = _cube((0, 0, s * 0.2), (s, s * 0.6, s * 0.4), wood, "base")
    # Rounded lid: a cylinder lying along X, flattened vertically; its lower half hides inside the base.
    lid = _cylinder((0, 0, s * 0.4), s * 0.3, s, wood, 12, "lid", rot=(0, math.radians(90), 0))
    lid.scale = (0.6, 1.0, 1.0)  # local X maps to world Z after the 90 degree rotation
    lock = _cube((0, -s * 0.31, s * 0.4), (s * 0.12, s * 0.04, s * 0.14), metal, "lock")
    band1 = _cube((-s * 0.3, 0, s * 0.43), (s * 0.06, s * 0.64, s * 0.66), metal, "band")
    band2 = _cube((s * 0.3, 0, s * 0.43), (s * 0.06, s * 0.64, s * 0.66), metal, "band")
    return [base, lid, lock, band1, band2]


def fence(p, rng):
    s = p.get("size", 2.0)
    wood = make_material("FenceWood", p.get("color", "#9a6b3a"), 0.9)
    parts = []
    for x in (-0.45, 0.0, 0.45):
        parts.append(_cube((x * s, 0, s * 0.25), (s * 0.06, s * 0.06, s * 0.5), wood, "post"))
    for z in (0.18, 0.36):
        parts.append(_cube((0, 0, s * z), (s * 1.0, s * 0.04, s * 0.06), wood, "rail"))
    return parts


GENERATORS = {
    "crate": crate, "barrel": barrel, "rock": rock, "pine_tree": pine_tree, "round_tree": round_tree,
    "house": house, "tower": tower, "coin": coin, "gem": gem, "sword": sword, "platform": platform,
    "mushroom": mushroom, "chest": chest, "fence": fence,
}


def build(kind, params=None, seed=1, flat=True, bevel=0.0):
    if kind not in GENERATORS:
        raise ValueError(f"unknown kind '{kind}'. Available: {', '.join(sorted(GENERATORS))}")
    rng = random.Random(seed)
    clear_scene()
    parts = GENERATORS[kind](params or {}, rng)
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = _active()
    obj.name = kind
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if bevel > 0:
        _bevel(obj, bevel)
    # origin to bottom centre
    mn_z = min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box)
    bpy.context.scene.cursor.location = (obj.location.x, obj.location.y, mn_z)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.context.scene.cursor.location = (0, 0, 0)
    obj.location = (0, 0, 0)
    if flat:
        bpy.ops.object.shade_flat()
    else:
        bpy.ops.object.shade_smooth()
    return obj


def main():
    args = load_args()
    obj = build(args["kind"], args.get("params"), args.get("seed", 1),
                args.get("flat", True), args.get("bevel", 0.0))
    scale = args.get("scale")
    if scale:
        obj.scale = (scale, scale, scale)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    out = {"kind": args["kind"], "vertices": len(obj.data.vertices), "faces": len(obj.data.polygons),
           "dimensions": [round(v, 3) for v in obj.dimensions]}
    if args.get("output_blend"):
        os.makedirs(os.path.dirname(os.path.abspath(args["output_blend"])), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=args["output_blend"])
        out["blend"] = args["output_blend"]
    if args.get("output_glb"):
        export_model(args["output_glb"], selected_only=False, animations=False)
        out["glb"] = args["output_glb"]
    write_result(args, out)


if __name__ == "__main__":
    main()
