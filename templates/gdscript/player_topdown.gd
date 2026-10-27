class_name TopDownPlayer
extends CharacterBody2D
## 8-direction top-down movement with acceleration and a dash.
## Required input actions: move_left, move_right, move_up, move_down, dash (optional)

signal dashed
signal facing_changed(direction: Vector2)

@export var max_speed: float = 110.0
@export var acceleration: float = 900.0
@export var friction: float = 1100.0
@export_group("Dash")
@export var dash_speed: float = 320.0
@export var dash_time: float = 0.14
@export var dash_cooldown: float = 0.5

var facing: Vector2 = Vector2.DOWN
var _dash_timer: float = 0.0
var _cooldown_timer: float = 0.0
var _dash_direction: Vector2 = Vector2.ZERO


func _physics_process(delta: float) -> void:
	_cooldown_timer = maxf(0.0, _cooldown_timer - delta)
	var input_vector: Vector2 = Input.get_vector(&"move_left", &"move_right", &"move_up", &"move_down")
	if input_vector != Vector2.ZERO:
		_set_facing(input_vector)

	if _dash_timer > 0.0:
		_dash_timer -= delta
		velocity = _dash_direction * dash_speed
	else:
		if InputMap.has_action(&"dash") and Input.is_action_just_pressed(&"dash") and _cooldown_timer <= 0.0:
			_start_dash(input_vector)
		if input_vector != Vector2.ZERO:
			velocity = velocity.move_toward(input_vector * max_speed, acceleration * delta)
		else:
			velocity = velocity.move_toward(Vector2.ZERO, friction * delta)
	move_and_slide()


func _start_dash(input_vector: Vector2) -> void:
	_dash_direction = input_vector if input_vector != Vector2.ZERO else facing
	_dash_timer = dash_time
	_cooldown_timer = dash_cooldown
	dashed.emit()


func _set_facing(direction: Vector2) -> void:
	var snapped_dir: Vector2 = direction.normalized()
	if snapped_dir.distance_to(facing) > 0.01:
		facing = snapped_dir
		facing_changed.emit(facing)
