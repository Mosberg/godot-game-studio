shader_type canvas_item;
// Burn/dissolve. Assign a NoiseTexture2D to `noise_tex`, then tween `dissolve` from 0.0 to 1.0.

uniform sampler2D noise_tex : repeat_enable;
uniform float dissolve : hint_range(0.0, 1.0) = 0.0;
uniform vec4 edge_color : source_color = vec4(1.0, 0.55, 0.1, 1.0);
uniform float edge_width : hint_range(0.0, 0.3) = 0.06;

void fragment() {
	float n = texture(noise_tex, UV).r;
	float cut = dissolve * (1.0 + edge_width);
	if (n < cut - edge_width) {
		discard;
	} else if (n < cut) {
		COLOR.rgb = edge_color.rgb;
	}
}
