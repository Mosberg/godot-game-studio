---
description: Art pass on the current game - generate or upgrade sprites, tiles, backgrounds, UI and VFX with a consistent style
argument-hint: <style direction, e.g. "16-color gameboy palette, 16x16 tiles">
---

Run an art pass with direction: $ARGUMENTS

Inventory current placeholders (`godot_search` for ColorRect/Polygon2D/icon.svg usage), define the style guide (resolution, palette, outline) in `art_src/style.md`, produce assets with the technical-artist-2d / comfyui-operator / blender-3d-artist pipelines, swap them into scenes, add shader/VFX polish, then capture frames before/after and summarise.
