shader_type canvas_item;
// Sprite outline. Leave 1-2 px of transparent padding around the art so the outline is not clipped.

uniform vec4 outline_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float outline_width : hint_range(0.0, 8.0, 1.0) = 1.0;
uniform bool enabled = true;

void fragment() {
	vec4 base = COLOR;
	if (enabled) {
		vec2 size = TEXTURE_PIXEL_SIZE * outline_width;
		float a = 0.0;
		a = max(a, texture(TEXTURE, UV + vec2(size.x, 0.0)).a);
		a = max(a, texture(TEXTURE, UV + vec2(-size.x, 0.0)).a);
		a = max(a, texture(TEXTURE, UV + vec2(0.0, size.y)).a);
		a = max(a, texture(TEXTURE, UV + vec2(0.0, -size.y)).a);
		vec4 outline = vec4(outline_color.rgb, outline_color.a * a);
		COLOR = mix(outline, base, base.a);
	}
}
