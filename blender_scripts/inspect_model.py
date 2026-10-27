"""Report on a model/blend: counts, dimensions, materials, animations, armatures, issues for game use.
    blender -b [file.blend] --python inspect_model.py -- args.json    (args: {model?, result_path?})
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import clear_scene, import_model, load_args, mesh_objects, world_bounds, write_result  # noqa: E402


def main():
    args = load_args()
    if args.get("model"):
        clear_scene()
        import_model(args["model"])
    meshes = mesh_objects()
    mn, mx = world_bounds(meshes)
    issues = []
    tris = 0
    for o in meshes:
        d = o.data
        t = sum(len(p.vertices) - 2 for p in d.polygons)
        tris += t
        if not d.uv_layers:
            issues.append(f"{o.name}: no UV map")
        if any(abs(s - 1.0) > 1e-4 for s in o.scale):
            issues.append(f"{o.name}: unapplied scale {tuple(round(s, 3) for s in o.scale)}")
        if not o.material_slots or not any(s.material for s in o.material_slots):
            issues.append(f"{o.name}: no material")
        if t > 20000:
            issues.append(f"{o.name}: {t} triangles (heavy for a game prop)")
    dims = [round(mx[i] - mn[i], 3) for i in range(3)]
    if max(dims) > 100 or max(dims) < 0.01:
        issues.append(f"suspicious size {dims} - check unit scale (1 unit = 1 metre in Godot)")
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    actions = []
    for a in bpy.data.actions:
        actions.append({"name": a.name, "frames": [round(a.frame_range[0]), round(a.frame_range[1])]})
    write_result(args, {
        "meshes": len(meshes), "triangles": tris, "dimensions_xyz": dims,
        "materials": sorted({s.material.name for o in meshes for s in o.material_slots if s.material}),
        "armatures": [{"name": a.name, "bones": len(a.data.bones)} for a in armatures],
        "actions": actions, "fps": bpy.context.scene.render.fps, "issues": issues,
    })


if __name__ == "__main__":
    main()
