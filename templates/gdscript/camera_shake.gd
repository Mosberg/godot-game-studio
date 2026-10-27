class_name ShakeCamera2D
extends Camera2D
## Trauma-based screen shake. Call add_trauma(0.3) for a hit, 0.8 for an explosion.
## Joins the "shake_camera" group; other scripts can do:
##   get_tree().call_group("shake_camera", "add_trauma", 0.4)

@export var decay: float = 1.6
@export var max_offset: Vector2 = Vector2(10.0, 7.0)
@export var max_roll: float = 0.04
@export var noise_speed: float = 55.0

var trauma: float = 0.0
var _noise: FastNoiseLite = FastNoiseLite.new()
var _t: float = 0.0


func _ready() -> void:
	add_to_group(&"shake_camera")
	_noise.seed = randi()
	_noise.frequency = 0.6


func add_trauma(amount: float) -> void:
	trauma = clampf(trauma + amount, 0.0, 1.0)


func _process(delta: float) -> void:
	if trauma <= 0.0:
		if offset != Vector2.ZERO or rotation != 0.0:
			offset = Vector2.ZERO
			rotation = 0.0
		return
	trauma = maxf(trauma - decay * delta, 0.0)
	_t += delta * noise_speed
	var shake: float = trauma * trauma
	offset = Vector2(
		max_offset.x * shake * _noise.get_noise_2d(_t, 0.0),
		max_offset.y * shake * _noise.get_noise_2d(0.0, _t))
	rotation = max_roll * shake * _noise.get_noise_2d(_t, 100.0)
