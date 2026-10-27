shader_type spatial;
render_mode unshaded, cull_front;
// Inverted-hull outline. Use as the Next Pass of a mesh material (toon_3d.gdshader or any StandardMaterial3D).

uniform vec4 outline_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float outline_width : hint_range(0.0, 0.2) = 0.03;

void vertex() {
	VERTEX += NORMAL * outline_width;
}

void fragment() {
	ALBEDO = outline_color.rgb;
}
