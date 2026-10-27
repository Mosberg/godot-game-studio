class_name HealthComponent
extends Node
## Reusable health. Add as a child of any actor; connect to `died`, `damaged`, `health_changed`.

signal health_changed(current: int, maximum: int)
signal damaged(amount: int, source: Node)
signal healed(amount: int)
signal died

@export var max_health: int = 100
## Seconds of invulnerability after taking damage (0 = none).
@export var invulnerable_time: float = 0.0
@export var start_full: bool = true

var current_health: int = 0
var is_dead: bool = false
var _invulnerable_until_ms: int = 0


func _ready() -> void:
	if start_full:
		current_health = max_health
	health_changed.emit(current_health, max_health)


func is_invulnerable() -> bool:
	return Time.get_ticks_msec() < _invulnerable_until_ms


func take_damage(amount: int, source: Node = null) -> void:
	if is_dead or amount <= 0 or is_invulnerable():
		return
	current_health = maxi(0, current_health - amount)
	if invulnerable_time > 0.0:
		_invulnerable_until_ms = Time.get_ticks_msec() + int(invulnerable_time * 1000.0)
	damaged.emit(amount, source)
	health_changed.emit(current_health, max_health)
	if current_health == 0:
		is_dead = true
		died.emit()


func heal(amount: int) -> void:
	if is_dead or amount <= 0:
		return
	var before: int = current_health
	current_health = mini(max_health, current_health + amount)
	if current_health != before:
		healed.emit(current_health - before)
		health_changed.emit(current_health, max_health)


func revive(health: int = -1) -> void:
	is_dead = false
	current_health = max_health if health < 0 else clampi(health, 1, max_health)
	health_changed.emit(current_health, max_health)


func get_ratio() -> float:
	return 0.0 if max_health <= 0 else float(current_health) / float(max_health)
