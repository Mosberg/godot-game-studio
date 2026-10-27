"""Helpers shared by the Blender-side scripts (they run INSIDE Blender with `--python`)."""
import json
import math
import os
import sys

import bpy


def load_args():
    """Reads the JSON file path passed after `--` and returns the parsed dict."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        return {}
    with open(argv[0], "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_result(args, data):
    """Scripts report back through a JSON file (path in args['result_path'])."""
    path = args.get("result_path")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
    print("@@RESULT@@" + json.dumps(data, default=str))


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def hex_to_rgba(value, alpha=1.0):
    if isinstance(value, (list, tuple)):
        vals = list(value) + [1.0] * (4 - len(value))
        return tuple(vals[:4])
    value = value.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c):  # sRGB -> linear, Blender colours are linear
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (lin(r), lin(g), lin(b), alpha)


def make_material(name, color="#cccccc", roughness=0.8, metallic=0.0, emission=None, emission_strength=2.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    rgba = hex_to_rgba(color)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission:
            key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
            bsdf.inputs[key].default_value = hex_to_rgba(emission)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    mat.diffuse_color = rgba
    return mat


def mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def world_bounds(objects):
    """Axis-aligned world bounding box (min, max) of the given objects."""
    from mathutils import Vector
    corners = []
    for o in objects:
        for c in o.bound_box:
            corners.append(o.matrix_world @ Vector(c))
    if not corners:
        return Vector((-1, -1, -1)), Vector((1, 1, 1))
    mn = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    mx = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return mn, mx


def import_model(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=path)
        else:
            bpy.ops.import_scene.obj(filepath=path)
    elif ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_import"):
            bpy.ops.wm.stl_import(filepath=path)
        else:
            bpy.ops.import_mesh.stl(filepath=path)
    elif ext == ".ply":
        if hasattr(bpy.ops.wm, "ply_import"):
            bpy.ops.wm.ply_import(filepath=path)
        else:
            bpy.ops.import_mesh.ply(filepath=path)
    elif ext == ".dae":
        bpy.ops.wm.collada_import(filepath=path)
    elif ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        raise ValueError(f"unsupported import format: {ext}")


def export_model(path, selected_only=False, animations=True, apply_modifiers=True):
    ext = os.path.splitext(path)[1].lower()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if ext in (".glb", ".gltf"):
        bpy.ops.export_scene.gltf(
            filepath=path, export_format="GLB" if ext == ".glb" else "GLTF_SEPARATE",
            use_selection=selected_only, export_apply=apply_modifiers, export_yup=True,
            export_animations=animations, export_cameras=False, export_lights=False)
    elif ext == ".fbx":
        bpy.ops.export_scene.fbx(filepath=path, use_selection=selected_only,
                                 apply_scale_options="FBX_SCALE_ALL", bake_anim=animations)
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_export"):
            bpy.ops.wm.obj_export(filepath=path, export_selected_objects=selected_only)
        else:
            bpy.ops.export_scene.obj(filepath=path, use_selection=selected_only)
    elif ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_export"):
            bpy.ops.wm.stl_export(filepath=path, export_selected_objects=selected_only)
        else:
            bpy.ops.export_mesh.stl(filepath=path, use_selection=selected_only)
    elif ext == ".blend":
        bpy.ops.wm.save_as_mainfile(filepath=path)
    else:
        raise ValueError(f"unsupported export format: {ext}")


def pick_engine(name):
    items = [i.identifier for i in bpy.context.scene.render.bl_rna.properties["engine"].enum_items]
    up = (name or "").upper()
    if up in ("EEVEE", "BLENDER_EEVEE"):
        for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            if cand in items:
                return cand
    if up == "WORKBENCH":
        return "BLENDER_WORKBENCH"
    if up in items:
        return up
    return "CYCLES" if "CYCLES" in items else items[0]
