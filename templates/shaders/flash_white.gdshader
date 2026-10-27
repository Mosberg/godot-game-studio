shader_type canvas_item;
// Hit flash. Tween `flash_amount` 1 -> 0 from code:
//   sprite.material.set_shader_parameter("flash_amount", 1.0)
//   create_tween().tween_property(sprite.material, "shader_parameter/flash_amount", 0.0, 0.12)

uniform vec4 flash_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float flash_amount : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	COLOR = vec4(mix(COLOR.rgb, flash_color.rgb, flash_amount), COLOR.a);
}
