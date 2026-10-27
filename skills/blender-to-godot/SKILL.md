---
name: blender-to-godot
description: Blender-to-Godot 3D asset pipeline - modelling conventions, glTF export, import hints, materials, animations, collision, LODs, sprite-sheet baking, and the Blender MCP tools.
---

# Blender -> Godot

**Tools**: `blender_info`, `blender_generate_asset`, `blender_run_python`, `blender_inspect`, `blender_convert`, `blender_export_for_godot`, `blender_render_sprites`, `blender_render_still`, and the live bridge (`blender_install_addon`, `blender_bridge_*`, `blender_start_headless_bridge`).

## Conventions
- Metric units, Z-up in Blender; glTF 2.0 (`.glb`) is the exchange format (Godot's best-supported). Apply transforms; origin at base.
- Materials: Principled BSDF -> base colour/metal/rough/normal/emission. Bake procedural textures before export.
- Naming suffixes in Godot import: `-col`, `-convcol`, `-colonly`, `-convcolonly`, `-navmesh`, `-occ`, `-noimp`; animation suffixes `-loop`/`-cycle`.
- Rigs: single armature, <= 4 weights per vertex, deform bones only; actions named `idle/walk/run/attack`.
- Budget: props <5k tris; characters <15k; use `blender_convert(decimate_ratio=0.5)` for LODs.

## Flow
1. Make/obtain the model -> `blender_inspect` and fix issues -> `blender_export_for_godot(input, project)`.
2. `godot_import`; instance the `.glb`, add collision/script in an inherited scene (don't edit the glb scene directly).
3. Screenshot in Godot (`godot_capture_frames`) to confirm scale/materials.
4. For 2D games from 3D models: `blender_render_sprites` with directions 4/8, elevation 30, size 96-128, then pixelate (`asset_pixelate`, palette) and pack.
