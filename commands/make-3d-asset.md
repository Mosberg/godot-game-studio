---
description: Make a 3D prop or character with Blender and export it to the Godot project as glTF
argument-hint: <description> [--kind crate|barrel|rock|house|...] [--lowpoly]
---

Create a 3D asset: $ARGUMENTS

Use the **blender-3d-artist** workflow. If the request matches a generator (`blender_list_asset_kinds`) use `blender_generate_asset`; otherwise write bpy via `blender_run_python` or the live bridge, take viewport screenshots to verify, then `blender_inspect` and `blender_export_for_godot`. Run `godot_import`, instance it in a test scene, capture a frame, and report triangle count, size and the res:// path.
