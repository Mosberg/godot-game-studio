shader_type canvas_item;
// Endlessly scrolling texture (parallax layers, conveyor belts, clouds).
// Set the node's CanvasItem > Texture > Repeat = Enabled so the texture wraps.

uniform vec2 scroll_speed = vec2(0.05, 0.0);

void fragment() {
	COLOR = texture(TEXTURE, UV + scroll_speed * TIME);
}
