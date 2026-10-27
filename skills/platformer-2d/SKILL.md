---
name: platformer-2d
description: Build a polished 2D platformer in Godot 4 - movement feel (coyote time, jump buffer, variable jump), tilemaps, enemies, hazards, checkpoints, camera, collectibles, juice. Use for any side-scroller.
---

# 2D platformer recipe

1. Project: `godot_create_project(kind="2d", pixel_art=true)`; add templates `player_platformer`, `state_machine`, `health_component`, `hitbox_2d`, `hurtbox_2d`, `enemy_patrol_2d`, `camera_shake`, `scene_manager`, `audio_manager`.
2. Input actions: left/right/jump/attack/pause with keyboard + gamepad.
3. **Feel numbers** (starting point for 16 px tiles @ 60 Hz): run speed 120-160 px/s, accel 800-1200, friction 1000, jump height ~3.5 tiles, gravity 900-1100, **coyote time 0.1 s**, **jump buffer 0.1 s**, variable jump (cut velocity x0.5 when released), max fall speed 300, apex gravity bonus. Template exposes all as `@export`.
4. Level: `TileMapLayer` ground with physics layer 1; one-way platforms; spikes (`Area2D` -> `hurtbox`); moving platforms via `AnimatableBody2D`; `Marker2D` checkpoints; kill-plane.
5. Enemies: patrol with ledge/wall detection (`RayCast2D`), contact damage via hurtbox, stomp detection (player falling & above enemy).
6. Camera: `Camera2D` with `position_smoothing`, limits from level bounds, look-ahead, shake on hit.
7. Juice: squash/stretch tween, dust particles, hit-stop 50 ms, flash shader, coin sounds with pitch ramp.
8. Test: `playtest_runner` scripts jumping across the first gap; `godot_capture_frames` to check visuals.

Pitfalls: tunnelling at high fall speed (clamp velocity), snapping to one-way platforms, forgetting `floor_snap_length`, animations driven from input instead of state.
