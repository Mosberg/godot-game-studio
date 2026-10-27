---
name: comfyui-game-art
description: Generate and refine game art with a local ComfyUI - presets, prompts, LoRAs, workflows, upscaling, consistency across assets, and cleanup into Godot-ready PNGs. Use with ComfyUI running.
---

# ComfyUI game art

- **Check**: `comfy_status`, `comfy_list_models`. No model installed? Tell the user which kind to download (SDXL or SD1.5 checkpoint, a pixel-art LoRA); ComfyUI's Manager can fetch them.
- **Assets**: `comfy_game_asset(preset=sprite|icon|tile|portrait|background|concept, subject, output_dir, style, palette, pixel_size)`.
- **Consistency**: fix the checkpoint, LoRA stack, style suffix and (for series) reuse seeds + `img2img` at denoise 0.35-0.5 from an approved reference; keep a `art_src/style.md`.
- **Pixel art**: generate big, then `pixel_size` 32/64 + palette snap; hand-fix with the assets tools. AI pixel art rarely lands on a clean grid, so downscaling with box filter + palette is the reliable route.
- **Animation frames**: img2img from the idle frame with small pose prompts, or render a 3D model via Blender; AI frame-to-frame coherence is weak - verify with `asset_make_gif`.
- **Custom workflows**: export "Save (API Format)" to the workflows folder; `comfy_run_workflow(name, overrides={"6.text": ...})`.
- **GPU sharing**: `comfy_free_memory` before heavy Godot/Blender work.
- **Provenance**: log prompt/seed/model in `art_src/prompts.md`; check model licences and store AI-disclosure rules.
