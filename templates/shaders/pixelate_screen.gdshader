shader_type canvas_item;
// Full-screen pixelation. Put on a ColorRect (full rect) inside a high CanvasLayer.
// mouse_filter must be Ignore on that ColorRect.

uniform sampler2D screen_texture : hint_screen_texture, filter_nearest;
uniform float pixel_size : hint_range(1.0, 32.0, 1.0) = 4.0;

void fragment() {
	vec2 res = 1.0 / SCREEN_PIXEL_SIZE;
	vec2 uv = floor(SCREEN_UV * res / pixel_size) * pixel_size / res;
	COLOR = texture(screen_texture, uv);
}
