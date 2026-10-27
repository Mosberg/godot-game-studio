class_name ThirdPersonPlayer
extends CharacterBody3D
## Third-person controller with a camera-relative move direction.
## Scene layout:
##   ThirdPersonPlayer (CharacterBody3D) + CollisionShape3D
##   ├─ Model (Node3D)              <- rotates toward movement
##   └─ CameraPivot (Node3D, y ≈ 1.5)
##      └─ SpringArm3D (spring_length ≈ 4)
##         └─ Camera3D
## Required input actions: move_left, move_right, move_forward, move_back, jump

@export var move_speed: float = 5.5
@export var acceleration: float = 14.0
@export var turn_speed: float = 10.0
@export var jump_velocity: float = 5.0
@export_range(0.0005, 0.01) var mouse_sensitivity: float = 0.003
@export var pitch_limits: Vector2 = Vector2(-60.0, 35.0)

@onready var model: Node3D = $Model
@onready var camera_pivot: Node3D = $CameraPivot

var _gravity: float = float(ProjectSettings.get_setting("physics/3d/default_gravity"))


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion: InputEventMouseMotion = event
		camera_pivot.rotate_y(-motion.relative.x * mouse_sensitivity)
		camera_pivot.rotation.x = clampf(
			camera_pivot.rotation.x - motion.relative.y * mouse_sensitivity,
			deg_to_rad(pitch_limits.x), deg_to_rad(pitch_limits.y))
	elif event.is_action_pressed(&"ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= _gravity * delta
	elif Input.is_action_just_pressed(&"jump"):
		velocity.y = jump_velocity

	var input_dir: Vector2 = Input.get_vector(&"move_left", &"move_right", &"move_forward", &"move_back")
	var yaw_basis: Basis = Basis(Vector3.UP, camera_pivot.global_rotation.y)
	var direction: Vector3 = (yaw_basis * Vector3(input_dir.x, 0.0, input_dir.y)).normalized()
	var target: Vector3 = direction * move_speed
	velocity.x = move_toward(velocity.x, target.x, acceleration * delta * move_speed)
	velocity.z = move_toward(velocity.z, target.z, acceleration * delta * move_speed)

	if direction.length() > 0.1:
		var target_yaw: float = atan2(-direction.x, -direction.z)
		model.rotation.y = lerp_angle(model.rotation.y, target_yaw, clampf(turn_speed * delta, 0.0, 1.0))
	move_and_slide()
