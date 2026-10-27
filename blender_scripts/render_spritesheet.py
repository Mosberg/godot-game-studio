"""Render a 3D model into 2D sprites (isometric / top-down / side) from N directions.
    blender -b [file.blend] --python render_spritesheet.py -- args.json
args.json:
  model        path to .glb/.gltf/.fbx/.obj (omit when the .blend is already open)
  out_dir      folder for PNG frames: dir{D}_f{F}.png
  directions   number of view directions around Z (1, 4, 8, 16)           default 8
  size         square frame size in px                                    default 128
  elevation    camera elevation in degrees (30 = classic dimetric, 90 = top-down, 0 = side)   default 30
  engine       eevee | cycles | workbench                                 default eevee
  samples      cycles/eevee samples                                       default 16
  frames       [start, end, step] animation frames to render, or null for a single still
  action       name of an action to play (armature animation), optional
  margin       framing margin multiplier                                  default 1.15
  light_energy sun strength                                               default 3.0
  ambient      world light strength                                       default 0.6
  outline_px   unused here (post-process outlines in the assets server)
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (clear_scene, import_model, load_args, mesh_objects, pick_engine,  # noqa: E402
                     world_bounds, write_result)


def setup_world(strength):
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (1, 1, 1, 1)
        bg.inputs[1].default_value = strength


def main():
    args = load_args()
    if args.get("model"):
        clear_scene()
        import_model(args["model"])
    scene = bpy.context.scene
    out_dir = os.path.abspath(args["out_dir"])
    os.makedirs(out_dir, exist_ok=True)
    size = int(args.get("size", 128))
    directions = int(args.get("directions", 8))
    # clamp just below 90 degrees: a camera looking exactly straight down has no defined "up" for TRACK_TO
    elevation = math.radians(min(float(args.get("elevation", 30)), 89.0))

    # playback setup
    action_name = args.get("action")
    if action_name:
        action = bpy.data.actions.get(action_name)
        if action is None:
            raise ValueError(f"action '{action_name}' not found. Available: {[a.name for a in bpy.data.actions]}")
        for obj in scene.objects:
            if obj.animation_data is None:
                obj.animation_data_create()
            if obj.type == "ARMATURE":
                obj.animation_data.action = action
    frames = args.get("frames")
    if frames:
        frame_list = list(range(int(frames[0]), int(frames[1]) + 1, int(frames[2] if len(frames) > 2 else 1)))
    else:
        frame_list = [scene.frame_current]

    # framing (union of bounds over the sampled frames)
    meshes = mesh_objects()
    mn, mx = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for f in frame_list[:: max(1, len(frame_list) // 6)] or frame_list:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        a, b = world_bounds(meshes)
        mn = Vector((min(mn.x, a.x), min(mn.y, a.y), min(mn.z, a.z)))
        mx = Vector((max(mx.x, b.x), max(mx.y, b.y), max(mx.z, b.z)))
    center = (mn + mx) / 2
    radius = (mx - mn).length / 2
    ortho = max(radius * 2 * float(args.get("margin", 1.15)), 0.01)

    # rig: pivot at the subject centre; camera + sun are children so lighting rotates with the view
    pivot = bpy.data.objects.new("SpritePivot", None)
    scene.collection.objects.link(pivot)
    pivot.location = center
    cam_data = bpy.data.cameras.new("SpriteCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho
    cam_data.clip_start = 0.01
    cam_data.clip_end = radius * 10 + 10
    cam = bpy.data.objects.new("SpriteCam", cam_data)
    scene.collection.objects.link(cam)
    cam.parent = pivot
    dist = radius * 3 + 2
    cam.location = (0, -math.cos(elevation) * dist, math.sin(elevation) * dist)
    track = cam.constraints.new("TRACK_TO")
    track.target = pivot
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = cam

    sun_data = bpy.data.lights.new("SpriteSun", "SUN")
    sun_data.energy = float(args.get("light_energy", 3.0))
    sun = bpy.data.objects.new("SpriteSun", sun_data)
    scene.collection.objects.link(sun)
    sun.parent = pivot
    sun.location = (-dist, -dist, dist)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    setup_world(float(args.get("ambient", 0.6)))

    # render settings
    r = scene.render
    r.resolution_x = r.resolution_y = size
    r.resolution_percentage = 100
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.engine = pick_engine(args.get("engine", "eevee"))
    samples = int(args.get("samples", 16))
    if r.engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = False
    elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = samples
    if hasattr(scene.view_settings, "view_transform"):
        try:
            scene.view_settings.view_transform = "Standard"
        except TypeError:
            pass

    written = []
    for d in range(directions):
        pivot.rotation_euler = (0, 0, math.tau * d / directions)
        for i, f in enumerate(frame_list):
            scene.frame_set(f)
            path = os.path.join(out_dir, f"dir{d}_f{i}.png")
            r.filepath = path
            bpy.ops.render.render(write_still=True)
            written.append(path)
    write_result(args, {"frames": written, "directions": directions, "frames_per_direction": len(frame_list),
                        "size": size, "engine": r.engine, "ortho_scale": ortho})


if __name__ == "__main__":
    main()
