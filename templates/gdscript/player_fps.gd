class_name FPSPlayer
extends CharacterBody3D
## First-person controller. Scene layout:
##   FPSPlayer (CharacterBody3D) + CollisionShape3D (capsule)
##   └─ Head (Node3D, y ≈ 1.6)
##      └─ Camera3D
## Required input actions: move_left, move_right, move_forward, move_back, jump, sprint (optional)

@export var walk_speed: float = 5.0
@export var sprint_speed: float = 8.0
@export var acceleration: float = 12.0
@export var air_acceleration: float = 3.0
@export var jump_velocity: float = 4.8
@export_range(0.0005, 0.01) var mouse_sensitivity: float = 0.0025
@export var capture_mouse_on_start: bool = true

@onready var head: Node3D = $Head
@onready var camera: Camera3D = $Head/Camera3D

var _gravity: float = float(ProjectSettings.get_setting("physics/3d/default_gravity"))


func _ready() -> void:
	if capture_mouse_on_start:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion: InputEventMouseMotion = event
		rotate_y(-motion.relative.x * mouse_sensitivity)
		head.rotate_x(-motion.relative.y * mouse_sensitivity)
		head.rotation.x = clampf(head.rotation.x, deg_to_rad(-89.0), deg_to_rad(89.0))
	elif event.is_action_pressed(&"ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton:
		var click: InputEventMouseButton = event
		if click.pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= _gravity * delta
	elif Input.is_action_just_pressed(&"jump"):
		velocity.y = jump_velocity

	var input_dir: Vector2 = Input.get_vector(&"move_left", &"move_right", &"move_forward", &"move_back")
	var direction: Vector3 = (transform.basis * Vector3(input_dir.x, 0.0, input_dir.y)).normalized()
	var wants_sprint: bool = InputMap.has_action(&"sprint") and Input.is_action_pressed(&"sprint")
	var target_speed: float = sprint_speed if wants_sprint else walk_speed
	var accel: float = acceleration if is_on_floor() else air_acceleration
	var target: Vector3 = direction * target_speed
	velocity.x = move_toward(velocity.x, target.x, accel * target_speed * delta)
	velocity.z = move_toward(velocity.z, target.z, accel * target_speed * delta)
	move_and_slide()
