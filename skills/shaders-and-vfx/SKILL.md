---
name: shaders-and-vfx
description: Godot shader and visual-effects cookbook - canvas_item and spatial shaders, particles, screen post-processing, outlines, dissolve, palette swap, CRT, toon, water, trails, screen shake and hit effects.
---

# Shaders & VFX

Library (`godot_add_template`): outline_2d, flash_white, dissolve, wave_2d, pixelate_screen, crt_screen, palette_swap, toon_3d, toon_outline_3d, scroll_uv.

## Minimal patterns
```glsl
shader_type canvas_item;
uniform vec4 flash_color : source_color = vec4(1.0);
uniform float flash : hint_range(0.0, 1.0) = 0.0;
void fragment() {
    vec4 c = texture(TEXTURE, UV);
    COLOR = vec4(mix(c.rgb, flash_color.rgb, flash), c.a);
}
```
Set at runtime: `sprite.material.set_shader_parameter("flash", 1.0)` then tween back. Give each instance its own material (`resource_local_to_scene = true`) to avoid shared flashes.

- **Screen effects**: `CanvasLayer` + full-rect `ColorRect` with `hint_screen_texture` shader.
- **Particles**: `GPUParticles2D` + `ParticleProcessMaterial`; one-shot bursts for hits (`emitting = true` then `one_shot`), colour ramp for fade, `local_coords=false` for trails.
- **3D toon**: `step()`ped NdotL in `light()`; outlines via inverted-hull second pass (`cull_front`, vertex expanded along normal).
- **Feel**: hit-stop, camera shake, squash/stretch, flash, slow-mo on kill - together they matter more than any shader.
- Validate via headless run + `godot_capture_frames`; mobile/web: keep shaders cheap and avoid `hint_screen_texture` stacks.
