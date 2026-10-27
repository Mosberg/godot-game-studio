shader_type canvas_item;
// Grayscale-to-palette swap. Draw sprites in grayscale; `palette` is a Wx(rows) image where each
// row is a ramp from dark (left) to light (right). Change `palette_row` (0..1) to recolour.
// Import the palette image with Filter = Nearest and no mipmaps.

uniform sampler2D palette : filter_nearest, repeat_disable;
uniform float palette_row : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	float luma = dot(COLOR.rgb, vec3(0.299, 0.587, 0.114));
	COLOR.rgb = texture(palette, vec2(luma, palette_row)).rgb;
}
