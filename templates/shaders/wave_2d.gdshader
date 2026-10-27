shader_type canvas_item;
// Wavy distortion for water, banners, heat haze. Keeps the node's modulate colour.

uniform float amplitude : hint_range(0.0, 0.1) = 0.01;
uniform float frequency = 20.0;
uniform float speed = 2.0;

varying vec4 v_modulate;

void vertex() {
	v_modulate = COLOR;
}

void fragment() {
	vec2 uv = UV;
	uv.x += sin(uv.y * frequency + TIME * speed) * amplitude;
	COLOR = texture(TEXTURE, uv) * v_modulate;
}
