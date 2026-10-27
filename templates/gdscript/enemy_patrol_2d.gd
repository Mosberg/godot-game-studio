class_name PatrolEnemy2D
extends CharacterBody2D
## Side-view enemy: patrols, turns at walls and ledges, chases the player when close.
## Optional children: Sprite2D (flipped by direction), RayCast2D named "LedgeCheck"
## (positioned in front of and slightly below the feet, pointing down).
## The player must be in the "player" group.

signal player_spotted(player: Node2D)
signal player_lost

@export var patrol_speed: float = 40.0
@export var chase_speed: float = 75.0
@export var detect_range: float = 96.0
@export var lose_range: float = 140.0
@export var turn_at_ledges: bool = true
@export var can_chase: bool = true

var direction: int = 1
var target: Node2D = null

var _gravity: float = float(ProjectSettings.get_setting("physics/2d/default_gravity"))
@onready var _ledge_check: RayCast2D = get_node_or_null("LedgeCheck") as RayCast2D
@onready var _sprite: Sprite2D = get_node_or_null("Sprite2D") as Sprite2D


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y += _gravity * delta
	_update_target()
	var speed: float = patrol_speed
	if target != null:
		var dx: float = target.global_position.x - global_position.x
		if absf(dx) > 4.0:
			_set_direction(1 if dx > 0.0 else -1)
		speed = chase_speed
	elif _should_turn():
		_set_direction(-direction)
	velocity.x = direction * speed
	move_and_slide()


func _should_turn() -> bool:
	if is_on_wall():
		return true
	if turn_at_ledges and _ledge_check != null and is_on_floor():
		_ledge_check.force_raycast_update()
		return not _ledge_check.is_colliding()
	return false


func _set_direction(new_direction: int) -> void:
	direction = new_direction
	if _sprite != null:
		_sprite.flip_h = direction < 0
	if _ledge_check != null:
		_ledge_check.position.x = absf(_ledge_check.position.x) * direction


func _update_target() -> void:
	if not can_chase:
		return
	var player: Node2D = get_tree().get_first_node_in_group(&"player") as Node2D
	if player == null:
		return
	var distance: float = global_position.distance_to(player.global_position)
	if target == null and distance <= detect_range:
		target = player
		player_spotted.emit(player)
	elif target != null and distance > lose_range:
		target = null
		player_lost.emit()
