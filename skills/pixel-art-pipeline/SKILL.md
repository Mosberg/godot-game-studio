---
name: pixel-art-pipeline
description: End-to-end pixel-art asset pipeline using Pillow tools (and GIMP when needed) - palettes, pixelation, outlines, tiles, sprite sheets, animation previews and Godot import settings.
---

# Pixel-art pipeline

1. Decide: base resolution (e.g. 320x180), sprite size (16/32/64), palette (`asset_list_palettes` or `asset_extract_palette` from a reference).
2. Convert: `asset_pixelate(path, width=32, palette="sweetie16", remove_bg=True)` -> `asset_outline` -> `asset_trim`.
3. Tiles: `asset_seamless_tile` -> inspect the `_preview.png`.
4. Sheets: `asset_pack_spritesheet(frames)` -> `.atlas.json` (cell size, columns) -> in Godot `Sprite2D(hframes, vframes)` or SpriteFrames. Preview with `asset_make_gif`; review batches with `asset_contact_sheet`.
5. Godot: `godot_set_pixel_art_defaults` (Nearest filter, integer scale, snap 2D transforms to pixel), import with `Filter: Nearest`, no mipmaps, no compression artefacts (Lossless).
6. GIMP (optional): `.xcf` conversion (`gimp_convert`), layer export, or Script-Fu/Python-Fu filters via `gimp_run_script`. Prefer Pillow tools for repeatable pipelines.
7. Rules: 1-px outlines consistent in colour, no sub-pixel rotation, limited palette, light from top-left, separate sheet per animation set, consistent pivot (feet).
