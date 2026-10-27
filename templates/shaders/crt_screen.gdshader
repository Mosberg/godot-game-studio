shader_type canvas_item;
// CRT look: barrel curvature, scanlines, chromatic aberration, vignette.
// Put on a full-screen ColorRect in a high CanvasLayer (mouse_filter = Ignore).

uniform sampler2D screen_texture : hint_screen_texture, filter_linear;
uniform float curvature : hint_range(0.0, 0.5) = 0.12;
uniform float scanline_strength : hint_range(0.0, 1.0) = 0.25;
uniform float scanline_count = 240.0;
uniform float vignette : hint_range(0.0, 1.0) = 0.35;
uniform float chroma : hint_range(0.0, 0.01) = 0.0015;

vec2 curve_uv(vec2 uv) {
	uv = uv * 2.0 - 1.0;
	vec2 offset = abs(uv.yx) * curvature;
	uv = uv + uv * offset * offset;
	return uv * 0.5 + 0.5;
}

void fragment() {
	vec2 uv = curve_uv(SCREEN_UV);
	if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
		COLOR = vec4(0.0, 0.0, 0.0, 1.0);
	} else {
		float r = texture(screen_texture, uv + vec2(chroma, 0.0)).r;
		float g = texture(screen_texture, uv).g;
		float b = texture(screen_texture, uv - vec2(chroma, 0.0)).b;
		vec3 col = vec3(r, g, b);
		float scan = sin(uv.y * scanline_count * 3.14159265) * 0.5 + 0.5;
		col *= 1.0 - scanline_strength * (1.0 - scan);
		float vig = smoothstep(0.8, 0.2, distance(uv, vec2(0.5)));
		col *= mix(1.0, vig, vignette);
		COLOR = vec4(col, 1.0);
	}
}
