shader_type spatial;
render_mode diffuse_toon, specular_toon;
// Cel-shaded surface. Pair with toon_outline_3d.gdshader as the material's Next Pass for an outline.

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D albedo_tex : source_color, filter_nearest;
uniform float roughness : hint_range(0.0, 1.0) = 0.8;
uniform float rim_amount : hint_range(0.0, 1.0) = 0.3;

void fragment() {
	ALBEDO = albedo.rgb * texture(albedo_tex, UV).rgb;
	ROUGHNESS = roughness;
	RIM = rim_amount;
	RIM_TINT = 0.5;
}
