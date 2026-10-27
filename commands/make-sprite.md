---
description: Make a game-ready 2D sprite or icon (AI via ComfyUI, 3D render via Blender, or procedural) and import it into Godot
argument-hint: <subject> [--size 32] [--palette pico8] [--source comfy|blender|auto]
---

Create a sprite: $ARGUMENTS

Follow the **technical-artist-2d** pipeline. Prefer `comfy_game_asset` when ComfyUI is up (`comfy_status`), otherwise `blender_generate_asset` + `blender_render_sprites`, otherwise draw a clean procedural placeholder with Pillow via `asset_*` tools. Remove background, pixelate/palette, outline, trim. Show me the result (view the PNG), save under `res://assets/sprites/`, run `godot_import`, and report the path plus Sprite2D settings.
