class_name PlatformerPlayer
extends CharacterBody2D
## Tight platformer movement: acceleration/friction, coyote time, jump buffering,
## variable jump height and optional extra jumps.
## Required input actions: move_left, move_right, jump

signal jumped
signal landed
signal facing_changed(direction: int)

@export_group("Run")
@export var max_speed: float = 180.0
@export var acceleration: float = 1400.0
@export var friction: float = 1800.0
@export_range(0.0, 1.0) var air_control: float = 0.7

@export_group("Jump")
@export var jump_height: float = 56.0 ## pixels
@export var time_to_apex: float = 0.38 ## seconds
@export var fall_gravity_multiplier: float = 1.6
@export var jump_cut_multiplier: float = 0.45
@export var coyote_time: float = 0.1
@export var jump_buffer_time: float = 0.1
@export var max_extra_jumps: int = 0
@export var terminal_velocity: float = 600.0

var facing: int = 1
var _gravity: float = 0.0
var _jump_velocity: float = 0.0
var _coyote_timer: float = 0.0
var _buffer_timer: float = 0.0
var _extra_jumps_left: int = 0
var _was_on_floor: bool = false


func _ready() -> void:
	recalculate_jump()


## Call again if you change jump_height or time_to_apex at runtime.
func recalculate_jump() -> void:
	_gravity = 2.0 * jump_height / (time_to_apex * time_to_apex)
	_jump_velocity = -2.0 * jump_height / time_to_apex


func _physics_process(delta: float) -> void:
	var direction: float = Input.get_axis(&"move_left", &"move_right")
	_apply_gravity(delta)
	_handle_jump(delta)
	_handle_horizontal(direction, delta)
	move_and_slide()
	_update_floor_state()


func _apply_gravity(delta: float) -> void:
	if is_on_floor():
		return
	var g: float = _gravity
	if velocity.y > 0.0:
		g *= fall_gravity_multiplier
	velocity.y = minf(velocity.y + g * delta, terminal_velocity)


func _handle_jump(delta: float) -> void:
	if is_on_floor():
		_coyote_timer = coyote_time
		_extra_jumps_left = max_extra_jumps
	else:
		_coyote_timer -= delta
	if Input.is_action_just_pressed(&"jump"):
		_buffer_timer = jump_buffer_time
	else:
		_buffer_timer -= delta
	if _buffer_timer > 0.0:
		if _coyote_timer > 0.0:
			_do_jump()
		elif _extra_jumps_left > 0:
			_extra_jumps_left -= 1
			_do_jump()
	# Variable jump height: releasing early cuts the rise.
	if Input.is_action_just_released(&"jump") and velocity.y < 0.0:
		velocity.y *= jump_cut_multiplier


func _do_jump() -> void:
	velocity.y = _jump_velocity
	_buffer_timer = 0.0
	_coyote_timer = 0.0
	jumped.emit()


func _handle_horizontal(direction: float, delta: float) -> void:
	var control: float = 1.0 if is_on_floor() else air_control
	if absf(direction) > 0.01:
		velocity.x = move_toward(velocity.x, direction * max_speed, acceleration * control * delta)
		var new_facing: int = 1 if direction > 0.0 else -1
		if new_facing != facing:
			facing = new_facing
			facing_changed.emit(facing)
	else:
		velocity.x = move_toward(velocity.x, 0.0, friction * control * delta)


func _update_floor_state() -> void:
	var on_floor: bool = is_on_floor()
	if on_floor and not _was_on_floor:
		landed.emit()
	_was_on_floor = on_floor
