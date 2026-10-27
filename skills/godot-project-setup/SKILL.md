---
name: godot-project-setup
description: Create and configure a new Godot 4 project the right way - folder layout, project settings, input map, autoloads, renderer, pixel-art defaults, git hygiene. Use when starting a game or fixing a messy project.
---

# Godot project setup

1. `godot_info` to confirm the engine (4.7.2 stable is current; .NET build only if C# is wanted).
2. `godot_create_project(path, name, kind="2d"|"3d", renderer, pixel_art, dotnet)`.
   - Renderer: **Forward+** (desktop, best 3D), **Mobile** (mobile/VR), **Compatibility** (web, old GPUs such as GTX 1070-era machines are fine with Forward+/Mobile, but pick Compatibility for web export).
   - Pixel art: `pixel_art=true` -> Nearest filter, integer scaling, 320x180-style viewport, `canvas_items` stretch.
3. Standard layout (created for you):
   ```
   res://scenes/ (levels, ui, actors)   res://scripts/   res://assets/{sprites,models,audio,fonts}
   res://autoload/   res://resources/   res://shaders/   res://tests/   docs/   art_src/
   ```
4. Input: `godot_add_input_actions_bulk` with tokens `key:Space`, `key:A`, `joy_button:0`, `joy_axis:0:-1`, `mouse:1`. Always map keyboard **and** gamepad. Names: `move_left move_right move_up move_down jump attack interact pause`.
5. Autoloads (`godot_add_autoload`): `Events` (signal bus), `GameState`, `AudioManager`, `SceneManager` (templates exist). Keep to <5.
6. Layer names (`godot_set_layer_names`): world, player, enemy, player_hurtbox, enemy_hurtbox, pickup, trigger.
7. Git: `.gitignore` already excludes `.godot/` and builds; commit `*.import` files. Use `.gitattributes` LFS for large binaries.
8. Verify: `godot_validate_project` then `godot_run_project(seconds=5)`.

Per-project guidance is written to `CLAUDE.md` in the project - read it first on every session.
