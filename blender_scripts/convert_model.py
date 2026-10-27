"""Import any supported model, optionally clean it, export in another format.
    blender -b --python convert_model.py -- args.json
args.json: {input, output, selected_only?, animations?, scale?, apply_modifiers?, merge_distance?,
            decimate_ratio?, triangulate?, origin: "bottom"|"center"|null, result_path?}
"""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (clear_scene, export_model, import_model, load_args, mesh_objects,  # noqa: E402
                     world_bounds, write_result)


def main():
    args = load_args()
    clear_scene()
    import_model(args["input"])
    meshes = mesh_objects()
    stats_before = sum(len(o.data.polygons) for o in meshes)

    scale = args.get("scale")
    if scale and scale != 1:
        for o in bpy.context.scene.objects:
            if o.parent is None:
                o.scale = (o.scale[0] * scale, o.scale[1] * scale, o.scale[2] * scale)
        bpy.context.view_layer.update()

    for o in meshes:
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        if args.get("apply_modifiers", True):
            for mod in list(o.modifiers):
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError:
                    pass
        if args.get("merge_distance"):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.remove_doubles(threshold=float(args["merge_distance"]))
            bpy.ops.object.mode_set(mode="OBJECT")
        if args.get("decimate_ratio") and 0 < float(args["decimate_ratio"]) < 1:
            mod = o.modifiers.new("Decimate", "DECIMATE")
            mod.ratio = float(args["decimate_ratio"])
            bpy.ops.object.modifier_apply(modifier=mod.name)
        if args.get("triangulate", False):
            mod = o.modifiers.new("Tri", "TRIANGULATE")
            bpy.ops.object.modifier_apply(modifier=mod.name)

    origin = args.get("origin")
    if origin:
        mn, mx = world_bounds(mesh_objects())
        z = mn.z if origin == "bottom" else (mn.z + mx.z) / 2
        target = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, z))
        for o in bpy.context.scene.objects:
            if o.parent is None:
                o.location -= target

    bpy.ops.object.select_all(action="DESELECT")
    export_model(args["output"], selected_only=args.get("selected_only", False),
                 animations=args.get("animations", True), apply_modifiers=True)
    meshes = mesh_objects()
    write_result(args, {"output": args["output"],
                        "bytes": os.path.getsize(args["output"]) if os.path.exists(args["output"]) else 0,
                        "triangles_before": stats_before,
                        "faces_after": sum(len(o.data.polygons) for o in meshes),
                        "objects": len(bpy.context.scene.objects)})


if __name__ == "__main__":
    main()
