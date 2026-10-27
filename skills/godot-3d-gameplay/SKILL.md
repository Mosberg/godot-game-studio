---
name: godot-3d-gameplay
description: Build 3D games in Godot 4 - first/third-person controllers, camera rigs, lighting, environments, GridMap/glTF levels, navigation, physics props, and performance. Use for any 3D project.
---

# 3D gameplay

- Create with `godot_create_project(kind="3d")`; templates `player_fps`, `player_third_person`, `toon_3d`, `toon_outline_3d`.
- **Scene**: `WorldEnvironment` (sky, tonemap Filmic/ACES, SSAO/glow sparingly), one `DirectionalLight3D` with shadows (`directional_shadow_mode` PSSM 2 splits), props instanced from `.glb`.
- **Controller**: `CharacterBody3D`, capsule shape, `mouse_motion` -> yaw on body, pitch on head; `move_toward` accel; `get_gravity()`; `floor_stop_on_slope`. Capture mouse (`Input.mouse_mode = Input.MOUSE_MODE_CAPTURED`) and release on pause.
- **Third person**: `SpringArm3D` + `Camera3D` to avoid wall clipping, orbit with right stick/mouse, rotate model toward move direction with `lerp_angle`.
- **Levels**: block out with `CSGBox3D`/`GridMap`, then replace with Blender props (`blender_generate_asset`, `blender_export_for_godot`). Bake `LightmapGI` or use `VoxelGI`/SDFGI only if the GPU budget allows.
- **Navigation**: `NavigationRegion3D` + baked navmesh, `NavigationAgent3D` for AI; avoid per-frame `get_next_path_position` spam (use `target_reached`).
- **Physics**: `RigidBody3D` for props, `Area3D` triggers, layers as in 2D. Use `Jolt` physics (Project Settings > Physics > 3D > Physics Engine) for stability in 4.4+.
- **Performance**: `MultiMeshInstance3D` for foliage, visibility ranges/LOD, occlusion culling, shadow distance limits; profile with the Debugger > Monitors and a headless frame-time run.
